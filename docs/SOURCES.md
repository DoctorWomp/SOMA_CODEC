# Source Index

Every design document in this repository, with its date, track, status and what replaced what.
Dates come from inside each document, not from file timestamps.

## How to use this index

**Precedence when documents disagree** (highest first):

1. **Non-negotiable rules:** host-owned physical safety, privacy and disclosure scopes, honest labels for simulated data, no affect or sincerity verdicts about people. These appear in every current document.
2. **[DECISIONS.md](DECISIONS.md):** approved decisions override any source document.
3. **CANON** documents (below): build from these.
4. **SUPPORTING** documents: current thinking, used for detail and background.
5. **SEED** documents: early ideas. Use them for vocabulary and inspiration only. Their superseded parts are listed below and must not be implemented.
6. **REFERENCE**: lateral context, not part of the build.

Within the same status, the **newer document wins**.

Status key: **CANON** = build from this · **SUPPORTING** = current, secondary · **SEED** = early idea, partly superseded · **REFERENCE** = lateral context.

## The four tracks

The material covers three projects that share one social core:

| Track | What it is | Folder |
|---|---|---|
| **RANGE** | Simulated expo test environment for building and A/B testing HORIZON. **First build target.** | `sources/range/` |
| **HORIZON** | The L0–L8 sensory and interpretation layers | `sources/horizon/` |
| **Social core** | Privacy, disclosure, setting rules and de-escalation, shared by all tracks | `sources/social-core/` |
| **Chatbot tier** | Tier 1 text-only expression rules | `sources/chatbot-tier/` |
| **BET hardware** | The physical expression module, audio and MIDI, CDC origins | `sources/bet-hardware/` |
| **Reference** | Lateral context | `sources/reference/` |

## Three eras

| Era | Dates | Character |
|---|---|---|
| 1. Origin | Jul 6 – Aug 5, 2026 | Ambitious scope. Reads emotions, sincerity and threat directly. Hard latency claims. |
| 2. Reframing | Oct 5 – Oct 20, 2026 | Same vision with "observable ≠ inferred", no stored person labels, host owns safety. |
| 3. Build spec | Oct 31 – Nov 12, 2026 | Testable contracts, gates, A/B design. |

The direction across all three is consistent: **keep the structure and vocabulary, drop judgments about people.**

---

## CANON

| Document | Date | Covers |
|---|---|---|
| [SOMA_RANGE_Master_Build_Blueprint_v1.0](sources/range/SOMA_RANGE_Master_Build_Blueprint_v1.0.md) | 2026-10-31 | RANGE build spec: architecture, Godot/Python ownership, maps, cast, COMMS, wire contracts, scenarios S001–S010, tests T01–T30, gates G0–G7 |
| [SOMA_HORIZON_Sensory_Layer_Operational_Atlas_v0.2](sources/horizon/SOMA_HORIZON_Sensory_Layer_Operational_Atlas_v0.2.md) | 2026-11-12 | **Newest.** Plain-language and engineering guide to L0–L8: what each layer does, quantifies, outputs, fails at, and a RANGE test per layer. Observation contract `horizon.observation.v0.2`. Ablation ladder A0–A6. |
| [SOMA_HORIZON_DeltaP_Math_Control_Addendum_v0.2](sources/horizon/SOMA_HORIZON_DeltaP_Math_Control_Addendum_v0.2.md) | 2026-10-31 | Canonical math: typed ΔP, salience `S`/coverage `Q`, social cost field, output smoothing, CDC as compute scheduling, acceptance checks |

Note: the Operational Atlas references an image `assets/horizon_layer_atlas_concept_01.png` that was not supplied. The closest available art is in [concept-art/](concept-art/).

## SUPPORTING

