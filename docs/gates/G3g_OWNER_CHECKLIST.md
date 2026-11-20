# G3g owner checklist: lean answers

**Gate:** G3g ([G3_PLAN.md](G3_PLAN.md) "G3g"). **Decisions:** D-84 to D-89 (PROPOSED); your 2026-11-20 decisions on D-75 to D-83 are recorded in DECISIONS.md.
**Target (D-87):** Robot R p95 under 4 s **and** its fallback decisions (timeouts + unusable answers, each a WAIT) at most 5% alone and at most 10% with N3, in LIVE and LIVE_LOAD. results.md prints it as "Target (G3g, D-87)", with G3f's timeout target beside it.
**LEAN targets offline (D-85),** on prompts_v3, Robot R's prompts: final valid ≥ 98%, promises kept (behavior) ≥ 95% and (flag) ≥ 60% (F3's FULL baseline), generated tokens p50 ≤ 70, no answer at the cap. results.md prints them in "Robot R's answers: tokens per answer and per field".

In the cloud, LEAN, salvage and the token accounting ran end to end with the 0.8B smoke model T1 on a CPU only: plumbing, not results. Everything below is on your PC.

## 0. Before you start: GPU memory (once, about 5 minutes)

Follow [OWNER_SETUP_WINDOWS.md](../OWNER_SETUP_WINDOWS.md) "GPU memory": close what holds GPU memory (Task Manager, Dedicated GPU memory column), and set **CUDA - Sysmem Fallback Policy = Prefer No Sysmem Fallback** for `llama-server.exe` if you want measurements that never spill into system RAM. Every run now records what other programs held before the servers started (`vram_hygiene` in each run's summary; the last column of the live VRAM table) and warns when less than the 2 GB reserve is left.

## 1. Update

```powershell
cd G:\SOMA_CODEC
```

```powershell
git fetch origin && git checkout claude/g3g-decisions-index-jxppr8 && git pull
```

```powershell
uv sync --locked
```

```powershell
uv run python tools/check.py
```

Start a fresh results file (the G3f one stays for reference):

```powershell
Move-Item results\bakeoff\results.json results\bakeoff\results_2026-11-20.json
```

## 2. What each field of Robot R's answer costs, and the grammar's string limits (D-84, about 15 minutes)

The same Robot R prompts with and without `maxLength` in the grammar; per-field token counts from the tokens the model actually generated:

```powershell
uv run python tools/bakeoff.py tokens --models F3 F1
```

Then the same for SHORT, whose 60-character reason limit is the one that binds (does a forced end of a string make the model write more, for example white space?):

```powershell
uv run python tools/bakeoff.py tokens --models F3 F1 --answer SHORT
```

**Paste back:** `results\bakeoff\tokens.md` and `results\bakeoff\tokens_short.md` (counts only; the answers stay in the .json files).

## 3. LEAN vs FULL offline, F3 and F1 (prompts_v3, about 30 minutes)

`--activity on` offers the activity as a live run does (the pulse is on in every run with a model); prompts_v3 holds prompts without it, so run FULL both ways:

```powershell
uv run python tools/bakeoff.py offline --models F3 F1 --kv q8_0
```

```powershell
uv run python tools/bakeoff.py offline --models F3 F1 --kv q8_0 --activity on
```

```powershell
uv run python tools/bakeoff.py offline --models F3 F1 --kv q8_0 --focal-answer LEAN --activity on
```

## 4. Live, F3 + N3, LEAN (about 25 minutes)

Salvage (D-86) is on in every run unless you pass `--no-salvage`. The baseline first, then LEAN:

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD
```

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --focal-answer LEAN
```

Robot R alone with LEAN (the 5% target):

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model none --modes LIVE --focal-answer LEAN
```

## 5. LEAN with the GPU guard at cap 1, in both guard settings (D-89, about 20 minutes)

`ALL` holds NPC calls during every Robot R call (as G3f); `DECISIONS` not during its background pulse reviews:

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --focal-answer LEAN --gpu-guard on --npc-cap 1 --guard-hold ALL
```

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --focal-answer LEAN --gpu-guard on --npc-cap 1 --guard-hold DECISIONS
```

## 6. F1 + N3 with LEAN, for the model comparison (about 12 minutes)

```powershell
uv run python tools/bakeoff.py live --models F1 --npc-model N3 --modes LIVE LIVE_LOAD --focal-answer LEAN
```

## 7. A real-model soak (21 minutes)

```powershell
uv run python tools/soak.py --model llama --mode live --focal-answer LEAN
```

(Without `--focal-answer` it runs configs/inference.yaml as it is, FULL.) The soak now fails only over a budget or a cap: a capped store or a context that grew below its bound is a NOTE (D-88).

## 8. Paste back

- `results\bakeoff\results.md` (all tables: the offline tables with "Robot R's answers: tokens per answer and per field", the live tables with the VRAM hygiene column, "Robot R's calls", and the target table);
- `results\bakeoff\tokens.md` and `tokens_short.md` from §2;
- the soak's printed table or its `soak_summary.json`.

| Question | Where | Decides |
|---|---|---|
| Does `maxLength` change the tokens generated for the same text, or make the model write white space after a forced end of a string? | tokens.md, tokens_short.md | D-84; whether LEAN keeps text limits out of the grammar |
| Which fields cost the most tokens (reason, activity and wake conditions, speech)? | tokens.md; the offline answer table | D-84, D-85 |
| Does LEAN meet its offline targets for F3 (and F1)? | "Robot R's answers" table: LEAN targets column | D-85: LEAN as Robot R's default |
| How many cut-off answers did salvage turn into actions, and how many fallbacks are left? | Robot R table (salvaged), target table | D-86 |
| Does F3 + N3 with LEAN meet the D-87 target in LIVE and LIVE_LOAD, and does the guard (cap 1, ALL vs DECISIONS) add anything? | target table; NPC timeouts beside | D-87, D-89 |
| Does F1 meet it where F3 does not, at the same quality? | target table; offline tables | D-79 stays or is revisited |
| Do other programs hold GPU memory, and is the free memory above the reserve? | live VRAM table, last column | D-87 |
