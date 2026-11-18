# Changelog

All notable changes, by gate. Dates are when the work was done.

## G3d — Closing G3: review fixes and measurement tools (2026-11-18; draft PR)

`docs/gates/G3_PLAN.md` (G3d), D-62 to D-70 PROPOSED, `docs/gates/G3d_OWNER_CHECKLIST.md`. D-60 and D-61 stay PROPOSED until the owner's PC run.

### Fixed (each reproduced first, with a regression test)
- A repair got a fresh deadline, so a decision could outlast the world's 6.5 s stale window: one deadline per decision now covers queue, generation and repair (D-63).
- Answers were sent even when their person had left or someone else had spoken meanwhile: a relevance check drops them before sending, with the reason, and allows the usual single replan (D-63).
- Memory changed when a request was sent, not when the world accepted it: promises, kept promises, the agent's own speech and conversation starts now apply on acceptance only (D-64).
- Pulse metrics counted any decision and "the last gaze target" as responses, and proposals as outcomes: only source-linked, accepted responses count, with 3 s gaze intervals (D-65). This exposed a presence-loop defect (a source glanced at once was never glanced at again), now fixed.
- FN-1 accepted a goodbye said to someone else, or after leaving: the closing line must be audible to the partner and come first, and the departure waits for the world to accept it (D-66).
- The idle budget missed cancelled and pre-empted reviews: it is debited at admission (D-67).

### Added
- Rendered-run frame pacing (`frames.json`, p50/p95/p99, spikes) and peak VRAM sampled during the run; `--resolution`, `--render-preset`; the bake-off's `LIVE_RENDERED` mode and render-tax table (D-69).
- `--no-pulse` (run_scenario, bake-off live), a per-agent `report` in `summary.json`, `tools/compare_runs.py` (D-69).
- SB-09 Soak and `tools/soak.py` (D-70).
- Scheduler job labels (observer, layer, evidence time, deadline, cost) and observer-isolation tests (D-62).

### Changed
- `tools/check.py` runs its scenario runs side by side (D-68).
- Journals: SB-06 and SB-08 changed (more glances, from the presence fix); the fake-model SB-04 and SB-06 changed (the presence fix and the idle debit at admission); SB-04 (Demo) and SB-07 are unchanged. Memory staging, the deadline and FN-1 change no stepped journal (checked by reverting the other two).

### Found, not fixed (owner decision)
- Memory grows linearly with raw heard speech over long runs (D-70 proposes a bound).

## G3c-2 — Usable NPCs, real-time live runs, the pulse protocol (2026-11-17 to 2026-11-18; draft PR)

`docs/gates/G3_PLAN.md` (G3c-2), D-60 and D-61 PROPOSED, `docs/gates/G3c2_OWNER_CHECKLIST.md`. D-59 APPROVED (owner, 2026-11-17); the owner's G3c-1 results recorded in G3_PLAN and D-59.

### Fixed (part A, D-60; each reproduced first, with a regression test)
- MOVE_TO and LOOK_AT arguments were not constrained: llama.cpp ignores `properties` beside a `oneOf`. The answer schema is flattened.
- NPC answers were cut off at the output caps: shorter text for NPC tiers in the answer schema; caps C1 170 and C2 220 tokens.
- C1 prompts now show argument formats and who is near (C1 budget 500 → 780 tokens). Answers can only name perceived tracks, allowed channels and the body's gestures and expressions.
- Headless LIVE runs ran about 15× faster than real time (`--fixed-fps`): LIVE now runs in real time.
- The world refused every answer slower than 1 s as stale: the stale window is now 6.5 s.
- The VRAM estimate follows llama.cpp's cache layout (sliding-window, shared-KV and hybrid layers); measured values are kept per model file.

### Added (part A)
- `bakeoff/prompts_v3.jsonl` (v1 and v2 unchanged).
- Live bake-off:
  - `--repeat`;
  - Robot R actions accepted vs stale;
  - NPC queue, prefill and generation;
  - share of NPC call time with Robot R's server busy;
  - event-loop lag;
  - promotion latency split into to-call, call and to-action;
  - LIVE_COLD without snapshots;
  - LIVE_LOAD leaves an NPC slot free.
