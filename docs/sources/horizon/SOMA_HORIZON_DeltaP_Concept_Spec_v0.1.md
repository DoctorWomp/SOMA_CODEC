# SOMA HORIZON ΔP — Adaptive Multimodal Spatial-Prosodic Perception

**Concept specification v0.1 · 16 October 2026 · SOMA Codec / BET (Bi-Directional Emotional Transduction)  Research**  
**Target:** Tier 3 (trusted embodied space), Tier 4 (mixed-public space, e.g., robotics expo)  
**Status:** Research proposal, not a validated sensing, affect-recognition, safety, or performance specification.

> **Working thesis:** A robot's useful “personal-space bubble” is not a fixed radius. It is a dynamically shaped, robot-centered perceptual horizon that represents *what is observed, where it is observed, how it changes relative to context, what it might mean, and how uncertain that interpretation remains*.

## 1. Identity and naming

**Preferred formal name:** **SOMA HORIZON ΔP**  
**Descriptor:** Adaptive Multimodal Spatial-Prosodic Perception System  
**Working nickname:** **the Halo**  
**Field:** **Horizon Field**  
**Changes in field:** **ΔP events** (“delta-pressure” events; normalized context-relative changes, not physical pascals)  
**Selective higher-detail regions:** **Focus Lobes**  
**Diagnostic visualization:** **Halo HUD**  
**Nonverbal and expressive output:** **Beacon** (the DAC side; distinct from sensing)

HORIZON ΔP extends the SOMA Social Geometry Engine (SGE) and interoperates with CDC, the Relational Ledger, and the BET expression module. It does **not** replace the chassis's navigation, collision avoidance, or emergency controller.

### Alternative names worth keeping in the naming pool

| Name | Character / possible use | Caution |
| --- | --- | --- |
| **SOMA HORIZON ΔP** | Most precise research/system name | The ΔP notation needs a definition |
| **SOMA HALO** | Memorable operator/UI name | “Aura” interpretations need guarding against |
| **SOMA PARALLAX FIELD** | Multiple perspectives, same scene; connects to BET Parallax terminology | Less immediately spatial |
| **SOMA NIMBUS** | Variable, layered cloud around the chassis | Slightly atmospheric rather than engineering-oriented |
| **SOCIAL SONOSPHERE** | The spatial-spectrogram visual metaphor | Undersells visual, tactile, and contextual channels |
| **SOMA PERCEPTUAL HORIZON** | Clear academic/technical presentation | Less distinctive |

**Recommended split:** use **HORIZON ΔP** in specifications, **Halo** in conversation, and **Halo HUD** for a visualization or AR overlay.

## 2. Scope, goals, non-goals

**Goal:** Give a BET-equipped robot a continuously updated, egocentric, confidence-aware model of nearby people, activities, conversation bids, physical geometry, and changes in multimodal expressive cues. Support *appropriate interaction timing and legible responses*, including recognition of when **not** to speak.

**In scope:** timestamped microphone-array data; multi-camera/depth data; proximity/range information; gestures and posture; host-provided pose/motion state; local conversational context; transient scene and group models; relative cue changes; uncertainty; operator-facing HUD; bounded advisory cues to expression and to the host.

**Out of scope:** reading private feelings as facts; deception or dangerousness detection from body language; estimating psychiatric/physiological state from ordinary social cues; unconsented recognition/profiling of bystanders; a direct motion-command or force path; assuming the HUD is an objective depiction of anyone's emotions.

### Operating rules inherited from SOMA

1. **Relative, not absolute:** changes against an appropriate person/session/environment baseline matter more than raw intensity.
2. **Situation before person:** explain apparently anomalous behavior through context before assigning motive.
3. **Decode the what; read the how; never grade the how:** delivery tunes interaction, not a person's worth or trustworthiness.
4. **Multiple hypotheses:** apparent mismatch can be joking, performance, error, ambiguity, or unknown—not automatically hostility.
5. **No invented certainty:** show the difference between measured, inferred, predicted, and unknown.
6. **Contextual integrity:** who can hear or see a reply is as important as what the robot knows.
7. **Respect remains constant:** adaptive sensing may change pacing and attention, never basic dignity.
8. **Human safety belongs to the host:** HORIZON gives social advisories; the host independently owns physical safety.

