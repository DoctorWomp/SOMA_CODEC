# G0 — Repository, contracts and headless test world

**Status:** READY TO START · runs entirely in a cloud session (no Godot, no model, no GPU)
**Scope:** [RANGE_V0_SCOPE.md](../RANGE_V0_SCOPE.md) §4 · Blueprint §20 (G0) · [DECISIONS.md](../DECISIONS.md) D-03, D-04, D-11, D-13, D-15, D-27

## Goal

Lay the foundation every later gate builds on: the folder layout, the message formats (contracts), a tiny 2D Python world for testing rules without Godot, the ΔP math, and one command that checks everything, running in CI on every push.

When G0 is done, nothing is visible yet, but the rules that matter most (no evaluator truth reaching agents, missing ≠ zero, walls block sight, same seed → same run) are enforced by tests.

## Deliverables

1. **Skeleton (D-15):** `range_service/` with subpackages `horizon/`, `sensors/`, `agents/`, `comms/`, `eval/`, `testworld/`; plus `contracts/`, `configs/`, `tests/`, `tools/`, `models/README.md`, and `godot_app/README.md` (placeholder for G1).
2. **Python project:** `pyproject.toml` (Python ≥ 3.12), managed with `uv`, with a committed lockfile. Minimal dependencies: `jsonschema`, `pyyaml`, `pytest`; anything else needs a reason.
3. **Contracts v1** in `contracts/` as JSON Schema files (D-27), each with valid and invalid examples:
   - Messages: `envelope`, `observation`, `delta_feature`, `hypothesis`, `action_request`, `action_result`, `comms_event`, `intervention`
   - Records: `memory_item`, `run_manifest` (policy / perception mask / sensor package per avatar, capability card, resolved settings)
   - Config files: `scenario`, `persona`, `body`, `map` (zones with environment values, ART_DIRECTION §5), `preset`
   - Shared rules: unknown fields rejected; ticks are non-negative integers; `validity` enums (`OBSERVED`, `DEGRADED`, `OCCLUDED`, `MISSING`, `EXPIRED`, `UNKNOWN_SOURCE`); read labels (`COMMIT`, `LEAN`, `HELD_OPEN`, `UNKNOWN`); scopes (`PUBLIC`, `GROUP`, `ONE_TO_ONE`, `SEALED`); evaluator-only fields cannot appear in agent-facing messages.
4. **Headless test world** (`range_service/testworld/`): 2D plane in meters; walls that block sight; avatars with position and heading; field of view, range and line of sight; a fixed tick; a seeded RNG; an event journal in JSONL. Only what the G0 tests need. COMMS channels and the full observer filter arrive in G2.
5. **ΔP module** (`range_service/horizon/delta.py`): the D-11 formula, returning `null` with a reason for missing or unsupported inputs; the optional `S`/`Q` summary.
6. **Config validator** (`tools/validate_configs.py`) plus one example each of map, persona, body, scenario and preset (Sandbox Flats, Robot R, Visitor Y, SB-04).
7. **One check command** (`tools/check.py`): runs schema checks, config validation and tests. CI runs it on Python 3.12 and 3.13 for every push and PR.
8. **Docs:** `docs/BUILD_AND_RUN.md` (exact commands), `CHANGELOG.md`, and the `Commands` and `Status` sections of `CLAUDE.md` filled in.

## Acceptance tests

| Test | Proves |
|---|---|
| Every contract's valid examples pass and invalid examples fail | Contracts are strict (unknown fields, bad enums, negative ticks, missing required fields) |
| Agent-facing schemas reject evaluator-only fields | No route for private goals or scenario labels into an observation (Assessment P0-01) |
| ΔP: missing input → `null` with reason, never 0; clipping; scale floor; categorical events untouched | D-11, Addendum §13 |
| `S`/`Q`: adding an inactive channel changes coverage `Q`, not salience `S` | Addendum §13 check 2 |
| Avatar behind a wall is not observed; one in view is | Line of sight works (Assessment first-session test) |
| Robot rotating while a stationary avatar is in view: world position stays fixed | Atlas L0 test (SB-01, simplified) |
| Same seed + same scripted inputs → identical journal hash; different seed → differs | Reproducibility (Blueprint T28 groundwork) |
| Example configs validate; a broken config fails with a clear message | Content files are safe to edit |
| `tools/check.py` passes locally and in CI | One command, green |

## Out of scope for G0

Godot, any LLM or model engine, COMMS channels and disclosure gate (G2), HORIZON layers beyond ΔP (G5), UI, Windows packaging.

## Definition of done

All acceptance tests pass in CI; `BUILD_AND_RUN.md` commands reproduce it; the report lists what works, commands run with results, and anything deferred; a draft PR is opened for owner review.
