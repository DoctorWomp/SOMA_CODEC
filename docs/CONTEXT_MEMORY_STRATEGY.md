# Context & Memory Strategy — bounded prompts, adaptive compression, no rot

**Status:** APPROVED (owner, 2026-11-13)
**Related:** [INFERENCE_STRATEGY.md](INFERENCE_STRATEGY.md) (caching, slots, tiers) · [DECISIONS.md](DECISIONS.md) D-12, D-13, D-24 · Blueprint §11 (RCC) · Runtime v0.2 §9 · CDC v0.1 (bounded interaction window) · PAE Part 8 (Covenant Ledger)

How every agent in RANGE keeps a long memory without carrying a long prompt, so runs can last hours without slowing down (**bloat**) or getting confused by stale, contradictory or self-generated material (**rot**).

---

## 1. Two problems

| Problem | What happens | Symptom in RANGE |
|---|---|---|
| **Context bloat** | The prompt grows with every event and turn | Each decision takes longer to process; fewer agents fit in VRAM; the sim lags as the run goes on |
| **Context rot** | The prompt fills with stale observations, superseded beliefs, the agent's own past guesses, and important facts buried in the middle | The agent repeats old mistakes, acts on things that are no longer true, forgets promises, drifts out of character |

Both have the same root cause: **treating the prompt as the memory.**

## 2. The core rule: the prompt is a view, not the memory

- **No growing transcripts.** Agents never carry an ever-growing chat history. Every decision gets a **freshly assembled** prompt, built from stores, within a fixed budget.
- **Store once, select per call.** Everything that happens is written once to the event journal and the agent's own memory stores (on disk). The context assembler picks what this decision needs.
- **Bounded by construction.** A prompt can't grow past its budget no matter how long the run lasts. Memory on disk can grow, under the retention rules in §8.

Result: prompt size and per-decision latency should be **flat over time**, whether minute 2 or hour 2. That is the main thing the tests in §10 check.

## 3. Memory stores (per agent)

| Store | Holds | Lifetime | Changes |
|---|---|---|---|
| **Identity Anchor** | Role, directive, persona, capabilities, guardrails, action schema | Whole run (Director edits are versioned) | Rarely |
| **Commitments & Refusals** | What the agent promised ("I'll help you after this") and declined ("I can't open that door") | Until fulfilled, released or expired | Occasionally |
| **Working Set** | Current goal, active conversation (last few turns), latest observations, current HORIZON scene state | Seconds to minutes; rolling | Every decision |
| **Episodic Ledger** | Compact cards for finished interactions: who, what was explicitly said, what was decided, what is still open | Decays with the forgetting kernel; capped per agent | At episode end |
| **Relational Ledger** | Facts explicitly shared with this agent, with owner, audience and scope (D-12) | Until released, forgotten on request, or run end | When something is shared |
| **World Knowledge** | Public facts this agent has actually discovered (signs read, map consulted) | Run | When discovered |
| **Trail buffer (L8)** | Timestamped short event history for HORIZON | Rolling, ~10–120 s | Continuously |
| *Evaluator truth* | Private goals, scenario labels, world truth | — | **Never assembled into any agent's context** |

Every memory item carries: `id`, `owner_id`, `source_event_id`, `observed_at`, `expires_at`, `status` (`observed` / `reported` / `inferred` / `contradicted` / `expired`), `scope`, `importance`, and `version` (D-13).

## 4. Context assembly

### 4.1 Section order: stable first, volatile last

This order serves two purposes. The engine's prefix cache reuses everything up to the first changed section ([INFERENCE_STRATEGY](INFERENCE_STRATEGY.md) T3). And models attend best to the start and end of a prompt, so the rules go first and the latest situation plus the question go last.

