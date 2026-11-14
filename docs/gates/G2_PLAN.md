# G2 — Senses and communication

**Status:** G2a BUILT, IN REVIEW (draft PR) · G2b PLANNED (next session, after G2a is reviewed) · owner checks: [G2a_OWNER_CHECKLIST.md](G2a_OWNER_CHECKLIST.md)
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

## G2b outline (next session)

COMMS router (Godot) producing `comms_event` records and per-recipient observations for all four channels; group membership by `CREATE_GROUP` / `INVITE_GROUP` / `ACCEPT_GROUP` / `DECLINE_GROUP` / `LEAVE_GROUP`; PA authorization from body capability `can_use_pa` and the scenario; the disclosure gate in Python with the earshot rule and `WITHHOLD` that never hints; the WebSocket link (127.0.0.1 only, session token at connection, size limits, heartbeat) with Python receiving observations and sending `agent.action_request`s that Godot validates (`CAPABILITY_DENIED`, `GROUP_NOT_MEMBER`, `PA_UNAUTHORIZED`, …); tests T13–T17 end to end.

## Out of scope for G2

Any LLM (G3), HORIZON layers (G5), Director and Participant controls (G4), noise/dropout realism beyond the proxies here (sensor realism is a dial, D-16), speech audio.
