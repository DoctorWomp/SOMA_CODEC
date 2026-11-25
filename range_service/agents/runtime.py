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
rejection triggers one replan from the latest observation (T27).

G3d (D-63, D-64):
- **Memory follows what the world accepted.** A promise, a kept promise, the agent's own speech
  turn and a conversation it starts are staged per action request and applied once, when the
  host accepts that request; a rejection leaves memory as it was. While a request is sent but not
  yet accepted, the next decision sees one line saying so (never as memory).
- **Relevance check before sending** (``recheck``, live runs): a MOVE_TO, a SPEAK or GESTURE aimed
  at someone, or an action that makes or keeps a promise is dropped, with the reason recorded, if
  its person is no longer perceived or someone else has addressed the agent since the decision's
  observation; the decision then gets the usual single replan. A model answer not sent within its
  decision deadline plus the send margin is dropped too.
- **FN-1:** a departure from an open conversation needs a closing line the partner could hear,
  before it in the same answer, and is held back until the host accepts that line.

The runtime sees only its own packets, its own memory and the public part of its persona.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

from range_service.comms import disclosure

from . import guardrails
from . import activity as activities
from .ambient import AmbientDisplay
from .pulse import Digest, Event, IntentMonitor, Presence, Pulse, Survey, is_closing, voice_key
from .cognition import FAR_FROM_FOCAL_M, LEVELS, NEAR_FOCAL_M, CognitionLevel, Signals
from .context import OUTPUT_CAPS, Assembled, ContextAssembler, Identity, ago
from .gateway import ActivityDropped, ModelGateway
from .handles import HandleMap
from .memory import AgentMemory
from .policy_demo import NpcTemplatePolicy, Proposal, RobotDemoPolicy, RoutinePolicy, is_farewell
from .tokenizer import ApproxTokenizer, Tokenizer
from .working_set import Perceived, WorkingSet

PARTNER_SILENCE_END_MS = 20_000     # a conversation ends after this long without an exchange
EXPRESSION_MIN_GAP_TICKS = 20       # the host refuses expression changes faster than 3 per second (D-14)
REPLAN_REASONS = frozenset({"STALE_OBSERVATION", "TARGET_UNKNOWN"})
# G3d (D-63): a model answer must be handed to the link within its decision deadline plus this
# much (event-loop lag); the rest of the 500 ms delivery margin covers the link and one world tick.
SEND_GRACE_MS = 400
# Model work started by the agent's own pulse or wake conditions while idle (counted by the idle budget).
IDLE_WORK_TRIGGERS = frozenset({"PULSE_REVIEW", "WAKE_CONDITION"})
DELIVERY_MARGIN_MS = 500
ARRIVED_M = 0.75                    # G3f (SB-10): within this of its MOVE_TO destination ...
MOVING_M = 0.005                    # ... and moved less than this since the last packet: it has arrived
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
    choices: dict[str, Any] | None = None  # what the answer may name, fixed when the job is made (D-60)
    started_at: float = 0.0               # time.monotonic() when the job was made: the decision deadline counts from here (D-63)
    now_ms: int = 0                       # simulated time of the observation it is based on
    sources: list[str] = field(default_factory=list)   # who or what triggered it (tracks, voices), for metrics (D-65)
    handles: Any = None                   # G3h (D-111): the agent's HandleMap when this prompt uses handles


