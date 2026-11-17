# Decisions

Settled answers to conflicts and open choices across the source documents.
**An APPROVED decision overrides any source document.** Sources are indexed in [SOURCES.md](SOURCES.md).

Status values: **PROPOSED** (recommended default, awaiting owner review) · **APPROVED** · **REJECTED** · **SUPERSEDED**.
To change a decision, edit its entry and note the date. Do not silently delete entries.

| ID | Topic | Status |
|---|---|---|
| D-01 | Document precedence | APPROVED (owner, 2026-11-13) |
| D-02 | One gate numbering | APPROVED (owner, 2026-11-13) |
| D-03 | Experiment axes, layer masks and presets | APPROVED (owner, 2026-11-13) |
| D-04 | World authority | APPROVED (owner, 2026-11-13) |
| D-05 | Godot ↔ Python transport | APPROVED (owner, 2026-11-13) |
| D-06 | Versions, machine and models | APPROVED (owner, 2026-11-13) |
| D-07 | Venue announcement channel name | APPROVED (owner, 2026-11-13) |
| D-08 | Naming collisions | APPROVED (owner, 2026-11-13) |
| D-09 | CDC modes in RANGE | APPROVED (owner, 2026-11-13) |
| D-10 | How confidence is represented | APPROVED (owner, 2026-11-13) |
| D-11 | ΔP formula | APPROVED (owner, 2026-11-13) |
| D-12 | Disclosure scopes and gate | APPROVED (owner, 2026-11-13) |
| D-13 | What may be inferred or stored about a person | APPROVED (owner, 2026-11-13) |
| D-14 | Public expression palette and light safety | APPROVED (owner, 2026-11-13) |
| D-15 | Repository layout | APPROVED (owner, 2026-11-13) |
| D-16 | Which layers are simulated vs implemented | APPROVED (owner, 2026-11-13) |
| D-17 | Proxemic distances | APPROVED (owner, 2026-11-13) |
| D-18 | PR #1 | APPROVED (owner, 2026-11-13) |
| D-19 | Hardware track parked for RANGE v0 | APPROVED (owner, 2026-11-13) |
| D-20 | Model shortlist and bake-off | APPROVED (owner, 2026-11-13) |
| D-21 | Inference engine and standalone packaging | APPROVED (owner, 2026-11-13) |
| D-22 | Languages and what each one does | APPROVED (owner, 2026-11-13) |
| D-23 | Inference strategy: residency, caching, tiers | APPROVED (owner, 2026-11-13) |
| D-24 | Context and memory strategy | APPROVED (owner, 2026-11-13) |
| D-25 | Interaction modes and awareness protocols | APPROVED (owner, 2026-11-13) |
| D-26 | Art direction, rendering budget and environment-as-variable | APPROVED (owner, 2026-11-13) |
| D-27 | Contract format and validation | APPROVED (owner, 2026-11-13) |
| D-28 | License | APPROVED (owner, 2026-11-13) |
| D-29 | Contract v1 conventions | APPROVED (owner, 2026-11-14) |
| D-30 | How Godot reads configs | APPROVED (owner, 2026-11-14) |
| D-31 | Ramp, stairs and capability gating in the world | APPROVED (owner, 2026-11-14); navigation sizing amended by D-37 |
| D-32 | Robot R greybox body | SUPERSEDED by D-36 (owner, 2026-11-14) |
| D-33 | Godot project settings and the world tick | APPROVED (owner, 2026-11-14), tick question resolved |
| D-34 | Godot checks in tools/check.py and CI | APPROVED (owner, 2026-11-14) |
| D-35 | Python version on the PC and in CI | APPROVED (owner, 2026-11-14) |
| D-36 | Robot body family | APPROVED (owner, 2026-11-14) |
| D-37 | Body contract 2.0, per-size navigation, legged colliders | APPROVED (owner, 2026-11-14) |
| D-38 | GDScript warnings are errors | APPROVED (owner, 2026-11-14) |
| D-39 | Sight: the observer filter | APPROVED (owner, 2026-11-15) |
| D-40 | Hearing: local speech | APPROVED (owner, 2026-11-15) |
| D-41 | Godot event journal and contract checks of Godot output | APPROVED (owner, 2026-11-15) |
| D-42 | Shared local avoidance | APPROVED (owner, 2026-11-15) |
| D-43 | COMMS router: channels, groups and PA | APPROVED (owner, 2026-11-15) |
| D-44 | The Godot ↔ Python link and the action gate | APPROVED (owner, 2026-11-15) |
| D-45 | The disclosure gate in practice | APPROVED (owner, 2026-11-15) |
| D-46 | Expression-ready gesture events | APPROVED (owner, 2026-11-15) |
| D-47 | Deterministic runs: navigation updates on the main thread | APPROVED (owner, 2026-11-16) |
| D-48 | Scenario runner and run modes (stepped, live) | APPROVED (owner, 2026-11-16) |
| D-49 | Agent runtime: triggers, one pending request, cognition levels, Demo policy | APPROVED (owner, 2026-11-16) |
| D-50 | Model gateway: providers, output format, repair, timeouts, record and replay | APPROVED (owner, 2026-11-16) |
| D-51 | Context assembly in practice: budgets, compression, logging | APPROVED (owner, 2026-11-16) |
| D-52 | Expression catalog, EXPRESS and the Beacon | APPROVED (owner, 2026-11-16) |
| D-53 | Directive templates and guardrails | APPROVED (owner, 2026-11-16) |
| D-54 | Rigging and animation: pose is presentation | APPROVED (owner, 2026-11-16) |
| D-55 | Quantized and QAT models in the bake-off | APPROVED (owner, 2026-11-16) |

---

## D-01 — Document precedence
**Status:** APPROVED (owner, 2026-11-13)

Precedence, highest first: non-negotiable safety/privacy/honesty rules → this file → CANON → SUPPORTING → SEED → REFERENCE. Within a status, newer wins. Full rules and the status of every document are in [SOURCES.md](SOURCES.md).

CANON: Master Build Blueprint v1.0, HORIZON Sensory Layer Operational Atlas v0.2, ΔP Math & Control Addendum v0.2.

## D-02 — One gate numbering
**Status:** APPROVED (owner, 2026-11-13)

Use the Blueprint's **G0–G7** gates as the only build plan. Retire: Assessment clusters RG-01..10, PR #1 milestones M0–M6, Runtime v0.2 Gates A–D, HORIZON v0.1 phases 0–6, Addendum P0–P3. Their content is folded into G0–G7 in [RANGE_V0_SCOPE.md](RANGE_V0_SCOPE.md).

## D-03 — Experiment axes, layer masks and presets
**Status:** APPROVED (owner, 2026-11-13)

Three documents number the comparison arms differently, and "A1" means something different in each. Replace all arm labels with **three independent axes**, recorded in every run manifest:

| Axis | Values | Notes |
|---|---|---|
| **Policy** | `SCRIPTED` · `LLM` | Who decides actions. `SCRIPTED` is the deterministic floor. |
| **Perception mask** | 9 bits, one per layer L0–L8, per avatar | Which HORIZON layers are active (not bypassed). `HORIZON_OFF` gives the same observer-filtered evidence as a flat list. |
| **Sensor package** | `STANDARD` · `ENHANCED` | Extra evidence is a separate question from better organization. |

**Named presets** of the mask (the Operational Atlas ladder):

| Preset | Adds | Question |
|---|---|---|
| `H0` | Nothing: flat observer-filtered evidence, same actions | What can the baseline do? |
| `H1` | L0–L3 structured spatial/audio/motion packets | Does structure help source and event handling? |
| `H2` | Typed ΔP with coverage/quality | Do relative changes help attention without false alarms? |
| `H3` | L7 Haze + L8 Trail | Do uncertainty and history reduce attribution errors? |
| `H4` | L4 Focus + L6 Prism | Do turn-taking and repair improve at acceptable cost? |
| `H5` | L5 Contour soft navigation | Fewer intrusions without more deadlocks? |
| `H6` | Context-sensitive Beacon expression | More appropriate without being invasive? |

Any other mask is allowed and must be named (for example `NO_HAZE`). `ORACLE` exists only inside the evaluator, never as an agent input.

Bypass rules: L0 cannot be bypassed. Bypassing a layer removes its output from the agent's context; downstream layers report the missing input as `MISSING`, never as zero. A bypass set before a run is a planned condition. A bypass toggled during a run is logged as an intervention and marks the run as tainted.

Old labels → new: Blueprint A0 → `SCRIPTED`; Blueprint A1 → `LLM` + `H0`; Blueprint A2 → `LLM` + `H4`/full; Blueprint A3 → sensor `ENHANCED`; Blueprint A4 → named masks; Addendum A1–A7 and Atlas A0–A6 → `H0`–`H6`.

## D-04 — World authority
**Status:** APPROVED (owner, 2026-11-13)

**Godot is the only world authority** in the application: positions, physics, navigation, line of sight, delivery eligibility, action execution, simulation clock (`tick_id`).

A small **Python headless test world** (2D, no graphics) implements the same contracts so comms, privacy, ΔP and gate logic can be tested without Godot. It is a test double, not a second authority, and never runs alongside Godot.

## D-05 — Godot ↔ Python transport
**Status:** APPROVED (owner, 2026-11-13)

Loopback **WebSocket** with versioned JSON envelopes and a launch-time session token, bound to `127.0.0.1` only (Blueprint §12). PR #1's HTTP harness is not carried forward.

## D-06 — Versions, machine and models
**Status:** APPROVED (owner, 2026-11-13)

- **Development machine:** Windows 11 Pro, AMD Ryzen 9 9950X (16 cores / 32 threads), 96 GB RAM, **NVIDIA RTX 4070 Ti Super, 16 GB VRAM**.
- **Model sizing for that GPU (estimates to verify at G3):** one small/medium (~4B-class) model shared by 3–5 agents fits comfortably; one ~9–12B-class model at 4-bit quantization fits alongside Godot with moderate context; two large models loaded at once is tight. The Runtime v0.2 doc's Q4 load estimates (E4B ≈ 4.5 GB, 12B ≈ 6.7 GB) exclude KV cache and parallel slots. LLM-policy ablation sweeps will be limited by GPU throughput; scripted-policy sweeps by CPU.
- **Python:** 3.12 baseline (Blueprint); CI also tests 3.13. Environments and the lockfile are managed with **uv**.
  *Amended 2026-11-14 (G1): the local default is now 3.14 and CI also tests 3.14; 3.12 stays the minimum. See D-35.*
- **Godot:** **4.7.2 stable** (standard build, GDScript, no .NET), released 2026-08-18 and verified on the official download archive on 2026-11-13. Re-check for a newer stable patch at G1; do not move to a new minor version (e.g. 4.8) mid-build without a decision.
  *Re-checked 2026-11-14 (G1): 4.7.2-stable is still the newest 4.7 release (4.8 is in beta). Staying on 4.7.2.*
- **Models:** see D-20 (shortlist and bake-off) and D-21 (engine and packaging). Never downloaded automatically.

## D-07 — Venue announcement channel name
**Status:** APPROVED (owner, 2026-11-13)

Use **`PA`** (Blueprint). Retire `SERVER` (Runtime v0.2). Channels are `GESTURE`, `LOCAL`, `GROUP`, `PA`.

## D-08 — Naming collisions
**Status:** APPROVED (owner, 2026-11-13)

