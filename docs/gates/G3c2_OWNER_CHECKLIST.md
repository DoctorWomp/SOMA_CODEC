# G3c-2 — What to do on your PC: usable NPCs, real-time live runs, and the pulse

About 1.5–2 hours, mostly waiting for runs. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` set), llama-server b12443 installed, F3, N3, N1 and S1 registered. What was built and why: [D-60](../DECISIONS.md) (part A) and [D-61](../DECISIONS.md) (part B, the pulse).

**Nothing downloads.** Both model servers listen on `127.0.0.1` only. Close games and other GPU programs first.

**Two things changed how earlier numbers should be read:**
- Headless LIVE runs used to run about 15× faster than real time.
- The world refused every answer slower than 1 s as stale.

So the earlier LIVE tables (G3b and G3c-1) did not measure live behavior. Step 3 measures it again. The stale window is now 6.5 s, a host rule that needs your approval (D-60).

## 1. Get the branch and check

1. GitHub Desktop → **Fetch origin** → **Current branch** → `claude/g3c1-servers-npcs-345no5`.
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
   - [ ] Five **PASS** lines and `All checks passed.` Step 6 now also runs the pulse scenarios SB-06, SB-07 and SB-08 (about 10 minutes for that step).

## 2. NPC prompts: offline bake-off on the new set (≈ 30–45 minutes)

```powershell
uv run python tools/bakeoff.py offline --models N3 N1 S1 --kv q8_0
```

This uses `bakeoff\prompts_v3.jsonl`, where NPC prompts show argument formats and who is near, and answers can only name what the agent perceives. Your earlier v2 results move to `results_previous_set.json`.

- [ ] In the **NPC prompts** table, N3 reaches at least **90% final valid** (it was 40%).
- [ ] If any model is below that, open `results\bakeoff\results.json` and look at `invalid_answers` for a few failures.

**Paste back:** `results\bakeoff\results.md`, and 3–5 `invalid_answers` entries if there are failures.

## 3. Live bake-off, in real time (≈ 50 minutes)

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3
```

Each mode now runs SB-04 three times **in real time** (90 s each): LIVE, LIVE_COLD (no pre-warming and no snapshots), LIVE_LOAD (NPC server busy) and STEPPED.

- [ ] **Robot R actions accepted / stale:** stale should be 0 (before, every LIVE answer was stale).
- [ ] **Robot R calls:** around 8–15 per LIVE run (it was 1–3).
- [ ] **NPC p50 total / queue / prefill / gen** and **NPC time with Robot R busy:** these show where NPC time goes. NPC timeouts should now be rare. If not, the share column tells whether it is GPU sharing with Robot R.
- [ ] **Promotion warm / cold:** to-call / call / to-action. Cold now has samples (LIVE_COLD).
- [ ] **VRAM focal / NPC** filled in (your measured values are now kept in `models\vram.local.yaml` and used for the fit check next time).

**Paste back:** `results\bakeoff\results.md`.

## 4. Watch the pulse: FN-1 and FN-2 by eye (≈ 20 minutes)

These use the Demo policy (no model), so what you see is the pulse itself:

```powershell
uv run python tools/run_scenario.py SB06_LONG_WAIT --watch
```
- [ ] Robot R answers Y's "one moment" with "Of course, take your time. I'll be here.", then **waits without interrupting** Y and Z for about three minutes.
- [ ] While it waits it **looks present**: it glances toward whoever speaks, holds the glance a few seconds, never darts, and the Beacon breathes slowly.
- [ ] It helps Y as soon as Y turns back.

```powershell
uv run python tools/run_scenario.py SB08_PERIPHERAL_SPEAKER --watch
```
- [ ] When the two visitors behind Robot R start talking, it **glances toward the voice right away** (FN-2) but does not answer them.
- [ ] When one of them asks it a question, it glances, turns and answers.

```powershell
uv run python tools/run_scenario.py SB07_EMPTY_HALL --watch
```
- [ ] Alone, Robot R wanders slowly to parts of the hall it has not seen recently, pauses at each, goes back to its post after about two minutes, and **never paces back and forth**.

Now with the real models (Option C, F3 + N3), pulse on:

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --mode live --watch
```
- [ ] **FN-1:** Robot R never walks away from Visitor X while they are talking, unless it says goodbye or excuses itself first.
- [ ] **FN-2:** when Visitor Y approaches or speaks, Robot R glances at Y quickly and then looks back at X.
- [ ] The visitors' behavior looks plausible.

At the end of each run the summary prints a `pulse robot_r:` line (decisions, CONTINUEs, wakes, glances, zombie time, FN-1 violations, model reviews per minute).

**Paste back:** the summary lines of each watched run (from `Run folder:` to `OK`), and anything that looked wrong: darting, staring, interrupting, walking off mid-conversation, pacing.

## 5. Decisions to approve

- **D-60:**
  - **The world's stale window 1 s → 6.5 s** (a host rule).
  - The C1 budget 500 → 780 tokens.
  - The NPC output caps (C1 170, C2 220 tokens).
- **D-61:** the pulse protocol as built.

## If something fails

- **A LIVE run takes much longer than 90 s:** that is expected now; one SB-04 is 90 s of real time.
- **`option B` with a fallback reason:** paste the `VRAM` line of `inference_events.jsonl` from the run folder.
- **The run prints `FAIL`:** paste the summary lines and the last 30 lines of `godot.log`.
