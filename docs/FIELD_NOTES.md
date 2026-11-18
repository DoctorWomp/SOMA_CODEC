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
