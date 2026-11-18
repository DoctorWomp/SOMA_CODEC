# G3e — What to do on your PC: presence and expression, watched

About 1.5 hours, most of it watching. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` set), llama-server b12443 installed, F3 and N3 registered. What changed and why: [D-71 to D-74](../DECISIONS.md); the G3e section of [G3_PLAN.md](G3_PLAN.md); FIELD_NOTES FN-5 to FN-7.

**Nothing downloads.** Both model servers listen on `127.0.0.1` only. Close games and other GPU programs, and leave the PC alone while a run plays (frame times are measured).

**Paste back summaries only:** the lines each run prints (from `Run folder:` to `OK`). Never paste or upload a run folder: it holds raw prompts and agent memory.

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

## 2. What changed, in one breath

- **The head looks; the body keeps going (D-72).** The legged and wheeled humanoids turn their head (world state now: what they can see follows it) to glance, also while walking. The body turns only when the target is behind the neck's reach and the robot is standing. The quadruped has no neck and turns its body.
- **The face says what the robot is doing (D-73).** Between decisions the visor (or the quadruped's light strip) shows a small loop: waiting `(.  )…(...)` in calm blue, thinking `( | ) ( / ) ( - ) ( \ )` with a sweeping white light, considering `(o_ )`↔`( _o)` in purple, listening `o_o` in calm blue, attending `._.` with no light.
- **Small signs of life, on a dial (D-74):** blinks, small eye shifts, slow light breathing, slight head adjustments. `--presence subtle`, `default` or `performative` sets how much.

## 3. Watched runs: four scenarios, three dial settings (≈ 70 minutes)

Each command opens a window and plays the scenario in real time with Robot R on F3 and the visitors on N3. Run each scenario at the three settings, in this order: `subtle`, `default`, `performative` (only the last word changes). Each run prints a `frames (1920x1080, preset v0): p50 … / p95 … / p99 … ms` line and a `peak VRAM during the run: … MiB` line (G3d tooling).

**SB-04, polite bid** (90 s each):
```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --mode live --watch --resolution 1920x1080 --render-preset v0 --presence subtle
```
- [ ] **Glance with the head:** when Visitor Y approaches or speaks, Robot R's **head** turns to Y and back to X; its body keeps facing X.
- [ ] **Thinking is visible:** while Robot R waits for its model, the visor shows the turning `( | ) ( / ) …` loop with a slow sweeping white light, and it stops when it answers.
- [ ] **No darting or flicker:** glances are smooth; nothing on the visor or lights flickers.

**SB-06, long wait** (4 min each):
```powershell
uv run python tools/run_scenario.py SB06_LONG_WAIT --model llama --mode live --watch --resolution 1920x1080 --render-preset v0 --presence subtle
```
- [ ] **No blank stare while waiting:** after "one moment", Robot R shows the waiting loop `(.  )…(...)` with a slow calm-blue pulse for the whole wait, so you can tell it is waiting without it speaking.
- [ ] **Alive but not busy:** occasional blinks and small eye shifts, slight head adjustments, glances toward whoever speaks; no fidgeting, no pacing, no interruptions.
- [ ] When Y turns back, the display changes (listening `o_o`) and Robot R helps Y.

**SB-07, empty hall** (about 3 min each):
```powershell
uv run python tools/run_scenario.py SB07_EMPTY_HALL --model llama --mode live --watch --resolution 1920x1080 --render-preset v0 --presence subtle
```
- [ ] **Alive but not busy while alone:** the attending face `._.` (no light) with occasional blinks, small eye shifts and slight head adjustments while it roams; the survey keeps its unhurried pace (no extra motion, no flicker). The hall is empty, so there is nobody to glance at.

**SB-08, peripheral speaker** (about 2 min each):
```powershell
uv run python tools/run_scenario.py SB08_PERIPHERAL_SPEAKER --model llama --mode live --watch --resolution 1920x1080 --render-preset v0 --presence subtle
```
- [ ] When the visitors behind Robot R start talking, its **head** turns toward the voice right away (it may turn its body only if the voice is behind its neck's reach), and it does not answer them.
- [ ] When one of them asks it a question, it turns, answers, and the visor shows listening between turns.

**Glance while walking:** none of these four scenarios has Robot R walking while someone speaks (it stands at its post in SB-04, SB-06 and SB-08, and SB-07's hall is empty), so you will see head glances while standing, not while walking. Glancing while walking is covered by the headless test `test_head_glance_while_walking` (in `tools/check.py`). If you want to see it, say so and a scenario can be added for it.

**At each dial setting, compare:**
- [ ] `subtle`: signs of life are there but easy to miss. Not a blank stare.
- [ ] `default`: noticeable at a glance, calm.
- [ ] `performative`: clearly visible, but never fast: no flashing, no darting, nothing that feels like it is trying to get attention.
- [ ] Which setting would you choose as the default for an expo assistant? (The baseline is `default`, 0.5, in `configs/pulse.yaml`; a persona or directive can set its own.)

**Paste back:** for each of the 12 runs, the summary lines (from `Run folder:` to `OK`, including the `frames` and `peak VRAM` lines), and anything that looked wrong: blank staring, darting, flicker, a body turning when the head should, a glance that did not happen.

## 4. Decisions

- **D-71** (color shifting: pattern, not hue; a brief resolved tease only, at G5) is recorded as your decision (option a).
- **D-72 to D-74** are PROPOSED. D-72 changes "the rig is presentation only" for the head: the head is now world state.
- D-60 to D-70 are unchanged by G3e.

## If something fails

- **No `frames` line after a `--watch` run:** paste the last 30 lines of `godot.log` from the run folder.
- **`option B` with a fallback reason:** paste the `VRAM` line of `inference_events.jsonl` from the run folder.
- **The run prints `FAIL`:** paste the summary lines and the last 30 lines of `godot.log`.