| # | Section | Stability | Focal budget | C2 NPC budget | Cut order under pressure |
|---|---|---|---|---|---|
| 1 | Guardrails + action schema | Fixed | ~400 | ~300 | **Never** |
| 2 | Identity Anchor | Run | ~300 | ~200 | **Never** |
| 3 | Commitments & Refusals (open ones) | Occasional | ~200 | ~100 | **Never** (cap count, oldest released first) |
| 4 | Scenario / setting facts | Scene | ~200 | ~100 | Summarize to one line |
| 5 | Relevant Relational + World facts (retrieved) | Episode | ~400 | ~150 | Fewer items |
| 6 | Relevant episodic cards (retrieved, ≤3) | Episode | ~400 | ~150 | Fewer cards → 1 → 0 |
| 7 | Active conversation (last N turns) | Turn | ~800 | ~400 | Older turns → one-line recap; **never** drop the latest turn |
| 8 | HORIZON scene state / observations | Every call | ~900 | ~400 | Lower-ranked tracks first; keep `UNKNOWN` markers |
| 9 | Current goal + the decision being asked | Every call | ~150 | ~100 | **Never** |
| | **Total input** | | **~3.75K** | **~1.9K** | |
| | Output cap | | ~200 | ~120 | |

C1 reactive NPCs use only sections 1, 2, 7 (last turn) and 9: about 0.5K tokens. C0 uses no model.

Budgets are starting values. They are measured with the real tokenizer, not estimated.

### 4.2 Memory updates at boundaries

Sections 3–6 change only at **turn or episode boundaries**, not on every tick. That keeps the cached prefix valid for many consecutive decisions. Only sections 7–9 change every call.

### 4.3 Retrieval

Sections 5 and 6 are selected by a deterministic score with documented weights:
**relevance** to the current participants, location and topic · **recency** (forgetting kernel) · **importance** (set when the item was stored; commitments, corrections and explicit disclosures rank high) · **scope permission** for everyone currently in earshot (D-12).
No embedding model is needed for v0; tags and IDs are enough. Embeddings are a later experiment.

## 5. Adaptive compression ladder

Applied in order until the context fits its budget. Steps 1–4 are deterministic and cheap; step 5 runs off the critical path; step 6 is the last resort.

| Step | Technique | Example |
|---|---|---|
| **1. Deduplicate and delta** | Keep changes, drop repeats | "X at booth C" ×40 ticks → "X at booth C since −35 s" |
| **2. Expire** | Remove items past their TTL, per modality | A gesture seen 90 s ago and not repeated is gone; an `UNKNOWN` sector is kept while it is still unknown |
| **3. Collapse to cards** | Template-based episode cards when an interaction ends | 14 turns with Visitor X → one card: "X asked about the Booth C demo; gave directions; X said thanks; nothing open" |
| **4. Rank and select** | Keep the top-k items by the §4.3 score | 9 nearby tracks → the 4 most relevant plus one line: "5 others, no interaction" |
| **5. Model summary (optional)** | Only when an episode is too complex for a template card. Runs after the episode closes, during idle time, on the NPC model. Output is validated and keeps links to its source events | A long negotiation → a 3-line card with source event IDs |
| **6. Section cut** | Drop sections in the §4.1 cut order | Episodic cards → 0 under heavy load |

**Compact formats help before any of this:** short IDs, relative times (`−12s`), rounded numbers, enums instead of prose, one field per line, and no empty fields, **except** that missing data stays visible as an explicit marker (`audio: MISSING`), never silently dropped (D-11).

### 5.1 HORIZON is itself compression

L4–L8 turn a raw stream of observations into a small scene state: ranked targets, groups, held-open readings, unknowns, recent events. That is a large part of HORIZON's value, and it is measured. Arm `H0` (flat evidence) will usually send longer prompts than full HORIZON. Token counts per section are logged for every call so A/B reports show the difference instead of hiding it (Blueprint §9.6).

## 6. Preventing rot

| Rule | Why |
|---|---|
| **Everything has an age and expiry.** Items show `observed_at`; expired items are removed or shown as expired | Stops acting on stale facts |
| **Corrections supersede.** A correction marks the old item `contradicted` and is itself stored as high-importance. Only the correction is assembled | Stops repeating a corrected mistake |
| **Inferred never becomes observed.** Prism hypotheses carry their read label and expire; compaction cannot upgrade them (Blueprint §11 rule 5) | Stops guesses hardening into "facts" |
| **No self-feeding.** The agent's own past `reason_summary` text is never fed back as evidence. Only its actions, utterances and observed outcomes are | Stops echo-chamber drift |
| **Untrusted text stays labeled.** Signs, overheard speech and other agents' messages keep their source label through every compaction step (D-09) | Stops injected text becoming "memory" |
| **Scopes survive compression.** A card inherits the strictest scope of its sources; items from different scopes are never merged into one card; overheard content is never stored as told (D-12) | Stops summaries leaking private content |
| **Commitments never compress away.** They live in their own store and section (D-13) | Stops broken promises after long runs |
| **Fresh assembly every call.** No transcript to rot | Each decision starts clean |
| **Identity re-anchored every call.** Persona and guardrails are always section 1–2, never summarized | Stops character drift |

