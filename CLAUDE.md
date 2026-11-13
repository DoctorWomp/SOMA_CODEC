# SOMA_CODEC — guide for Claude Code

SOMA HORIZON is an advisory sensory layer (L0–L8) that helps an embodied agent act in a way that fits the people around it. SOMA RANGE is the simulated test environment where HORIZON is built and A/B tested: Godot owns the world, a Python sidecar runs agents and HORIZON.

## Read first

1. [docs/RANGE_V0_SCOPE.md](docs/RANGE_V0_SCOPE.md): what we are building now and in what order.
2. [docs/DECISIONS.md](docs/DECISIONS.md): settled answers. Approved decisions override every source document.
3. [docs/SOURCES.md](docs/SOURCES.md): index of all design documents with status and precedence.
4. [docs/INFERENCE_STRATEGY.md](docs/INFERENCE_STRATEGY.md): model residency, caching and scheduling (read before G3 work).
5. [docs/CONTEXT_MEMORY_STRATEGY.md](docs/CONTEXT_MEMORY_STRATEGY.md): bounded context assembly, compression and anti-rot rules (read before G3 work).
6. [docs/INTERACTION_MODES.md](docs/INTERACTION_MODES.md): modes, permissions, awareness protocols (read before G4 work).

Main specs: the [Master Build Blueprint](docs/sources/range/SOMA_RANGE_Master_Build_Blueprint_v1.0.md), the [HORIZON Operational Atlas](docs/sources/horizon/SOMA_HORIZON_Sensory_Layer_Operational_Atlas_v0.2.md) and the [ΔP Math Addendum](docs/sources/horizon/SOMA_HORIZON_DeltaP_Math_Control_Addendum_v0.2.md). They are long: read the sections the current task needs, not everything. Do not implement anything listed as superseded in SOURCES.md.

## Status

Documentation only. No code yet. Next gate: **G0** (repo skeleton, contracts, headless test world, tests, CI). Update this section when a gate completes.

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

None yet. Added at G0.

These working rules adapt the `AGENTS.md` rules from the earlier scaffold in DoctorWomp/SOMA_CODEC#1 (D-18).
