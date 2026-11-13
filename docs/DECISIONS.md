# Decisions

Settled answers to conflicts and open choices across the source documents.
**An APPROVED decision overrides any source document.** Sources are indexed in [SOURCES.md](SOURCES.md).

Status values: **PROPOSED** (recommended default, awaiting owner review) · **APPROVED** · **REJECTED** · **SUPERSEDED**.
To change a decision, edit its entry and note the date. Do not silently delete entries.

| ID | Topic | Status |
|---|---|---|
| D-01 | Document precedence | PROPOSED |
| D-02 | One gate numbering | PROPOSED |
| D-03 | Experiment axes, layer masks and presets | PROPOSED |
| D-04 | World authority | PROPOSED |
| D-05 | Godot ↔ Python transport | PROPOSED |
| D-06 | Versions, machine and models | PROPOSED |
| D-07 | Venue announcement channel name | PROPOSED |
| D-08 | Naming collisions | PROPOSED |
| D-09 | CDC modes in RANGE | PROPOSED |
| D-10 | How confidence is represented | PROPOSED |
| D-11 | ΔP formula | PROPOSED |
| D-12 | Disclosure scopes and gate | PROPOSED |
| D-13 | What may be inferred or stored about a person | PROPOSED |
| D-14 | Public expression palette and light safety | PROPOSED |
| D-15 | Repository layout | PROPOSED |
| D-16 | Which layers are simulated vs implemented | PROPOSED |
| D-17 | Proxemic distances | PROPOSED |
| D-18 | PR #1 | APPROVED (owner, 2026-11-13) |
| D-19 | Hardware track parked for RANGE v0 | PROPOSED |
| D-20 | Model shortlist and bake-off | PROPOSED |
| D-21 | Inference engine and standalone packaging | PROPOSED |
| D-22 | Languages and what each one does | PROPOSED |
| D-23 | Inference strategy: residency, caching, tiers | PROPOSED |
| D-24 | Context and memory strategy | PROPOSED |
| D-25 | Interaction modes and awareness protocols | PROPOSED |

---

## D-01 — Document precedence
**Status:** PROPOSED

Precedence, highest first: non-negotiable safety/privacy/honesty rules → this file → CANON → SUPPORTING → SEED → REFERENCE. Within a status, newer wins. Full rules and the status of every document are in [SOURCES.md](SOURCES.md).

CANON: Master Build Blueprint v1.0, HORIZON Sensory Layer Operational Atlas v0.2, ΔP Math & Control Addendum v0.2.

## D-02 — One gate numbering
**Status:** PROPOSED

Use the Blueprint's **G0–G7** gates as the only build plan. Retire: Assessment clusters RG-01..10, PR #1 milestones M0–M6, Runtime v0.2 Gates A–D, HORIZON v0.1 phases 0–6, Addendum P0–P3. Their content is folded into G0–G7 in [RANGE_V0_SCOPE.md](RANGE_V0_SCOPE.md).

## D-03 — Experiment axes, layer masks and presets
**Status:** PROPOSED

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
**Status:** PROPOSED

**Godot is the only world authority** in the application: positions, physics, navigation, line of sight, delivery eligibility, action execution, simulation clock (`tick_id`).

A small **Python headless test world** (2D, no graphics) implements the same contracts so comms, privacy, ΔP and gate logic can be tested without Godot. It is a test double, not a second authority, and never runs alongside Godot.

## D-05 — Godot ↔ Python transport
**Status:** PROPOSED

Loopback **WebSocket** with versioned JSON envelopes and a launch-time session token, bound to `127.0.0.1` only (Blueprint §12). PR #1's HTTP harness is not carried forward.

## D-06 — Versions, machine and models
**Status:** PROPOSED