## 3. Architecture at a glance

```text
MIC ARRAY / RGB + DEPTH / RANGE / IMU + HOST POSE / TASK CONTEXT
                          │
                    MULTIMODAL ADC
             features + source + timestamp
                          │
           TIME SYNC / CALIBRATION / DATA QUALITY
                          │
              SOURCE AND EVENT ASSOCIATION
            (who/what/where; with ambiguity)
                          │
          EGO-CENTRIC GEOMETRY / TEMPORAL TRACKING
                          │
       ΔP ENGINE: CONTEXT-RELATIVE FEATURE CHANGES
                          │
              HORIZON FIELD (typed layers)
      HALO · ECHO · WAKE · FOCUS · CONTOUR · PRISM
               HAZE (uncertainty) · TRAIL
                          │
     ┌────────────────────┴──────────────────────┐
     ▼                                           ▼
  HALO HUD                               SOCIAL RESPONSE ADVISOR
  internal diagnostic / optional AR       turn timing / attention / expression
                                                 │
                                           BET MULTIMODAL DAC
                                         face / ARGB / voice / gesture request
                                                 │
                                 HOST CONTROLLER (can refuse requests)
                                independent motion + safety authority
```

The diagnostic HUD and the robot's publicly visible ARGB/face palette are **different codebooks**. An orange area in an engineering display should not automatically make the robot glow orange or signal that a person is a threat.

## 4. The layered Halo: working vocabulary

The **Halo** is a *rendering* of multiple data layers, not one magical all-purpose emotion scalar. A spherical shell makes 360° coverage easy to view, but the underlying map is a multi-resolution 3D field, deformed by physical geometry and attention.

| Layer | Short name | Function | Typical inputs | Representative display |
| --- | --- | --- | --- | --- |
| **L0 — ANCHOR** | **Origin** | Robot pose, local X/Y/Z frame, clock and self-motion correction | IMU, odometry, SLAM/host pose | Axes, compass, motion origin |
| **L1 — HALO** | **Horizon** | Coarse omnidirectional occupancy and event awareness | Cameras, depth, range, sound activity | Transparent blue spherical/coarse shell |
| **L2 — ECHO** | **Resonance** | Acoustic direction and vocal-prosodic activity, separated from ambient reflections where possible | Array time delays, beamforming, VAD, pitch and spectral features | Directional ripples and time-frequency ribbons |
| **L3 — WAKE** | **Motion** | Movement, gesture, trajectory, and event after-effects | Visual pose/optical flow, depth tracking, touch if present | Trails, vector arrows, kinetic lobes |
| **L4 — FOCUS** | **Lobes** | Higher-resolution sensing around active speakers, possible bids, and task-relevant objects | Source tracks, gaze/head orientation, pointing, dialogue state | Adaptive cones/petals near salient participants |
| **L5 — CONTOUR** | **Boundary** | Physical obstacles, proxemic margins, group geometry, and occupancy-sensitive approach buffers | Geometry, flow, interaction roles, consent/context | Deformed contours around people, walls, booth edges |
| **L6 — PRISM** | **Context gate** | Holds alternative explanations and modulates social relevance | Current task, discourse, situation, event history | Symbolic labels: `PLAYFUL?`, `BID?`, `NOT ADDRESSED`, `UNKNOWN` |
| **L7 — HAZE** | **Uncertainty** | Coverage, occlusion, conflicting observations, source ambiguity, calibration limits | Sensor health, triangulation disagreement, track loss | Transparency/texture/hatching; never solely hue |
| **L8 — TRAIL** | **Memory of motion** | Short time-window history, onset, decay, transitions, conversational turn changes | Timestamped field snapshots | Fading wakes / waterfall-like temporal ribbons |

**BEACON** is the separate outward *DAC expression bus*—voice, face, ARGB, and optional gesture/haptics—not a sensing layer. It receives a bounded response plan from the social advisor.

### Geometry is intentionally not spherical at every scale

