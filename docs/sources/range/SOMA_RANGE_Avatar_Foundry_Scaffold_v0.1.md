# SOMA RANGE — Avatar Foundry & Embodiment Scaffold v0.1

**Status:** Speculative, engine-neutral prototype design (2026-10-17)  
**Target:** Low-poly Tier 3–4 HORIZON ΔP research simulation  
**Working maxim:** *Same mind, different body; same body, different observations.*

## 1. Purpose and experimental boundary

Build reusable human and robot avatar prefabs that can independently vary **visual identity, mechanical embodiment, movement, articulation, social expression, and agent policy**. The simulator runs physical constraints; an LLM selects high-level actions; SOMA HORIZON ΔP is an optional perception-and-interpretation layer. An avatar's stated personality does not automatically follow from its body or appearance.

For HORIZON-on/off comparisons, **R1 and R2 must be mechanically, visually, and behaviorally equivalent** at baseline. Compare a HORIZON-enabled observation policy to a control with matched underlying sensory evidence wherever feasible. Re-run with swapped labels, matched scenario seeds, identical NPC objectives, and recorded policies/model versions.

The images and numeric values in this document are conceptual. Do not treat candidate thresholds or mechanical profiles as validated robotic specifications.

## 2. Prefab composition

```text
AvatarRoot (persistent unique ID, world transform)
├── EmbodimentProfile (body class, dimensions, limits, affordances)
├── PhysicsRoot (kinematic controller or articulated rigid body)
│   ├── PrimaryCollision (capsule / cylinder / box / compound proxy)
│   ├── ContactTriggers (hands, feet, bumpers, grasp region)
│   └── ProxemicZones (social boundaries: NON-PHYSICAL triggers)
├── NavigationController (navmesh / waypoint graph / dynamic avoidance)
├── MobilityController (locomotion, acceleration, stopping, turning)
├── VisualRig (low-poly mesh, material palette, LODs)
│   ├── SkeletonOrJoints (human rig or mechanical joints)
│   ├── AnimationGraph (idle, walk, gesture, gaze, recover)
│   └── ExpressionOutputs (face/eyes/ARGB for robots; expression rigs for humans)
├── SimulatedPerception (camera FOV, audio field, contacts, occlusion)
├── SocialActuators (gaze, head orientation, gesture, voice, pause)
├── TaskPlanner (independent objectives, scheduler, action affordances)
├── PersonaState (stable behavior knobs + ephemeral context/state)
├── OptionalHorizonAdapter (Halo/Echo/Wake/Focus/Contour/Prism/Haze/Trail)
└── Telemetry (events, contacts, decisions, sensor observations, timestamps)
```

**Separation of concerns:** The LLM cannot set arbitrary positions, velocities, poses, or force impulses. It issues bounded requests: `move_to`, `look_at`, `turn_to`, `speak`, `wait`, `gesture`, `join_queue`, `yield`, `interact_with`, `request_help`. A deterministic controller decides whether each request is physically and contextually feasible; the simulation physics and robot host safety boundary remain authoritative.

## 3. Visual direction: compute-first low poly

**Overall aesthetic:** stylized expo diorama; geometric shapes with recognizable silhouette, matte flat-shaded materials, restrained color palettes, minimal texture atlases, no hair/fabric simulation in v0.1. Favor readable poses and motion trails over face realism. Avatars need visible head/torso orientation, hands/arms or wheels, and distinctive gait class for prosodic experiments.

| Class | Readable silhouette | Distinctive cues | Prototype animation needs |
|---|---|---|---|
| Human pedestrian | Head, torso, articulated arms/legs; varied stature and clothing | Badge, backpack, jacket, glasses, hair shape | Idle, walk, turn, nod, point, wave, sit, stand, speak |
| Human with mobility aid | Similar character rig with independent wheelchair/cane/walker asset | Wheels/hand positions, maneuver envelope | Roll/propel, turn, reach, stop, interact |
| Humanoid robot R1/R2 | Matched head-screen, torso, two arms/legs | Identical chassis; HORIZON shown only in debug HUD | Walk, turn, look, gesture, stop, dock |
| Wheeled service robot | Boxy body + wheels/casters + head/screen | Low center of mass, wide turn constraints | Differential/holonomic move, rotate, dock |
| Quadruped robot | Four legs, central body, sensor mast | Larger footprint, distinct pose envelope | Walk, stop, pivot, crouch, reposition |
| Background NPC | Simplified silhouette and palette variations | Low detail, clear motion direction | Idle, locomotion, basic gesture |

