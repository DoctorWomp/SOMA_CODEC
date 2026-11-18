# Build and run

Exact commands to set up the project, run every check and open the Godot world (G1).

## One-time setup

You need **uv** (it installs the right Python for you). On Windows, see [OWNER_SETUP_WINDOWS.md](OWNER_SETUP_WINDOWS.md). On Linux/macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

uv uses the Python version in `.python-version` (3.14; D-35) and downloads it if needed.
Then, in the repository folder, install the exact dependency versions from the lockfile:

```bash
uv sync --locked
```

## Run every check

This is the one command that must pass before any change is merged. CI runs it on Python 3.12, 3.13 and 3.14 for every push and pull request, with Godot required.

```bash
uv run python tools/check.py
```

It runs five steps and prints a summary:

1. **Contracts**: every schema in `contracts/` is valid, every valid example passes and every invalid example fails for its stated reason.
2. **Configs**: every file in `configs/` matches its contract, and everything it refers to exists.
3. **Godot data**: the JSON copies in `godot_app/data/` match `configs/` (D-30).
4. **Tests**: the full `pytest` suite.
5. **Godot**: imports the Godot project, compiles every GDScript file (a GDScript warning counts as an error, D-38), runs the headless tests with three test Python sidecars, checks every journal line, packet, action result, link message and agent decision record against the contracts, scans every agent context for private text, and runs SB-04 (twice, to prove it is deterministic) and SB-05 end to end (needs Godot; see below).

`All checks passed.` and exit code 0 means green. If Godot is not found, step 5 shows **SKIP** (never PASS) and the summary says so. CI uses `--require-godot`, which turns a missing Godot into a failure.

## Godot (G1 onwards)

The checks need **Godot 4.7.2 stable** (D-06). Tell them where it is with the `GODOT_BIN` environment variable. On Windows, use the **console** executable, so its output reaches the checks. In PowerShell (once; then open a new PowerShell window):

```powershell
setx GODOT_BIN "G:\Godot\Godot_v4.7.2-stable_win64_console.exe"
```

Or let the project download its own verified copy into `.tools/godot/` (Linux and Windows; used by CI and cloud sessions):

```bash
uv run python tools/install_godot.py
```

Run only the Godot checks, or only some Godot tests:

```bash
uv run python tools/godot_check.py
```

```bash
uv run python tools/godot_check.py --filter sb05
```

### Open and run the world

1. Start Godot, choose **Import**, and pick `godot_app/project.godot` in the repository folder.
2. Press **F5** (or the ▶ button) to run Sandbox Flats. The world is built when it runs; the editor's 3D view of `main.tscn` is empty on purpose.
3. To see every robot body side by side, open `scenes/robot_lineup.tscn` and press **F6** (Run Current Scene).

Keys: `C` camera mode (free / orbit) · `[` `]` select avatar · hold right mouse to look or orbit · wheel to zoom · `W A S D` move · `Q` `E` down / up · `Shift` faster · `Space` pause · `R` restart the demo · `H` hide the panel · `F2` show what the selected avatar sees and hears.

Each run of the main scene writes an event journal (one JSON line per event, D-41) to `user://journals/`; on Windows that is `%APPDATA%\Godot\app_userdata\SOMA RANGE\journals`. The newest 10 are kept.

From a terminal instead of the editor:

```bash
godot --path godot_app
```

### The demo connected to Python (G2b)

```bash
uv run python tools/run_link_demo.py
```