- **Coarse outer shell:** sparse 360° bearings and broad confidence/occupancy bins; retain explicit unobserved sectors.
- **Near-field contours:** dense depth and motion geometry for nearby people/objects; surfaces bend around obstacles and conversations.
- **Focus lobes:** narrow, higher-fidelity sensing regions around direct participants and candidate bids.
- **Temporal tails:** recent evidence decays rather than vanishing when tracking pauses.
- **Occlusion voids:** do not paint a hidden area as known merely because a glossy sphere looks complete.

No fixed “personal bubble radius” is universally valid. Relative distances, visible boundary signals, crowding, accessibility, relationship, task, cultural norms, and explicit requests affect the *advisory* social contours. A robot's physical collision margins remain controlled independently.

## 5. ΔP: a pressure metaphor with precise limits

For each measurable cue channel `k`, define a **context-relative deviation**:

```text
ΔP_k(t) = q_k(t) × clip[(x_k(t) − b_k(c, s, t)) / scale_k(c, s), −M, +M]
```

Where:

- `x_k(t)` is an observed feature (e.g., normalized loudness, relative approach speed, speech rate, gesture rate).
- `b_k(c,s,t)` is a *provisional* baseline for current context `c` and source/session `s`.
- `scale_k` is a robust reference variability estimate or engineering normalization, not a universal human threshold.
- `q_k` expresses the signal's data quality/reliability; `M` limits outlier influence.
- If baseline or source attribution is unavailable, leave the relative reading **unknown** or use a clearly marked environment-level comparison; do not invent a person's baseline.

The notation is **not sound-pressure pascals**, a calibrated emotion meter, or EEG band detection. Some features are categorical (e.g., “turn yielded”), and should remain events, not be forced through this numerical expression.

**Crucial design decision:** keep a **typed vector** `ΔP = {acoustic, kinetic, proximity, attention, temporal, ...}` instead of collapsing it immediately into one “emotional pressure” score. High loudness plus a smile can suggest excited levity; high loudness plus sudden approach may suggest urgency; neither establishes malicious intent. The **PRISM** layer proposes possible contextual readings and preserves uncertainty.

### One possible field data model

```text
H(azimuth, elevation, radius, time) = {
  occupancy,       acoustic_activity,     visual_motion,
  gesture_activity, attention_bid,        conversational_role,
  boundary_context, candidate_meanings[], uncertainty,
  observed_sources[], timestamp,          coverage_state
}
```

Different layers may use different resolutions and update cadences. This field is a useful *internal representation*, not a requirement to compute every quantity at every voxel.

## 6. Multimodal feature families

| Family | Candidate observations | Important qualifier |
| --- | --- | --- |
| **Acoustic** | SPL/loudness proxy, F0 contour, cadence, onset, pause, VAD, spectral energy, direct/reverb ratio | Echoes and announcements can be falsely assigned to people |
| **Localization** | Azimuth/elevation, array delays, beamformer direction, track motion, range estimates | Sparse arrays may not resolve elevation or distance reliably |
| **Visual / kinematic** | Depth, body/face orientation, pose, gesture, pointing, gaze proxy, approach, occlusion | Appearance is not a reliable measure of intention or emotion |
| **Proxemic** | Relative distance, velocity, interpersonal spacing, group formation, passage corridors | People need different margins and consent norms |
| **Tactile / chassis** | Contact events, vibration, robot articulation/IMU, actuator/self-noise | Contact detection does not explain why contact occurred |
| **Semantic / discourse** | Addressed words, turn-taking, references, explicit invitation or refusal, current task | Speech meaning needs context; overheard speech is not permission to use it |
| **Ambient** | Crowd motion/noise, PA announcements, exhibit robots, geometry and light changes | Context can dominate the raw feature values |
| **Provenance / control** | Time sync, consent, sensor status, source confidence, audience visibility | Uncertainty and permission are first-class data |

## 7. Proposed observation packet and social event schema

