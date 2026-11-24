# G4 — Controls: Spectator, Director, Participant, layer viewer v1

**Status:** G4a in progress (this branch, draft PR). G4b and G4c planned.
**Scope:** [RANGE_V0_SCOPE.md](../RANGE_V0_SCOPE.md) §2.4 (layer viewer) and §4 (G4 row) · [INTERACTION_MODES.md](../INTERACTION_MODES.md) §2, §4–§7, §10 · [HORIZON_OPERATIONAL_ARCHITECTURE.md](../HORIZON_OPERATIONAL_ARCHITECTURE.md) (per-observer labels, D-62) · [ART_DIRECTION.md](../ART_DIRECTION.md) §3.1, §7, §8 · Blueprint §7 (modes), §18 (T06–T12), §20 (G4 gate: *T06–T12 pass via real controls*) · [DECISIONS.md](../DECISIONS.md) D-03, D-12, D-13, D-25, D-51, D-62, D-63, D-69, D-72 to D-74, D-85, D-87, D-110, D-111

## Goal

A person can watch, steer and join the simulation **without changing the simulation underneath**. G3 is complete; G4 adds seats, views and controls. The world stays the only authority: every request carries its requester's role and the world dispatcher checks it (INTERACTION_MODES §2.2).

## Split: G4a, G4b, G4c

| Part | INTERACTION_MODES §10 | Contents | Proof |
|---|---|---|---|
| **G4a — Permissions, Spectator, layer viewer v1** (this branch) | Steps 1–3 | Roles and the permission check in the world dispatcher; body + controller split; Spectator cameras (free, orbit, follow, POV) and avatar cycling; World and Sensor views; the Evaluator truth panel (Evaluator seat only); layer viewer v1 (2D, per observer, from logged run data, live and on replays) with lanes, Solo/Mute, Bypass shown disabled, timeline and scrub, decision markers, capability cards (scope §2.4 items 1–4 and 8); its cost measured | Permission tests without UI; T06; no view reaches an agent; no journal changes; the first end-to-end target as far as G4a reaches |
| **G4b — Director** | Step 4 | Directive edit, prop placement, event trigger; intervention journal (`director.intervention`, contract exists); recipes; Bypass mid-run as a logged intervention once G5 layers exist | T07, T08, T09 |
| **G4c — Participant** | Steps 5–6 | `HUMAN_INPUT` controller, first/third person, typed chat, gestures; P1/P2 spawns, then P3 reveal, P4 possession, P5 tape capture | T10, T11, T12; repair latency measured |

Step 7 (microphone push-to-talk) is a later, opt-in milestone.

## G4a design

### 1. Seats, roles and the world dispatcher (D-90, D-91)