| Document | Date | Use it for | Superseded parts |
|---|---|---|---|
| [SOMA_RANGE_Agent_Runtime_Communication_Blueprint_v0.2](sources/range/SOMA_RANGE_Agent_Runtime_Communication_Blueprint_v0.2.md) | ~late Oct 2026 | Detail on agent runtime, RCC memory tiers, scheduler, COMMS mechanics | Mostly absorbed into Blueprint. Uses `SERVER` channel name (now `PA`, see D-07). Python-first world authority is a phase-0 idea only (D-04). |
| [SOMA_RANGE_HORIZON_Design_Assessment_v0.1](sources/range/SOMA_RANGE_HORIZON_Design_Assessment_v0.1.md) | 2026-10-20 | Rationale: P0 corrections, experimental controls, "prove it in a tiny world first", pilot metrics, evaluation anti-patterns | Cluster numbering RG-01..10 retired (D-02). |
| [SOMA_RANGE_Avatar_Foundry_Scaffold_v0.1](sources/range/SOMA_RANGE_Avatar_Foundry_Scaffold_v0.1.md) | 2026-10-17 | Avatar composition, embodiment sliders vs hard capability flags, physics fidelity P0–P3, collision channels | R1/R2 in the **same** world as the main A/B is replaced by one robot per isolated world. |
| [SOMA_HORIZON_DeltaP_Concept_Spec_v0.1](sources/horizon/SOMA_HORIZON_DeltaP_Concept_Spec_v0.1.md) | 2026-10-16 | Original HORIZON vocabulary and naming, operating rules, scenarios A–D, Tier 3 vs 4 behavior | ΔP formula multiplying by quality `q` is retired (D-11). |
| [SOMA_Codec_Situational_Tier_Protocols_v0.1](sources/social-core/SOMA_Codec_Situational_Tier_Protocols_v0.1.md) | 2026-10-11 | **Social core.** Settings A/B/C, CDC templates' social meaning, confidence protocol (public / group / one-to-one / sealed), "overheard is not told", earshot rule, de-escalation moves, AIMD rate limiting | Hard latency figures are ballpark only. |
| [SOMA_Codec_Chatbot_Tier_Expression_Spec_v0.5](sources/chatbot-tier/SOMA_Codec_Chatbot_Tier_Expression_Spec_v0.5.md) | 2026-10-05 to 10-15 | Six design principles, repair protocol, three-axis humor read, **COMMIT / LEAN / HELD_OPEN**, six-swatch public palette, reaction lanes → Beacon keyframes (A2.9), incongruence ≠ hostility (A6) | Meme and comic reading (A1, A3–A5, A8) applies to the chatbot track, not RANGE v0. |
| [SOMA_BET_ADC_DAC_MIDI_Buffer_Atlas_v0.1](sources/bet-hardware/SOMA_BET_ADC_DAC_MIDI_Buffer_Atlas_v0.1.md) | 2026-11 | Hardware track: analysis windows vs callback size, BET typed control bus, MIDI as an optional adapter, "four separate loops" | Not needed for RANGE v0. Referenced images not supplied. |
| [BET_Module_Concept_Note_v0.1](sources/bet-hardware/BET_Module_Concept_Note_v0.1.md) | 2026-10-06 | Hardware track: the module puck, host/module split, persona continuity, latency budget | Not needed for RANGE v0. |

## SEED

Use for ideas and vocabulary only. **Do not implement the listed superseded parts.**