**Suggested visual budgets, not validated:** In a low-end first prototype, start near ~1–4k triangles for important avatars and ~0.2–1k for distant crowds; reduce materials and draw calls before obsessing over polygon count. Use LOD switching, pooled animation controllers, simple shadows or none, and avoid unnecessary skinning updates for distant NPCs. Measure actual frame times on target hardware.

**Important:** Body proportions, disability, clothing, facial appearance, or apparent age must not encode moral alignment, intelligence, trustworthiness, or hidden intent. Persona settings and physical ability are separate.

## 4. Mechanical and articulation profiles

Represent each avatar's embodiment through **independent sliders plus hard constraints**. Slider values are normalized 0–100 for editor usability, but the physics engine uses units/curves appropriate for each chassis. A mobility aid isn't a defect or reduced social agency; its controller simply follows different kinematic constraints.

| Group | Slider / setting | Meaning / effect | Notes |
|---|---|---|---|
| Mobility | Max ground speed | Upper translational velocity | Resolve to m/s by embodiment type |
| Mobility | Acceleration | Time to reach movement speed | Affects motion salience |
| Mobility | Braking control | Stopping distance / deceleration | Test queue entry and pedestrian yielding |
| Mobility | Turning agility | Yaw-rate or turn-radius limit | Wheeled vs biped modes differ |
| Mobility | Path clearance | Preferred extra space around obstacles | Behavioral preference; never override physical clearance |
| Mobility | Gait cadence | Walk/step frequency or wheel motion beat | Candidate prosodic movement signal |
| Stability | Balance/recovery | Recovery from perturbation | Early prototype is scripted, not full dynamic balance |
| Stability | Terrain tolerance | Permitted slope/step/ramp profile | Derived from rig and navigation link data |
| Manipulation | Arm reach | Reachable interaction envelope | Different from total body radius |
| Manipulation | Joint range | Available joint angles / constraints | Per-joint authored limit table |
| Manipulation | Dexterity | How precisely props can be picked/placed | Can initially be discrete success bands |
| Expression | Gesture amplitude | Small-to-large gesture motion | Keep within collision limits |
| Expression | Gesture tempo | Speed and cadence of gestures | Makes exaggerated behavior visually legible |
| Expression | Head/gaze agility | Orientation speed and tracking | Independent of inference quality |
| Expression | Expressive bandwidth | Available channels: face, lights, voice, hands | Capability, not claimed emotion |
| Interaction | Personal-space preference | Preferred conversational distance | Context and individual-relative; nonphysical |
| Interaction | Response preparation | Delay before an action/acknowledgment | Separate LLM computation from simulated reaction |
| Interaction | Yield tendency | Willingness to pause/replan path | Behavior policy; not mechanical stability |
| Sensor | FOV / range / noise | Simulated visual/acoustic sensor availability | Observation, not body capability |

Keep **categorical capabilities** separate from continuous sliders: `locomotion_type`, `can_use_stairs`, `escalator_allowed`, `elevator_compatible`, `wheelchair_access`, `can_reach_high_counter`, `can_open_door`, `can_grasp`, `can_speak`, `can_display_face`, `sensor_suite`. Enforce coherent settings: a wheeled non-stair-climbing body cannot acquire stair navigation by increasing agility to 100.

## 5. Physics and collision fidelity ladder

**P0 — Prototype navigation (recommended first):** Static props use primitive collider shapes; agents use a capsule/cylinder/compound body proxy, navmesh or graph navigation, overlap triggers, velocity-based local avoidance, no articulated ragdolls. Contact events are logged. Movement is deterministic between high-level LLM decisions.

**P1 — Kinematic embodiment:** Add chassis-specific accel/brake, turning radius, wheelbase or gait, slopes, low steps, door widths, elevators, queuing/spacing, simple object manipulation snaps. Use swept collision queries to prevent tunneling and avoid sudden teleports.

**P2 — Articulated interaction:** Add joint limits, IK hand targets, contact sensors at hands/feet/bumpers, staged object pickup, physically meaningful collision of moving appendages, and animated recovery; disable self-collision pairs that are supposed to overlap.

**P3 — Robotics validation:** Optional physically simulated actuators, contact forces, mass/inertia, friction, suspension/balance, real sensor models and ROS/Isaac-style hardware-oriented integration. This is a separate validation track rather than an early requirement.

