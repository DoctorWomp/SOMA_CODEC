# Inference Strategy — model residency, caching and scheduling

**Status:** APPROVED (owner, 2026-11-13)
**Related:** [DECISIONS.md](DECISIONS.md) D-20 (models), D-21 (engine), D-23 (this strategy) · [RANGE_V0_SCOPE.md](RANGE_V0_SCOPE.md) gate G3

How RANGE keeps local models fast enough for live social interaction on one 16 GB GPU, and how that differs for **focal** avatars (the ones being tested) and **non-focal** avatars (crowd, staff, supporting NPCs).

All numbers here are estimates to measure at G3. Engine features are those of llama.cpp `llama-server`; verify each against the pinned version before relying on it.

---

## 1. Where the time goes

A model call has four costs:

| Cost | What it is | Typical lever |
|---|---|---|
| **Load** | Reading model weights into VRAM | Pay once at startup; never during a run |
| **Prefill** | Processing the prompt tokens (2–4K per decision) | **Prefix caching:** reuse work for the unchanged part of the prompt |
| **Generation** | Producing output tokens | Short, schema-constrained outputs; optional speculative decoding |
| **Queue wait** | Waiting for a free slot | Priorities, dedicated capacity for focal agents, fewer calls |

Generation for a short action (~50–150 tokens) is usually not the problem. **Prefill and queueing are**, and those are what caching and scheduling fix.

## 2. Techniques

Each technique with its effect, cost and when to use it.

| # | Technique | How it works | Effect | Cost / risk |
|---|---|---|---|---|
| T1 | **Keep models resident** | Load all models at app start, run a warm-up request, never unload during a run | Removes multi-second cold loads mid-scene | VRAM is reserved for the whole run |
| T2 | **Separate servers by tier** | One engine process for focal agents, one for non-focal NPCs | Focal latency unaffected by crowd load; cleaner A/B timing | A little more VRAM overhead; two processes to manage |
| T3 | **Stable-prefix prompt layout** | Order every prompt from most to least stable: rules + action schema → identity/persona → scenario facts → memories → latest observations → request | The engine reuses cached work for the unchanged prefix and only processes the new tail | Must never put changing values (timestamps, counters) early in the prompt |
| T4 | **Slot pinning** | Each focal agent always uses the same engine slot, so its prefix stays cached there | Near-instant prefill after the first call | Pinned slots are unavailable to others |
| T5 | **Persona snapshots** | At scene load, precompute each important NPC's identity prefix and save that slot state; restore it when the NPC is promoted | Promotion from scripted to model-driven is fast instead of a full prefill | Disk/RAM for snapshots; snapshots tied to model + prompt version |
| T6 | **Predictive pre-warming** | When Focus/Trail suggest an NPC is about to interact (approaching R, repeated glances, scenario trigger), restore its snapshot into a free slot *before* it speaks | Hides promotion latency entirely when the prediction is right | Wasted work when wrong; needs spare slots |
| T7 | **Tight context budgets** | Fixed per-tier budgets with deterministic compaction (RCC) | Smaller caches → more parallel slots in VRAM; faster prefill | Must protect commitments and permissions during compaction (D-13) |
| T8 | **KV cache quantization** | Store the attention cache at 8-bit instead of 16-bit | Roughly halves cache memory → more slots or longer contexts | Small quality risk; measure. May require flash attention |
| T9 | **Constrained, short output** | JSON-schema-constrained actions, low token cap, action field first | Valid output by construction; bounded generation time | Schema must be kept in sync with contracts |
| T10 | **Streaming speech** | Stream the `text` field of `SPEAK` so the bubble (and later TTS) starts early | Feels faster | Must still validate the full action before execution |
| T11 | **Fast-lane nonverbal cue** | Deterministic rules trigger an immediate nod/glance/light while the model thinks (BET Atlas Plate 06) | Covers model latency the way a human "mm" does | Must be honest (an acknowledgment, not a decision) |
| T12 | **Priority scheduling** | Queue order: player-facing / focal > turn-taking conflicts > task planning > background, with deadlines, fairness aging, one pending request per agent, stale requests dropped | Focal decisions never wait behind crowd chatter | Background agents get slower under load (by design) |
| T13 | **Continuous batching** | The engine processes several NPC requests together | Higher throughput for the NPC tier | Each individual request is slightly slower; batching can make outputs slightly nondeterministic |
| T14 | **Event-driven calls** | HORIZON and the scheduler decide *when* a decision is needed; no polling | Far fewer calls overall | Trigger rules must be tested so agents don't "freeze" |
| T15 | **Response cache (non-focal only)** | Cache answers to repeated public questions ("where is the café?") per map version | Staff answer instantly | Less variety; **never used for focal agents in trials** |
| T16 | **CPU tier** | Run a tiny model (0.8–2B) on the CPU for reactive lines | Uses the 16-core CPU and 96 GB RAM; frees GPU for focal agents | Slower per request; CPU also runs the simulation; measure |
| T17 | **Speculative decoding** | A tiny "draft" model from the same family proposes tokens; the big model verifies | Faster generation for the focal model | Needs a tokenizer-compatible draft model; small gain for short outputs; measure |
| T18 | **No model swapping mid-run** | Bake-offs swap models *between* runs, never during | Stable timing | — |
| T19 | **Stepped research mode** | Simulation time pauses at decision points (Blueprint §3.1) | Latency stops affecting behavior; good for logic experiments | Not valid for real-time claims |
| T20 | **Record and replay outputs** | Every model response is logged with its request; replays reuse them | Exact replays, cheap sweeps of non-model changes | Re-running the model is labeled a rerun, not a replay |

