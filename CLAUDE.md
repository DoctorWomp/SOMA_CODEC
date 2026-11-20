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
**G3 in progress** ([docs/gates/G3_PLAN.md](docs/gates/G3_PLAN.md)): G3a merged 2026-11-15 (scenario runner with stepped and live runs, agent runtime with the Demo policy and C0/C1/C2 levels, model gateway with a fake model and record/replay, context assembly, expression catalog and Beacon). D-47 to D-55 APPROVED 2026-11-16, including rigging and animation ([docs/gates/RIG_PLAN.md](docs/gates/RIG_PLAN.md), D-54) and quantized/QAT models ([docs/QUANTIZATION_OPTIONS.md](docs/QUANTIZATION_OPTIONS.md), D-55). **G3b complete**: G3b-1 (pinned llama-server with checksums pinned, model catalog and registry, llama-server provider) and G3b-2 (priority scheduler, `tools/bakeoff.py`) merged; D-57, D-58 APPROVED 2026-11-16. The owner's bake-off ran 2026-11-17: Robot R defaults to F3 (Gemma 4 12B QAT), the NPC server to N3 (Qwen3.5-4B Q4_K_M), KV cache q8_0, F2 dropped (D-58). **Rig step A** merged (D-56 APPROVED 2026-11-16); next rig step: B (gaits and foot IK). **G3c-1 merged** 2026-11-17: two model servers (Option C), model-driven C1/C2 NPCs, persona snapshots and pre-warming, bake-off fixes and prompts_v2 (D-59 APPROVED 2026-11-17). **G3c-2** built: model-driven NPC fixes and real-time LIVE runs (D-60), the pulse protocol ([docs/PULSE_PROTOCOL.md](docs/PULSE_PROTOCOL.md); FIELD_NOTES FN-1, FN-2; D-61); D-60, D-61 PROPOSED until the owner's PC run. **G3d** merged (closes G3, pending the owner's PC results, [docs/gates/G3d_OWNER_CHECKLIST.md](docs/gates/G3d_OWNER_CHECKLIST.md)): one deadline per decision and a relevance check before sending (D-63), memory that follows what the world accepted (D-64), honest pulse metrics and a presence fix (D-65), an audible goodbye before leaving (D-66), the idle budget at admission (D-67), parallel scenario runs in check.py (D-68), rendered-client numbers, pulse on/off and run reports (D-69), the soak (D-70; memory grows with heard speech: owner decision needed), and the HORIZON operational architecture as design constraints (D-62; its three-body experiment is the first step of G5). All PROPOSED. **G3e** (presence and expression) merged, [docs/gates/G3e_OWNER_CHECKLIST.md](docs/gates/G3e_OWNER_CHECKLIST.md): head-anchored sensing, the head as host-owned world state (D-72); the ambient state display (D-73); presence motion and the subtle ↔ performative dial (D-74); color shifting decided, pattern not hue (D-71, APPROVED). D-72 to D-74 PROPOSED. **Owner decisions 2026-11-19:** D-60, D-61, D-63 to D-69 APPROVED; D-70's memory proposal APPROVED (built in G3f, D-81); D-72 to D-74 stay PROPOSED until the G3e watch. **G3f** (Robot R on time under load) built as a draft PR, [docs/gates/G3f_OWNER_CHECKLIST.md](docs/gates/G3f_OWNER_CHECKLIST.md): the diagnosis (GPU contention between the two servers dominates; a bake-off defect pooled runs in reused folders) and per-call instrumentation with `bakeoff.py diagnose` (D-75); Robot R's prompt layout (and a persona-prefix defect fixed), short answers and the focal-first GPU guard as named conditions (D-76 to D-78, off by default until measured); model choice and the deadline unchanged (D-79, D-80); raw heard speech bounded (D-81); attention while walking and SB-10 (D-82); a simulated shared GPU for cloud measurement (D-83). D-75 to D-83 PROPOSED.
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
- `uv run python tools/bakeoff.py offline` / `live --models F3 --npc-model N3`: the model bake-off (D-58 to D-60); results in `results/bakeoff/results.md`. LIVE runs are real time.
- `uv run python tools/run_scenario.py SB06_LONG_WAIT [--pulse on|off] [--no-pulse]`: the pulse protocol scenarios SB-06 to SB-08 (D-61).
- `uv run python tools/run_scenario.py SB04_POLITE_BID --watch --resolution 1920x1080 --render-preset v0`: a rendered run with frame times and peak VRAM in `summary.json` (D-69); `uv run python tools/compare_runs.py RUN_A RUN_B` compares runs; `uv run python tools/soak.py` runs the 21-minute soak (D-70). Summaries only are shared: run folders hold raw prompts and memory. `--presence subtle|default|performative` sets the presence dial (D-74).
- `uv run python tools/bakeoff.py diagnose` / `live ... --focal-layout SYSTEM_PREFIX --focal-answer SHORT --gpu-guard on`: G3f conditions (D-75 to D-78); `uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model fake-gpu --npc-load 3` and `uv run python tools/contention_sim.py`: the simulated shared GPU (D-83, a model, not a measurement); `SB10_GLANCE_WHILE_WALKING` (D-82).

Layout: contracts in `contracts/` (see [contracts/README.md](contracts/README.md)), Python in `range_service/`, Godot in `godot_app/` (see [godot_app/README.md](godot_app/README.md)), content in `configs/`, tests in `tests/` and `godot_app/tests/`, scripts in `tools/`.

These working rules adapt the `AGENTS.md` rules from the earlier scaffold in DoctorWomp/SOMA_CODEC#1 (D-18).
