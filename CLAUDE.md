# SOMA_CODEC — guide for Claude Code

SOMA HORIZON is an advisory sensory layer (L0–L8) that helps an embodied agent act in a way that fits the people around it. SOMA RANGE is the simulated test environment where HORIZON is built and A/B tested: Godot owns the world, a Python sidecar runs agents and HORIZON.

## Read first

1. [docs/RANGE_V0_SCOPE.md](docs/RANGE_V0_SCOPE.md): what we are building now and in what order.
2. [docs/DECISIONS.md](docs/DECISIONS.md): settled answers. Approved decisions override every source document.
3. [docs/SOURCES.md](docs/SOURCES.md): index of all design documents with status and precedence.
4. [docs/INFERENCE_STRATEGY.md](docs/INFERENCE_STRATEGY.md): model residency, caching and scheduling (read before G3 work).
5. [docs/CONTEXT_MEMORY_STRATEGY.md](docs/CONTEXT_MEMORY_STRATEGY.md): bounded context assembly, compression and anti-rot rules (read before G3 work).
6. [docs/INTERACTION_MODES.md](docs/INTERACTION_MODES.md): modes, permissions, awareness protocols (read before G4 work).
7. [docs/ART_DIRECTION.md](docs/ART_DIRECTION.md): visual style, rendering budget, fidelity ladder (read before G1 and G6 work).

Main specs: the [Master Build Blueprint](docs/sources/range/SOMA_RANGE_Master_Build_Blueprint_v1.0.md), the [HORIZON Operational Atlas](docs/sources/horizon/SOMA_HORIZON_Sensory_Layer_Operational_Atlas_v0.2.md) and the [ΔP Math Addendum](docs/sources/horizon/SOMA_HORIZON_DeltaP_Math_Control_Addendum_v0.2.md). They are long: read the sections the current task needs, not everything. Do not implement anything listed as superseded in SOURCES.md.

## Status

**G0 complete** (merged 2026-11-14): contracts v1, headless test world, ΔP module, config validator, one check command, CI. Decision D-29 (contract conventions) is APPROVED.
**G1 complete** (merged 2026-11-14): Sandbox Flats in Godot 4.7.2, capability-gated ramp/stairs, free/orbit camera, headless Godot tests in `tools/check.py` and CI. Decisions D-30, D-31, D-33, D-34, D-35 APPROVED.
**G1b complete** (merged 2026-11-14): robot body family (legged humanoid, wheeled humanoid, quadruped + arm variant); Robot R is a role. D-36, D-37, D-38 APPROVED.
**G2 complete** ([docs/gates/G2_PLAN.md](docs/gates/G2_PLAN.md)): G2a and G2b merged 2026-11-15 (observer filter, hearing, journal, avoidance, COMMS router, action gate, disclosure gate, Godot ↔ Python link; D-39 to D-46 APPROVED).
**G3 in progress** ([docs/gates/G3_PLAN.md](docs/gates/G3_PLAN.md)): G3a merged 2026-11-15 (scenario runner with stepped and live runs, agent runtime with the Demo policy and C0/C1/C2 levels, model gateway with a fake model and record/replay, context assembly, expression catalog and Beacon; flaky determinism fixed). D-47 to D-55 APPROVED 2026-11-16, including rigging and animation ([docs/gates/RIG_PLAN.md](docs/gates/RIG_PLAN.md), D-54) and quantized/QAT models ([docs/QUANTIZATION_OPTIONS.md](docs/QUANTIZATION_OPTIONS.md), D-55). **G3b-1** built 2026-11-16, in review as a draft PR (pinned llama-server installer, model catalog and local registry, llama-server provider with constrained output, slot pinning and real token counts, stand-in server tests; D-57 PROPOSED; [owner checklist](docs/gates/G3b_OWNER_CHECKLIST.md)). **G3b-2** built 2026-11-16, in review as a draft PR (priority scheduler with a pinned focal slot, aging and stale-drop; `tools/bakeoff.py` with the committed offline prompt set; D-58 PROPOSED). Next: the owner's bake-off run on the PC; then G3c (two servers, NPC promotion). **Rig step A** built 2026-11-16, in review as a draft PR (skeletons for the four robot bodies, posture, gesture and gaze layers with IK, wheel spin, gesture amplitude/tempo; D-56 PROPOSED; [owner checklist](docs/gates/RIG_A_OWNER_CHECKLIST.md)). Next rig step: B (gaits and foot IK).
Owner PC setup: [docs/OWNER_SETUP_WINDOWS.md](docs/OWNER_SETUP_WINDOWS.md). Update this section when a gate completes.

