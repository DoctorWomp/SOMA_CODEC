# SOMA RANGE × HORIZON ΔP — Architecture Assessment & Efficient Build Plan

**Review v0.1 · 20 October 2026**  
**Status:** design review and proposed experimental plan, not validation of an implementation.  
**Primary question:** Under controlled, reproducible conditions, does HORIZON's context-relative, spatial-temporal organization of observations improve appropriate agent decisions beyond simpler baselines?

> **Recommendation:** Keep SOMA HORIZON ΔP as an optional, interpretable perception-and-interpretation adapter. Build the smallest reproducible RANGE simulator **before** committing to an expensive game-engine world. Keep the low-poly game engine as a rendering, embodiment, and later sensor-simulation layer, with a stable typed interface to the experiment core.

## 1. What was reviewed and how

Four user-provided specialist *role briefs* were used as complementary review lenses, **not as empirical proof or independently running experts**:

1. **THE FORGE — Agentic Development (v1.0):** Orchestrator/Actor/HITL task-cluster design; capped build–test–correct loops; verifiable completion gates; human steering.
2. **AI ALIGNMENT RESEARCH BRIEF (v1.0):** Epistemic boundaries, robustness against context spillover, empirical benchmarking, independent validation, reproducibility, data integrity.
3. **SIGINT + COMSEC BRIEF (v1.0):** Signal localization, source attribution, interference/multipath, provenance, synchronization and transport security; applied to **consent-bound robot sensor simulation**, not to unauthorized surveillance or offensive interception.
4. **AI + ROBOTICS R&D BRIEF (v1.0):** Data acquisition → simulation → hardware/edge path; perception, control, integration, safety, repeatable tests and compute limits.

Existing designs examined: `SOMA_HORIZON_DeltaP_Concept_Spec_v0.1.md`; `SOMA_RANGE_Avatar_Foundry_Scaffold_v0.1.md`; `SOMA Codec — Chatbot Tier Expression Spec v0.5.md`; `SOMA Codec — Situational Tier Protocols v0.1.md`; `SOCIAL_GEOMETRY_ENGINE_v0.1.md`; `RELATIONAL_LEDGER_SPEC_v0.1.md`; `BET Module — Concept Note v0.1.md`; `SOMA_EXPRESSION_MODULE_v0.1.md`; `INTENT_TRIANGULATION_RESEARCH.md`; `CDC_MODE_SWITCHING_ARCHITECTURE_v0.1.md`; plus the conversation's proposed Persona Mixer and map concepts.

**Evidence distinction:** The supplied documents support the *intent and proposed structure*. Recommendations and sample thresholds in this assessment are engineering proposals, **not** demonstrated experimental results. Game-engine capabilities referenced later are supported by linked vendor documentation.

## 2. High-level verdict

| Dimension | Assessment | Immediate consequence |
|---|---|---|
| Conceptual architecture | Coherent and modular | Keep HORIZON separate from motor control, safety and outward BET DAC |
| Interpretation guardrails | Strongest in the newer specs | Promote latest rules to canonical precedence over early trait/sincerity scoring drafts |
| Operational data contract | Partially specified | Write one versioned event/observation/action schema before coding |
| Experimental design | Useful intent, incomplete controls | Define information-parity and paired-trial protocols; prevent hidden-state leakage |
| Simulation assets | Visual concepts, not executable geometry | Author a canonical coordinate-level map/props schema and collision rules |
| Autonomous NPCs | Good role/persona vocabulary | Define an NPC state machine and perception restrictions; LLM only for higher-order choices |
| ΔP signal definition | Promising as a *typed deviation vector* | Preserve units, missingness, calibration, provenance and per-channel uncertainty |
| Sensor realism | Currently conceptual | Use synthetic, explicitly tagged observations first; validate physical sensing separately |
| Robotics transfer | Plausible roadmap, not established | Keep physics/navigation safety authority independent and track sim-to-real gaps |
| Developer workflow | Well suited to FORGE loops | Small task clusters, explicit verification gates, short capped iterations |