**Collision channels:** (1) world static; (2) dynamic obstacles/props; (3) human/robot actor bodies; (4) interactable targets; (5) line-of-sight/acoustic occluders; (6) nonphysical social proximity triggers; (7) debug overlays. Never use a social 'boundary bubble' as the sole physical collision volume.

**Important distinctions:** Contacts are observable events, not proof of hostility; virtual 'personal space' overlap is a context cue, not physical impact; scripted fictional security incidents should have clear simulator-owned authorities and consequence rules, never uncontrolled force from HORIZON interpretations.

## 6. Mobility, venues and navigation links

- **Navigation surfaces:** public aisles, booth interiors, test lane, lounges, ramps, staff-only corridors, service lanes.
- **Static constraints:** door width, low overhang, pillar, booth wall, crowd barrier, stage edge, table/counter, cable cover, planters, stacked crates.
- **Dynamic constraints:** queues, mobile carts, temporarily closed paths, people clustering, low-speed robot traffic, doors changing state.
- **Multi-floor links:** stair links, ramps, elevators with queues/capacity/timers, escalators with direction and boarding constraints. An actor only receives links supported by its capability profile.
- **Socially meaningful geometry:** conversation groups create avoid-if-possible space; staff-only areas require role authorization; people aren't static obstacles and must retain their own objectives.

The host nav/physics controller performs collision avoidance and emergency stopping. SOMA may suggest a conversational detour, yielding, a socially preferable route or a request for passage, but must not supersede host safety logic.

## 7. Observable kinetic vectors sent to HORIZON ΔP

Source every event from actual simulation state or a clearly marked synthetic sensor model, not directly from hidden objectives:

```text
world_position_xyz, heading, translational_velocity, angular_velocity,
proximity_and_approach, pose_joint_angles, gesture_id_and_envelope,
head_orientation, line_of_sight, contact_location_and_duration,
relative_spatial_delta, movement_timing, voice_source_and_amplitude,
source_confidence, occlusion, event_timestamp, source_provenance
```

The environment holds privileged ground truth for *scoring only*. Robot R sees noisy, partial, delayed observations. Personal labels (shy, hostile, deceptive) should not be auto-filled from the simulator state into its perceived sensor field.

## 8. Lightweight avatar configuration (YAML example)

```yaml
avatar_id: R1
role: guide_robot
embodiment:
  archetype: biped_service_robot
  scale_m: 1.45
  locomotion_type: legged
  physics_fidelity: P1
  colliders: [capsule_body, hand_probes]
  capabilities: [walk, turn, gesture, speak, face_display, argb]
  navigation_links: [flat_ground, ramps, stairs_authorized, elevators]
visual:
  style: low_poly_mat
  mesh: robots/biped_guide_a
  palette: [ivory, graphite, cyan]
  rig: biped_robot_v1
  lod: auto
mobility_sliders:        # 0..100 => resolve via embodiment-specific lookup
  speed: 55
  acceleration: 55
  braking: 75
  turning_agility: 60
  clearance_preference: 65
  balance_recovery: 70
articulation_sliders:
  arm_reach: 65
  dexterity: 40
  gesture_amplitude: 45
  gesture_tempo: 50
  gaze_agility: 80
social_actuation:
  expression_channels: [face, argb, voice, head, arms]
  personal_space_preference: 60
planner:
  independent_goal: guide_visitors_and_complete_tasks
  action_set: [move_to, look_at, turn_to, speak, wait, yield, gesture, request_help]
perception:
  mode: horizon_on           # R2 test: horizon_off, all else matched
  sensors: [rgbd, mic_array, proximity, contacts]
logging:
  record_actions: true
  record_observations: true
  record_contact_events: true
```

## 9. Starter avatar cast presets

Keep these mechanical/visual presets **independent** of the separately authored Persona Mixer. Numbers and details below are illustrative.