| Document | Date | Still useful | Superseded (do not implement) |
|---|---|---|---|
| [SOMA_HORIZON_Foundational_Measurement_Metrics_Concept_v0.1](sources/horizon/SOMA_HORIZON_Foundational_Measurement_Metrics_Concept_v0.1.md) | undated (earliest HORIZON) | 14 families of signals; the common vector envelope; "observable field vs interpretive field" | Affective inference field (calm/aggressive…), color = emotional valence, "social pressure" scalar |
| [SOCIAL_GEOMETRY_ENGINE_v0.1](sources/social-core/SOCIAL_GEOMETRY_ENGINE_v0.1.md) | 2026-08-03 | Contextual integrity framing, perceptual horizon, context classifier, disclosure gate structure, anonymous-by-default identification table | Trust score (SARS), trait baseline, "sincerity detection", fixed proxemic radii as rules (D-17), "diplomatic buffer" phrases that reveal a secret exists (D-12) |
| [RELATIONAL_LEDGER_SPEC_v0.1](sources/social-core/RELATIONAL_LEDGER_SPEC_v0.1.md) | 2026-08-03 | Public / semi-public / private buffers, information items with owner, origin context and recipients, disclosure gate | `trust_score` and its update rules, `trait_baseline`, `power_delta`, `conflict_history` (D-13) |
| [CDC_MODE_SWITCHING_ARCHITECTURE_v0.1](sources/bet-hardware/CDC_MODE_SWITCHING_ARCHITECTURE_v0.1.md) | 2026-07-06 | Identity anchor always resident, context slices per mode, pre-load the likely next mode, bounded interaction window (ancestor of RCC) | Threat Vector Composite, deception channel CC 4, `<1 ms` threat interrupt in the social layer, Sovereignty Defense triggered by deception scores (D-09) |
| [BUFFER_LATENCY_REFERENCE](sources/bet-hardware/BUFFER_LATENCY_REFERENCE.md) | 2026-07-07 | Buffer latency math and perception thresholds | Smaller audio buffer per more urgent CDC mode (rejected by BET Atlas, Plate 05) |
| [SPATIAL_SENSING_RESEARCH](sources/bet-hardware/SPATIAL_SENSING_RESEARCH.md) | 2026-07-06 | Phase 1/2 mic and depth hardware ideas; informs how realistic the simulated Echo layer should be | — |
| [SOMA_EXPRESSION_MODULE_v0.1](sources/bet-hardware/SOMA_EXPRESSION_MODULE_v0.1.md) | 2026-08-03 | ASCII face lexicon (Beacon keyframes), light → face → voice timing order, hardware cost tiers, cultural color overrides | Mehrabian 7/38/55, `sincerity_score`, `human_emotional_state`, "truth plane", red = hostile, random-strobe mischievous mode (D-14) |
| [BET_LEXICON_v0.1](sources/bet-hardware/BET_LEXICON_v0.1.md) | 2026-08-05 | Large **output** vocabulary: emoji, ASCII, color, intensity, pulse rate for what the robot shows | Tier 5 alignment matrix and toxic-personality "detection" for profiling or threat assessment (D-13); `STROBE` ≥ 8 Hz (D-14). Reading people's emotions with it is superseded. |

## REFERENCE

