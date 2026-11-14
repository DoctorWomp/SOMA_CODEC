# Changelog

All notable changes, by gate. Dates are when the work was done.

## G2a — Senses, journal, avoidance (2026-11-14, in review)

First half of G2 (plan: `docs/gates/G2_PLAN.md`; G2b adds channels, the disclosure gate and the WebSocket link).

### Added
- **Observer filter** in Godot (`scripts/senses/`, D-39): sight lines from each body's sensor mount to the head, torso, both sides and the gesturing hand of every other avatar; walls, props, steps and other avatars block sight. Fully seen → `OBSERVED`; partly → `DEGRADED` / `PARTLY_OCCLUDED` with the visible parts; recently seen but hidden → `OCCLUDED` / `MISSING` at the last known spot with no quality; never seen → absent.
- **Hearing** (D-40): local speech level falls with distance, walls take some off, the zone noise floor masks it; heard without sight as `UNKNOWN_SOURCE` with a direction only; delivered once, never backfilled.
- **Gestures and speech as world events:** `Avatar.perform_gesture()` (refused if the body cannot, D-36) and `Avatar.say()`; perceived only by those who could see or hear them.
- **Observation packets** in the observation contract, sampled at `tick_hz` (10 Hz) on the 60 Hz tick (D-33), with anonymous per-observer tracks.
- **Event journal** written by Godot (D-41) to `user://journals/`, deterministic (same seed, same bytes); `tools/godot_check.py` validates every journal line and packet the tests write against the contracts in Python.
- **Shared local avoidance** across the per-size navigation maps (D-42).
- **Low divider** (1.1 m) in Sandbox Flats: the quadruped cannot see over it, humanoids can.
- **F2 sense view**: lines and labels for what the selected avatar perceives; the info panel lists what it sees and hears.
- Demo: robots greet each other on the platform; the quadruped's attempted wave is refused and journaled.
- Contract additions (backward-compatible): observation `validity_reason`, `visible_parts`; journal kinds `GESTURE_PERFORMED`, `GESTURE_REFUSED`, `SPEECH_EMITTED`; `sample_hz` in `RUN_STARTED`.
- Godot tests 19 → 30; Python tests 399 → 410.
- Decisions D-39 to D-42 (proposed).

### Changed
- Owner approved D-37 and D-38.

## G1b — Robot body family (2026-11-14, complete: merged 2026-11-14)

### Added
- **Three robot bodies** (D-36): `legged_humanoid`, `wheeled_humanoid`, `quadruped`, plus the `quadruped_arm` variant, each with realistic starting values for size, collider, speed and turn limits, stairs/ramp capability, sensor mount height and field of view, reach, arms, gestures and expression channels. "Robot R" is a role; a scenario picks its body.
- **Body contract 2.0** (D-37): collider footprint, sensor mount height, arms, gestures, expression channels; robot kinds renamed. One shared gesture vocabulary in `contracts/common.schema.json` (adds `HEAD_TILT`, `SIT_IN_PLACE`, `HAND_OVER`) and expression channels (`SPEECH`, `FACE`, `LIGHT`).
- `range_service/bodies.py` and `godot_app/scripts/core/bodies.gd`: turning/navigation radius and gesture/channel permissions; the config validator reports contradictions.
- Greybox models: legged and wheeled humanoids (shared upper body; legs or a four-wheeled base with lift column) and the quadruped (sensor-visor head, dorsal rail, four legs, optional stowed arm). Number badges, matte trim and 1–3 stripes.
- **Per-size navigation** (D-37): one navigation map per body size; a single mesh for the quadruped would have removed 14% of people's walkable floor.
- Bevelled colliders for legged box bodies, so the quadruped climbs the stairs while the wheeled base is still stopped by the steps.
- `configs/scenarios/SB05_RAMP_VS_STAIRS.yaml` (Robot R in all three bodies) and three SB-05 spawn points in Sandbox Flats.
- Demo with all three robot families going up to the platform; `scenes/robot_lineup.tscn` showing every robot body side by side.
- Godot tests 15 → 19 (and several rewritten for every body); Python tests 356 → 399.
- A compile step in `tools/godot_check.py` that loads every GDScript file (D-38).
- Decisions D-36 (approved), D-37 and D-38 (proposed); later embodiments in RANGE_V0_SCOPE §6.1.

### Changed
- Owner approved D-30, D-31, D-33 (tick resolved: Godot's 60 Hz tick is canonical; `tick_hz` must divide 60, now checked), D-34 and D-35. D-32 superseded by D-36.
- `robot_r` body renamed `wheeled_humanoid` (persona `robot_r` and SB-04 point at it).

### Fixed
- Six GDScript warnings seen in the owner's editor (integer division; `tr`, `owner`, `basis` shadowing). Every default-on GDScript warning is now an error (D-38).

## G1 — Sandbox Flats in Godot (2026-11-14, complete: merged 2026-11-14)

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
