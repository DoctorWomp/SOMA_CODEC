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
| `map`, `persona`, `body`, `scenario`, `preset` | config | The YAML content files in `configs/` |

`x-audience` in each file records its audience. **Agent-facing contracts can never carry evaluator-only fields** (private goals, scenario labels, delivery lists; the list is `common.schema.json#/$defs/evaluator_only_field`). Tests insert every one of those names at every level of every agent-facing example and check that each is rejected.

## Shared rules

- Unknown fields are rejected everywhere (`additionalProperties: false`). Where an object's shape depends on a `kind`, `action` or `type`, it is marked `x-closed-by` and closed by one rule per value; a test checks that every value has a rule.
- Ticks and times are non-negative integers. Seeds are capped at 2^53−1 so Godot reads them exactly.
- Missing or stale evidence is `null` with a reason, never `0`.
- Enum values are `UPPER_SNAKE`; envelope `type` values are dotted lowercase (`world.observation`), as in the Blueprint.
- Positions use Godot's frame: floor is x/z, y is up, yaw 0 faces −z, positive yaw and bearing turn left (D-29).
- Every top-level contract has `schema_version: "1.0"`. An incompatible change bumps it.

## Examples

`examples/<contract>/valid/*.json` must pass. `examples/<contract>/invalid/*.json` must fail, and `invalid/_expect.json` names the JSON Schema keyword each one should fail on (for example `additionalProperties` or `minimum`), so an example can't "pass" by failing for an unrelated reason.

Check everything with `uv run python tools/check.py` (see [docs/BUILD_AND_RUN.md](../docs/BUILD_AND_RUN.md)).
