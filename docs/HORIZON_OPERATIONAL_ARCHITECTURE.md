# HORIZON operational architecture for multiple avatars and a physical chassis

**Status — Proposed for engineering review.** This document describes a deployment model and a first experiment for SOMA RANGE. The existing gate plan and approved decisions govern implementation. The multi-avatar scheduler, measurements, and acceptance tests below are proposals.

## One observer per body

Give each HORIZON-equipped avatar one logical HORIZON instance. A legged humanoid, a wheeled humanoid, and a quadruped standing near the same booth can each hear a speaker from a different bearing. The booth can hide the speaker's face from the quadruped while the standing humanoid can see it. Each robot must be able to arrive at its own attribution, including an unresolved one. Chassis names alone establish no sensing capability. The scenario declares each body's sensor mounts, coverage, rates, and calibration.

On a physical robot, a host can dedicate its compute budget to one observer. RANGE can execute several observers in one process and schedule their work on one machine. In both deployments the unit to port and test is the observer's state update from its own time-stamped evidence.

| Responsibility | Owner | Practical boundary |
|---|---|---|
| Generate simulated measurements | Godot and the observer filter | Share geometry and broad-phase queries. Resolve occlusion, range, bearing, and available modalities separately at each sensor pose before delivery. |
| Interpret evidence | One HORIZON instance per observer | Own clock alignment, frame transforms, tracks, attention, hypotheses, uncertainty, and bounded history. Scope mutable state to the run and observer. |
| Execute work | Shared RANGE scheduler and workers | Share immutable code and compatible model weights. Keep queues attributable and separate each observer's mutable inference context, caches, and outputs. |
| Deliberate and act | Agent pulse and host action gate | A HORIZON update can propose a wake. The agent chooses whether to deliberate, and the host validates the resulting action. A chassis retains its own motion and safety controllers. |
| Visualize and score | Spectator and evaluator | Read observer-labelled diagnostics. Keep world truth, private goals, and evaluator labels outside the observer feed. |

Explicit communication can carry a scoped report between agents. The receiving agent keeps the sender and report provenance. Track identifiers remain local to their observer, including when both agents describe the same visitor.

## Interface between RANGE and a chassis

Start from the [RANGE observation packet](../contracts/observation.schema.json). It already carries the observer, tick, simulation time, pose, and evidence with observation time, expiry, validity, quality, and provenance. Its wire coordinate frame is `world_meters_xyz`. Anchor uses the observer pose at acquisition to transform eligible estimates into the body frame. Preserve the source frame, units, timestamps, and transform quality through that conversion.

A chassis adapter would provide the equivalent inputs from sensor drivers and time-aligned odometry. Record sensor acquisition time, host arrival time, and clock alignment quality. If a transform is missing or stale, carry that uncertainty forward and retain any usable evidence, such as an acoustic bearing without a range. Keep salience and evidence coverage distinct. A loud sound with poor localization can warrant attention while its source remains unknown.

Use filtered synthetic observations first to test layer semantics. Introduce rendered camera feeds, synthesized audio, or recorded sensor data when the question concerns front-end accuracy, calibration, or processing cost. Record the input mode with each run. A synthetic event run and a raw-sensor run measure different parts of the system.

## Layer scheduling and fidelity

| Layers | Proposed update policy |
|---|---|
| L0 Anchor and L1 Halo | Refresh pose and coarse availability within declared freshness limits. Reserve service for each observer, including observers outside the spectator camera. |
| L2 Echo and L3 Wake | Process time-stamped acoustic and motion events. Preserve onset, direction, and track changes across batches. |
| L4 Focus | Reconsider attention when a speaker, task, uncertainty, or salient track changes. Send a reason and evidence references with a candidate pulse wake. |
| L5 Contour | Refresh affected local boundaries when the robot moves, a group changes, or an approach crosses a relevant margin. |
| L6 Prism | Revisit competing interpretations on material changes, conflicting evidence, or expiry. Record the evidence time behind each interpretation. |
| L7 Haze and L8 Trail | Evaluate missingness and age even during idle periods. Apply expiry and decay against elapsed observation time. Bound per-observer history while preserving provenance and disclosure scope. |