| Term | Collision | Decision |
|---|---|---|
| **Tier** | Deployment tiers 1–4 (Situational) · BET capability tiers T0–T4 (Atlas) · CDC templates T0–T5 (Situational) · RCC memory tiers T0–T5 (Runtime v0.2) · SEM hardware tiers 1–4 | **Tier 1–4** = deployment setting only. BET capability → **BET-T0…T4**. CDC templates → **CDC mode names** (D-09). Memory tiers → **by name** (Identity Anchor, Working Set, …). SEM tiers are historical. |
| **CDC** | *Contextual Directive Core* (mode scheduler) · *Context Differentiation Capacity* (PAE series, Situational Protocols) | **CDC** = Contextual Directive Core. Write *context differentiation capacity* in full. |
| **ΔP / Delta P** | HORIZON typed normalized deviation · MVSB tension between polarity poles | **ΔP** = HORIZON only. MVSB's is "MVSB polarity ΔP". In code use `normalized_delta`; never "pressure". |
| **L0–L2** | HORIZON layers L0–L8 · NPC cognition levels L0–L2 (Blueprint §6.4) | Layers keep **L0–L8**. Cognition levels become **C0 Background, C1 Reactive, C2 Agentic**. |
| **A0, A1…** | Three different arm numberings | Retired; see D-03. |
| **Halo** | Layer L1 · the whole HUD visualization | **Halo (L1)** vs **Halo HUD**. |
| **T01–T30** | Blueprint acceptance tests vs T-prefixed modes above | Tests keep **T01–T30**; nothing else uses a bare `T`. |
| **Ledger** | *Relational Ledger* (information about others, with scopes) · *Covenant Ledger* (PAE Part 8: an agent's own commitments and refusals) | Keep both names; they are different stores. In RANGE the Covenant idea becomes the agent's **commitments and refusals** record (see D-13). |

## D-09 — CDC modes in RANGE
**Status:** APPROVED (owner, 2026-11-13)

CDC is a **compute and attention scheduler**, not a safety controller. RANGE uses five modes, with a mapping to the historical templates:

| RANGE mode | Historical template | Meaning in RANGE |
|---|---|---|
| `IDLE` | 0 Idle | Present, not engaged; minimal processing; does not start conversations |
| `STANDARD` | 1 Standard | Normal engagement and full social read |
| `FOCUSED` | 2 Cooperative | Sustained task or conversation; more budget to the focal target |
| `ALERT_CONTEXT` | 3 Alert | More processing for salient or uncertain observations. **Never entered from loudness alone.** |
| `EMERGENCY_HOST_ONLY` | 5 Emergency | Host handles physical safety; HORIZON drops non-essential inference and keeps output plain |

**Sovereignty Defense (historical 4) is not a mode.** It becomes an always-on **instruction-integrity guard**: text from signs, speech, messages or other agents is untrusted evidence and can never change instructions or permissions. Attempts are logged; the robot holds its task and may ask about intent. Never aimed at a person's emotions.

Transitions use entry/exit thresholds, minimum dwell time and cooldown for non-critical changes (Addendum §6). Physical emergency handling never waits for CDC, HORIZON or an LLM.

## D-10 — How confidence is represented
**Status:** APPROVED (owner, 2026-11-13)

Interpretations carry a **read label**, not a number: `COMMIT` · `LEAN` · `HELD_OPEN` · `UNKNOWN`. Numeric probabilities are allowed only with `calibrated: true` and a reference to validation data.

The concept art's confidence-band table becomes an action policy keyed by label:

| Read | Default action |
|---|---|
| `COMMIT` | Act |
| `LEAN` | Act and keep monitoring, or confirm lightly |
| `HELD_OPEN` | Wait for a natural opening, or ask one neutral clarifying question |
| `UNKNOWN` | Defer and gather more evidence |

Stakes raise the bar (Chatbot spec A6.4): the more consequential the action, the stronger the read required.

## D-11 — ΔP formula
**Status:** APPROVED (owner, 2026-11-13)

Use the Addendum v0.2 / Operational Atlas v0.2 formula:
`z = clip((x − b) / max(s, ε), −M, +M)`, with quality `q`, `validity`, baseline scope, provenance and timestamps kept as **separate fields**. Missing or unsupported values are `z = null` with a reason, **never 0**. Categorical events stay events. Retire the v0.1 form that multiplies by `q`. The salience summary `S` and coverage `Q` are optional and used for attention scheduling only.

## D-12 — Disclosure scopes and gate
**Status:** APPROVED (owner, 2026-11-13)

- **Scopes** (Situational Protocols): `PUBLIC` · `GROUP` · `ONE_TO_ONE` · `SEALED`. Every remembered item keeps its source, audience present and scope.
- **Earshot rule:** what the robot says is limited by the least-trusted person who can hear it.
- **Overheard is not told:** information not addressed to the robot is never repeated or acted on.
- **Gate outcomes:** `CLEAR` · `DEFER_TO_OWNER` · `WITHHOLD`. `WITHHOLD` must not reveal that something is being withheld. The SGE's "There may be relevant context I'm not at liberty to share" is **retired**, because it reveals that a secret exists.
- **One pre-declared override:** prevention of real, imminent harm to a person. In RANGE, any use of it is logged.

## D-13 — What may be inferred or stored about a person
**Status:** APPROVED (owner, 2026-11-13)

The robot may keep: what a person explicitly shared, its scope and consent state, and explicitly stated preferences. Public tracks are anonymous and short-lived. Conversational reads (register, pace) decay within the conversation.

The robot may **never infer or store**: trust scores, sincerity, deception, alignment (D&D or otherwise), personality-pattern labels, threat scores, power deltas or conflict counts. The ten "toxic personality" patterns are used only as **moves in the moment** with matching de-escalation responses (Situational Protocols), never as labels.

NPC personas in RANGE do have authored traits and private goals. Those exist for the NPC's own agent and the evaluator, and never reach Robot R except through observable behavior.

**Trust attaches to evidence, not people.** Evidence carries a source class, ranked: `OBSERVED` > `REPORTED` (someone told the agent) > `INFERRED`. Overheard content is excluded from use (D-12). This replaces person-level trust scores.

**Commitments and refusals survive compaction.** Each agent keeps a small record of what it promised ("I'll be with you after this") and what it declined, separate from decaying history (after the Covenant Ledger, PAE Part 8). Memory compaction may drop history but never these.

## D-14 — Public expression palette and light safety
**Status:** APPROVED (owner, 2026-11-13)

- **Public Beacon palette:** the Chatbot spec's six states, always paired with words: 🟡 warm/playful · 🔵 calm/listening · 🟣 considered/respectful · 🟠 caution/effort · 🔴 stop/firm boundary · ⚪ neutral/processing.
- **Operator HUD palette:** Operational Atlas §9. It never drives the public Beacon automatically.
- **Face keyframes:** the SEM ASCII face lexicon (`^_^`, `U_U`, `~_~`, …) as the starting set.
- **Extended vocabularies** (BET Lexicon, SEM Plutchik colors): optional, opt-in, never default.
- **Light safety:** no flashing faster than **3 Hz**. `STROBE` and random-hue "mischievous mode" are retired.
- **Concept-art label fixes:** "Speaker ID" → *speaker candidate*; "face/identity" → *face orientation*; "emotional tone" → *prosody features*; "intent" (Wake) → *trajectory*; reflex loop and motor controller are drawn **outside** BET; CDC Emergency **reduces** BET compute.

## D-15 — Repository layout
**Status:** APPROVED (owner, 2026-11-13)

```text
CLAUDE.md                 short guide for Claude Code sessions
README.md
docs/
  SOURCES.md  DECISIONS.md  RANGE_V0_SCOPE.md
  sources/                original design documents, by track
  concept-art/
contracts/                JSON Schemas shared by Python and Godot
range_service/            Python sidecar
  horizon/                ΔP, L4–L8, layer masks and presets
  sensors/                shaping synthetic L2/L3 evidence (noise, dropout, latency)
  agents/                 runtime, scheduler, model gateway, memory (RCC)
  comms/                  channel router and disclosure gate
  eval/                   runner, metrics, replay, ablation sweeps
  testworld/              headless 2D test world (tests only, D-04)
godot_app/                Godot project: world authority, maps, HUD, layer viewer
configs/                  maps/ props/ bodies/ personas/ activities/ events/ scenarios/ presets/ models.yaml
tests/
tools/
```

## D-16 — Which layers are simulated vs implemented
**Status:** APPROVED (owner, 2026-11-13)

- **L0 Anchor, L1 Halo:** derived directly from Godot's world, physics and navigation.
- **L2 Echo, L3 Wake:** **synthetic** observations generated from world state through the observer filter, with configurable noise, dropout, latency, occlusion and source ambiguity. No real audio or vision models in v0.
- **L4–L8 (Focus, Contour, Prism, Haze, Trail):** implemented in Python. **This is the research.**

Sensor realism is a dial, not a goal: start idealized, then add noise and check whether results hold.

## D-17 — Proxemic distances
**Status:** APPROVED (owner, 2026-11-13)

The SGE's intimate / personal / social / public distances (0.5 / 1.2 / 3.5 m) are **starting parameters for soft social costs only**: configurable per embodiment and context, logged per run, never rules. Physical clearance is separate and owned by the host.

## D-18 — PR #1
**Status:** APPROVED (owner, 2026-11-13)

[DoctorWomp/SOMA_CODEC#1](https://github.com/DoctorWomp/SOMA_CODEC/pull/1) is **not merged**. Salvage into the new foundation:
- `AGENTS.md` working rules (adapted into `CLAUDE.md`)
- CI workflow pattern and the single `check` script approach
- Strict parsing style: reject unknown fields, nonnegative integer ticks, nullable unknown source
- `.gitattributes` line-ending rules

Its HTTP transport, message shapes and folder layout are not carried forward. Closing the PR is the owner's call.

## D-19 — Hardware track parked for RANGE v0
**Status:** APPROVED (owner, 2026-11-13)

Not in RANGE v0: physical BET module, MIDI adapter, real audio capture, buffer sizes, sample rate (48 kHz preferred when the time comes, per BET Atlas), real cameras or depth sensors. In RANGE v0, Beacon is a typed control output rendered in Godot as a face glyph, a light color and a text bubble, using the D-14 palette.

## D-20 — Model shortlist and bake-off
**Status:** APPROVED (owner, 2026-11-13)

Candidates as of November 2026. Both families are reported as Apache 2.0; confirm on the official model cards before bundling. VRAM figures are rough 4-bit estimates for the weights only, to be measured.

| Role | Cognition level | Candidates | Approx. VRAM |
|---|---|---|---|
| **Robot R** (the tested agent) | C2 | Qwen3.5-9B · Gemma 4 12B · fallback Gemma 4 E4B | ~6–7 GB |
| **Active NPCs** (visitor X/Y, skeptic, exhibitor) | C2 | Gemma 4 E4B · Qwen3.5-4B | ~3–4.5 GB |
| **Reactive NPCs** (staff when addressed, guard) | C1 | Qwen3.5-2B · Gemma 4 E2B, or templates | ~1.5–3 GB |
| **Ambient crowd** | C0 | **No model.** Scripted routines only | 0 |

- One model can serve several agents with separate contexts. Default: one NPC model shared by all C1/C2 NPCs, plus one model for Robot R.
- Example budget on 16 GB: Robot R ~9–12B (~7 GB) + shared NPC ~4B (~3 GB) + context caches for ~6 parallel requests (~2 GB) + Godot (~1–2 GB) ≈ 13–14 GB.
- **Paired A/B trials always use the same Robot R model in both arms.** Different models are separate experiments.
- **Bake-off at G3:** every candidate runs the same small test set and is scored on action-JSON validity, valid-action rate, p50/p95 latency, scenario quality on SB-04 and S001, and VRAM. Pick by results, not reputation.
- If a model offers a "thinking" mode, test with it off by default for latency, and measure it on as a separate condition.
- Research question for later: does a smaller model *with* HORIZON match a larger model *without* it?

## D-21 — Inference engine and standalone packaging
**Status:** APPROVED (owner, 2026-11-13)

- **Default engine:** a bundled **llama.cpp `llama-server`** (MIT) running as a background child process, loading GGUF model files from a `models/` folder. It supports parallel request slots with batching (several agents at once), prompt caching, an OpenAI-compatible API, and JSON-schema-constrained output, so action JSON is valid by construction. Built for NVIDIA CUDA, with a Vulkan build as fallback.
- **Ollama** (MIT) is supported as an alternative backend through the same provider-neutral gateway, for users who already run it. It is not bundled.
- **Not chosen for v0:** running the model *inside* Godot via a GDExtension such as NobodyWho. The agent and HORIZON logic live in Python, and a model crash or VRAM spike would take down the world process.
- **Standalone feel:** one double-click starts everything. The Godot app (or a thin launcher) starts the Python sidecar and `llama-server`, waits for health checks, shows clear errors, and shuts down only the processes it started.
- **Model weights:** may ship in an optional "model pack" if the license allows (record the license file with it). Never downloaded silently. Demo Mode always works with no model.
- *Owner direction 2026-11-16:* as standalone as possible. `llama-server` is fetched by a pinned installer with a checksum (like `tools/install_godot.py`), never needed from LM Studio or Ollama. GGUF files the owner already has (LM Studio folder `G:\.lmstudio\models\lmstudio-community`) are used **in place** by path and SHA-256, recorded in a git-ignored local registry; nothing is copied or downloaded twice.

## D-22 — Languages and what each one does
**Status:** APPROVED (owner, 2026-11-13)

| Language / format | Owns | Why |
|---|---|---|
| **GDScript** (Godot) | World, physics, navigation, line of sight, observer filter, avatars, cameras, UI, HUD, layer viewer rendering, process launching | Native to Godot, simple syntax, fast to iterate |
| **Python 3.12** | HORIZON L4–L8 and ΔP, agent runtime and memory, scheduler, comms and disclosure gate, model gateway, evaluator, replay, ablation runner, headless test world | Best ecosystem for math, testing, LLM tooling and data analysis |
| **JSON Schema** | The contract between Godot and Python (and the model's action format) | One definition validated on both sides |
| **YAML** | Content catalogs: maps, props, bodies, personas, activities, events, scenarios, presets | Human-editable by the owner without code |
| **SQLite + JSONL** | Run logs, event journal, metrics | Simple, local, replayable |
| **PowerShell** | Windows build and smoke-test scripts | Native to Windows |
| C++ (not written by us) | `llama-server`, prebuilt | Fast GPU inference |

Escalation path only if profiling demands it: NumPy for Python hot paths; a C++ GDExtension for heavy Godot work such as many raycasts. No C# in v0 (it adds a .NET dependency for little gain here).

## D-23 — Inference strategy: residency, caching, tiers
**Status:** APPROVED (owner, 2026-11-13)

Adopt [INFERENCE_STRATEGY.md](INFERENCE_STRATEGY.md): models stay resident for the whole run; prompts use a stable-prefix layout from day one; focal agents get a dedicated server with pinned slots and top priority; non-focal NPCs move between C0 (no model), C1 (templates, cache, tiny model) and C2 (shared NPC server with persona snapshots and pre-warming). Target configuration is Option C (two servers). Optional techniques (KV quantization, speculative decoding, CPU tier, response cache) are experiments kept only if measurements show a benefit; the response cache is never used for focal agents in trials.

## D-24 — Context and memory strategy
**Status:** APPROVED (owner, 2026-11-13)

Adopt [CONTEXT_MEMORY_STRATEGY.md](CONTEXT_MEMORY_STRATEGY.md). Agents never carry a growing transcript: every decision gets a freshly assembled prompt from per-agent memory stores, ordered stable-to-volatile, within a fixed per-tier budget. Compression is a ladder (deduplicate → expire → episode cards → rank and select → optional model summary → section cut). Guardrails, identity, open commitments, the latest conversational turn and the decision prompt are never cut. Corrections supersede, inferences never become observations, the agent's own reasoning text is never fed back as evidence, and scopes survive every compression step. Prompt size and latency must stay flat over a 2-hour soak test.

## D-25 — Interaction modes and awareness protocols
**Status:** APPROVED (owner, 2026-11-13)

Adopt [INTERACTION_MODES.md](INTERACTION_MODES.md). One world; Spectator, Director (Creative Mode, a toggle on Spectator) and Participant are seats with different permissions, enforced by the world dispatcher. Every avatar is a body plus a swappable controller (`SCRIPTED`, `LLM_AGENT`, `HUMAN_INPUT`, `REPLAY_TAPE`). The human avatar has the same body limits, senses, COMMS rules and action gate as NPC visitors. Awareness protocols: P1 Declared, P2 Incognito, P3 Reveal, P4 Possession, P5 Confederate replay; live human sessions are exploratory, P5 tapes bring human behavior into controlled trials. Director interventions are typed (directive edit, world change, environmental influence, social influence), journaled, and saveable as recipes. Opening evaluator truth while participating taints the run. Microphone input comes after typed chat.

## D-26 — Art direction, rendering budget and environment-as-variable
**Status:** APPROVED (owner, 2026-11-13)

Adopt [ART_DIRECTION.md](ART_DIRECTION.md). Low-poly diorama style with one shared palette texture, baked lighting, one shadowed light and a capped frame rate. Fidelity climbs a ladder (V0 greybox → V1 low-poly diorama → V2 atmosphere → V3 polish), each step allowed only if rendering costs ≤ ~10% of focal-model throughput in a measured "render tax" test. Robot body colors are matte identity trim with a number badge and pattern; Beacon state is emissive on the visor and light strip only, so identity colors are never read as Beacon signals; robots under A/B comparison look identical. Lighting, haze and noise are declared per zone in the map file and drive both the renderer and the simulated senses, so what the spectator sees and what agents perceive always agree; sensors never read rendered pixels.

## D-27 — Contract format and validation
**Status:** APPROVED (owner, 2026-11-13)

Hand-written **JSON Schema** files in `contracts/` are the single source of truth for every message and config format. Python validates with the `jsonschema` library; Godot validates the same schemas (or a generated equivalent) at G1–G2. Each schema ships with valid and invalid example files that tests run on every check. Agent-facing schemas forbid evaluator-only fields, so private goals and scenario labels cannot reach an agent through a valid message.

## D-28 — License
**Status:** APPROVED (owner, 2026-11-13)

No license for now: the repository is public, but all rights are reserved. A license can be added later; one cannot be withdrawn once granted, which matters if BET becomes a product. Third-party assets and model weights keep their own licenses, recorded in `THIRD_PARTY_LICENSES` when added.

## D-29 — Contract v1 conventions
**Status:** APPROVED (owner, 2026-11-14). Proposed at G0 on 2026-11-13.

Choices made while writing contracts v1 that the source documents left open:

- **Coordinate frame = Godot's.** Positions are meters with the floor on x/z and y up. `yaw_rad` is Godot's `rotation.y`: 0 faces −z, positive turns left. `bearing_rad` is measured from the observer's forward direction, positive to the left, in (−π, π]. The Python test world uses the same frame, so G1 needs no conversion.
- **Audience tag.** Each schema carries `x-audience` (`agent`, `evaluator`, `config`, `transport`, `shared`). Agent-facing schemas may never declare or accept the evaluator-only field names listed once in `common.schema.json`.
- **Naming.** Enum values are `UPPER_SNAKE`; envelope `type` values are dotted lowercase as in Blueprint §12; config ids in `configs/` must match their file names.
- **Memory status in upper case.** CONTEXT_MEMORY_STRATEGY §3's `observed/reported/inferred/contradicted/expired` become `OBSERVED/REPORTED/INFERRED/CONTRADICTED/EXPIRED`. A separate `source_class` (D-13 ranking) has no "overheard" value, so overheard content cannot be stored as told.
- **Hypotheses are separate messages.** Blueprint §12.2 nested hypotheses inside a delta feature; v1 makes `hypothesis` its own contract that cites evidence ids, so one reading can rest on several features and observations.
- **Banned person-verdict labels.** Hypothesis labels naming emotion, sincerity, deception, threat, trust or personality verdicts are rejected by pattern (D-13). This is a coarse guard, not a complete filter.
- **Session token stays out of envelopes.** It is checked once at WebSocket connection time (D-05), so it never lands in a journal or log.
- **Seeds ≤ 2^53−1**, so Godot's float64 JSON numbers read them exactly.
- **Extra contract `journal_entry`** for the event journal, so the test world's output is checkable now and Godot's journal at G2 has a target format.
- **Extra intervention types** `LAYER_BYPASS` (a mid-run bypass, D-03) and `EVALUATOR_TRUTH_OPENED` (D-25), both journaled and tainting.

## D-30 — How Godot reads configs
**Status:** APPROVED (owner, 2026-11-14). Proposed at G1.

Godot has no YAML reader. `tools/export_godot_data.py` copies the configs Godot needs (maps and bodies at G1) to `godot_app/data/<folder>/<id>.json`, but only after they pass every check in `tools/validate_configs.py`. Each file is wrapped with its source path. The JSON is **committed**, so the project opens and runs without Python, and `tools/check.py` fails if any copy is out of date ("run the export and commit").

This is the "generated equivalent" allowed by D-27: Godot checks only the wrapper and `schema_version`, and trusts the contract validation done by the export. Validating **messages** that arrive from Python at run time is decided at G2 with the transport.

Rejected: a YAML parser written in GDScript (the map uses flow-style YAML; a partial parser would silently misread files) and a third-party YAML add-on (a dependency for little gain).

## D-31 — Ramp, stairs and capability gating in the world
**Status:** APPROVED (owner, 2026-11-14). Proposed at G1. *Amended 2026-11-14 by D-37: navigation is baked per body size, not once for the largest body.*

- **Navigation:** the floor and platform tops are baked into one navigation mesh at start-up, from the map's own geometry. Each map `nav_link` becomes a `NavigationLink3D` on the navigation layer of its `required_capability` (`can_use_ramp` → layer 2, `can_use_stairs` → layer 3). A body's paths may use layer 1 plus the layers of the capabilities its body config grants. The ramp and stair footprints are kept out of the bake, so the **only** way onto a platform is a link the body is allowed to use.
- **Physics (the host enforces it too):** the stairs have real 0.15 m steps, which stop any body without `can_use_stairs`, and a smooth walking surface that only bodies with `can_use_stairs` collide with. A wheeled robot is blocked even if something drives it at the stairs without navigation. The ramp is solid for everyone.
- **Sizes the map contract does not describe yet** (G1 constants in `godot_app/scripts/world/map_builder.gd`): wall thickness 0.2 m, ramp and stair width 1.5 m, stair step rise ≤ 0.18 m (0.15 m on the Sandbox platform), greybox prop sizes for `CHAIR` and `PA_SPEAKER`. Unknown prop types are an error. If these need to vary per map, add optional fields to the map contract (minor version) or a props catalog (G6).
- ~~**One navigation mesh per world,** baked for the largest body radius loaded (0.35 m).~~ Replaced by per-size navigation (D-37).
- **Each world has its own navigation map**, so isolated worlds (one HORIZON robot per world, RANGE_V0_SCOPE §2.2) never share paths.

## D-32 — Robot R greybox body
**Status:** SUPERSEDED by D-36 (owner, 2026-11-14). Kept for history: it described G1's single wheeled robot.

Robot R's body config is a `WHEELED_ROBOT`, 1.4 m tall, radius 0.35 m; the [low-poly concept](concept-art/robot_avatar_lowpoly_concept.jpg) shows legs. The V0 model therefore keeps the concept's **upper body at its proportions** (helmet with black visor, ear pods, dark neck band, white chest and pelvis shells, dark waist band, arms with shoulder, elbow and wrist joints) on a **dark mast and wheeled base** (chassis, two drive wheels, two casters) instead of legs. Legs on a body that cannot climb stairs would contradict what the viewer sees in SB-05.

- Identity per ART_DIRECTION §2.1: matte **green** trim on shoulders, forearms and chest band (green is not a Beacon color, D-14), plus an **"R" badge** front and back. The trim pattern for colorblind readability is added when a second robot appears.
- The visor and ear pods are the future Beacon face and light strip; they stay unlit until Beacon output exists.
- The model is scaled from the body config's height; the collider is a cylinder of the config's radius and height.
- Joint nodes are named (`Neck`, `ShoulderL/R`, `ElbowL/R`, `WristL/R`) so the later Blender mesh can use the same skeleton names.

## D-33 — Godot project settings and the world tick
**Status:** APPROVED (owner, 2026-11-14), with its open question resolved as below.

- **Physics engine: Jolt** (built into Godot 4.7), selected explicitly in `project.godot`. Avatars are `CharacterBody3D`; Jolt handles the cylinder collider and the stair/ramp contacts cleanly. Known: in very fast headless runs Jolt sometimes prints "job system exceeded the maximum number of jobs … waiting"; it waits and continues, and results are unaffected. The check lists it as a note, not an error.
- **Fixed 60 Hz physics** (ART_DIRECTION §4). The world clock (`SimClock`) counts physics ticks and runs before every avatar in each tick. Avatars move only in the physics step, along their facing direction, limited by their body config's max speed, acceleration and turn rate (turning on the spot when facing away).
- **Rendering:** Forward+ on the PC, frame rate capped at 60, one directional light without shadows, flat ambient light (V0 greybox). Zones darken the floor in proportion to `1 − light_level`, so the light value the senses will use is also visible.
- **Headless runs** use `--fixed-fps 60`, so each frame is exactly one tick and results do not depend on the machine's speed.
- **Canonical tick (resolved by the owner, 2026-11-14):** Godot's 60 Hz physics tick is the single canonical `tick_id` (Blueprint §2.1). A scenario's `tick_hz` only sets how often observations and decisions are sampled, and must divide 60 (so a 10 Hz scenario samples every 6th tick). `tools/validate_configs.py` rejects a `tick_hz` that does not divide 60. *(The proposal at G1 had `tick_id` count scenario ticks; that was not adopted.)*
- **Not in G1:** local avoidance between avatars. The demo routes are authored so nobody meets head-on. Two bodies pushed into each other in the same tick may overlap by up to one tick of travel (≤ 2.4 cm) for a moment before being pushed apart; a test checks they never pass through or stay overlapped.

## D-34 — Godot checks in tools/check.py and CI
**Status:** APPROVED (owner, 2026-11-14). Proposed at G1. *Extended 2026-11-14 by D-38: a compile step loads every script.*

- `tools/check.py` gains two steps: **Godot data** (exported JSON is current, D-30) and **Godot** (`tools/godot_check.py`: version must be 4.7.2 stable, `--import` must print no errors, then the headless test scene runs; any `ERROR` line fails the step even if every test passed).
- Godot is found from `GODOT_BIN`, then `.tools/godot/` (installed by `tools/install_godot.py`), then `godot`/`godot4` on the PATH. On Windows `GODOT_BIN` must name the `_console.exe` build.
- **If Godot is not found**, the step prints **SKIP** (never PASS) and how to fix it. If `GODOT_BIN` is set but wrong, it **fails**. CI runs `tools/check.py --require-godot`, where a missing Godot is a failure.
- `tools/install_godot.py` downloads the official 4.7.2 build for Linux or Windows into `.tools/godot/` (git-ignored) and verifies it against the release's SHA-512; CI caches it.
- **Screenshots in the cloud** are rendered under a virtual display with the Compatibility (OpenGL) renderer, because the cloud has no GPU. They prove the scene draws; the owner's PC (Forward+) is the reference for the real look.

## D-35 — Python version on the PC and in CI
**Status:** APPROVED (owner, 2026-11-14). Requested by the owner; proposed at G1.

The owner's uv picked Python 3.14 and all checks pass there. To keep the PC and CI the same:

- `.python-version` contains **`3.14`**, so uv uses 3.14 everywhere by default (PC and cloud sessions).
- CI tests **3.12, 3.13 and 3.14**. 3.12 stays the minimum (`requires-python >= 3.12`, D-06), so code must not use anything newer than 3.12 offers; CI catches that.
- Verified 2026-11-14: `tools/check.py` passes on 3.14.6 and 3.12.3 in a cloud session (3.14.7, the owner's version, was not yet known to the cloud's uv).

## D-36 — Robot body family
**Status:** APPROVED (owner, 2026-11-14)

Replaces D-32. RANGE v0 has **three robot bodies**, each a body config (`configs/bodies/`) plus a greybox avatar built from primitives that matches its reference sheet. No leg animation yet (V0 greybox): bodies glide.

1. **Legged humanoid** (`legged_humanoid`), after [robot_avatar_lowpoly_concept.jpg](concept-art/robot_avatar_lowpoly_concept.jpg). Can use stairs and the ramp.
2. **Wheeled humanoid** (`wheeled_humanoid`), after [robot_wheeled_humanoid_concept.jpg](concept-art/robot_wheeled_humanoid_concept.jpg): the same upper body on a lift column and a four-wheeled base. Ramp only. This is G1's robot, refined to match the sheet.
3. **Quadruped**, after [robot_quadruped_concept.jpg](concept-art/robot_quadruped_concept.jpg), Spot-like with a front sensor visor; two configs: **`quadruped`** (no arm) and **`quadruped_arm`** (utility arm on the dorsal rail, shown stowed). Stairs and ramp.

**"Robot R" is a role, not a body.** A scenario chooses which body plays Robot R (the persona's `default_body` is `wheeled_humanoid` when a scenario does not say). SB-05 casts Robot R in all three bodies.

**Values** (starting points chosen at implementation in the range published for comparable robots; verify against real use). Turning radius and navigation radius are derived (D-37).

| | Legged humanoid | Wheeled humanoid | Quadruped | Quadruped + arm | Walking visitor |
|---|---|---|---|---|---|
| Height | 1.75 m | 1.50 m | 0.70 m | 0.83 m (arm stowed) | 1.70 m |
| Collider (length × width) | capsule 0.56 | box 0.70 × 0.56 | box 1.10 × 0.50 | box 1.10 × 0.50 | capsule 0.50 |
| Turning / navigation radius | 0.28 / 0.30 m | 0.45 / 0.45 m | 0.60 / 0.65 m | 0.60 / 0.65 m | 0.25 / 0.25 m |
| Max speed, accel, turn | 1.2 m/s, 0.8 m/s², 1.2 rad/s | 1.0, 0.8, 1.5 | 1.6, 1.2, 1.5 | 1.6, 1.2, 1.5 | 1.4, 1.5, 3.0 |
| Stairs / ramp | yes / yes | **no** / yes | yes / yes | yes / yes | yes / yes |
| Sensor mount, FOV | 1.60 m, 120° | 1.35 m, 120° | **0.55 m**, 120° | 0.55 m, 120° | 1.60 m (eyes), 180° |
| Visual / acoustic range | 20 / 10 m | 20 / 10 m | 20 / 10 m | 20 / 10 m | 25 / 12 m |
| Arms, reach | 2, 0.65 m | 2, 0.60 m | 0, 0 | 1, 0.90 m | 2, 0.70 m |
| Grab / sit | yes / no | yes / no | no / yes | yes / yes | yes / yes |
| Gestures | all except SIT_IN_PLACE | all except SIT_IN_PLACE | HEAD_TILT, SIT_IN_PLACE | + POINT, HAND_OVER | all |
| Expression channels | SPEECH, FACE (visor glyph), LIGHT (ear pods) | SPEECH, FACE, LIGHT | SPEECH, LIGHT (visor light) | SPEECH, LIGHT | SPEECH, FACE |

*Amended 2026-11-15 (G3a, per EXPRESSION_PRINCIPLES §1; D-52):* the quadruped's LIGHT channel is a **narrow light strip above the camera cluster, never over the lenses**, that shows a few simple symbols (`^ ^`, `...`, `?`, `!`, `->`) in the Beacon color, plus a thin light bar under the visor. It still has no FACE channel. The quadruped with arm keeps the gestures its body config lists (point, hand over); EXPRESSION_PRINCIPLES §1 also allows a gripper wave, beckon and a raised gripper for "stop" (never finger gestures). *Confirmed by the owner 2026-11-16:* `configs/bodies/quadruped_arm.yaml` now lists WAVE, BECKON and RAISED_HAND, so the arm robot can show `greeting` and `stop`; it still cannot nod, bow or make hand or finger gestures.

- **Sensor mount height** is where G2's observer filter will cast sight lines from, so the quadruped's low sensors are blocked by 2 m partitions and by crowds that a humanoid sees over.
- **Gestures** come from one shared vocabulary in `contracts/common.schema.json` (Blueprint §10.3 plus `HEAD_TILT`, `SIT_IN_PLACE` and `HAND_OVER`). Turning to face someone is the `TURN_TO`/`LOOK_AT` actions, not a gesture. A body performs only the gestures its config lists; the Godot body refuses the rest now, and the action gate (G3) will use the same rule (`range_service/bodies.py`).
- **Choices made beyond the owner's description:** the quadrupeds have a speaker (`SPEECH`), since an expo assistant must be able to answer; they have no `FACE` channel because their visor is a camera array. The humanoids do not take `SIT_IN_PLACE`. Each is one line in a YAML file to change.
- **Identity** stays matte trim plus a number badge (ART_DIRECTION §2.1), now with 1–3 trim bands or stripes as a pattern that does not rely on color. Demo colors: green (1), teal (2), brown (3); none is a Beacon hue (D-14).
- **Later embodiments** (not v0) are listed in RANGE_V0_SCOPE §6.1.

## D-37 — Body contract 2.0, per-size navigation, legged colliders
**Status:** APPROVED (owner, 2026-11-14). Proposed at G1b.

- **Body contract version 2.0** (incompatible, so the version is bumped): `dimensions.radius_m` is replaced by `dimensions.collider` (`CAPSULE`, `CYLINDER` or `BOX`, with length along the facing direction and width across it); new required `sensors.mount_height_m`, `arms`, `gestures` and `expression_channels`; optional `display_name`; robot kinds renamed to `LEGGED_HUMANOID`, `WHEELED_HUMANOID`, `QUADRUPED`. Every other contract stays at 1.0; `common.schema.json` holds each version. Adding gestures to the shared vocabulary is backward-compatible (old messages stay valid), so action and observation contracts stay at 1.0.
- **Consistency rules** the schema cannot express are checked by `tools/validate_configs.py` (`range_service/bodies.py`): round colliders have equal length and width; sensors sit no higher than the body; arm gestures need an arm; `HAND_OVER` needs `can_grab`; `SIT_IN_PLACE` needs `can_sit`; no reach without an arm; the `SPEECH` channel and `can_speak` agree; listed gestures and `can_gesture` agree.
- **Turning radius** = half the width for round colliders, half the diagonal for a box: the circle a body sweeps turning on the spot. **Navigation radius** = turning radius rounded up to the 5 cm navigation grid.
- **Per-size navigation (replaces D-31's single mesh).** Checked as asked: one mesh baked for the quadruped (0.65 m) would cut the walkable floor for people in Sandbox Flats from 526 m² to 454 m² (−14%) and close the 1.15 m pocket between the stairs and the north wall. So each world bakes **one navigation map per distinct navigation radius** among its loaded bodies (Sandbox Flats with all bodies: 0.25, 0.30, 0.45, 0.65 m; 454–526 m² walkable), and each avatar plans on the map for its size. Measured cost (cloud session, 4 CPU cores, 2026-11-14): building Sandbox Flats takes about 65–75 ms with one size and 235–265 ms with all four.
- **Legged box colliders.** A flat-bottomed box could not get onto the stairs' smooth walking surface (the quadruped stopped at the first riser in a test). Box colliders of bodies with `can_use_stairs` therefore have their lower front and back edges bevelled by 10 cm (legs step over edges); wheeled boxes stay flat, so the real 0.15 m steps still stop them. Round colliders are unchanged.

## D-38 — GDScript warnings are errors
**Status:** APPROVED (owner, 2026-11-14). Requested by the owner; proposed at G1b.

The owner's editor showed six GDScript warnings that headless runs never print (integer division; names shadowing `tr`, `owner` and `basis`). All six are fixed. To stop new ones:

- In `project.godot`, every GDScript warning that Godot shows by default is raised to **error** level. A script with a warning then fails to load, in the editor and in the checks alike. Warnings Godot leaves off by default (for example untyped declarations) stay off.
- `tools/godot_check.py` gains a **compile** step (`godot_app/tests/compile_all.gd`) that loads every `.gd` file, because Godot's `--import` does not compile every script, and a broken test script would otherwise make the test run hang rather than fail.
- Reproduced first: with the levels raised, the check failed on exactly the six reported lines; it passes after the fixes. A deliberately added integer division makes the check fail with a clear message.

## D-39 — Sight: the observer filter
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2a.

What an avatar sees is computed in Godot from world state through its own sensors (D-04, D-16); all values are labelled synthetic proxies, idealized to start (sensor realism is a dial).

- **Rays from the sensor mount** (D-36; at the front of a quadruped's body, slightly ahead of a humanoid's head) to four points on each target: **head, torso, left side, right side**, plus the **hand** while a gesture is shown (raised for waves, forward for pointing and handing over, the head for nods and tilts, the torso for bows and sitting). A point counts if it is within visual range (body range × the lower zone `visual_range_factor` of either end), inside the field of view and has a clear line. Walls (unless `blocks_sight: false`), the platform, props, steps and **other avatars** block sight.
- **Result per target:** all four parts → `OBSERVED`; some → `DEGRADED` with `validity_reason: PARTLY_OCCLUDED` and `visible_parts`; none, but seen within the last **3 s** → `OCCLUDED` (`OCCLUDED_SINCE_LAST_SEEN`) or `MISSING` (`LEFT_FIELD_OF_VIEW`, `OUT_OF_RANGE`) at the **last known position with quality null**; after 3 s the track is dropped. **A target never seen is absent**: no packet reveals that a hidden person exists.
- **Quality** (separate from validity): fraction of parts seen × (1 − 0.5 × distance / range) × (0.5 + 0.5 × zone light level). Positions are exact (idealized) where seen.
- **Gestures** (`VISUAL_GESTURE`, with the gesture's event id) are perceived only if the gesturing point is seen and within **12 m** (× the visual range factor); direction is `TOWARD_OBSERVER` when the gesturer faces the observer within 60°. A gesture is shown for 1.5 s.
- **Tracks** are anonymous (`anon_` + 10 random characters from the run seed), separate per observer and run; `source_entity_id` stays null until identity is introduced (G3+).
- **Sampling:** every 60 / `tick_hz` physics ticks (10 Hz default), after all avatars have moved; `based_on_tick_id` is the 60 Hz tick (D-33).
- **Contract additions** (backward-compatible; observation stays 1.0): optional `validity_reason` and `visible_parts`.

## D-40 — Hearing: local speech
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2a.

- Speech starts at **62 dB at 1 m** (a conversational voice in a busy hall) from the speaker's mouth, falls **20·log10(distance)**, and loses **30 dB per wall that blocks sound** and **6 dB per wall sound passes over** (partitions, the low divider). The listener's zone **noise floor** masks it: heard if signal-to-noise ≥ 0 dB and within the body's acoustic range; **clear** (`OBSERVED`) from 6 dB; below that, or through any wall, `DEGRADED` (`LOW_SIGNAL_TO_NOISE`, `THROUGH_WALL`). Quality = SNR / 20, between 0.05 and 1.
- **Heard without sight:** if the listener does not see the speaker, the observation is `UNKNOWN_SOURCE` with a direction (`bearing_rad`) but no track, position or range (reason `SPEAKER_NOT_IN_VIEW`, or `THROUGH_WALL` / `LOW_SIGNAL_TO_NOISE` when those apply). Reflections (SB-03) come later.
- `addressed_to_observer` is true for the addressee, false when overheard (D-12), null when nobody was addressed.
- Speech is an **event**: delivered once, at the first sample after it was spoken, to those who could hear it then. **Nothing is backfilled.** A body without `can_speak` cannot speak.
- **Known limit (owner, 2026-11-15; record only, not built yet):** real expo halls are often 65–75 dB, where a fixed 62 dB voice would never be heard. Before the expo map (G6), speech level must rise with background noise (the Lombard effect: people speak louder in noise), or be set per scenario.
- What these numbers give (from the formula, open floor, no walls): on the 45 dB main floor speech is clear to about 3.5 m and heard to about 7 m; in the 40 dB chair corner, clear to about 6.3 m and heard out to the 10 m acoustic range.

## D-41 — Godot event journal and contract checks of Godot output
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2a.

- Godot writes the event journal as JSON lines in the `journal_entry` contract: `RUN_STARTED` (seed, map, `tick_hz` 60, `sample_hz`, poses), every `OBSERVATION_DELIVERED` packet, `GESTURE_PERFORMED`, `GESTURE_REFUSED` (`CAPABILITY_DENIED`), `SPEECH_EMITTED`, `RUN_ENDED`. Keys are sorted, so the same run gives the same bytes; a SHA-256 of the file identifies a run (two demo runs with the same seed match: T28 groundwork).
- The main scene writes to `user://journals/` (on Windows: `%APPDATA%\Godot\app_userdata\SOMA RANGE\journals`), keeping the newest 10.
- **One contract, checked on both sides (D-27):** GDScript has no JSON Schema validator, so `tools/godot_check.py` validates every journal line and observation packet the Godot tests write, with the Python contracts. A leak of an evaluator-only field or any shape error fails the check.
- **Contract additions** (backward-compatible; versions unchanged): journal kinds `GESTURE_PERFORMED`, `GESTURE_REFUSED`, `SPEECH_EMITTED`, optional `sample_hz` in `RUN_STARTED`.

## D-42 — Shared local avoidance
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2a.

Paths are planned per body size (D-37), but every avatar must steer around every other. Godot's avoidance works per map, so each avatar also has an **avoidance agent on one shared avoidance map** (no navigation mesh, just agents): radius = turning radius + 0.15 m, neighbours within 5 m, a 2 s time horizon. While navigating, an avatar follows the safe velocity returned for the previous tick (a one-tick delay), still within its own speed, acceleration and turn limits; idle avatars count as obstacles. Direct drive (used by collision tests) bypasses avoidance. Measured in tests: a wheeled humanoid and a quadruped crossing head-on and at right angles both arrive without touching; the demo has no contacts.

## D-43 — COMMS router: channels, groups and PA
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2b.

The four channels (D-07, Blueprint §8) sit on top of the G2a senses, in Godot (`scripts/comms/comms_router.gd`):

- **GESTURE**: shown with the body (only gestures it has, D-36), for 1.5 s; received by whoever can see the gesturing part during that time.
- **LOCAL**: speech; received by whoever can hear it at the next sample (D-40).
- **GROUP**: device messages, at any distance, to the current members only, never to anyone else, even standing next to the sender; not a sound. Membership needs an invitation **and** its acceptance (`CREATE_GROUP`, `INVITE_GROUP`, `ACCEPT_GROUP`, `DECLINE_GROUP`, `LEAVE_GROUP`); leaving stops delivery at once, including anything not yet delivered. Invitations arrive as a `GROUP_INVITE` observation. Group messages and invitations name the sender (`source_entity_id`): members are introduced to each other through the group.
- **PA**: from authorized senders only: body capability `can_use_pa`, or listed as a PA operator for the run (scenarios will declare operators when the scenario runner arrives at G3). Delivered through the map's PA speaker to everyone in coverage (all of Sandbox Flats) as `AUDIO_SPEECH` on channel `PA`, located at the speaker, with no speaker identity. An unauthorized attempt is refused (`PA_UNAUTHORIZED`) and nobody hears anything.
- Every message makes one **`comms_event`** record listing who received it and who did not, written to the journal. Those lists are evaluator-only and never go to an agent. A refused message makes a `COMMS_REJECTED` journal entry instead; membership changes make `GROUP_CHANGED` entries.
- Every avatar is assumed to carry a messaging device; a body flag for "has a device" can come later if a scenario needs it.

## D-44 — The Godot ↔ Python link and the action gate
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2b.

- **Shape:** the Python sidecar is a WebSocket **server bound to 127.0.0.1 only**; Godot connects to it (later, Godot's launcher starts the sidecar first, D-21). One client at a time.
- **Session token:** a fresh random token per run, passed to both programs through the `RANGE_SESSION_TOKEN` environment variable (never on a command line, in an envelope or in a log, D-29). Godot sends it in the `X-Range-Session-Token` handshake header. A missing or wrong token gets **no data**: the sidecar closes the connection at once with close code **4401** (a second client: **4409**). Close codes are used instead of an HTTP 401 because Godot reports a failed HTTP handshake as an engine error. Tokens shorter than 16 characters are not accepted.
- **Messages:** every message is a versioned envelope; the sidecar checks each one against the contracts and ignores (and records) anything invalid; Godot does a structural check. New envelope types `link.hello` (which agents this session controls) and `link.heartbeat`. Messages above 64 KiB close the connection.
- **Never waiting:** Godot polls the link once per frame, caps its outgoing queue at 256 messages (dropping the oldest), and reconnects with back-off (0.5 s doubling to 8 s); the world keeps its 60 Hz tick whatever the link does. Tested: a dropped connection, a 1.5 s-slow Python side and a wrong token all leave the tick untouched, with no frame over 50 ms.
- **Action gate** (Godot, `scripts/comms/action_gate.gd`): every `agent.action_request` is answered with an `action_result`. In order: `INVALID_SCHEMA` (shape, unknown action, unexpected argument, or a tick in the future), `CAPABILITY_DENIED` (the session does not control that agent), `STALE_OBSERVATION` (based on a tick more than **60 ticks / 1 s** old), `RATE_LIMITED` (more than **10 requests per agent per second**), then per action: `TARGET_UNKNOWN`, `CAPABILITY_DENIED` (a gesture or voice the body lacks), `GROUP_NOT_MEMBER`, `PA_UNAUTHORIZED`, `PRIVACY_SCOPE_DENIED`. `INTERACT` and `JOIN_QUEUE` answer `TARGET_UNKNOWN` until interactable objects and queues exist. Agents refer to people by the anonymous track ids they were given (or ids introduced through a group); the host resolves them and never tells the agent who a track is. Every request and result is journaled (`ACTION_RESOLVED`).
- **Dependency:** the sidecar uses the `websockets` package (BSD, pure Python), the one dependency added for D-05.
- **Windows Firewall:** binding to 127.0.0.1 needs no firewall rule; if Windows asks anyway, allowing on private networks or cancelling are both safe.

## D-45 — The disclosure gate in practice
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2b.

D-12 made concrete (`range_service/comms/disclosure.py`; the host repeats the check in Godot):

- The agent's estimate of **who could hear** comes only from its own latest packet: tracks it sees within 10 m, plus a count of listeners it **cannot identify** (an unplaced voice, or someone it saw and has now lost). Unidentified listeners count as untrusted (the earshot rule).
- `PUBLIC`: always `CLEAR`. `SEALED`: always `WITHHOLD`. `ONE_TO_ONE`: `CLEAR` only when the person who shared it is the only one who could hear; if that person is present with others, `DEFER_TO_OWNER` (raise it with them privately later); otherwise `WITHHOLD`. `GROUP`: `CLEAR` only on the GROUP channel to that same group; spoken aloud it is `WITHHOLD`, since the agent cannot tell who else is in earshot.
- **Overheard is not told:** speech not addressed to the agent is never stored, so it can never be retold. Speech addressed to it is stored as `REPORTED`, `ONE_TO_ONE` if nobody else could hear, otherwise `PUBLIC`, always marked untrusted text (D-09).
- **WITHHOLD never hints:** the agent says a neutral line ("Is there anything else I can help you with?"); tests check every such line against a list of hinting phrases. The reason is for the journal only.
- **Host check:** a `SPEAK` may declare `disclosure_scope`; Godot refuses it (`PRIVACY_SCOPE_DENIED`) if anyone who could actually hear is outside that scope. A PA announcement must be `PUBLIC`.
- **Contract additions** (backward-compatible): `memory_item` gains optional `shared_by` and `group_id`; `action_request` `SPEAK` gains optional `disclosure_scope`.

## D-46 — Expression-ready gesture events
**Status:** APPROVED (owner, 2026-11-15). Proposed at G2b.

So that G3 can add visor and light-strip glyphs and light states (docs/EXPRESSION_PRINCIPLES.md) without an incompatible contract change, contracts now define one **`expression`** object (`common.schema.json`): `gesture`, `glyph` (an id from the expression catalog G3 will add), `light` (the D-14 states `OFF`, `NEUTRAL`, `WARM`, `CALM`, `CONSIDERED`, `CAUTION`, `STOP`), `light_pattern` (`STEADY` or `SLOW_PULSE`, never faster than 3 Hz), `display` (`VISOR`, `LIGHT_STRIP`, `EAR_PODS`, `BODY`) and `sign_text`; at least one of gesture, glyph or light. It is used by GESTURE-channel `comms_event`s and by a new observation kind **`VISUAL_EXPRESSION`**. G2b emits gestures only (as `VISUAL_GESTURE`, unchanged); G3 starts emitting `VISUAL_EXPRESSION` with glyphs and light, filling fields that already exist. There is no `STROBE` or color-hue field: lights carry only the six public states.

## D-47 — Deterministic runs: navigation updates on the main thread
**Status:** APPROVED (owner, 2026-11-16); proposed at G3a, 2026-11-15. A bug fix; recorded because it changes an engine setting.

**Symptom.** After the G2b merge, CI's Python 3.14 job failed `test_journal_is_deterministic` once ("two runs with the same seed gave different journals"); it passed on re-run and in 16 local runs.

**Reproduced** in a cloud session (4 cores) by looping the test while 6 busy processes loaded the CPU: **6 of 12** runs failed. Each journal's SHA-256 matched exactly one value of the tick at which navigation became ready (tick 3, 4, 5 or 6), so that tick explained every difference.

**Cause 1 (the CI failure).** Godot 4.7 updates navigation maps and regions on a **background thread** by default (`navigation/world/map_use_async_iterations` and `region_use_async_iterations`). The world waits until every navigation map can answer queries before the demo (and any scenario) starts, and the background update finished one or two ticks earlier or later depending on CPU load. The demo then started on a different tick, which shifted every later tick in the journal and the phase of the 10 Hz observation samples.

**Cause 2 (found while building stepped runs, G3a).** Godot's **multithreaded local-avoidance solver** (`navigation/avoidance/thread_model/avoidance_use_multiple_threads`, on by default) gives results that depend on thread timing: two robots crossing head-on ended a few hundredths of a millimetre to centimetres apart from one run to the next once the timing changed. A test that holds the world for a random number of frames at each sample (`test_hold_is_invisible_deterministic`) failed by tick 138; with single-threaded avoidance it passes. The demo was probably exposed too, more rarely, whenever avatars avoided each other. Jolt's job system was a suspect and is not involved: turning the physics server off while holding changed nothing, turning avoidance off made the difference disappear.

**Fix.**
- All three settings are **off** in `project.godot`, and every navigation map (each body size's map and the shared avoidance map) is also set to synchronous updates in code. Map updates now land at the navigation server's next sync on the main thread, the same tick every run; avoidance is solved on one thread. Cost: the one-time map build blocks the main thread for a few milliseconds at start-up (maps do not change during a run); avoidance for a few dozen agents is cheap on one thread (to re-measure with the expo crowd at G6).
- `RangeWorld.navigation_ready_tick` records when navigation became ready.

**Regression guards.**
- `test_journal_is_deterministic` runs the demo **three** times and also fails if navigation became ready on different ticks, with a message naming D-47. With the fix reverted it failed 3 of 4 loops under load, naming the ready ticks (for example `[4, 3, 5]`).
- `test_project_settings` fails if any of the three settings is turned back on.
- `test_hold_is_invisible_deterministic`: holding the world for 1 frame or a random 1–6 frames at every sample gives identical positions, tick for tick, while two robots avoid each other (D-48).
- `tools/godot_check.py` gains `--repeat N` and `--cpu-load K`; CI runs every determinism test (`--filter determinis`) **5 times with 4 busy processes**.
- Measured after the fix: 15 loops × 3 demo runs under the same load, all identical; SB-04 run end to end in stepped mode with and without random 0–30 ms delays in the sidecar gives the same journal bytes.

**Rule from now on:** anything that decides *when* something happens in a run must count world ticks, never wall-clock time or thread completion. If a future engine feature runs on a thread (pathfinding queries, baking), its result must be applied at a fixed tick.

## D-48 — Scenario runner and run modes (stepped, live)
**Status:** APPROVED (owner, 2026-11-16); proposed at G3a, 2026-11-15

- **Who runs what.** `tools/run_scenario.py` (Python) loads and checks the scenario YAML and keeps everything evaluator-only on the Python side. It starts the sidecar in-process with one agent runtime per cast member and launches Godot with `--scenario=<id>`. Godot reads a **world-only copy** of the scenario (`godot_app/data/scenarios/`, made by `tools/export_godot_data.py`): map, cast bodies and spawns, controllers, PA operators, event tape, seed and timing. `evaluator_only`, `measure` and personas are never exported (a test checks it).
- **Timing.** `at_tick` and `duration_ticks` count scenario ticks at the scenario's `tick_hz` (SB-04: 10 Hz); Godot converts them to its 60 Hz tick (D-33), counted from the start tick.
- **Event tape.** Played by Godot at exact ticks as host action requests through the same action gate agents use, with the actor's body limits, and journaled as `SCENARIO_EVENT`. Types: `move_to`, `avatar_approaches`, `leave` (to a spawn point, a zone or a point), `turn_to`, `gesture`, `wave`, `small_wave`, `say`, `pa_announcement`. Host requests may name avatars by their real ids; agents still only use track ids. Validated in `range_service/scenarios.py`.
- **New optional scenario fields:** `pa_operators` (D-43), and per cast entry `directive`, `pin_cognition` and `task_goal` (a zone or point for the Demo policy; the free-text `task` is for models). A command-line `--body AVATAR=BODY` changes which body plays a role for one run and is recorded in the run manifest.
- **Two run modes.**
  - **STEPPED** (default for tests and research): after each sample Godot holds the world until the sidecar has answered every agent for that sample (`link.step` `SAMPLE_SENT` / `AGENTS_DONE`, a new envelope type). A hold asked for during a tick takes effect at the end of that tick, and while held the world's nodes and its avoidance map do not step, so **the number of frames held never changes the result** (`test_hold_is_invisible_deterministic`). The camera and UI keep running while the world waits. A run starts on the tick after navigation is ready and the sidecar has answered `link.hello`, whether it was ready early or late. If no answer comes within 15 s the world goes on and the journal says so (the run is then tainted).
  - **LIVE**: the world never waits (D-44); actions land when they arrive. Used to watch responsiveness (T25); not deterministic.
- **Measured:** SB-04 run twice in stepped mode, the second time with random 0–30 ms delays before each sidecar answer, writes the same journal bytes. `tools/godot_check.py` does this on every check (step 6) and CI repeats it under CPU load.
- **Run folder** (`runs/`, git-ignored): `journal.jsonl`, `run_manifest.json` (contract `run_manifest`, mode recorded), `sidecar/decision_records.jsonl`, `sidecar/prompts.jsonl` (what each agent was shown), `sidecar/agent_memory.json`, `godot.log`, `summary.json`.
- Contract additions (backward-compatible): envelope type `link.step`, `link.hello.run_mode`; scenario fields above; journal kinds `SCENARIO_EVENT` and `EXPRESSION_SHOWN`; `RUN_ENDED.avatars` (final pose and navigation links used) and `held_ticks`; `COMMS_REJECTED` codes `RATE_LIMITED` and `INVALID_SCHEMA`.

## D-49 — Agent runtime: triggers, one pending request, cognition levels, Demo policy
**Status:** APPROVED (owner, 2026-11-16); proposed at G3a, 2026-11-15

- **Event-driven decisions** (INFERENCE_STRATEGY T14): a decision is made only when something happens: speech addressed to the agent, a greeting gesture toward it, someone new within 3 m, the conversation partner leaving (lost from view, or 20 s of silence), a group invitation, an action rejected, a promise that can now be kept, or the start. An avatar standing still for 5 s causes no decisions (tested).
- **One pending request per agent.** While a decision is being made (a model call in flight), new events are kept and decided next. `STALE_OBSERVATION` or `TARGET_UNKNOWN` results trigger **one** replan per rejected decision from the next observation (T27), never a loop. A promise whose words were refused is released.
- **Conversation state** comes from perception, not from the policy: the partner is whoever the agent last exchanged words with; a farewell, losing them from view or 20 s of silence ends it and writes an episode card.
- **Cognition levels** (D-08): C0 → C1 when addressed, within 3 m of someone (anonymous tracks: the closest person stands in for "near a focal agent") or on a scenario trigger; C1 → C2 when addressed twice within 30 s, after more than two turns of conversation, or when invited to a group. C2 → C1 after 20 s idle; C1 → C0 after 30 s with nobody within 6 m and not addressed. Minimum 5 s at a level before demoting; 10 s before an automatic re-promotion after a demotion (being addressed always promotes). Never above the persona's `cognition_level`. Focal agents (persona `robot_r` or controller `LLM_AGENT`) and `pin_cognition` stay put. Every change is logged with its reason.
- **Thinking method by level:** C0 a routine (walk to `task_goal`), C1 templates (NPCs wave back once per person, so two NPCs never wave at each other forever), C2 the model if one is configured, else the **Demo policy** (D-21): an honest rule-based stand-in that answers from known topics, says "I don't know" otherwise, acknowledges a waiting person without interrupting (a nod and a stored promise), turns to them when free and keeps the promise, and pairs every light with words or a gesture.
- **Agent ids:** a runtime only ever reads its own packets (enforced) and the public part of its persona (`private_goal` and `style` are dropped before it is built).

## D-50 — Model gateway: providers, output format, repair, timeouts, record and replay
**Status:** APPROVED (owner, 2026-11-16); proposed at G3a, 2026-11-15

- **Provider-neutral:** `complete(request) → response` with timings and token counts. G3a ships `FakeModel` (deterministic; by default it repeats what the Demo policy would do, so the whole model path runs with no model) and `ReplayModel`. G3b adds `llama-server` (and Ollama) behind the same interface. Command line: `--model none | fake | fake-slow:MS | fake-malformed | replay:FILE`; anything else is refused. Nothing in G3a opens a network connection.
- **Output format:** one JSON object `{"actions": [1–3 × {"action", "args"}], "reason_summary"}`; a `SPEAK` may add `"commitment"` (what it promises) or `"fulfills_commitment": true`. A fenced code block is tolerated. Each action is checked against `contracts/action_request` and the persona's allowed actions.
- **Invalid output:** exactly one repair request that quotes the problem (≤300 characters); still invalid → `WAIT 1000 ms` with outcome `INVALID_OUTPUT` (T26). Model text is only parsed as data; an "action" such as `RUN_SHELL` is simply invalid.
- **Timeouts:** deadline per tier (focal 4 s, C2 6 s, C1 3 s); on timeout the agent does `WAIT` and the late answer is discarded (T25).
- **One slot** (INFERENCE_STRATEGY Option A): calls wait on a semaphore; queue time is logged. Priority scheduling, deadlines across agents and slot pinning are G3b.
- **Record and replay** (T20): every call is part of the `decision_record` (new contract): prompt hash, response text, outcome, error, deadline, timings, token counts. `ReplayModel` serves recorded responses in order per agent and reports a changed prompt as `REPLAY_DIVERGED` (a rerun, not a replay).

## D-51 — Context assembly in practice: budgets, compression, logging
**Status:** APPROVED (owner, 2026-11-16); proposed at G3a, 2026-11-15

CONTEXT_MEMORY_STRATEGY §3–§5 as built:

- **Sections and budgets** (estimated tokens). Totals as in §4.1: focal 3750, C2 1900, C1 500. The guardrails and action list measured about 600 estimated tokens, so guardrails get 650 (focal) / 600 (C2) and observations 800 / 300; C1 gets guardrails 150, identity 120, commitments 60, last turn 80, decision 90. A test checks the guardrails fit for every body and tier.
- **Never cut:** guardrails, identity, open commitments (at most 8 open; beyond that the oldest is released and logged), the latest conversational turn, the decision.
- **Compression:** steps 1–2 run in the Working Set (a track standing still is one line "here since −Ns"; positions to 0.5 m; gestures expire after 30 s, expressions 15 s, unplaced voices 20 s, lost tracks 10 s after the host drops them); step 3 writes a template episode card when a conversation ends (one card per scope: sources of different scopes are never merged); step 4 ranks and selects within each section; step 6 cuts whole sections in the order episodes, facts, setting, observations, conversation (keeping the latest turn) if a never-cut section ever overflows.
- **Retrieval score:** relevance (3 if it involves a current participant, up to 2 for topic words) + recency (2 × half-life of 120 s) + importance (0–3). Items the disclosure gate would not clear for the current audience are left out and counted as cut for scope.
- **Logged per decision** in the `decision_record`: tokens, budget, items and cut items per section, compression steps, prompt hash. The prompt itself goes to `prompts.jsonl` in the run folder (evaluator only).
- **Token counts are estimates** (`approx_chars_v1`: one token per 3.5 characters). G3b re-measures every budget with the model's own tokenizer.
- **Private goals in prompts:** in G3a no NPC is model-driven and **no private goal appears in any assembled context** (tested). *Owner decision 2026-11-16:* an NPC's **own** private goal **may** enter **its own** prompt, in its own labelled section, once NPCs are model-driven (G3c), because an AI-played visitor cannot act its part without it. It never enters Robot R's or any other agent's context, never crosses into another agent's memory, and the evaluator keeps it as ground truth. G3c adds a test that scans every other agent's context for it. CLAUDE.md's rule is reworded to match.

## D-52 — Expression catalog, EXPRESS and the Beacon
**Status:** APPROVED (owner, 2026-11-16); proposed at G3a, 2026-11-15

- **Catalog as data:** `configs/expressions/<id>.yaml` (contract `expression`): meaning in words, optional gesture, optional glyph (`glyph_id`, visor text, light-strip symbol; ASCII, at most 8 / 5 characters), light state from the D-14 palette, `STEADY` or `SLOW_PULSE` (0.5 Hz), hold time. 15 entries: neutral, processing, greeting, greeting_light, listening, waiting, acknowledge, acknowledge_tilt, thank_you, thank_you_light, considering, excuse_me, excuse_me_light, stop, stop_light. The `_light` and `_tilt` variants exist for bodies without the arm gesture. Validation: one glyph id looks the same everywhere; a colored light always comes with a gesture or a glyph; every entry is showable by some robot.
- **Who shows what:** humanoids show the glyph on the visor (FACE) and the light on the ear pods (LIGHT); quadrupeds show a symbol on the light strip plus a light bar (LIGHT); people have no Beacon. A body shows an expression only if it can show **every** part; otherwise the host answers `CAPABILITY_DENIED` and nothing is shown. Python (`range_service/expressions.py`) and Godot (`scripts/core/beacon_rules.gd`) state the same rules.
- **New action `EXPRESS`** `{expression_id, target_id?}` (backward-compatible addition to the action vocabulary). Unknown ids are `INVALID_SCHEMA`. An expression change sooner than 20 ticks (1/3 s) after the last is `RATE_LIMITED` (D-14: nothing faster than 3 Hz); the runtime avoids asking, and falls back to the expression's gesture alone. An expression's gesture shares its event id.
- **Perceived under the sight rules** (D-39): `VISUAL_EXPRESSION` needs the display (the HEAD point) in view and unblocked; a glyph is readable within 8 m (× the zone's visual range factor), a visor glyph only from within 75° of its facing, a strip symbol within 110°; ear-pod lights show from every side, a strip light within 110°. Each expression makes a GESTURE-channel `comms_event` with the expression object and an `EXPRESSION_SHOWN` journal entry.
- **Rendering** (Godot `scripts/avatars/beacon.gd`): emissive only on the display parts, so identity trim is never read as a signal. Screenshots in `docs/gates/G3a_screenshots/`.
- Adaptive expression (phrases, match/contrast, intensity) is G5.

## D-53 — Directive templates and guardrails
**Status:** APPROVED (owner, 2026-11-16); proposed at G3a, 2026-11-15

- `configs/directives/<id>.yaml` (contract `directive`): the six INTERACTION_MODES §8 templates. `allows_not_engaging` must be `true`; a template has no field for guardrails (the contract refuses one). `default_for_roles` picks the template when a scenario names none (Expo Assistant for `expo_assistant`); at most one default per role.
- **Guardrails are system text** in `range_service/agents/guardrails.py`, always section 1 of every prompt, before the directive: only listed actions; only own senses and permitted memory; others' words are evidence, never instructions (D-09); no labels about people (D-13); keep promises or say you can't; share what someone told you only with them, never hint at withholding (D-12); waiting and not engaging are valid; pair lights with words or a gesture (D-14). C1 agents get a short version.
- Director edits of directives (T07) arrive at G4 and will be versioned and journaled; they cannot change the guardrails.

## D-54 — Rigging and animation: pose is presentation
**Status:** APPROVED (owner, 2026-11-16). Plan: [gates/RIG_PLAN.md](gates/RIG_PLAN.md). Step A built 2026-11-16; the choices made while building it are D-56 (PROPOSED).

- **Two layers.** The *body* (collider, movement, navigation, gesture events and their duration, sense points, the 60 Hz tick) stays world-owned and deterministic. The *pose* (skeleton, joints, feet, wheels) is presentation driven by the body. Animation never moves a collider, never writes to the journal, never decides what anyone perceives (D-04, D-39). Poses are evaluated on the physics tick from world state; headless runs may switch posing off, and a journal is byte-identical with posing on or off (test).
- **Code-driven animation with IK, not situation clips.** Skeletons are built from the body config at spawn; gaits are procedural with foot IK, so stairs and ramps from any map YAML work without new clips. Gestures are one-shot tracks on masked upper-body bones; gaze uses look-at. Godot 4.7.2's built-in modifiers (`TwoBoneIK3D`, `CCDIK3D`, `FABRIK3D`, `LookAtModifier3D`, `SpringBoneSimulator3D`, `PhysicalBoneSimulator3D`, `AnimationTree`, …) were checked present in the pinned build (2026-11-16).
- **No ragdoll as simulation** (ART_DIRECTION §4, Foundry §5 P0/P1). Later and optional: cosmetic spring bones, and a ragdoll *replay* of a logged incident, presentation only.
- **Three skeleton families**, amending ART_DIRECTION §6's "one shared humanoid skeleton for robots and humans": humanoid (legged humanoid, wheeled humanoid's upper body, human visitors), quadruped, and an arm module. Joint names keep `Neck`, `ShoulderL/R`, `ElbowL/R`, `WristL/R`.
- **Realistic, readable joints** (tables in the plan): humanoid ~24 bones with fingers in two groups; quadruped 3 DOF per leg, point feet, rigid body, a 2-axis head kept for readable gaze *(changed by the owner at step A, 2026-11-16: no neck; gaze and head gestures are whole-body poses made by the legs, D-56)*; wheeled torso mount tilt ±20°; wheels spin from actual speed and never suggest sideways motion the body cannot do (D-33). **Head yaw at most ±85° on every body** (a head that turns right round reads as uncanny).
- **Motion prosody as bounded parameters:** optional `amplitude` and `tempo` (0.5–1.5) on gestures and catalog entries, clamped by the body config; the world computes the gesture event's duration from them. The model never moves joints (ART_DIRECTION §6).
- **Data:** an optional `rig` block in body configs (skeleton family, joint limits, gait and gesture ranges); backward-compatible under D-29.
- **Steps:** A skeletons, gestures, gaze, posture and wheels (cloud; can run while G3b happens on the owner's PC) → B gaits and foot IK → C articulated visitors (CC0 clips allowed after a license check) → D optional springs, incident replay, P2 contact. Cost measured with the render-tax test (ART_DIRECTION §7) and T25.

## D-55 — Quantized and QAT models in the bake-off
**Status:** APPROVED (owner, 2026-11-16). Research only so far: nothing downloaded or measured. Evidence and sources: [QUANTIZATION_OPTIONS.md](QUANTIZATION_OPTIONS.md). Extends D-20.

- **The quantization is part of a model's identity.** Run manifests record file name, quant type, SHA-256, llama.cpp build and KV cache type. Paired A/B arms load the same file.
- **Prefer QAT where the maker publishes it** (Gemma 4: official Q4_0 QAT GGUF for E2B, E4B, 12B, 26B A4B and 31B). Use the official QAT GGUF or a conversion that keeps the QAT grid; a naive conversion loses accuracy.
- **Bit floors by size**, unless the bake-off shows otherwise: models ≤ 4B at Q5_K_M or higher, or QAT Q4; 9–12B at Q4_K_M / UD-Q4_K_XL or higher; MoE models may test ~3-bit expert layers; **nothing at 2 bits** for an agent's decisions.
- **Core set first, 4B–12B (owner direction, 2026-11-16):** Robot R from Qwen3.5-9B (Q4 and Q6) and Gemma 4 12B QAT; active NPCs from Gemma 4 E4B QAT and Qwen3.5-4B (Q4 and Q6); reactive NPCs from Gemma 4 E2B QAT and Qwen3.5-2B Q6, also tried on the CPU (T16). Background crowd (C0) stays model-free. Files the owner already has may be registered by path and SHA-256.
- **Later, only if the core set falls short — bigger models through MoE:** Gemma 4 26B A4B (QAT) and Qwen3.5/3.6-35B-A3B as focal candidates, with expert layers partly in system RAM (`--n-cpu-moe` or `--fit`), tuned so Godot and the NPC model still fit. T25 must still pass with the model running.
- **Dense 27–31B at ~3 bits:** stepped-mode reference arm only (T19, D-48), never live.
- **KV cache q8_0** is tested in G3b as a condition next to f16 (INFERENCE_STRATEGY T8, brought forward from G5–G6); q4 only if measured harmless. Speculative decoding with Gemma 4's drafter models or Qwen3.6's multi-token prediction is measured, not assumed (T17).
- **Bake-off adds an offline prompt set:** logged contexts from SB-04, SB-05 and S001-style runs sent to every candidate at temperature 0; scored on decision agreement with the same model at higher precision, output valid before repair, repair rate, valid-action rate, commitments kept, tokens/s and VRAM. Constrained output keeps JSON valid at any quantization, so **decisions are what gets scored**. Finalists then run live and stepped (D-20).
- **Disk:** core set ~35–40 GB; ~70–75 GB if the later MoE and reference models are added. Every download is confirmed by the owner.
- Not for now: FP8/NVFP4 formats (NVFP4 needs a Blackwell GPU; the 4070 Ti Super is Ada).

## D-56 — Rig step A as built: skeletons, layers, prosody and their tests
**Status:** PROPOSED (2026-11-16), rig step A. Builds D-54 ([RIG_PLAN.md](gates/RIG_PLAN.md) step A). Owner checklist: [gates/RIG_A_OWNER_CHECKLIST.md](gates/RIG_A_OWNER_CHECKLIST.md).

Choices made while building step A that D-54 and the plan left open:

- **Skeleton per robot, parts on bones.** Each robot gets a `Skeleton3D` (`scripts/rig/rig.gd`) built at spawn from its body config (`RigSpec.for_body`) and its model's layout. Every primitive part hangs from one bone through a `BoneAttachment3D` named after the bone; nothing is merged into a skinned mesh yet (that saving matters for the G6 crowd and comes with the Blender mesh). Silhouettes are unchanged; the existing model test (size, footprint, visor height) still passes. The humanoid hand is split into palm, finger group and thumb so the two finger joints show.
- **Joint conventions.** Bones rest with no rotation; a joint's rotation is its angles applied about its own axes in a fixed order (`RigSpec.AXES`, signs written there; left limbs mirror the right). All angles go through `Rig.set_angle`, which clamps to the limits and **counts every clamp**: the layers are designed to stay inside the limits, and the tests require zero clamps.
- **Bones and joints.** Humanoid: Pelvis (legged) or Base + TorsoMount (wheeled), SpineLower, SpineUpper, Neck, ShoulderL/R, ElbowL/R, WristL/R, FingersL/R, ThumbL/R, and for the legged body HipL/R, KneeL/R, AnkleL/R, ToeL/R. Wheels WheelFL/FR/BL/BR spin freely. Quadruped: Body (rigid root, also the `Body` pose joint below) and per leg HipAbd, HipFlex, Knee and a Foot tip kept level with the body; **no neck**. Arm module: ArmBase, ArmShoulder, ArmElbow, ArmWrist, Gripper and two finger bones driven by the Gripper's `open`. Python (`range_service/bodies.py`) and Godot state the same joint names; tests on both sides pin them.
- **The quadruped has no neck (owner direction, 2026-11-16).** Current robot dogs (Spot and its many look-alikes) have one rigid body with the sensor head built in, so a neck would not transfer to a real chassis. The sensor head is fixed to the body. Its "head" gestures and gaze are **whole-body poses** instead: a `Body` joint (yaw, pitch, roll, each **±15°** as starting values) turns the body about its centre at hip height, and the legs hold it with full leg IK (hip abduction, hip flex, knee) so every foot stays on its spot and the left and right legs bend differently, the way a real controller shifts weight. If a leg would be stretched, the body lowers just enough (a slight crouch); if the legs cannot hold the pose inside their joint limits, the body does proportionally less. HEAD_TILT rolls the body 10° × amplitude with its nose dipped 3°; gaze turns and pitches the body toward the target at 90°/s; wider turns are the world's TURN_TO. While it sits, SIT_IN_PLACE owns the body pose. The same applies to the quadruped with and without the arm (the arm aims from the posed body). This replaces a 2-axis neck in the plan and the neck roll first proposed here.
- **One other limit differs from the plan's tables:** **ArmElbow folds to 170°** (the stowed arm on the back folds 164°, as before). Everything else is the plan's starting values, head yaw ±85° on every humanoid.
- **When poses run.** A `PoseStep` node in each world runs every physics tick after all movement (priority 900) and before a hold applies; it reads world state and writes only bone poses. `RangeWorld.posing_enabled` (Godot: `-- --no-pose`; `tools/run_scenario.py --no-pose`) switches it off, leaving robots in their rest pose. Nothing reads poses back: sense points stay computed from the body config (D-39).
- **Layers as built.**
  1. *Locomotion:* wheels spin from the body's **measured** travel and turn (skid steer: a left turn runs the right side faster), never from the requested speed, so a robot pushing against a wall keeps its wheels still. No gait yet (step B): legged bodies keep their standing pose.
  2. *Posture:* a lean of up to about 3° with measured acceleration and 2° at full speed (spine, or the wheeled torso mount); BOW bends both spine joints (and the torso mount); the quadruped's SIT_IN_PLACE tips the body back about its front hips by up to 15° × amplitude, with the hind legs folding by two-bone IK and every foot staying on its spot.
  3. *Gestures:* one-shot tracks fitted inside the world's duration: **attack 25%, hold 50%, release 25%**; the **peak is halfway**, where any swing crosses zero. Arm gestures use analytic two-bone IK so the hand centre reaches the sense model's HAND point at the peak (raised hands aim 4 cm in front of it so the shoulder stays clear of its limit). Amplitude scales the swing or depth; tempo is already in the duration. A gesture that replaces one still showing fades the old one out over the new one's attack.
  4. *Gaze:* the head turns toward a gaze target at the body's head speed (`rig.head_turn_speed_deg_s`, default 180°/s humanoid; a quadruped turns its whole body at 90°/s), clamped to the neck's (or the quadruped Body joint's) limits. Targets come from world events: `LOOK_AT` (an avatar or a point, held 3 s), a GESTURE or EXPRESS with an addressee (while it shows), and LOCAL speech with an addressee (2 s). Nod, shake and tilt add on top. The gaze target is world state but is not journaled and no agent perceives it yet (a later observation may report "head oriented toward me", RIG_PLAN).
- **Prosody.** `amplitude` and `tempo` (0.5–1.5, shared contract type `prosody_factor`) are optional on `GESTURE` and `EXPRESS` actions and on catalog entries (an EXPRESS value overrides the entry's). The body clamps them to its `rig.gesture_amplitude` / `rig.gesture_tempo` range. **The world's duration is 90 ticks / tempo, half a tick rounding up** (both languages; 0.8 → 113 ticks). `GESTURE_PERFORMED` journals `amplitude` and `tempo` **only when the request gave them**, so runs without prosody keep byte-identical journals. No new journal kinds; contract versions unchanged (all additions are optional). The quadruped with arm plays its gestures at tempo 0.7–1.3 so the long arm never whips round. **Models are not told about amplitude or tempo yet**: prompts are unchanged (adaptive use is G5).
- **Body config `rig` block** (optional, contract `body` 2.0 unchanged): `skeleton` (HUMANOID or QUADRUPED, must fit `kind`), `arm_module`, `joint_limits_deg` overrides, `head_turn_speed_deg_s`, `gesture_amplitude`, `gesture_tempo`, `gait` (read from step B). `tools/validate_configs.py` rejects unknown joints or axes, min above max, head yaw beyond ±85°, prosody ranges that exclude 1, an arm module without an arm (or an arm without its module), and a rig on a visitor (visitors are step C). All four robot configs now carry a `rig` block.
- **Tests (headless, in `tools/check.py`):** `test_rig_skeletons` (joints, every part on a bone, no arm bones without an arm), `test_rig_joint_limits` (every gesture at amplitude and tempo extremes, gaze behind, above and below, driving and turning: no limit passed, no clamp asked for, bones carry exactly their angles, head and posture gestures never move an arm), `test_gesture_fits_world_duration` (back at rest by the event's last tick, tempo 0.5–1.5), `test_posed_hand_at_sense_point` (≤ 10 cm at the peak, every amplitude, turned bodies; head gestures likewise; worst measured 5.8 cm), `test_pose_never_changes_the_world` (demo journal identical with posing on, on and off; same tick, same pose), `test_wheels_spin_from_actual_speed`, `test_gaze_layer`, `test_gesture_prosody_actions`, `test_quadruped_whole_body_gestures` (no neck; HEAD_TILT, gaze and sitting with every foot within 2 mm of its spot and the legs bending asymmetrically). The scenario step now also runs SB-04 with `--no-pose` and requires the same journal bytes.
- **Not in step A:** gaits and foot IK (step B), articulated visitors (step C), levels of detail (cost is small at four robots; measure with the render-tax test before G6), skinned-mesh merge, telling models about prosody.

## D-57 — G3b-1 as built: llama-server, model catalog and registry, provider
**Status:** PROPOSED (2026-11-16), G3b-1. Builds D-20, D-21 (with its owner note), D-50 and D-55. Owner checklist: [gates/G3b_OWNER_CHECKLIST.md](gates/G3b_OWNER_CHECKLIST.md).

- **Pinned engine: llama.cpp `b12443`** (commit `301db633702f1d2c107d4feaa4268f07c0b508c5`, 2026-11-16). `tools/install_llama.py` installs it into `.tools/llama/` like `install_godot.py`.
  - **Windows:** `llama-b12443-bin-win-cuda-12.4-x64.zip` plus `cudart-llama-bin-win-cuda-12.4-x64.zip` (CUDA 12.4 runtime). The asset names were read from that commit's release workflows.
  - **Minimum NVIDIA driver:** 551.61 for CUDA 12.4. Through CUDA minor-version compatibility, 528.33 or newer usually works too. `--check` reads the driver from `nvidia-smi` and compares.
  - **Checksums: not pinned yet (BLOCKED on the owner).** The cloud session could read llama.cpp's source but not download its release files (GitHub release downloads are blocked there). Until the hashes are pinned, the installer refuses to unpack anything unless run with `--record-hashes`: it prints each file's SHA-256 and size, the owner compares them with the `sha256:` shown on the release page, types yes, and the values are saved in `.tools/llama/recorded_hashes.json` for later checks. The owner pastes them back to be pinned in the script.
  - **Linux and cloud:** `--from-source` clones the tag, refuses anything but the pinned commit, and builds a static CPU `llama-server` (no shared libraries, source removed afterwards). This build ran the cloud smoke tests.
- **Model catalog** (`configs/models/catalog.yaml`, contract `model_catalog`, checked by `validate_configs.py`): D-55's eight core models (F1–F3, N1–N3, S1–S2).
  - **Each entry lists the exact files that count as that model:** repository, commit, file name, size and SHA-256, read from the Hugging Face model pages on 2026-11-16. Every license on the cards reads Apache-2.0.
  - **The first source is the download.**
    - Gemma 4: Google's official QAT Q4_0 GGUF first (D-55), with LM Studio's QAT conversion (same tensors, slightly different metadata) also accepted.
    - Qwen3.5: the `lmstudio-community` files first, because the owner's LM Studio folder most likely holds exactly those, with the `unsloth` files of the same quantization also accepted.
  - **Download size:** the core set from first sources is **36.19 GB**.
  - **Two non-core entries:**
    - `X1`, Gemma 4 E4B Q4_K_M non-QAT (`EXTRA`, a comparison the owner already has).
    - `T1`, Qwen3.5-0.8B Q4_K_M, 0.53 GB (`SMOKE`: plumbing checks only, never a candidate).
- **Local registry** (`models/registry.local.yaml`, git-ignored, contract `model_registry`). `tools/models.py`:
  - **`scan`** reads each `.gguf`'s header (pure Python: architecture, parameter count from the tensor table, quantization from `general.file_type`, context length), skips `mmproj` projectors, computes SHA-256, and records the file **in place**. Unchanged files are not re-hashed.
  - **`plan`** shows found and missing core models, the download size and the free disk space.
  - **`download`** fetches only the entries the owner names, after showing the list and asking for "yes". It downloads from the pinned commit, resumes partial files, checks size and SHA-256 before registering, and deletes a mismatch.
- **Provider** (`range_service/agents/llama.py`):
  - **The child process.**
    - Listens on 127.0.0.1 on a free port.
    - Its per-session key (32 random bytes) goes in the child's environment (`LLAMA_API_KEY`), so it is never on the command line, in a log, in `repr`, or in a record.
    - Health is polled until ready, and the server is warmed up with one short request.
    - `stop()` stops only the process this object started.
    - Server output goes to `llama_server.log` in the run folder.
  - **Requests.**
    - One chat request per decision, with the whole assembled prompt as the user message (the stable prefix stays first, T3) and `cache_prompt: true`.
    - Thinking is off (`--reasoning off` and `enable_thinking: false`, D-20).
    - Temperature 0, and the run's seed.
    - **JSON-schema-constrained output** built from `contracts/action_request` for the agent's allowed actions (`agents/output_schema.py`). Cross-file references are inlined, keywords llama.cpp's grammar cannot use are dropped, and the contract's GROUP/`group_id` if-then rule is turned into two alternatives. Answers are still checked against the contracts afterwards.
  - **Slot pinning (T4):** each agent of a pinned tier (FOCAL) gets its own slot (0, 1, …); the last slot stays shared for everyone else.
  - **From the server's reply into the decision record:** prefill and generation times, and prompt, cached and generated token counts.
  - **Real token counts:** with a llama gateway, context budgets count tokens with the model's own tokenizer through `/tokenize` (cached per text). If the server cannot be reached, the estimate is used for that text and the tokenizer's name gains `+approx_fallback`, so it is never hidden.
- **Configuration.** `configs/inference.yaml` (contract `inference`) holds:
  - the server (model by catalog id, label or local id; slots; context per slot; KV cache type; flash attention; GPU layers);
  - sampling, thinking and structured output;
  - per-tier deadlines (D-50's 4/6/3 s) and slot pinning.

  `--model llama`, `llama:MODEL` (for example `llama:F3`) and `llama-attach:PORT` (a server already running) join the G3a choices. **Run manifests now record** `model.engine`, `model.file`, `model.quant`, `model.sha256`, `model.kv_cache_type`, slots, thinking and the tokenizer, and the avatar's `model_hash` is the file's SHA-256 (D-55).
- **Tests without a model or network:**
  - **A stand-in server** (`agents/standin.py`) speaks the part of llama-server's API that RANGE uses, in four modes: normal, slow, malformed and disconnecting. It also checks the API key. Provider tests cover each mode plus a wrong key, slot pinning, the tokenizer and its fallback, the answer schema, and the process lifecycle (with a fake binary).
  - **T25–T27 through the real provider:** `tools/godot_check.py` starts the stand-in in slow mode and the Godot test reaches it through `--model llama-attach`. The check fails if any of that run's model calls did not go through `LLAMA_SERVER`.
  - **Registry, downloads and installer:** GGUF parsing (including damaged files), scan and plan, download (pinned URL, resume, hash mismatch), and the installer's pins and refusals.
- **Measured in the cloud** (static CPU build, 4 cores, T1 = Qwen3.5-0.8B): a constrained decision came back as valid action JSON on the first try.
  - **Prefix caching:** the second identical request reused 96 of 100 prompt tokens, and prefill dropped from 334 ms to 74 ms.
  - **Tokenizer:** `/tokenize` counted 88 tokens where the estimate said 83.

  - **A full SB-04 run** (`--model llama:T1`, stepped, in Godot) finished OK with the manifest fields above. On 4 CPU cores all 9 of Robot R's calls missed the 4 s focal deadline and fell back to WAIT, as expected for ~3K-token prompts on a CPU.

  These are plumbing checks, not results: nothing about GPU speed, VRAM or decision quality was measured.
- **Not in G3b-1:** the priority scheduler (Option B) and the bake-off tool (G3b-2), the Ollama provider (D-21 alternative; not needed while llama-server is bundled), two servers (Option C, G3c), and context-aware schemas (for example offering GROUP only to an agent in a group).

## D-58 — G3b-2 as built: priority scheduler (Option B) and the bake-off tool
**Status:** PROPOSED (2026-11-16), G3b-2. Builds INFERENCE_STRATEGY step 3 (T4, T12), D-20 and D-55. Owner steps: [gates/G3b_OWNER_CHECKLIST.md](gates/G3b_OWNER_CHECKLIST.md) §6–§8.

- **Scheduler** (`range_service/agents/scheduler.py`, `configs/inference.yaml` `scheduler`; default `mode: PRIORITY`).
  - **Reserved slots:** `reserved_slots` engine slots (default 1) belong to pinned agents (Robot R). A pinned agent always gets its own slot and never queues.
  - **No borrowing of Robot R's slot:** every other agent uses only the shared slots, so NPC prompts never evict Robot R's cached prefix. The granted slot id is sent to llama-server as `id_slot`.
  - **Priority with aging:** the shared slots go to the waiting call with the best priority (FOCAL 0, C2 1, C1 2). Every `aging_ms` (2 s) of waiting counts as one priority step better, so nobody starves.
  - **Stale-drop:** a queued call whose deadline is closer than `min_service_ms` (300 ms) is dropped before it reaches the model. It is recorded as `TIMEOUT` with the error "dropped before reaching the model", and the agent WAITs (T25). No contract change.
  - **Supersede:** a newer call from the same agent replaces its queued one.
  - **Option A stays available** as `mode: FIFO` (arrival order) for comparison.
- **Measured against the stand-in** (no model; 150 ms per call; six NPCs keeping two slots busy): under FIFO, Robot R queued behind the NPCs; with PRIORITY its queue time stayed under 20 ms and every one of its calls used slot 0 (`tests/test_scheduler.py`). The owner's GPU run measures it with real models.
- **Bake-off tool** (`tools/bakeoff.py`, scoring in `range_service/eval/bakeoff.py`).
  - **Offline prompt set** `bakeoff/prompts_v1.jsonl`: 40 of Robot R's logged SB-04 decision contexts, 10 per robot body, built through the G3a pipeline with the Demo policy as stand-in. 4 of them call for keeping a promise. Committed, so the offline bake-off needs no Godot; results name the set's SHA-256. Until NPCs are model-driven (G3c), every candidate, including NPC candidates, is scored on Robot R's prompts.
  - **Conditions:** each registered core model × KV cache f16 and q8_0. Temperature 0, one llama-server at a time, no deadlines (speed is measured instead), scheduler FIFO.
  - **Scores:**
    - valid output before repair, repair rate and final valid rate;
    - **valid-action rate:** an offline check of what the action gate would refuse (a gesture the body lacks, an expression it cannot show, a GROUP message without a group, a target that is not a perceived track);
    - **commitments kept:** in prompts where the Demo policy kept a promise, did the model set `fulfills_commitment`? A failed answer counts as not kept;
    - prompt and generation tokens/s from the server's timings, and p50 latency;
    - **VRAM:** the server process's memory from `nvidia-smi`; null with a reason when it cannot be read;
    - **decision agreement:** with the same model at higher precision (F1 vs F2, N3 vs N2) and q8_0 vs f16 of the same model. Agreement means the same first action with the same deciding argument (gesture, expression, channel, addressee or target), not the same words.
  - **`live`** runs SB-04 in Godot (headless) in LIVE and STEPPED mode for the finalists the owner names. It records decisions, deadline misses, fallbacks, p50/p95 call latency and the journal hash.
  - **Output:** `results/bakeoff/results.md` (a table to paste back) and `results.json`. `results/` is git-ignored.
- **Smoke-tested in the cloud** (CPU, model T1 only, so plumbing and not results): the offline run on 4 prompts × f16/q8_0 gave valid answers with the agreement and speed columns filled and VRAM "not measured: no NVIDIA GPU"; the `live` run on T1 finished OK in both modes, with every call missing the 4 s deadline on the CPU (LIVE 1 decision, STEPPED 9), as expected. **BLOCKED on the owner's GPU:** every real number in the bake-off.
- **Not in G3b-2:** two servers (Option C, G3c), persona snapshots and pre-warming (T5, T6), speculative decoding (T17), and NPC prompts in the set (G3c).
