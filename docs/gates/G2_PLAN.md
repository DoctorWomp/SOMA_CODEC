# G2 — Senses and communication

**Status:** G2 COMPLETE. G2a merged 2026-11-14 · G2b merged 2026-11-15 (D-43 to D-46 approved) · owner checks: [G2b_OWNER_CHECKLIST.md](G2b_OWNER_CHECKLIST.md)
**Scope:** [RANGE_V0_SCOPE.md](../RANGE_V0_SCOPE.md) §4 (G2 row) · Blueprint §8 (RANGE COMMS), §12 (wire contracts), §20 (G2 gate), tests T13–T17 · [INTERACTION_MODES.md](../INTERACTION_MODES.md) §9 (who knows what) · [DECISIONS.md](../DECISIONS.md) D-04, D-05, D-07, D-12, D-29, D-33, D-36, D-37

## Goal

What each avatar can perceive, and how avatars communicate, enforced by the world, still with **no LLM** (scripted senders only). The Blueprint's G2 gate: *FOV/LOS/audibility router, all four channels, group ACL, event journal; T13–T16 and T17 pass; no cross-agent leaks.*

## Split: G2a and G2b

G2 is too large for one session, so it is split in two, each with its own draft PR:

| Part | Contents | Blueprint tests |
|---|---|---|
| **G2a — Senses, journal, avoidance** (this session) | Observer filter (sight and hearing), observation packets sampled at `tick_hz`, gestures and local speech as perceived events, the Godot event journal, shared local avoidance, the low divider | T13 (gestures out of view are not perceived), T14 (local speech: heard without sight, weakened or blocked by walls and distance) |
| **G2b — Channels, disclosure, link** (next session) | COMMS router with all four channels (GESTURE, LOCAL, GROUP with invite/accept, PA for authorized senders) and `comms_event` records; disclosure gate (PUBLIC / GROUP / ONE_TO_ONE / SEALED); loopback WebSocket link with session token; Python receives observations and sends action requests that Godot validates | T13–T14 again through the router, T15 (group ACL), T16 (PA privilege), T17 (memory isolation, no private information crossing) |

The cut follows the Blueprint's sequence (§8.3): G2a is the sensor adapter ("who could perceive this, and how well"); G2b is the router, the access rules and the link that sit on top of it.

## G2a deliverables

1. **Observer filter** (Godot, `scripts/senses/`):
   - **Sight.** From each observer's sensor mount height (D-36) to several points on each target: head, torso, left and right side, and the gesturing hand. Each point needs range, field of view and a clear line of sight. Walls, the platform, props and **other avatars** (crowds) block sight; a wall with `blocks_sight: false` does not.
   - **Result per target:** all points seen → `OBSERVED`; some → `DEGRADED` with reason `PARTLY_OCCLUDED` and the list of visible parts; none, but seen within the last 3 s → `OCCLUDED` (behind something) or `MISSING` (left the field of view or range), at its last known position with no quality. A target the observer has never seen is simply absent: an observation never reveals that someone hidden exists.
   - **Hearing.** Speech level falls with distance; walls take some off (more for sound-blocking walls than for partitions and dividers); the listener's zone noise floor masks it. Speech can be heard without seeing the speaker (then the source is `UNKNOWN_SOURCE`, with a direction but no position), and is weakened (`DEGRADED`) or lost through walls and distance.
   - **Gestures** an avatar performs (only ones its body allows, D-36) are perceived as `VISUAL_GESTURE` only by observers who can see the gesturing body part, within a legible range.
   - **Anonymous tracks** per observer and session; `source_entity_id` stays null (no introductions yet).
2. **Sampling:** observation packets follow `contracts/observation.schema.json`, are built every 60 / `tick_hz` physics ticks (10 Hz by default), and carry `based_on_tick_id` = the 60 Hz physics tick (D-33).
3. **Event journal** written by Godot in the `journal_entry` format (JSONL): run start and end, every observation packet delivered, gestures performed or refused, speech emitted. `tools/godot_check.py` validates the journals and packets Godot writes against the contracts with Python.
4. **Local avoidance:** every avatar steers around every other avatar through one shared avoidance map, even though paths are planned on per-size navigation maps (D-37).
5. **Low divider** (1.1 m, like a booth counter) in Sandbox Flats: a quadruped's 0.55 m sensors cannot see over it, a humanoid's can.
6. **Sense view** (F2, Blueprint §7.4): lines from the selected avatar's sensors to what it perceives, so the owner can watch the filter work; the panel lists what it sees and hears.
7. **Contract additions** (backward-compatible, version stays 1.0): optional `validity_reason` and `visible_parts` on observations; journal kinds for gestures and speech; optional `sample_hz` in the run-start record.
8. **Docs and decisions** for the sensor, acoustic, avoidance and journal choices.

## G2a acceptance tests

