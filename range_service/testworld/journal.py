"""Append-only JSONL event journal with a stable hash (Blueprint §13.3).

Every line is canonical JSON (sorted keys, no spaces, floats rounded to 1 µm /
1 µrad) so the same run always produces the same bytes and the same hash.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

FLOAT_DIGITS = 6


def _canonical(value: Any) -> Any:
    if isinstance(value, float):
        rounded = round(value, FLOAT_DIGITS)
        return 0.0 if rounded == 0 else rounded  # avoid "-0.0" vs "0.0"
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class EventJournal:
    def __init__(self) -> None:
        self._lines: list[str] = []
        self._entries: list[dict[str, Any]] = []

    def append(self, *, tick_id: int, sim_time_ms: int, kind: str, actor_id: str | None, payload: dict) -> dict:
        entry = {
            "schema_version": "1.0",
            "seq": len(self._entries),
            "tick_id": tick_id,
            "sim_time_ms": sim_time_ms,
            "kind": kind,
            "actor_id": actor_id,
            "payload": payload,
        }
        line = canonical_json(entry)
        stored = json.loads(line)  # what a reader of the file will see
        self._lines.append(line)
        self._entries.append(stored)
        return stored

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def to_jsonl(self) -> str:
        return "".join(line + "\n" for line in self._lines)

    def sha256(self) -> str:
        return hashlib.sha256(self.to_jsonl().encode("utf-8")).hexdigest()

    def write(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.to_jsonl(), encoding="utf-8", newline="\n")
        return out
