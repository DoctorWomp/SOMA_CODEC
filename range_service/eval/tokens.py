"""What each field of Robot R's answer costs in tokens (G3g, D-84).

``field_spans(text)`` reads an answer (also one cut off at the output cap) and says, for every
character, which field it belongs to. ``account(text, pieces)`` adds up tokens per field from the
token pieces of that text: the pieces the model generated (llama-server's ``logprobs``), or the
model's own tokenization of the text (``/tokenize`` with pieces). A token belongs to the field of
its first character that is not white space.

Fields (the owner's list): ``actions`` (the action names and the list's JSON), ``args`` (an
action's arguments, apart from speech), ``speech`` (SPEAK and REQUEST_CLARIFICATION text),
``ids`` (G3h: tokens holding part of a person's id, a track id or a handle, wherever it is),
``numbers`` (G3h: numeric literals in an action's arguments), ``promise`` (``commitment``, ``fulfills_commitment``), ``activity`` (kind, target, review time),
``wake`` (wake conditions), ``reason`` (``reason_summary``), ``space`` (tokens that are only white
space: line breaks and indentation between JSON elements, which the grammar allows anywhere between
them; G3g found them a large share of a small model's answer) and ``other`` (the outer braces,
anything unparsed).

Counts only: no answer text leaves this module except through the caller.
"""

from __future__ import annotations

import json
import re
import statistics
from typing import Any

FIELDS = ("actions", "args", "ids", "numbers", "speech", "promise", "activity", "wake", "reason", "space", "other")
# G3h (D-111): a person's id in an answer, wherever it is (args, the activity): an anonymous track id
# or an observer-local handle (P1, P2, ...); and a numeric literal in an action's arguments.
ID_VALUE = re.compile(r'"(anon_[a-z0-9]{10}|P[0-9]{1,4})"')
_DEC = json.JSONDecoder()


class _Cut(Exception):
    pass


def field_spans(text: str) -> list[tuple]:
    """The JSON path that owns each character of ``text`` (an empty tuple outside the object)."""
    owner: list[tuple] = [()] * len(text)
    n = len(text)

    def ws(i: int, path: tuple) -> int:
        while i < n and text[i] in " \t\r\n":
            owner[i] = path
            i += 1
        return i

    def mark(a: int, b: int, path: tuple) -> None:
        for k in range(a, min(b, n)):
            owner[k] = path

    def value(i: int, path: tuple) -> int:
        i = ws(i, path)
        if i >= n:
            raise _Cut
        c = text[i]
        if c == "{":
            owner[i] = path
            i = ws(i + 1, path)
            while i < n and text[i] != "}":
                try:
                    key, j = _DEC.raw_decode(text, i)
                except ValueError:
                    mark(i, n, path + ("?",))
                    raise _Cut from None
                sub = path + (str(key),)
                mark(i, j, sub)
                i = ws(j, sub)
                if i >= n:
                    raise _Cut
                owner[i] = sub                       # the colon
                i = value(i + 1, sub)
                i = ws(i, path)
                if i < n and text[i] == ",":
                    owner[i] = path
                    i = ws(i + 1, path)
            if i >= n:
                raise _Cut
            owner[i] = path
            return i + 1
        if c == "[":
            owner[i] = path
            i = ws(i + 1, path)
            k = 0
            while i < n and text[i] != "]":
                i = value(i, path + (k,))
                k += 1
                i = ws(i, path)
                if i < n and text[i] == ",":
                    owner[i] = path
                    i = ws(i + 1, path)
            if i >= n:
                raise _Cut
            owner[i] = path
            return i + 1
        try:
            v, j = _DEC.raw_decode(text, i)
        except ValueError:
            mark(i, n, path)                         # a string or number cut off: the rest is this field's
            raise _Cut from None
        numeric = isinstance(v, (int, float)) and not isinstance(v, bool)
        mark(i, j, path + ("#num",) if numeric else path)
        return j

    try:
        value(0, ())
    except _Cut:
        pass
    return owner


def category(path: tuple) -> str:
    if not path:
        return "other"
    head = path[0]
    if head == "reason_summary":
        return "reason"
    if head == "activity":
        return "wake" if len(path) > 1 and path[1] in ("wake_if", "wake", "within_m") else "activity"
    if head == "actions":
        if len(path) >= 3 and path[2] in ("commitment", "fulfills_commitment"):
            return "promise"
        if len(path) >= 4 and path[2] == "args":
            if path[-1] == "#num":
                return "numbers"
            return "speech" if path[3] == "text" else "args"
        if len(path) >= 3 and path[2] == "args":
            return "args"
        return "actions"
    return "other"


def account(text: str, pieces: list[str]) -> dict[str, Any]:
    """Tokens per field. ``pieces`` must spell ``text`` when joined; if they do not (byte-level
    pieces of a multi-byte character), counting stops at the first mismatch and says so."""
    owner = field_spans(text)
    ids = [False] * len(text)
    for m in ID_VALUE.finditer(text):
        for k in range(m.start(1), m.end(1)):
            ids[k] = True
    counts = dict.fromkeys(FIELDS, 0)
    pos = 0
    aligned = True
    for piece in pieces:
        if text.startswith(piece, pos) and piece and not piece.strip():
            counts["space"] += 1
            pos += len(piece)
        elif text.startswith(piece, pos):
            first = pos
            while first < pos + len(piece) and text[first] in " \t\r\n":
                first += 1
            if first >= pos + len(piece):
                first = pos
            span = range(pos, min(pos + len(piece), len(text)))
            if any(ids[k] for k in span):
                counts["ids"] += 1                   # a token that holds part of a person's id
            else:
                counts[category(owner[first]) if first < len(owner) else "other"] += 1
            pos += len(piece)
        else:
            aligned = False
            counts["other"] += 1
    return {"tokens": len(pieces), "by_field": counts, "aligned": aligned and pos == len(text)}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per field: p50 and mean tokens per answer and the share of all tokens; plus totals."""
    if not rows:
        return {"n": 0}
    total = sum(r["tokens"] for r in rows)
    out: dict[str, Any] = {"n": len(rows), "tokens_p50": statistics.median(r["tokens"] for r in rows),
                           "tokens_mean": round(total / len(rows), 1), "by_field": {}}
    for f in FIELDS:
        vals = [r["by_field"][f] for r in rows]
        out["by_field"][f] = {"p50": statistics.median(vals), "mean": round(sum(vals) / len(vals), 1),
                              "share": round(sum(vals) / total, 3) if total else None,
                              "answers_with": sum(1 for v in vals if v)}
    return out