```yaml
observation_id: obs_0172              # Example only; synthetic
frame: chassis_local_xyz
measured_at_ms: 172000                 # Monotonic relative timestamp
source_modality: [audio_array, rgbd]
source_track: anonymous_ephemeral_02
position_m: {x: -1.3, y: 1.4, z: 0.0}
geometry_status: partially_observed
observed:
  speaking: false
  head_orientation_toward_robot: intermittent
  relative_approach: stable
  body_orientation_toward_group: likely
  turn_status: current_speaker_is_other_person
relative_delta:
  attention_cues: rising
  vocal_intensity: unavailable
interpretations:
  - {hypothesis: possible_bid_to_join, evidence: [orientation, repeated_glance]}
  - {hypothesis: watching_demo, evidence: [expo_context]}
read: held_open
confidence_status: provisional_uncalibrated
privacy_scope: public_venue_ephemeral
suggested_response: preserve_active_speaker_and_offer_low_pressure_opening_later
```

The schema deliberately separates **observations**, **deltas**, **hypotheses**, and **permitted actions**. The identifiers, coordinates, and example values are synthetic; they are not empirical thresholds.

## 8. Update loop and adaptive allocation

```text
FOR each sensor interval:
    acquire timestamped observations + host pose + current task
    remove or tag robot self-noise; estimate sensor quality
    align time and coordinate frames
    associate events with anonymous tracks, or leave association unknown
    update coarse Halo coverage + geometry
    update ECHO/WAKE features and relative deltas where justified
    allocate FOCUS detail to current speaker, event, or repeated social bid
    update CONTOUR using geometry and situational etiquette
    let PRISM maintain 2–3 plausible meanings when needed
    propagate HAZE into any uncertain interpretation
    decay TRAIL history; apply hysteresis to noisy social changes
    publish diagnostic Halo HUD
    propose bounded DAC/social response; obtain host consent for any motion
```

**Adaptive sensing budget:** keep the outer field cheap; spend additional compute on task-relevant areas and new changes. Avoid *tunnel vision*: occasional broad sweeps preserve peripheral coverage. When sensors degrade, reduce precision/claims and increase explicit uncertainty rather than fabricating continuity.

**Timing:** existing SOMA situational drafts discuss approximately 10–20 Hz social read updates and fast face/light reactions. These are **research starting points**, not guaranteed rates for HORIZON ΔP. Sensor acquisition, tracking, fusion, display, and reaction end-to-end latency need independent measurement on target hardware.

## 9. Scenario protocol: expo and mixed-public space

### Scenario A — current conversation and a shy side bid

**Observed:** Robot is talking with Person X. Person Y is to the side, at a stable distance, intermittently orienting toward the robot, without speaking.  
**Halo:** X gets the dominant Focus Lobe; Y gets a small provisional green *operator-only* bid marker; the crowd remains low-resolution background.  
**PRISM hypotheses:** Y might want a turn; Y might be watching the demonstration; intent remains held open.  
**Conduct:** Do not interrupt X, label Y “shy,” or publicly announce an inference. At a natural conversational opening, a subtle inclusive gaze/face cue or a neutral question to the group may invite participation **without pressuring Y**. If Y does not engage, let the bid decay. In a public space, unsolicited approaches remain off by default.

### Scenario B — loud absurdity mistaken for hostility

**Observed:** A nearby group is laughing, shouting, gesturing and acting out an absurd scenario. ECHO and WAKE show elevated activity.  
**PRISM check:** Context is recreational; group cues and verbal content are consistent with performance or levity; no grounds for a hostility verdict.  
**Conduct:** Maintain suitable physical spacing and normal social rhythm. Do not classify a person as aggressive because a pressure visualization turned orange/red. If the robot is addressed, respond in the appropriate register.

### Scenario C — reflection, occlusion, and source disagreement

**Observed:** An announcement echoes off a booth wall behind the robot while a nearby attendee is silent.  
**HAZE:** Acoustic origin has competing hypotheses; ray paths disagree with visible speakers.  
**Conduct:** Render uncertain acoustic direction rather than attributing speech or emotional intensity to the attendee. Prefer clarification if the robot needs to act conversationally.

### Scenario D — privacy boundary changes mid-sentence