Give sensing and language inference separate queues and budgets. A pending model call can coexist with a new bearing, a gaze response, or an expiring track. Reuse the [pulse protocol](PULSE_PROTOCOL.md) for event-driven deliberation, triage, and backoff. Coalesce repeated updates for the same observer and cause while preserving discrete events such as speech onset and loss of track.

A scheduler job should identify its observer, layer, evidence time, earliest run time, deadline, and estimated cost. Stagger periodic work. Batch compatible jobs up to the earliest deadline, reserve a configurable service floor per observer, and age waiting jobs. If the model supports shared serving, load its weights once and account separately for each observer's mutable state and in-flight requests. Session resets and model-slot reuse must clear or restore the correct observer's state.

Under contention, defer background interpretation first. Expose the age of the last result, flag missed freshness limits, and record which work was deferred, expired, or coalesced. A deliberate change to sensor fidelity or sampling rate becomes a named experimental condition. Keep the render camera independent of sensor eligibility.

## Resource accounting

Profile one, two, then three equipped avatars under the same scene, display preset, model configuration, and event sequence. Measure CPU time per layer, queue wait and service time, per-observer RAM, GPU time, peak VRAM, frame-time tails, and per-observer missed deadlines. Include simultaneous events and a sustained run long enough to exercise Trail expiry and cache reuse.

Start with the existing [inference configuration](../configs/inference.yaml). Its GPU budget is 16,376 MiB with a 2,048 MiB reserve for Godot and headroom. Count shared model weights once, then measure growth from per-observer caches, sensor buffers, activations, and concurrent jobs. Use measured peak usage with rendering and both model servers active to set admission limits. A memory fit alone leaves GPU execution contention unresolved. Apply the project's [render-tax comparison](ART_DIRECTION.md) and record foreground inference p95 and rendered frame p95/p99.

For STEPPED replay, use simulation time for layer aging and deterministic ordering for simultaneous updates. For LIVE, record simulation time alongside monotonic wall time for queueing, execution, and delivery. Compare a physical host using its own compute, sensor rates, and clocks before making a chassis capacity claim.

## First experiment: three bodies and a peripheral speaker

Adapt SB-08. Place the three bodies near a booth at known poses. A visitor speaks from behind the booth, enters view, then addresses one robot. Declare sensor geometry, event times, and expected visibility and audibility for each observer in the evaluator fixture. Start with Anchor, Halo, and an Echo bearing feeding Focus. Log candidate Focus wakes in shadow mode while the existing pulse drives behavior.

1. **Solo reference.** Record each observer's filtered stream. Replay each stream alone with identical configuration and capture track updates, attribution or abstention, evidence age, and candidate wakes.
2. **Concurrent replay.** Replay those same three streams together. Match outputs by observer, observation, and simulated time. Require identical discrete outcomes for the deterministic path and declare numerical tolerances before comparing continuous outputs. Perturb only one recorded stream and check that other observers' semantic outputs stay identical under adequate budget. Use recorded model decisions wherever deliberation enters the comparison.
3. **Rendered LIVE.** Repeat with the owner-machine rendering preset and F3/N3 active. Trigger a burst across all three observers and rotate which chassis gets the foreground role. Report every observer's response latency, missed wakes, stale outputs, maximum service gap, and which source it attended to. Measure sensor-to-Focus latency separately from model latency and host-accepted action latency.

**Review decision.** Advance one Focus wake into a controlled pulse-on/pulse-off comparison after observer isolation and replay parity pass, the occluded observer preserves uncertainty, and resource targets hold in rendered LIVE. Declare freshness and fairness limits before the LIVE trial, using the solo runs and task requirements. Publish the measured combination of observer count, sensor profile, renderer preset, and inference load that passes. If three observers exceed capacity, retain that result and identify the first exhausted resource before tuning rates or extending the stack.

## Project references

- [HORIZON Sensory Layer Operational Atlas](sources/horizon/SOMA_HORIZON_Sensory_Layer_Operational_Atlas_v0.2.md)
- [ΔP Math and Control Addendum](sources/horizon/SOMA_HORIZON_DeltaP_Math_Control_Addendum_v0.2.md)
- [RANGE scope and gates](RANGE_V0_SCOPE.md)
- [Inference strategy](INFERENCE_STRATEGY.md)
- [Decisions and approval status](DECISIONS.md)
