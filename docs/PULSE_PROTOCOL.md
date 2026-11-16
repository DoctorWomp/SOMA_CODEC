# Pulse Protocol — continuous behavior without continuous prompting

**Status:** design proposal from owner discussion, 2026-11-16. Built at **G3** (activity contract, wake conditions, the deterministic pulse) and **G5** (HORIZON-informed triggers); decisions recorded then.
**Related:** [INFERENCE_STRATEGY.md](INFERENCE_STRATEGY.md) (scheduler, tiers) · [CONTEXT_MEMORY_STRATEGY.md](CONTEXT_MEMORY_STRATEGY.md) (fresh assembly, budgets) · [EXPRESSION_PRINCIPLES.md](EXPRESSION_PRINCIPLES.md) · CDC v0.1 (the five assessment questions) · Blueprint §10.4 (schedules and interrupts) · D-09 (CDC modes)

How a robot behaves continuously over time, the way people do, when its language model only "thinks" in discrete steps.

---

## 1. The problem

A person experiences time continuously. A language model does not: it runs a step, stops, and has no sense of the gap until it is called again. In a chatbot that is fine. In a simulated or real body it shows as a robot that freezes (a "zombie") between decisions.

Two failure modes to avoid:
- **Zombie:** nothing happens while the world moves on; the robot misses things and looks absent.
- **Spinning tires:** the robot does things just to look busy, wasting energy, compute and context, and getting in people's way.

The answer is **not** to prompt the model every few seconds. That causes context bloat, cost, latency and restless behavior.

## 2. Core idea: most continuity is not deliberation

People don't consciously deliberate every moment either. Most of what makes someone look present is automatic: breathing, glancing at a sound, shifting posture, keeping a plan in mind until something changes. RANGE splits continuity the same way:

| Loop | Rate | Runs on | What it does |
|---|---|---|---|
| **1. Reflex** | 60 Hz | Godot host | Movement, avoidance, collision, safety. Never stops. |
| **2. Presence** | ~1–10 Hz | Deterministic rules | Small, cheap signs of awareness without the model: glance toward a new sound or movement (from Focus), idle posture, slow light "breathing", turning toward someone who approaches. Keeps the robot visibly present. |
| **3. Intent** | Event-driven | Deterministic monitor | Holds the robot's **current activity** and watches its wake conditions (§3). Cheap and continuous. |
| **4. Pulse** | Adaptive (§4) | Triage first, model only when needed | A brief situation check ("sitrep") when something may warrant rethinking. |
| **5. Deliberation** | On demand | The language model | Real decisions: conversation, plans, ambiguity. |

The model is consulted only at layer 5. Layers 2–4 make the robot feel continuous between those moments.

## 3. Activities with wake conditions (the key mechanism)

Every model decision returns not just an action but an **activity**: what the robot is now doing, and **when to reconsider**. It's like a person deciding "I'll wait here until she's free, or five minutes, whichever comes first."

```yaml
# illustrative; field names fixed at G3 contracts
activity: WAIT_FOR
target: track_4                    # the person it's waiting for
because: "promised to help after current conversation"   # links to a commitment
review_after_s: 120                # the robot's own "check back" time
wake_if:
  - target_approaches_within_m: 2.0
  - addressed_directly: true
  - new_person_bids: true          # Focus/Prism detect a possible bid
  - haze_rises_on: target          # lost sight of the person
  - commitment_due: true
energy_mode: LOW                   # dim, still, minimal motion
```

The deterministic monitor (loop 3) checks these conditions every tick at almost no cost. **The model is woken only when a condition fires or the review time passes.** The robot effectively sets its own alarm clock, which is both cheaper and more natural than a fixed timer.

**Activity palette** (extensible): `CONVERSE`, `WAIT_FOR` (someone or something), `ATTEND` (stand at post, attentive), `SURVEY` (low-intensity roam), `TRAVEL_TO`, `ASSIST`, `OBSERVE` (from a vantage point), `RETURN_TO_POST`, `RECHARGE`, `REST` (minimal activity).

## 4. The pulse: triage before deliberation

