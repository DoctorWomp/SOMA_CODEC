# godot_app/

The Godot 4.7.2 project (D-06): the world authority for SOMA RANGE (D-04). Open `project.godot` in Godot and press F5 to run Sandbox Flats. Commands are in [docs/BUILD_AND_RUN.md](../docs/BUILD_AND_RUN.md).

| Folder | Contents |
|---|---|
| `scenes/` | `main.tscn`, the entry scene (F5); `robot_lineup.tscn`, every robot body side by side (F6). Both build everything from data when they run. |
| `scripts/core/` | Data loading (`world_data.gd`), body rules (`bodies.gd`), the 60 Hz clock, physics/navigation layers, palette, lighting, mesh helpers |
| `scripts/world/` | `map_builder.gd` (walls, platform, ramp, stairs, props, zones, spawns from the map file) and `range_world.gd` (per-size navigation, avatars, path queries) |
| `scripts/avatars/` | `avatar.gd` (body limits, collider, navigation, gesture checks), `humanoid_model.gd` (legged and wheeled), `quadruped_model.gd` (with or without arm), `visitor_model.gd`, `robot_parts.gd` |
| `scripts/senses/` | The observer filter: `sense_model.gd` (sight lines, hearing) and `observer_filter.gd` (observation packets, anonymous tracks) (D-39, D-40) |
| `scripts/sim/` | `journal.gd`, the event journal (D-41) |
| `scripts/demo/` | The G1 walk-to-goal demo routes (replaced by the scripted policy at G3) |
| `scripts/ui/` | Free / orbit camera, the status panel and the F2 sense view |
| `data/` | **Generated** JSON copies of `configs/maps/` and `configs/bodies/` (D-30). Do not edit; run `uv run python tools/export_godot_data.py` |
| `tests/` | Headless tests and the compile-everything script, run by `tools/godot_check.py` (part of `tools/check.py`) |
| `dev/` | Screenshot capture scene and its staged senses scene |

Rules this project keeps: the host owns physics, collision and navigation; capabilities in the body config decide which ramps and stairs a body may use (D-31) and which gestures it may perform (D-36); avatars move only in the fixed physics tick (D-33); GDScript warnings are errors (D-38). No Python connection and no models yet (G2–G3).

Commit the `*.uid` files next to scripts; Godot uses them to keep references stable. The `.godot/` cache folder is ignored.
