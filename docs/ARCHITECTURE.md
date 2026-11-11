# SOMA RANGE architecture and scope

## Evidence and status

Baseline repository at `21658df` contained only `README.md` (`# SOMA_CODEC`), preserved as the README heading. No existing app, assets or research documents were replaced.

The available conversation *SOMA Codec Memory Check* (`6ad2caed-a750-83ea-b2d9-92b3519434a5`) describes an Expo world, autonomous Robot R and visitors, RANGE COMMS, HORIZON perception experiments, scoped memory, three user modes and replay. Its retrieved history includes the staged-build discussion and ADC/DAC/MIDI buffer atlas summary. Earlier master blueprints and sandbox-linked PDF/ZIP assets were not available in that history or repository. This document is an explicit implementation starting point, not a reconstruction of missing specifications. Resolve uncertain HORIZON module semantics with the project owner before implementing them.

## Boundaries

Godot 4 owns authoritative world state, physics, navigation, sensory eligibility (distance, occlusion, channel), communication delivery and action validation. Python receives only observations already eligible for the named NPC, maintains private agent memory, invokes future inference adapters and proposes actions. Godot validates actor, tick, permissions and physical feasibility before applying a proposal. The current Godot screen merely displays a stub decision; no physical action is applied.

Planned flow: world event → per-agent sensor filter → attributed observation → HORIZON adapter → agent policy → bounded decision → world action validator → trace. Raw evidence and inferred interpretations remain separate, with confidence and provenance added in a future version. ECHO/WAKE/source fusion and PRISM are names from the chat, not implemented algorithms or settled specifications.

Spectator sees an observatory view but cannot inject agent knowledge. Director can alter scenario conditions through explicitly authorized, logged interventions. Participant controls an avatar through the same world communication and perception rules as NPCs. These permissions must be enforced by the world dispatcher, not by hiding UI controls. The initial screen is a Spectator-labelled harness only.

## HORIZON and communication experiments

A is a baseline adapter; B will add a declared HORIZON treatment over the same eligible inputs. Current A and B are deliberately identical deterministic stubs except for the arm label. No emotion recognition, social-awareness improvement or latency benefit is claimed. Future evaluations use matched scenario/seed, prompt/model revisions, inference parameters, repeated trials and explicit scoring. Avoid privileged inputs in B that A cannot access unless that input difference is the declared experiment.

RANGE COMMS will model addressed/local speech, gesture and environmental channels with range and occlusion. Public visibility means eligible for delivery through world rules; it never means every NPC receives it. Private content is delivered and remembered only for eligible recipients. `source_id: null` is valid and must not become a fabricated identity.

BET capability tiers T0–T4, CDC operating modes 0–5, and ADC buffer sizes are separate axes. Future configurations may measure capture window, feature cadence, queue time, inference time and output latency separately. MIDI is a proposed expressive control namespace, not raw audio transport. ADC/DAC hardware, prosody inference and motor control are outside this scaffold. Any future BET layer remains advisory to host motor/safety authority.

## Memory, privacy and replay

The in-process memory primitive rejects owner/recipient mismatches and exposes owner-scoped reads. It is not authentication: a future dispatcher must derive identity from a trusted session, never an arbitrary caller field. The stateless loopback HTTP harness accepts synthetic observations only and is unsuitable for multi-user or network deployment. It has no persistence, provider access, authentication or browser CORS allowance.

Replay currently validates and hashes ordered recorded decision lists. This proves stable serialization and change detection, not full world replay. Future traces must record initial snapshot, tick rate, scenario hash, world/engine version, inputs, interventions, delivered observations, decisions, prompt/model revisions and RNG streams. Replaying recorded model output is different from rerunning a stochastic model. Cross-platform physics determinism requires separate evidence.

Never export private raw memory in a bug bundle by default. Future F8 bundles need explicit consent/redaction, bounded retention and a manifest of what is included. Correlate observations → decisions → validation/rejection → animation with trace IDs so debugging can locate the failing boundary.
