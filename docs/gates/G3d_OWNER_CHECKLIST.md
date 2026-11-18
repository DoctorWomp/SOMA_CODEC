# G3d — What to do on your PC: rendered SB-04, pulse on/off, live bake-off rerun

About 1.5–2 hours, mostly waiting for runs. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` set), llama-server b12443 installed, F3 and N3 registered. What changed and why: [D-62 to D-70](../DECISIONS.md); the G3d section of [G3_PLAN.md](G3_PLAN.md).

**Nothing downloads.** Both model servers listen on `127.0.0.1` only. Close games and other GPU programs first, and leave the PC alone during the rendered runs (frame times are measured).

**What to paste back is only summaries:** the lines a command prints, `results\bakeoff\results.md`, and `soak_summary.json`. **Never paste or upload a run folder** (`runs\…`, `results\bakeoff\run_*`): those hold raw prompts and agent memory. Both folders are git-ignored.

## 1. Get the branch and check (≈ 10 minutes)

1. GitHub Desktop → **Fetch origin** → **Current branch** → `claude/keen-turing-llek1j`.
2. In PowerShell:
   ```powershell
   cd G:\SOMA_CODEC
   ```
   ```powershell
   uv sync --locked
   ```
   ```powershell
   uv run python tools/check.py
   ```
   - [ ] Five **PASS** lines and `All checks passed.`
   - [ ] The Godot step prints `22 scenario runs, N at a time, in … s`: they now run side by side (D-68). Note the Godot step's time in the summary (it was about 11 minutes on your PC at G3c-2).

## 2. Rendered SB-04 with F3 + N3: frame times and peak VRAM (≈ 5 minutes)

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --mode live --watch --resolution 1920x1080 --render-preset v0
```

A window opens and SB-04 plays in real time (90 s) with Robot R on F3 and the visitors on N3 (Option C).

- [ ] The summary prints a `frames (1920x1080, preset v0): p50 … / p95 … / p99 … ms` line. The initial target is **p95 ≤ 16.7 ms at 60 FPS**: report what it says, met or not; nothing is tuned to it.
- [ ] A `peak VRAM during the run: … MiB` line (sampled every second while the run is going, Godot and both servers together).
- [ ] **FN-1 by eye:** Robot R never walks away from someone it is talking with unless it says goodbye **to them** first, and it only leaves once the line has been said.
- [ ] **FN-2 by eye:** when Visitor Y approaches or speaks, Robot R glances at Y and then back at X.

**Paste back:** the summary lines (from `Run folder:` to `OK`), and anything that looked wrong.

## 3. Live bake-off rerun with the render tax (≈ 35 minutes)

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --resolution 1920x1080 --render-preset v0
```

All five modes, three real-time SB-04 runs each: LIVE, LIVE_COLD, LIVE_LOAD, STEPPED and the new **LIVE_RENDERED** (LIVE with the window open). Every run uses the G3d fixes (one deadline per decision, the relevance check before sending, memory that follows what the world accepted).

- [ ] **Robot R actions accepted / stale:** stale 0.
- [ ] **Robot R p50 / p95** and **NPC p50**, as at G3c-2: compare with your G3c-2 numbers if you have them.
- [ ] The new table **Pulse, render, frame pacing and peak VRAM:** peak VRAM per mode; frame p50/p95/p99 and spikes for LIVE_RENDERED.
- [ ] The new **Render tax** table: Robot R p50/p95 and NPC calls per minute, headless LIVE vs LIVE_RENDERED, with the change in percent. The proposed limit (ART_DIRECTION §7) is that rendering costs at most 10% of focal throughput: report it either way.

**Paste back:** `results\bakeoff\results.md`.

## 4. Pulse on vs off (≈ 15 minutes)

Same scene, seed, models and preset; only the pulse changes.

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE --no-pulse
```
- [ ] `results.md` now has a **Pulse on vs off** table (the "on" row is LIVE from step 3).

Then the long wait, where the pulse matters most:

```powershell
uv run python tools/run_scenario.py SB06_LONG_WAIT --model llama --mode live --out runs\g3d_sb06_pulse_on
```
```powershell
uv run python tools/run_scenario.py SB06_LONG_WAIT --model llama --mode live --no-pulse --out runs\g3d_sb06_pulse_off
```
```powershell
uv run python tools/compare_runs.py runs\g3d_sb06_pulse_on runs\g3d_sb06_pulse_off
```
- [ ] The table shows, per run: offered vs accepted actions, response latency, timeouts and fallbacks, model calls, glances, zombie events (pulse on), FN-1 departures, and frame pacing (`not recorded` for headless runs).

**Paste back:** `results\bakeoff\results.md` (again) and the `compare_runs.py` table.

## 5. Optional: the soak (≈ 5 minutes)

```powershell
uv run python tools/soak.py
```
21 simulated minutes of SB-09 with the fake model (the cloud ran the same; D-70). Expected: prompt tokens and log growth bounded, and **memory reported as growing** (raw heard speech has no expiry yet; D-70 asks you how to bound it).

**Paste back:** the printed lines (from `Soak SB09_SOAK` to `OK`/`FAIL`), or `soak_summary.json` from the run folder. Not the folder itself.

## 6. Decisions

- **D-60 and D-61** stay PROPOSED until you approve them after this run (the 6.5 s stale window, D-63, is now re-derived and holds).
- **D-62 to D-70** are new and PROPOSED. One needs a choice from you: **D-70, how to bound memory** (expire raw heard speech once its conversation is summarized, after a retention window, and/or cap it per agent).

## If something fails

- **`option B` with a fallback reason:** paste the `VRAM` line of `inference_events.jsonl` from the run folder.
- **No frames line after a `--watch` run:** paste the last 30 lines of `godot.log` from the run folder.
- **`peak VRAM … (nvidia-smi not found)`:** nvidia-smi is not on PATH in that PowerShell; it normally is with the NVIDIA driver installed.
- **The run prints `FAIL`:** paste the summary lines and the last 30 lines of `godot.log`.
