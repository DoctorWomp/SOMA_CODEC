# Rig plan — skeletons, animation and body language

**Status:** APPROVED (D-54, 2026-11-16). **Step A built** (2026-11-16, D-56 PROPOSED, in review; [owner checklist](RIG_A_OWNER_CHECKLIST.md), [screenshots](RIG_A_screenshots/)); steps B–D not started · Amends [ART_DIRECTION.md](../ART_DIRECTION.md) §6 (skeleton row, done)
**Related:** [EXPRESSION_PRINCIPLES.md](../EXPRESSION_PRINCIPLES.md) · D-14 (lights), D-33 (movement and the 60 Hz tick), D-36 (body family), D-39 (sight), D-47 (determinism), D-52 (expression catalog) · Avatar Foundry §5 (fidelity P0–P2) · Blueprint §1 (release scope: "dynamic ragdolls" not required)

## Goal

Give every robot body a skeleton so gestures, gaze and posture read as body language, and so legged bodies visibly walk up the stairs instead of gliding. The world stays exactly as it is underneath: the same colliders, movement, journal and senses.

## The rule: two layers

| Layer | What it is | Owner | Deterministic? |
|---|---|---|---|
| **Body** | Collider, movement, navigation, the gesture *event* and its duration, sense points, the 60 Hz tick | The world (unchanged) | Yes, tested |
| **Pose** | Skeleton, joint angles, feet on steps, arm and head motion, wheel spin | Presentation, driven by the body | Yes (same tick, same pose), but nothing depends on it |

- Animation **never** moves the collider, writes to the journal or decides what anyone perceives.
- Sight keeps its sense points computed from the body config and the gesture (`scripts/senses/sense_model.gd`). The rig's job is to put the visible hand where the sense model says it is, and a test checks that it does.
- Poses are evaluated on the physics tick from world state at that tick. Headless runs and tests can switch posing off. **A journal is byte-identical with posing on or off** (test).
- The model never moves joints. It picks a gesture or an expression from the catalog with bounded parameters, and the body performs it (ART_DIRECTION §6).

## Why not stair-climb clips, and why not ragdoll

| | Recorded clips per situation | **Code-driven gait + IK (chosen)** | Full or active ragdoll |
|---|---|---|---|
| CPU per avatar | Lowest | Low: a few IK solves and 2–4 short downward rays per tick | High: ~15 rigid bodies and joints each |
| GPU | Same for all three: skinning cost depends on triangles and draw calls, not on where a pose comes from | | |
| Authoring | A clip per body × stair height × direction, plus transitions | One gait per skeleton family, tuned by numbers | Physics tuning |
| A map changes (maps are YAML) | Feet float or sink | Adapts | Adapts |
| Same result every run | Yes | Yes | Fragile |

Ragdoll as simulation is out: it would put body physics in charge (against D-04, "the host owns physics") and break determinism (D-47). Two narrow uses may come later (step D): cosmetic springs, and a ragdoll replay of a logged incident (for example a visitor tripping), where the contact still comes from the colliders and the ragdoll only draws it.

## Godot tools (checked present in 4.7.2)

`Skeleton3D`, `AnimationPlayer` / `AnimationTree` (blend spaces, one-shots, bone filters), `SkeletonModifier3D` and its subclasses: `TwoBoneIK3D`, `CCDIK3D`, `FABRIK3D`, `LookAtModifier3D`, `AimModifier3D`, `CopyTransformModifier3D`, `LimitAngularVelocityModifier3D`, `SpringBoneSimulator3D`, `PhysicalBoneSimulator3D`, `BoneAttachment3D`, `RetargetModifier3D`. All are built in and need no plugin. Their exact behavior is verified as each is used.

## Skeletons

Three families instead of ART_DIRECTION §6's "one shared humanoid skeleton for robots and humans", which cannot fit a quadruped:

| Family | Used by | Bones (approx.) |
|---|---|---|
| **Humanoid** | legged humanoid, wheeled humanoid (upper body), human visitors (step C) | ~24 |
| **Quadruped** | quadruped, quadruped with arm | ~18 |
| **Arm module** | quadruped_arm (dorsal mount); reusable on future bodies | 7 |

Joint names keep D-32's `Neck`, `ShoulderL/R`, `ElbowL/R`, `WristL/R`, so a later Blender mesh uses the same names (ART_DIRECTION §6).