class AgentRuntime:
    def __init__(self, agent_id: str, *, persona: dict[str, Any], body: dict[str, Any], directive: str,
                 expressions: list[str], setting: list[str], task: str | None = None,
                 task_goal: dict[str, float] | None = None, focal: bool = False, pin: bool = False,
                 controller: str = "SCRIPTED", gateway: ModelGateway | None = None,
                 tokenizer: Tokenizer | None = None, expression_gestures: dict[str, str] | None = None,
                 own_private_goal: str | None = None, prewarm: bool = True, pa_operator: bool = False,
                 pulse: dict[str, Any] | None = None, seed: int = 0, post: dict[str, float] | None = None,
                 post_duty: bool = False, survey_area: dict[str, float] | None = None,
                 ambient: dict[str, str] | None = None, expression_holds: dict[str, int] | None = None,
                 style: dict[str, int] | None = None) -> None:
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
        self.pa_operator = pa_operator or bool(body["capabilities"].get("can_use_pa"))
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
        # G4b (D-98): persona sliders, editable by the Director and shown on inspection. No policy
        # reads them yet: style stays out of prompts (D-13).
        self.style: dict[str, int] = dict(style or {})
        self.edits: list[dict[str, Any]] = []          # Director edits applied, in order (evaluator)
        self.cognition = CognitionLevel(persona["cognition_level"], pinned=pin or focal)
        self.memory = AgentMemory(agent_id)
        self.ws = WorkingSet(agent_id)
        self.conversation = Conversation()
        self.perceived = Perceived()
        self.tokenizer = tokenizer or ApproxTokenizer()
        self.pending = False
        self.records: list[dict[str, Any]] = []
        self.prompts: list[dict[str, str]] = []       # assembled contexts, for leak checks and the viewer
        self.handles: HandleMap | None = None          # G3h (D-111): observer-local handles, made on first use
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
        self.snapshots_wanted: list[tuple[str, str, str]] = []  # G4b: new prefixes after a directive edit (T5)
        self._prewarm_asked: set[str] = set()
        self.promotions: list[dict[str, Any]] = []
        self._open_promotions: list[dict[str, Any]] = []
        # The pulse protocol (G3c-2, D-61): None = off (the G3a/G3b behavior, byte for byte).
        self.pulse_cfg = pulse
        self.activity: activities.Activity | None = None
        self.pulse_log: list[dict[str, Any]] = []
        self.post_duty = post_duty
        self.pending_kind: str | None = None
        self.preempt_requested = False
        self._presence_out: list[tuple[str, dict[str, Any]]] = []
        self._answer_activity: dict[str, Any] | None = None
        self._speaking_until_ms = 0
        self._last_due_ms = -10**9
        self._speech_seen = 0
        self._sitrep_changes: list[str] = []
        self._fn1_events: list[str] = []
        self._first_trigger_ms: int | None = None
        # G3d (D-63, D-64): memory changes staged until the host accepts the request; departures held
        # for a closing line; what was dropped before sending and why.
        self._staged: dict[str, dict[str, Any]] = {}
        self._held: dict[str, list[dict[str, Any]]] = {}      # closing SPEAK id -> MOVE_TOs waiting for it
        self._release_out: list[dict[str, Any]] = []
        self._addressed_log: list[tuple[int, str]] = []       # (sim ms, speaker) of speech addressed to it
        self.delivery_log: list[dict[str, Any]] = []
        self._sources_now: set[str] = set()
        self._queued_sources: set[str] = set()
        self._presence_events: dict[str, dict[str, Any]] = {}   # presence request id -> its pulse-log event
        # The ambient state display (G3e, D-73): state -> expression id this body can show; only with
        # the pulse on (agents that decide for themselves) and a Beacon.
        self.ambient = AmbientDisplay(ambient or {}, expression_holds or {}) if pulse is not None and ambient else None
        self.pending_policy: str | None = None
        self._last_fallback = False
        self.travel_to: dict[str, Any] | None = None   # its own accepted MOVE_TO destination (G3f, SB-10)
        self._moving = False
        if pulse is not None:
            self.monitor = IntentMonitor(pulse["pulse"]["cooldowns_s"])
            self.pulse = Pulse(pulse["pulse"], agent_id, seed)
            self.presence = Presence(pulse["presence"])
            if self.ambient is not None:
                self.presence.idle_expression = None     # the ambient display shows waiting instead (D-73)
            self.survey = Survey(pulse["survey"], survey_area, post) if survey_area is not None else None
        else:
            self.monitor = self.pulse = self.presence = self.survey = None   # type: ignore[assignment]
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

    def en_route(self) -> bool:
        """Walking to a destination of its own accepted MOVE_TO, not there yet (G3f, SB-10). Then
        attention goes with the head (LOOK_AT), never a body turn that would break its stride (D-72)."""
        dest, pose = self.travel_to, self.ws.pose
        if not isinstance(dest, dict) or "x" not in dest or pose is None:
            return False
        return math.hypot(dest["x"] - pose["x"], dest["z"] - pose["z"]) > ARRIVED_M or self._moving

    def observe(self, packet: dict[str, Any]) -> DecisionJob | None:
        """Take in one packet. Returns a decision job if one is needed now, else None."""
        if packet["observer_id"] != self.agent_id:
            raise ValueError("a runtime only reads its own packets")
        prev = self.ws.pose
        self.perceived = p = self.ws.update(packet)
        now = self.ws.now_ms
        pose = self.ws.pose
        # Still moving: its own position changed since the last packet (no speed in the packet).
        self._moving = prev is not None and pose is not None and \
            math.hypot(pose["x"] - prev["x"], pose["z"] - prev["z"]) > MOVING_M
        if self.travel_to is not None and not self.en_route():
            self.travel_to = None                    # arrived
        self.memory.expire(now)
        triggers: list[str] = []
        if not self._started:
            self._started = True
            triggers.append("START")
        conv = self.conversation
        self._sources_now = set()
        for item in p.addressed:
            speaker = item.get("track_id")
            source = _source_of(item)
            self._sources_now.add(source)
            self._addressed_log.append((now, source))
            del self._addressed_log[:-50]
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
            self._sources_now |= {i["track_id"] for i in p.greetings if i.get("track_id")}
        if p.invites:
            triggers.append("GROUP_INVITE")
        near = [t for t in p.new_tracks if (self.ws.tracks[t].range_m or 99.0) <= NEAR_FOCAL_M]
        if near:
            triggers.append("PERSON_NEAR")
            self._sources_now |= set(near)
        if conv.partner is not None and (conv.partner in p.lost_tracks and not self.ws.visible(conv.partner)
                                         or now - conv.last_exchange_ms > PARTNER_SILENCE_END_MS):
            self._sources_now.add(conv.partner)
            self._end_conversation("PARTNER_LEFT" if conv.partner in p.lost_tracks else "SILENCE")
            triggers.append("PARTNER_LEFT")
        if conv.partner is None and any(self.ws.visible(t) for c in self.memory.open_commitments()
                                        for t in c["audience_present"]):
            triggers.append("COMMITMENT_DUE")
            self._sources_now |= {t for c in self.memory.open_commitments() for t in c["audience_present"]
                                  if self.ws.visible(t)}
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
        if self.pulse is not None:
            triggers = self._pulse_observe(p, triggers)
        if self.pending:
            if triggers:
                if self.pending_kind == "PULSE" and any(t != "PULSE_REVIEW" for t in triggers):
                    self.preempt_requested = True      # a real event: the pulse review gives way (D-61)
                self._queued += [t for t in triggers if t not in self._queued and t != "PULSE_REVIEW"]
                self._queued_sources |= self._sources_now
                self.stats["skipped_pending"] += 1
            return None
        triggers = sorted(set(self._queued + triggers), key=_TRIGGER_ORDER.index)
        sources = self._queued_sources | self._sources_now
        self._queued, self._queued_sources = [], set()
        if not triggers:
            return None
        job = self._job(triggers, packet)
        job.sources = sorted(sources)
        return job

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

    # ---------- the pulse protocol (G3c-2, D-61; PULSE_PROTOCOL) ----------

    def _log(self, event: str, **data: Any) -> None:
        self.pulse_log.append(Event(event, self.ws.now_ms, data).record())

    def _promise_due(self) -> bool:
        """A promise can be kept now: free, the person in view, and not busy talking to someone else."""
        if self.conversation.partner is not None:
            return False
        for c in self.memory.open_commitments():
            for track in c["audience_present"]:
                if self.ws.visible(track) and not self._busy_talking(track):
                    return True
        return False

    def _busy_talking(self, track: str, window_ms: int = 20_000, near_m: float = 2.0) -> bool:
        """Observable only: the person, or someone standing within 2 m of them, spoke to someone
        else in the last 20 s (a conversation it is not part of). Never a judgment about them."""
        me = self.ws.tracks.get(track)
        if me is None or me.x is None:
            return False
        for other in self.ws.tracks.values():
            if other.speaking_ms is None or self.ws.now_ms - other.speaking_ms >= window_ms or other.x is None:
                continue
            if other is me or math.hypot(other.x - me.x, other.z - me.z) <= near_m:
                return True
        return False

    def _conversation_open(self) -> bool:
        conv, cfg = self.conversation, self.pulse_cfg["conversation"]
        if conv.partner is None or conv.closing or not self.ws.visible(conv.partner):
            return False
        state = self.ws.tracks[conv.partner]
        return (state.range_m is None or state.range_m <= cfg["range_m"]) and \
            self.ws.now_ms - conv.last_exchange_ms <= cfg["silence_limit_s"] * 1000

    def _digest(self) -> Digest:
        act = self.activity
        target_visible = self.ws.visible(act.target_id) if act is not None and act.target_id else None
        progress = None
        if act is not None and act.destination is not None and self.ws.pose is not None:
            progress = round(math.hypot(act.destination["x"] - self.ws.pose["x"], act.destination["z"] - self.ws.pose["z"]), 1)
        due = frozenset(c["memory_id"] for c in self.memory.open_commitments()) if self._promise_due() else frozenset()
        return Digest(frozenset(t for t in self.ws.tracks if self.ws.visible(t)), self._speech_seen, due,
                      target_visible, progress)

    def _pulse_observe(self, p: Perceived, triggers: list[str]) -> list[str]:
        """Loops 2-4 on one packet: presence, the intent monitor, the pulse and the survey. Only the
        agent's own perception; simulated time only."""
        now = self.ws.now_ms
        cfg = self.pulse_cfg
        # Speech that could be to the agent counts as a change; talk between others it overhears
        # does not (D-12), or a robot waiting near a conversation would review every few seconds.
        self._speech_seen += len(p.addressed) + sum(1 for h in p.heard if h["addressed"] is None)
        triggers = [t for t in triggers if t != "COMMITMENT_DUE"]       # rate-limited below, not per packet
        due = self._promise_due()
        if due and now - self._last_due_ms >= cfg["pulse"]["cooldowns_s"]["commitment_due"] * 1000:
            self._last_due_ms = now
            triggers.append("COMMITMENT_DUE")
            self._sources_now |= {t for c in self.memory.open_commitments() for t in c["audience_present"]
                                  if self.ws.visible(t)}
        if self.survey is not None:
            self.survey.observe(now, self.ws.pose)
        glance_range = cfg["presence"]["glance_range_m"]
        for track in p.new_tracks:
            if (self.ws.tracks[track].range_m or 99) <= glance_range:
                self._log("RELEVANT", source=track, kind="movement")
        heard = p.heard + [{"track_id": i.get("track_id"), "range_m": i.get("range_m"),
                            "bearing_rad": i.get("bearing_rad"), "to_me": True} for i in p.addressed]
        for h in heard:
            if h.get("track_id") and (h.get("range_m") or 99) <= glance_range:
                self._log("RELEVANT", source=h["track_id"], kind="speech")
            elif h.get("track_id") is None and h.get("bearing_rad") is not None:
                self._log("RELEVANT", source=voice_key(h["bearing_rad"]), kind="voice")
        # Loop 2: presence (no model). Glance at new movement or speech; gaze back to the partner.
        actions, events = self.presence.step(
            now_ms=now, ws=self.ws, perceived=p,
            heard=heard,
            partner=self.conversation.partner, speaking_until_ms=self._speaking_until_ms, activity=self.activity,
            can_look="LOOK_AT" in self.allowed_actions, expressions=self.expressions, en_route=self.en_route())
        for (action, args), e in zip(actions, events):
            record = e.record()
            self.pulse_log.append(record)
            self._presence_out.append((action, args, record))
        # Loop 3: the intent monitor. Speech that could be to it (unknown addressee, within
        # conversation range) may wake it; speech to someone else only gets a glance (FN-2).
        possibly_to_me = [h["track_id"] for h in p.heard if h["addressed"] is None and h["track_id"]
                          and (h.get("range_m") or 99) <= cfg["conversation"]["range_m"]]
        wakes = self.monitor.check(self.activity, now_ms=now, perceived=p, ws=self.ws, addressed=bool(p.addressed),
                                   heard_tracks=possibly_to_me, new_tracks=p.new_tracks, due_commitment=due)
        if wakes:
            triggers.append("WAKE_CONDITION")
            self._log("WAKE", conditions=wakes)
            if self.activity is not None and self.activity.target_id:
                self._sources_now.add(self.activity.target_id)
        if triggers and self._first_trigger_ms is None:
            self._first_trigger_ms = now
        # The ambient display (D-73) yields to a decision about to be made from this packet: a chosen
        # expression gets the light-change slot first, and the display follows on a later packet.
        if not triggers or self.pending:
            self._ambient_step(now)
        if triggers:
            self.pulse.schedule(now, self.activity, reset=True)
            return triggers
        if self.pending:
            return triggers
        # Loop 4: the pulse. Triage first; the model only when something changed.
        if self.pulse.next_ms is None:
            self.pulse.schedule(now, self.activity, reset=True)
        elif self.pulse.due(now):
            changed = self.pulse.triage(self._digest())
            if self.activity is not None and self.activity.kind == "CONVERSE" and not self._conversation_open():
                changed.append("the conversation is over")
            busy = self.npc_model and self.gateway is not None and \
                self.gateway.busy_share(self.tier) >= cfg["pulse"]["npc_busy_share"]
            if changed and not self.pulse.over_budget(now) and not busy:
                self._sitrep_changes = changed
                self.pulse.reviews += 1
                triggers.append("PULSE_REVIEW")
            else:
                reason = "nothing changed" if not changed else ("idle budget used" if not busy else "NPC server busy")
                self.pulse.continues += 1
                self.pulse.continues_since_change += 1
                self.pulse.step += 1
                self.pulse.schedule(now, self.activity, reset=False)
                self._log("CONTINUE", reason=reason, activity=self.activity.kind if self.activity else None)
        # SURVEY / RETURN_TO_POST: deterministic moves, no model.
        if not triggers and self.survey is not None and self.conversation.partner is None and \
                self.activity is not None and self.activity.kind in ("SURVEY", "RETURN_TO_POST") and \
                "MOVE_TO" in self.allowed_actions:
            people = [(s.x, s.z) for k, s in self.ws.tracks.items() if self.ws.visible(k) and s.x is not None]
            someone_close = any((s.range_m or 99) <= cfg["conversation"]["range_m"]
                                for k, s in self.ws.tracks.items() if self.ws.visible(k))
            # Never walk off while someone is close enough to talk to (they may be about to).
            move = None if someone_close else self.survey.next_move(now, self.ws.pose, people)
            if move is not None:
                why, dest = move
                self.activity.kind, self.activity.destination = why, dest
                self._log(why, destination=dest)
                self._presence_out.append(("MOVE_TO", {"destination": dest}, self.pulse_log[-1]))
            elif self.activity.kind == "RETURN_TO_POST" and not self.survey.returning:
                self.activity.kind = "SURVEY"
        return triggers

    def ambient_state(self) -> str:
        """The agent's own state, for the ambient display (G3e, D-73). Own state only, in order:
        THINKING (a decision's model call in flight), CONSIDERING (a pulse review in flight, or the
        last model answer could not be used; Prism's HELD_OPEN joins at G5), LISTENING (a
        conversation is open and it is not speaking), WAITING (activity WAIT_FOR), ATTENDING."""
        if self.pending and self.pending_policy == "MODEL":
            return "THINKING" if self.pending_kind == "REAL" else "CONSIDERING"
        if self._last_fallback:
            return "CONSIDERING"
        if self._conversation_open() and self.ws.now_ms >= self._speaking_until_ms:
            return "LISTENING"
        if self.activity is not None and self.activity.kind == "WAIT_FOR":
            return "WAITING"
        return "ATTENDING"

    def _ambient_step(self, now: int) -> None:
        """At most one gated EXPRESS per change of state, through the normal action path."""
        if self.ambient is None or "EXPRESS" not in self.allowed_actions:
            return
        if self.ws.tick - self._last_express_tick < EXPRESSION_MIN_GAP_TICKS:
            return                                      # the host's 1/3 s light-change limit (D-14)
        state = self.ambient_state()
        eid = self.ambient.want(state, now)
        if eid is None:
            return
        self._log("AMBIENT", state=state, expression=eid)
        self._presence_out.append(("EXPRESS", {"expression_id": eid, "target_id": None}, self.pulse_log[-1]))
        self.ambient.sent(eid, now)

    def sitrep(self) -> str:
        """Time made explicit for the model (PULSE_PROTOCOL §6): the activity and how long it has
        run, the last interaction and review, promises due, and what changed (one line each).
        Repeated CONTINUEs are one line here, never a growing log (§7)."""
        now = self.ws.now_ms
        act = self.activity
        lines = []
        if act is not None:
            target = f" {act.target_id}" if act.target_id else ""
            lines.append(f"Activity: {act.kind}{target} ({act.source.lower()}) for {(now - act.started_ms) // 1000}s.")
        last_turn = max((tr.at_ms for tr in self.ws.turns), default=None)
        lines.append(f"Last interaction: {ago(now, last_turn) if last_turn is not None else 'none yet'}.")
        if self.pulse.last_review_ms is not None:
            lines.append(f"Last review: {ago(now, self.pulse.last_review_ms)}; "
                         f"{self.pulse.continues_since_change} quiet checks since, nothing changed.")
        due = [c for c in self.memory.open_commitments()]
        if due:
            lines.append("Open promises: " + "; ".join(f"{c['memory_id']} to {', '.join(c['audience_present']) or 'nobody'}"
                                                        f" (made {ago(now, c['observed_at_ms'])})" for c in due[:3]) + ".")
        if self._sitrep_changes:
            lines.append("Changed since the last review: " + "; ".join(self._sitrep_changes[:4]) + ".")
        return "\n".join(lines)

    def take_presence(self) -> list[dict[str, Any]]:
        """Presence-loop and survey actions to send now (LOOK_AT, EXPRESS, MOVE_TO): through the
        normal action path, journaled and gated like any other request."""
        out = []
        for action, args, event in self._presence_out:
            if action not in self.allowed_actions:
                event["not_sent"] = "NOT_ALLOWED"
                continue
            if action == "EXPRESS":
                if self.ws.tick - self._last_express_tick < EXPRESSION_MIN_GAP_TICKS:
                    event["not_sent"] = "LIGHT_TOO_SOON"
                    continue
                self._last_express_tick = self.ws.tick
            self._requests += 1
            request_id = f"act_{self.agent_id}_{self._requests:05d}"[:64]
            event["request_id"] = request_id
            self._presence_events[request_id] = event
            out.append({"schema_version": "1.0", "action_request_id": request_id,
                        "agent_id": self.agent_id, "based_on_tick_id": self.ws.tick, "action": action, "args": args})
        self._presence_out = []
        self.stats["presence"] = self.stats.get("presence", 0) + len(out)
        # Departures released once their closing line was accepted (FN-1, D-66), rechecked first.
        released, self._release_out = self._release_out, []
        for request in released:
            reason = self._irrelevant(self._sent.get(request["action_request_id"], {}), since_ms=None)
            if reason is not None:
                self._discard(request, reason)
                continue
            request["based_on_tick_id"] = self.ws.tick      # rechecked against this observation just now
            out.append(request)
            self._delivery("RELEASED", request, "closing line accepted")
        return out

    def _moves_away(self, a: dict[str, Any]) -> bool:
        """A MOVE_TO that takes the agent away from its conversation partner."""
        if a["action"] != "MOVE_TO" or self.conversation.partner is None:
            return False
        partner = self.conversation.partner
        state = self.ws.tracks.get(partner)
        target = a["args"].get("target_id")
        dest = a["args"].get("destination")
        if target is not None:
            return target != partner
        if dest is not None and state is not None and state.x is not None and self.ws.pose is not None:
            d_now = math.hypot(state.x - self.ws.pose["x"], state.z - self.ws.pose["z"])
            return math.hypot(state.x - dest["x"], state.z - dest["z"]) > d_now + 0.5
        return False

    def _audible_closing(self, a: dict[str, Any]) -> bool:
        """A closing or excuse line the partner could hear (FN-1, G3d D-66): addressed to them, or LOCAL
        speech to nobody in particular while they are within earshot. Earshot is the conversation
        range (3.5 m: speech is clear that far on the main floor, D-40)."""
        if a["action"] != "SPEAK" or not is_closing(a["args"].get("text", "")):
            return False
        partner = self.conversation.partner
        to = a["args"].get("addressee_id")
        if to is not None:
            return to == partner
        state = self.ws.tracks.get(partner) if partner else None
        return a["args"].get("channel") == "LOCAL" and state is not None and state.range_m is not None \
            and state.range_m <= self.pulse_cfg["conversation"]["range_m"]

    def _fn1_problem(self, actions: list[dict[str, Any]], activity: dict[str, Any] | None) -> str | None:
        """FN-1 (D-61, agent policy, not the host's gate): during an open conversation, moving away
        needs a closing or excuse line the partner could hear, before the departure in the same
        answer (G3d, D-66)."""
        if self.pulse is None or not self._conversation_open():
            return None
        partner = self.conversation.partner
        first_move = next((i for i, a in enumerate(actions) if self._moves_away(a)), None)
        leaving = first_move is not None or (
            activity is not None and activity.get("kind") in ("TRAVEL_TO", "SURVEY", "RETURN_TO_POST", "REST"))
        if not leaving:
            return None
        closing = next((i for i, a in enumerate(actions) if self._audible_closing(a)), None)
        if closing is not None and (first_move is None or closing < first_move):
            return None
        if closing is None and any(a["action"] == "SPEAK" and is_closing(a["args"].get("text", "")) for a in actions):
            return (f"you are in a conversation with {partner}: your closing line must be said to {partner} "
                    "(addressee_id) so they hear it, before moving away")
        if closing is not None:
            return (f"you are in a conversation with {partner}: say the closing line first, then move away "
                    "(put the SPEAK before the MOVE_TO)")
        return (f"you are in a conversation with {partner}: before moving away, say a closing or excuse line "
                f"to {partner} first in the same answer (for example \"Excuse me, I need to go\"), or stay with them")

    def _answer_check(self, actions: list[dict[str, Any]], activity: dict[str, Any] | None) -> Any:
        """The runtime's policy check of an answer: None, an error (FN-1: the answer is refused and
        repaired, or held), or ActivityDropped (G3h, D-110): the optional activity broke a rule, so
        the gateway drops it and keeps the actions; the runtime then derives one (D-61)."""
        if activity is not None:
            _, error = activities.parse(activity, now_ms=self.ws.now_ms,
                                        default_review_s=self.pulse_cfg["pulse"]["default_review_after_s"],
                                        max_review_s=self.pulse_cfg["pulse"]["max_review_after_s"],
                                        open_commitments={c["memory_id"] for c in self.memory.open_commitments()},
                                        perceived={t for t in self.ws.tracks if self.ws.visible(t)})
            if error:
                return ActivityDropped(activities.rule_of(error), error)
        return self._fn1_problem(actions, activity)

    def _set_activity(self, job: DecisionJob, proposals: list[Proposal],
                      requests: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        cfg = self.pulse_cfg["pulse"]
        chosen = None
        if self._answer_activity is not None:
            chosen, _ = activities.parse(self._answer_activity, now_ms=self.ws.now_ms,
                                         default_review_s=cfg["default_review_after_s"],
                                         max_review_s=cfg["max_review_after_s"],
                                         open_commitments={c["memory_id"] for c in self.memory.open_commitments()},
                                         perceived={t for t in self.ws.tracks if self.ws.visible(t)})
        self._answer_activity = None
        if chosen is None:
            promised = {t: c["memory_id"] for c in self.memory.open_commitments() for t in c["audience_present"]}
            promised.update({st["commit"]["target"]: st["commit"]["memory_id"] for st in self._staged.values()
                             if "commit" in st and st["commit"]["target"]})        # made now, not yet accepted
            chosen = activities.derive([{"action": p.action, "args": p.args, "commitment": p.commitment}
                                        for p in proposals], now_ms=self.ws.now_ms, current=self.activity,
                                       partner=self.conversation.partner, promised=promised,
                                       default_review_s=cfg["default_review_after_s"],
                                       has_task_goal=self.task_goal is not None or bool(self.task),
                                       post_duty=self.post_duty)
        if chosen.kind in ("SURVEY", "RETURN_TO_POST") and self.activity is not None and \
                self.activity.kind in ("SURVEY", "RETURN_TO_POST") and chosen.source != "CHOSEN":
            chosen.kind, chosen.destination = self.activity.kind, self.activity.destination
        self.activity = chosen
        self.pulse.last_review_ms = self.ws.now_ms
        self.pulse.schedule(self.ws.now_ms, chosen, reset=True)
        self._sitrep_changes = []
        waited = self.ws.now_ms - self._first_trigger_ms if self._first_trigger_ms is not None else 0
        self._first_trigger_ms = None
        reqs = requests or []
        self._log("REVIEW" if "PULSE_REVIEW" in job.triggers else "DECISION", policy=job.policy,
                  triggers=job.triggers, activity=chosen.kind, source=chosen.source, waited_ms=waited,
                  tokens=job.assembled.record["total_tokens"] if job.assembled else None,
                  # G3d (D-65): what it responded to and at whom it acted, for source-linked metrics.
                  sources=list(job.sources),
                  targets=sorted({t for r in reqs for t in [r["args"].get("addressee_id", r["args"].get("target_id"))]
                                  if t}),
                  actions=[[r["action_request_id"], r["action"], r["args"].get("addressee_id", r["args"].get("target_id"))]
                           for r in reqs])
        return chosen.record()

    # ---------- the Agent Director (G4b, D-98) ----------

    def editable(self) -> dict[str, Any]:
        """What the Director may see and edit (Blueprint §10.2), and what it can see but never edit."""
        from range_service.director import LOCKED   # noqa: PLC0415

        return {"directive": self.identity.directive, "goal": self.task or self.identity.public_goal,
                "sliders": dict(sorted(self.style.items())), "locked": list(LOCKED)}

    def apply_edit(self, field: str, value: Any, name: str | None = None) -> tuple[str | None, str | None, str | None]:
        """Apply a Director edit; it takes effect at the next decision (the next assembled prompt) and
        never rewrites past context: records, prompts and memory are untouched. Returns
        (refusal reason or None, before, after). A directive edit changes the persona prefix, so its
        key changes and no warm slot or snapshot of the old persona is used again; an NPC's new
        prefix is queued for a snapshot (T5/T6)."""
        from range_service.director import MAX_DIRECTIVE, MAX_GOAL   # noqa: PLC0415

        if field == "directive":
            if not isinstance(value, str) or not 0 < len(value) <= MAX_DIRECTIVE:
                return "INVALID_VALUE", None, None
            before, self.identity.directive = self.identity.directive, value
            self._prefixes.clear()
            if self.npc_model and self.gateway is not None:
                for tier in self.model_tiers():
                    key, prefix = self.persona_prefix(tier)
                    self.snapshots_wanted.append((tier, key, prefix))
            after = value
        elif field == "goal":
            if not isinstance(value, str) or not 0 < len(value) <= MAX_GOAL:
                return "INVALID_VALUE", None, None
            before = self.task or self.identity.public_goal
            self.task = value
            after = value
        elif field == "slider":
            if name not in self.style:
                return "NOT_EDITABLE", None, None
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100 \
                    or not float(value).is_integer():
                return "INVALID_VALUE", None, None
            before = json.dumps(self.style, sort_keys=True)
            self.style[name] = int(value)
            after = json.dumps(self.style, sort_keys=True)
        else:
            return "NOT_EDITABLE", None, None
        self.edits.append({"at_ms": self.ws.now_ms, "field": field, "name": name})
        return None, before, after

    def take_snapshots(self) -> list[tuple[str, str, str]]:
        wanted, self.snapshots_wanted = self.snapshots_wanted, []
        return wanted

    # ---------- persona prefixes, pre-warming and promotion latency (G3c-1; T5, T6) ----------

    def _handles_for(self, tier: str, policy: str) -> HandleMap | None:
        """G3h (D-111): Robot R's prompts and answers use handles under the LEAN answer format."""
        if policy != "MODEL" or tier != "FOCAL" or self.answer_condition() != "LEAN":
            return None
        if self.handles is None:
            self.handles = HandleMap()
        return self.handles

    def answer_condition(self) -> str:
        """Robot R's answer condition on its gateway (FULL, SHORT, LEAN; G3f D-77, G3g D-85)."""
        return getattr(self.gateway, "answer", "FULL") if self.gateway is not None else "FULL"

    def persona_prefix(self, tier: str) -> tuple[str, str]:
        """(key, text) of this agent's stable prompt prefix at ``tier``: guardrails and identity,
        identical from call to call. The key changes if the text does (model + prompt version)."""
        if tier not in self._prefixes:
            assembler = ContextAssembler(self.tokenizer, tier)
            # The same guardrails as the prompt: with the pulse on they carry the activity format
            # (G3f, D-76: without it no prompt started with its prefix).
            text = assembler.persona_prefix(
                guardrails.guardrails_section(tier, self.allowed_actions, self.body, self.expressions,
                                              activity=self.pulse is not None, answer=self.answer_condition()),
                self.identity)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
            self._prefixes[tier] = (f"{self.agent_id}:{tier}:{digest}", text)
        return self._prefixes[tier]

    def answer_choices(self) -> dict[str, Any]:
        """What this agent may name in its next answer (G3c-2, D-60): the people it perceives now
        (never an invented id), the channels it may use, its body's gestures and expressions."""
        targets = sorted(t for t in self.ws.tracks if self.ws.visible(t))
        channels = ["LOCAL"] + (["PA"] if self.pa_operator else [])
        gestures = list(self.body["gestures"]) if self.body["capabilities"]["can_gesture"] else []
        return {"targets": targets, "channels": channels, "gestures": gestures, "expressions": list(self.expressions)}

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
        # D-70 (owner 2026-11-19): the card now holds the conversation, so its raw heard items expire
        # after the retention window (unless tied to an open promise or a correction).
        self.memory.summarized(set(conv.participants), conv.since_ms, self.ws.now_ms)
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
            text = f"In conversation with {self.conversation.partner}. Task: {self.task or self.identity.public_goal}"
        else:
            text = f"Task: {self.task or self.identity.public_goal}"
        pending = self.pending_line()
        return text + ("\n" + pending if pending else "")

    def pending_line(self) -> str | None:
        """What was sent but not yet accepted by the world (G3d, D-64): one line in the next decision,
        never memory. In stepped runs results arrive before the next sample, so it is always empty."""
        parts = []
        for request_id, st in self._staged.items():
            if "speech" in st:
                to = st["speech"]["target"]
                parts.append(f'SPEAK{" to " + to if to else ""} "{st["speech"]["text"][:60]}"')
            if "commit" in st:
                parts.append(f'promise "{st["commit"]["text"][:60]}"')
            if "fulfill" in st:
                parts.append("keeping a promise")
        for held in self._held.values():
            parts += [f"{r['action']} (waits for your closing line)" for r in held]
        if not parts:
            return None
        return "Sent, not yet confirmed by the world: " + "; ".join(parts[:4]) + ". Do not repeat them."

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
            goal = self._goal_text()
            if self.pulse is not None:
                goal += "\n" + self.sitrep()
            handles = self._handles_for(tier, policy)
            assembled = assembler.assemble(
                guardrails=guardrails.guardrails_section(tier, self.allowed_actions, self.body, self.expressions,
                                                         activity=self.pulse is not None, answer=self.answer_condition()),
                identity=self.identity, memory=self.memory, ws=self.ws, setting=self.setting, goal=goal,
                triggers=[t.lower().replace("_", " ") for t in triggers], participants=participants, topics=topics,
                audience=disclosure.audience_from_packet(packet), rename=handles.rename if handles else None)
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
        choices = self.answer_choices() if policy == "MODEL" else None
        if choices is not None and self.pulse is not None:
            choices["activity"] = self.pulse_cfg["pulse"]["max_review_after_s"]
        handles = self._handles_for(tier, policy) if tier != "C0" else None
        if handles is not None and choices is not None:
            # G3h (D-111): the model names people by handle; the answer is mapped back before anything leaves.
            choices["targets"] = [handles.handle(x) for x in choices["targets"]]
            demo_hint = handles.rename(demo_hint) if demo_hint else demo_hint
        if self.pulse is not None and policy == "MODEL" and set(triggers) <= IDLE_WORK_TRIGGERS and \
                (self.activity is None or self.activity.kind in activities.IDLE_KINDS):
            # The idle budget caps attempted work (G3d, D-67): debited when the job is admitted,
            # so a review later cancelled, pre-empted or timed out still counts.
            self.pulse.model_reviews_at.append(self.ws.now_ms)
            self._log("IDLE_DEBIT", decision_id=decision_id, triggers=triggers)
        return DecisionJob(decision_id, self.ws.tick, triggers, policy, tier, self.cognition.level, assembled,
                           proposals, demo_hint, prefix_key, choices, started_at=time.monotonic(), now_ms=self.ws.now_ms,
                           handles=handles if policy == "MODEL" else None)

    async def decide(self, job: DecisionJob) -> list[dict[str, Any]]:
        """Answer a job: returns the action requests to send. Model calls happen here."""
        self.pending = True
        self.pending_kind = "PULSE" if job.triggers == ["PULSE_REVIEW"] else "REAL"
        self.pending_policy = job.policy
        try:
            model_calls: list[dict[str, Any]] = []
            fallback = None
            if job.proposals is not None:
                proposals = job.proposals
            else:
                assert self.gateway is not None and job.assembled is not None
                call_started = time.perf_counter()
                for rec in self._open_promotions:
                    if "to_first_model_call_ms" not in rec:
                        # G3c-2 (D-60): promotion -> the first model call starts, apart from the call itself
                        rec["to_first_model_call_ms"] = round((call_started - rec["_t0"]) * 1000)
                result = await self.gateway.decide(
                    agent_id=self.agent_id, tier=job.tier, prompt=job.assembled.prompt,
                    prompt_sha256=job.assembled.record["prompt_sha256"], max_tokens=OUTPUT_CAPS.get(job.tier, 120),
                    allowed_actions=self.allowed_actions, tick=job.tick, demo_hint=job.demo_hint,
                    prefix_key=job.prefix_key,
                    # NPCs: the persona prefix may go as its own (system) message. Robot R's prompt
                    # stays one message, as the G3b bake-off measured it, unless its gateway runs the
                    # SYSTEM_PREFIX layout condition (G3f, D-76). The prompt text is the same either way.
                    prefix=self.persona_prefix(job.tier)[1]
                    if self.npc_model or getattr(self.gateway, "prompt_layout", "ONE_MESSAGE") == "SYSTEM_PREFIX" else None,
                    choices=job.choices, background=job.triggers == ["PULSE_REVIEW"],
                    check=self._answer_check if self.pulse is not None else None, started_at=job.started_at,
                    evidence_ms=job.now_ms, handles=job.handles)
                model_calls, fallback = result.model_calls, result.fallback
                proposals = [_proposal_from_model(a, self.memory, self.conversation) for a in result.actions]
                self._answer_activity = result.activity
                if result.activity_dropped is not None:
                    self._log("ACTIVITY_DROPPED", rule=result.activity_dropped["rule"], decision_id=job.decision_id)
                if fallback is not None and self.pulse is not None and "conversation with" in (result.fallback_error or ""):
                    # FN-1: the repair also walked away without a word. Stay engaged instead. Recorded as
                    # held by FN-1 (G3h, D-110): the right outcome, not a failure.
                    partner = self.conversation.partner
                    proposals = [Proposal("LOOK_AT", {"target_id": partner}), Proposal("WAIT", {"duration_ms": 1000})]
                    fallback = {"action": "WAIT", "reason": "FN1_HELD"}
                    self._log("FN1_HELD", partner=partner, how="model answer replaced after one repair")
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
            self.pending_kind = None
            self.pending_policy = None

    def decide_now(self, job: DecisionJob) -> list[dict[str, Any]]:
        """Synchronous answer for jobs that need no model (ROUTINE, TEMPLATE, DEMO)."""
        if job.proposals is None:
            raise ValueError("this job needs the model; use decide()")
        proposals = job.proposals
        if self.pulse is not None and self._fn1_problem([p.as_dict() for p in proposals], None):
            proposals = [p for p in proposals if p.action != "MOVE_TO"]          # FN-1: stay engaged
            self._log("FN1_HELD", partner=self.conversation.partner, how="rule policy move dropped")
        return self._emit(job, proposals, [], None)

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
        # FN-1 (D-66): a departure after an audible closing line waits until the host accepts that line.
        closing_at = None
        if self.pulse is not None and self._conversation_open():
            closing_at = next((i for i, p in enumerate(kept) if self._audible_closing(p.as_dict())), None)
        closing_id = None
        held: list[dict[str, Any]] = []
        for i, p in enumerate(kept):
            self._requests += 1
            request_id = f"act_{self.agent_id}_{self._requests:05d}"[:64]
            request = {"schema_version": "1.0", "action_request_id": request_id, "agent_id": self.agent_id,
                       "based_on_tick_id": job.tick, "action": p.action, "args": p.args}
            commitment_id = None
            target = p.args.get("addressee_id", p.args.get("target_id"))
            # Memory follows what the world accepts (D-64): staged here, applied in on_result.
            staged: dict[str, Any] = {}
            if p.commitment:
                commitment_id = self.memory.reserve_id()
                staged["commit"] = {"text": p.commitment, "target": target, "memory_id": commitment_id,
                                    "at_ms": self.ws.now_ms}
            if p.fulfills:
                staged["fulfill"] = list(p.fulfills)
            if p.action == "SPEAK":
                staged["speech"] = {"text": p.args["text"], "target": target,
                                    "start": target is not None and self.conversation.partner is None,
                                    "touch": target is not None and target == self.conversation.partner}
            if staged:
                self._staged[request_id] = staged
            checked = p.action == "MOVE_TO" or (p.action in ("SPEAK", "GESTURE") and target is not None) \
                or bool(p.commitment) or bool(p.fulfills)
            self._sent[request_id] = {"action": p.action, "commitment_id": commitment_id, "decision_id": job.decision_id,
                                      "replanned": "ACTION_REJECTED" in job.triggers, "target": target,
                                      "checked": checked, "job_ms": job.now_ms, "policy": job.policy,
                                      "tier": job.tier, "started_at": job.started_at,
                                      "expression_id": p.args.get("expression_id") if p.action == "EXPRESS" else None,
                                      "destination": p.args.get("destination") if p.action == "MOVE_TO" else None}
            if closing_at is not None and i == closing_at:
                closing_id = request_id
            if closing_id is not None and i > closing_at and self._moves_away(p.as_dict()):
                held.append(request)
                continue
            requests.append(request)
        if held:
            self._held[closing_id] = held
            for r in held:
                self._delivery("HELD_FOR_CLOSING", r, f"waits for {closing_id} to be accepted")
        if self.conversation.closing:
            self._end_conversation("FAREWELL")
        self.stats["decisions"] += 1
        self.stats["requests"] += len(requests)
        self._last_fallback = fallback is not None and job.policy == "MODEL"
        if fallback is not None:
            self.stats["fallbacks"] += 1
        record = {
            "schema_version": "1.0", "decision_id": job.decision_id, "agent_id": self.agent_id,
            "based_on_tick_id": job.tick, "cognition_level": job.level, "tier": job.tier, "policy": job.policy,
            "triggers": job.triggers, "context": job.assembled.record if job.assembled else None,
            "model_calls": model_calls,
            "action_request_ids": [r["action_request_id"] for r in requests + held],
            "fallback": fallback,
        }
        if self.pulse is not None:
            if self._fn1_problem([p.as_dict() for p in kept], None) and any(p.action == "MOVE_TO" for p in kept):
                self._log("FN1_VIOLATION", partner=self.conversation.partner)      # should never happen (tested)
            record["activity"] = self._set_activity(job, kept, requests + held)
        self.records.append(record)
        if job.assembled is not None:
            entry = {"decision_id": job.decision_id, "prompt": job.assembled.prompt}
            if job.choices is not None:
                entry["choices"] = job.choices
            if job.handles is not None:
                entry["handles"] = job.handles.snapshot()     # G3h (D-111): handle -> anonymous id (evaluator view)
            self.prompts.append(entry)
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
        presence = self._presence_events.pop(request_id, None)
        if self.pulse is not None and (sent is not None or presence is not None):
            # Accepted outcomes, not only proposals (G3d, D-65).
            self._log("RESULT", request_id=request_id, accepted=bool(result["accepted"]),
                      reason_code=result["reason_code"],
                      action=sent["action"] if sent is not None else presence.get("event"))
        if self.ambient is not None and presence is not None and presence.get("event") == "AMBIENT":
            self.ambient.result(presence["expression"], bool(result["accepted"]))
        if self.ambient is not None and sent is not None and sent["action"] == "EXPRESS" and result["accepted"]:
            # A chosen expression overrides the ambient display for its hold time (D-73).
            self.ambient.override(sent.get("expression_id"), self.ws.now_ms)
        staged = self._staged.pop(request_id, None)
        held = self._held.pop(request_id, None)
        if sent is None:
            return
        if result["accepted"]:
            if sent["action"] == "MOVE_TO":
                # G3f (SB-10): where it is walking, from its own accepted move (no speed in the packet).
                self.travel_to = sent.get("destination")
            elif sent["action"] in ("TURN_TO", "STOP"):
                self.travel_to = None
            if staged:
                self._apply(staged)
            if held:
                self._release_out += held          # sent with the next sample, after a recheck (FN-1)
            return
        self.stats["rejected"] += 1
        # A rejection leaves memory as it was (D-64): nothing staged is applied.
        if staged and "commit" in staged:
            self._forget_promise(staged["commit"]["memory_id"])
        if held:
            for r in held:
                self._delivery("DROPPED", r, f"the closing line was refused ({result['reason_code']}): stays")
            self._log("FN1_STAYED", partner=self.conversation.partner, refused=result["reason_code"])
            self._stay_with_partner()
        # One replan per rejected decision, from the next observation (T27); never a loop.
        if result["reason_code"] in REPLAN_REASONS:
            self._allow_replan(sent)

    def _apply(self, staged: dict[str, Any]) -> None:
        """Apply an accepted request's memory changes, once (D-64)."""
        if "commit" in staged:
            c = staged["commit"]
            self.memory.commit(c["text"], c["target"], now_ms=c["at_ms"], memory_id=c["memory_id"])
        for memory_id in staged.get("fulfill", []):
            try:
                if self.memory.get(memory_id)["content"].get("commitment_state") == "OPEN":
                    self.memory.set_commitment_state(memory_id, "FULFILLED")
            except KeyError:
                pass
        if "speech" in staged:
            sp = staged["speech"]
            self.ws.my_turn(sp["text"], sp["target"])
            self._speaking_until_ms = max(self._speaking_until_ms, self.ws.now_ms + min(8000, 60 * len(sp["text"])))
            if sp["start"] and self.conversation.partner is None:
                self._start_conversation(sp["target"], None)
            if sp["touch"] and sp["target"] == self.conversation.partner:
                self.conversation.last_exchange_ms = self.ws.now_ms

    def _forget_promise(self, memory_id: str) -> None:
        """A promise the world never heard: the activity built on it no longer holds."""
        if self.activity is not None and self.activity.commitment_id == memory_id:
            self.activity = None

    def _stay_with_partner(self) -> None:
        partner = self.conversation.partner
        if partner is not None and self.pulse is not None:
            self.activity = activities.Activity("CONVERSE", partner, None, 20, [{"addressed": True}, {"target_lost": True}],
                                                "DERIVED", self.ws.now_ms)

    def _allow_replan(self, sent: dict[str, Any]) -> None:
        if not sent["replanned"] and sent["decision_id"] not in self._replanned_decisions:
            self._replanned_decisions.add(sent["decision_id"])
            self._replan_due = True
            self.stats["replans"] += 1

    # ---------- before sending: is the answer still relevant? (G3d, D-63) ----------

    def _irrelevant(self, info: dict[str, Any], since_ms: int | None = None) -> str | None:
        """Why a sent-to-be action no longer fits the agent's latest observation, or None."""
        if not info or not info.get("checked"):
            return None
        target = info.get("target")
        if target is not None and not self.ws.visible(target):
            return "TARGET_NOT_PERCEIVED"
        since = info["job_ms"] if since_ms is None else since_ms
        others = {who for at, who in self._addressed_log if at > since and who != target}
        if others:
            return "SOMEONE_ELSE_ADDRESSING"
        return None

    def recheck(self, requests: list[dict[str, Any]], live: bool = True) -> list[dict[str, Any]]:
        """Just before sending a decision's requests (the sidecar calls it): drop what no longer fits
        the latest observation, and (live) a model answer that missed its decision deadline. Dropped
        requests are recorded with the reason, their staged memory changes are discarded, and the
        decision may replan once. In stepped runs nothing changes while the agents think."""
        keep = []
        for request in requests:
            info = self._sent.get(request["action_request_id"], {})
            reason = self._irrelevant(info)
            if reason is None and live and info.get("policy") == "MODEL" and self.gateway is not None:
                limit_ms = self.gateway.deadlines_ms.get(info["tier"], 0) + SEND_GRACE_MS
                if (time.monotonic() - info["started_at"]) * 1000 > limit_ms:
                    reason = "DECISION_DEADLINE_PASSED"
            if reason is None:
                keep.append(request)
                continue
            self._discard(request, reason)
            if reason != "DECISION_DEADLINE_PASSED":
                self._allow_replan(info)
        return keep

    def _discard(self, request: dict[str, Any], reason: str) -> None:
        request_id = request["action_request_id"]
        staged = self._staged.pop(request_id, None)
        if staged and "commit" in staged:
            self._forget_promise(staged["commit"]["memory_id"])
        for r in self._held.pop(request_id, []):          # a dropped closing line keeps its departure back too
            self._delivery("DROPPED", r, "its closing line was not sent: stays")
            self._stay_with_partner()
        self.stats["discarded"] = self.stats.get("discarded", 0) + 1
        self._delivery("DISCARDED", request, reason)

    def _delivery(self, what: str, request: dict[str, Any], reason: str) -> None:
        info = self._sent.get(request["action_request_id"], {})
        self.delivery_log.append({"event": what, "at_ms": self.ws.now_ms, "tick": self.ws.tick,
                                  "decision_id": info.get("decision_id"), "action_request_id": request["action_request_id"],
                                  "action": request["action"], "target": info.get("target"), "reason": reason})
        if self.pulse is not None:
            self._log("DELIVERY", what=what, request_id=request["action_request_id"], action=request["action"],
                      reason=reason)


_TRIGGER_ORDER = ["START", "ADDRESSED_SPEECH", "DIRECTED_GESTURE", "DIRECTED_EXPRESSION", "PERSON_NEAR",
                  "PARTNER_LEFT", "GROUP_INVITE", "ACTION_REJECTED", "COMMITMENT_DUE", "TASK_STEP",
                  "WAKE_CONDITION", "PULSE_REVIEW"]


def _source_of(item: dict[str, Any]) -> str:
    """Who an observation came from: its track, or for an unseen voice its direction (as presence keys it)."""
    if item.get("track_id"):
        return item["track_id"]
    return voice_key(item.get("bearing_rad") or 0.0)


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