**Observed:** A stranger enters earshot while a private colleague discussion is underway.  
**CONTOUR + PRISM:** Audience scope changes; contextual-integrity check activates.  
**Conduct:** Narrow or pause sensitive output without disclosing that a secret exists. The public DAC signal stays neutral and low-key.

## 10. Halo HUD visual grammar (candidate)

The HUD is for *operators and debugging*, unless a separately vetted AR accessibility mode is enabled.

| Visual primitive | Encodes | Caution |
| --- | --- | --- |
| **Angular region / lobe** | Source direction and focus allocation | Focus is not endorsement or suspicion |
| **Radius / contour** | Physical range or contextual spacing band | Avoid implying a measured personal preference |
| **Brightness** | Observable activity magnitude or relevance | Intensity is not hostility |
| **Ripple frequency / trail** | Change rate and history | “FFT-like” is a visualization analogy for non-audio signals |
| **Hatching / translucency** | Incomplete coverage and uncertainty | Use patterns as well as color for accessibility |
| **Arrow / vector** | Measured or estimated approach / direction | Prediction marked separately from observation |
| **Text badge** | `OBSERVED`, `INFERRED`, `HELD OPEN`, `NO DATA` | Do not publish private social diagnoses |

**Color proposal for internal diagnostics:** blue = baseline/coverage; green = candidate cooperative attention; yellow/orange = elevated activity; red = engineering limit/event priority (not a “bad person”); violet = alternate hypotheses; gray/hatching = missing data. This **must not be confused** with the six-state user-facing expression palette from Chatbot Tier v0.5, where red has a firm-boundary meaning, violet means considered respect, and colors accompany plain words.

**Never conflate axes:** spatial angle ≠ spectral frequency; strong color ≠ statistical certainty; high acoustic amplitude ≠ emotional intensity; a signed ΔP ≠ moral judgment.

## 11. Tier 3 vs Tier 4 behavior

| Dimension | Tier 3: trusted space | Tier 4: public expo |
| --- | --- | --- |
| Identity | Introduced/opt-in familiarity possible | Anonymous by default; explicit opt-in before recognition |
| Context | Longer cooperative task, known codebook | Rapid audience turnover; high ambiguity |
| Focus | Richer group-aware conversational cues | Brief, minimally identifying event tracks |
| Baselines | Consensual session-specific adaptation | Environment-relative and short-lived session adaptation; no bystander profiling |
| Disclosure | Group and one-to-one scopes both enforced | Restrict to least-trusted person within earshot |
| Expression | More nuanced agreed signals | Simple, legible, conservative DAC |
| Bids to interact | Natural invitations can be familiar | Wait for sufficiently clear engagement; no unsolicited solicitation |
| Persistence | Only what was authorized under ledger rules | Drop ephemeral social tracks promptly; minimize retained sensor data |
| Robotics | Host retains all physical authority | Same; stronger robustness and privacy defaults |

## 12. Interfaces and boundary enforcement

**Host → HORIZON:** pose, velocity, task, safety state, permissible sensing modes, environment geometry when available.  
**HORIZON → Social advisor:** typed observations and uncertainty-aware proposals (e.g., *speaker is probably to rear-left*, *possible turn bid*, *audience changed*).  
**Advisor → BET DAC:** permitted expressive plan (listen, wait, glance, speak briefly, neutral light, quiet acknowledgment).  
**HORIZON / advisor → Host:** *requests*, such as orient camera toward a likely speaker or slow approach for social comfort. The host can ignore or reject any request. **No direct motor actuation or emergency response from HORIZON.**

**Privacy and safety floor:** no inferred anger/dishonesty/threat labels on persistent person records; no continuous raw recording by default; visible consent controls; public-venue bystanders are not enrolled; third-party speech does not grant disclosure rights; no covert psychological targeting or engagement-maximization; physical hazards handled by the host safety stack.

## 13. Human augmented-reality variant

A wearable version can render a **sparse** human-centered Halo—direction of addressed speech, off-axis turn bids, crowd activity, or obstacle context—for opt-in situational assistance or HRI debugging. It must suppress speculative emotion labels, keep confidence visible, avoid recording bystanders unnecessarily, and be evaluated for attention overload, accessibility, privacy, and user consent. It is **not** a social lie detector or thought-reading aid.

