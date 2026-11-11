# SOMA_CODEC

SOMA RANGE development foundation for Claude Code: a Godot 4 connection harness and a Python HORIZON sidecar scaffold. This is preparation for building the Expo simulator, not a finished game or working HORIZON perception system. The original repository contained only this heading; existing history is preserved.

## Start here

Install Python 3.11+ and Godot **4.5.1** (the pinned test baseline). No Python third-party packages or model credentials are needed for the offline checks. From the repository root:

```powershell
python scripts/check.py
python scripts/demo.py
$env:PYTHONPATH = "$PWD/sidecar"
python -m soma_range.server
```

Leave that terminal running. Open `godot/project.godot` in Godot and press F6 on `main.tscn` (or F5 for the project). Click the synthetic observation button; the screen should display `acknowledge` from the offline adapter. If the sidecar is stopped, the screen reports a connection failure. Close the sidecar with Ctrl+C.

To run the full automated gate on Windows:

```powershell
$env:GODOT_BIN = 'C:/path/to/Godot_v4.5.1-stable_win64_console.exe'
python scripts/check.py --require-godot
# Equivalent wrapper:
./scripts/run_tests.ps1 -RequireGodot
```

On macOS/Linux use `PYTHONPATH=sidecar python -m soma_range.server` and `GODOT_BIN=/path/to/godot python scripts/check.py --require-godot`. A missing engine is explicitly skipped in the default check and fails the required gate. CI runs Python 3.11/3.13 and the pinned Linux Godot headless import/startup check. GUI playtesting remains a separate human check.

## What exists

- Strict observation and decision contracts, synthetic Expo fixture, per-owner memory primitive.
- Loopback-only stateless sidecar, offline A/B stub, canonical recorded-decision digest checks.
- Godot UI that sends one synthetic observation and displays the result; headless startup smoke.
- Tests for malformed inputs, owner isolation, unknown sources, HTTP boundary and trace replay validation.

## What comes next

Read [architecture and source boundaries](docs/ARCHITECTURE.md), [wire contracts](docs/CONTRACTS.md) and [milestones](docs/MILESTONES.md). M1 is the first incomplete feature milestone: one Expo room with Robot R and Visitor X. Live autonomous LLM NPCs, navigation, perception filtering, Director/Participant modes, HORIZON inference, audio/MIDI hardware, persistent memory, F8 bug capture and world replay are all planned.

Open Claude Code in this repository and ask:

> Read CLAUDE.md and implement the first incomplete milestone in docs/MILESTONES.md. Preserve the architecture and source/privacy boundaries. Add acceptance tests, run the complete gate, and report what needs manual verification before advancing.

`CLAUDE.md` imports the canonical [AGENTS.md](AGENTS.md) rules. Use small feature branches and draft PRs; do not merge until reviewed. No automatic provider access or permissive agent settings are installed.

## References and research limits

The available SOMA Codec Memory Check conversation grounds the concepts; unavailable earlier blueprints and linked atlas files are documented in the architecture notes. A/B arms currently behave identically. No experimental benefit or full simulation determinism is established.

Engine check commands follow the [Godot 4.5 command-line documentation](https://docs.godotengine.org/en/4.5/tutorials/editor/command_line_tutorial.html); the connection uses [HTTPRequest](https://docs.godotengine.org/en/4.5/classes/class_httprequest.html). Project instructions use [Claude Code memory imports](https://code.claude.com/docs/en/memory). No project license existed in the baseline; this change does not choose one on the owner's behalf.