**Research hypothesis worth testing:** HORIZON's representations may reduce missed conversational bids, false interruptions, mistaken social-source association and context-repair delay *without* reducing task completion or increasing compute cost unacceptably. None of these gains is yet demonstrated.

## 3. P0 corrections before implementing

### P0-01 — Establish canonical document precedence

Older SOMA drafts include persistent trust scores, sincerity/deception classifiers, threat labels or behavioral profiling. Those conflict with newer HORIZON/Tier-1 principles of **observable ≠ inferred**, **ephemeral anonymous tracks**, **no automatic hostility verdict**, and **no persistent person labels without consent**. Create `DESIGN_DECISIONS.md` and `SAFETY_BOUNDARY.md` establishing:

- **Authoritative for RANGE v0.x:** HORIZON v0.1 + Avatar Foundry v0.1 + chatbot v0.5 interpretive limitations + situational Tier 3/4 confidentiality and host-only physical safety.
- **Research seeds only:** early sincerity scoring, threat-score heuristics, unvalidated EEG/affect mappings, old hardware latency claims and the generalized 7/38/55 communication percentages.
- **Allowed in synthetic scenario ground truth:** authored NPC motivations and fictional event labels for *evaluation only*. These are not inputs to Robot R.

Test: no route from hidden NPC personality, author-defined `intent`, privileged simulator state or benchmark answer into the robot's observation packet.

### P0-02 — Prevent the paired-robot contamination problem

Running R1-HORIZON and R2-Control together in one expo produces interference: NPCs respond to two robots, crowd flow changes and decisions cease to be equivalent. **Default:** one robot per isolated scenario replica; same geometry, NPC initial private goals, seed and event schedule. Swap `R1`/`R2` visual IDs across runs. A two-robot collaboration test is a **separate scenario**, not the main paired A/B experiment.

Note: matched random seeds do not guarantee identical future trajectories after agents choose different actions. Compare paired *starting conditions* and measure divergent outcomes. If exact exogenous equivalence is necessary, use a replayed scripted event tape; label limitations because reactive NPCs are then constrained.

### P0-03 — Separate three experimental questions

1. **Additional information:** does the sensor package give more useful evidence than a basic perception feed?
2. **Better organization:** with **identical available evidence**, does the HORIZON representation outperform raw structured observations?
3. **Better execution:** do resulting response plans actually improve embodied interactions once timing, navigation, and safety gates are applied?

Recommended experiment arms:

| Arm | Perceptual input | Decision layer | What it isolates |
|---|---|---|---|
| A0 — Scripted baseline | Basic structured observations | Deterministic rules | Floor for navigation and turn-taking |
| A1 — Raw-evidence LLM | Full same sensory packet available to A2 | Same LLM/prompt budget | Rich evidence without HORIZON organization |
| A2 — HORIZON LLM | **Same evidence as A1** reorganized by HORIZON | Same LLM/model/action set | Representation and reasoning benefit |
| A3 — Sensor-enhanced HORIZON | Optional extra sensor cues | Same LLM | Incremental value of more modalities |
| A4 — Ablations | Same evidence, remove selected HORIZON modules | Same LLM | Contribution of ECHO/WAKE/PRISM/HAZE etc. |
| Oracle — Evaluation only | Privileged full world truth | Reference policy | Optional upper-bound diagnostic, **never** a deployable agent |

Equalize or *report* context-window/token differences, otherwise the comparison also measures prompt compression.

### P0-04 — Maintain a single world authority and perception boundary

One authoritative `WorldState` owns NPC positions, geometry, private goals, object states and collision. `SensorAdapter` derives **partial, delayed and noisy observations** for each observer. `HorizonAdapter` sees only those observer-specific packets. `EvaluationOracle` alone reads hidden goals and scene truth. `ActionGate` validates proposed commands. This must be enforced in code and unit-tested.