| Actor | Base prefab | Distinguishing visual design | Mechanical/kinetic test affordance |
|---|---|---|---|
| R1 HORIZON | humanoid robot A | Ivory/graphite, cyan face-light | Baseline test body; HORIZON on |
| R2 CONTROL | **same humanoid robot A** | Same mesh, same body; distinct small ID badge only | Matched-control body; HORIZON off |
| Developer | human pedestrian | Dark cardigan, lanyard, laptop | Pauses, pivots, points at monitors |
| Floor coordinator | human pedestrian | Event vest, tablet | Walks briskly, reroutes around queues |
| Security officer | human pedestrian | Uniform/vest and radio | Patrols, stands at boundaries, calls for assistance |
| Exhibitor | human pedestrian | Bright booth colors | Exaggerated arm/hand gestures; dynamic audio |
| Visitor X | human pedestrian | Color-distinct coat, badge | Direct speech, nodding, pointing |
| Visitor Y | human pedestrian | Backpack, muted clothing | Subtle hand raises, glance-and-withdraw poses |
| Entertainer | human pedestrian | Bright jacket or hat | Quick gesture shifts and playful movement |
| Skeptic | human pedestrian | Ordinary neutral clothing | Direct gesture and speech variation, not villain coding |
| Observer | human pedestrian or mobility-aid variant | Minimal accessories | Watching, waiting, moving on without addressing robot |

For accessibility and testing, randomly assign alternative locomotion and mobility-aid archetypes across a balanced sample of roles rather than consistently tying one role to a particular body. Avoid conflating visible physical differences with interpersonal intent.

## 10. Editor: Avatar Foundry controls

**A. Visual:** silhouette, body archetype, scale, outfit kit, color palette, face rig, badge, LOD, animation set.  
**B. Mobility:** speed, accel, braking, turn agility, clearance, gait cadence, stability, terrain compatibility.  
**C. Articulation:** joint range, arms, reach, dexterity, head/gaze agility, gesture amplitude/tempo.  
**D. Physical interaction:** collider type/size, mass/fidelity setting, contact sensors, prop manipulation, route affordances.  
**E. Persona link:** independent goals, behavioral slider preset, current ephemeral state, relationships and interaction history.  
**F. Sensing:** available simulated sensors, FOV, noise, delay, HORIZON enabled/disabled/ablated.  
**G. Test options:** random seed, reproducibility lock, randomize appearance only, randomize mechanics only, A/B match lock.

**Editor constraint system:** On each slider change, show derived physical units and feasibility warnings; clamp physically invalid combinations and explain why. Keep a 'Reset to paired control' action so R1 and R2 can always be compared fairly.

## 11. Event/action loop

```text
Fixed simulation tick: movement + physics + collision + nav state
    ↓
Sensor emulation: limited view, acoustic field, contacts, timestamps
    ↓
Optional HORIZON: source association, delta baseline, context, uncertainty
    ↓
Policy checkpoint: LLM selects high-level action on meaningful events
    ↓
Action gate: permission, capability, safety, path feasibility
    ↓
Controller: animate/locomote/speak/gesture using bounded parameters
    ↓
Telemetry: cause, observation, choice, execution, outcome, repair
```

**Candidate scheduling only:** Physics/controller tick might begin at 30–60 Hz; social/perception refresh can be slower or event-driven; LLM calls should not occur per rendered frame. Benchmark timing rather than baking in assumed real-time rates.

## 12. Graduated difficulty and ablation

Start with uncluttered layouts, a handful of objects, wide hallways and one or two interacting NPCs. Gradually vary **prop density, clutter distribution, moving-obstacle density, occlusion complexity, crowd behavior, audio interference, dialogue overlap, multi-floor transit and agent capability diversity**. Avoid one global difficulty slider that changes everything: a master 'complexity' control may drive separate clearly logged dimensions, but individual axes must remain independently adjustable.

For each scenario, record `seed, map_id, environment_generation_params, actor_profile_hashes, control_or_horizon_mode, agent_model_version, available_evidence, action_log, contact_log, success_metrics`. Re-run matched seeds with one variable changed, then use randomized seeds for generalization.

## 13. Minimum viable build

1. One single-floor low-poly expo map with booth walls, desks, chairs, a central aisle and a queue.
2. Two mechanically identical R-class biped prefabs, one human pedestrian prefab with cosmetic variants, optional one wheeled service robot.
3. Rigid/capsule collision, navmesh, gaze and a small gesture set, simple voice/text events.
4. Synthetic vision/acoustic/proximity observations with timestamps and partial occlusion.
5. Persona Mixer + Avatar Foundry profiles loaded from data, and A/B toggle for HORIZON.
6. One test scene: Robot talks with X; Y makes subtle bid; Z creates a playful high-intensity disturbance; dynamic obstacle blocks a path.
7. Logs and replay; compare decisions, interruption rates, clearance, task completion, false hostility interpretations and computational load.

**Design assertion:** Do not spend the early compute budget on rendered realism. Spend it on controlled tests, plausible motion cues, reproducible simulations, and legible HORIZON diagnostics.