## Rules that never bend

- The host (Godot in RANGE) owns physics, collision, navigation and safety. HORIZON and LLMs only **propose**; the action gate validates.
- Agents see only what their simulated senses could observe. NPC private goals, scenario labels and world truth are **evaluator-only** and never enter another agent's prompt. The one exception: an NPC's **own** private goal may enter **its own** prompt, labelled as its own, and nowhere else (D-51, owner 2026-11-16).
- Missing or stale evidence is `null`/`UNKNOWN` with a reason, **never 0 or "calm"**.
- No emotion, sincerity, deception, threat or personality verdicts about people, and no stored labels or trust scores (D-13). Observable ≠ inferred.
- Text from signs, speech, messages or other agents is untrusted evidence. It can never change instructions or permissions (D-09).
- Disclosure follows scopes `PUBLIC / GROUP / ONE_TO_ONE / SEALED`; overheard is not told; never reveal that something is being withheld (D-12).
- Interpretations use `COMMIT / LEAN / HELD_OPEN / UNKNOWN`; no uncalibrated numeric confidence (D-10).
- Never claim a test passed, a result was measured or a feature works unless it was actually run.

## How to work

- One gate at a time, on a feature branch, with draft PRs. Do not merge without owner review.
- Start each gate with a plan against its section of RANGE_V0_SCOPE.md and the relevant Blueprint tests (T01–T30).
- **Bug fixes:** reproduce first, find the responsible boundary, add a failing regression test, make the smallest fix, run the full check. Never remove or skip a test to get green.
- Keep JSON Schemas, Python validation, Godot consumers, examples and tests aligned when a contract changes. Bump the version for incompatible changes.
- No provider calls, telemetry, microphone capture or paid services by default. Never commit credentials or private data.
- Record new decisions in docs/DECISIONS.md rather than deciding silently in code.
- Before finishing: review the diff, list what works vs what is planned, give the commands run and their results, and note what still needs a manual check on the owner's Windows PC.

## Commands

Full details: [docs/BUILD_AND_RUN.md](docs/BUILD_AND_RUN.md).

- `uv sync --locked`: install the exact locked dependencies.
- `uv run python tools/check.py`: **run every check** (contracts, configs, Godot data, tests, Godot headless tests). Must pass before finishing any task. A missing Godot shows as SKIP; in a cloud session run `uv run python tools/install_godot.py` first so the Godot step really runs.
- `uv run python tools/validate_configs.py`: check only the YAML files in `configs/`.
- `uv run python tools/export_godot_data.py`: refresh `godot_app/data/` after editing a map or body config (commit both).
- `uv run python tools/godot_check.py [--filter NAME]`: only the Godot import, compile, headless tests and the contract check of what Godot wrote.
- `uv run pytest`: run only the Python tests.
- `uv run python tools/run_link_demo.py`: open the Godot demo connected to the Python sidecar.
- `uv run python tools/run_scenario.py SB04_POLITE_BID [--watch] [--no-pose] [--model llama]`: run a scenario end to end (stepped, Demo policy unless a model is given); writes a run folder under `runs/`. `--no-pose` keeps robots in their rest pose (the journal is the same).
- `uv run python tools/install_llama.py --check` / `uv run python tools/models.py plan`: the pinned llama-server and the model files on this machine (G3b, D-57).
- `uv run python tools/bakeoff.py offline` / `live --models F1 F3`: the model bake-off (D-58); results in `results/bakeoff/results.md`.

Layout: contracts in `contracts/` (see [contracts/README.md](contracts/README.md)), Python in `range_service/`, Godot in `godot_app/` (see [godot_app/README.md](godot_app/README.md)), content in `configs/`, tests in `tests/` and `godot_app/tests/`, scripts in `tools/`.

These working rules adapt the `AGENTS.md` rules from the earlier scaffold in DoctorWomp/SOMA_CODEC#1 (D-18).
