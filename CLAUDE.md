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
**G1 built, in review** (draft PR; not merged until the owner approves): Sandbox Flats in Godot 4.7.2, Robot R and three visitors, capability-gated ramp/stairs (SB-05), free/orbit camera, 15 headless Godot tests in `tools/check.py` and CI. Plan: [docs/gates/G1_PLAN.md](docs/gates/G1_PLAN.md); owner checks: [docs/gates/G1_OWNER_CHECKLIST.md](docs/gates/G1_OWNER_CHECKLIST.md). Decisions D-30 to D-35 are PROPOSED. See [CHANGELOG.md](CHANGELOG.md).
Next gate after merge: **G2** (observer filter, COMMS, disclosure gate, event journal). Owner PC setup: [docs/OWNER_SETUP_WINDOWS.md](docs/OWNER_SETUP_WINDOWS.md). Update this section when a gate completes.

## Rules that never bend

- The host (Godot in RANGE) owns physics, collision, navigation and safety. HORIZON and LLMs only **propose**; the action gate validates.
- Agents see only what their simulated senses could observe. NPC private goals, scenario labels and world truth are **evaluator-only** and never enter an agent's prompt.
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
- `uv run python tools/godot_check.py [--filter NAME]`: only the Godot import and headless tests.
- `uv run pytest`: run only the Python tests.

Layout: contracts in `contracts/` (see [contracts/README.md](contracts/README.md)), Python in `range_service/`, Godot in `godot_app/` (see [godot_app/README.md](godot_app/README.md)), content in `configs/`, tests in `tests/` and `godot_app/tests/`, scripts in `tools/`.

These working rules adapt the `AGENTS.md` rules from the earlier scaffold in DoctorWomp/SOMA_CODEC#1 (D-18).
