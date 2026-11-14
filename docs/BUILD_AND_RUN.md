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
5. **Godot**: imports the Godot project and runs its headless tests (needs Godot; see below).

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

Keys: `C` camera mode (free / orbit) · `[` `]` select avatar · hold right mouse to look or orbit · wheel to zoom · `W A S D` move · `Q` `E` down / up · `Shift` faster · `Space` pause · `R` restart the demo · `H` hide the panel.

From a terminal instead of the editor:

```bash
godot --path godot_app
```

### After editing a map or body file

Godot reads JSON copies of `configs/maps/` and `configs/bodies/` (D-30). After changing one of those YAML files, refresh the copies and commit both:

```bash
uv run python tools/export_godot_data.py
```

`tools/check.py` fails with a clear message if you forget.

### Screenshots in a cloud session (no GPU)

Render under a virtual display with the Compatibility renderer:

```bash
xvfb-run -a -s "-screen 0 1600x900x24" .tools/godot/Godot_v4.7.2-stable_linux.x86_64 --path godot_app --rendering-method gl_compatibility --rendering-driver opengl3 --fixed-fps 60 --resolution 1600x900 res://dev/capture.tscn -- --out=$PWD/docs/gates/G1_screenshots
```

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
