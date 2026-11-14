# G1b — Robot body family (between G1 and G2)

**Status:** BUILT, IN REVIEW (draft PR)
**Scope:** owner request of 2026-11-14 · [DECISIONS.md](../DECISIONS.md) D-36 (approved), D-37 and D-38 (proposed) · RANGE_V0_SCOPE §2.2, §3 (SB-05), §6.1 · ART_DIRECTION §2

## Goal

Three robot bodies instead of one, so that "Robot R" can be played by a legged humanoid, a wheeled humanoid or a quadruped, each with honest size, movement, sensor and gesture limits that the world enforces. Plus: fix the six GDScript warnings seen on the owner's PC and make new warnings fail the checks.

## What was built

| Area | Result |
|---|---|
| Body configs | `legged_humanoid`, `wheeled_humanoid` (was `robot_r`), `quadruped`, `quadruped_arm`, `human_walker`, all on body contract 2.0 (D-37). Values in D-36. |
| Rules | `range_service/bodies.py` (Python) and `godot_app/scripts/core/bodies.gd` (Godot): turning and navigation radius, gesture and channel permissions. The config validator rejects contradictions (for example a waving quadruped with no arm). |
| Avatars | Greybox models from primitives: legged and wheeled humanoids share one upper body; the quadruped has a sensor-visor head, dorsal rail and four legs, and the arm variant a stowed arm. Number badge, matte trim and 1–3 bands per robot. A `SensorMount` marker at each body's sensor height. |
| World | Per-size navigation (one navigation map per body size); bevelled colliders for legged box bodies so the quadruped can climb the stairs; the host refuses gestures a body cannot perform. |
| SB-05 | `configs/scenarios/SB05_RAMP_VS_STAIRS.yaml` casts Robot R in all three bodies. Tests: the wheeled humanoid takes the ramp; the legged humanoid, both quadrupeds and a walker take the stairs. |
| Demo | The three robot families start beside the stairs and go up onto the platform (wheeled by the ramp, the others by the stairs), with three visitors walking elsewhere. |
| Lineup scene | `godot_app/scenes/robot_lineup.tscn`: all four robot bodies and a visitor side by side. |
| Warnings | Six warnings fixed; every default-on warning is an error; a compile step loads every script (D-38). |
| Tick | D-33 resolved: Godot's 60 Hz tick is the canonical `tick_id`; a scenario's `tick_hz` must divide 60 (checked). |
| Docs | Later embodiments in RANGE_V0_SCOPE §6.1; ART_DIRECTION §2; contracts README. |

## Tests added

Python (`tests/test_bodies.py` and others): the robot families exist; stairs/ramp capabilities; turning and navigation radii; plausible dimensions and sensor heights; gesture permissions per body; expression channels; the arm variant differs only by the arm; each contradiction rule; `tick_hz` must divide 60; SB-05 casts one Robot R per family; body contract 2.0 examples (2 valid, 14 invalid); one gesture vocabulary shared by three contracts.

Godot (`godot_app/tests/test_main.gd`, 19 tests): body dimensions, colliders, sensor mounts and navigation radii; each robot model's parts, height, footprint, visor height and badge; gesture permissions in the world; per-size navigation (a walker reaches a pocket a quadruped cannot); SB-05 path choice for all five bodies; the wheeled humanoid drives the ramp; the stair climbers physically climb; the wheeled humanoid is stopped by the steps while the quadruped climbs them; the lineup scene; the full demo with no contacts; warning levels in `project.godot`.

## Screenshots

In [G1b_screenshots/](G1b_screenshots/), rendered in the cloud without a GPU (Compatibility renderer):
`bodies_lineup.png`, `body_legged_humanoid.png`, `body_wheeled_humanoid.png`, `body_quadruped.png`, `body_quadruped_arm.png`, `sb05_ramp_and_stairs.png`, `sb05_all_on_platform.png`, `demo_overview.png`, `reflective_wall_pa_chairs.png`.

## Owner checklist (Windows PC)

About 15 minutes. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot`; `GODOT_BIN` is already set from G1.

1. **Get the branch.** GitHub Desktop → **Fetch origin** → **Current branch** → `claude/trusting-mccarthy-9zeq6j`.
2. **Run the checks.** In PowerShell:
   ```powershell
   cd G:\SOMA_CODEC
   ```
   ```powershell
   uv run python tools/check.py
   ```
   Expect five **PASS** lines, `22 GDScript files compiled with no errors or warnings`, and 19 Godot tests.
3. **Open Godot** (`G:\Godot\Godot_v4.7.2-stable_win64.exe`) and the SOMA RANGE project. The editor's **Debugger → Errors** tab should now show **no** GDScript warnings.
4. **Look at the robots side by side.** In the FileSystem panel, open `scenes/robot_lineup.tscn` and press **F6** (Run Current Scene). Press `C` to orbit the selected robot, `]` / `[` to switch, wheel to zoom.
   - [ ] Legged humanoid, wheeled humanoid and quadruped each look like their concept sheet in `docs/concept-art/`.
   - [ ] The quadruped with the arm: the arm folded flat on its back, gripper over the visor.
   - [ ] Sizes look right next to the visitor (1.70 m).
   - [ ] Each robot has its number badge and trim stripes (1, 2, 3 or 4).
5. **Watch the demo.** Press **F5**. In about 20 seconds:
   - [ ] the quadruped (3) and the legged humanoid (1) go **up the stairs**;
   - [ ] the wheeled humanoid (2) drives round to the **ramp**, never the stairs;
   - [ ] nobody walks through anything or anyone.
   Select a robot with `]` and read the panel: its stairs/ramp capability, sensor height and the gestures it can do.
6. **Note FPS and video memory** (Debugger → Monitors), as you did for G1, and any red lines in the Output panel.
7. **Tell me** what to change (looks, sizes, which gestures each robot can do), and your answers on D-37 and D-38.