### Joint tables (realistic and readable)

The owner's reference sheets (2026-11-16) are the joint maps. They are trimmed to what real hardware has and what reads at our camera distance. **Head yaw is capped at ±85° on every body**: a head that turns right round reads as uncanny, and fitting in with people is HORIZON's purpose.

**Humanoid** (legged; the wheeled one shares everything above the waist)

| Joint | DOF | Limits | Note |
|---|---|---|---|
| Pelvis (root) | — | — | Follows the body; bobs with the gait |
| SpineLower, SpineUpper | 2 × 3 | bend ±30° / ±25°, twist ±45° each | Lean in, step back, bow |
| Neck + Head | 3 | yaw ±85°, pitch −40°…+60°, roll ±30° | Gaze, nod, head tilt |
| ShoulderL/R | 3 | pitch −60°…+180°, yaw ±90°, roll ±90° | |
| ElbowL/R | 1 | 0°…145° | |
| WristL/R | 2 | pitch ±70°, roll ±90° | |
| FingersL/R, ThumbL/R | 1 + 1 | curl 0°…90° | Two groups are enough for wave, point, open palm, hand-over |
| HipL/R | 3 | pitch −30°…+120°, yaw ±45°, roll ±30° | Legged only |
| KneeL/R | 1 | 0°…140° | Legged only |
| AnkleL/R | 2 | pitch ±40°, roll ±20° | Legged only; foot IK |
| ToeL/R | 1 | 0°…40° | Legged only |

The reference sheet's 86 DOF (three segments per finger) is film-level detail that nobody sees at a distance.

**Wheeled humanoid: lower body**

| Joint | DOF | Limits | Note |
|---|---|---|---|
| TorsoMount | 3 | yaw ±90°, pitch ±20°, roll ±10° | Leaning in and backing off is strong body language |
| Wheels (×2 drive, ×2 caster) | spin | free | Spun from the body's actual speed and turn rate |

**The visuals must match the motion model** (D-33: it drives along its facing, with a turning radius). The reference sheet shows omni wheels that strafe; ours do not slide sideways, so the model must not look as if it could.

**Quadruped**

