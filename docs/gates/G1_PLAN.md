# G1 — Sandbox Flats in Godot

**Status:** BUILT, IN REVIEW (draft PR) · built and tested in a cloud session with Godot's headless mode; the owner checks the visuals on the Windows PC ([checklist](G1_OWNER_CHECKLIST.md))
**Scope:** [RANGE_V0_SCOPE.md](../RANGE_V0_SCOPE.md) §2.1 (Sandbox Flats), §3 (SB-05), §4 (G1 row) · [ART_DIRECTION.md](../ART_DIRECTION.md) §2, §3, §4, §7 (V0 greybox) · Blueprint §5.2, §5.3, §6.1, §7.1, §20 (G1) · [DECISIONS.md](../DECISIONS.md) D-04, D-06, D-22, D-26, D-27, D-29

## Goal

The first thing you can see and move around in: Sandbox Flats as a flat-colored Godot world, built from `configs/maps/sandbox_flats.yaml`, with Robot R and three visitors walking to goals on a fixed 60 Hz tick, colliding with walls and each other, and the wheeled robot taking the ramp, never the stairs.

The Blueprint's G1 asks for a primitive Expo Hall A. RANGE_V0_SCOPE §4 moves the Expo to G6 and builds Sandbox Flats first; this plan follows the scope document.

## Deliverables

1. **Godot 4.7.2 project** in `godot_app/` (standard build, GDScript only, Forward+ renderer, Jolt physics, 60 Hz physics, frame rate capped at 60).
2. **Data path from YAML to Godot.** `tools/export_godot_data.py` validates the map and body configs against their contracts and writes JSON copies to `godot_app/data/`. The JSON is committed, so the project opens without running Python first; `tools/check.py` fails if the copies are out of date. Godot reads only these files.
3. **Map builder** that creates, from the map data:
   - floor (30 × 20 m), four outer walls, two movable partitions (`partition_a`, `partition_b`);
   - the raised platform (0.6 m) with a **ramp** and a **stair** placed by the map's `nav_links`;
   - the **acoustically reflective west wall**, visibly marked (a striped panel and a label);
   - the **PA speaker** and the **three chairs**;
   - zones as `Area3D` volumes carrying their environment values (light, visual range, noise floor), and spawn-point markers.
4. **Navigation** baked at startup from the built geometry, with the stairs and ramp as `NavigationLink3D`s on capability layers: a body's `can_use_ramp` / `can_use_stairs` flags decide which links its path may use.
5. **Physical capability check.** The stairs carry a smooth walking surface only for bodies with `can_use_stairs`; everyone else meets the real 0.15 m steps and is stopped by them. Navigation never relies on this, but the host blocks a wheeled body even if something tries to drive it up the stairs directly.
6. **Robot R** assembled from primitives in the proportions of the [low-poly concept](../concept-art/robot_avatar_lowpoly_concept.jpg): white shell panels, dark joints and neck band, black visor, ear pods, articulated arms, on a **wheeled base** (its body config is `WHEELED_ROBOT`, 1.4 m tall, radius 0.35 m). Matte identity trim and an `R` number badge per ART_DIRECTION §2.1. No Beacon output yet (visor and ear-pod light stay unlit).
7. **Three capsule visitors** (`visitor_x`, `visitor_y`, `visitor_z`) using the `human_walker` body, each with a visible head direction marker and a name label. Neutral colors that do not encode role or intent.
8. **Avatars** as `CharacterBody3D` with `NavigationAgent3D`, limited by their body config (max speed, acceleration, turn rate, radius, height). Movement runs only in the physics step.
9. **Fixed tick:** a simulation clock counts physics ticks at exactly 60 Hz. Headless runs use `--fixed-fps 60`, so one rendered frame = one tick and runs are not tied to wall-clock time.
10. **Scripted walk-to-goal demo:** each avatar follows a short list of goals (the robot goes up the ramp to the platform and back; one visitor uses the stairs; the others walk around the partitions and to the chairs). This is a G1 demo only; the real scripted policy arrives at G3.
11. **Camera:** free fly (WASD, Q/E down/up, right mouse to look, Shift faster) and orbit follow of the selected avatar (right mouse to orbit, wheel to zoom); `C` switches mode, `[` / `]` select the previous/next avatar (Blueprint §7.4). A small help and status label shows the tick, camera mode and selected avatar.
12. **Headless Godot tests** (`godot_app/tests/`) run by `tools/godot_check.py` (import project, run tests, fail on any script error), included in `tools/check.py` and CI.
13. **Screenshots** of the scene rendered in the cloud (software OpenGL under a virtual display) as proof that it draws, kept in `docs/gates/G1_screenshots/`.
14. **Python version alignment** with the owner's PC (`.python-version` and CI matrix).
15. **Docs:** decisions for the new choices, `BUILD_AND_RUN.md` (Godot commands), `OWNER_SETUP_WINDOWS.md` (Godot path), `CHANGELOG.md`, `CLAUDE.md` status, and an owner checklist for opening the project on Windows.

## Acceptance tests

All automated, in Godot headless mode unless marked Python.

| Test | Proves |
|---|---|
| Exported JSON matches the YAML (Python) | Godot sees exactly the validated configs |
| Map builds: 4 walls + 2 partitions, platform, 1 ramp, 1 stair, PA speaker, 3 chairs, 3 zones, 4 spawn points; west wall flagged reflective | The world is built from the map file, nothing hard-coded |
| Physics runs at 60 ticks/s and the clock counts every tick | Fixed 60 Hz tick |
| No avatar ever moves faster than its body's max speed in any tick | Body limits enforced |
| Each visitor reaches its goal within a time limit | Navigation and walk-to-goal |
| An avatar driven straight into a partition stops at it; two avatars driven into each other never overlap | Collision (walls and bodies) |
| **SB-05:** from a start next to the stairs, the walker's path uses the stairs, Robot R's path uses the ramp; Robot R reaches the platform top and its trace never enters the stair footprint | Wheeled body takes the ramp, not the stairs, because of its capability flags |
| A body with neither stairs nor ramp capability gets no path onto the platform | Gating comes from capabilities, not distance |
| Robot R driven directly at the stairs (no navigation) stays on the floor | The host enforces the capability physically too |
| Robot R's assembled model is ~1.4 m tall and has head, visor, ear pods, arms and wheeled base | Robot built in concept proportions from body config |
| Orbit camera follows the selected avatar; free camera moves with input; avatar selection cycles | Basic camera works |
| The full demo runs for 30 s of simulated time with no script errors | Smoke test |
| `tools/check.py` passes locally and in CI (Python 3.12, 3.13, 3.14) | One command, green |

## Out of scope for G1

Python connection, WebSocket transport and the event journal from Godot (G2); observer filter and COMMS (G2); any model or agent policy (G3); Director, Participant, agent POV camera and HUD panels (G4); HORIZON layers (G5); Expo Hall A, props catalog and V1 art (G6); Beacon rendering; local avoidance between avatars (paths are authored not to cross head-on).

## Risks

- **Cloud vs PC rendering:** the cloud has no GPU, so screenshots use Godot's Compatibility renderer; on the PC the project uses Forward+. Colors and shading may differ slightly. The owner checks the real look.
- **Navmesh baking differences between machines** are possible in principle; tests check routes and outcomes (which link, reached or not), not exact path coordinates.

## Definition of done

All acceptance tests pass locally and in CI; screenshots committed; new decisions recorded as PROPOSED; report lists what works, commands run with results, and what the owner should check on the Windows PC; a draft PR is opened for owner review.