- **Principals.** Four **seats** a person can take: `SPECTATOR`, `DIRECTOR`, `PARTICIPANT`, `EVALUATOR`. Two **internal** principals: `AGENT` (the sidecar session that controls avatars) and `HOST` (the scenario's event tape, D-48).
- **The table is data:** `configs/permissions.yaml` (contract `permissions`), exported to `godot_app/data/permissions/` like every config Godot reads (D-30). One capability per kind of request: act in the world, edit a directive, change the world, trigger an event, possess, bypass a layer, each camera, each view, pause. A grant names a scope: `ANY`, `CONTROLLED` (the agent session's linked avatars whose controller it runs), `OWN_AVATAR` (a participant's own body). A capability can be `built: false` with the gate that builds it: the dispatcher answers `NOT_BUILT`, never pretends.
- **The Evaluator is its own seat.** The owner's G4a instruction: evaluator truth is for the Evaluator role only, never Spectator or Participant (INTERACTION_MODES §2.2 gave it to Spectator; D-90 amends that). Director is a toggle on top of Spectator and sees what Spectator sees.
- **Godot's `WorldDispatcher`** (a child of `RangeWorld`) is the one door: the link's `agent.action_request`s (principal `AGENT`), the event tape (`HOST`), and every seat request (camera, view, pause, and later Director and Participant requests). Allowed agent and host requests go to the unchanged action gate, so **journals do not change**. Seat requests and refusals go to an **operator log** (`operator.jsonl` in the run folder), never the journal: watching is not part of the world's record (D-92).
- **Body + controller split (D-91).** Every avatar has a `controller` (`SCRIPTED`, `LLM_AGENT`, `HUMAN_INPUT`, `REPLAY_TAPE`, from the scenario's cast). Swapping it changes only who may drive the body: the agent session drives `SCRIPTED` and `LLM_AGENT` avatars it linked; a participant only the `HUMAN_INPUT` avatar bound to its seat. Body, senses, COMMS and the gate are untouched.
- **Python mirror** (`range_service/viewer/permissions.py`) reads the same file: the viewer feed is filtered with it, and tests compare the Python and Godot answers for every principal × capability × scope.

### 2. Spectator (T06)

- Cameras: **free**, **orbit** and **follow** (behind the selected avatar, `SpringArm3D` so it does not clip walls), and the avatar's **POV** (its sensor point, facing its head, D-72). `[` `]` cycle avatars; `C` cycles camera modes. A participant (G4c) may use only its own avatar's follow and POV.
- **World view:** the scene and the status panel. **Sensor view** (F2): what the selected observer perceived, **from its observation packets only**: the sight cone from the packet's own pose (body yaw plus head yaw), each track by **its own id** (with its D-111 handle beside it when the observer has one), heard speech with its bearing (relative to the body, as the packet says). Nothing from world truth.

### 3. The viewer feed (D-93)

One record format, built by one Python builder (`range_service/viewer/feed.py`), whether the run is live or finished:

- **Sources** (what the sidecar saw): observation packets, the requests it sent and the world's results, decision records, the pulse log, `delivery.jsonl` drops and holds (D-63, D-66), each decision's handle map (D-111).
- **Live:** in a watched run the sidecar appends records to `RUN/viewer/observer_feed.jsonl` as they happen, and Godot's viewer reads the file's new lines. No new link message, so the agent link's traffic and buffers are untouched. **Replay:** at the end of every run the runner rebuilds the feed from the run's logs (also for old run folders: `tools/view_run.py RUN`). The live file and the rebuilt one are compared (`summary.viewer.live_matches_replay`).
- **Two audiences, two files.** `observer_feed.jsonl` (audience `OBSERVER`): per observer, only what that observer's own packets, decisions and requests hold: anonymous track ids, handles, timings, outcomes, reason codes. `evaluator_truth.jsonl` (audience `EVALUATOR`): which avatar each track was (written by Godot at run end, `truth_tracks.json`), scenario labels (`evaluator_only`, `measure`), private goals, assembled prompt text and raw answers. Godot reads the evaluator file only for the Evaluator seat; agents never see either file.
- **reason_summary** is shown only when present, labelled as the model's own words; LEAN (D-85, the default) has none. An NPC's prompt holds its own private goal (D-51), so an NPC's own words go to the evaluator file only.
- Contract `viewer_record` (examples, valid and invalid).

### 4. Layer viewer v1 (scope §2.4 items 1–4 and 8)

A 2D panel in the Godot client (F3), drawn with `_draw` (no textures), redrawn only when its data or the playhead changes:

- **Per observer (D-62):** every panel says whose view it is ("seen by robot_r"); tracks of different observers are never merged.
- **Top-down view:** the map's walls, the observer's own pose, its head-anchored sight cone, its tracks at their estimated positions with id and handle, heard speech as bearings.
- **Lanes** for what exists today: sight, hearing, tracks, head and gaze, pulse (activity, wake conditions, events), model calls (queue, prefill, generation, tokens, outcome including salvaged), actions (sent, accepted, refused with reason, dropped before sending with its reason), Beacon and ambient display. **HORIZON L0–L8 lanes are present and empty, labelled "not built (G5)".**
- **Solo / Mute** (view only) and **Bypass** look different: Bypass is a disabled control with its reason ("removes the layer from the avatar's perception; no layer exists until G5").
- **Timeline and scrub** over the run; live it follows the newest data until scrubbed.
- **Decision markers:** a pin per decision; selecting one shows why from evidence: triggers, context sections and sizes, the activity and wake conditions (and an activity dropped, D-110), model-call timing and outcome, each action sent and what the host did with it, drops before sending and their reasons. reason_summary only when present.
- **Capability card** per avatar (the run manifest's, plus the body's sensing and movement line).
- **Evaluator truth panel:** separate, labelled `EVALUATOR TRUTH`, created only for the Evaluator seat; real ids of the observer's tracks, scenario labels, private goals, the selected decision's prompt and answer.

### 5. Cost (ART_DIRECTION §3.1, §7; D-69, D-87)

Rendered SB-04 with the viewer closed and open: frame p50/p95/p99, spikes, Godot's video memory, peak VRAM and `vram_hygiene` (owner's PC), Robot R p50/p95 and fallbacks. `run_scenario.py --viewer off|closed|open`, `bakeoff.py live --modes LIVE_RENDERED --viewer open`. Reported against the render tax (≤ 10% of focal throughput) and D-87's live target; these numbers also inform D-114 later.

### Not in G4a

Director and Participant controls (G4b, G4c; their capabilities answer `NOT_BUILT`), HORIZON layers and Bypass (G5), routing view, automation lanes, A/B split (scope §2.4 items 5–7), the 3D Halo view.

## Tests (G4a)

- **Python:** the permission table (every principal × capability; agents never get a view; only the Evaluator gets evaluator truth); the feed (observer records carry no real id of another avatar, no private goal, label or prompt text, never another observer's tracks; handles beside track ids; drops before sending with reasons; salvaged and dropped activities; reason_summary rules); live == replay; the canary run's observer feed holds no marker while the evaluator file holds them; contracts.
- **Godot (headless):** dispatcher refusals for every seat (no UI); the link and tape routed through it with the same results; controller swap; T06 cameras; the sensor view drawn from packet pose; the layer viewer from a fixture feed (lanes, L0–L8 not built, Bypass disabled, Solo/Mute view only, scrub, decision panel with drop reasons, no evaluator panel for Spectator, evaluator panel for Evaluator); the Python/Godot permission matrices agree.
- **End to end (`tools/godot_check.py`):** SB-04 with the fake model and the live feed on writes the same journal as without; the Godot replay of that run scrubs to every decision of Robot R (self-test) as Spectator and as Evaluator.
