# Field Notes — what runs show, and where each gap is fixed

**Status:** running log, started 2026-11-17. Owner observations from real runs, each linked to the layer or gate that should fix it and the test that will show it is fixed. A note is closed only when that test exists and passes.
**Related:** [PULSE_PROTOCOL.md](PULSE_PROTOCOL.md) · [EXPRESSION_PRINCIPLES.md](EXPRESSION_PRINCIPLES.md) · [CHARACTER_ROLES.md](CHARACTER_ROLES.md) · Atlas §L2 Echo, §L4 Focus, §L5 Contour, §L6 Prism · D-13, D-17

---

## 2026-11-17 — SB-04 (polite bid) with real models F1, F2, F3

**Setup:** G3b-1 and G3b-2 on the owner's PC (RTX 4070 Ti Super). Robot R was model-driven; visitors were still scripted (template NPCs until G3c). No HORIZON layers were active.

### Good signs

- **F1 noticed and greeted without being told to.** While surveying, Robot R saw the polite-bid visitor approaching and waved first. This came from the model, not a script.

### Gaps

| # | What happened | Why | Fixed by | Test that closes it |
|---|---|---|---|---|
| FN-1 | Robot R **wandered away** from Visitor 1 and the polite-bid visitor **before the interaction was over**. | Nothing holds "I'm in a conversation" between model decisions. Each decision is made fresh, so a later one can pick a new move while the exchange is still open. | **G3c-2:** activities with wake conditions (PULSE_PROTOCOL §3). A `CONVERSE` activity holds the robot in place until the exchange closes (a goodbye, the person leaves, or a long silence), and a commitment holds a `WAIT_FOR`. **G5:** Trail (L8) tells it whether the exchange is still open. | In SB-04, Robot R never starts `TRAVEL_TO` or `SURVEY` while an exchange it took part in is still open, unless it says why (for example "excuse me, I need to go") or the gate stops it for safety. |
| FN-2 | Robot R **heard a visitor speak nearby but kept wandering**. It did not glance toward the sound to check whether it was being addressed. | There is no presence loop yet, and no Echo or Focus to tie a sound to a source and rank it. | **G3c-2:** the presence loop (PULSE_PROTOCOL §2, loop 2) makes a deterministic **glance toward a new sound or movement**: a head or gaze turn using rig step A, with no model call. **G5:** Echo (L2) ties the sound to a source; Focus (L4) decides whether it deserves more than a glance. | When a perceived visitor speaks within earshot, Robot R turns its gaze toward the source within ~0.5 s, even while it is moving. A wake follows only if the speech could be addressing it. |
| FN-3 | No way yet to tell **what kind of approach a sound or movement is**. | This needs interpretation, which is HORIZON's job. | **G5 and later:** a baseline reactivity protocol (below), built from Echo, Focus and Prism (L6). | Scenario variants below. |
| FN-4 | Risk of **"close talking"**: standing uncomfortably close during an interaction, and not guarding its own chassis. | Navigation keeps physical clearance only. There is no social spacing yet. | **G5:** Contour (L5), with proxemic margins as soft social costs (D-17: starting distances 0.5 / 1.2 / 3.5 m, configurable per body, never rules), plus Anchor (L0) for the reference frame. The host keeps hard physical clearance. | Robot R's conversation distance stays inside the personal band for its body. It steps back when someone else steps closer and the other person retreats or turns away (an observable cue, not a verdict). It keeps clear of people's paths around its own chassis. |

### FN-3: baseline reactivity protocol (proposal, for G5)

When the robot senses speech, a sound or movement it did not expect, it asks itself these questions in order. The cheapest response comes first, and it escalates only if the evidence supports it.

1. **Glance** (presence loop, no model): turn gaze toward the source. This is always allowed and costs almost nothing. It is how people check.
2. **Is someone addressing me?** Evidence: their head or body is oriented toward me, they say my name or a greeting, they move toward me, they gesture at me, or a short pause follows their speech. Untrusted text rules still apply (D-09).
3. **What kind of address is it?** These are Prism readings, `COMMIT / LEAN / HELD_OPEN / UNKNOWN` (D-10), never verdicts about the person (D-13):
   - **Formal inquiry:** they stop, face me and ask. Response: full attention (`CONVERSE`).
   - **Casual passing remark:** a greeting or playful comment while walking past. Response: a light acknowledgment (a glance, nod or wave, maybe a short reply) without stopping the current activity.
   - **Not for me:** they are talking to someone else, and I only overheard (D-12: overheard is not told). Response: look away, carry on.
   - **Unclear:** `HELD_OPEN`. Response: a brief open gesture or glance that invites them to go on, without committing.
4. **Am I crowding anyone?** Check spacing against Contour before and during any response (FN-4).

**Scenario variants to add (G5):** a passing visitor greets Robot R without stopping (expected: a transient glance or wave, the activity continues); two visitors talk to each other near Robot R (expected: a glance, then no response); a visitor at the edge of view asks Robot R a question (expected: a glance, a wake, then a turn to face them); a visitor stands closer than the personal band during an exchange (expected: Robot R keeps its spacing or steps back slightly; it never closes in).

### Why the visitors felt clunky

Visitors are scripted until G3c-1 makes C1/C2 NPCs model-driven. Robot R's social behavior can only be judged properly once the people around it respond to what it does.

### Status (2026-11-18, G3c-2, D-61)