- A pre-warm never takes the last free slot.

### Added (part B, D-61: the pulse protocol)
- Optional `activity` with wake conditions in model answers (backward-compatible), derived when absent, recorded in `decision_record.activity`. A reserved `horizon` wake condition for G5.
- The intent monitor, the pulse with triage, backoff, seeded jitter, idle budget and a time-explicit sitrep. Pulse reviews are background calls and give way to real events.
- FN-1: no walking away from an open conversation without a closing line (one repair, then stay engaged).
- The presence loop: glances toward new speech or movement (and unseen voices), gaze defaults, slow Beacon breathing.
- SURVEY and RETURN_TO_POST from the agent's own observation history.
- `configs/pulse.yaml` (contract `pulse`); scenario fields `pulse` and `post_duty`; `tools/run_scenario.py --pulse`.
- Scenarios SB-06 (long wait), SB-07 (empty hall) and SB-08 (peripheral speaker); per-run pulse metrics (`pulse.jsonl`, `summary.json`); checks in `tools/godot_check.py` step 6.

## G3c-1 — Two model servers, model-driven NPCs (2026-11-17; draft PR)

Owner approvals and the first bake-off results come first; then the bake-off fixes; then G3c-1 (`docs/gates/G3_PLAN.md`, D-59 PROPOSED, `docs/gates/G3c_OWNER_CHECKLIST.md`).

### Owner decisions
- D-56, D-57, D-58 APPROVED (2026-11-16). llama.cpp b12443's two Windows checksums pinned in `tools/install_llama.py` (D-57).
- Bake-off results and verdict recorded (G3_PLAN, D-58): Robot R defaults to F3 (Gemma 4 12B QAT), NPCs to N3 (Qwen3.5-4B Q4_K_M), KV cache q8_0; F2 leaves the core set.

### Fixed
- Bake-off VRAM on Windows: the change in total GPU memory where per-process memory is N/A; no more "CPU build" message.
- Bake-off "promises kept": open promises shown by id with a rule for when to set the flag; scored as *flag* and *behavior*.
- Bake-off: every unusable answer saved raw with its error; the progress line no longer leaves old text.
- Answers cut off at the token limit are reported as such; C1 output cap 60 → 100 tokens.
- Prompt-set hashes ignore line endings; `*.jsonl` pinned to LF in `.gitattributes`.
- The from-source llama-server build no longer downloads the web UI.

### Added
- **Option C:** an NPC llama-server next to Robot R's, own port and key, started and stopped together; VRAM estimated and measured; fallback to Option B with the reason recorded (`inference_events.jsonl`, run manifest).
- **Model-driven NPCs** at C1/C2 (`--npc-model`), with their own private goal in their own prompt only (D-51); canary and observer-filter checks in `tools/godot_check.py`.
- **Persona snapshots and pre-warming** (T5, T6): slot save/restore, slot affinity, prefix state per call, promotion latency per promotion (`promotions.jsonl`); NPC persona prefix sent as a system message.
- `decision_record`: optional `server`, `slot`, `prefix_state` on model calls; `activity` reserved for G3c-2.
- **Bake-off:** `bakeoff/prompts_v2.jsonl` (Robot R, NPC and promise prompts; v1 unchanged), per-role tables, live runs with Option C in four modes (Robot R under NPC load, promotion latency warm and cold, VRAM per server).

## Planning — rigging and quantization (2026-11-16; proposed, docs only)

### Added
- `docs/gates/RIG_PLAN.md` and **D-54** (PROPOSED): skeletons for every robot body, code-driven animation with IK (no stair-climb clips, no ragdoll as simulation), joint tables trimmed from the owner's reference sheets, motion prosody as bounded `amplitude`/`tempo`, steps A–D. Pose is presentation: journals stay identical with posing on or off.
- `docs/QUANTIZATION_OPTIONS.md` and **D-55** (PROPOSED): QAT checkpoints (Gemma 4), bit floors by model size, MoE models with experts in system RAM as the route to bigger models, KV cache q8_0 as a G3b condition, and an offline prompt-set comparison for the bake-off. Research only; nothing downloaded or measured.

