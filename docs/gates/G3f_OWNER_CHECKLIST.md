# G3f owner checklist: Robot R on time under load

**Gate:** G3f ([G3_PLAN.md](G3_PLAN.md) "G3f"). **Decisions:** D-75 to D-83 (PROPOSED), D-81 builds your D-70 decision.
**Target:** Robot R p95 under 4 s with at most 5% of its calls timed out, in LIVE and LIVE_LOAD, NPC timeouts reported beside it. results.md now prints this target table for every live row.

Everything below is on your PC (RTX 4070 Ti SUPER). In the cloud the conditions were measured against a simulated shared GPU only (`agents/simgpu.py`, `tools/contention_sim.py`): those numbers say which condition helps under stated assumptions, not what your GPU does.

Each live SB-04 run is 90 s of real time; `--repeat 3` (the default) pools three. One mode with one condition takes about 5 minutes plus loading the models.

## 0. Update

```powershell
cd G:\SOMA_CODEC
```

```powershell
git fetch origin && git checkout claude/dazzling-newton-m8p798 && git pull
```

```powershell
uv sync --locked
```

```powershell
uv run python tools/check.py
```

## 1. Diagnose the runs you already have (no rerun, about a minute)

Your 2026-11-18/19 run folders under `results\bakeoff\run_*` are still there. The old harness appended later runs to a folder's records (D-75): `diagnose` splits every folder run by run and breaks Robot R's calls down by outcome and cost.

```powershell
uv run python tools/bakeoff.py diagnose
```

**Paste back:** `results\bakeoff\diagnosis.md` (counts and timings only). It answers what results.json could not: which invalid outputs were cut off, FN-1 or activity-rule repairs; Robot R's queue, prefill and generation times; prompt, cached and generated tokens; and how much of each timed-out call the NPC server was also busy. Timed-out calls have no server timings (the call was abandoned), so their prompt size is the assembled context's.

## 2. Keep results comparable

Move the old results aside so the new rows start clean (the old file stays for reference):

```powershell
Move-Item results\bakeoff\results.json results\bakeoff\results_2026-11-19.json
```

Rows from the pre-G3c-2 harness (not real time) are now left out of results.md, and rows that pooled an earlier run are marked POOLED, if you ever run `tools/bakeoff.py report` on the old file.

## 3. Baseline with the new instrumentation (about 25 minutes)

The same conditions as before, now with Robot R's per-call breakdown and one run per folder:

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD STEPPED
```

```powershell
uv run python tools/bakeoff.py live --models F3 F1 --npc-model none --modes LIVE
```

## 4. Each condition alone, LIVE and LIVE_LOAD (about 10 minutes each)

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --focal-layout SYSTEM_PREFIX
```

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --focal-answer SHORT
```

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --gpu-guard on
```

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --gpu-guard on --npc-cap 1
```

## 5. All three together, and F1 with them (about 20 minutes)

```powershell
uv run python tools/bakeoff.py live --models F3 F1 --npc-model N3 --modes LIVE LIVE_LOAD --focal-layout SYSTEM_PREFIX --focal-answer SHORT --gpu-guard on
```

## 6. Quality of the conditions offline (Robot R prompts, prompts_v3, about 20 minutes)

SHORT changes what Robot R may write; SYSTEM_PREFIX only how the same prompt is sent. Both must keep validity and promises:

```powershell
uv run python tools/bakeoff.py offline --models F3 F1 --kv q8_0
```

```powershell
uv run python tools/bakeoff.py offline --models F3 F1 --kv q8_0 --focal-layout SYSTEM_PREFIX --focal-answer SHORT
```

## 7. Paste back

- `results\bakeoff\results.md` (all tables, including "Robot R's calls: outcomes and where the time goes" and the G3f target table);
- `results\bakeoff\diagnosis.md` from step 1.

What to look for, and what each answer decides:

| Question | Where | Decides |
|---|---|---|
| Does Robot R's cache share rise from about 0 to about a third with SYSTEM_PREFIX, and its prefill fall? | Robot R table: cache share, prefill p50 | D-76: make SYSTEM_PREFIX Robot R's default |
| How many tokens does Robot R generate, and does SHORT cut them without losing validity or promises? | Robot R table: generated tokens; offline table | D-77: make SHORT the default |
| Does the GPU guard bring LIVE_LOAD under the target, and what do NPC timeouts and NPC p95 cost? | target table; NPC columns | D-78: turn the guard on, and with which cap |
| Does F1 meet the target where F3 does not, at the same validity and promises? | target table; offline Robot R table | D-79: switch Robot R's default model |

## 8. Soak with real models (optional, 21 minutes)

D-81 bounds raw heard speech. With the fake model the cloud soak passes; with real models:

```powershell
uv run python tools/soak.py --model llama --mode live
```

**Paste back:** the printed table, or `soak_summary.json` from the run folder.

## 9. SB-10 (watched): see [G3e_OWNER_CHECKLIST.md](G3e_OWNER_CHECKLIST.md) §SB-10

Not answered here, needs your eyes: how the glance while walking looks.
