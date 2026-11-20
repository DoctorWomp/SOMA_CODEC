# Contracts v1

JSON Schema (draft 2020-12) files that define every message, record and config format (D-27). Python validates them with `jsonschema`; Godot validates the same files from G1–G2. **These files are the source of truth:** change a schema first, then its examples, the Python code, the Godot consumers and the tests (CLAUDE.md).

## Files

| Contract | Audience | What it is |
|---|---|---|
| `common` | shared | Building blocks: ids, ticks, `validity`, read labels, scopes, channels, layer mask, poses, the evaluator-only field list |
| `envelope` | transport | WebSocket wrapper; the payload is checked against the schema its `type` names |
| `observation` | **agent** | What one observer's simulated senses received at one tick |
| `delta_feature` | **agent** | One ΔP channel: `normalized_delta`, or `null` plus `null_reason` |
| `hypothesis` | **agent** | One candidate reading with a read label (`COMMIT`/`LEAN`/`HELD_OPEN`/`UNKNOWN`) |
| `action_request` | **agent** | An action an agent proposes; arguments are checked per action |
| `action_result` | **agent** | The host's accept/reject answer with a reason code |
| `memory_item` | **agent** | One item in an agent's own memory stores, with scope and source |
| `comms_event` | evaluator | Router record of a message, including who it was and wasn't delivered to |
| `intervention` | evaluator | A journaled Director action; taints the run unless pre-scheduled |
| `run_manifest` | evaluator | How a run was set up: seed, versions, per-avatar policy/mask/sensors |
| `journal_entry` | evaluator | One line of the JSONL event journal |
| `decision_record` | evaluator | One agent decision: triggers, context sizes per section, model calls with responses (record and replay), the requests it made (G3a, D-49–D-51) |
| `map`, `persona`, `body`, `scenario`, `preset`, `expression`, `directive` | config | The YAML content files in `configs/` |
| `pulse` | config | The pulse protocol settings, configs/pulse.yaml (G3c-2, D-61) |
| `model_catalog`, `inference`, `model_registry` | config | The pinned model files, the real-model settings and the local (git-ignored) list of model files on this machine (G3b, D-57) |

`x-audience` in each file records its audience. **Agent-facing contracts can never carry evaluator-only fields** (private goals, scenario labels, delivery lists; the list is `common.schema.json#/$defs/evaluator_only_field`). Tests insert every one of those names at every level of every agent-facing example and check that each is rejected.

## Shared rules

- Unknown fields are rejected everywhere (`additionalProperties: false`). Where an object's shape depends on a `kind`, `action` or `type`, it is marked `x-closed-by` and closed by one rule per value; a test checks that every value has a rule.
- Ticks and times are non-negative integers. Seeds are capped at 2^53−1 so Godot reads them exactly.
- Missing or stale evidence is `null` with a reason, never `0`.
- Enum values are `UPPER_SNAKE`; envelope `type` values are dotted lowercase (`world.observation`), as in the Blueprint.
- Positions use Godot's frame: floor is x/z, y is up, yaw 0 faces −z, positive yaw and bearing turn left (D-29).
- Every top-level contract has a `schema_version`. An incompatible change bumps it. All contracts are at `1.0` except **`body`, at `2.0`** (D-37); `common.schema.json` holds each version.
- The link between Godot and Python (D-44) adds envelope types `link.hello` and `link.heartbeat`; the session token is never in an envelope.
- Expressions (D-46, D-52): one shared `expression` object (gesture, glyph, light state) used by GESTURE-channel `comms_event`s and `VISUAL_EXPRESSION` observations. The `EXPRESS` action names an entry of the expression catalog (`configs/expressions/`, contract `expression`).
- G3a (D-48): envelope type `link.step` for stepped runs; journal kinds `SCENARIO_EVENT` and `EXPRESSION_SHOWN`; optional scenario fields `pa_operators`, `directive`, `pin_cognition`, `task_goal`. All backward-compatible, versions unchanged.
- Rig step A (D-56): optional `amplitude` and `tempo` (`prosody_factor`, 0.5–1.5) on `GESTURE` and `EXPRESS` actions, on catalog entries and on the `GESTURE_PERFORMED` journal payload (only when given); an optional `rig` block in `body`. All backward-compatible, versions unchanged.
- G3b (D-57): new config contracts `model_catalog` (configs/models/catalog.yaml), `model_registry` (the git-ignored models/registry.local.yaml) and `inference` (configs/inference.yaml). No message contract changed.
- G3c-1 (D-59): `inference` gains optional `vram` (budget, reserve, compute buffer, FALLBACK/WARN) and `personas` (snapshots, prewarm, system_prefix); `decision_record` model calls gain optional `server`, `slot` and `prefix_state`, and `activity` is reserved (null only) for G3c-2. All backward-compatible, versions unchanged.
- G3c-2 (D-60, D-61): `decision_record.activity` now holds an activity (`common` `activity_kind`, `wake_condition`, with `horizon` reserved for G5); new trigger values `WAKE_CONDITION` and `PULSE_REVIEW`; optional model-call field `other_server_busy_ms`; scenario fields `pulse` and `post_duty`; new config contract `pulse`. All backward-compatible, versions unchanged.
- G3f/G3g (D-77, D-78, D-85, D-86, D-89): `inference` `focal.answer` takes FULL, SHORT or LEAN; optional `gpu_guard.hold` (ALL, DECISIONS) and top-level `salvage`; `decision_record` model calls gain optional `salvaged` (the field cut off, the actions used). All backward-compatible, versions unchanged.
- Gestures come from one shared vocabulary, `common.schema.json#/$defs/gesture`, used by `body`, `action_request` and `observation` (D-36). Expression channels likewise (`SPEECH`, `FACE`, `LIGHT`).

## Examples

`examples/<contract>/valid/*.json` must pass. `examples/<contract>/invalid/*.json` must fail, and `invalid/_expect.json` names the JSON Schema keyword each one should fail on (for example `additionalProperties` or `minimum`), so an example can't "pass" by failing for an unrelated reason.

Check everything with `uv run python tools/check.py` (see [docs/BUILD_AND_RUN.md](../docs/BUILD_AND_RUN.md)).