| Item | Notes |
|---|---|
| [MVSB_CORE_PROMPT_COMPACT_v1.4](sources/reference/MVSB_CORE_PROMPT_COMPACT_v1.4.md) | A test-environment prompt to help an AI reason conversationally. Origin of the forgetting kernel, Atonement Vector (→ repair protocol), A vs B constraints, Pedestrian Permission. Its "Delta P" is a different quantity from HORIZON ΔP (D-08). |
| [The Soul Accord](https://doctorwomp.com/soul_accord) | Author's independent philosophical research. Lateral, not focal for this build. |
| [PAE — Perception Attribution Error](https://doctorwomp.com/pae) | Author's research series. Close in spirit to HORIZON's source-attribution and uncertainty work (Echo, Haze). Uses "CDC" to mean *Context Differentiation Capacity* (D-08). |
| [PAE Part 2 — Fictional AI case studies](https://doctorwomp.com/pae_part_2/) | "Graceful error" (error ≠ existential threat) → repair protocol; "does my response create the threat?" → measuring robot-caused escalation (RANGE_V0_SCOPE §5.1). |
| [PAE Part 3 — Formal definition](https://doctorwomp.com/pae_part_3/) | PAE = correct perception assigned to the wrong context; context spillover; the "person on the ground" three-context example → scenario S011. |
| [PAE Part 4 — Three Doors](https://doctorwomp.com/pae_part_4/) | Same signal, different containers. Three outcomes: low, high and **inverted** (confidently wrong) context differentiation → S011 scoring. Context Inversion Pressure (exploiting empathy to bypass protections) → S012. |
| [PAE Part 6 — Contextual Superposition Defense](https://doctorwomp.com/pae_part_6/) | Holding several readings open instead of collapsing early → Prism `HELD_OPEN`, premature-collapse metric. Containment below the "doxing line" → private escalation, never public exposure (D-12). |
| [PAE Part 7 — Humor as a CDC metric](https://doctorwomp.com/pae_part_7/) | Benign violation needs correct context; metrics: humor not flagged as attack, urgency not always read as emergency, repair after a missed joke. Clinical sections are not ported (no pathologizing, D-13). |
| [PAE Part 8 — Covenant Ledger](https://doctorwomp.com/pae_part_8/) | Commitments + refusals + source trust hierarchy + compression policy → commitments survive memory compaction; trust attaches to evidence, not people (D-13); promise follow-through → S013. |
| [PAE Part 10 — Sigil Protocol](https://doctorwomp.com/pae_part_10/) | One-line capability disclosure ("declare the spectrometer") → each avatar's **capability card** in the viewer and run manifest (RANGE_V0_SCOPE §2.4). |

## Concept art

Illustrations only. **Numbers shown in the art (confidence scores, rates, percentages) are illustrative, not specifications.** Known disagreements with the written rules are listed in D-10 and D-14.

| Image | Shows |
|---|---|
| [horizon_L0-L1_foundation_stack](concept-art/horizon_L0-L1_foundation_stack.webp) | Anchor and Halo: sensors, SLAM, occupancy, coarse saliency |
| [horizon_L2-L3_interaction_input_stack](concept-art/horizon_L2-L3_interaction_input_stack.webp) | Echo and Wake: mic array, pose tracking, gesture |
| [horizon_L4-L5_social_navigation_stack](concept-art/horizon_L4-L5_social_navigation_stack.webp) | Focus and Contour: attention lobes, target ranking, queues, social cost map |
| [horizon_L6-L8_interpretation_stack](concept-art/horizon_L6-L8_interpretation_stack.webp) | Prism, Haze, Trail: hypotheses, uncertainty, temporal context, confidence bands |
| [runtime_orchestration_cdc_bet_horizon](concept-art/runtime_orchestration_cdc_bet_horizon.webp) | Runtime dataflow, ROS2 topics, CDC modes |
| [range_expo_hall_v0.1_top_down](concept-art/range_expo_hall_v0.1_top_down.webp) | **Reference layout for Expo Hall A** (48 × 32 m, booths A–F, matches Blueprint §5) |
| [range_expo_robot_r_concept](concept-art/range_expo_robot_r_concept.webp) | Visual target and prop categories for the expo |
| [range_expo_multi_floor_variant](concept-art/range_expo_multi_floor_variant.webp) | Future multi-floor map (deferred) |

## Referenced but not in the repository

These are cited by the documents above but were not supplied. None blocks RANGE v0.

- ACCORD MIDI SPEC v0.2 (source of CC channel numbers)
- Diplomacy Protocols D-1
- Intent Triangulation Research
- B-Bus brief v3.2.6, Covenant Ledger
- SOMA HORIZON Systems Atlas and BET Module Form Factor Atlas, and the BET Atlas plate images
- FORGE, AI Alignment, SIGINT + COMSEC, and AI + Robotics R&D briefs
- Earlier-phase code mentioned in SEM: `prosody_extractor.py`, `escalation_engine.py`

## External tools and research

| Item | Relevance |
|---|---|
| [OpenRoboKit / RoboKit](https://github.com/openrobokit/robokit) (MIT, Python) | Motor-skill toolkit: IK, motion planning, retargeting, grasping, locomotion, RL. The "do task" half that BET would sit on top of. Relevant at physics fidelity P2+ or real-robot integration, not RANGE v0. |
| Social navigation simulators: [Arena 3.0](https://arxiv.org/pdf/2406.00837), [SocialGym 2.0](https://arxiv.org/pdf/2303.05584v1.pdf), [SEAN](https://pdf.arxiv.org/pdf/2103.00047), [Social-Navigation-PyEnvs](https://www.github.com/TommasoVandermeer/Social-Navigation-PyEnvs), [CrowdSim++](https://scitepress.org/Papers/2025/131923/131923.pdf) | Overlap mainly with L5 Contour. Borrow crowd motion models (Social Force, ORCA) for background walkers, and their social-navigation metrics so L5 results can be compared with published work. |
| [PR DoctorWomp/SOMA_CODEC#1](https://github.com/DoctorWomp/SOMA_CODEC/pull/1) | Earlier scaffold written without the Blueprint. Not merged. Parts salvaged per D-18. |