## 3. Focal vs non-focal

### 3.1 Focal avatars (Robot R and any avatar under HORIZON test)

| Aspect | Strategy |
|---|---|
| Model | The larger model (9–12B class, D-20), **same model in both A/B arms** |
| Engine | **Dedicated focal server** (T2), resident all run (T1) |
| Slots | 1 pinned slot per focal agent (T4), plus 1 spare for pre-warming or a second sandbox robot |
| Context | ~4–6K tokens, stable prefix (T3), deterministic compaction (T7) |
| When it thinks | Event-driven from HORIZON triggers (T14); highest priority (T12) with a deadline; fallback `WAIT` on timeout |
| While it thinks | Fast-lane nonverbal cue (T11); speech streamed (T10) |
| Output | Schema-constrained action (T9) |
| Not allowed in trials | Response cache (T15); mid-run model changes (T18) |
| Optional, measured | KV quantization (T8), speculative decoding (T17) |
| Fairness | Record queue time, prefill tokens, cached tokens and generation time per call, per arm. HORIZON arms may send longer or shorter prompts; report it rather than hide it. |

### 3.2 Non-focal avatars (crowd, staff, supporting NPCs)

Three cognition levels (D-08), with promotion and demotion:

| Level | Who | How they think | Model use |
|---|---|---|---|
| **C0 Background** | Ambient walkers, idle staff | Scripted routines, utility choices, canned gestures and barks | **None** |
| **C1 Reactive** | Staff answering a question, a guard on patrol, a visitor briefly addressed | Templates first; response cache (T15); tiny model for short lines (T16 or small GPU model) | Occasional, short |
| **C2 Agentic** | Scenario NPCs (Visitor X/Y, skeptic, exhibitor) while engaged | Shared NPC server (~4B), slot pool with LRU affinity, persona snapshots (T5), pre-warming (T6), batching (T13) | Event-driven, budgeted |

**Lifecycle with hysteresis:**

```text
C0 ──(addressed · near a focal agent · scenario trigger)──▶ C1
C1 ──(conversation continues · goal conflict · invited to a group)──▶ C2
       on entry: take a free NPC slot, restore persona snapshot (T5)
C2 ──(idle ~20 s, conversation ended)──▶ C1
       on exit: save the slot state, release the slot
C1 ──(out of interaction range for a while)──▶ C0
Prediction: Focus/Trail flag a likely promotion → pre-warm (T6)
```

Scenario-critical NPCs (for example X and Y in S001) can be **pinned at C2** for the scenario's duration. Identity, goals and memory persist across levels; only the *thinking method* changes.

## 4. Build options

Four ways to assemble the above, from simplest to most capable:

| Option | Setup | Pros | Cons | Use |
|---|---|---|---|---|
| **A. One server, one model** | A single ~4B model serves everyone | Simplest, least VRAM | Robot R limited to 4B; R competes with NPCs for slots | First integration at G3 |
| **B. One server, focal priority** | Single model, but R gets a pinned slot and top priority | Still simple; R never waits behind NPCs | R still limited to the shared model size | Quick upgrade from A |
| **C. Two servers (recommended v0 target)** | Focal server (9–12B) + NPC server (~4B), both resident | Fair A/B timing, best focal quality, NPC load isolated | More VRAM; two processes | Main configuration |
| **D. Three tiers** | C + a CPU tiny model for C1 lines | Most GPU headroom for focal and C2 | Most moving parts; CPU contention with the simulation | Only if C runs out of GPU |

## 5. Example VRAM budget (Option C, 16 GB)

| Item | Estimate |
|---|---|
| Focal model, ~9–12B at 4-bit | ~6–7 GB |
| Focal cache: 2 slots × ~6K tokens | ~0.5–1.5 GB |
| NPC model, ~4B at 4-bit | ~3 GB |
| NPC cache: 4 slots × ~2K tokens | ~0.5–1 GB |
| Godot (low-poly) | ~1–2 GB |
| Headroom | ~1.5 GB |
| **Total** | **~13–15 GB** |

Cache sizes vary a lot by model architecture and quantization. This table gets replaced by measured values at G3.

## 6. Configuration (illustrative)

```yaml
# configs/inference.yaml — field names not final until G0 contracts
servers:
  focal:
    model: models/<focal-model>.gguf
    parallel_slots: 2
    context_per_slot: 6144
    kv_cache_type: f16          # experiment: q8_0
    resident: true
  npc:
    model: models/<npc-model>.gguf
    parallel_slots: 4
    context_per_slot: 2048
    kv_cache_type: f16
    resident: true
tiers:
  focal:     {server: focal, pin_slot: true, priority: 0, deadline_ms: 4000, response_cache: false}
  c2:        {server: npc, slot_policy: lru_affinity, persona_snapshots: true, prewarm: true, priority: 1}
  c1:        {templates_first: true, response_cache: true, model: none_or_tiny}
  c0:        {model: none}
promotion:
  c1_to_c2:  [addressed_twice, invited_to_group, scenario_trigger]
  c2_idle_demote_s: 20
fallback_on_timeout: WAIT
```

## 7. Implementation plan

| Step | When | What | Measure |
|---|---|---|---|
| 1 | G3a | Option A: one server, one model, Robot R only. Stable-prefix prompt layout (T3) from day one | Baseline prefill, generation and total latency; cache hit rate |
| 2 | G3a | Record-and-replay of model outputs (T20); timeout → `WAIT` | Replay matches log exactly |
| 3 | G3b | Priority scheduler with deadlines and stale-drop (T12); slot pinning (T4) | Focal p50/p95 under NPC load |
| 4 | G3b | Option C: split focal and NPC servers (T2); model bake-off (D-20) | Same, plus VRAM |
| 5 | G3c | C0/C1/C2 lifecycle with hysteresis; persona snapshots (T5) | Promotion latency |
| 6 | G5 | Pre-warming hooks from Focus/Trail (T6); fast-lane nonverbal cue (T11) | Promotion latency when predicted; perceived response time |
| 7 | G5–G6 | Experiments behind flags: KV quantization (T8), speculative decoding (T17), CPU tier (T16), response cache (T15) | Each compared against baseline; kept only if it helps |

**Instrumentation from step 1:** for every model call log agent, tier, server, slot, queue wait, prompt tokens, cached tokens, prefill time, generated tokens, generation time, total time, deadline met or missed, and whether the resulting action was still valid when it arrived. The engine reports timing and cache statistics per request; verify the exact fields on the pinned version.

## 8. Connection to the design documents

- **CDC "pre-load the likely next template"** (CDC v0.1) becomes persona snapshots and pre-warming (T5, T6).
- **CDC "identity anchor always resident"** becomes the cached stable prefix (T3, T4).
- **RCC context tiers** (Runtime v0.2 §9) set the prompt order and budgets (T3, T7).
- **BET fast lanes** (BET Atlas Plate 06) become the fast-lane nonverbal cue (T11).
- **Blueprint §10.4 scheduler** is implemented by T12–T14.
