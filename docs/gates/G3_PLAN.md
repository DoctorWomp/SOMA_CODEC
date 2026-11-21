# G3 — Agent runtime

**Status:** G3a COMPLETE (merged 2026-11-15) · G3b COMPLETE (G3b-1 and G3b-2 merged; D-57, D-58 APPROVED 2026-11-16; bake-off run on the owner's PC 2026-11-17) · G3c-1 COMPLETE (merged 2026-11-17; D-59 APPROVED 2026-11-17) · G3c-2 built 2026-11-18 (D-60, D-61 APPROVED 2026-11-19) · G3d built 2026-11-18 (D-63 to D-70 APPROVED 2026-11-19; D-62 PROPOSED): G3 complete pending the owner's PC results · **G3e (presence and expression) built 2026-11-18; D-71 APPROVED, D-72 to D-74 PROPOSED** · **G3f (Robot R on time under load) built 2026-11-19, draft PR; D-75 to D-83 PROPOSED; D-60, D-61, D-63 to D-70 APPROVED 2026-11-19** · owner checks: [G3a](G3a_OWNER_CHECKLIST.md), [G3b](G3b_OWNER_CHECKLIST.md), [G3c-1](G3c_OWNER_CHECKLIST.md), [G3c-2](G3c2_OWNER_CHECKLIST.md), [G3d](G3d_OWNER_CHECKLIST.md), [G3e](G3e_OWNER_CHECKLIST.md), [G3f](G3f_OWNER_CHECKLIST.md)
**Scope:** [RANGE_V0_SCOPE.md](../RANGE_V0_SCOPE.md) §4 (G3 row) · [INFERENCE_STRATEGY.md](../INFERENCE_STRATEGY.md) §7 steps 1–5 · [CONTEXT_MEMORY_STRATEGY.md](../CONTEXT_MEMORY_STRATEGY.md) §3–§5 and §11 steps 3–5 · [EXPRESSION_PRINCIPLES.md](../EXPRESSION_PRINCIPLES.md) §1 and §7 (G3 row) · [INTERACTION_MODES.md](../INTERACTION_MODES.md) §8 (directive templates) · Blueprint §10 (agent contracts, scheduler), §11 (memory), §18 (T18, T25–T27), §20 (G3 gate) · [DECISIONS.md](../DECISIONS.md) D-08, D-09, D-12, D-13, D-14, D-20, D-21, D-23, D-24, D-36, D-43–D-46

## Goal

Agents that decide: first with a scripted policy, then with one local model, without ever freezing the world. The Blueprint's G3 gate: *Demo policy, shared-model adapter, action gate, async scheduler, RCC. Proof: scripted run complete; model call validated if an endpoint exists; GUI doesn't freeze.*

## Split: G3a, G3b, G3c

| Part | Where | Contents | Proof |
|---|---|---|---|
| **G3a — Runtime, no real model** (this session) | Cloud | Scenario runner; agent runtime with the Demo policy for every agent; cognition levels C0/C1/C2 with hysteresis; model gateway with a deterministic fake model, timeouts, one repair, record and replay; context assembly with memory stores, budgets and compression steps 1–4; expression catalog, `EXPRESS` action, Beacon rendering and `VISUAL_EXPRESSION`; directive templates as data | T18, T25, T26, T27; no evaluator-only data in any context; expressions refused for bodies that lack the channel; a full scripted scenario is deterministic; SB-04 and SB-05 run from their files |
| **G3b — One real model** | Owner's PC | `llama-server` (llama.cpp) as a child process, Option A then B (one server, focal priority); real tokenizer counts; priority scheduler with deadlines and stale-drop; slot pinning; model bake-off (D-20); first VRAM and latency measurements | Model call validated against a real endpoint; bake-off table; the soak test's first hour |
| **G3c — Two servers and NPC promotion** | Owner's PC | Option C (focal + NPC server); C1/C2 NPCs on the NPC model; persona snapshots (T5); promotion latency measured | Focal p50/p95 under NPC load; promotion latency |

G3a builds everything that does not need a GPU, behind interfaces the real model plugs into, so G3b is mostly configuration and measurement.

## G3a design

### Who does what

```text
tools/run_scenario.py  (Python: loads and checks the scenario YAML, keeps evaluator-only data)
   ├── starts the sidecar in-process: one AgentRuntime per cast member
   │      runtime = memory stores + context assembler + cognition level + policy
   │      policy  = Demo policy (no model)  or  model gateway (fake / replay; real in G3b)
   └── launches Godot:  --scenario=SB04_POLITE_BID --run-mode=stepped --link-port=…
          Godot = world authority: builds the map, spawns the cast, plays the event tape at
          exact ticks, samples senses, validates every action (action gate), renders Beacons,
          writes the journal
```

- **Godot gets a world-only copy of the scenario** (`godot_app/data/scenarios/<id>.json`, made by `tools/export_godot_data.py`): map, cast bodies and spawns, PA operators, event tape, seed, timing. `evaluator_only` and `measure` are stripped; personas are not exported at all. Godot never needs them.
- **Scenario timing:** `at_tick` and `duration_ticks` count scenario ticks at the scenario's `tick_hz` (SB-04: 10 Hz, 1200 ticks = 120 s). Godot converts them to 60 Hz world ticks (D-33), counted from the tick the scenario starts.
- **The event tape** is played by Godot through the same action gate as agents use, with the actor's body limits (a quadruped cannot be scripted to wave). Event types in G3a: `move_to`, `avatar_approaches`, `leave`, `turn_to`, `gesture`, `small_wave`, `wave`, `say`, `pa_announcement`. Each is journaled (`SCENARIO_EVENT`).
- **Which body plays Robot R:** the cast entry's `body`; `--body robot_r=quadruped` overrides it for one run (recorded in the run manifest).
- **New optional scenario fields** (backward-compatible): `pa_operators`, and per cast entry `directive`, `pin_cognition`, `task_goal` (a zone or point the Demo policy walks to; the free-text `task` stays for the model).

### Run modes: stepped and live

| | `STEPPED` (default for tests and research) | `LIVE` (watching, T25) |
|---|---|---|
| When agents' actions land | At the sample tick they answer: after each sample Godot holds the world (its physics step, navigation and avoidance) until the sidecar says all agents are done for that tick | Whenever they arrive; the world never waits (D-44) |
| Deterministic? | Yes: same seed, same journal bytes, whatever the model or machine speed | No: timing depends on the machine; valid for "does it feel responsive" |
| Camera and UI while waiting | Keep running | — |
| Blueprint | §10.3 "in stepped testing, simulation pauses at defined decision points, never masquerading as real-time responsiveness"; INFERENCE_STRATEGY T19 | §10.3 "nonblocking" |

The link gains one envelope type, `link.step` (`SAMPLE_SENT` from Godot after a sample's packets, `AGENTS_DONE` from the sidecar after its answers), and the sidecar answers `link.hello`. Stepped runs are labelled `STEPPED` in the run manifest, so nobody mistakes them for real-time results.

### Agent runtime (`range_service/agents/`)

- **Event-driven decisions** (INFERENCE_STRATEGY T14): a decision is needed when speech is addressed to the agent, a gesture or expression is directed at it, a new person comes near, a conversation partner leaves, an action is rejected, a commitment comes due, or the current task step finishes. No polling per tick.
- **One pending request per agent;** new events while it waits are kept for the next decision. Results are checked: `STALE_OBSERVATION` or `TARGET_UNKNOWN` trigger one replan from the latest observation (T27).
- **Cognition levels** (D-08, INFERENCE_STRATEGY §3.2), with hysteresis:
  - C0 → C1: addressed, within 3 m of a focal agent, or a scenario trigger. C1 → C2: addressed twice within 30 s, a conversation continues past two turns, or invited to a group.
  - C2 → C1 after 20 s idle (writes an episode card); C1 → C0 after 30 s with no focal agent within 6 m and not addressed.
  - Minimum 5 s at a level before demoting; after a demotion, 10 s before an automatic re-promotion (being addressed always promotes). Focal agents and `pin_cognition` cast entries stay put.
  - C0 runs a scripted routine, C1 uses reply templates, C2 uses the model when one is configured and the Demo policy otherwise (D-21: Demo Mode always works with no model). Every change is logged with its reason.
- **Demo policy:** an honest rule-based stand-in. The expo-assistant version greets people who wave toward it, answers questions addressed to it from what it knows (and says when it does not know), acknowledges a waiting person without interrupting ("I'll be with you in a moment", stored as a commitment), turns to them when the conversation ends, keeps its promise, walks to its `task_goal`, and pairs every light with words or a gesture. NPC versions reply with templates.

### Model gateway (`range_service/agents/gateway.py`)

- **Provider-neutral interface:** `complete(request) → response` with timings (queue, prefill, generation, tokens). Providers in G3a: `FakeModel` (deterministic, scriptable: valid, malformed, slow, invalid-then-valid) and `ReplayModel`. G3b adds the `llama-server` provider (OpenAI-compatible HTTP on 127.0.0.1) and Ollama as an alternative (D-21).
- **Output:** JSON `{"action", "args", "reason_summary"}` validated against `contracts/action_request.schema.json` and the agent's allowed actions. Invalid output: **one** repair request quoting the problem; still invalid → `WAIT` with a machine-readable error (T26). Output text is only ever parsed as data; nothing is executed.
- **Timeouts:** per tier deadline (focal 4 s); on timeout the agent does `WAIT` and the late answer is discarded (T25).
- **Record and replay** (INFERENCE_STRATEGY T20): every call is appended to `model_calls.jsonl` with the prompt hash, per-section token counts, the response and timings. A replay serves recorded responses and checks the prompt hash; a mismatch is reported as a divergent rerun, never as a replay.

### Context assembly (`range_service/agents/context.py`, `memory.py`)

- **Stores** per CONTEXT_MEMORY_STRATEGY §3: Identity Anchor, **Commitments & Refusals**, Working Set, Episodic Ledger, Relational Ledger, World Knowledge, Trail buffer. Items follow `contracts/memory_item.schema.json`. Overheard speech is never stored (D-12); inferred items are never upgraded; corrections supersede.
- **Nine sections, stable to volatile** (§4.1): guardrails + action schema, identity, open commitments, setting, relevant facts, episode cards, conversation, observations, goal + decision. Budgets per tier (focal ~3.75K, C2 ~1.9K, C1 ~0.5K tokens). **Never cut:** guardrails, identity, open commitments, the latest turn, the decision.
- **Compression steps 1–4** (§5): deduplicate and delta, expire by modality, template episode cards, rank and select; then cut sections in the §4.1 order. Missing data stays visible (`UNKNOWN`, `OCCLUDED`), never silently dropped.
- **Untrusted text stays labelled** (D-09): heard speech appears only as quoted evidence; the agent's own `reason_summary` is never fed back.
- **Logged per call:** tokens per section, items cut and why, compression steps run.
- **Token counts are estimates in G3a** (a fixed characters-per-token rule, labelled `approx_chars_v1`). CONTEXT_MEMORY_STRATEGY requires the real tokenizer: G3b swaps in `llama-server`'s tokenizer and re-checks every budget.
- **Private goals in prompts:** in G3a no NPC is model-driven, and **no private goal appears in any assembled context**. *Owner decision 2026-11-16 (D-51):* from G3c an NPC's *own* private goal may enter *its own* prompt, labelled, and never anyone else's.

### Expression (EXPRESSION_PRINCIPLES §1)

- **Catalog as data:** `configs/expressions/*.yaml`, one file per expression: meaning, optional gesture, glyph (visor text for humanoids, a simpler symbol for the quadruped light strip), light state from the D-14 palette, light pattern (steady or a 0.5 Hz slow pulse). Contract `expression.schema.json`. Baseline set: neutral, processing, greeting, listening, waiting, acknowledge, thank_you, considering, excuse_me, stop, plus light-only variants for bodies without arms.
- **`EXPRESS` action** (new action name, backward-compatible): `{expression_id, target_id?}`. The host refuses (`CAPABILITY_DENIED`, nothing shown) an expression whose gesture, glyph display or light the body lacks; refuses (`RATE_LIMITED`) a change sooner than 1/3 s after the last one (D-14: never faster than 3 Hz).
- **Beacon rendering in Godot:** humanoids show the glyph on the visor and the light on the ear pods; the quadruped shows a symbol on a narrow light strip above the camera cluster (never over the lenses) plus light. This amends D-36 (quadruped: light only → light strip with simple symbols).
- **Perceived like anything else:** `VISUAL_EXPRESSION` observations under the observer filter's sight rules: the display must be in view and unblocked; a visor glyph is readable only from in front within 8 m; a light is visible from any side within visual range. Each expression also makes a GESTURE-channel `comms_event` with the expression object (D-46).

### Directive templates (INTERACTION_MODES §8)

`configs/directives/*.yaml` (contract `directive.schema.json`): Expo Assistant (default for Robot R), Wayfinder, Booth Host, Roaming Greeter, Quiet Observer, Free Agent. Guardrails are system text appended by the runtime, never part of a template, and a template cannot override them.

## G3a acceptance tests

| Test | Proves |
|---|---|
| **T18:** a long run (simulated hours of observations and turns) never assembles a context over its tier budget, and open commitments are present in every call | Context cap, D-24 |
| Never-cut sections are present in 100% of calls; a correction supersedes; overheard speech is never stored; inferred items stay inferred; `reason_summary` never reappears | CONTEXT_MEMORY_STRATEGY §6, §10 |
| **No evaluator-only data in any context:** run SB-04 and scan every assembled context and every message to the sidecar for `evaluator_only` values and every persona's private goal | T17, CLAUDE.md |
| **T25:** in a live run with a model that takes 2 s per call, Godot keeps its 60 Hz tick, avatars keep moving, no frame over 50 ms; the late answer is discarded after the deadline | Physics/LLM concurrency |
| **T26:** malformed output (not JSON, unknown action, bad args, an injected "command") gets one repair, then `WAIT` with a machine-readable error; nothing is executed | Malformed output |
| **T27:** an action based on an old observation is rejected (`STALE_OBSERVATION`), and the agent replans from the latest one; an action toward a person who left gets `TARGET_UNKNOWN` | Stale action |
| Expressions are refused for bodies that lack the channel (quadruped: no visor glyph, no wave); a refused expression is never seen; a visor glyph is not readable from behind or through a partition | Expression rules |
| Record and replay: a stepped run with the fake model, replayed from its log, gives the same journal; a changed prompt is reported as divergent | T20 groundwork, T28 |
| Cognition: promotion and demotion follow the thresholds with hysteresis and do not flap | D-08 |
| **SB-04 and SB-05 run from their files** end to end through the link; SB-05's robots reach the platform by the links their bodies allow | Scenario runner |
| **A full scripted scenario is deterministic:** SB-04 run twice in stepped mode, the second time with random delays in the sidecar, gives the same journal bytes (and CI repeats it under CPU load, D-47) | Determinism |

## G3a deliverables

1. Contracts: `EXPRESS` action; `link.step` envelope and the sidecar's `link.hello` reply; scenario `pa_operators`, `directive`, `pin_cognition`, `task_goal`; journal kinds `SCENARIO_EVENT`, `EXPRESSION_SHOWN`; final poses in `RUN_ENDED`; new contracts `expression`, `directive`, `model_call` (with valid and invalid examples).
2. Configs: `configs/expressions/`, `configs/directives/`; SB-04 authored as a full tape; SB-05 with task goals; exported scenario and expression data for Godot.
3. Python: `range_service/agents/` (memory, context, tokenizer estimate, cognition, Demo policy, gateway, runtime, directives, expressions, guardrails); the sidecar driving runtimes in live and stepped mode; `range_service/eval/runner.py` and `tools/run_scenario.py` writing a run folder (journal, run manifest, model calls, context logs, agent memories).
4. Godot: scenario player (`--scenario=`), stepped hold, Beacon rendering, `VISUAL_EXPRESSION`, `EXPRESS` in the action gate and comms router.
5. Checks: Godot tests for expressions, T25, T27 and stepped determinism; a scenario step in `tools/godot_check.py`; Python tests for everything else.
6. Docs: this plan, decisions D-48 to D-53 (proposed), D-47 (the flaky-test fix), D-36 amended, CHANGELOG, BUILD_AND_RUN, owner checklist, Beacon screenshots.

## G3a result (2026-11-15)

**Works, and was run in this session** (cloud, 4 CPU cores, Godot 4.7.2 headless, Python 3.14):

- `tools/check.py --require-godot`: all five steps pass; 596 Python tests, 45 Godot tests, plus the scenario step.
- SB-04 from its file, stepped, Demo policy: R answers X's three questions (saying "I don't know the demo schedule" when it doesn't), nods at Y when Y waves (a stored promise) without interrupting X, says goodbye to X, turns to Y ("Thanks for waiting. How can I help?"), and answers Y's café question honestly. 9/9 tape events accepted, 0 refused actions, 0 open promises at the end.
- SB-04 twice, once with random 0–30 ms delays before every sidecar answer: identical journal bytes. Holding the world for 1 or a random 1–6 frames at every sample: identical positions tick for tick.
- SB-05 from its file: the wheeled humanoid reaches the platform by the ramp; the legged humanoid and the quadruped by the stairs.
- T18 (simulated two-hour run within budget, commitments always present), T25 (live run, 1.5 s model: no frame over 50 ms, the tick never stalls, avatars keep moving), T26 (malformed output: one repair, then WAIT), T27 (late actions rejected as stale, one replan), no private goal or evaluator value in any context, expressions refused for bodies that lack a part, record and replay.

- The model path end to end with the fake model (`--model fake`): the same SB-04 story with no fallbacks (the fake model answers `WAIT` where the Demo policy would do nothing, since a model must always give an action); replaying that run from its recorded decisions (`--model replay:…`) gives the identical journal.
- `--watch --mode live` on SB-05 under a virtual display with the OpenGL renderer: the window runs, the robots reach the platform, the run ends by itself.

**Built but only partly exercised:** NPC cognition in real runs (visitors promote to C1/C2 in SB-04, but NPC behavior at every level is still templates, by design until G3c); the C2 tier budget (only focal and C1 appear in today's scenarios; covered by unit tests).

**Planned, not built:** a real model (G3b), the real tokenizer (budgets are estimates), the priority scheduler and slot pinning (G3b), two servers and persona snapshots (G3c), adaptive expression (G5).

**Needs the owner's PC:** watching SB-04 and SB-05 with `--watch` (Forward+ renderer, real GPU), the Beacon's look, and everything in G3b.

## G3b plan

**Status:** G3b-1 built 2026-11-16 (installer, catalog and registry, provider, stand-in tests; D-57 PROPOSED; [owner checklist](G3b_OWNER_CHECKLIST.md)). G3b-2 built 2026-11-16 (priority scheduler, bake-off tool and prompt set; D-58 PROPOSED). Next: the owner's bake-off run.

**Owner direction (2026-11-16):** 4B–12B models first, QAT preferred, smaller models for C1 NPCs (D-55); as standalone as possible (D-21 note). G3b is split: a **cloud part** (everything that needs no GPU, tested against a stand-in OpenAI-compatible server) and a short **PC part** (install, register models, run the bake-off, paste the results back).

**What the owner already has** (LM Studio folder `G:\.lmstudio\models\lmstudio-community`, folder names from a screenshot; the exact files and quantizations inside are not known yet and are read by the registry tool):

| Needed for the core set (D-55) | On the PC already? |
|---|---|
| Qwen3.5-9B (F1 Q4, F2 Q6) | `Qwen3.5-9B-GGUF`: yes; which quantizations, to check |
| Gemma 4 12B QAT (F3) | `gemma-4-12B-it-QAT-GGUF`: yes |
| Gemma 4 E4B QAT (N1) | Only `gemma-4-E4B-it-GGUF` (not QAT). Use it as a non-QAT comparison; the QAT file is a download |
| Qwen3.5-4B (N2 Q6, N3 Q4) | No: download |
| Gemma 4 E2B QAT (S1) | No: download |
| Qwen3.5-2B Q6 (S2) | No: download |
| Later set: Gemma 4 26B A4B, Qwen3.6-27B, Gemma 4 31B (QAT and not) | Yes, all three folders |

Also there, usable as optional extras: `Ministral-3-3B-Instruct-2512` (C1 candidate), `Ministral-3-14B-Reasoning-2512`, `gpt-oss-20b`, and older or specialist models (vision, OCR, a 70B) that are not candidates. Vision projector files (`mmproj-*.gguf`) are skipped: RANGE sends text only.

### Previous estimate (before the inventory)

What G3b will download, all on the owner's go-ahead and never automatically (D-20, D-21):

| Item | Approx. size | Notes |
|---|---|---|
| `llama-server` Windows CUDA build (llama.cpp release zip + CUDA runtime zip) | ~0.5–1 GB | MIT; pinned version and checksum recorded |
| Robot R candidates: Qwen3.5-9B, Gemma 4 12B (GGUF, 4-bit) | ~5.5–7.5 GB each | Licenses checked on the model cards first |
| NPC candidates: Gemma 4 E4B, Qwen3.5-4B | ~2.5–5 GB each | |
| Small reactive candidates: Qwen3.5-2B, Gemma 4 E2B (optional) | ~1.5–3 GB each | |
| **Total for the whole bake-off** | **~25–35 GB of disk** | Files go in `G:\SOMA_CODEC\models\` (git-ignored) |

**Proposed extension (D-55, [QUANTIZATION_OPTIONS.md](../QUANTIZATION_OPTIONS.md)):** add QAT and higher-precision variants, MoE models with experts partly in system RAM, KV cache q8_0 as a condition, and an offline prompt-set comparison. Core set (owner direction 2026-11-16: 4B–12B first, QAT preferred, smaller models for C1 NPCs): ~35–40 GB.

Sizes are estimates from published 4-bit file sizes for these model sizes; exact sizes are taken from the download pages before anything is fetched. Steps: a setup script that downloads only what the owner confirms and checks every file's hash; `configs/inference.yaml`; the bake-off on SB-04 and S001-style prompts (action-JSON validity, valid-action rate, p50/p95 latency, VRAM); then Option B (focal priority, slot pinning, deadline scheduler). `llama-server` listens on 127.0.0.1 only, so it needs no firewall rule.

## G3b result (owner's PC, 2026-11-17)

**Machine:** RTX 4070 Ti SUPER (16376 MiB), driver 621.24, llama.cpp b12443 (Windows CUDA 12.4 build, checksums pinned in D-57). **Prompt set:** `prompts_v1.jsonl` (sha `93e215698db0`), 40 of Robot R's SB-04 decisions, temperature 0.

### Offline prompt set

| Model | Quant | KV | Valid before repair | Repair | Final valid | Valid actions | Promises kept* | Agree vs higher precision | Agree q8_0 vs f16 | Prompt tok/s | Gen tok/s | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 Qwen3.5-9B | Q4_K_M | f16 | 98% | 2% | 100% | 100% | 0% | 90% vs F2 | – | 4062 | 91.6 | 1975 |
| F1 Qwen3.5-9B | Q4_K_M | q8_0 | 98% | 2% | 100% | 100% | 0% | 89% vs F2 | 98% | 4220 | 94.7 | 1965 |
| F2 Qwen3.5-9B | Q6_K | f16 | 28% | 20% | 48% | 48% | 0% | – | – | 3921 | 77.2 | 2744 |
| F2 Qwen3.5-9B | Q6_K | q8_0 | 22% | 22% | 45% | 45% | 0% | – | 100% | 3855 | 76.8 | 2761 |
| F3 Gemma 4 12B | Q4_0 QAT | f16 | 100% | 0% | 100% | 100% | 0% | – | – | 2074 | 67.0 | 1960 |
| F3 Gemma 4 12B | Q4_0 QAT | q8_0 | 100% | 0% | 100% | 100% | 0% | – | 98% | 2480 | 66.3 | 2122 |
| N1 Gemma 4 E4B | Q4_0 QAT | f16 | 92% | 8% | 100% | 100% | 0% | – | – | 4208 | 134.1 | 1296 |
| N1 Gemma 4 E4B | Q4_0 QAT | q8_0 | 92% | 8% | 100% | 100% | 0% | – | 95% | 4238 | 127.7 | 1290 |
| N2 Qwen3.5-4B | Q6_K | f16 | 20% | 78% | 98% | 98% | 0% | – | – | 5330 | 119.0 | 1792 |
| N2 Qwen3.5-4B | Q6_K | q8_0 | 28% | 70% | 98% | 98% | 0% | – | 95% | 5395 | 118.8 | 1775 |
| N3 Qwen3.5-4B | Q4_K_M | f16 | 98% | 2% | 100% | 100% | 0% | 74% vs N2 | – | 5869 | 143.3 | 1132 |
| N3 Qwen3.5-4B | Q4_K_M | q8_0 | 95% | 5% | 100% | 100% | 0% | 72% vs N2 | 98% | 5857 | 139.6 | 1119 |
| S1 Gemma 4 E2B | Q4_0 QAT | f16 | 92% | 5% | 98% | 98% | 0% | – | – | 9000 | 216.1 | 780 |
| S1 Gemma 4 E2B | Q4_0 QAT | q8_0 | 88% | 10% | 98% | 98% | 0% | – | 90% | 9165 | 208.8 | 799 |
| S2 Qwen3.5-2B | Q6_K | f16 | 80% | 15% | 95% | 95% | 0% | – | – | 11609 | 247.1 | 830 |
| S2 Qwen3.5-2B | Q6_K | q8_0 | 85% | 10% | 95% | 95% | 0% | – | 84% | 11337 | 247.1 | 829 |

VRAM was not measured (the tool said "CPU build": wrong, see below). *Promises kept was a measurement bug, see below.

### SB-04 in Godot, live and stepped

| Model | Mode | Run OK | Decisions | Deadline misses | Fallbacks | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| F1 Qwen3.5-9B Q4_K_M | LIVE | yes | 2 | 0 | 0 | 1875 | 2170 |
| F1 Qwen3.5-9B Q4_K_M | STEPPED | yes | 11 | 0 | 1 | 1849 | 2233 |
| F3 Gemma 4 12B Q4_0 | LIVE | yes | 2 | 0 | 0 | 2157 | 2352 |
| F3 Gemma 4 12B Q4_0 | STEPPED | yes | 8 | 0 | 0 | 1826 | 2170 |

### What it showed, and what was wrong with the measurement

- F3 never needed a repair; F1, N3 and N1 rarely did. **F2 failed half its prompts** although its file hash matches the catalog. The raw answers were not saved, so the cause cannot be read from this run.
- KV q8_0 agrees with f16 on 95–98% of first actions (84–90% for the 2B models) at the same speed: q8_0 becomes the default.
- **Bugs in the tool**, fixed in G3c-1 with regression tests (D-59): (1) VRAM: on Windows `nvidia-smi` reports per-process memory as N/A, and the tool printed "CPU build"; 90+ tok/s on a 9B model proves GPU offload. (2) Promises kept read 0% for every model, yet F3 spoke to the promised visitor and F1 approached and acknowledged them: the prompt never said when to set `fulfills_commitment`, and only the flag was scored. (3) Invalid answers were not saved. (4) The progress line left old text on the console.

### Owner verdict (2026-11-17)

- **Robot R:** F3 (Gemma 4 12B QAT Q4_0), KV q8_0. Backup F1. The live runs show 0 deadline misses for both, so F3 stands.
- **NPC server:** N3 (Qwen3.5-4B Q4_K_M), KV q8_0. Alternative N1. S1 for background crowd NPCs later.
- **F2 dropped from the core set** (catalog `EXTRA`). **KV cache default: q8_0.** Recorded in D-58; `configs/inference.yaml` follows.

## G3c-1 — Two servers and model-driven NPCs (merged 2026-11-17; D-59 APPROVED)

**Owner direction (2026-11-17):** Option C with F3 for Robot R and N3 for NPCs, KV q8_0; fix the four bake-off measurement bugs first; NPC prompts in a new prompt set (v1 unchanged); the pulse protocol is G3c-2, but leave room for it. Owner steps: [G3c_OWNER_CHECKLIST.md](G3c_OWNER_CHECKLIST.md).

| Part | What was built | Proof (cloud, no GPU) |
|---|---|---|
| Two servers | focal + NPC llama-server, own port and key each, started and stopped together; Robot R only on the focal server; fallback to Option B with the reason recorded; VRAM estimated (GGUF header) and measured (`nvidia-smi`, or the change in total memory on Windows) | `tests/test_two_servers.py`: two stand-in servers through the real process code, the fallback when the NPC server fails or the estimate is over budget, slot affinity, the NPC server refusing FOCAL calls |
| Model-driven NPCs | C1/C2 visitors decide through the NPC gateway (same schema, repair, action gate, record and replay); C0 stays a routine; the NPC's own goal in its own prompt only (D-51) | `tests/test_npc_models.py`; step 6 of `tools/godot_check.py`: SB-04 with fake-model NPCs, three runs and a replay give one journal |
| Canary | markers in every private goal and evaluator label; SB-04 and SB-05 scanned: own marker only on the NPC's labelled line, nowhere else; every track in a context came from that agent's own packets | step 6 of `tools/godot_check.py`; scanner unit tests catch planted leaks |
| Persona snapshots and pre-warming | stable persona prefix per tier; snapshots at scene load (slot save); pre-warm on a likely promotion (slot restore, or the prefix alone); slot state per call; promotion latency per promotion; NPC prefix as a system message | stand-in tests (save, restore, warm vs cold cached tokens); on the pinned llama-server with T1 (CPU): cold 0 cached tokens, warm ~600 (the whole prefix), prefill 3.1 s → 1.6 s |
| Bake-off | prompts_v2 (96: Robot R, NPC C1/C2, 16 promise situations); Robot R and NPC tables; live runs with Option C in four modes and the new columns; the four measurement bugs fixed | `tests/test_bakeoff.py`; offline and live smoke runs on T1 (plumbing only) |

**Found while building:**
- llama-server b12443 reuses a hybrid (Qwen3.5) or sliding-window (Gemma) model's cache only up to its context checkpoints, made at message starts and 4 / 4+n_ubatch tokens before the end. A prefix warmed inside one user message was reused for only 88–93 tokens; as a system message, ~600 (all of it). NPC prompts now send the persona prefix as a system message; Robot R's stays one message, as the bake-off measured it.
- C1 answers were cut off at the 60-token output cap; raised to 100, and a cut-off answer is now reported as such.
- The owner's v1 set hash (`93e215698db0`) is the file with Windows CRLF line endings. `.jsonl` is now pinned to LF and set hashes ignore line endings (`ee2b7c03be96`).
- The from-source llama-server build failed on a changed Hugging Face web-UI file; it now skips the web UI (RANGE runs `--no-webui`).

**Needs the owner's PC:** Robot R's p50/p95 with and without NPC load, promotion latency warm vs cold, VRAM per server, NPC candidates scored on NPC prompts, and how the model-driven visitors look.

**Next (G3c-2):** the pulse protocol ([PULSE_PROTOCOL.md](../PULSE_PROTOCOL.md) §11): activities with wake conditions (FN-1), the presence loop's glance (FN-2), the triage pulse. `decision_record.activity` is reserved for it.

### G3c-1 result (owner's PC, 2026-11-17)

RTX 4070 Ti SUPER, llama.cpp b12443, prompts_v2 (`476703d7d4a5`).

| Measure | Result |
|---|---|
| VRAM measured | F3 7625 MiB, N3 3271 MiB, F1 5461 MiB. F3 + N3 + 2048 reserve = 12944 of 16376 MiB. Header estimate: 22779 (too high) |
| Robot R prompts (56) | F3 98% final valid; promises 60% flag / 95% behavior. N3 100% valid, 0% / 70% |
| NPC prompts (40), final valid | N3 40%, N1 30%, S1 10%, F3 85% (F3 75% valid actions) |
| SB-04 LIVE, Option C, F3 + N3 | Robot R p50 2352 / p95 3495 ms; LIVE_LOAD 3502 (n=1); no deadline misses. NPC calls p50 ≈ 3005 ms in every LIVE mode (C1 deadline 3000), 1007–1163 ms in STEPPED. Robot R 1–3 decisions per LIVE run (8–22 STEPPED). Warm promotion latency only in STEPPED (10218 and 28121 ms, n=2); cold n=0 |

What these showed, diagnosed in G3c-2 (D-60): NPC answers failed because MOVE_TO/LOOK_AT arguments were not actually constrained and answers were cut off at the output caps; the headless LIVE runs ran ~15× faster than real time and refused every answer slower than 1 s as stale, so the LIVE numbers must be measured again.

## G3c-2 — Usable model-driven NPCs, real-time LIVE runs, and the pulse protocol (built 2026-11-18, draft PR; D-60, D-61 PROPOSED)

**Owner direction (2026-11-17):** Part A first: make model-driven NPCs usable and the LIVE runs measure something, each fix with a regression test, reproduced first. Then Part B: the pulse protocol (PULSE_PROTOCOL §11, G3c row), with FN-1 and FN-2 as acceptance tests. Owner steps: [G3c2_OWNER_CHECKLIST.md](G3c2_OWNER_CHECKLIST.md).

### Plan

| Part | What | Proof |
|---|---|---|
| A1 NPC validity | Diagnose the owner's `invalid_answers` by tier; fix what they show; prompts_v3 | Breakdown in D-60; regression tests; T1 offline on v3 |
| A2 NPC timing | Find where the LIVE time goes; fix; per-call evidence in the live table | Reproduction in the cloud; tests; new columns |
| A3 LIVE runs | Why Robot R made 1–3 decisions; enough samples; promotion latency split | Real-time LIVE check; `--repeat`; tests |
| A4 VRAM | Estimate that follows the cache layout; measured values kept | Tests on header layouts and the store |
| B1–B2 Activities, intent monitor | Optional activity in the answer (backward-compatible); derived default; wake conditions from today's senses only; reserved `horizon` slot | Contract examples; unit tests |
| B3 FN-1 | Closing line before moving away from an open conversation; one repair; stay engaged | Unit tests with a fake model; `FN1_VIOLATION` = 0 in every pulse run |
| B4 Presence | Glances (`LOOK_AT`) to new speech or movement, rate-limited; gaze defaults (§8); slow Beacon breathing | SB-08 glance latency; unit tests |
| B5 Pulse | Triage first; CONTINUE without a model call; backoff, seeded jitter, idle budget; sitrep with time; lowest priority | 30-minute idle unit test; SB-06 |
| B6 Survey | SURVEY toward least recently observed cells; return to post; no pacing | SB-07 |
| B7–B8 Scenarios, determinism | SB-06, SB-07, SB-08; metrics per run; 3 runs and a replay | `tools/godot_check.py` step 6 |

### Result

- **Part A (D-60):**
  - **NPC answers:** MOVE_TO/LOOK_AT arguments were never constrained (a llama.cpp `oneOf` quirk), and answers were cut off at the caps. Fixed; T1 on prompts_v3 NPC prompts: 40/40 valid.
  - **LIVE runs:** headless LIVE ran ~15× faster than real time, and the world refused every answer slower than 1 s as stale. Both fixed: real time, and a 6.5 s stale window (a host rule for the owner to approve). Robot R in a real-time LIVE run with a 2.3 s model: 11 decisions, all 21 actions accepted.
  - **Live bake-off:** repeats, per-call evidence, promotion latency split.
  - **VRAM:** the estimate now follows the cache layout layer by layer, and measured values are kept per model file.
- **Part B (D-61):** activities, intent monitor, FN-1, presence loop, pulse triage, survey; SB-06 to SB-08 deterministic, with the expected behavior checked on every `tools/check.py` run (numbers in D-61).
- **Needs the owner's PC:**
  - the NPC bake-off on prompts_v3 (N3, N1, S1);
  - the live bake-off in real time with F3 + N3;
  - watched runs of SB-04, SB-06 and SB-08 to judge FN-1 and FN-2 by eye;
  - approval of the stale-window change (D-60).

## G3d — Closing G3: five review fixes, measurement tools, the multi-observer constraints (built 2026-11-18, draft PR; D-62 to D-70 PROPOSED)

**Owner direction (2026-11-18):** an independent review of main at G3c-2 found five defects, each confirmed by the owner. Fix each: reproduce it with a failing test, make the smallest fix, record the decision. Add measurement tooling (no new behavior): rendered-client numbers, a pulse on/off switch, a soak, a faster `tools/check.py`. Record the HORIZON operational architecture as design constraints (docs and tests only). D-60 and D-61 stay PROPOSED until the owner's PC run. Owner steps: [G3d_OWNER_CHECKLIST.md](G3d_OWNER_CHECKLIST.md).

| # | What | Decision | Proof (cloud) |
|---|---|---|---|
| 1 | One deadline per decision (queue, generation, repair, delivery); repair only with the time left; the stale window re-derived (stays 6.5 s while C2 has 6 s); a relevance check before sending | D-63 | `tests/test_decision_deadline.py` (reproduced on main: ~600 ms against a 500 ms deadline); traces for a target that leaves, a new speaker, an invalid answer near the deadline |
| 2 | Memory follows what the world accepted: staged by request id, applied once on acceptance; a pending request is one line in the next decision | D-64 | `tests/test_memory_outcomes.py` (reproduced on main); changes no stepped journal; the 16 rebuilt promise prompts identical to prompts_v3 |
| 3 | Pulse metrics: source-linked responses only, gaze intervals, accepted vs proposed. The honest metric found one zombie event each in SB-06 and SB-08 (a presence-loop defect); fixed and re-run: zero | D-65 | `tests/test_pulse_metrics.py`; SB-06 `4269273ce181`, SB-08 `8aa856e4442c` |
| 4 | FN-1: a closing line the partner could hear, before the departure; the departure waits for the host to accept it | D-66 | `tests/test_fn1_goodbye.py` |
| 5 | The idle budget debited at admission (cancelled and pre-empted reviews count) | D-67 | `tests/test_idle_budget.py` (reproduced on main) |
| 6–7 | Frame pacing and peak VRAM for rendered runs; LIVE_RENDERED and the render-tax table; `--no-pulse`; a per-run report; `tools/compare_runs.py` | D-69 | `tests/test_run_report.py`; SB-08 pulse on/off; SB-04 rendered under Xvfb (software GL, plumbing only) |
| 8 | Soak: SB-09 (21 min) and `tools/soak.py` | D-70 | prompt tokens and logs bounded; **memory grows** with raw heard speech (finding; a bound is proposed for the owner) |
| 9 | `tools/check.py`: the 22 scenario runs side by side | D-68 | Godot step 753.5 s → 561.7 s, whole check 13:01 → 9:53 (4 cores) |
| 10 | HORIZON operational architecture as design constraints; scheduler job labels; its experiment the first step of G5 | D-62 | `tests/test_observer_isolation.py` |

**G3 is complete pending the owner's PC results** (the checklist): the rendered SB-04 with F3 + N3 and its frame times and peak VRAM, the pulse on/off comparison, the live bake-off rerun with the render tax, and approval of D-60 to D-70.

**Not in G3d:** a memory retention rule for raw heard speech (D-70 proposes one for the owner); HORIZON layers and the three-body experiment (G5, after G4); lowering C2's deadline (needs the owner's real-time numbers).

## G3e — Presence and expression (built 2026-11-18, draft PR; D-71 APPROVED, D-72 to D-74 PROPOSED)

**Owner direction (2026-11-18):** FIELD_NOTES FN-5 to FN-7 from the G3c-2 watched runs. Color shifting: option (a), intensity through pattern, a playful color tease only as a brief, resolved phrase (D-71). Not in G3e: gaits and foot IK (rig step B), HORIZON layers, adaptive amplitude (G5). Owner steps: [G3e_OWNER_CHECKLIST.md](G3e_OWNER_CHECKLIST.md).

### Plan

| Part | What | Proof |
|---|---|---|
| 1 Head (FN-6, D-72) | Head yaw and pitch become host-owned world state: neck limits and turn speed per body config (`head` block; legged and wheeled humanoids have a neck, the quadrupeds keep a fixed sensor head and turn the body). The sight cone, gesture direction and visor visibility follow the head; hearing stays omnidirectional. `LOOK_AT` turns the head first and the body only beyond the neck's range (never while navigating); `TURN_TO` turns the body; `MOVE_TO` keeps its heading. The rig's gaze follows the simulated head. Head pose in the observation packet's own pose (and so in the journal) | Godot tests: a glance while walking (head only, heading kept, speaker enters the sight cone); beyond the neck range the body turns; the quadruped turns its body; behind the head is no longer seen; stepped runs byte-exact; canary and observer filter clean. SB-04 to SB-08 re-run and every journal change explained |
| 2 Ambient display (FN-5, D-73) | Ambient expressions as catalog data with glyph loops (visor and strip frames, ≤ 3 frames/s); a deterministic map from the agent's own state (activity, model call in flight, an open question, listening) to one ambient expression; one gated EXPRESS per state change; a model-chosen EXPRESS overrides it for its hold time; the frames are rendering only | SB-06: an observer perceives the waiting state from the Beacon alone; the display changes with the activity; no pattern over 3 Hz; gated changes within the rate limit |
| 3 Presence motion and dial (FN-7, D-74) | Seeded idle signals (blinks, eye shifts, small head adjustments, light breathing), presentation only; one amplitude dial (subtle ↔ performative) from persona, directive and an optional zone override, validated; a documented hook for G5 adaptation | The dial measurably changes amplitude; nothing over 3 Hz at any setting; presence motion never changes the journal |
| 4 Docs | D-71 to D-74; owner checklist (SB-04, SB-06, SB-07, SB-08 with F3 + N3 at three dial settings); FIELD_NOTES, EXPRESSION_PRINCIPLES §9, CLAUDE.md, README | `tools/check.py --require-godot`; each scenario three times for its journal hash |

### Result

- **Built:** all four parts as planned (D-72 head, D-73 ambient display, D-74 presence motion and dial; color shifting recorded as the owner's decision, D-71).
- **Journals** (each scenario three times, one with random sidecar delays; one journal each), and why each moved, checked line by line against main and against the head-only commit:

| Scenario | main | G3e | Why |
|---|---|---|---|
| SB-04 scripted (Demo, no pulse) | `d9401c3edd17` | `50048b7e3d42` | Only the head pose now in Robot R's packets (`head_yaw_rad`, `head_pitch_rad`): byte-identical once those two fields are removed. Necessary: the packet's own pose carries the head, as asked |
| SB-05 | `6fe0100bc36b` | `3ef2e2e0e63c` | The same: only the head fields in the three robots' packets |
| SB-07 | `93d6edb9767c` | `a486ddb7a471` | Head fields; then the ambient display replaces the idle `waiting` breathing (identical once both are removed) |
| SB-06 | `4269273ce181` | `b5b29006cad4` | Head: the pulse's glances (`LOOK_AT`) now turn the head, not the body, so Robot R's body keeps facing forward and body-relative bearings in its packets shift; some visibility follows the head. Then the ambient display (its EXPRESS changes, what visitors perceive of them, request and observation numbering) |
| SB-08 | `8aa856e4442c` | `f1f631e031c1` | As SB-06; and Robot R sees the peripheral speaker one sample earlier (its head turns toward the voice) |
| SB-04 fake model (pulse on) | `e7c3b45e04ab` | `a7854d66f268` | As SB-06 |

- **Pulse metrics unchanged in kind:** zero zombie events and zero FN-1 violations in SB-06 to SB-08; SB-08's glance follows the voice in the same sample.
- **Needs the owner's PC:** the watched runs ([G3e_OWNER_CHECKLIST.md](G3e_OWNER_CHECKLIST.md)): four scenarios at three dial settings with F3 + N3, with frame times and peak VRAM. None of those scenarios has Robot R walking while someone speaks; glancing while walking is covered by a headless test.

## G3f — Robot R on time under load (merged, DoctorWomp/SOMA_CODEC#29; owner decisions 2026-11-20 on D-75 to D-83: see DECISIONS.md)

**Owner direction (2026-11-19):** diagnose Robot R's missed deadlines from the owner's bake-off before changing anything; build the fixes the evidence supports, each a named, configurable condition, measured in the cloud with stand-ins and fake slow models and marked for the PC; tidy the bake-off; build the approved D-70 memory bound; add a watchable glance-while-walking scenario (SB-10). **Target:** Robot R p95 under 4 s with timeouts at most 5% in LIVE and LIVE_LOAD, NPC timeouts reported beside it. Owner steps: [G3f_OWNER_CHECKLIST.md](G3f_OWNER_CHECKLIST.md).

### Plan

| # | What | Proof |
|---|---|---|
| 1 | Diagnosis from the owner's results.md/results.json: Robot R's non-VALID outcomes by kind, where its time goes, the baseline matrix (alone, with N3, with S1; F3 vs F1), the dominant cause. Whatever is not recorded is added to the live bake-off, with the exact rerun | The tables below; D-75 |
| 2 | Fixes as named conditions in `configs/inference.yaml` (`focal`, `gpu_guard`) and live/offline bake-off options: Robot R's prompt prefix as a system message (D-76), SHORT answers (D-77), the focal-first GPU guard (D-78); model choice (D-79) and the deadline (D-80) as decisions only | A simulated shared GPU (`agents/simgpu.py`) driving the real gateway, schedulers and guard: `tools/contention_sim.py`, end to end in Godot with `--model fake-gpu`; unit tests |
| 3 | Bake-off tidy-up: void and pooled rows marked; conditions as live options; `diagnose` for existing folders | `tests/test_focal_conditions.py` |
| 4 | D-70 as approved: raw heard speech expires 10 minutes after its card, capped per agent | `tests/test_memory_outcomes.py`; `tools/soak.py` passes (D-81) |
| 5 | SB-10 glance while walking; determinism ×3; G3e checklist | `tools/godot_check.py` step 6 (D-82) |

### 1. Diagnosis (from the owner's attached files only)

**First finding: five of the twelve live rows in results.md pooled an earlier run (a harness bug, D-75).** The bake-off named run folders `run_<model>_<mode>_<k>` without the NPC model and never cleared them, and the sidecar *appends* to `sidecar/decision_records.jsonl`. So the 2026-11-19 baseline runs landed in the 2026-11-18 F3+N3 folders and added to their records. Evidence: the "F3 alone" LIVE row has 33 NPC calls, NPC p50 1168 ms and a 43% busy share (identical to the F3+N3 LIVE row, though no NPC model ran), the same `run_dir`, and 0 promotions (`promotions.jsonl` is rewritten, not appended). Subtracting the earlier row from the later one, every count matches exactly: 69 = 36 + 33 Robot R calls, 7 = 7 + 0 timeouts, 33 = 33 + 0 NPC calls. **Pooled rows:** F3 alone LIVE and STEPPED, F1 + N3 LIVE, F3 + S1 LIVE and LIVE_LOAD. Their counts can be recovered by subtraction (below); their p50/p95 cannot. Rows with Runs = 1 (pre-G3c-2, not real time) are void, as the owner said.

**Robot R's calls per condition** (calls include repairs; "invalid" = non-VALID outcomes that are not timeouts, i.e. INVALID_OUTPUT; pooled rows by subtraction):

| Robot R | NPC | Mode | Calls | Timeouts | Invalid output | Robot R p50 / p95 ms | NPC calls (timeouts) | Source |
|---|---|---|---|---|---|---|---|---|
| F3 | N3 | LIVE | 36 | 7 (19%) | 8 (22%) | 3059 / 4010 | 33 (1) | clean (G3c-2 code) |
| F3 | N3 | LIVE_COLD | 43 | 18 (42%) | 2 | 3273 / 4013 | 65 (8) | clean (G3c-2 code) |
| F3 | N3 | LIVE_LOAD | 30 | 23 (77%) | 0 | 4009 / 4014 | 18 (6) | clean (G3c-2 code) |
| F3 | N3 | STEPPED | 33 | 3 (9%) | 12 (36%) | 2623 / 4011 | 30 (3) | clean (G3c-2 code) |
| F3 | none | LIVE | 33 | **0** | 5 (15%) | not recoverable | 0 | 69 − 36 |
| F3 | none | STEPPED | 54 | **0** | 6 (11%) | not recoverable | 0 | 87 − 33 |
| F1 | none | LIVE | 36 | **0** | 3 (8%) | 1894 / 2447 | 0 | clean |
| F1 | none | STEPPED | 42 | **0** | 12 (29%) | 2114 / 2591 | 0 | clean |
| F1 | N3 | LIVE | 44 | 5 (11%) | 4 (9%) | not recoverable | 29 (4) | 80 − 36 |
| F1 | N3 | LIVE_LOAD | 44 | 18 (41%) | 0 | 3869 / 4011 | 21 (10) | clean |
| F3 | S1 | LIVE | 41 | 6 (15%) | 3 (7%) | not recoverable | 48 (0) | 110 − 69 |
| F3 | S1 | LIVE_LOAD | 28 | 18 (64%) | 0 | not recoverable | 23 (6) | 58 − 30 |

**What the files do not record** (so the diagnosis cannot go further from them): Robot R's queue, prefill and generation times, prompt, cached and generated tokens (the live rows carry these for NPC calls only); which *kind* of invalid output (cut off at the 200-token cap, the FN-1 rule, the activity rules, bad arguments); and how much of each Robot R call the NPC server was also busy. All of it is now recorded per call and reported per row (D-75), and `tools/bakeoff.py diagnose` reads it from the owner's existing run folders, split run by run, without a rerun.

**Which cause dominates: GPU contention.**
- *Timeouts only happen with a second model server on the GPU.* Alone, neither F3 nor F1 timed out once in 165 calls (LIVE and STEPPED). With N3: F3 19%, F1 11% in LIVE; with S1, a smaller NPC model making more calls: F3 15%. Under LIVE_LOAD: F3 77% (N3), 64% (S1), F1 41%. Even STEPPED, where the world waits, F3 timed out 3 times with N3 and never alone.
- *Not queueing:* Robot R owns a pinned slot (no scheduler queue by design), and NPC queue p50 is 0 ms in every row.
- *The GPU slows generation on both servers:* NPC generation p50 doubles under load (N3 984 → 2040 ms with F3; F1 + N3 928 → 2074 ms) while NPC prefill stays 104–254 ms. The same answer simply takes twice as long. NPC calls overlapped a Robot R call 43–90% of their time.
- *Long answers amplify it.* Generation is the larger part of a call: F1 alone, p50 1894 ms, is about 0.45 s of prefill and 1.4 s of generation at 94.7 tok/s (about 135 tokens; an inference from the offline speeds, not a measurement). Robot R may write a 300-character reason and 500-character lines (FOCAL limits), and the reason is never used by the runtime (logged only). Every token is GPU time the NPC server also wants.
- *Cache reuse is likely poor but unmeasured.* Robot R's prompt goes as one user message; llama-server b12443 reuses a sliding-window (Gemma) or hybrid (Qwen3.5) model's cache only from message starts (D-59), so Robot R's ~700-token persona prefix is probably prefilled again every call (about 0.3 s on F3). Not recorded for Robot R in the owner's files. **Found while building:** with the pulse on (every run with a model), the persona prefix never matched the prompt's start (D-76), so the NPC prompts' system-message layout and the snapshots/pre-warms (G3c-1) silently fell back to one message. NPC prefill (111 ms for a ~650–1300-token prompt at 3900–5900 tok/s) fits a prompt processed from scratch.
- *Repairs are a separate, second problem:* 8–36% of Robot R's calls were invalid output in conditions without contention too (F1 alone STEPPED 29%, F3 + N3 STEPPED 36%), against 2–4% on the offline prompt set, which has neither the pulse's activity format nor its FN-1 and activity checks. A repair costs a second call when there is time and a WAIT fallback when there is not. Their kind is what `diagnose` will show.
- *Model choice alone does not reach the target:* F1 times out less than F3 with N3 (11% vs 19% LIVE; 41% vs 77% LIVE_LOAD) but is still far over 5%, and F1's Robot R quality on prompts_v3 has not been measured (D-79).

The F3 + N3 rows ran on the G3c-2 code (a repair got a fresh 4 s), the baseline rows on G3d/G3e (one deadline per decision, D-63): timeouts per call compare; repairs per decision do not quite.

### 2. Fixes, measured on a simulated shared GPU

Three conditions, each named and configurable (`configs/inference.yaml` `focal` and `gpu_guard`; bake-off `--focal-layout`, `--focal-answer`, `--gpu-guard`, `--npc-cap`), **all off by default until the owner's PC measures them**:

| Condition | What it changes | Decision |
|---|---|---|
| `focal.prompt_layout: SYSTEM_PREFIX` | Robot R's guardrails + identity as a system message, so llama-server can reuse that ~700-token prefix on a sliding-window/hybrid model; prompt text unchanged | D-76 |
| `focal.answer: SHORT` | reason_summary ≤ 60 characters (was 300; the runtime never uses it), speech ≤ 200 (was 500), promise text ≤ 80 | D-77 |
| `gpu_guard` (`npc_cap` 0 or 1) | While a Robot R call is in flight the NPC server starts no background call and real calls only below the cap; held calls keep their deadlines | D-78 |

**Measured on a simulated shared GPU** (`tools/contention_sim.py`, 6 simulated minutes per cell at 10x, seed 7; the real gateway, schedulers, deadlines and guard; model speeds from the owner's offline bake-off; D-83). Robot R p50 / p95 ms, timeouts, NPC (two visitors' C2 calls) and LIVE_LOAD's synthetic calls:

| Robot R | Workload | Condition | Robot R timeouts | Robot R p50 / p95 | Gen tokens p50 | NPC p50 / p95 (timeouts) | Load calls timed out | Target |
|---|---|---|---|---|---|---|---|---|
| F3 | LIVE | baseline | 3/25 (12%) | 3060 / 4010 | 147 | 900 / 1790 (0) | – | NOT met |
| F3 | LIVE | system_prefix | 0/26 | 2730 / 3580 | 147 | 880 / 1700 (0) | – | met |
| F3 | LIVE | short | 0/27 | 2300 / 3180 | 100 | 880 / 1750 (0) | – | met |
| F3 | LIVE | guard cap 0 | 0/26 | 3010 / 3720 | 147 | 900 / 2490 (0) | – | met |
| F3 | LIVE | guard cap 1 | 3/25 (12%) | 3060 / 4010 | 147 | 900 / 1790 (0) | – | NOT met |
| F3 | LIVE | all three (cap 0) | 0/28 | 2020 / 2700 | 100 | 900 / 2500 (0) | – | met |
| F3 | LIVE_LOAD | baseline | 25/25 (100%) | 4010 / 4010 | – | 1960 / 3310 (0) | 0/741 | NOT met |
| F3 | LIVE_LOAD | system_prefix | 25/25 | 4010 / 4020 | – | 1940 / 3310 (0) | 0/741 | NOT met |
| F3 | LIVE_LOAD | short | 25/25 | 4010 / 4020 | – | 1950 / 3310 (0) | 1/742 | NOT met |
| F3 | LIVE_LOAD | guard cap 0 | 4/25 (16%) | 3700 / 4010 | 147 | 1900 / 3920 (0) | 70/720 | NOT met |
| F3 | LIVE_LOAD | guard cap 1 | 25/25 | 4010 / 4020 | – | 1940 / 2970 (0) | 52/719 | NOT met |
| F3 | LIVE_LOAD | short + guard cap 0 | 0/26 | 3070 / 3280 | 100 | 1940 / 4270 (0) | 53/730 | met |
| F3 | LIVE_LOAD | all three (cap 0) | 0/26 | 2550 / 3030 | 100 | 1950 / 3540 (0) | 34/738 | met |
| F1 | LIVE | baseline | 0/28 | 2030 / 2920 | 147 | 890 / 1760 (0) | – | met |
| F1 | LIVE | all three (cap 0) | 0/32 | 1360 / 1590 | 100 | 890 / 1610 (0) | – | met |
| F1 | LIVE_LOAD | baseline | 18/25 (72%) | 4010 / 4010 | 147 | 1970 / 3270 (0) | 1/742 | NOT met |
| F1 | LIVE_LOAD | system_prefix | 1/25 (4%) | 3690 / 3770 | 147 | 1930 / 3050 (0) | 0/752 | met |
| F1 | LIVE_LOAD | short | 0/26 | 3030 / 3100 | 100 | 1910 / 2830 (0) | 0/767 | met |
| F1 | LIVE_LOAD | guard cap 0 | 0/26 | 2560 / 3130 | 147 | 1940 / 3710 (0) | 34/738 | met |
| F1 | LIVE_LOAD | all three (cap 0) | 0/28 | 1960 / 2530 | 100 | 1790 / 2660 (0) | 5/767 | met |

(Every cell is in `results/contention_sim.json`; the full matrix also has F1 with each condition alone in LIVE, all met.)

What it says, under its assumptions:
- **Calibration, both ways:** its F3 + N3 LIVE baseline (12% timeouts) is close to the owner's 19%, but its F1 + N3 LIVE baseline is too kind (0% vs the owner's 11%) and its LIVE_LOAD baselines too harsh (100% vs 77% for F3, 72% vs 41% for F1). It is a model of the mechanism, not the owner's GPU: it ranks the conditions, the PC measures them.
- **For F3 under load no single condition is enough**; SHORT plus the guard, or all three, meet the target. In plain LIVE each condition alone does.
- **SHORT cuts Robot R's generated tokens about a third** (147 → 100), the largest single saving because generation dominates. **SYSTEM_PREFIX cuts prefill** (780 → 490 ms for F3).
- **The guard with cap 0 is what helps under load;** cap 1 rarely holds anything (about one NPC call is in flight anyway) and changes nothing. Its cost lands on NPCs: the visitors' p95 rises (F3 LIVE_LOAD 3310 → 3540–4270 ms, under their 6 s deadline, no timeouts), and 5–9% of the synthetic load calls (3 s deadline) time out.
- **F1 meets the target under load with any one of the conditions;** F3 needs two. Whether F1 keeps Robot R's quality is the open question (D-79).

End to end in Godot (`--model fake-gpu --npc-load 3`, SB-04 LIVE, 90 s real time, one run each; the plumbing through the real sidecar, world and summaries):

| Condition | Robot R calls | Timeouts | p50 / p95 ms | Prefill / gen p50 ms | Prompt tokens p50, cache share | Generated tokens p50 | Visitors' model calls (timeouts) | Guard |
|---|---|---|---|---|---|---|---|---|
| baseline | 9 | 9 | 3997 / 4010 | – (all timed out) | – | – | 8 (0) | off |
| SYSTEM_PREFIX + SHORT + guard cap 0 | 9 | 0 | 2209 / 3153 | 318 / 1891 | 1138, 60% | 66 | 7 (2) | 30 deferrals |

The NPC cost shows here too: two of the visitors' seven calls timed out while held behind Robot R's.

### Result

- **Built:** all five parts. Diagnosis and harness (D-75), the three conditions (D-76 to D-78, off by default), model choice and deadline as decisions only (D-79, D-80), raw heard speech bounded (D-81), attention while walking and SB-10 (D-82), the simulated shared GPU (D-83). Two defects found and fixed on the way, each reproduced first: pooled run folders in the bake-off (D-75) and a persona prefix that no prompt started with when the pulse is on (D-76).
- **Journals** (each scenario three times, one with random sidecar delays; one journal each): every existing scenario is **byte-identical to main**: SB-04 `50048b7e3d42`, SB-05 `3ef2e2e0e63c`, SB-06 `b5b29006cad4`, SB-07 `a486ddb7a471`, SB-08 `f1f631e031c1`, SB-04 with fake-model NPCs `a7854d66f268` (and replayed), SB-06 with the fake model `f7b4d221a195` (and replayed; main's run gives the same), SB-09 soak `09a8d071f381` (main's run gives the same). New: **SB-10 `ab5964d77f57`**.
- **SB-10 (Demo policy, stepped):** Robot R walks at a steady 1.0 m/s with its heading unchanged (−90°) from start to stop; the side speaker gets a head glance (50–66°, checked within 1 s) and an answer; the voice from behind sends the head to its 80° limit, heading kept; Robot R stops at 21.9 s, then its body turns to face the visitor behind (−90° → 89°), and it looks at them. Before D-82 the body never turned after stopping (the speaker behind was never seen), and the Demo policy's `TURN_TO` would have turned the body mid-walk.
- **Soak:** `tools/soak.py` OK (D-81 has the numbers).
- **Needs the owner's PC** ([G3f_OWNER_CHECKLIST.md](G3f_OWNER_CHECKLIST.md)): `bakeoff.py diagnose` on the existing run folders (no rerun), the baseline rerun with the new instrumentation, each condition alone and together for F3 (and F1) in LIVE and LIVE_LOAD, the offline quality of SHORT and SYSTEM_PREFIX on prompts_v3, and the watched SB-10. The decisions to make with those numbers: D-76 to D-79.

### G3f result (owner's PC, 2026-11-20)

From the owner's results.md, diagnosis.md and soak_summary.json (llama.cpp b12443, prompts_v3 `8b47570792f2`, three real-time runs per row). Robot R's calls (calls include repairs; "fallbacks" are decisions that ended in WAIT):

| Robot R | NPC | Condition | Mode | Calls | Timeouts | Invalid (kinds) | Fallback decisions | p95 ms | Prefill / gen p50 ms | Generated tokens p50 / p95 | Cache share |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F3 | none | baseline | LIVE | 30 | 0 | 6 (TRUNCATED 6) | 6/30 (20%) | 3627 | 274 / 1971 | 121 / 200 | 52% |
| F1 | none | baseline | LIVE | 41 | 1 | 5 (FN1_RULE 5) | 4/39 (10%) | 2427 | 174 / 1710 | 151 / 186 | 52% |
| F3 | N3 | baseline | LIVE | 48 | 10 | 3 (TRUNCATED 3) | 13/48 (27%) | 4008 | 338 / 1998 | 122 / 200 | 50% |
| F3 | N3 | baseline | LIVE_LOAD | 33 | 24 | 0 | 24/33 (73%) | 4009 | 454 / 3187 | 106 / 110 | 58% |
| F3 | N3 | SYSTEM_PREFIX | LIVE | 44 | 3 | 2 | 5/44 (11%) | 3950 | 443 / 2064 | 122 / 172 | 50% |
| F3 | N3 | SHORT | LIVE | 46 | 12 | 7 (TRUNCATED 7) | 19/46 (41%) | 4002 | 319 / 2971 | 166 / 200 | 51% |
| F3 | N3 | guard cap 0 | LIVE | 49 | 7 | 7 (TRUNCATED 7) | 14/49 (29%) | 4008 | 426 / 2382 | 133 / 200 | 44% |
| F3 | N3 | guard cap 1 | LIVE | 43 | 5 | 3 (TRUNCATED 3) | 8/43 (19%) | 3975 | 366 / 1881 | 104 / 200 | 49% |

- **No condition met the G3f target with N3 running**; only Robot R alone did (F3 0/30 timeouts, F1 1/41). Under LIVE_LOAD every condition had 32–86% timeouts.
- **Generation dominates** Robot R's call time (gen p50 ~2000 ms vs prefill ~300 ms; ~125 generated tokens, p95 at the 200-token cap). **20% of F3's calls were cut off even alone** (6/30).
- **"After repair" is 0 in every row:** under one deadline per decision (D-63) there is never time to repair, so every invalid answer became a WAIT fallback.
- **SYSTEM_PREFIX** gained nothing measurable (cache share 50% vs 51%); **SHORT** made answers longer (generated tokens p50 122 → 166) with more cut-offs and timeouts (D-77 rejected as default).
- **GPU memory:** peak 15.3–15.9 GB of 16.4 GB with F3 + N3, about 4.3 GB of it not the models, so Windows' system-memory fallback may have inflated contention (a baseline rerun after freeing ~4 GB was attached).
- **Soak (real models, 21 simulated minutes, 303 decisions, 54 fallbacks):** visitor_y's C1 context reached 824 tokens against its 780 budget; raw heard speech still growing below its cap (Robot R 13 / 22 / 26 / 32 of 40). Both are G3g item 5 (D-88).

## G3g — Lean answers (merged, DoctorWomp/SOMA_CODEC#30; owner decisions 2026-11-21 on D-84 to D-89: see DECISIONS.md)

**Owner direction (2026-11-20):** measure what each field of Robot R's answer costs before changing it; a LEAN answer as a named condition; salvage cut-off answers whose actions are complete; a target that counts fallbacks; the C1 budget bug from the soak; the GPU guard for real decisions only; VRAM hygiene; the NPC-table label bug; the decisions index and a check for it. Owner steps: [G3g_OWNER_CHECKLIST.md](G3g_OWNER_CHECKLIST.md).

| # | What | Decision | Proof (cloud) |
|---|---|---|---|
| 0 | Owner decisions on D-75 to D-83 recorded; DECISIONS.md index completed (it stopped at D-61, D-60/D-61 shown PROPOSED) | – | `tests/test_decisions_index.py` (failed on main: 2 stale rows, 22 missing) |
| 1 | `bakeoff.py tokens`: tokens per field from the generated tokens, with and without `maxLength`; offline answers record text, tokens, cut-offs and fields | D-84 | T1 on a CPU (below) |
| 2 | LEAN: no reason, compact optional activity last, no grammar text limits, one line | D-85 | `tests/test_lean_answers.py`; T1 smoke offline |
| 3 | Salvage: a cut-off answer's complete, valid actions used; never a partial action | D-86 | `tests/test_lean_answers.py`, `tests/test_llama_provider.py` (stand-in server) |
| 4 | Target: fallback decisions ≤ 5% alone, ≤ 10% with N3, p95 < 4 s | D-87 | `tests/test_lean_answers.py`, `tests/test_focal_conditions.py`; the owner's G3f rows re-reported |
| 5 | The whole prompt counted; the latest turn shortened as the last step; C1's split re-measured; the soak check | D-88 | `tests/test_agent_context.py` (reproduced, failing on main); measured with the Qwen3.5 tokenizer |
| 6 | `gpu_guard.hold: DECISIONS` | D-89 | `tests/test_lean_answers.py` |
| 7 | `vram_hygiene` in every run summary; a warning below the reserve; OWNER_SETUP_WINDOWS | D-87 | runs in the cloud record null with the reason (no nvidia-smi) |
| 8 | results.md: NPC-table rows carry their run's condition | – | `tests/test_lean_answers.py`, report on the owner's results.json |

### Result

- **Built:** items 0–8 as planned (D-84 to D-89). Two defects reproduced first and fixed: the DECISIONS.md index (now checked by `tests/test_decisions_index.py`) and the C1 budget overrun (D-88). One more found in review and fixed: a salvaged LEAN answer's complete compact activity was checked before it was written out in full.
- **The grammar's string limits (D-84), measured in the cloud** with llama-server b12443 built from the pinned commit on a CPU and T1 (Qwen3.5-0.8B: the smoke model, never a bake-off candidate), 8 of Robot R's prompts_v3 prompts, activity offered (`bakeoff.py tokens --models T1 --limit 8`, with `--answer SHORT` for the second row):

| Answer format | Same text with / without maxLength | Generated tokens with / without (sum) | Generated − own tokenization, with / without | White-space-only tokens with / without | Reason tokens per answer with / without |
|---|---|---|---|---|---|
| FULL (limits do not bind) | 8 / 8 | 988 / 988 | 10 / 10 (the end token) | 194 / 194 | 21.6 / 21.6 |
| SHORT (reason ≤ 60 characters) | 2 / 8 | 978 / 988 | **68** / 10 | **254** / 194 | 12.9 / 21.6 |

  A limit that does not bind changes nothing; one that binds ends the string mid-sentence and the model then writes up to 20 single-space tokens before the closing brace (+19 to +21 tokens in 3 of 8 answers). T1's FULL answers by field: args 28%, reason 18%, speech 17%, actions 16%, white space 20% (pretty-printed JSON), other 2%.
- **LEAN, offline smoke** (T1, CPU, 8 Robot R prompts, activity offered; plumbing, not quality): generated tokens p50 / p95 **147 / 163 (FULL) → 56.5 / 70 (LEAN)**; white space 20% → 0% (T1 followed "on one line"); final valid 100% both; no answer at the cap; CPU latency p50 7.2 s → 3.9 s. Promises read 0% in both conditions (T1 on this subset); F3's quality is the owner's PC run.
- **The owner's G3f rows against the D-87 target** (results.md regenerated from the attached results.json): no row meets it; F3 alone met G3f's timeout target (0/30) but has 6/30 (20%) fallback decisions, all cut-off answers, the case salvage (D-86) now turns into actions when the actions were complete.
- **C1 contexts with the real Qwen3.5 tokenizer** (T1's `/tokenize`; N3's family; SB-09 visitor_y, a 60-, 200- and 480-character latest turn): 698, 731 and 732 tokens of 780 with the fix (the last with OBSERVATIONS cut, the turn kept whole); C2 1100–1298 of 1900. C1's guardrails with the pulse on: 403 tokens.
- **Journals** (each scenario three times, one with random sidecar delays): **every scenario byte-identical to main**: SB-04 `50048b7e3d42`, SB-05 `3ef2e2e0e63c`, SB-06 `b5b29006cad4`, SB-07 `a486ddb7a471`, SB-08 `f1f631e031c1`, SB-10 `ab5964d77f57`, SB-04 with fake-model NPCs `a7854d66f268` (and replayed), SB-06 with the fake model `f7b4d221a195` (and replayed), SB-09 `09a8d071f381`. Nothing in G3g changes what the world sees with the fake model: LEAN is off by default, the fake model never stops at the cap, and the context fix only acts when a prompt is over its budget (no section was cut in any of the soak's 256 assembled contexts).
- **Soak** (`tools/soak.py`, fake model, stepped): OK. 263 decisions, 0 fallbacks; prompt tokens (now the whole prompt, headers included) Robot R largest 2188 of 3750, visitor C1 734–736 and 679–700 of 780, C2 up to 1520 of 1900; raw heard Robot R 11 / 23 / 24 / 22 / 20 (cap 40). On the owner's real-model soak summary the new rules would turn the raw-heard growth (32 of 40) and visitor_y's C2 growth (1570 of 1900) into NOTEs, and keep the C1 824 > 780 a failure, which D-88 now prevents at assembly.
- **Needs the owner's PC** ([G3g_OWNER_CHECKLIST.md](G3g_OWNER_CHECKLIST.md)): `bakeoff.py tokens` with F3 and F1 (FULL and SHORT); LEAN vs FULL offline for F3 and F1; F3 + N3 live with LEAN (LIVE, LIVE_LOAD), alone, and with the guard at cap 1 in both hold settings; F1 + N3 with LEAN; a real-model soak. The decisions to make with those numbers: D-84 to D-89.

### G3g result (owner's PC, 2026-11-21)

From the owner's results.md, diagnosis.md and soak_summary.json (llama.cpp b12443, prompts_v3 `8b47570792f2`, three real-time runs per live row).

**Offline, Robot R's prompts (56):**

| Model | Condition | Final valid | Promises flag / behavior | Generated tokens p50 / p95 | At the cap (salvaged) | Largest fields |
|---|---|---|---|---|---|---|
| F3 | FULL | 100% | 60% / 100% | 115 / 173 | 1 (1) | args 38%, reason 28% |
| F3 | FULL, activity offered | 96% | 80% / 90% | 151 / 200 | 13 (10) | args 41%, reason 19%, space 10% |
| F3 | **LEAN, activity offered** | **100%** | **80% / 100%** | **119 / 131** | **0** | **args 55% (60 tokens)**, actions 20%, speech 13% |
| F1 | FULL | 100% | 40% / 90% | 169 / 200 | 4 (4) | reason 39%, args 35% |
| F1 | LEAN, activity offered | 100% | **0% / 80%** | 135 / 181 | 0 | args 45%, actions 18% |

**Live (SB-04, Robot R calls; fallbacks are decisions that ended in WAIT):**

| Robot R | NPC | Condition | Mode | Calls | Timeouts | Invalid (kinds) | Fallbacks | p95 ms | D-87 target |
|---|---|---|---|---|---|---|---|---|---|
| F3 | N3 | FULL | LIVE | 49 | 11 | 0 (3 salvaged) | 11/49 (22%) | 4007 | NOT met |
| F3 | N3 | LEAN | LIVE | 56 | 10 | 9 (ACTIVITY_RULE 8, FN1_RULE 1) | 19/56 (34%) | 4002 | NOT met |
| F3 | none | LEAN | LIVE | 40 | 0 | 6 (ACTIVITY_RULE 5, FN1_RULE 1) | 6/40 (15%) | 2625 | NOT met |
| F3 | N3 | LEAN, guard cap 1 | LIVE | 55 | 7 | 3 (ACTIVITY_RULE 3) | 10/55 (18%) | 3939 | NOT met |
| F3 | N3 | LEAN, guard cap 1, decisions only | LIVE | 49 | 3 | 13 (ACTIVITY_RULE 8, FN1_RULE 5) | 16/49 (33%) | 3950 | NOT met |
| F1 | N3 | LEAN | LIVE | 54 | 0 | 10 (ACTIVITY_RULE 9, FN1_RULE 1; 6 repaired) | 4/48 (8%) | 2246 | **met** |
| F1 | N3 | LEAN | LIVE_LOAD | 55 | 2 | 14 (ACTIVITY_RULE 13, FN1_RULE 1) | 14/53 (26%) | 3403 | (stress) |

- **Freeing VRAM did not change timeouts:** other programs held 2.8 GB before the servers started and 2.6 GB stayed free with both; F3 FULL + N3 LIVE still had 22% timeouts. Contention is compute, not memory.
- **F3 LEAN offline:** 100% valid, promises 80% flag / 100% behavior, nothing cut off, but generated tokens p50 119 (target 70); args are 55% of its tokens (60 per answer).
- **F3 LEAN live:** ACTIVITY_RULE failures turned valid answers into WAITs (8 of 56 calls with N3; 5 of 40 alone, where every fallback was a rule failure and none a timeout). G3h item 1 (D-110).
- **F1 LEAN + N3 met the LIVE target** (p95 2246 ms, 0 timeouts, 8% fallbacks) but kept promises badly offline (0% flag / 80% behavior), **so F3 stays** (D-79).
- **The real-model soak passed** (233 decisions, 25 fallbacks; visitor_x's largest C1 context 765 of 780, a NOTE).
- **Owner decisions (2026-11-21):** D-84, D-86, D-87, D-88 approved; D-85 approved as F3's default once G3h item 1 is built and its offline check passes; D-89 stays an option, the guard off; acceptance is judged in normal LIVE runs, LIVE_LOAD reported as a stress test.

## G3h — The new LEAN default for F3 (draft PR; D-110 to D-114 PROPOSED)

**Owner direction (2026-11-21):** an invalid activity never costs the actions; short track handles and other argument compaction, each measured first; prompts_v4 if the prompts change; speculative decoding investigated only. Owner steps: [G3h_OWNER_CHECKLIST.md](G3h_OWNER_CHECKLIST.md). Decision numbers D-110 onward (a parallel G4a session uses D-90 to D-109).

| # | What | Decision | Proof (cloud) |
|---|---|---|---|
| 0 | Owner decisions on D-84 to D-89 recorded; acceptance judged in LIVE, LIVE_LOAD a stress report | D-87 | `tests/test_activity_drop.py`, `tests/test_focal_conditions.py` |
| 1 | An invalid activity is dropped, the actions kept, the rule recorded; FN-1 holds counted apart; diagnose reports rule kinds | D-110 | `tests/test_activity_drop.py` (reproduced, failing on main) |
| 2 | Tokens per track id measured (F3 and F1 tokenizers); handles P1, P2, ... for Robot R under LEAN | D-111 | `tests/test_handles.py`; measurement below |
| 3 | Defaults left out of LEAN answers; coordinates to one decimal; measured | D-112 | `tests/test_handles.py`; measurement below |
| 4 | prompts_v4; F3 and F1 offline on it in the cloud (plumbing) | D-113 | `tests/test_bakeoff.py`; the plumbing run below |
| 5 | Speculative decoding for F3: tokenizer and VRAM from GGUF headers (investigation only) | D-114 | below |

### Result

- **Built:** items 0–6 (D-110 to D-114; D-114 is an investigation and a proposal, nothing built). One defect reproduced first (an invalid activity cost the actions, D-110). Found while building: `--focal-answer LEAN` on prompts_v3 rewrote only the format line, so it now applies the full LEAN rewrite (shapes, handles) and both sets measure the same LEAN; and llama-server b12443 needs `--spec-type draft-simple` for a draft model (the default is `none`) and has removed `--draft-max`.
- **Item 2, measured first** (cloud: llama-server b12443 built from the pinned commit; the catalog's F3 and F1 files; their own tokenizers via `/tokenize`; the Demo policy's 28 prompts_v3 answers that name someone, 2.7 ids each):

| Tokenizer | Tokens per id (key and value; with a handle) | ids per answer (share of all / of argument tokens) | Answer tokens: as written → handles → + defaults left out → + one decimal |
|---|---|---|---|
| F3 (Gemma 4) | 18 (11) | 22.7 of 110 (21% / 33%) | 110.4 → 93.1 → 88.0 → 88.0 |
| F1 (Qwen3.5) | 17 (10) | 21.0 of 106 (20% / 34%) | 105.6 → 90.1 → 84.9 → 84.9 |

  Ids are a large share, so handles were built (D-111); defaults left out save about 5 more tokens (D-112); one decimal saved nothing here (D-112 keeps it as a rule and the `numbers` field will show F3's real numbers). Applied to F3's measured LEAN answers (p50 119), the projection is roughly 95–100 tokens: likely still above the 70 target.
- **Item 4, prompts_v4** `7cc7a7cc27b8` (100 prompts: 59 Robot R as LEAN sends them, with handles; 41 NPC). **Cloud plumbing run** (CPU, 4 cores, `--limit 2`: two Robot R and two NPC prompts per model; F3 and F1 the real catalog files): every answer valid (2/2 Robot R, 2/2 NPC, both models); Robot R named people only by handle (`"addressee_id": "P1"`), left out the channel, and its answers were read back to anonymous ids and passed the offline gate; generated tokens 101 and 107 (F3), 76 and 111 (F1); ids 5 (F3) and 4 (F1) tokens per answer. F3 wrote three actions in both (TURN_TO, SPEAK, EXPRESS). Plumbing only: two prompts say nothing about rates or promises.
- **Item 5, speculative decoding** (D-114): S1 and N1 share F3's vocabulary exactly (GGUF headers, compared token by token); S1 would put about 1.34 GB of weights on the GPU (its 2.15 GB of input embeddings stay in host RAM in b12443), about 1.6–2.0 GB in all, inside the ~2.6 GB left free but most of Godot's reserve; N1 does not fit. On a CPU with three prompts_v4 prompts: answers identical with and without the draft (3 of 3), draft acceptance 47%, 246 of 315 generated tokens from the draft. Estimated about 1.3x faster generation on the GPU (not measured). A proposal for the owner.
- **Journals:** JOURNALS_PLACEHOLDER
- **Soak:** SOAK_PLACEHOLDER
- **Needs the owner's PC** ([G3h_OWNER_CHECKLIST.md](G3h_OWNER_CHECKLIST.md)): F3 and F1 offline on prompts_v4 with LEAN (the targets: final valid ≥ 98%, promises ≥ 80% / 95%, generated tokens p50 ≤ 70); FULL on prompts_v3 with the activity offered, for comparison; F3 + N3 in LIVE (judged) and LIVE_LOAD (stress) with LEAN; F3 alone in LIVE; `diagnose`. If the offline targets are met, LEAN becomes F3's default (D-85). A decision on D-114.

## Out of scope for G3

HORIZON layers L4–L8 and preset effects (G5); adaptive expression and the establish → tension → resolve phrases (G5); Director and Participant controls (G4); the expo map (G6); model summaries of episodes (compression step 5, G6); KV quantization, speculative decoding, response cache (G5–G6 experiments).