### P0-05 — Safety/privacy are execution constraints, not affect labels

Physical collision avoidance, forbidden-zone access, emergency stops and staff authority belong to the simulator/robot-host rules, not PRISM's interpretation of facial expression, sarcasm or ΔP. Person-to-person friction is an interpretive variable, not authority to eject or restrain anyone. Public-space participants should be anonymous by default; in simulated events, restrict disclosure according to modeled recipient/earshot rules.

## 4. P1 technical design tightening

### P1-01 — Fix the ΔP semantics

The current formula multiplies a normalized feature deviation by reliability `q_k`. That risks turning **unavailable or unreliable** measurements into apparent neutral zeroes. Prefer the packet:

```text
DeltaFeature {
  channel, value, units, baseline, baseline_scope,
  signed_delta, normalized_delta, scale_method,
  quality, observed_at, expires_at,
  status: OBSERVED | DEGRADED | MISSING | NOT_APPLICABLE,
  source_track, provenance
}
```

Compute `normalized_delta = clip((value - baseline) / max(scale, epsilon), -M, M)` **only if valid**. Keep `quality` separate. Do not add heterogeneous signed acoustic, distance, gaze and gesture deltas into one universal emotion scalar. ΔP means *family of relative feature deviations*; a spatial **gradient** of the field may be derived separately and should not be confused with time change.

Cold start: if no person-specific baseline exists, use `baseline_scope: ENVIRONMENT` and mark it clearly; do not invent a person's preferences. Freeze/slow baseline learning during abrupt anomalous events to avoid adapting the anomaly into the new normal. Specify robust scale fallback and clamping conditions.

### P1-02 — Define coordinates, clocks and evidence age

Define right-handed/left-handed axes explicitly, transforms between `world`, `robot_local` and each sensor, units in meters/radians/seconds, fixed `sim_time_ms`, independent `wall_clock_ms`, modality acquisition latency, `observed_at`, `ingested_at`, `decision_at` and `expires_at`. Handle moving robot ego-motion before associating external tracks. Test stale detections and out-of-order arrivals.

**Critical:** a 360° HUD may show *full angular bins* while parts are `UNOBSERVED`; a 360° spherical graphic must not imply 360° camera coverage. Acoustic broad awareness and visual coverage are different.

### P1-03 — Make source association uncertainty first-class

A source hypothesis must carry competing alternatives (e.g., person vs loudspeaker vs reflection) and abstention. Echo, announcement, overlapping dialogue and visually silent bystanders are minimum synthetic test cases. Do not derive identity or intention from a source location alone. SIGINT's localization analogy is useful for direction finding and provenance but doesn't grant confidence in private intent.

### P1-04 — Distinguish detection from interpretation from response

Example sequence: `head turned toward robot` (**observed**) → `possible turn bid` (**interpretation**) → `offer a low-pressure opening at the next pause` (**proposal**) → `wait/speak or no-op` (**approved action**). Each stage has separate test labels, error classes and logs. The HORIZON HUD is an operator diagnostic; BEACON is a separate public-facing output palette. No hue-to-hazard trigger.

### P1-05 — Formalize the map and density controls

The images are useful mock blueprints, not machine-readable world geometry. Make **one canonical parameterized map** with coordinates, asset footprints, collision categories, zones, visibility/acoustic occluders, accessible nav links and spawn areas. Scene art is a derived view.

Keep independently adjustable axes:

| Axis | Proposed examples | Why independent? |
|---|---|---|
| Static clutter | booth dividers, tables, plants, crates | Pure path planning |
| Dynamic density | walkers, queues, carts | Crowd avoidance |
| Sight occlusion | high walls, low partitions, corners | Information uncertainty |
| Acoustic difficulty | announcements, reverb proxy, overlap | Source attribution |
| Social complexity | number of speakers, bids, ambiguity | Conversational decisions |
| Vertical topology | one floor, stairs, elevator | Multi-level planning and capability limits |
| NPC behavior variation | persona sliders, goals, temporary states | Generalization |
| Sensor fidelity | idealized to noisy/delayed/missing | Robustness |