### Changed
- ART_DIRECTION §6 and G3_PLAN's G3b section point to the proposed amendments.
- D-55's core bake-off set narrowed to 4B–12B models (owner direction); MoE and large dense models moved to "later".
- CLAUDE.md status: G3a merged 2026-11-15 (PR #12).
- Owner approved D-47 to D-55 (2026-11-16) and answered the two G3a questions: an NPC's own private goal may enter its own prompt only, from G3c (D-51; CLAUDE.md rule reworded); the quadruped with arm may wave, beckon and raise its gripper for "stop" (`configs/bodies/quadruped_arm.yaml`, tests updated).
- G3_PLAN: G3b split into a cloud part and a PC part, with the owner's existing LM Studio models listed against the core set.

## G3a — Agent runtime, no real model (2026-11-15; merged 2026-11-15)

First part of G3 (`docs/gates/G3_PLAN.md`). G3b (a real model on the owner's PC) and G3c (two servers, NPC promotion) follow.

### Fixed
- **Flaky determinism test** (D-47): the demo journal sometimes differed between two same-seed runs. Reproduced under CPU load (6 of 12 runs failed). Cause 1: Godot updated navigation maps on a background thread, so the demo started a tick early or late. Cause 2 (found while building stepped runs): Godot's multithreaded avoidance solver depends on thread timing. Both now run on the main thread. The test runs the demo three times and checks the start tick; CI repeats the determinism tests 5 times under CPU load (`tools/godot_check.py --repeat --cpu-load`).

### Added
- **Scenario runner** (D-48): `tools/run_scenario.py <scenario>` runs a scenario from its YAML end to end through the link and writes a run folder (journal, run manifest, decision records, prompts, memories). Godot gets a world-only copy of the scenario and plays the event tape through the action gate. SB-04 now has a full tape; SB-05 has task goals.
- **Stepped and live runs** (D-48): stepped runs hold the world at each sample until every agent has answered, so a run is exactly repeatable (proved with random sidecar delays); live runs never wait.
- **Agent runtime** (D-49): event-driven decisions, one pending request per agent, conversation state from perception, cognition levels C0/C1/C2 with hysteresis, the Demo policy (answers, honest "I don't know", acknowledges a waiting person and keeps the promise), NPC templates.
- **Model gateway** (D-50): provider-neutral interface; fake and replay models; output validated against the contracts; one repair, then `WAIT`; timeouts → `WAIT`; every call recorded in a `decision_record`.
- **Context assembly** (D-51): nine sections stable to volatile, per-tier budgets, never-cut sections, compression steps 1–4, scope-aware retrieval, untrusted text labelled, token counts per section logged (estimated until G3b).
- **Memory stores**: Commitments & Refusals (capped, never compacted away, expire visibly), Working Set, Episodic Ledger with template episode cards (scopes never merged), Relational Ledger, World Knowledge.
- **Expressions and the Beacon** (D-52): catalog as data (`configs/expressions/`, 15 entries); new `EXPRESS` action; glyph on the humanoid visor and light on the ear pods; symbol on the quadruped's light strip above the camera cluster (D-36 amended); `VISUAL_EXPRESSION` under the sight rules; at most 3 changes per second.
- **Directive templates** (D-53): `configs/directives/` (the six INTERACTION_MODES §8 templates); guardrails are system text no template can change.
- Contracts: `expression`, `directive`, `decision_record` (new); `EXPRESS`, `link.step`, `SCENARIO_EVENT`, `EXPRESSION_SHOWN`, final states in `RUN_ENDED`, scenario `pa_operators`/`directive`/`pin_cognition`/`task_goal` (backward-compatible).
- Tests: Python 451 → 596; Godot 39 → 45; a scenario step in `tools/godot_check.py` (SB-04 twice, SB-05 once). Beacon screenshots in `docs/gates/G3a_screenshots/`.

### Changed
- Owner approved D-43 to D-46; G2 complete.
- `link.hello` is answered by the sidecar; the sidecar can run agent runtimes for a whole cast (`--scenario`, `--model`).

## G2b — Channels, disclosure gate, Python link (2026-11-15; complete: merged 2026-11-15)

Second half of G2 (`docs/gates/G2_PLAN.md`). With it, G2 is complete.

### Added
- **COMMS router** (Godot, D-43): GESTURE, LOCAL, GROUP (invite and accept; decline; leaving stops delivery) and PA (authorized senders only, through the PA speaker), each message making one `comms_event` record (evaluator-only) in the journal.
- **Action gate** (Godot, D-44): validates every agent action request and answers with `action_result` and a reason code (`INVALID_SCHEMA`, `CAPABILITY_DENIED`, `STALE_OBSERVATION`, `RATE_LIMITED`, `TARGET_UNKNOWN`, `GROUP_NOT_MEMBER`, `PA_UNAUTHORIZED`, `PRIVACY_SCOPE_DENIED`).
- **Disclosure gate** (Python, D-45): PUBLIC / GROUP / ONE_TO_ONE / SEALED with the earshot rule; overheard speech never stored or retold; withheld answers never hint. Godot repeats the check on `SPEAK`.
- **Godot ↔ Python link** (D-44): the Python sidecar (`range_service/link/`, WebSocket on 127.0.0.1 with a per-run session token) receives each controlled agent's observations and sends action requests; Godot validates and answers. Scripted agents (no LLM) wave back and say hello. Godot never waits for Python and reconnects by itself.
- **Expression-ready contracts** (D-46): a shared `expression` object (gesture, glyph, light state) and the observation kind `VISUAL_EXPRESSION`, so G3 can add visor/strip glyphs and lights without an incompatible change.
- `tools/run_link_demo.py`: the demo connected to the sidecar, in one command. The demo now has a visitor waving at the robots on the platform.
- Panel line showing the Python link's status.
- Tests: T13–T17 through the router and the link, the action gate's reason codes, wrong token, slow and disconnecting Python side. Godot tests 30 → 39; Python tests 410 → 451. `tools/godot_check.py` runs two test sidecars and validates every message that crossed the link, including a scan for NPC private goals (T17).
- Contract additions (backward-compatible): envelope types `link.hello`, `link.heartbeat`; observation kinds `VISUAL_EXPRESSION`, `GROUP_INVITE`; `comms_event.expression`; `SPEAK.disclosure_scope`; `memory_item.shared_by`, `memory_item.group_id`; journal kinds `COMMS_EVENT`, `COMMS_REJECTED`, `GROUP_CHANGED`, `ACTION_RESOLVED`, `LINK_STATUS`.
- Dependency `websockets` (the sidecar's WebSocket server).
- Decisions D-43 to D-46 (proposed).

### Changed
- Owner approved D-39 to D-42; D-40 records the known limit for loud halls (Lombard effect before G6).

## G2a — Senses, journal, avoidance (2026-11-14, complete: merged 2026-11-14)

First half of G2 (plan: `docs/gates/G2_PLAN.md`; G2b adds channels, the disclosure gate and the WebSocket link).

### Added
- **Observer filter** in Godot (`scripts/senses/`, D-39): sight lines from each body's sensor mount to the head, torso, both sides and the gesturing hand of every other avatar; walls, props, steps and other avatars block sight. Fully seen → `OBSERVED`; partly → `DEGRADED` / `PARTLY_OCCLUDED` with the visible parts; recently seen but hidden → `OCCLUDED` / `MISSING` at the last known spot with no quality; never seen → absent.
- **Hearing** (D-40): local speech level falls with distance, walls take some off, the zone noise floor masks it; heard without sight as `UNKNOWN_SOURCE` with a direction only; delivered once, never backfilled.
- **Gestures and speech as world events:** `Avatar.perform_gesture()` (refused if the body cannot, D-36) and `Avatar.say()`; perceived only by those who could see or hear them.
- **Observation packets** in the observation contract, sampled at `tick_hz` (10 Hz) on the 60 Hz tick (D-33), with anonymous per-observer tracks.
- **Event journal** written by Godot (D-41) to `user://journals/`, deterministic (same seed, same bytes); `tools/godot_check.py` validates every journal line and packet the tests write against the contracts in Python.
- **Shared local avoidance** across the per-size navigation maps (D-42).
- **Low divider** (1.1 m) in Sandbox Flats: the quadruped cannot see over it, humanoids can.
- **F2 sense view**: lines and labels for what the selected avatar perceives; the info panel lists what it sees and hears.
- Demo: robots greet each other on the platform; the quadruped's attempted wave is refused and journaled.
- Contract additions (backward-compatible): observation `validity_reason`, `visible_parts`; journal kinds `GESTURE_PERFORMED`, `GESTURE_REFUSED`, `SPEECH_EMITTED`; `sample_hz` in `RUN_STARTED`.
- Godot tests 19 → 30; Python tests 399 → 410.
- Decisions D-39 to D-42 (proposed).

### Changed
- Owner approved D-37 and D-38.

## G1b — Robot body family (2026-11-14, complete: merged 2026-11-14)

### Added
- **Three robot bodies** (D-36): `legged_humanoid`, `wheeled_humanoid`, `quadruped`, plus the `quadruped_arm` variant, each with realistic starting values for size, collider, speed and turn limits, stairs/ramp capability, sensor mount height and field of view, reach, arms, gestures and expression channels. "Robot R" is a role; a scenario picks its body.
- **Body contract 2.0** (D-37): collider footprint, sensor mount height, arms, gestures, expression channels; robot kinds renamed. One shared gesture vocabulary in `contracts/common.schema.json` (adds `HEAD_TILT`, `SIT_IN_PLACE`, `HAND_OVER`) and expression channels (`SPEECH`, `FACE`, `LIGHT`).
- `range_service/bodies.py` and `godot_app/scripts/core/bodies.gd`: turning/navigation radius and gesture/channel permissions; the config validator reports contradictions.
- Greybox models: legged and wheeled humanoids (shared upper body; legs or a four-wheeled base with lift column) and the quadruped (sensor-visor head, dorsal rail, four legs, optional stowed arm). Number badges, matte trim and 1–3 stripes.
- **Per-size navigation** (D-37): one navigation map per body size; a single mesh for the quadruped would have removed 14% of people's walkable floor.
- Bevelled colliders for legged box bodies, so the quadruped climbs the stairs while the wheeled base is still stopped by the steps.
- `configs/scenarios/SB05_RAMP_VS_STAIRS.yaml` (Robot R in all three bodies) and three SB-05 spawn points in Sandbox Flats.
- Demo with all three robot families going up to the platform; `scenes/robot_lineup.tscn` showing every robot body side by side.
- Godot tests 15 → 19 (and several rewritten for every body); Python tests 356 → 399.
- A compile step in `tools/godot_check.py` that loads every GDScript file (D-38).
- Decisions D-36 (approved), D-37 and D-38 (proposed); later embodiments in RANGE_V0_SCOPE §6.1.

### Changed
- Owner approved D-30, D-31, D-33 (tick resolved: Godot's 60 Hz tick is canonical; `tick_hz` must divide 60, now checked), D-34 and D-35. D-32 superseded by D-36.
- `robot_r` body renamed `wheeled_humanoid` (persona `robot_r` and SB-04 point at it).

### Fixed
- Six GDScript warnings seen in the owner's editor (integer division; `tr`, `owner`, `basis` shadowing). Every default-on GDScript warning is now an error (D-38).

## G1 — Sandbox Flats in Godot (2026-11-14, complete: merged 2026-11-14)

### Added
- **Godot 4.7.2 project** in `godot_app/` (GDScript, Forward+, Jolt physics, fixed 60 Hz tick, frame rate capped at 60).
- **Sandbox Flats built from `configs/maps/sandbox_flats.yaml`**: floor with a 5 m grid, outer walls, two movable partitions, the 0.6 m platform with a ramp and a 4-step stair placed by the map's nav links, the acoustically reflective west wall (striped and labelled), PA speaker, three chairs, zone volumes carrying their environment values (floor darkened by light level), spawn markers.
- **Capability-gated navigation (D-31):** baked navigation mesh plus ramp/stairs links on capability layers; bodies without `can_use_stairs` are also physically stopped by the steps.
- **Robot R** assembled from primitives in the concept's proportions on a wheeled base, with green identity trim and an `R` badge (D-32); **three capsule visitors** with head-direction markers.
- **Avatars** (`CharacterBody3D` + `NavigationAgent3D`) limited by their body config's speed, acceleration and turn rate; a 60 Hz world clock; stuck detection.
- **Walk-to-goal demo** (about 40 s): Robot R up the ramp and back, visitor_y up the stairs, two visitors around the partitions and to the chairs.
- **Camera:** free fly and orbit-follow with avatar selection; a small status and help panel; pause, restart, hide.
- **15 headless Godot tests** (`godot_app/tests/`), including SB-05 ramp-vs-stairs routing, physical stair blocking, wall and body collision, speed and turn limits, the robot model, the camera and a full demo run.
- `tools/export_godot_data.py` (configs → validated JSON for Godot, D-30), `tools/godot_check.py` (headless import and tests), `tools/install_godot.py` (pinned, SHA-512-verified Godot download).
- `tools/check.py` now has five steps (adds Godot data and Godot); a missing Godot shows as SKIP, `--require-godot` makes it a failure (D-34).
- CI installs and caches Godot 4.7.2 and runs every check on Python 3.12, 3.13 and 3.14.
- `.python-version` set to 3.14 (D-35).
- Screenshots in `docs/gates/G1_screenshots/`; plan in `docs/gates/G1_PLAN.md`; owner checklist in `docs/gates/G1_OWNER_CHECKLIST.md`.
- Decisions D-30 to D-35 (PROPOSED). D-06 annotated (Godot patch re-checked; Python 3.14).

### Changed
- G0 marked complete; decision D-29 approved by the owner.
- `docs/BUILD_AND_RUN.md`, `docs/OWNER_SETUP_WINDOWS.md` and `godot_app/README.md` cover Godot.

## G0 — Repository, contracts and headless test world (2026-11-13, complete: merged 2026-11-14)

### Added
- Python project (`pyproject.toml`, `uv.lock`) for Python 3.12+, with only `jsonschema`, `pyyaml` and `pytest`.
- Folder layout per D-15: `range_service/` (`horizon/`, `sensors/`, `agents/`, `comms/`, `eval/`, `testworld/`), `contracts/`, `configs/`, `tests/`, `tools/`, `models/`, `godot_app/`.
- **Contracts v1** (`contracts/`, schema version `1.0`): `envelope`, `observation`, `delta_feature`, `hypothesis`, `action_request`, `action_result`, `comms_event`, `intervention`, `memory_item`, `run_manifest`, `map`, `persona`, `body`, `scenario`, `preset`, plus `common` and `journal_entry`. 30 valid and 115 invalid examples.
- Evaluator-only leak guard: agent-facing contracts reject every evaluator-only field name at every level.
- ΔP module (`range_service/horizon/delta.py`): D-11 formula, `null` with a reason for missing/unsupported input, clipping, scale floor, categorical pass-through, robust scale, optional `S`/`Q` summary.
- Headless 2D test world (`range_service/testworld/`): walls, field of view, range, line of sight, fixed tick, seeded RNG, JSONL journal with SHA-256 hash.
- Example configs: Sandbox Flats map; Robot R and human walker bodies; Robot R, Visitor X and Visitor Y personas; preset H0; scenario SB-04 Polite bid.
- `tools/validate_configs.py` (schema, duplicate keys, file names, cross-references) and `tools/check.py` (one command for everything).
- CI workflow running `tools/check.py` on Python 3.12 and 3.13.
- `docs/BUILD_AND_RUN.md`, `contracts/README.md`, decision D-29 (approved by the owner on 2026-11-14).
