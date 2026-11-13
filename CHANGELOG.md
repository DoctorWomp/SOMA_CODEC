# Changelog

All notable changes, by gate. Dates are when the work was done.

## G0 — Repository, contracts and headless test world (2026-11-13, in review)

### Added
- Python project (`pyproject.toml`, `uv.lock`) for Python 3.12+, with only `jsonschema`, `pyyaml` and `pytest`.
- Folder layout per D-15: `range_service/` (`horizon/`, `sensors/`, `agents/`, `comms/`, `eval/`, `testworld/`), `contracts/`, `configs/`, `tests/`, `tools/`, `models/`, `godot_app/`.
- **Contracts v1** (`contracts/`, schema version `1.0`): `envelope`, `observation`, `delta_feature`, `hypothesis`, `action_request`, `action_result`, `comms_event`, `intervention`, `memory_item`, `run_manifest`, `map`, `persona`, `body`, `scenario`, `preset`, plus `common` and `journal_entry`. 30 valid and 115 invalid examples.
- Evaluator-only leak guard: agent-facing contracts reject every evaluator-only field name at every level.
- ΔP module (`range_service/horizon/delta.py`): D-11 formula, `null` with a reason for missing/unsupported input, clipping, scale floor, categorical pass-through, robust scale, optional `S`/`Q` summary.
- Headless 2D test world (`range_service/testworld/`): walls, field of view, range, line of sight, fixed tick, seeded RNG, JSONL journal with SHA-256 hash.
- Example configs: Sandbox Flats map; Robot R and human walker bodies; Robot R, Visitor X and Visitor Y personas; preset H0; scenario SB-04 Polite bid.
- `tools/validate_configs.py` (schema, duplicate keys, file names, cross-references) and `tools/check.py` (one command for everything).
- CI workflow running `tools/check.py` on Python 3.12 and 3.13.
- `docs/BUILD_AND_RUN.md`, `contracts/README.md`, decision D-29 (PROPOSED).
