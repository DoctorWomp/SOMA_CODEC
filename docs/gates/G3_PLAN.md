# G3 — Agent runtime

**Status:** G3a COMPLETE (merged 2026-11-15) · G3b COMPLETE (G3b-1 and G3b-2 merged; D-57, D-58 APPROVED 2026-11-16; bake-off run on the owner's PC 2026-11-17) · G3c-1 in progress · owner checks: [G3a](G3a_OWNER_CHECKLIST.md), [G3b](G3b_OWNER_CHECKLIST.md)
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

## Out of scope for G3

HORIZON layers L4–L8 and preset effects (G5); adaptive expression and the establish → tension → resolve phrases (G5); Director and Participant controls (G4); the expo map (G6); model summaries of episodes (compression step 5, G6); KV quantization, speculative decoding, response cache (G5–G6 experiments).
