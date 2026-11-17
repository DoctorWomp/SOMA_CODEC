# G3b — What to do on your PC: real models and the bake-off

About 1–2 hours in all, mostly waiting for hashes, downloads and the bake-off itself. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` is set). What was built and why: [D-57](../DECISIONS.md) (models, server) and [D-58](../DECISIONS.md) (scheduler, bake-off).

**Nothing downloads unless you type `yes`.** Everything runs on `127.0.0.1` (your own PC only).

## 1. Get the branch and update

1. GitHub Desktop → **Fetch origin** → **Current branch** → `claude/g3b-2-scheduler-bakeoff` (it includes G3b-1).
2. In PowerShell:
   ```powershell
   cd G:\SOMA_CODEC
   ```
   ```powershell
   uv sync --locked
   ```
3. Run the checks:
   ```powershell
   uv run python tools/check.py
   ```
   Expect five **PASS** lines and `All checks passed.` (no GPU or model needed for this).

## 2. Install llama-server (≈ 0.5–1 GB download)

1. Check your NVIDIA driver:
   ```powershell
   uv run python tools/install_llama.py --check
   ```
   - [ ] It shows your RTX 4070 Ti Super and says the driver meets CUDA 12.4's minimum (551.61). If not, update the driver from NVIDIA first.
2. Install. The checksums could not be pinned from the cloud, so this one time you compare them yourself:
   ```powershell
   uv run python tools/install_llama.py --record-hashes
   ```
   It downloads two files and prints, for each, a `sha256` line and a `size` line.
3. Open https://github.com/ggml-org/llama.cpp/releases/tag/b12443, scroll to **Assets** and find:
   - `llama-b12443-bin-win-cuda-12.4-x64.zip`
   - `cudart-llama-bin-win-cuda-12.4-x64.zip`

   Next to each, GitHub shows a `sha256:` value (click the copy icon if it is shortened).
4. - [ ] Both values match what PowerShell printed → type `yes`. If either differs, type anything else (nothing is installed) and tell me.
5. - [ ] Run `uv run python tools/install_llama.py --check` again: `Installed:` now shows a path ending in `llama-server.exe`, and `Server says:` shows the version.

**Paste back:** the two `sha256` and `size` lines, so I can pin them.

## 3. Register the models you already have

```powershell
uv run python tools/models.py scan "G:\.lmstudio\models\lmstudio-community"
```

This reads every model file in place. Nothing is copied or moved. Vision files (`mmproj-…`) are skipped. Computing SHA-256 reads each whole file once, so expect several minutes for a big folder (the 70B and 31B files take longest). A second scan skips files that did not change.

- [ ] The list shows your models with architecture, size, quantization and context. The ones that match the bake-off say `catalog F1`, `catalog F3` and so on.

## 4. Review the plan

```powershell
uv run python tools/models.py plan
```

- [ ] It lists the 8 core models (F1–F3 for Robot R, N1–N3 for active NPCs, S1–S2 for reactive NPCs), each `FOUND` (with its path) or `MISSING` (with its size and source).
- [ ] It ends with the total download size and the free disk space.

**Paste back:** the whole output.

## 5. Download what is missing (your choice)

Pick the labels you want, for example all missing ones:

```powershell
uv run python tools/models.py download F1 F2 N1 N2 N3 S1 S2
```

It lists each file, its size and its license (all Apache-2.0), then waits for you to type `yes`. Every file is checked against its pinned SHA-256 before it is used. If a download stops, run the same command again: it continues where it stopped.

- [ ] Each file ends with `verified and registered as …`.

## 6. First real run

Robot R on the default model (Qwen3.5-9B Q4_K_M, F1), watching:

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --watch
```

It loads the model (up to a minute the first time), then plays SB-04 as before, with Robot R deciding through the real model.

- [ ] The run finishes and prints `OK`.
- [ ] Robot R talks with X, acknowledges Y without interrupting, and turns to Y when X leaves. Note anything odd: wrong actions, long pauses, repeating itself.
- [ ] In the run folder (printed at the end):
  - `run_manifest.json` lists `model.file`, `model.quant`, `model.sha256` and `model.kv_cache_type`;
  - `llama_server.log` is there;
  - `sidecar\decision_records.jsonl` shows `cached_tokens` growing after the first decision.

Then the Gemma 4 12B QAT model (F3):

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama:F3 --watch
```

**Paste back:** the summary lines both runs print (from `Run folder:` to `OK` or `FAIL`).

## 7. The bake-off, offline part (≈ 30–60 minutes)

```powershell
uv run python tools/bakeoff.py offline
```

This sends the 40 committed Robot R prompts (`bakeoff\prompts_v1.jsonl`) to every core model you have, once with KV cache f16 and once with q8_0. Each model is loaded alone, one after another; Godot does not run. Close games or other GPU programs first: VRAM is measured.

- [ ] It ends with `Results: …\results\bakeoff\results.md`. Each line shows valid answers, repairs, valid actions, promises kept, agreement, tokens/s, p50 and VRAM.

To run only some models: `uv run python tools/bakeoff.py offline --models F1 F2 F3`.

## 8. The bake-off, live part (finalists)

Pick two or three finalists from the table (best valid actions and agreement, fast enough for the 4 s deadline), then:

```powershell
uv run python tools/bakeoff.py live --models F1 F3
```

Each model plays SB-04 headless twice, once LIVE and once STEPPED. That is about 2–3 minutes per run.

- [ ] The "Live and stepped SB-04" table appears in `results.md`, with `Run OK: yes`, deadline misses, fallbacks and p50/p95.

**Paste back:** the whole `results\bakeoff\results.md`.

## 9. If Windows Firewall asks

llama-server listens on `127.0.0.1` only, so it should not need any firewall rule. If Windows still asks about **llama-server**, **Python** or **Godot**, tick **Private networks** only, or click **Cancel**. Never allow Public networks. Cancelling does not break anything here.

## 10. If something fails

- **`llama-server not found`:** step 2 did not finish. Run `uv run python tools/install_llama.py --check`.
- **`model … is not on this machine`:** run `uv run python tools/models.py plan`, then scan or download it.
- **The run prints `FAIL` or the server stops while loading:** open `llama_server.log` in the run folder and paste its last 30 lines.