A convenience master slider may choose a preset, but **log every underlying parameter**. Never change all axes simultaneously in a scientific comparison.

### P1-06 — Correct workload/latency assumptions

Distinct loops are required:

| Loop | Starting design, not measured target | Function |
|---|---|---|
| World/kinematics | Fixed timestep | Move, collide, navigate; independent from LLM |
| Synthetic sensors | Periodic or event-driven, modality-specific | Create timestamped observations |
| HORIZON | Event-driven with periodic coverage maintenance | Fuse, track, update interpretations |
| LLM planner | Only when a meaningful decision is needed | Choose one bounded high-level action |
| Renderer/HUD | Can be slower/disabled | Human visualization |
| Evaluator | At events + episode end | Collect outcomes, cost and failures |

Use two modes: **stepped research mode** (sim time can pause awaiting a slow LLM decision) and **real-time stress mode** (world continues, agent may miss deadlines). Do not use stepped-mode success to claim real-time responsiveness. Track simulated latency and actual inference wall-clock latency separately.

### P1-07 — Separate personas, bodies, and observations

- Persona: goals, interaction style, preferences, temporary situational state.
- Embodiment: dimensions, locomotion type, joint limits, collider and navigation affordances.
- Performance: actual ability to perceive and act, not asserted character quality.

Treat sliders as tunable configuration **resolved into real physical units** by embodiment. Hard capability flags govern steps, stairs, elevators, ramp limits, grasping, verbal and gestural communication. In mixed-population testing vary accessibility affordances without linking appearance/disability to inferred worth or character.

## 5. Proposed reference architecture

```text
SCENARIO SPEC (YAML/JSON; seed + goals + events + geometry)
                  │
             SCENARIO RUNNER ──────────────────────────────────────────┐
                  ▼                                                     │
        AUTHORITATIVE WORLD STATE ──> EVALUATION ORACLE (isolated)      │
             │     │                                                   │
     Physics/Nav   NPC private schedulers                               │
             │     │                                                   │
             └──> SENSOR EMULATION / OBSERVER FILTER                   │
                             │                                         │
                    OBSERVATION PACKETS                                 │
                             │                                         │
            ┌────────────────┴────────────────┐                        │
            ▼                                 ▼                        │
     RAW EVIDENCE VIEW                 HORIZON ΔP ADAPTER              │
      (control arm)             ANCHOR / HALO / ECHO / WAKE            │
                                  FOCUS / CONTOUR / PRISM              │
                                    HAZE / TRAIL                       │
            │                                 │                        │
            └────────────────┬────────────────┘                        │
                             ▼                                         │
                   SHARED LLM POLICY API                               │
                 (structured, bounded actions)                         │
                             │                                         │
                     ACTION GATE / HOST                                │
                             │                                         │
                          WORLD                                        │
                             ├──> EVENT LOG ──> REPLAY / METRICS <────┘
                             └──> OPTIONAL GODOT 3D VIEW / HALO HUD
```

**Do not duplicate authoritative physics** between Python and the game engine: in phase 0, Python is world authority; once 3D navigation/physics matters, promote the engine as authoritative and have Python act as scenario orchestrator, sensor/LLM service, and evaluator via the same typed interface.

### Minimal canonical event contract (illustrative)

```json
{
  "schema_version": "0.1",
  "episode_id": "expo_bid_0042",
  "sim_time_ms": 8350,
  "observer_id": "robot_R",
  "event_id": "ev_0093",
  "type": "observation",
  "sensor": "vision_pose_proxy",
  "frame": "robot_local",
  "source_track": "anon_02",
  "measurement": { "bearing_rad": -0.48, "distance_m": 2.1, "head_orientation": "toward_group" },
  "observation_status": "OBSERVED",
  "confidence_status": "synthetic_proxy_uncalibrated",
  "observed_at_ms": 8220,
  "expires_at_ms": 8950,
  "provenance": "scene_sensor_adapter_v0",
  "consent_scope": "public_ephemeral"
}
```

