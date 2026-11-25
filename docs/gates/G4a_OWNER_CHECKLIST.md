# G4a owner checklist: permissions, Spectator and the layer viewer v1

**Gate:** G4a ([G4_PLAN.md](G4_PLAN.md)). **Decisions:** D-90 to D-96 (PROPOSED); your 2026-11-23 approval of D-62 and D-72 to D-74 is recorded in DECISIONS.md.
**What is new:** every request goes through the world dispatcher with its seat's permissions (D-90); bodies and controllers are separate (D-91); watching never writes the journal (D-92); a viewer feed per observer, live and on replay (D-93); the layer viewer v1 (D-94); follow and POV cameras and a Sensor view drawn from packets only (D-95). Agents behave as before: every scenario's journal is the same as on main (G4_PLAN "G4a results").

What the cloud showed (software rendering, fake model; D-96 and G4_PLAN "G4a results"): no journal changed in any scenario (three runs each); writing the live feed costs nothing measurable; the open viewer cost llvmpipe about 1–2 ms of frame p50 and 7 ms of p95, and 5.5 MiB of Godot's video memory. Screenshots: [live Spectator with the viewer](G4a_screenshots/live_spectator_viewer.png), [a decision with a drop before sending](G4a_screenshots/replay_decision_drop.png), [EVALUATOR TRUTH](G4a_screenshots/replay_evaluator_truth.png).

Everything below is on your PC. Close what holds GPU memory first (OWNER_SETUP_WINDOWS.md "GPU memory"): the cost numbers in §4 compare runs, so keep the other programs the same in all of them.

## 1. Update

```powershell
cd G:\SOMA_CODEC
```

```powershell
git fetch origin && git checkout claude/youthful-volta-513zpl && git pull
```

```powershell
uv sync --locked
```

```powershell
uv run python tools/check.py
```

Expected: everything passes, with the Godot step's new lines: `test_dispatcher_permissions_without_ui`, `test_spectator_cameras_t06`, `test_layer_viewer_from_fixture` and the others PASS; the scenario step says `viewer: live feed ... = rebuilt, journal unchanged; replay observer=robot_r seat=SPECTATOR ... | observer=robot_r seat=EVALUATOR ... evaluator_panel=present`.

## 2. Watch SB-04 (the first end-to-end target as far as G4a reaches)

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model llama --watch --viewer open
```

(F3 + N3, LIVE, about 90 s.) While it runs:

- [ ] The status panel says `Seat: SPECTATOR`. `C` cycles free → orbit → follow → POV; `[` `]` change the avatar. Follow stays behind the avatar and never inside a wall; POV looks where the robot's head looks (watch it glance with the head while walking).
- [ ] Select Robot R, press **F2**: the Sensor view's cone turns with the head; each person is labelled with Robot R's own track id and its handle, e.g. `anon_… (P1) · seen`; heard speech shows as an arrow from where it came, with the words.
- [ ] The layer viewer (F3 toggles it) says `seen by robot_r` everywhere. Lanes fill as the run goes; L0–L8 say `not built (G5)`; every Bypass button is greyed out and its tooltip says why. S and M only hide or show lanes.
- [ ] Click a pin (▼) or press N / P: the right-hand panel explains the decision: triggers, context sections, activity and wake conditions, the model call's queue / prefill / generation / tokens / outcome, and each action with what the host did. **Look for a request "DROPPED before sending: …"**: your G3h run dropped 28 of Robot R's requests, so a LIVE run with F3 + N3 should show some (reason TARGET_NOT_PERCEIVED, SOMEONE_ELSE_ADDRESSING or DECISION_DEADLINE_PASSED).
- [ ] No panel shows a private goal, a scenario label, prompt text, or a real id (`visitor_x`) for a track. Pressing F4 does nothing in this seat.

After the run, replay it and scrub:

```powershell
uv run python tools/view_run.py latest
```

- [ ] `,` `.` step through the run (Shift: 10 s); `[` `]` switch to visitor_y's view: its tracks are its own ids, never merged with Robot R's.

## 3. The Evaluator seat

```powershell
uv run python tools/view_run.py latest --seat evaluator
```

- [ ] A separate amber panel titled **EVALUATOR TRUTH** shows which avatar each of the observer's tracks was, the scenario labels, every private goal, and the selected decision's prompt and raw answer (select a pin to see it). The Spectator run of §2 never showed it.
- [ ] `runs\<run>\operator_replay.jsonl` lists the Evaluator's reads of evaluator truth; the journal has no such lines.

## 4. The viewer's cost (ART_DIRECTION §3.1 and §7; D-69, D-87)

Three rendered SB-04 runs, F3 + N3, LIVE, 1920×1080, preset v0, the same other programs open: viewer off (no live feed), closed (the feed written, panel hidden), open (panel drawn all run).

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model llama --watch --resolution 1920x1080 --render-preset v0 --viewer off --out runs\g4a_cost_off
```

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model llama --watch --resolution 1920x1080 --render-preset v0 --viewer closed --out runs\g4a_cost_closed
```

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model llama --watch --resolution 1920x1080 --render-preset v0 --viewer open --out runs\g4a_cost_open
```

```powershell
uv run python tools/compare_runs.py runs\g4a_cost_off runs\g4a_cost_closed runs\g4a_cost_open
```

Please send the table (it has frame p50 / p95 / p99, spikes, Godot's video memory, peak VRAM, the viewer's open time and redraws, Robot R's model call p50 / p95, fallbacks, event-loop lag) and each run's `vram_hygiene` line from `summary.json`:

| Measure | Viewer off | Closed | Open | Limit |
|---|---|---|---|---|
| Frame p95 / p99 ms | | | | p95 ≤ 16.7 ms (D-69) |
| Godot video memory peak MiB | | | | rendering ≤ ~1.5 GB (ART_DIRECTION §3.1) |
| Peak VRAM MiB; free after servers | | | | 2 GB reserve (D-87) |
| Robot R p50 / p95 ms | | | | p95 < 4 s (D-87); open vs off ≤ +10% (render tax) |
| Robot R fallback decisions | | | | ≤ 10% with N3 (D-87) |

## 5. A live bake-off row with the rendered client open (F3 + N3, LIVE)

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_RENDERED --resolution 1920x1080 --render-preset v0 --repeat 1
```

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE_RENDERED --viewer open --resolution 1920x1080 --render-preset v0 --repeat 1
```

- [ ] `results\bakeoff\results.md`'s render-tax table now has two rendered rows for F3 + N3: `1920x1080 v0` and `1920x1080 v0 · viewer open`, each against headless LIVE. The target table says whether Robot R still meets D-87 with the viewer open.
- [ ] These numbers also decide D-114 (speculative decoding) later: note the free VRAM with the viewer open.
- Note: since G4a a LIVE_RENDERED run writes the live viewer feed (`--viewer closed`, the default when watched); `--viewer off` reproduces G3's rendered runs exactly.

## 6. What to send back

The `check.py` summary line, your notes on §2–§3, the table of §4, the two results.md rows of §5. If the viewer pushes Robot R over D-87's target, say so: the viewer can stay closed during measured runs, and its redraw rate can drop.
