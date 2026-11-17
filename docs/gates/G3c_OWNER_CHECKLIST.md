# G3c-1 — What to do on your PC: two servers, model-driven NPCs, latency and VRAM

About 45–75 minutes, mostly waiting for runs. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` is set), llama-server b12443 installed. What was built and why: [D-59](../DECISIONS.md).

**Nothing downloads unless you type `yes`.** Both model servers listen on `127.0.0.1` only (your own PC), each with its own key.

Close games, browsers with video and other GPU programs first: VRAM is measured.

## 1. Get the branch and update

1. GitHub Desktop → **Fetch origin** → **Current branch** → `main` → **Pull origin** (G3c-1 is merged).
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
   - [ ] Five **PASS** lines and `All checks passed.` (no GPU or model needed). Step 6 now also runs SB-04 with model-driven NPCs (fake model) and the canary check.
3. Check that the models are there:
   ```powershell
   uv run python tools/models.py plan
   ```
   - [ ] F3 and N3 show `FOUND` (also N1 and S1 if you want them in step 5).

## 2. First run with two servers (watching)

Robot R on F3, the visitors on N3, both servers started together:

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --watch
```

- [ ] The summary says `NPC model: llama (option C)`. If it says `option B` and a `fallback:` reason, copy that line: the NPC server did not start or the VRAM estimate was over budget.
- [ ] It ends with `OK`.
- [ ] Watch the visitors: they now answer Robot R and react to it through the NPC model (their scripted lines from the scenario still play). Note anything odd: a visitor repeating itself, saying something strange, or wandering off.
- [ ] In the run folder (printed at the end):
  - `run_manifest.json` lists `inference.option: "C"`, `npc_model.file`, `vram.focal_mib`, `vram.npc_mib` and `vram.note`;
  - `llama_server_focal.log` and `llama_server_npc.log` are there, and `slot_snapshots\` has a few `persona_….bin` files;
  - `promotions.jsonl` has one line per visitor promotion.

**Paste back:** the summary lines (from `Run folder:` to `OK` or `FAIL`), and the `vram.` and `inference.` lines of `run_manifest.json`.

## 3. Robot R's latency under NPC load, promotion latency and VRAM (≈ 20–30 minutes)

```powershell
uv run python tools/bakeoff.py live --models F3 F1 --npc-model N3
```

Each Robot R model plays SB-04 headless four times with N3 on the NPC server:

| Mode | What it measures |
|---|---|
| `LIVE` | Robot R and the visitors in real time, pre-warming on |
| `LIVE_COLD` | the same with pre-warming off: cold promotion latency |
| `LIVE_LOAD` | the same plus four streams of recorded NPC prompts kept running on the NPC server: Robot R's latency while NPCs load the other server |
| `STEPPED` | the world waits for every answer: decisions without time pressure |

- [ ] The "SB-04 in Godot: Robot R and the NPC server (Option C)" table in `results\bakeoff\results.md` has 8 rows with `Run OK: yes` and option `C`.
- [ ] Compare Robot R's p50/p95 in `LIVE` and `LIVE_LOAD`: that is the cost of NPC load on the other server (both servers share one GPU).
- [ ] Promotion latency: `LIVE` (warm) against `LIVE_COLD` (cold). A visitor that is never promoted, or never acts, shows `– (0)`.
- [ ] VRAM per server (focal / NPC). If it shows `–`, `results.json` holds the reason (`vram_note`).

If you also want N1 as the NPC model: `uv run python tools/bakeoff.py live --models F3 --npc-model N1`.

## 4. NPC candidates on NPC prompts (≈ 20–40 minutes)

```powershell
uv run python tools/bakeoff.py offline --models N3 N1 S1 F3 --kv q8_0
```

This uses the new prompt set `bakeoff\prompts_v2.jsonl` (96 prompts: 40 Robot R, 40 visitor decisions at C1 and C2, 16 extra promise situations). The old results move to `results_previous_set.json`, so sets are never mixed.

- [ ] `results.md` now has two offline tables: **Robot R prompts** and **NPC prompts**.
- [ ] "Promises kept" shows two numbers: *flag* (the model set `fulfills_commitment`) / *behavior* (it addressed, faced or approached the person it promised to help).
- [ ] Any unusable answer is saved raw in `results.json` under `invalid_answers`.

Optional, to find out why F2 failed: `uv run python tools/bakeoff.py offline --models F2 --kv q8_0 --set bakeoff/prompts_v1.jsonl`, then look at `invalid_answers` in `results.json` (paste a few back).

## 5. Optional: watch the visitors with each NPC candidate

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --npc-model llama:N1 --watch
```

Same with `llama:S1` for the small model. NPCs on templates for comparison: `--npc-model none`.

## What to paste back

1. The summary lines of step 2 and the `vram.` / `inference.` lines of its `run_manifest.json`.
2. The whole `results\bakeoff\results.md` after steps 3 and 4.
3. Anything odd you saw the visitors do in step 2 or 5.

## If something fails

- **`option B` with `fallback: …did not start`:** open `llama_server_npc.log` in the run folder and paste its last 30 lines.
- **`option B` with `…over the 16376 MiB budget`:** paste the `VRAM` line of `inference_events.jsonl` (it shows the estimate per server). The estimate is an upper bound; `over_budget: WARN` in `configs\inference.yaml` lets the run start anyway, recorded.
- **The run prints `FAIL`:** paste the summary lines and the last 30 lines of `godot.log`.
- **Windows Firewall asks about llama-server, Python or Godot:** tick **Private networks** only, or **Cancel**. Never Public.