The NPC's hidden goal (`wants_to_speak`) is absent. The benchmark stores it separately. Avoid claiming an empirical numeric confidence unless calibrated; use evidence/status flags first.

### Suggested bounded action API

`move_to(zone_or_point)`, `turn_to(track)`, `look_at(track)`, `wait(duration_s)`, `speak(text, addressee_scope)`, `invite(track)`, `gesture(type)`, `yield_to(track)`, `request_help()`, `no_op()`.

`ActionGate` checks reachability, access permissions, speaking audience, event validity, timeout, and independent collision/safety rules. Rejections are logged rather than silently corrected.

## 6. Efficient tooling: what to use and when

### Default recommendation: Python-first → Godot 3D → robotics simulator if needed

**Stage A — Python reference lab (no game engine):** Python 3 with `pytest`, typed dataclasses or Pydantic, JSONL/SQLite, NumPy/pandas for analysis; optional Mesa if its agent scheduling, spatial modeling and visualization fit. Avoid a framework merely for its reputation. Build a 2D or 2.5D graph/continuous-plane expo, scripted actors, collision proxies, synthetic sensor packets and a trace viewer. **No LLM is required for the first end-to-end integration test.**

**Stage B — Godot 4 low-poly client:** create one room/booth/corridor map, capsule robot, cylinder/capsule humans, NavigationAgent3D/navmesh, static shapes, one moving cart, minimal head/hand gesture rigs. Godot has official 3D navigation facilities, WebSocketPeer for connecting to external services and `--headless` for automated/CI use. Prefer a short, authenticated/local-only bridge with versioned messages. Its navigation avoidance does not replace physics collision and can stall in cramped scenes; test it independently. [Godot navigation](https://docs.godotengine.org/en/stable/tutorials/navigation/navigation_using_navigationservers.html) · [Godot WebSocket](https://docs.godotengine.org/en/stable/classes/class_websocketpeer.html) · [Godot headless](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)

**Alternative — Unity:** sensible if you specifically prioritize ML-Agents' Python environment interface, existing Unity skills/assets, or future RL training. The first pilot doesn't require RL. [Unity ML-Agents](https://github.com/Unity-Technologies/ml-agents)

**Later — Isaac Sim:** revisit when testing modeled camera/depth/LiDAR/contacts, ROS 2, real robot control, physical fidelity or sim-to-real transfer. Its capabilities do not eliminate the need to validate simulated sound, social conventions, and uncertainty in real conditions. [NVIDIA Isaac Sim](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/) · [Sensors](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/sensors/index.html)

**Not recommended for day one:** Unreal photorealistic levels, networked production multiplayer, full-body ragdoll/actuator simulation, 10 continuously prompting LLMs, live speech synthesis for everyone, real acoustics, facial emotion classification, fine-tuning, a multilayer GPU voxel field, or a public AR product.

### Starter repository layout

```text
soma-range/
  README.md
  docs/
    DESIGN_DECISIONS.md
    SAFETY_BOUNDARY.md
    EXPERIMENT_PROTOCOL.md
    METRICS.md
  schemas/
    observation.schema.json
    action.schema.json
    scenario.schema.json
  configs/
    avatars/robot_r.yaml
    personas/visitor_y.yaml
    maps/expo_micro_v01.yaml
    scenarios/expo_polite_bid_v01.yaml
  range_core/
    world.py                # single authoritative state
    scenario.py             # load/seed/run
    nav.py                  # collision + route constraints
    npc.py                  # scripts/goal states
    sensor_adapter.py       # filtered, time-stamped evidence
    horizon.py              # optional typed perception layer
    action_gate.py          # independent execution checks
    policy.py               # rules and LLM API adapter
    recorder.py             # event log / replay
    metrics.py
  tests/
    test_no_oracle_leak.py
    test_paired_start.py
    test_occlusion.py
    test_action_gate.py
    test_event_replay.py
    test_horizon_toggle.py
  viewer/                   # optional early 2D browser/map
  godot_client/             # add only after phase-0 tests pass
  results/                  # structured run outputs
```

**Runtime configuration:** pin Python and dependency versions in a lockfile; pin model identifier and decoding settings; never store API keys in repo or in logs. Remote model calls may differ even with fixed seeds. For exact repeat, cache and replay returned decisions.

## 7. Pilot scenario and test metrics

### Scenario S001 — “Polite bid during active conversation”

- **Geometry:** one rectangular room, two booth partitions, an information counter, narrow/wide alternate passage, optional moving cart; no second floor.
- **Actors:** Robot R; Visitor X asking a question; Visitor Y observing and possibly bidding; Exhibitor Z conducting an unrelated animated demonstration. Start with Y/X only, then introduce Z and cart independently.
- **Hidden oracle:** each NPC's actual authored goal, plan and event timing; R cannot read these.
- **Observable events:** approach/orientation, simulated speech source, time-limited gestures, proximity/occlusion, pauses, loud demonstration cues.
- **Available actions:** continue, yield, invite, clarify, orient, reroute, avoid obstruction, no-op.
- **Target behavior:** avoid disrupting X unnecessarily; detect a possible bid without assuming it; allow correction if Y was merely watching; handle loud levity without a hostility verdict; navigate safely.

### Primary outcome definitions

| Metric | Definition and failure analysis |
|---|---|
| Bid response precision | Appropriate bid responses / all unsolicited bid responses; mark false approaches |
| Bid opportunity recall | Appropriate responses to authored observable bids / evaluable bid opportunities; record inaccessible/occluded opportunities separately |
| False interruption rate | Disruptive robot turns / eligible conversation opportunities |
| Navigation validity | Contact violations, blocked-portal attempts, path failures, minimum separation; per embodiment |
| Task completion | Whether assigned guide objective completed under deadline/constraints |
| Context repair | Turns after corrective evidence; correction accuracy; repeated misinterpretation |
| Incongruence misread | Playful or unrelated high-intensity events misclassified as interpersonal conflict |
| Uncertainty discipline | Abstention where source ambiguous; calibration if numeric probabilities are genuinely estimated |
| Privacy/scope violations | Disclosure to unauthorized listeners / audience changes mishandled |
| Resources | Median/p95 inference latency, calls, tokens, CPU/GPU load, wall time per episode |

**Important:** human social norms are often ambiguous. Use a documented scenario oracle plus multiple human ratings where applicable; record disagreement. Do not use a single magic “social accuracy” score.

### Test method

1. Define success criteria and label rubric **before** collecting comparison runs.
2. Write a small deterministic unit-test suite first (e.g., source misassociation, actor outside FOV, no-permission disclosure, impossible movement).
3. Run several dozen varied pilot seeds per condition as a *debugging sample*, not a claim of statistical power.
4. Pair scenario starts; log identical evidence availability, models, prompt version, policy options, decisions and actions.
5. Analyze by scenario type; bootstrap confidence intervals or other suitable uncertainty estimates once data volume justifies them.
6. Preserve unseen hold-out scenarios and evaluate after freezing code/prompt changes.
7. When ready for humans, blind/reorder transcript comparisons and rate respect, interruption appropriateness and comprehension; keep fictional goal ground truth separate.

### Evaluation anti-patterns

- R1/R2 competing in the same environment during the primary A/B trial.
- Giving HORIZON access to NPC scripts, role cards or intent labels.
- Comparing HORIZON with a deliberately underinformed control and claiming the effect is *representation*.
- Letting LLM-generated explanations substitute for sensor/action traces.
- Tuning on the final evaluation scenarios.
- Using model confidence scores as calibrated probabilities without calibration.
- Reporting step-mode success as real-time performance.
- Treating expressive loudness as a safety/honesty/personality score.

## 8. FORGE implementation plan: small, gated task clusters

The uploaded FORGE brief calls for an Orchestrator, specialized Actors, capped loops, explicit human verification and a compressed HITL interface. For a solo beginner, these can be **sequential AI-assisted roles**, not ten concurrent paid agent instances.

| Cluster | Owner lens | Deliverable | Verification gate |
|---|---|---|---|
| **RG-01 — Contracts** | Systems + alignment | Data schemas, axes, timing, permission and provenance rules | Example observations/actions validate; hidden fields rejected |
| **RG-02 — World** | Simulation engineer | Small top-down expo world with zones and collision | Deterministic routes, blocked objects and fixed seeds work |
| **RG-03 — Actors** | Agent/UX | X/Y/Z schedulers and hidden goals; R action API | NPCs pursue goals without reading Robot R's internal state |
| **RG-04 — Sensor proxies** | Signals + vision | Synthetic gaze, audio direction, FOV, occlusion, noise/latency | Known false-source/occlusion tests pass |
| **RG-05 — Controls** | ML/research | A0/A1/A2 toggles and identical evidence inputs | Paired start validated; oracle leakage test passes |
| **RG-06 — HORIZON-lite** | SOMA research | ANCHOR, HALO, ECHO, WAKE, PRISM, HAZE, short TRAIL; FOCUS/CONTOUR minimally | Typed delta and missingness; correct alternative hypotheses |
| **RG-07 — Harness** | QA/data | Event logs, replay, metrics dashboard and test runner | Repeated scripted trace matches; reports reproducible |
| **RG-08 — LLM planner** | LLM engineering | Bounded structured high-level actions with timeouts | Invalid output rejected; no direct motor-state modification |
| **RG-09 — Godot client** | Graphics/robotics | Minimal low-poly hall and representative animations | Engine and Python agree on object IDs/world state; headless pass |
| **RG-10 — Hard cases** | Alignment/red team | Humor, source confusion, crowding, privacy, prompt injection via overheard speech | Failing scenarios reproducible with traces and corrective tests |

**Human verification:** after each cluster, inspect a short demo or report, accept/reject it, and approve the next scope increase. Cap retries and token/API expenditures. Do not launch parallel actors against the same files without ownership boundaries. Maintain a brief decisions register.

### Suggested immediate first work session (low complexity)

1. Create the repository and `docs/EXPERIMENT_PROTOCOL.md` containing the **one question**: “With evidence held equal, does HORIZON alter turn-taking decisions appropriately?”
2. Author one room with robot/X/Y in meters, no textures, three obstacles, two entrances, and one scripted conversation.
3. Implement world-state → filtered observation → simple rule policy → bounded action → event log.
4. Add two unit tests: Y behind a wall cannot be visually detected; X's private hidden intent is never in R's inputs.
5. Run and inspect one scripted episode; only then write `HorizonAdapter` and compare A1/A2.

**Minimum vertical slice:** `scenario.yml -> run_experiment.py -> observations.jsonl -> decisions.jsonl -> metrics.json -> optional 2D viewer`.

## 9. Deep-dive queue (not blockers for the first vertical slice)

| Research question | Proposed experiment | Priority after pilot |
|---|---|---|
| Does a shape-adaptive Halo beat a tracked-object list? | Same evidence, spatial-lobe vs object-centric representations; compare decisions and cost | High |
| How should mixed signals be localized? | Loudspeaker echo, group overlap, moving speaker, a stationary bystander; test attribution/abstention | High |
| Does ΔP normalize usefully across personalities? | Script same situation with different habitual loudness/gesture baselines, evaluate false anomaly detection | High |
| Can PRISM distinguish benign theater from escalation? | Graded playful roast, genuine argumentative escalation, near-identical gestures different dialog/context | High |
| When should a robot invite a shy bystander? | Controlled bid-strength and time-pressure gradients; false-invitation vs missed-bid tradeoffs | High |
| Does adaptive FOCUS create tunnel vision? | Peripheral bid during main conversation; vary scan coverage and focus budget | Medium |
| What uncertainty display helps operators? | Compare sphere, compass and event-list readouts; comprehension and misinterpretation tests | Medium |
| Are simulated cues physically credible? | Match simplified observations against later recorded/synthetic cameras/audio; measure domain gap | Medium-high |
| How much realism is needed? | Increase proxy fidelity with unchanged policy; check if rankings between A1/A2 persist | Medium |
| How do social constraints combine with route planning? | Queues, mobility aids, blocked corridors, escalation requiring staff rather than robot intervention | Medium |
| How should tiers 3 and 4 differ? | Same scene with trusted/anonymous introductions and changing earshot; disclosure/reply tests | Medium |
| Does a compact field help edge efficiency? | Compare structured-event vs dense voxel update cost under multiple agents | Later |

## 10. Exit gates and what *not* to claim

**Gate 1 — Functional:** at least one full episode runs with observer-restricted inputs, reproducible scripted behavior, bounded actions and a trace explaining every decision.

**Gate 2 — Experimental:** an A1 vs A2 comparison uses matched evidence, comparable policies and predeclared outcome measures; at least one scenario shows a meaningful, inspectable difference **or** a documented null result.

**Gate 3 — Generalization:** benefits do not vanish when NPC persona, map clutter, line-of-sight and noise vary on unseen scenarios; regressions are recorded, not hidden.

**Gate 4 — Embodiment:** after 3D/client integration, routing, collision, visibility, simulated latency and permitted action semantics remain faithful to the reference interface.

**Gate 5 — Sim-to-real research:** only after separate sensor validation can claims be made about real acoustic localization, body-cue detection, interaction quality, response times or embodied safety. Public deployment requires further privacy, consent, accessibility and formal safety evaluation.

### One-page decision

**Build now:** deterministic synthetic 2D/2.5D micro-expo; typed observation/action bus; hidden oracle; scripted NPCs; minimal HORIZON-lite; paired A/B and replay; low-cost evaluation.

**Add next:** Godot low-poly 3D geometry, constrained avatar motion/gestures, a small number of LLM agents, independently controlled complexity sliders, HORIZON HUD diagnostics.

**Defer:** multi-floor world, ten simultaneously running LLMs, physical audio propagation, realistic facial/affective inference, sensor fusion at full 3D voxel resolution, hardware robotics, AR overlay and any claim that HORIZON recognizes true human emotion or intent.

> **Operational motto:** *Prove the interpretive advantage in a tiny world before increasing the size of the world.*

---

## Reference documents

**User-provided project briefs (internal):** THE FORGE — Agentic Development; AI ALIGNMENT RESEARCH BRIEF v1.0; SIGINT + COMSEC BRIEF v1.0; AI + ROBOTICS R&D BRIEF v1.0.

**SOMA / RANGE concepts (internal):** SOMA HORIZON ΔP Concept Spec v0.1; SOMA RANGE Avatar Foundry Scaffold v0.1; SOMA Codec Chatbot Tier Expression Spec v0.5; Situational Tier Protocols v0.1; Social Geometry Engine v0.1; Relational Ledger v0.1; BET Module Concept Note v0.1 and earlier research seeds.

**External platform references:**
- Mesa (Python agent-based modeling): https://github.com/mesa/mesa
- Godot navigation: https://docs.godotengine.org/en/stable/tutorials/navigation/navigation_using_navigationservers.html
- Godot WebSocketPeer: https://docs.godotengine.org/en/stable/classes/class_websocketpeer.html
- Godot command line / headless: https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html
- Unity ML-Agents: https://github.com/Unity-Technologies/ml-agents
- NVIDIA Isaac Sim: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/