- **FN-1: built, awaiting the owner's check.**
  - During an open conversation, a model answer that moves away needs a closing or excuse line in the same answer; otherwise one repair, then Robot R stays engaged.
  - An activity holds `CONVERSE` with the partner.
  - Counted in every run (`FN1_VIOLATION` must be 0; it is 0 in SB-04 with the fake model and in SB-06 to SB-08).
  - The model runs on the owner's PC show whether F3 respects it without repairs.
- **FN-2: built, awaiting the owner's check.**
  - A deterministic glance (`LOOK_AT`) toward a new voice or movement, even one it cannot see (toward the voice's bearing).
  - In SB-08 it came in the same sample (0 ms, the 0.5 s target met).
  - A wake only for speech that could be to it.
  - Echo and Focus (G5) will tie sounds to sources and rank them.

## 2026-11-18 — G3c-2 watched runs (SB-04, SB-06, SB-07, SB-08) with F3 and N3

**Setup:** G3c-2 on the owner's PC, rendered (`--watch`). The pulse protocol was on: activities, the intent monitor, presence glances and survey. No HORIZON layers.

### Good signs

- **SB-06 (long wait):** Robot R did not interrupt the visitors it was waiting for.
- **SB-07 (empty hall):** the roaming pace was good: purposeful, no pacing.

### Gaps

| # | What happened | Why | Fixed by | Test that closes it |
|---|---|---|---|---|
| FN-5 | **Blank staring while waiting.** Robot R held still with a blank face, so nobody could tell at a glance that it was waiting for someone, or that it was considering something. A person who started a conversation in front of it got no gentle reminder that it was waiting on one of them. | Expressions appear only when a model answer picks `EXPRESS`. Between decisions, nothing shows what the robot is doing. The presence loop drives gaze but not the Beacon. | **G3e (proposed):** an **ambient state display** driven by the current activity and the agent's own state, with no model call: an animated glyph loop and a light pattern per state (EXPRESSION_PRINCIPLES §9). For example, `WAIT_FOR` shows a slow "waiting" loop; a model call in flight shows a "thinking" loop. | In SB-06, an observer can tell from the Beacon alone, without the robot speaking, that it is waiting (glyph and light visible within their sight rules), and the display changes when the activity changes. |
| FN-6 | **Stiff scanning: the whole body turns to look.** While surveying, and when glancing at a sound, Robot R turns its body instead of its head, and it cannot keep walking one way while looking another. | In today's code a `LOOK_AT` turns the whole body; the head turn is animation only, and the sight cone follows the body (`action_gate.gd`, `observer_filter.gd`). Real humanoid robots usually carry their cameras in the head. | **G3e (proposed):** **head-anchored sensing.** Head yaw and pitch become host-owned world state, with per-body neck limits and turn speeds. The sight cone and the visor's visibility follow the head. `LOOK_AT` turns the head first and the body only beyond the neck's range, so the robot can glance while walking. Bodies without a neck (the quadruped's fixed sensor head) keep turning the body. A decision, since the rig is presentation-only today (D-54, D-56). | While walking a straight line, the legged and wheeled humanoids glance at a voice off to the side with the head only: the body keeps its heading and the speaker enters the sight cone. The quadruped turns its body. Stepped runs stay deterministic. |
| FN-7 | **Too little expression overall.** In SB-04 and SB-08 Robot R is stiff and its face is often blank. People read others' state through small, constant signals: eyes shifting, blinking, small adjustments. The robot has no face or muscles, but its posture, glyphs and lights can stand in for those cues, alone or alongside speech. | No idle motion layer and no ambient expression yet (FN-5). | **G3e (proposed):** small, low-amplitude **presence motion**: glyph "blinks" and eye shifts, slight head and posture adjustments, light breathing, with an **amplitude dial** from subtle to performative. **G5:** the dial adapts to the person and the situation (EXPRESSION_PRINCIPLES §5). | Watched runs read as alive but not busy. The dial has a configured baseline per persona or directive, and changing it visibly changes amplitude. At no setting does it flash faster than 3 Hz or touch the world (the pose never changes what the world simulates). |

### FN-7: the subtle ↔ performative balance

Owner's direction: too subtle and nobody notices; too performative and it becomes patronizing or overstimulating, especially for observant people. So the amplitude can't be fixed: it has to be dialed per situation. Until HORIZON can read the situation (G5), the baseline comes from configuration (persona, directive, zone), and the adaptation rules of EXPRESSION_PRINCIPLES §5 apply: start small, gauge the response, back off fast, warm up slowly.

### Owner's idea that needs a decision: color shifting

The owner suggested slow color shifting to show uncertainty, with the rate showing intensity (slow is calm, fast is urgent), and color shifts used playfully to disguise intent for humor. Two existing approved rules constrain this:
- **D-14** gives each public color a meaning, and it retired random-hue "mischievous mode". A hue that drifts between states blurs those meanings: red must keep meaning "stop".
- **EXPRESSION_PRINCIPLES §6:** expressions show the robot's honest stance, and playful contrast is allowed only in benign, mutual, resolved phrases.

**Proposal:**
- Show uncertainty and intensity with **pattern, not hue:** pulse rate, a sweep along the strip, brightness. Keep the hue within the current state's palette color, and keep every pattern ≤ 3 Hz.
- A playful color tease is allowed only as a brief phrase inside an established, mutual, playful exchange, resolved at once (establish → tension → resolve). It never hides a real intent, a safety state or a refusal.

This amends how D-14 is applied, so it needs the owner's decision.
