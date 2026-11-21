"""Short, observer-local handles for the people an agent perceives (G3h, D-111).

An anonymous track id (``anon_`` + 10 characters, from the observer filter, D-39) costs about 8
tokens in Robot R's answers (F1's tokenizer; ``"P1"`` costs 1 or 2), and an answer names 2 to 3
people. Under the LEAN answer format (D-85) Robot R's prompts and answers use handles instead:

- **P1, P2, ...** in order of first appearance, per agent (observer-local: another agent's P1 is
  someone else, or nobody).
- **Stable while the track lives, never reused** for another track in a run: a handle is given
  once and kept (the map only grows, by one entry per track the agent ever saw).
- **Only in the model's view.** The prompt text and the answer choices carry handles; the
  answer is mapped back to the anonymous ids **in the runtime, before anything leaves**
  (requests, memory, records of what was done). Packets, the journal and contracts keep the
  anonymous ids; nothing about the observer filter changes (D-39, D-62).
- **An unknown handle is refused like an unknown target:** an answer naming a handle the agent
  never gave is invalid output (repaired or WAIT), and its actions never reach the host.

The prompt and the raw answer as the model saw and wrote them (with handles) stay in the
evaluator records (prompts.jsonl, decision records), with the map in prompts.jsonl.
"""

from __future__ import annotations

import json
import re
from typing import Any

TRACK = re.compile(r"\banon_[a-z0-9]{10}\b")       # the observer filter's anonymous track ids
HANDLE = re.compile(r"^P[1-9][0-9]{0,3}$")
ID_KEYS = ("target_id", "addressee_id", "to_id")


class HandleMap:
    def __init__(self) -> None:
        self._to_handle: dict[str, str] = {}
        self._to_id: dict[str, str] = {}

    def handle(self, track_id: str) -> str:
        """The track's handle, given now if it has none (never reused)."""
        h = self._to_handle.get(track_id)
        if h is None:
            h = f"P{len(self._to_handle) + 1}"
            self._to_handle[track_id] = h
            self._to_id[h] = track_id
        return h

    def track(self, handle: str) -> str | None:
        return self._to_id.get(handle)

    def snapshot(self) -> dict[str, str]:
        """handle -> anonymous id, for the evaluator records (prompts.jsonl)."""
        return dict(self._to_id)

    def rename(self, text: str) -> str:
        """``text`` with every anonymous track id replaced by its handle (in order of appearance)."""
        return TRACK.sub(lambda m: self.handle(m.group(0)), text) if text else text

    def to_handles(self, value: Any) -> Any:
        """A JSON-like value with anonymous ids replaced by handles (answer choices, the Demo hint)."""
        if isinstance(value, str):
            return self.rename(value)
        if isinstance(value, list):
            return [self.to_handles(v) for v in value]
        if isinstance(value, dict):
            return {k: self.to_handles(v) for k, v in value.items()}
        return value

    def answer_to_ids(self, text: str) -> tuple[str, str | None]:
        """A model answer with the handles in its id fields mapped back to anonymous ids:
        (text, None), or (text, error) when it names a handle this agent never gave. Text that is
        not a JSON object is returned unchanged (the parser names that problem)."""
        try:
            data = json.loads(text)
        except ValueError:
            return text, None
        if not isinstance(data, dict):
            return text, None
        problems: list[str] = []

        def ids(obj: Any, where: str | None) -> Any:
            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    if k in ID_KEYS and isinstance(v, str) and HANDLE.match(v):
                        tid = self._to_id.get(v)
                        if tid is None:
                            if where is not None:
                                problems.append(f"{where}: {k} {v} is not a track you perceive")
                            out[k] = v
                        else:
                            out[k] = tid
                    else:
                        out[k] = ids(v, where)
                return out
            if isinstance(obj, list):
                return [ids(v, where) for v in obj]
            return obj

        actions = data.get("actions")
        if isinstance(actions, list):
            data["actions"] = [ids(a, f"action {i + 1}") for i, a in enumerate(actions)]
        if isinstance(data.get("activity"), dict):
            # An unknown handle here is left as it is: the activity check refuses its target and the
            # activity alone is dropped, the actions kept (D-110).
            data["activity"] = ids(data["activity"], None)
        return json.dumps(data), (problems[0] if problems else None)