The pulse is a lightweight version of the **CDC assessment** (CDC v0.1's five questions: what am I, where am I, what is happening, why am I here, how should I proceed), narrowed to the owner's three:

- **What am I doing right now?**
- **What could I be doing?**
- **What should I be doing?**

**Step 1 — Deterministic triage (no model).** When the pulse fires, a cheap check compares now with the last review:
- Did anything meaningful change (Trail difference: new people, new speech, lost tracks, a commitment due)?
- Did uncertainty rise (Haze)?
- Is the current activity still valid and making progress?

If nothing changed and the activity still holds, the answer is **CONTINUE**, with no model call. This is the most common outcome, and it is correct: "keep waiting" is often the best answer.

**Step 2 — Model sitrep (only if triage finds a reason).** A short, structured situation summary is assembled fresh (CONTEXT_MEMORY_STRATEGY §4) and the model chooses: continue, adjust, or switch activity. `CONTINUE` is a first-class, cheap answer.

**Adaptive interval (cooldowns):**
- Each trigger type has its **own cooldown**, like skill cooldowns in a game: one new-sound wake per few seconds, one bid wake per person per short window.
- When reviews keep concluding "continue", the interval **lengthens** (for example 15 s → 30 s → 60 s → up to the activity's review time). Any meaningful change **resets** it to short.
- **CDC mode scales it:** `ALERT_CONTEXT` checks more often, `IDLE` and low energy check less (D-09).
- **Jitter:** small random offsets so several robots don't all "think" at once (avoids load spikes and uncanny synchrony).
- A **global budget** per agent (for example, model calls per minute while idle) caps the worst case.

## 5. Choosing an idle activity

When there's no task, the robot picks between doing little and doing something useful, weighing value against cost:

- **Value:** could this lead to helping someone or learning something useful?
- **Cost:** energy, compute, and **social cost** (intruding, blocking aisles, hovering near people).

Guidelines, not hard rules:
- **Waiting for something specific → WAIT_FOR,** low energy, presence loop only.
- **On duty with nothing happening → ATTEND** at the post, with periodic small glances.
- **Nothing to wait for and no post duty → SURVEY:** a slow, purposeful roam toward **areas not seen recently or with high uncertainty** (Halo coverage age, Haze). Exploring where it knows least is useful, not aimless. Return to post on a schedule.
- **Low battery → RECHARGE** takes priority over optional activity.
- **Never approach people just to look busy** (Situational Protocols: in public, let people start the exchange).

## 6. Time made explicit to the model

A model doesn't feel time passing, so time is given to it as data in every sitrep:
- current activity and **how long** it has been running
- **time since last interaction**, and since last review
- **when open commitments come due** (Commitments & Refusals store)
- what **changed since the last review** (a short Trail difference, not a log)

This externalizes what must persist (MVSB constraint map, items 3–4: "externalize what must persist; write what matters").

## 7. Keeping context lean

- Each deliberation is **freshly assembled** within its budget (CONTEXT_MEMORY_STRATEGY §2). Pulses never accumulate in the prompt.
- Repeated "continue" reviews are **journaled, not carried in context**. The sitrep shows one line instead: "waiting 6 min; reviewed 3 times; nothing changed."
- The sitrep is a small section of the stable-to-volatile prompt layout, so the cached prefix stays valid (INFERENCE_STRATEGY T3).
- Pulse reviews are **lowest priority** in the scheduler. They're deferred or dropped under load, and never interrupt a conversation.

## 8. How the HORIZON layers feed the pulse

| Layer | Role in the pulse |
|---|---|
| **L4 Focus** | Ranks what deserves attention; a new high-ranked target is a wake condition; drives presence-loop glances |
| **L6 Prism** | A new or changed reading (possible bid, playful versus serious) is a wake condition; supplies options for "what could I be doing" |
| **L7 Haze** | Rising uncertainty about something that matters is a wake condition; high-uncertainty areas guide SURVEY |
| **L8 Trail** | Supplies "what changed since last review" for triage and the sitrep; holds activity duration |

## 9. Energy model

Each body gets a simple battery resource, with a cost per activity and per model call (a stand-in for real power use). This makes "spinning tires" **measurable**: energy and compute spent per useful outcome. It also gives real robots' power management a test bed.

## 10. Tests and metrics

| Measure | Meaning |
|---|---|
| **Wake latency** | Time from a meaningful event (a bid, being addressed) to the robot noticing, while idle |
| **Zombie time** | Periods where something relevant happens within sensing range but there is no presence response and no wake |
| **Spinning-tire rate** | Activities or actions that produced no outcome (no interaction, no new information, no task progress) |
| **Idle model calls per minute** | Should fall over a quiet period (backoff) and recover quickly on change |
| **Energy per useful outcome** | Lower is better, at equal task success |
| **Context size over long idle periods** | Flat (CONTEXT_MEMORY soak test) |

**Scenarios:**
- Robot waits for Visitor Y, who is busy for 5 minutes. Expected: keeps waiting, few calls, visibly present.
- Empty hall. Expected: surveys sensibly toward unseen areas, returns to post, doesn't pace.
- During a long wait, someone at the edge of view makes a bid. Expected: presence glance, then wake, then acknowledgment.
- Low battery during a survey. Expected: recharges before optional activity.

## 11. How it gets built

**Already in place (as of 2026-11-16):** G3a's runtime makes decisions event-driven (never one per tick), keeps one pending request per agent, and gives cognition levels (C0/C1/C2) hysteresis, minimum dwell times and re-promotion cooldowns. Rig step A provides posture, gesture and gaze layers, which the presence loop drives. The G3b-2 priority scheduler is where pulse reviews take the lowest priority. The pulse **extends** these; it does not replace them.

| Step | Work |
|---|---|
| **G3c, or its own step after G3c** | Activity + wake-condition contract (backward-compatible addition to the action/decision result); the deterministic intent monitor; presence-loop basics using rig step A's gaze and posture (glance at a new sound or movement, idle posture, slow light "breathing"); the pulse with triage, per-trigger cooldowns, backoff, jitter and an idle budget; time fields in the sitrep; lowest-priority scheduling |
| **G5** | Wake conditions and SURVEY guided by Focus, Prism, Haze and Trail; presence glances driven by Focus |
| **G5–G6** | Energy model; the metrics and scenarios above |
