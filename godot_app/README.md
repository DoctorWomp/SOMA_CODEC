# godot_app/

The Godot 4.7.2 project (D-06): the world authority for SOMA RANGE (D-04). Open `project.godot` in Godot and press F5 to run Sandbox Flats. Commands are in [docs/BUILD_AND_RUN.md](../docs/BUILD_AND_RUN.md).

| Folder | Contents |
|---|---|
| `scenes/` | `main.tscn`, the entry scene (F5; with `-- --scenario=<id>` it runs a scenario instead of the demo, D-48); `robot_lineup.tscn`, every robot body side by side (F6). Both build everything from data when they run. |
| `scripts/core/` | Data loading (`world_data.gd`), body rules (`bodies.gd`), expression rules (`beacon_rules.gd`), the 60 Hz clock, physics/navigation layers, palette, lighting, mesh helpers |
| `scripts/world/` | `map_builder.gd` (walls, platform, ramp, stairs, props, zones, spawns from the map file; the Director's prop sizes), `range_world.gd` (per-size navigation, avatars, path queries) and `world_editor.gd` (the World Director: place, move and remove props with the placement rules, every size's navigation rebaked and tested on scratch maps; D-99) |
| `scripts/avatars/` | `avatar.gd` (body limits, collider, navigation, gesture and expression checks, gaze target), `humanoid_model.gd` (legged and wheeled), `quadruped_model.gd` (with or without arm), `beacon.gd` (visor or light-strip glyph and light, D-52), `visitor_model.gd`, `robot_parts.gd` |
| `scripts/rig/` | Skeletons and poses (D-54, D-56): `rig_spec.gd` (joint axes and limits per family, the body's `rig` block, gesture duration from tempo), `rig.gd` (the `Skeleton3D`, parts on bones, clamped joint angles), `poser.gd` (wheels, posture, gestures with IK, gaze). Presentation only: a world's `PoseStep` poses every robot after movement; `-- --no-pose` turns it off and the journal stays the same |
| `scripts/senses/` | The observer filter: `sense_model.gd` (sight lines, hearing) and `observer_filter.gd` (observation packets, anonymous tracks) (D-39, D-40) |
| `scripts/comms/` | `world_dispatcher.gd` (every request's principal checked against `data/permissions/`; D-90, D-91), `director.gd` (G4b: every Director intervention, checked by the dispatcher, carried out world-side or sent to the sidecar, journaled; recipes scheduled; D-97), `comms_router.gd` (the four channels, groups, PA; D-43), `action_gate.gd` (checks every agent request; D-44), `link_client.gd` (the WebSocket link to the Python sidecar) |
| `scripts/sim/` | `journal.gd`, the event journal (D-41) |
| `scripts/scenario/` | `scenario_player.gd`: spawns a scenario's cast and plays its event tape through the action gate (D-48) |
| `scripts/demo/` | The G1 walk-to-goal demo routes (replaced by the scripted policy at G3) |
| `scripts/ui/` | Spectator cameras (free, orbit, follow, POV; T06), the status panel, the F2 Sensor view (from packets only; D-95) and the F6 Director console `director_panel.gd` (Director seat only; D-97) |
| `scripts/ui/viewer/` | The layer viewer v1 (F3; D-94): `viewer_store.gd` (reads the run's viewer feed, live or replay, through the dispatcher's audience check), `layer_viewer.gd` (2D lanes, timeline, decision pins, capability card), `decision_text.gd` (why a decision was made, from evidence), `evaluator_panel.gd` (EVALUATOR TRUTH, Evaluator seat only, F4) |
| `data/` | **Generated** JSON copies of `configs/maps/`, `configs/bodies/`, `configs/expressions/`, `configs/permissions.yaml` and a world-only view of `configs/scenarios/` and `configs/recipes/` (D-30, D-48, D-90, D-102). Do not edit; run `uv run python tools/export_godot_data.py` |
| `tests/` | Headless tests and the compile-everything script, run by `tools/godot_check.py` (part of `tools/check.py`); `tests/fixtures/viewer_sb04/` is a small viewer feed for the layer viewer tests (checked against its contract in `tests/test_viewer_feed.py`) |
| `dev/` | Screenshot capture scenes (`capture.tscn`, `beacon_capture.tscn`, `gesture_capture.tscn`) and the staged senses scene |

Rules this project keeps: the host owns physics, collision and navigation; capabilities in the body config decide which ramps and stairs a body may use (D-31) and which gestures it may perform (D-36); avatars move only in the fixed physics tick (D-33); GDScript warnings are errors (D-38); navigation and avoidance run on the main thread so runs are repeatable (D-47); a stepped run holds the world between ticks without changing it (D-48). Agents and models live in the Python sidecar, never in Godot (D-21).

Commit the `*.uid` files next to scripts; Godot uses them to keep references stable. The `.godot/` cache folder is ignored.