| Test | Proves |
|---|---|
| A gesture outside the field of view, out of legible range or behind a wall is not perceived; one in view is | T13 groundwork (gesture eligibility) |
| A gesture a body cannot perform is refused and never perceived | D-36 in the world |
| Local speech is heard behind the listener (no sight needed), weaker through a partition, not heard through an outer wall or beyond range | T14 groundwork (audibility) |
| Speech in a louder zone is masked sooner | Zone noise drives hearing (ART_DIRECTION §5) |
| The low divider hides a visitor from a quadruped but not from a humanoid standing at the same spot | Sensor height matters (D-36) |
| A visitor half hidden behind a partition's end is `DEGRADED` / `PARTLY_OCCLUDED` with only some parts visible; fully visible and fully hidden controls behave | Partial visibility |
| A target that walks behind a partition becomes `OCCLUDED` at its last known position, then disappears after 3 s; a never-seen hidden target is absent | No existence leak; missing ≠ zero |
| Another avatar standing in between blocks sight | Crowds occlude |
| Packets are sampled at `tick_hz` with `based_on_tick_id` on the 60 Hz tick; track ids are anonymous and per observer | D-33, Blueprint §12.1 |
| Every journal line and packet Godot writes validates against the contracts (checked in Python) | One contract on both sides (D-27) |
| A wheeled humanoid and a quadruped crossing head-on and at right angles both arrive, with no contact | Shared avoidance across size maps |
| The full demo still runs with no contacts and nobody stuck; two runs give the same journal | Regression, determinism |

## G2b deliverables

1. **COMMS router** (Godot, `scripts/comms/`), one entry point per channel, each producing a `comms_event` record (evaluator audience: it lists who received it) in the journal:
   - `GESTURE`: delivered to whoever can see the gesturing part during the gesture (G2a observer filter); a body can only use gestures it has (D-36).
   - `LOCAL`: speech, delivered to whoever can hear it at the next sample (G2a hearing).
   - `GROUP`: device messages. Membership by invite **and** accept; declined invitations do nothing; leaving stops delivery at once. Delivered to every current member except the sender, at any distance, and **never** to anyone else, even standing next to the sender. Group messages are not sounds.
   - `PA`: only senders authorized for it (body capability `can_use_pa`, or listed by the scenario as PA operators). Delivered through the map's PA coverage as `AUDIO_SPEECH` on channel `PA`, sourced at the PA speaker. Unauthorized: rejected with `PA_UNAUTHORIZED`, nobody hears it.
2. **Expression-ready gesture events.** A shared `expression` object in `common.schema.json` (gesture, visor/strip glyph, light state from the D-14 palette, light pattern, where it is shown) is used by `comms_event` and by a new observation kind `VISUAL_EXPRESSION`. G2b emits only gestures; G3 adds glyphs and light states (docs/EXPRESSION_PRINCIPLES.md) by filling the same fields, so no incompatible contract change is needed.
3. **Action gate** (Godot): validates every `agent.action_request` (schema, the session controls that agent, freshness, rate, capability, group membership, PA authorization, disclosure scope against who can actually hear) and answers with `action_result` and a reason code from Blueprint §12.3.
4. **Disclosure gate** (Python, `range_service/comms/disclosure.py`, D-12): `PUBLIC` / `GROUP` / `ONE_TO_ONE` / `SEALED`; the earshot rule (who could hear decides, and an unidentified or unseen listener counts as untrusted); overheard speech is never stored or retold; `WITHHOLD` never hints that something is withheld. Godot repeats the check on `SPEAK` with a disclosure scope (defence in depth).
5. **Loopback WebSocket link** (D-05): the Python sidecar listens on 127.0.0.1 only; Godot connects with the session token in the handshake (from an environment variable, never logged or put in an envelope); every message is a versioned envelope checked against the contracts on the Python side and by a small structural check on the Godot side; size limit, capped outgoing queue, heartbeat, automatic reconnect. Godot never waits for Python: the world keeps its 60 Hz tick whatever the link does.
6. **Scripted Python agents** (no LLM): each controlled avatar gets its observations only, keeps its own memory, and answers with action requests (for example: wave back and say hello when waved at).
7. `tools/run_link_demo.py`: starts the sidecar and opens the Godot demo connected to it, for the owner.

## G2b acceptance tests

| Test | Proves |
|---|---|
| A gesture's `comms_event` lists as received only those who could see it | T13 through the router |
| Speech's `comms_event` lists listeners in earshot, not those behind an outer wall or out of range | T14 through the router |
| A group message reaches a far member and never a non-member standing next to the sender; invite without accept, decline and leave all stop delivery; a non-member cannot post | T15 |
| A PA announcement from an unauthorized sender is rejected and heard by nobody; an authorized one reaches everyone in coverage | T16 |
| A secret told one-to-one stays in that agent's memory; other agents' observations and memories never contain it; no evaluator-only field or NPC private goal ever crosses the link | T17 |
| Disclosure gate: each scope against each audience; overheard is not stored or told; `WITHHOLD` text never hints | D-12 |
| A wrong or missing session token is refused; the sidecar binds 127.0.0.1 only; oversized and malformed messages are refused without a crash | D-05, Blueprint §12 |
| Invalid, stale, unauthorized, rate-limited and capability-denied action requests get the right reason code; a valid one executes | Action gate |
| End to end: Godot sends observations, a scripted Python agent waves back and speaks; the sidecar disconnects and is slow, and Godot keeps ticking smoothly and reconnects | The link works and fails safely |

## Out of scope for G2

Any LLM (G3), HORIZON layers (G5), Director and Participant controls (G4), noise/dropout realism beyond the proxies here (sensor realism is a dial, D-16), speech audio.