| Joint | DOF | Limits | Note |
|---|---|---|---|
| Body (root) | — | — | Rigid, like current robot dogs. No segmented spine (the sheet's 3 segments are not current hardware) |
| HipAbd ×4 | 1 | ±35° | Hip sideways |
| HipFlex ×4 | 1 | −60°…+120° | |
| Knee ×4 | 1 | −150°…0° | |
| Foot ×4 | — | — | Point feet, no ankle (the sheet's 2-DOF ankle is not current hardware) |
| Body pose (no neck) | 3 | yaw ±15°, pitch ±15°, roll ±15° | **Changed at step A (owner, 2026-11-16; D-56):** no neck, as on current robot dogs; the sensor head is fixed to the body. Gaze and HEAD_TILT are whole-body poses that the legs make over planted feet (asymmetric hip and knee angles), lowering the body slightly when needed. *Was: a 2-axis neck for readable gaze* |

3 DOF per leg is what current robot dogs have, and it also keeps the IK simple.

**Arm module** (quadruped_arm)

| Joint | DOF | Limits |
|---|---|---|
| ArmBase | 1 | yaw ±170° |
| ArmShoulder | 1 | pitch −10°…+150° |
| ArmElbow | 1 | 0°…150° |
| ArmWrist | 3 | pitch ±90°, yaw ±90°, roll ±170° |
| Gripper | 1 | open 0°…60° |

All limits are starting values, to be set in the body configs and adjusted against the reference sheets.

## Animation layers

| # | Layer | Bones | What drives it |
|---|---|---|---|
| 1 | **Locomotion** | Legs or wheels, pelvis bob | Body speed and turn rate. Gait cycle in place, with foot IK onto the ground under each foot. Wheels spin from the speed |
| 2 | **Posture** | Spine or torso mount | Lean in, step back, bow, sit (quadruped `SIT_IN_PLACE`) |
| 3 | **Gesture** | Arms (masked) | One-shot tracks for the gesture vocabulary: WAVE, SMALL_WAVE, RAISED_HAND, POINT, BECKON, OPEN_PALM, HAND_OVER, BOW, NOD, SHAKE_HEAD, HEAD_TILT |
| 4 | **Gaze** | Neck and head | `LookAtModifier3D` toward a gaze target, within the joint limits, turning at the body's head speed |

The Beacon (glyphs and lights, D-52) stays a separate, non-skeletal layer.

### Motion "prosody"

The *how* of a movement carries meaning: **tempo, amplitude, hold time, gaze timing, approach speed, stopping distance, posture height.**

- Gestures and catalog entries gain **optional** `amplitude` and `tempo` parameters (0.5–1.5, default 1). The body config clamps them.
- The **world** computes the gesture event's duration from them, so duration stays world-owned and deterministic. Today it is a fixed 90 ticks (`GESTURE_DURATION_TICKS`).
- The animation fits inside that duration.

This is the motion half of EXPRESSION_PRINCIPLES §3 ("expression is in motion"). Adaptive use (phrases, matching or contrasting someone) stays G5.

### Gaze and posture as observable facts (later)

A gaze target and a facing direction are world state. A later observation may report "head oriented toward me" as an observable fact, with no inference (D-13). That would be computed from world state, never by reading bones, and is not part of this plan.

**G3e (D-72):** for the legged and wheeled humanoids the head's yaw and pitch are now world state (body config `head` block): the sight cone, gesture direction and visor follow it, and the rig's Neck shows the simulated head instead of driving it. Small presence adjustments (D-74) stay presentation on top of it. The quadrupeds keep a fixed sensor head.

## Data and contracts

- A **body config `rig` block** (optional; backward-compatible under D-29's conventions):
  - skeleton family;
  - per-joint limits;
  - gait parameters: step height, step length, cadence;
  - gesture amplitude and tempo ranges;
  - head turn speed.

  `tools/export_godot_data.py` carries it to Godot as it does the rest of the body config.
- `amplitude` and `tempo` become optional fields on `GESTURE` and `EXPRESS` actions and on catalog entries. They are backward-compatible.
- **No new journal kinds.** Pose is not recorded: a replay re-derives it from the same ticks.

## How the meshes change

Today each robot is a tree of primitive mesh parts. Each part becomes **rigidly attached to one bone**, either merged into one skinned mesh per avatar (fewer draw calls, which helps the expo crowd at G6) or parented with `BoneAttachment3D` where merging is awkward. The silhouettes stay the same. A later Blender mesh replaces the primitives on the same skeleton.

## Cost control

- **Levels of detail:**
  - near the camera: full IK and every layer;
  - mid distance: gait cycle without IK;
  - far: no skeleton update.

  Headless runs skip posing.
- Measured with ART_DIRECTION §7's render-tax test, and against T25 (no frame over 50 ms while a model runs).

## Steps

Each step is a draft PR with its own owner checklist. Step A needs no GPU or model, so it can be built in the cloud **while the owner runs G3b** (the real model) on the PC.

| Step | Contents | Tests (headless) |
|---|---|---|
| **A — Skeletons, gestures, gaze** | Skeletons built from body configs for all four robot bodies; parts attached to bones; layers 2–4; wheel spin; `rig` block and `amplitude`/`tempo`; lineup screenshots of every gesture | No joint ever passes its limit; each gesture finishes inside its world duration; the posed hand is within 10 cm of the sense model's HAND point at the gesture's peak; the same tick gives the same pose; the journal is identical with posing on or off; bodies without an arm never move one |
| **B — Gaits and foot IK** | Legged humanoid and quadruped gaits with foot IK; pelvis or body height follows the feet; turning on the spot steps | On stairs and the ramp, each planted foot is within 3 cm of the surface; no foot inside a step; SB-05 still passes for every body; the gait's cadence matches body speed |
| **C — Articulated visitors** | Human visitors on the humanoid skeleton (faceted mannequin, ART_DIRECTION §2); breathing idle; free CC0 clips allowed after a license check recorded in `THIRD_PARTY_LICENSES` | The same as A and B for humans; visitor appearance never encodes intent (ART_DIRECTION §2) |
| **D — Optional, later** | Cosmetic springs (`SpringBoneSimulator3D`); ragdoll replay of a logged incident (presentation only); fidelity P2 contact (hands, bumpers) | Ragdoll and springs never change the journal |

## Out of scope

Full-body ragdoll or actuator simulation; motion capture; facial rigs (robots have visors; human faces stay simple); anything that lets a model move joints directly.