- **Development machine:** Windows 11 Pro, AMD Ryzen 9 9950X (16 cores / 32 threads), 96 GB RAM, **NVIDIA RTX 4070 Ti Super, 16 GB VRAM**.
- **Model sizing for that GPU (estimates to verify at G3):** one small/medium (~4B-class) model shared by 3–5 agents fits comfortably; one ~9–12B-class model at 4-bit quantization fits alongside Godot with moderate context; two large models loaded at once is tight. The Runtime v0.2 doc's Q4 load estimates (E4B ≈ 4.5 GB, 12B ≈ 6.7 GB) exclude KV cache and parallel slots. LLM-policy ablation sweeps will be limited by GPU throughput; scripted-policy sweeps by CPU.
- **Python:** 3.12 (Blueprint). Pin exact dependency versions in a lockfile after a tested install.
- **Godot:** the latest *verified stable* 4.x release, chosen and pinned at G1. Sources disagree (Blueprint says 4.7.2, PR #1 used 4.5.1); verify what exists before pinning.
- **Models:** see D-20 (shortlist and bake-off) and D-21 (engine and packaging). Never downloaded automatically.

## D-07 — Venue announcement channel name
**Status:** PROPOSED

Use **`PA`** (Blueprint). Retire `SERVER` (Runtime v0.2). Channels are `GESTURE`, `LOCAL`, `GROUP`, `PA`.

## D-08 — Naming collisions
**Status:** PROPOSED

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
**Status:** PROPOSED

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
**Status:** PROPOSED

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
**Status:** PROPOSED

Use the Addendum v0.2 / Operational Atlas v0.2 formula:
`z = clip((x − b) / max(s, ε), −M, +M)`, with quality `q`, `validity`, baseline scope, provenance and timestamps kept as **separate fields**. Missing or unsupported values are `z = null` with a reason, **never 0**. Categorical events stay events. Retire the v0.1 form that multiplies by `q`. The salience summary `S` and coverage `Q` are optional and used for attention scheduling only.

## D-12 — Disclosure scopes and gate
**Status:** PROPOSED

- **Scopes** (Situational Protocols): `PUBLIC` · `GROUP` · `ONE_TO_ONE` · `SEALED`. Every remembered item keeps its source, audience present and scope.
- **Earshot rule:** what the robot says is limited by the least-trusted person who can hear it.
- **Overheard is not told:** information not addressed to the robot is never repeated or acted on.
- **Gate outcomes:** `CLEAR` · `DEFER_TO_OWNER` · `WITHHOLD`. `WITHHOLD` must not reveal that something is being withheld. The SGE's "There may be relevant context I'm not at liberty to share" is **retired**, because it reveals that a secret exists.
- **One pre-declared override:** prevention of real, imminent harm to a person. In RANGE, any use of it is logged.

## D-13 — What may be inferred or stored about a person
**Status:** PROPOSED

The robot may keep: what a person explicitly shared, its scope and consent state, and explicitly stated preferences. Public tracks are anonymous and short-lived. Conversational reads (register, pace) decay within the conversation.

The robot may **never infer or store**: trust scores, sincerity, deception, alignment (D&D or otherwise), personality-pattern labels, threat scores, power deltas or conflict counts. The ten "toxic personality" patterns are used only as **moves in the moment** with matching de-escalation responses (Situational Protocols), never as labels.

NPC personas in RANGE do have authored traits and private goals. Those exist for the NPC's own agent and the evaluator, and never reach Robot R except through observable behavior.

**Trust attaches to evidence, not people.** Evidence carries a source class, ranked: `OBSERVED` > `REPORTED` (someone told the agent) > `INFERRED`. Overheard content is excluded from use (D-12). This replaces person-level trust scores.

**Commitments and refusals survive compaction.** Each agent keeps a small record of what it promised ("I'll be with you after this") and what it declined, separate from decaying history (after the Covenant Ledger, PAE Part 8). Memory compaction may drop history but never these.

## D-14 — Public expression palette and light safety
**Status:** PROPOSED

- **Public Beacon palette:** the Chatbot spec's six states, always paired with words: 🟡 warm/playful · 🔵 calm/listening · 🟣 considered/respectful · 🟠 caution/effort · 🔴 stop/firm boundary · ⚪ neutral/processing.
- **Operator HUD palette:** Operational Atlas §9. It never drives the public Beacon automatically.
- **Face keyframes:** the SEM ASCII face lexicon (`^_^`, `U_U`, `~_~`, …) as the starting set.
- **Extended vocabularies** (BET Lexicon, SEM Plutchik colors): optional, opt-in, never default.
- **Light safety:** no flashing faster than **3 Hz**. `STROBE` and random-hue "mischievous mode" are retired.
- **Concept-art label fixes:** "Speaker ID" → *speaker candidate*; "face/identity" → *face orientation*; "emotional tone" → *prosody features*; "intent" (Wake) → *trajectory*; reflex loop and motor controller are drawn **outside** BET; CDC Emergency **reduces** BET compute.

## D-15 — Repository layout
**Status:** PROPOSED

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
**Status:** PROPOSED

- **L0 Anchor, L1 Halo:** derived directly from Godot's world, physics and navigation.
- **L2 Echo, L3 Wake:** **synthetic** observations generated from world state through the observer filter, with configurable noise, dropout, latency, occlusion and source ambiguity. No real audio or vision models in v0.
- **L4–L8 (Focus, Contour, Prism, Haze, Trail):** implemented in Python. **This is the research.**

Sensor realism is a dial, not a goal: start idealized, then add noise and check whether results hold.

## D-17 — Proxemic distances
**Status:** PROPOSED

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
**Status:** PROPOSED

Not in RANGE v0: physical BET module, MIDI adapter, real audio capture, buffer sizes, sample rate (48 kHz preferred when the time comes, per BET Atlas), real cameras or depth sensors. In RANGE v0, Beacon is a typed control output rendered in Godot as a face glyph, a light color and a text bubble, using the D-14 palette.

## D-20 — Model shortlist and bake-off
**Status:** PROPOSED

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
**Status:** PROPOSED

- **Default engine:** a bundled **llama.cpp `llama-server`** (MIT) running as a background child process, loading GGUF model files from a `models/` folder. It supports parallel request slots with batching (several agents at once), prompt caching, an OpenAI-compatible API, and JSON-schema-constrained output, so action JSON is valid by construction. Built for NVIDIA CUDA, with a Vulkan build as fallback.
- **Ollama** (MIT) is supported as an alternative backend through the same provider-neutral gateway, for users who already run it. It is not bundled.
- **Not chosen for v0:** running the model *inside* Godot via a GDExtension such as NobodyWho. The agent and HORIZON logic live in Python, and a model crash or VRAM spike would take down the world process.
- **Standalone feel:** one double-click starts everything. The Godot app (or a thin launcher) starts the Python sidecar and `llama-server`, waits for health checks, shows clear errors, and shuts down only the processes it started.
- **Model weights:** may ship in an optional "model pack" if the license allows (record the license file with it). Never downloaded silently. Demo Mode always works with no model.

## D-22 — Languages and what each one does
**Status:** PROPOSED

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
**Status:** PROPOSED

Adopt [INFERENCE_STRATEGY.md](INFERENCE_STRATEGY.md): models stay resident for the whole run; prompts use a stable-prefix layout from day one; focal agents get a dedicated server with pinned slots and top priority; non-focal NPCs move between C0 (no model), C1 (templates, cache, tiny model) and C2 (shared NPC server with persona snapshots and pre-warming). Target configuration is Option C (two servers). Optional techniques (KV quantization, speculative decoding, CPU tier, response cache) are experiments kept only if measurements show a benefit; the response cache is never used for focal agents in trials.

## D-24 — Context and memory strategy
**Status:** PROPOSED

Adopt [CONTEXT_MEMORY_STRATEGY.md](CONTEXT_MEMORY_STRATEGY.md). Agents never carry a growing transcript: every decision gets a freshly assembled prompt from per-agent memory stores, ordered stable-to-volatile, within a fixed per-tier budget. Compression is a ladder (deduplicate → expire → episode cards → rank and select → optional model summary → section cut). Guardrails, identity, open commitments, the latest conversational turn and the decision prompt are never cut. Corrections supersede, inferences never become observations, the agent's own reasoning text is never fed back as evidence, and scopes survive every compression step. Prompt size and latency must stay flat over a 2-hour soak test.

## D-25 — Interaction modes and awareness protocols
**Status:** PROPOSED

Adopt [INTERACTION_MODES.md](INTERACTION_MODES.md). One world; Spectator, Director (Creative Mode, a toggle on Spectator) and Participant are seats with different permissions, enforced by the world dispatcher. Every avatar is a body plus a swappable controller (`SCRIPTED`, `LLM_AGENT`, `HUMAN_INPUT`, `REPLAY_TAPE`). The human avatar has the same body limits, senses, COMMS rules and action gate as NPC visitors. Awareness protocols: P1 Declared, P2 Incognito, P3 Reveal, P4 Possession, P5 Confederate replay; live human sessions are exploratory, P5 tapes bring human behavior into controlled trials. Director interventions are typed (directive edit, world change, environmental influence, social influence), journaled, and saveable as recipes. Opening evaluator truth while participating taints the run. Microphone input comes after typed chat.

