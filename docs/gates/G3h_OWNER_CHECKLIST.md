# G3h owner checklist: the new LEAN default for F3

**Gate:** G3h ([G3_PLAN.md](G3_PLAN.md) "G3h"). **Decisions:** D-110 to D-114 (PROPOSED); your 2026-11-21 decisions on D-84 to D-89 are recorded in DECISIONS.md.
**What is new:** an invalid activity no longer costs the actions (D-110); Robot R's LEAN prompts and answers name people by handle, P1, P2, ... (D-111), and leave out defaults (D-112); prompts_v4 holds Robot R's prompts as LEAN sends them (D-113). FULL is unchanged and stays the configured default until §2 passes.

**Targets for the new default** (F3, LEAN with D-110 to D-112), offline on prompts_v4, Robot R's prompts: **final valid ≥ 98%, promises kept ≥ 80% (flag) and ≥ 95% (behavior), generated tokens p50 ≤ 70.** If met, LEAN becomes F3's default (D-85, your conditional approval): one line in `configs/inference.yaml` (`focal.answer: LEAN`), in a follow-up change.
**Live acceptance (D-87, your 2026-11-21 decision):** normal LIVE runs, Robot R p95 < 4 s and fallback decisions ≤ 10% with N3, ≤ 5% alone. LIVE_LOAD is a stress test: reported, not judged. Decisions held by FN-1 are counted apart.

In the cloud, F3 and F1 ran on prompts_v4 on a CPU with 2 prompts per role: plumbing only (G3_PLAN "G3h" has what it showed). Everything below is on your PC.

## 0. Before you start

Close what holds GPU memory (OWNER_SETUP_WINDOWS.md "GPU memory"). Your G3g run showed it does not change timeouts (contention is compute), but it keeps the reserve for Godot.

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

Start a fresh results file (the G3g one stays for reference):

```powershell
Move-Item results\bakeoff\results.json results\bakeoff\results_2026-11-21.json
```

## 2. Offline on prompts_v4, F3 and F1 (about 30 minutes)

prompts_v4 holds LEAN prompts, so it runs with `--focal-answer LEAN` only:

```powershell
uv run python tools/bakeoff.py offline --models F3 F1 --kv q8_0 --set bakeoff\prompts_v4.jsonl --focal-answer LEAN
```

For comparison with FULL as a live run sends it (prompts_v3, the activity offered):

```powershell
uv run python tools/bakeoff.py offline --models F3 F1 --kv q8_0 --activity on
```

The "Robot R's answers" table now has `ids` and `numbers` columns: they show what handles and compaction left in F3's and F1's arguments.

## 3. Live, F3 + N3, the new default (about 15 minutes)

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_LOAD --focal-answer LEAN
```

LIVE is judged; LIVE_LOAD prints "stress: reported, not judged".

## 4. F3 alone, LIVE (about 5 minutes)

```powershell
uv run python tools/bakeoff.py live --models F3 --npc-model none --modes LIVE --focal-answer LEAN
```

## 5. Diagnose the new runs (a minute)

```powershell
uv run python tools/bakeoff.py diagnose
```

It now shows which activity rule an answer broke (the kind only), how many activities were dropped with the actions kept, and how many decisions were held by FN-1.

## 6. Paste back

- `results\bakeoff\results.md` (the offline tables with the LEAN targets column, the live tables, "Robot R's calls" and the target table);
- `results\bakeoff\diagnosis.md`.

| Question | Where | Decides |
|---|---|---|
| Does F3 with the new LEAN meet final valid ≥ 98%, promises ≥ 80% / 95%, generated tokens p50 ≤ 70 on prompts_v4? | "Robot R's answers" table, LEAN targets column; Robot R offline table | D-85: LEAN as F3's default |
| How many tokens are ids and numbers now, and what is left in args? | `ids`, `numbers`, `args` columns | D-111, D-112; what to cut next |
| Do dropped activities replace the ACTIVITY_RULE fallbacks, and which rules do answers break? | target table "Activities dropped"; diagnosis.md | D-110 |
| Does F3 + N3 meet the LIVE target with the new default, and F3 alone the 5%? | target table (LIVE rows) | D-87 acceptance |
| How many decisions were held by FN-1? | target table "Held by FN-1" | D-110 |

## 7. Speculative decoding (not built; a proposal to decide on)

D-114 has the investigation: S1 (Gemma 4 E2B, already in the catalog) shares F3's tokenizer exactly and would take about 1.6 to 2.0 GB of VRAM as a draft model. Nothing to run for it now; tell me whether to build it as a named condition in a later gate.
