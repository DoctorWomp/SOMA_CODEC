# godot_app/

The Godot 4.7.2 project (D-06): the world authority for SOMA RANGE (D-04). Open `project.godot` in Godot and press F5 to run Sandbox Flats. Commands are in [docs/BUILD_AND_RUN.md](../docs/BUILD_AND_RUN.md).

| Folder | Contents |
|---|---|
| `scenes/` | `main.tscn`, the entry scene. It builds everything from data when it runs. |
| `scripts/core/` | Data loading (`world_data.gd`), the 60 Hz clock, physics/navigation layers, palette, mesh helpers |
| `scripts/world/` | `map_builder.gd` (walls, platform, ramp, stairs, props, zones, spawns from the map file) and `range_world.gd` (navigation, avatars, path queries) |
| `scripts/avatars/` | `avatar.gd` (body limits, collider, navigation), `robot_r_model.gd`, `visitor_model.gd` |
| `scripts/demo/` | The G1 walk-to-goal demo routes (replaced by the scripted policy at G3) |
| `scripts/ui/` | Free / orbit camera and the small status panel |
| `data/` | **Generated** JSON copies of `configs/maps/` and `configs/bodies/` (D-30). Do not edit; run `uv run python tools/export_godot_data.py` |
| `tests/` | Headless tests, run by `tools/godot_check.py` (part of `tools/check.py`) |
| `dev/` | Screenshot capture scene |

Rules this project keeps: the host owns physics, collision and navigation; capabilities in the body config decide which ramps and stairs a body may use (D-31); avatars move only in the fixed physics tick (D-33). No Python connection and no models yet (G2–G3).

Commit the `*.uid` files next to scripts; Godot uses them to keep references stable. The `.godot/` cache folder is ignored.
