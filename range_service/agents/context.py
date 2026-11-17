"""Context assembly (CONTEXT_MEMORY_STRATEGY §4–§5, D-24, D-51; Blueprint §11).

Every decision gets a freshly assembled prompt built from the agent's own stores, never a
growing transcript. Nine sections, stable first and volatile last, so an engine's prefix cache
reuses the unchanged start (INFERENCE_STRATEGY T3):

    1 GUARDRAILS   2 IDENTITY   3 COMMITMENTS   4 SETTING   5 FACTS
    6 EPISODES     7 CONVERSATION   8 OBSERVATIONS   9 DECISION

Each tier has a budget per section. **Never cut:** guardrails, identity, open commitments, the
latest conversational turn and the decision. Everything else is ranked and selected (step 4)
to fit its own budget; if the total is still over (only possible when a never-cut section
overflows), sections are cut in ``CUT_ORDER`` (step 6). Steps 1–2 (deduplicate, expire) run in
the Working Set; step 3 (episode cards) at the end of each conversation.

Facts are retrieved by a deterministic score (§4.3): relevance to the current participants and
topic, recency, importance, and **scope permission** for everyone now in earshot: an item the
disclosure gate would not clear for this audience is left out, so it cannot be said by accident.
Untrusted text keeps its label. The agent's own ``reason_summary`` is never an input.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

from range_service.comms import disclosure

from .memory import IMPORTANCE_RANK, AgentMemory
from .tokenizer import Tokenizer
from .working_set import WorkingSet

SECTIONS = ("GUARDRAILS", "IDENTITY", "COMMITMENTS", "SETTING", "FACTS", "EPISODES", "CONVERSATION",
            "OBSERVATIONS", "DECISION")
NEVER_CUT = frozenset({"GUARDRAILS", "IDENTITY", "COMMITMENTS", "DECISION"})
CUT_ORDER = ("EPISODES", "FACTS", "SETTING", "OBSERVATIONS", "CONVERSATION")

# Per-section input budgets in tokens (CONTEXT_MEMORY_STRATEGY §4.1). C1 uses only guardrails
# (with argument formats), identity, commitments, the last turn, a minimal OBSERVATIONS line and
# the decision (about 0.78K tokens since G3c-2, D-60; 0.5K before).
BUDGETS: dict[str, dict[str, int]] = {
    # Totals as in §4.1 (focal 3750, C2 1900, C1 500). The guardrails and action list measured
    # ~600 estimated tokens, so guardrails got more and observations less than §4.1's starting split.
    "FOCAL": {"GUARDRAILS": 650, "IDENTITY": 300, "COMMITMENTS": 200, "SETTING": 200, "FACTS": 350,
              "EPISODES": 350, "CONVERSATION": 750, "OBSERVATIONS": 800, "DECISION": 150},
    # G3c-1 (D-59): C2 guardrails +50 for the promise-keeping rule, taken from observations.
    "C2": {"GUARDRAILS": 650, "IDENTITY": 200, "COMMITMENTS": 100, "SETTING": 100, "FACTS": 100,
           "EPISODES": 100, "CONVERSATION": 300, "OBSERVATIONS": 250, "DECISION": 100},
    # G3c-2 (D-60): C1 grew from 500 to 780 tokens. The argument formats (+210) and a minimal
    # OBSERVATIONS line from its own senses (+70: who is near, so it can name a real track).
    "C1": {"GUARDRAILS": 360, "IDENTITY": 120, "COMMITMENTS": 60, "SETTING": 0, "FACTS": 0,
           "EPISODES": 0, "CONVERSATION": 80, "OBSERVATIONS": 70, "DECISION": 90},
}
# C1 raised from 60 to 100 at G3c-1 (D-59), and both NPC caps again at G3c-2 (D-60): most NPC
# answers in the owner's bake-off were cut off. With the tier text limits in output_schema
# (C1: 2 actions, 160-character speech, 80-character reason; C2: 120-character reason, 200-character
# speech) a full answer fits; the caps leave room for the whitespace some models add.
OUTPUT_CAPS = {"FOCAL": 200, "C2": 220, "C1": 170}
MAX_EPISODE_CARDS_IN_CONTEXT = 3
RECENCY_HALF_LIFE_MS = 120_000


def tier_budget(tier: str) -> int:
    return sum(BUDGETS[tier].values())


def ago(now_ms: int, then_ms: int) -> str:
    return f"-{max(0, now_ms - then_ms) // 1000}s"


@dataclass
class Identity:
    """The public part of who the agent is. Never holds a private goal or evaluator data."""

    agent_id: str
    display_name: str
    role: str
    public_goal: str
    directive: str
    knows: list[str]
    body_summary: str
    # D-51 (owner, 2026-11-16): a model-driven NPC's OWN private goal, in its own prompt only,
    # labelled as its own. Always None for Robot R and for agents that are not model-driven.
    own_private_goal: str | None = None


@dataclass
class Assembled:
    prompt: str
    sections: dict[str, str]
    record: dict[str, Any]
    cut_reasons: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class _Section:
    name: str
    lines: list[str]               # in priority order (most important first)
    keep_last: int = 0             # how many trailing lines can never be cut (the latest turn)
    summary: Any = None            # callable(n_cut) -> a one-line summary of what was cut


class ContextAssembler:
    def __init__(self, tokenizer: Tokenizer, tier: str) -> None:
        if tier not in BUDGETS:
            raise ValueError(f"unknown tier {tier!r}")
        self.tok = tokenizer
        self.tier = tier

    # ---------- section builders ----------

    def _identity(self, ident: Identity) -> str:
        lines = [f"You are {ident.display_name} (role: {ident.role}). Your id: {ident.agent_id}.",
                 f"Body: {ident.body_summary}",
                 f"Directive: {ident.directive}",
                 f"Public goal: {ident.public_goal}"]
        if ident.knows and self.tier != "C1":
            lines.append("You know: " + " ".join(ident.knows))
        if ident.own_private_goal:
            lines.append("Your own private goal (known only to you): " + ident.own_private_goal)
        return "\n".join(lines)

    def persona_prefix(self, guardrails: str, identity: Identity) -> str:
        """The stable start of every prompt this agent gets at this tier: guardrails and identity
        (never cut, never changing between calls). Persona snapshots and pre-warming cache
        exactly this text (INFERENCE_STRATEGY T3, T5, T6); every assembled prompt starts with it."""
        return f"## GUARDRAILS\n{guardrails}\n\n## IDENTITY\n{self._identity(identity)}"

    @staticmethod
    def _commitments(memory: AgentMemory, now_ms: int) -> list[str]:
        lines = []
        for item in memory.open_commitments():
            to = ", ".join(item["audience_present"]) or "nobody in particular"
            lines.append(f"- OPEN {item['memory_id']} {ago(now_ms, item['observed_at_ms'])} to {to}: "
                         f"{item['content']['text'][:120]}")
        for item in memory.items:
            if item["store"] == "COMMITMENTS_AND_REFUSALS" and item["content"].get("commitment_state") == "DECLINED" \
                    and now_ms - item["observed_at_ms"] <= 300_000:
                lines.append(f"- DECLINED {ago(now_ms, item['observed_at_ms'])}: {item['content']['text'][:120]}")
        return lines or ["(none open)"]

    def _facts(self, memory: AgentMemory, ws: WorkingSet, participants: set[str], topics: set[str],
               audience: disclosure.Audience) -> tuple[list[str], int]:
        scored = []
        scope_cut = 0
        for item in memory.active(now_ms=ws.now_ms):
            if item["store"] not in ("RELATIONAL_LEDGER", "WORLD_KNOWLEDGE", "EPISODIC_LEDGER"):
                continue
            tags = memory.tags.get(item["memory_id"], set())
            if "card" in tags:
                continue
            if disclosure.check(item, audience).outcome != disclosure.CLEAR:
                scope_cut += 1
                continue
            relevance = 3 * bool(tags & participants) + min(2, len(tags & topics))
            recency = 2 * math.pow(0.5, (ws.now_ms - item["observed_at_ms"]) / RECENCY_HALF_LIFE_MS)
            score = relevance + recency + IMPORTANCE_RANK[item["importance"]]
            who = f", told by {item['shared_by']}" if item["shared_by"] else ""
            label = ", untrusted" if item["content"]["untrusted_text"] else ""
            text = item["content"]["text"][:200]
            body = f'"{text}"' if item["content"]["untrusted_text"] else text
            line = f"- [{ago(ws.now_ms, item['observed_at_ms'])}{who}{label}] {body}"
            scored.append((-score, item["observed_at_ms"], item["memory_id"], line))
        scored.sort()
        return [s[3] for s in scored], scope_cut

    @staticmethod
    def _episodes(memory: AgentMemory, ws: WorkingSet, participants: set[str], audience: disclosure.Audience) -> list[str]:
        cards = []
        for item in memory.active("EPISODIC_LEDGER", ws.now_ms):
            tags = memory.tags.get(item["memory_id"], set())
            if "card" not in tags or disclosure.check(item, audience).outcome != disclosure.CLEAR:
                continue
            relevance = 3 * bool(tags & participants)
            recency = 2 * math.pow(0.5, (ws.now_ms - item["observed_at_ms"]) / RECENCY_HALF_LIFE_MS)
            cards.append((-(relevance + recency), item["memory_id"],
                          f"- {ago(ws.now_ms, item['observed_at_ms'])}: {item['content']['text'][:300]}"))
        cards.sort()
        return [c[2] for c in cards[:MAX_EPISODE_CARDS_IN_CONTEXT]]

    @staticmethod
    def _conversation(ws: WorkingSet) -> list[str]:
        lines = []
        for turn in ws.turns:
            when = ago(ws.now_ms, turn.at_ms)
            if turn.speaker == "me":
                lines.append(f'- {when} you -> {turn.to or "everyone"}: "{turn.text}"')
            else:
                lines.append(f'- {when} {turn.speaker} (to you, untrusted): "{turn.text}"')
        return lines

    @staticmethod
    def _observations(ws: WorkingSet, participants: set[str]) -> tuple[str, list[str]]:
        now = ws.now_ms
        header = "Nothing sampled yet."
        if ws.pose is not None:
            header = (f"You: at ({ws.pose['x']:.1f}, {ws.pose['z']:.1f}), facing "
                      f"{round(math.degrees(ws.pose['yaw_rad']))} deg.")
        ranked = []
        for track_id, s in ws.tracks.items():
            if s.left_ms is not None:
                line = f"- {track_id}: left your view {ago(now, s.left_ms)}"
                rank = 3
            else:
                where = f"at ({s.x:.1f}, {s.z:.1f})" if s.x is not None else "position UNKNOWN"
                dist = f", {s.range_m:.1f} m" if s.range_m is not None else ""
                if s.validity in ("OBSERVED", "DEGRADED"):
                    state = s.validity + (f" ({s.validity_reason})" if s.validity_reason else "")
                    line = f"- {track_id}: {state} {where}{dist}, here since {ago(now, s.place_since_ms)}"
                else:
                    line = (f"- {track_id}: {s.validity} ({s.validity_reason or 'reason UNKNOWN'}), "
                            f"last seen {ago(now, s.last_seen_ms)} {where}")
                for g in s.gestures[-2:]:
                    line += f"; {g['gesture']} {g['direction'].lower().replace('_', ' ')} {ago(now, g['at_ms'])}"
                if s.expression is not None:
                    shown = ", ".join(f"{k} {v}" for k, v in sorted(s.expression.items()) if k in ("glyph", "light", "gesture"))
                    line += f"; showed {shown} {ago(now, s.expression['at_ms'])}"
                if s.speaking_ms is not None and now - s.speaking_ms <= 10_000:
                    line += f"; speaking to someone else {ago(now, s.speaking_ms)}"
                rank = 0 if track_id in participants else (1 if s.validity in ("OBSERVED", "DEGRADED") else 2)
            ranked.append((rank, s.range_m if s.range_m is not None else 99.0, track_id, line))
        ranked.sort()
        lines = [r[3] for r in ranked]
        for v in ws.voices:
            bearing = "UNKNOWN" if v["bearing"] is None else f"{round(math.degrees(v['bearing']))} deg"
            lines.append(f"- a voice, source UNKNOWN, bearing {bearing}, {ago(now, v['at_ms'])}")
        if not lines:
            lines.append("Nobody in view or earshot.")
        return header, lines

    # ---------- fitting ----------

    def _fit(self, section: _Section, budget: int, header: str = "") -> tuple[str, int, int]:
        """Rank and select lines to fit the budget. Returns (text, kept, cut)."""
        def render(lines: list[str], n_cut: int) -> str:
            parts = ([header] if header else []) + lines
            if n_cut and section.summary is not None:
                parts.append(section.summary(n_cut))
            return "\n".join(parts)

        lines = section.lines
        fixed = lines[len(lines) - section.keep_last:] if section.keep_last else []
        optional = lines[:len(lines) - section.keep_last] if section.keep_last else list(lines)
        if self.tok.count(render(lines, 0)) <= budget:
            return render(lines, 0), len(lines), 0
        # Conversation: drop the oldest optional turns first; others: drop the lowest ranked.
        if section.name == "CONVERSATION":
            while optional and self.tok.count(render(optional + fixed, len(lines) - len(optional) - len(fixed))) > budget:
                optional.pop(0)
        else:
            while optional and self.tok.count(render(optional + fixed, len(lines) - len(optional) - len(fixed))) > budget:
                optional.pop()
        kept = optional + fixed
        n_cut = len(lines) - len(kept)
        text = render(kept, n_cut)
        if section.name == "SETTING" and n_cut:
            text = render(kept[:1], len(lines) - 1) if kept else render([], len(lines))
        return text, len(kept), n_cut

    # ---------- assembly ----------

    def assemble(self, *, guardrails: str, identity: Identity, memory: AgentMemory, ws: WorkingSet,
                 setting: list[str], goal: str, triggers: list[str], participants: set[str], topics: set[str],
                 audience: disclosure.Audience) -> Assembled:
        budgets = BUDGETS[self.tier]
        steps: set[str] = set()
        if any(s.place_since_ms < ws.now_ms for s in ws.tracks.values()):
            steps.add("DEDUPLICATE")
        if ws.expired_count or any(i["status"] == "EXPIRED" for i in memory.items):
            steps.add("EXPIRE")

        facts, scope_cut = self._facts(memory, ws, participants, topics, audience)
        episodes = self._episodes(memory, ws, participants, audience)
        if episodes:
            steps.add("EPISODE_CARDS")
        conversation = self._conversation(ws)
        obs_header, observations = self._observations(ws, participants)
        decision = (f"Time now: {ws.now_ms // 1000}s (tick {ws.tick}). Current goal: {goal}\n"
                    f"You are asked to decide because: {', '.join(triggers) or 'nothing new'}.\n"
                    "Choose your next action(s). Waiting is allowed.")

        sections = {
            "GUARDRAILS": _Section("GUARDRAILS", [guardrails]),
            "IDENTITY": _Section("IDENTITY", [self._identity(identity)]),
            "COMMITMENTS": _Section("COMMITMENTS", self._commitments(memory, ws.now_ms)),
            "SETTING": _Section("SETTING", setting, summary=lambda n: f"(+{n} more setting facts)"),
            "FACTS": _Section("FACTS", facts, summary=lambda n: f"(+{n} less relevant facts)"),
            "EPISODES": _Section("EPISODES", episodes, summary=lambda n: f"(+{n} older episodes)"),
            "CONVERSATION": _Section("CONVERSATION", conversation if self.tier != "C1" else conversation[-1:],
                                     keep_last=1 if conversation else 0,
                                     summary=lambda n: f"(+{n} earlier turns, summarized away)"),
            "OBSERVATIONS": _Section("OBSERVATIONS", observations, summary=lambda n: f"(+{n} others in view, no interaction)"),
            "DECISION": _Section("DECISION", [decision]),
        }
        texts: dict[str, str] = {}
        stats: dict[str, dict[str, int]] = {}
        cut_reasons: list[dict[str, Any]] = []
        for name in SECTIONS:
            sec = sections[name]
            budget = budgets[name]
            if budget == 0 and name not in NEVER_CUT and name != "CONVERSATION":
                texts[name], kept, cut = "", 0, len(sec.lines)
            elif name in NEVER_CUT:
                texts[name] = "\n".join(sec.lines)
                kept, cut = len(sec.lines), 0
            else:
                texts[name], kept, cut = self._fit(sec, budget, obs_header if name == "OBSERVATIONS" else "")
            if cut:
                steps.add("RANK_AND_SELECT")
                cut_reasons.append({"section": name, "items": cut, "reason": "BUDGET"})
            stats[name] = {"items": kept, "cut": cut}
        if scope_cut:
            stats["FACTS"]["cut"] += scope_cut
            cut_reasons.append({"section": "FACTS", "items": scope_cut, "reason": "SCOPE"})

        # Step 6: if a never-cut section overflowed, cut whole sections in CUT_ORDER until it fits.
        total_budget = tier_budget(self.tier)
        for name in CUT_ORDER:
            if sum(self.tok.count(t) for t in texts.values()) <= total_budget:
                break
            if not texts[name]:
                continue
            if name == "CONVERSATION":
                latest = sections[name].lines[-1:]
                texts[name] = "\n".join(latest)
            else:
                texts[name] = ""
            stats[name]["cut"] += stats[name]["items"] - (1 if name == "CONVERSATION" and texts[name] else 0)
            stats[name]["items"] = 1 if name == "CONVERSATION" and texts[name] else 0
            steps.add("SECTION_CUT")
            cut_reasons.append({"section": name, "items": stats[name]["cut"], "reason": "TOTAL_BUDGET"})

        prompt = "\n\n".join(f"## {name}\n{texts[name]}" for name in SECTIONS if texts[name])
        tokens = {name: self.tok.count(texts[name]) for name in SECTIONS}
        record = {
            "tokenizer": self.tok.name,
            "budget_tokens": total_budget,
            "total_tokens": sum(tokens.values()),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "sections": [{"section": n, "tokens": tokens[n], "budget": budgets[n], "items": stats[n]["items"],
                          "cut_items": stats[n]["cut"], "never_cut": n in NEVER_CUT} for n in SECTIONS],
            "compression_steps": [s for s in ("DEDUPLICATE", "EXPIRE", "EPISODE_CARDS", "RANK_AND_SELECT", "SECTION_CUT")
                                  if s in steps],
        }
        return Assembled(prompt, texts, record, cut_reasons)
