"""One agent's runtime (Blueprint §10.4, INFERENCE_STRATEGY §3, CONTEXT_MEMORY_STRATEGY, D-49).

For each observation packet the runtime:

1. updates its Working Set (deduplicated, expired by modality) and its memory (speech addressed
   to it only, D-12);
2. derives **triggers**: decisions are event-driven (T14), never one per tick;
3. updates its **cognition level** (C0/C1/C2, with hysteresis);
4. if a decision is needed and none is pending (**one pending request per agent**), assembles
   a fresh context within its tier budget and asks its policy: a routine (C0), templates (C1),
   the model through the gateway (C2 with a model), or the Demo policy (C2 without one, D-21);
5. turns the answer into ``action_request`` messages and writes a ``decision_record``.

Results come back from the host's action gate. A ``STALE_OBSERVATION`` or ``TARGET_UNKNOWN``
rejection triggers one replan from the latest observation (T27); a rejected promise is released.

The runtime sees only its own packets, its own memory and the public part of its persona.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from range_service.comms import disclosure

from . import guardrails
from .cognition import FAR_FROM_FOCAL_M, LEVELS, NEAR_FOCAL_M, CognitionLevel, Signals
from .context import OUTPUT_CAPS, Assembled, ContextAssembler, Identity
from .gateway import ModelGateway
from .memory import AgentMemory
from .policy_demo import NpcTemplatePolicy, Proposal, RobotDemoPolicy, RoutinePolicy, is_farewell
from .tokenizer import ApproxTokenizer, Tokenizer
from .working_set import Perceived, WorkingSet

PARTNER_SILENCE_END_MS = 20_000     # a conversation ends after this long without an exchange
EXPRESSION_MIN_GAP_TICKS = 20       # the host refuses expression changes faster than 3 per second (D-14)
REPLAN_REASONS = frozenset({"STALE_OBSERVATION", "TARGET_UNKNOWN"})
_WORD = re.compile(r"[a-zà-ÿ']{4,}")
STOPWORDS = frozenset({"about", "there", "where", "what", "that", "this", "with", "your", "have", "from", "they",
                       "would", "could", "should", "thanks", "tell", "please"})


def topics_of(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in STOPWORDS}


@dataclass
class Conversation:
    partner: str | None = None
    since_ms: int = 0
    last_exchange_ms: int = 0
    turns: int = 0
    closing: bool = False
    participants: set[str] = field(default_factory=set)
    topics: set[str] = field(default_factory=set)
    scopes: set[str] = field(default_factory=set)
    first_event_id: str | None = None


@dataclass
class DecisionJob:
    """A decision to make: built synchronously, answered by ``AgentRuntime.decide``."""

    decision_id: str
    tick: int
    triggers: list[str]
    policy: str
    tier: str
    level: str
    assembled: Assembled | None
    proposals: list[Proposal] | None      # set for ROUTINE/TEMPLATE/DEMO; None when the model decides
    demo_hint: str | None
    prefix_key: str | None = None         # the persona prefix of this tier (T5/T6), for the provider


class AgentRuntime:
    def __init__(self, agent_id: str, *, persona: dict[str, Any], body: dict[str, Any], directive: str,
                 expressions: list[str], setting: list[str], task: str | None = None,
                 task_goal: dict[str, float] | None = None, focal: bool = False, pin: bool = False,
                 controller: str = "SCRIPTED", gateway: ModelGateway | None = None,
                 tokenizer: Tokenizer | None = None, expression_gestures: dict[str, str] | None = None,
                 own_private_goal: str | None = None, prewarm: bool = True) -> None:
        self.agent_id = agent_id
        self.body = body
        self.focal = focal
        self.controller = controller
        self.gateway = gateway
        # G3c-1: an NPC with a gateway decides through the model at C1 and C2 (C0 stays a routine).
        self.npc_model = gateway is not None and not focal
        if own_private_goal and not self.npc_model:
            raise ValueError("only a model-driven NPC gets its own private goal in its prompt (D-51)")
        self.prewarm_enabled = prewarm and self.npc_model
        self.expressions = sorted(expressions)
        # Each available expression's gesture, if it has one (from the catalog).
        self.expression_gestures = {k: v for k, v in (expression_gestures or {}).items() if k in self.expressions}
        self.setting = list(setting)
        self.task = task
        self.task_goal = task_goal
        self.allowed_actions = [a for a in persona["allowed_actions"]]
        self.robot = persona["role"] == "expo_assistant"
        # Only the public part of the persona (D-13): never its private goal or style.
        self.identity = Identity(agent_id, persona["display_name"], persona["role"], persona["public_goal"], directive,
                                 list(persona.get("knows", [])), _body_summary(body, expressions),
                                 own_private_goal=own_private_goal or None)
        self.cognition = CognitionLevel(persona["cognition_level"], pinned=pin or focal)
        self.memory = AgentMemory(agent_id)
        self.ws = WorkingSet(agent_id)
        self.conversation = Conversation()
        self.perceived = Perceived()
        self.tokenizer = tokenizer or ApproxTokenizer()
        self.pending = False
        self.records: list[dict[str, Any]] = []
        self.prompts: list[dict[str, str]] = []       # assembled contexts, for leak checks and the viewer
        self.results: dict[str, dict[str, Any]] = {}
        self.stats = {"decisions": 0, "requests": 0, "fallbacks": 0, "replans": 0, "rejected": 0, "skipped_pending": 0}
        self._queued: list[str] = []
        self._started = False
        self._decisions = 0
        self._requests = 0
        self._sent: dict[str, dict[str, Any]] = {}     # request id -> {"action", "commitment_id", "replanned"}
        self._replan_due = False
        self._replanned_decisions: set[str] = set()
        self._last_express_tick = -10_000
        self.waved_back: set[str] = set()     # NPC templates wave back once per person
        # Persona prefixes (T5/T6) and promotion latency (G3c-1). Wall-clock values live only in
        # these evaluator records, never in anything sent to the world (stepped runs stay exact).
        self._prefixes: dict[str, tuple[str, str]] = {}      # tier -> (key, prefix)
        self.prewarm_wanted: list[tuple[str, str, str]] = []  # (tier, key, prefix) for the sidecar to warm
        self._prewarm_asked: set[str] = set()
        self.promotions: list[dict[str, Any]] = []
        self._open_promotions: list[dict[str, Any]] = []
        for fact in persona.get("knows", []):
            self.memory.add("WORLD_KNOWLEDGE", fact, now_ms=0, status="OBSERVED", source_class="OBSERVED",
                            importance="NORMAL", tags=topics_of(fact))

    # ---------- capabilities ----------

    def body_supports_gesture(self, gesture: str) -> bool:
        return bool(self.body["capabilities"]["can_gesture"]) and gesture in self.body["gestures"]

    @property
    def tier(self) -> str:
        if self.focal:
            return "FOCAL"
        return {"C2": "C2", "C1": "C1", "C0": "C0"}[self.cognition.level]

    # ---------- perception ----------

    def observe(self, packet: dict[str, Any]) -> DecisionJob | None:
        """Take in one packet. Returns a decision job if one is needed now, else None."""
        if packet["observer_id"] != self.agent_id:
            raise ValueError("a runtime only reads its own packets")
        self.perceived = p = self.ws.update(packet)
        now = self.ws.now_ms
        self.memory.expire(now)
        triggers: list[str] = []
        if not self._started:
            self._started = True
            triggers.append("START")
        conv = self.conversation
        for item in p.addressed:
            speaker = item.get("track_id")
            topics = topics_of(item["value"]["text"])
            stored = self.memory.remember_heard(item, packet, topics)
            if conv.partner is None and speaker is not None:
                self._start_conversation(speaker, item.get("event_id"))
                conv = self.conversation
            if speaker is not None and speaker == conv.partner:
                conv.last_exchange_ms = now
                conv.turns += 1
                conv.topics |= topics
                if stored is not None:
                    conv.scopes.add(stored["scope"])
                if is_farewell(item["value"]["text"]):
                    conv.closing = True
            triggers.append("ADDRESSED_SPEECH")
        if p.greetings:
            triggers.append("DIRECTED_GESTURE")
        if p.invites:
            triggers.append("GROUP_INVITE")
        near = [t for t in p.new_tracks if (self.ws.tracks[t].range_m or 99.0) <= NEAR_FOCAL_M]
        if near:
            triggers.append("PERSON_NEAR")
        if conv.partner is not None and (conv.partner in p.lost_tracks and not self.ws.visible(conv.partner)
                                         or now - conv.last_exchange_ms > PARTNER_SILENCE_END_MS):
            self._end_conversation("PARTNER_LEFT" if conv.partner in p.lost_tracks else "SILENCE")
            triggers.append("PARTNER_LEFT")
        if conv.partner is None and any(self.ws.visible(t) for c in self.memory.open_commitments()
                                        for t in c["audience_present"]):
            triggers.append("COMMITMENT_DUE")
        if self._replan_due:
            self._replan_due = False
            triggers.append("ACTION_REJECTED")

        before = self.cognition.level
        signals = self._update_cognition(p, bool(p.addressed), packet)
        if self.npc_model:
            self._track_promotion(before, packet)
            likely = self.cognition.likely_next(signals)
            if self.prewarm_enabled and likely is not None:
                key, prefix = self.persona_prefix(likely)
                if key not in self._prewarm_asked:
                    self._prewarm_asked.add(key)
                    self.prewarm_wanted.append((likely, key, prefix))
        if self.pending:
            if triggers:
                self._queued += [t for t in triggers if t not in self._queued]
                self.stats["skipped_pending"] += 1
            return None
        triggers = sorted(set(self._queued + triggers), key=_TRIGGER_ORDER.index)
        self._queued = []
        if not triggers:
            return None
        return self._job(triggers, packet)

    def _update_cognition(self, p: Perceived, addressed: bool, packet: dict[str, Any]) -> None:
        # Distance to focal agents is not knowable from anonymous tracks; the closest seen person
        # stands in for "near a focal agent" for NPCs (scene salience, never person judgments).
        ranges = [s.range_m for s in self.ws.tracks.values() if s.range_m is not None and s.left_ms is None]
        closest = min(ranges) if ranges else None
        signals = Signals(
            now_ms=self.ws.now_ms, addressed=addressed,
            near_focal=closest is not None and closest <= NEAR_FOCAL_M,
            focal_within_far=closest is not None and closest <= FAR_FROM_FOCAL_M,
            invited_to_group=bool(p.invites), conversation_turns=self.conversation.turns)
        reason = self.cognition.update(signals)
        if reason == "IDLE" and self.conversation.partner is not None:
            self._end_conversation("DEMOTED")
        return signals

    # ---------- persona prefixes, pre-warming and promotion latency (G3c-1; T5, T6) ----------

    def persona_prefix(self, tier: str) -> tuple[str, str]:
        """(key, text) of this agent's stable prompt prefix at ``tier``: guardrails and identity,
        identical from call to call. The key changes if the text does (model + prompt version)."""
        if tier not in self._prefixes:
            assembler = ContextAssembler(self.tokenizer, tier)
            text = assembler.persona_prefix(
                guardrails.guardrails_section(tier, self.allowed_actions, self.body, self.expressions), self.identity)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
            self._prefixes[tier] = (f"{self.agent_id}:{tier}:{digest}", text)
        return self._prefixes[tier]

    def model_tiers(self) -> list[str]:
        """The tiers at which this NPC calls the model (for persona snapshots at scene load)."""
        if not self.npc_model:
            return []
        return [lv for lv in ("C1", "C2") if LEVELS.index(lv) <= LEVELS.index(self.cognition.ceiling)]

    def take_prewarms(self) -> list[tuple[str, str, str]]:
        wanted, self.prewarm_wanted = self.prewarm_wanted, []
        return wanted

    def _track_promotion(self, before: str, packet: dict[str, Any]) -> None:
        after = self.cognition.level
        if after == before:
            return
        if LEVELS.index(after) < LEVELS.index(before):
            for rec in self._open_promotions:
                self._close_promotion(rec, "DEMOTED_BEFORE_ACTION")
            return
        key = self.persona_prefix(after)[0] if after != "C0" else None
        rec = {"agent_id": self.agent_id, "from": before, "to": after,
               "reason": self.cognition.changes[-1]["reason"], "tick": packet["based_on_tick_id"],
               "sim_time_ms": packet["sim_time_ms"], "predicted": key in self._prewarm_asked,
               "prewarm": "OFF" if not self.prewarm_enabled else (
                   "PREDICTED" if key in self._prewarm_asked else "NOT_PREDICTED"),
               "status": "OPEN", "first_validated_action_ms": None, "decisions_until_action": 0,
               "first_model_call": None, "_t0": time.perf_counter(), "_requests": set()}
        self.promotions.append(rec)
        self._open_promotions.append(rec)

    def _close_promotion(self, rec: dict[str, Any], status: str) -> None:
        rec["status"] = status
        if rec in self._open_promotions:
            self._open_promotions.remove(rec)

    def promotion_records(self, run_ended: bool = False) -> list[dict[str, Any]]:
        """Evaluator records of every promotion so far (open ones say so)."""
        out = []
        for rec in self.promotions:
            r = {k: v for k, v in rec.items() if not k.startswith("_")}
            if run_ended and r["status"] == "OPEN":
                r["status"] = "NO_ACTION_BEFORE_END"
            out.append(r)
        return out

    # ---------- conversations and episode cards ----------

    def _start_conversation(self, partner: str, event_id: str | None) -> None:
        now = self.ws.now_ms
        self.conversation = Conversation(partner, now, now, 0, False, {partner}, set(), set(), event_id)

    def _end_conversation(self, why: str) -> None:
        conv = self.conversation
        if conv.partner is None:
            return
        open_to = [c for c in self.memory.open_commitments() if conv.partner in c["audience_present"]]
        topics = ", ".join(sorted(conv.topics)[:6]) or "nothing specific"
        open_text = "promised to help later" if open_to else "nothing open"
        seconds = max(0, self.ws.now_ms - conv.since_ms) // 1000
        # Scopes survive compression: a card takes the strictest scope of its sources and
        # sources of different scopes are never merged (CONTEXT_MEMORY_STRATEGY §6).
        for scope in sorted(conv.scopes or {"PUBLIC"}):
            self.memory.add_episode_card(
                f"Talked with {conv.partner} for {seconds}s ({conv.turns} turns from them); topics: {topics}; "
                f"ended: {why.lower()}; {open_text}.",
                now_ms=self.ws.now_ms, scope=scope, participants=set(conv.participants), topics=set(conv.topics),
                source_event_id=conv.first_event_id)
        self.conversation = Conversation()

    # ---------- deciding ----------

    def _policy_name(self) -> str:
        level = self.cognition.level
        if level == "C0":
            return "ROUTINE"
        if self.npc_model:
            return "MODEL"          # G3c-1: C1 and C2 NPCs decide through the NPC model
        if level == "C1":
            return "TEMPLATE"
        if self.controller == "LLM_AGENT" and self.gateway is not None:
            return "MODEL"
        return "DEMO"

    def _rule_policy(self, name: str):
        if name == "ROUTINE":
            return RoutinePolicy()
        if self.robot and name in ("DEMO", "MODEL"):
            return RobotDemoPolicy()
        return NpcTemplatePolicy()

    def _goal_text(self) -> str:
        if self.conversation.partner is not None:
            return f"In conversation with {self.conversation.partner}. Task: {self.task or self.identity.public_goal}"
        return f"Task: {self.task or self.identity.public_goal}"

    def _job(self, triggers: list[str], packet: dict[str, Any]) -> DecisionJob:
        self._decisions += 1
        decision_id = f"dec_{self.agent_id}_{self._decisions:06d}"[:64]
        policy = self._policy_name()
        tier = self.tier
        assembled = None
        if tier != "C0":
            conv = self.conversation
            participants = set(conv.participants) | {i["track_id"] for i in self.perceived.greetings}
            topics = set(conv.topics)
            for item in self.perceived.addressed:
                topics |= topics_of(item["value"]["text"])
            assembler = ContextAssembler(self.tokenizer, tier)
            assembled = assembler.assemble(
                guardrails=guardrails.guardrails_section(tier, self.allowed_actions, self.body, self.expressions),
                identity=self.identity, memory=self.memory, ws=self.ws, setting=self.setting, goal=self._goal_text(),
                triggers=[t.lower().replace("_", " ") for t in triggers], participants=participants, topics=topics,
                audience=disclosure.audience_from_packet(packet))
        rule = self._rule_policy(policy)
        proposals = rule.decide(self, triggers)
        demo_hint = None
        if policy == "MODEL":
            demo_hint = json.dumps({"actions": [_proposal_entry(p) for p in proposals] or
                                    [{"action": "WAIT", "args": {"duration_ms": 1000}}]}, sort_keys=True)
            proposals = None
        else:
            proposals = [p for p in proposals if p.action in self.allowed_actions]
        prefix_key = self.persona_prefix(tier)[0] if policy == "MODEL" else None
        return DecisionJob(decision_id, self.ws.tick, triggers, policy, tier, self.cognition.level, assembled,
                           proposals, demo_hint, prefix_key)

    async def decide(self, job: DecisionJob) -> list[dict[str, Any]]:
        """Answer a job: returns the action requests to send. Model calls happen here."""
        self.pending = True
        try:
            model_calls: list[dict[str, Any]] = []
            fallback = None
            if job.proposals is not None:
                proposals = job.proposals
            else:
                assert self.gateway is not None and job.assembled is not None
                result = await self.gateway.decide(
                    agent_id=self.agent_id, tier=job.tier, prompt=job.assembled.prompt,
                    prompt_sha256=job.assembled.record["prompt_sha256"], max_tokens=OUTPUT_CAPS.get(job.tier, 120),
                    allowed_actions=self.allowed_actions, tick=job.tick, demo_hint=job.demo_hint,
                    prefix_key=job.prefix_key,
                    # NPCs: the persona prefix may go as its own (system) message; Robot R's prompt
                    # shape stays one message, as the G3b bake-off measured it.
                    prefix=self.persona_prefix(job.tier)[1] if self.npc_model else None)
                model_calls, fallback = result.model_calls, result.fallback
                proposals = [_proposal_from_model(a, self.memory, self.conversation) for a in result.actions]
            requests = self._emit(job, proposals, model_calls, fallback)
            if job.policy == "MODEL":
                for rec in self._open_promotions:
                    rec["decisions_until_action"] += 1
                    if rec["first_model_call"] is None and model_calls:
                        c = model_calls[0]
                        rec["first_model_call"] = {k: c.get(k) for k in ("outcome", "server", "slot", "prefix_state",
                                                                         "prompt_tokens", "cached_tokens")}
                        rec["first_model_call"].update(c["timings"])
                        # Decisions are event-driven (D-49): the first one may wait for a trigger.
                        rec["first_decision_tick"] = job.tick
                    if fallback is None:
                        rec["_requests"] |= {r["action_request_id"] for r in requests}
            return requests
        finally:
            self.pending = False

    def decide_now(self, job: DecisionJob) -> list[dict[str, Any]]:
        """Synchronous answer for jobs that need no model (ROUTINE, TEMPLATE, DEMO)."""
        if job.proposals is None:
            raise ValueError("this job needs the model; use decide()")
        return self._emit(job, job.proposals, [], None)

    def _emit(self, job: DecisionJob, proposals: list[Proposal], model_calls: list[dict[str, Any]],
              fallback: dict[str, str] | None) -> list[dict[str, Any]]:
        requests = []
        kept = []
        for p in proposals[:3]:
            # The host refuses a light change sooner than 1/3 s after the last (D-14), so don't ask
            # for one: show the expression's gesture alone if it has one (gestures are not light),
            # and a promise riding on it stays with that gesture or moves to the words.
            if p.action == "EXPRESS":
                if job.tick - self._last_express_tick < EXPRESSION_MIN_GAP_TICKS:
                    gesture = self.expression_gestures.get(p.args.get("expression_id", ""))
                    if gesture is not None and self.body_supports_gesture(gesture):
                        kept.append(Proposal("GESTURE", {"gesture": gesture, "target_id": p.args.get("target_id")},
                                             p.commitment, p.fulfills))
                        continue
                    # No gesture: the promise moves to the words, if any. With nothing said or shown,
                    # no promise was made, so none is recorded.
                    nxt = next((q for q in proposals if q.action == "SPEAK"), None)
                    if p.commitment and nxt is not None and nxt.commitment is None:
                        nxt.commitment = p.commitment
                    continue
                self._last_express_tick = job.tick
            kept.append(p)
        for p in kept:
            self._requests += 1
            request_id = f"act_{self.agent_id}_{self._requests:05d}"[:64]
            requests.append({"schema_version": "1.0", "action_request_id": request_id, "agent_id": self.agent_id,
                             "based_on_tick_id": job.tick, "action": p.action, "args": p.args})
            commitment_id = None
            target = p.args.get("addressee_id", p.args.get("target_id"))
            if p.commitment:
                commitment_id = self.memory.commit(p.commitment, target, now_ms=self.ws.now_ms)["memory_id"]
            for memory_id in p.fulfills:
                self.memory.set_commitment_state(memory_id, "FULFILLED")
            if p.action == "SPEAK":
                self.ws.my_turn(p.args["text"], target)
                if target is not None and self.conversation.partner is None:
                    self._start_conversation(target, None)
                if target is not None and target == self.conversation.partner:
                    self.conversation.last_exchange_ms = self.ws.now_ms
            self._sent[request_id] = {"action": p.action, "commitment_id": commitment_id, "decision_id": job.decision_id,
                                      "replanned": "ACTION_REJECTED" in job.triggers}
        if self.conversation.closing:
            self._end_conversation("FAREWELL")
        self.stats["decisions"] += 1
        self.stats["requests"] += len(requests)
        if fallback is not None:
            self.stats["fallbacks"] += 1
        record = {
            "schema_version": "1.0", "decision_id": job.decision_id, "agent_id": self.agent_id,
            "based_on_tick_id": job.tick, "cognition_level": job.level, "tier": job.tier, "policy": job.policy,
            "triggers": job.triggers, "context": job.assembled.record if job.assembled else None,
            "model_calls": model_calls, "action_request_ids": [r["action_request_id"] for r in requests],
            "fallback": fallback,
        }
        self.records.append(record)
        if job.assembled is not None:
            self.prompts.append({"decision_id": job.decision_id, "prompt": job.assembled.prompt})
        return requests

    # ---------- results from the host ----------

    def on_result(self, result: dict[str, Any]) -> None:
        request_id = result["action_request_id"]
        self.results[request_id] = result
        if result["accepted"]:
            for rec in list(self._open_promotions):
                if request_id in rec["_requests"]:
                    rec["first_validated_action_ms"] = round((time.perf_counter() - rec["_t0"]) * 1000)
                    rec["first_action_tick"] = result.get("resolved_at_tick_id")
                    self._close_promotion(rec, "VALIDATED")
        sent = self._sent.get(request_id)
        if sent is None or result["accepted"]:
            return
        self.stats["rejected"] += 1
        if sent["commitment_id"] is not None:
            self.memory.set_commitment_state(sent["commitment_id"], "RELEASED")
        # One replan per rejected decision, from the next observation (T27); never a loop.
        if result["reason_code"] in REPLAN_REASONS and not sent["replanned"] \
                and sent["decision_id"] not in self._replanned_decisions:
            self._replanned_decisions.add(sent["decision_id"])
            self._replan_due = True
            self.stats["replans"] += 1


_TRIGGER_ORDER = ["START", "ADDRESSED_SPEECH", "DIRECTED_GESTURE", "DIRECTED_EXPRESSION", "PERSON_NEAR",
                  "PARTNER_LEFT", "GROUP_INVITE", "ACTION_REJECTED", "COMMITMENT_DUE", "TASK_STEP"]


def _proposal_entry(p: Proposal) -> dict[str, Any]:
    entry: dict[str, Any] = {"action": p.action, "args": p.args}
    if p.commitment:
        entry["commitment"] = p.commitment
    if p.fulfills:
        entry["fulfills_commitment"] = True
    return entry


def _proposal_from_model(action: dict[str, Any], memory: AgentMemory, conv: Conversation) -> Proposal:
    fulfills: list[str] = []
    target = action["args"].get("addressee_id", action["args"].get("target_id"))
    if action.get("fulfills_commitment") and target is not None:
        fulfills = [c["memory_id"] for c in memory.commitments_to(target)]
    return Proposal(action["action"], action["args"], action.get("commitment"), fulfills)


def _body_summary(body: dict[str, Any], expressions: list[str]) -> str:
    caps = body["capabilities"]
    moves = "stairs and ramp" if caps.get("can_use_stairs") and caps.get("can_use_ramp") else \
        ("ramp only, no stairs" if caps.get("can_use_ramp") else "flat floor only")
    return (f"{body.get('display_name', body['body_id'])}, {body['dimensions']['height_m']} m tall, "
            f"max {body['motion']['max_speed_m_s']} m/s, {moves}; channels {', '.join(body['expression_channels'])}.")
