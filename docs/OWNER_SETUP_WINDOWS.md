# Owner setup — Windows PC

Checklist for the development PC (Windows 11 Pro, Ryzen 9 9950X, 96 GB RAM, RTX 4070 Ti Super). **Not needed until G1.** G0 runs entirely in the cloud.

## Before G1 (Godot world)

- [ ] **GitHub Desktop** — https://desktop.github.com — sign in, then *Clone repository* → `DoctorWomp/SOMA_CODEC` into a folder without spaces, e.g. `C:\dev\SOMA_CODEC`.
- [ ] **Godot 4.7.2 (standard, not .NET), Windows 64-bit** — https://godotengine.org/download/archive/4.7.2-stable/ — unzip to e.g. `C:\tools\godot\`. Keep both the normal and the `_console` executable; the console one is used for automated checks.
- [ ] **uv** (manages Python and dependencies) — in PowerShell:
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  uv installs the right Python version for the project by itself.
- [ ] **VS Code** (optional) with the *Claude Code* and *godot-tools* extensions.
- [ ] Check: in the repo folder, `uv run python tools/check.py` passes (available after G0 merges).

## Before G3 (local models)

- [ ] Update the **NVIDIA driver**.
- [ ] llama.cpp Windows CUDA build and the bake-off model files: exact downloads and commands will be provided at G3 (D-20, D-21).
- [ ] Free disk space: ~3–8 GB per model file.

## Habits

- Open GitHub Desktop and **Pull** before starting work; **Commit** and **Push** when done.
- Don't edit the same file locally and in a cloud session at the same time.
- Never commit API keys, passwords or personal recordings.