## 7. Adaptive budgets

Budgets are not fixed for a whole run. They adjust to the situation and the load:

- **By CDC mode (D-09):** `IDLE` → minimal; `STANDARD` → default; `FOCUSED` → more conversation turns for the focal partner, fewer peripheral tracks; `ALERT_CONTEXT` → more observation budget, fewer episodic cards; `EMERGENCY_HOST_ONLY` → smallest possible context.
- **By load (back off fast, recover slowly):** when the scheduler sees queue wait or prefill time over target, C2 budgets drop sharply (about half) for a while, then grow back in small steps once things are smooth. This mirrors the AIMD rule in the Situational Protocols. **Focal budgets are not reduced by load during controlled trials**, so the A/B comparison stays fair; overload shows up as recorded queue time instead.
- **By engagement level:** promotion to C2 brings the larger budget; demotion to C1 writes an episode card and shrinks the budget (see the lifecycle in INFERENCE_STRATEGY §3.2).

Every adjustment is logged with the reason.

## 8. Retention over long runs

| Store | Retention |
|---|---|
| Trail buffer | Rolling window only |
| Working Set | Replaced continuously |
| Episodic cards | Capped per agent (e.g. 50); lowest score evicted, with forgetting-kernel decay |
| Public anonymous tracks | Expire shortly after leaving perception unless tied to an open interaction (Atlas L8 privacy baseline) |
| Relational facts | Kept while in scope; removed on "forget that" or run end; never turned into person labels (D-13) |
| Event journal | Full record on disk for replay and evaluation; **never** read directly into a prompt |

Memory is reset between runs unless a scenario explicitly tests carry-over, which is then declared in the run manifest.

## 9. What the layer viewer shows

For the selected agent and any decision marker: the assembled context by section, with token counts; which items were cut and why; which compression steps ran; and the cache-hit portion. This makes "why did R forget that?" answerable by looking.

## 10. Tests and metrics

| Test / metric | Pass condition |
|---|---|
| **Soak test** | 2-hour sandbox run: prompt tokens and prefill time per decision stay flat (no upward trend) |
| **Budget cap** (Blueprint T18) | No assembled context exceeds its tier budget, ever |
| **Commitment retention** (S013) | Open commitments present in context after any amount of compaction |
| **Correction carry-over** | Correction at minute 10; at minute 50 the old belief is never used |
| **Stale use** | Actions based on expired observations are counted; target zero |
| **Scope leak** (T17, T24) | No private or overheard item appears in another agent's context or in a public utterance |
| **Never-cut sections** | Guardrails, identity, commitments, latest turn and the decision prompt are present in 100% of calls |
| **Cache hit rate** | Share of prompt tokens served from cache, per tier, tracked over time |
| **Compression fidelity** | Sample episode cards checked against their source events: no invented facts, scopes preserved |

## 11. Implementation plan

| Step | Gate | What |
|---|---|---|
| 1 | G0 | Memory item contract (fields in §3); context section contract with per-section token counts |
| 2 | G0 | Tests for scopes, expiry and no-leak against the headless test world |
| 3 | G3 | Context assembler with §4.1 order and budgets; boundary-only updates (§4.2); real tokenizer counts |
| 4 | G3 | Compression steps 1–4 (deterministic); episode cards from templates |
| 5 | G3 | Commitments & Refusals store and S013 test |
| 6 | G5 | Adaptive budgets by CDC mode and load (§7); viewer context panel (§9) |
| 7 | G6 | Optional model summaries (step 5) behind a flag; 2-hour soak test; correction carry-over test |
