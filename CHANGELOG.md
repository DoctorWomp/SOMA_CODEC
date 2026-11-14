# Changelog

All notable changes, by gate. Dates are when the work was done.

## G1 — Sandbox Flats in Godot (2026-11-14, in review)

### Added
- **Godot 4.7.2 project** in `godot_app/` (GDScript, Forward+, Jolt physics, fixed 60 Hz tick, frame rate capped at 60).
- **Sandbox Flats built from `configs/maps/sandbox_flats.yaml`**: floor with a 5 m grid, outer walls, two movable partitions, the 0.6 m platform with a ramp and a 4-step stair placed by the map's nav links, the acoustically reflective west wall (striped and labelled), PA speaker, three chairs, zone volumes carrying their environment values (floor darkened by light level), spawn markers.
- **Capability-gated navigation (D-31):** baked navigation mesh plus ramp/stairs links on capability layers; bodies without `can_use_stairs` are also physically stopped by the steps.
- **Robot R** assembled from primitives in the concept's proportions on a wheeled base, with green identity trim and an `R` badge (D-32); **three capsule visitors** with head-direction markers.
- **Avatars** (`CharacterBody3D` + `NavigationAgent3D`) limited by their body config's speed, acceleration and turn rate; a 60 Hz world clock; stuck detection.
- **Walk-to-goal demo** (about 40 s): Robot R up the ramp and back, visitor_y up the stairs, two visitors around the partitions and to the chairs.
- **Camera:** free fly and orbit-follow with avatar selection; a small status and help panel; pause, restart, hide.
- **15 headless Godot tests** (`godot_app/tests/`), including SB-05 ramp-vs-stairs routing, physical stair blocking, wall and body collision, speed and turn limits, the robot model, the camera and a full demo run.
- `tools/export_godot_data.py` (configs → validated JSON for Godot, D-30), `tools/godot_check.py` (headless import and tests), `tools/install_godot.py` (pinned, SHA-512-verified Godot download).
- `tools/check.py` now has five steps (adds Godot data and Godot); a missing Godot shows as SKIP, `--require-godot` makes it a failure (D-34).
- CI installs and caches Godot 4.7.2 and runs every check on Python 3.12, 3.13 and 3.14.
- `.python-version` set to 3.14 (D-35).
- Screenshots in `docs/gates/G1_screenshots/`; plan in `docs/gates/G1_PLAN.md`; owner checklist in `docs/gates/G1_OWNER_CHECKLIST.md`.
- Decisions D-30 to D-35 (PROPOSED). D-06 annotated (Godot patch re-checked; Python 3.14).

### Changed
- G0 marked complete; decision D-29 approved by the owner.
- `docs/BUILD_AND_RUN.md`, `docs/OWNER_SETUP_WINDOWS.md` and `godot_app/README.md` cover Godot.

## G0 — Repository, contracts and headless test world (2026-11-13, complete: merged 2026-11-14)

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
- `docs/BUILD_AND_RUN.md`, `contracts/README.md`, decision D-29 (approved by the owner on 2026-11-14).
