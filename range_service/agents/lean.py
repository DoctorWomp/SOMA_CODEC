"""Robot R's LEAN answer format (G3g, D-85): a named condition, ``focal.answer: LEAN``.

The owner's G3f run showed generation dominating Robot R's call time (gen p50 ~2000 ms vs prefill
~300 ms; ~125 generated tokens per answer, p95 at the 200-token cap). LEAN removes what the
runtime never uses and writes the rest compactly, so nothing the runtime uses is lost:

- **No ``reason_summary``.** It is logged only and never fed back (CONTEXT_MEMORY_STRATEGY §6);
  the constrained answer does not offer it, so the model cannot spend tokens on it.
- **A compact, optional activity, last:** ``{"kind", "target_id"?, "commitment_id"?, "review_s"?,
  "within_m"?, "wake"?: ["addressed", ...]}``. ``expand`` turns it into the full activity the
  pulse protocol reads (D-61), before any check, so the intent monitor, records and metrics are
  unchanged. Without one the runtime derives an activity from the actions (D-61), as before.
  A targeted kind without ``target_id`` takes the person the answer's actions name.
- **Text limits after parsing, not in the grammar** (``GRAMMAR_TEXT_LIMITS``): speech and promise
  text are checked against the contract (500 and 200 characters) once the answer is parsed
  (gateway.parse_output), instead of as ``maxLength`` in the schema. D-84 has the measurement
  behind this choice.
- **On one line:** the format line asks for the JSON on one line (white space between JSON elements
  was about a quarter of a small model's answer tokens, D-84); the grammar still accepts any layout.

The prompt's answer-format lines (guardrails) say the same; ``rewrite_prompt`` turns a FULL prompt
of the offline prompt set into its LEAN version for the bake-off.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .activity import MAX_WAKE, PALETTE, TARGETED, WAKE_KINDS

# D-84 (llama.cpp b12443, measured in the cloud with T1): maxLength changes nothing while a string stays
# under it, but when it binds the grammar ends the string mid-sentence and the model then fills the
# allowed white space (up to 20 single-space tokens before the closing brace; +19 to +21 tokens in 3 of 8
# answers at SHORT's 60-character reason). So LEAN has no character limit in the grammar: the contract's
# limits are checked after parsing (gateway.parse_output). The owner's PC repeats it with F3 and F1.
GRAMMAR_TEXT_LIMITS = False
LEAN_KEYS = ("kind", "target_id", "commitment_id", "review_s", "within_m", "wake")
LEAN_WAKE = tuple(k for k in WAKE_KINDS if k != "target_within_m")
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)

OUTPUT_FORMAT_LEAN = (
    'Answer with one JSON object only, on one line: {"actions": [{"action": "...", "args": {...}}]} with 1 to 3 actions. '
    'A SPEAK, GESTURE or EXPRESS may add "commitment": "what you promise" or "fulfills_commitment": true. '
    'Your OPEN promises are listed under COMMITMENTS with an id. When an action keeps one (you now help, answer or '
    'greet the person you promised), add "fulfills_commitment": true to that action.'
)
ACTIVITY_FORMAT_LEAN = (
    'After the actions you may add "activity": {"kind": CONVERSE|WAIT_FOR|ATTEND|SURVEY|TRAVEL_TO|ASSIST|OBSERVE|'
    'RETURN_TO_POST|REST, "target_id": track (default: the person your actions name), "review_s": s, "within_m": m, '
    '"wake": [addressed, target_lost, speech_heard, new_track, commitment_due]}: what you do until one of these '
    "happens. Leave it out to keep doing what your actions imply. In a conversation, say goodbye or excuse yourself "
    "before leaving."
)


def schema_part(targets: tuple[str, ...] | None, max_review_s: int) -> dict[str, Any]:
    """The compact activity in a LEAN constrained answer (all fields but ``kind`` optional)."""
    target: dict[str, Any] = {"anyOf": [{"enum": list(targets)}, {"type": "null"}]} if targets else {"type": "null"}
    if targets is None:
        target = {"anyOf": [{"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"}, {"type": "null"}]}
    return {"type": "object", "additionalProperties": False, "required": ["kind"],
            "properties": {"kind": {"enum": list(PALETTE)}, "target_id": target,
                           "commitment_id": {"type": "string", "pattern": "^mem_[A-Za-z0-9_]{1,56}$"},
                           "review_s": {"type": "integer", "minimum": 5, "maximum": max_review_s},
                           "within_m": {"type": "number", "minimum": 0.5, "maximum": 30},
                           "wake": {"type": "array", "maxItems": MAX_WAKE, "items": {"enum": list(LEAN_WAKE)}}}}


def _named_person(actions: Any) -> str | None:
    for a in actions if isinstance(actions, list) else []:
        args = a.get("args") if isinstance(a, dict) else None
        if isinstance(args, dict):
            for key in ("addressee_id", "target_id", "to_id"):
                if isinstance(args.get(key), str):
                    return args[key]
    return None


def expand_activity(lean: Any, actions: Any) -> Any:
    """A compact activity as the full one (activity.parse checks it). Anything that is not a
    compact activity is returned unchanged, so the parser's error names the real problem."""
    if not isinstance(lean, dict) or set(lean) - set(LEAN_KEYS):
        return lean
    full: dict[str, Any] = {"kind": lean.get("kind")}
    target = lean.get("target_id")
    if target is None and "target_id" not in lean and lean.get("kind") in TARGETED:
        target = _named_person(actions)
    if target is not None:
        full["target_id"] = target
    if "commitment_id" in lean:
        full["commitment_id"] = lean["commitment_id"]
    if "review_s" in lean:
        full["review_after_s"] = lean["review_s"]
    wake: list[Any] = []
    if "within_m" in lean:
        wake.append({"target_within_m": lean["within_m"]})
    raw = lean.get("wake", [])
    for w in raw if isinstance(raw, list) else [raw]:
        wake.append({w: True} if isinstance(w, str) else w)
    if wake:
        full["wake_if"] = wake
    return full


def expand(text: str) -> str:
    """A LEAN answer's text with its compact activity written out in full; any other text as given."""
    body = text.strip()
    fenced = _FENCE.match(body)
    try:
        data = json.loads(fenced.group(1) if fenced else body)
    except ValueError:
        return text
    if not isinstance(data, dict) or not isinstance(data.get("activity"), dict):
        return text
    data["activity"] = expand_activity(data["activity"], data.get("actions"))
    return json.dumps(data)


def rewrite_prompt(prompt: str, answer: str, activity: bool) -> str:
    """An offline prompt (written with the FULL answer format) as Robot R would get it under
    ``answer`` (FULL, SHORT, LEAN) with or without the activity format (pulse on). Only the
    answer-format lines change; the rest of the prompt is the same text."""
    from .guardrails import ACTIVITY_FORMAT, OUTPUT_FORMAT   # noqa: PLC0415

    out = prompt
    if answer == "LEAN":
        out = out.replace(OUTPUT_FORMAT, OUTPUT_FORMAT_LEAN, 1)
    has = ACTIVITY_FORMAT in out or ACTIVITY_FORMAT_LEAN in out
    if activity and not has:
        line = ACTIVITY_FORMAT_LEAN if answer == "LEAN" else ACTIVITY_FORMAT
        head, sep, rest = out.partition("\n\n## IDENTITY")
        out = head + "\n" + line + sep + rest if sep else out
    elif activity and answer == "LEAN":
        out = out.replace(ACTIVITY_FORMAT, ACTIVITY_FORMAT_LEAN, 1)
    return out