## 14. Build path and validation gates

| Phase | Deliverable | Minimum validation |
| --- | --- | --- |
| **0 — Synthetic Halo** | Animated 3D shell driven by scripted XYZ/signal events | Fields and unknown regions render accurately; no false sensor claims |
| **1 — Geometry + audio** | Host pose, range/depth, mic-array direction, source uncertainty | Angular error, echo/multipath confusion, latency and dropouts |
| **2 — People and turns** | Anonymous short-lived tracks, coarse gestures, active speaker and possible bid | False speaker association, missed bids, unwanted interruptions |
| **3 — Context + ΔP** | Provisional baselines, alternative interpretations, absurdity/levity tests | False hostility attribution; correction quality; calibration under shift |
| **4 — BET DAC integration** | Conservative glance/face/light/voice responses | Human-rated respect, clarity, nuisance, consent, repair |
| **5 — Expo trial** | Instrumented and consent-aware controlled public pilot | Privacy failures, crowd interference, bystander effects, robustness |
| **6 — AR research** | Optional sparse headset view | Comprehension, overload, access needs, privacy impact |

**Candidate measurements:** localization angular error; track continuity; detection/false-positive rates of conversational bids; context-repair turn latency; calibration of uncertainty; time-to-first appropriate nonverbal cue; human-rated intrusion and perceived respect; CPU/GPU/battery cost; lost-frame and acoustic-multipath resilience; privacy/disclosure violations; host-rejected motion requests. No target values are claimed until an experimental setup exists.

## 15. Open design questions

- Is the underlying map best implemented as multi-resolution spherical bins, voxels, tracked objects with radial kernels, or a hybrid?
- What information belongs in each layer rather than duplicated across layers?
- How should uncertainty propagate when vision and audio disagree or are occluded?
- What is an acceptable false-positive rate for a possible conversational bid in public?
- How should the system handle uninstrumented sectors, crowd density, and people who cannot or do not use stereotypical gaze/gesture patterns?
- When can an environment-level reference become a person-specific baseline, and what consent is needed?
- Can human observers reliably understand the Halo HUD without believing the colors are objective emotions?
- Which functions genuinely need 10–20 Hz updates, and which should run event-driven or slower?
- Is a spherical visualization more useful than a simpler polar compass + inset 3D geometry for real operation?

## 16. Relationship to existing SOMA documents

**Inherited architecture / requirements:**
- *SOMA Codec — Chatbot Tier Expression Spec v0.5*: relative baselines; contextual interpretation; A4–A8 visual/temporal/incongruence concepts; honest expression; uncertainty; no manipulation.
- *SOMA Codec — Situational Tier Protocols v0.1*: Tier 3 vs Tier 4 social rules; CDC setting templates; privacy and earshot; restraint in public; candidate read rates.
- *SOCIAL_GEOMETRY_ENGINE_v0.1*: perceptual horizon, contextual classifier, spatial/relational awareness.
- *RELATIONAL_LEDGER_SPEC_v0.1*: information ownership and disclosure boundaries; subject to newer confidentiality restrictions where drafts differ.
- *BET Module — Concept Note v0.1*: chassis/module split; localized sensing/expression; host-only safety control; latency research.
- *CDC_MODE_SWITCHING_ARCHITECTURE_v0.1* and *SPATIAL_SENSING_RESEARCH*: initial contextual templates and directional sensing research seeds, not verified performance guarantees.

**Novel in this document:** the named HORIZON ΔP subsystem; typed multichannel delta-pressure formalism; shape-adaptive multi-layer Halo representation; confidence visualization; explicit focus allocation; social-bid example; staged validation plan. These are proposals requiring empirical testing.

---

**One-line concept:** *The Halo does not tell SOMA what people feel. It helps SOMA track where signals originate, how they change, which explanations remain plausible, and when respectful interaction is appropriate.*

*Research signature: HORIZON ΔP · Perceive → Contextualize → Hold uncertainty → Convey.*