This starts the Python sidecar on 127.0.0.1 with a fresh session token and opens the Godot demo connected to it. Robot_legged and robot_quadruped are then driven by scripted Python agents: when the visitor below the platform waves at them, they wave back and say hello (the quadruped's wave is refused: it has no arm). The panel shows `Python link: CONNECTED`. Close the Godot window to finish; a summary of what crossed the link is printed. To run the sidecar on its own: `RANGE_SESSION_TOKEN=<16+ characters> uv run python -m range_service.link --agent robot_legged=greeter`.

### Run a scenario (G3a)

```bash
uv run python tools/run_scenario.py SB04_POLITE_BID
```

Runs the scenario from its file, end to end: the Python agent runtimes (Demo policy, no model) and Godot (headless) connected through the link, in **stepped** mode (exactly repeatable, D-48). It prints a summary and writes a run folder under `runs/` with the journal, the run manifest, every decision record and what each agent was shown. Useful variants:

```bash
uv run python tools/run_scenario.py SB04_POLITE_BID --watch
```

```bash
uv run python tools/run_scenario.py SB05_RAMP_VS_STAIRS --watch
```

```bash
uv run python tools/run_scenario.py SB04_POLITE_BID --body robot_r=quadruped
```

```bash
uv run python tools/run_scenario.py SB04_POLITE_BID --model fake --mode live --watch
```

`--watch` opens the Godot window (it closes by itself when the scenario ends). `--model` takes `none` (Demo policy), `fake`, `fake-slow:MS`, `fake-malformed` or `replay:<run folder>/sidecar/decision_records.jsonl`; no real model is called before G3b. `--mode live` never holds the world (not repeatable).

### Repeat the determinism checks under CPU load

```bash
uv run python tools/godot_check.py --filter determinis --repeat 5 --cpu-load 4
```

CI runs this on every push (D-47).

### After editing a map, body, expression or scenario file

Godot reads JSON copies of `configs/maps/`, `configs/bodies/`, `configs/expressions/` and a world-only view of `configs/scenarios/` (D-30, D-48). Body files follow body contract 2.0 (D-37); `tools/validate_configs.py` explains any problem, including contradictions such as a gesture that needs an arm on a body without one. After changing one of those YAML files, refresh the copies and commit both:

```bash
uv run python tools/export_godot_data.py
```

`tools/check.py` fails with a clear message if you forget.

### Screenshots in a cloud session (no GPU)

Render under a virtual display with the Compatibility renderer:

```bash
xvfb-run -a -s "-screen 0 1600x900x24" .tools/godot/Godot_v4.7.2-stable_linux.x86_64 --path godot_app --rendering-method gl_compatibility --rendering-driver opengl3 --fixed-fps 60 --resolution 1600x900 res://dev/capture.tscn -- --out=$PWD/docs/gates/G1_screenshots
```

The Beacon (G3a) has its own capture scene:

```bash
xvfb-run -a -s "-screen 0 1600x900x24" .tools/godot/Godot_v4.7.2-stable_linux.x86_64 --path godot_app --rendering-method gl_compatibility --rendering-driver opengl3 --fixed-fps 60 --resolution 1600x900 res://dev/beacon_capture.tscn -- --out=$PWD/docs/gates/G3a_screenshots
```

Rig step A (D-56): every gesture, the four robots side by side at the gesture's peak, plus gaze:

```bash
xvfb-run -a -s "-screen 0 1600x900x24" .tools/godot/Godot_v4.7.2-stable_linux.x86_64 --path godot_app --rendering-method gl_compatibility --rendering-driver opengl3 --fixed-fps 60 --resolution 1600x900 res://dev/gesture_capture.tscn -- --out=$PWD/docs/gates/RIG_A_screenshots
```

## Real models (G3b, D-57)

Everything runs on 127.0.0.1. Nothing downloads without your "yes". Owner steps: [gates/G3b_OWNER_CHECKLIST.md](gates/G3b_OWNER_CHECKLIST.md).

```bash
uv run python tools/install_llama.py --check            # pinned llama.cpp b12443, NVIDIA driver check
uv run python tools/install_llama.py --record-hashes    # Windows: CUDA 12 build (compare the checksums once)
uv run python tools/install_llama.py --from-source      # Linux / cloud: static CPU build of the pinned commit
uv run python tools/models.py scan <folder>             # register .gguf files in place (models/registry.local.yaml)
uv run python tools/models.py plan                      # core set: found, missing, download size
uv run python tools/models.py download F3 N1            # only what you name; SHA-256 checked
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama          # configs/inference.yaml
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama:F3       # another catalog model
uv run python tools/run_scenario.py SB04_POLITE_BID --model llama --npc-model none   # NPCs on templates (Option B)
uv run python tools/bakeoff.py offline                  # bake-off on bakeoff/prompts_v3.jsonl (D-58 to D-60)
uv run python tools/bakeoff.py live --models F3 F1 --npc-model N3   # Option C: Robot R under NPC load, promotions, VRAM
```

**Measurements (G3d, D-69, D-70):**

```bash
uv run python tools/run_scenario.py SB04_POLITE_BID --mode live --model llama --watch --resolution 1920x1080 --render-preset v0
uv run python tools/run_scenario.py SB06_LONG_WAIT --no-pulse
uv run python tools/compare_runs.py runs/<run A> runs/<run B>
uv run python tools/bakeoff.py live --models F3 --npc-model N3 --modes LIVE LIVE_RENDERED --resolution 1920x1080
uv run python tools/soak.py
```

A rendered run (`--watch`) records frame times and peak VRAM in `summary.json` (`render`); every run has a per-agent `report` (offered vs accepted actions, response latency, timeouts, fallbacks, model calls, glances, FN-1). `compare_runs.py` prints two or more runs side by side. `soak.py` runs SB-09 (21 simulated minutes) and writes `soak_summary.json`. Summaries hold counts only; run folders hold raw prompts and memories and stay under the git-ignored `runs/` and `results/`. `tools/check.py` runs its scenario runs side by side (`RANGE_CHECK_JOBS=N` to change how many at once, D-68).

**The pulse (G3c-2, D-61):** SB-06, SB-07 and SB-08 run the pulse protocol (robots that stay visibly present between decisions): `uv run python tools/run_scenario.py SB06_LONG_WAIT --watch`. It is on whenever a scenario asks for it or a model drives Robot R; `--pulse on|off` overrides. A run folder adds `pulse.jsonl` and a `pulse` section in `summary.json`; settings are in `configs/pulse.yaml`. LIVE runs now run in real time (one SB-04 is 90 s).

**Two servers (G3c-1, D-59):** `--model llama` starts Robot R's server and the NPC server from `configs/inference.yaml` (Option C). Visitors promoted to C1/C2 decide through the NPC model; `--npc-model` chooses it (`auto` follows `--model`; `none` keeps the templates; `fake` and `replay:` drive NPCs without a model). If the NPC server cannot start or would not fit the VRAM budget, the run uses one server (Option B) and says why. A run folder adds `inference_events.jsonl`, `promotions.jsonl` and `slot_snapshots/`.

`--model llama-attach:PORT` uses a llama-server you started yourself (key in `RANGE_LLAMA_API_KEY`). Tests never need a model: `range_service/agents/standin.py` plays the server.

## Smaller commands

Check only the content files (useful after editing a YAML file):

```bash
uv run python tools/validate_configs.py
```

Run only the tests, or one test file:

```bash
uv run pytest
```

```bash
uv run pytest tests/test_delta.py -v
```

Run the checks on a specific Python version (uv downloads it if needed):

```bash
uv run --python 3.12 python tools/check.py
```

## Adding or changing a dependency

Dependencies are kept minimal (`jsonschema`, `pyyaml`, `pytest`). If one is truly needed, add it with uv so the lockfile updates, and commit both files:

```bash
uv add <package>
```
