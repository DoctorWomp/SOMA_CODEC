# Owner setup — Windows PC

Checklist for the development PC (Windows 11 Pro, Ryzen 9 9950X, 96 GB RAM, RTX 4070 Ti Super).

## For G1 (Godot world)

- [x] **GitHub Desktop** with the repository cloned (yours is at `G:\SOMA_CODEC`).
- [x] **Godot 4.7.2 (standard, not .NET), Windows 64-bit**, unzipped (yours is at `G:\Godot`). The folder should hold two files: `Godot_v4.7.2-stable_win64.exe` (the editor you open) and `Godot_v4.7.2-stable_win64_console.exe` (used by the automated checks).
- [x] **uv**. Your uv picked Python 3.14, and the project now asks for 3.14 too (`.python-version`, D-35).
- [ ] **Tell the checks where Godot is** (once). In PowerShell:
  ```powershell
  setx GODOT_BIN "G:\Godot\Godot_v4.7.2-stable_win64_console.exe"
  ```
  Close PowerShell and open a new window so the setting takes effect.
- [ ] **Check:** in a new PowerShell window, in `G:\SOMA_CODEC`, run `uv run python tools/check.py`. The summary should list five PASS lines, including **Godot**. If it says **SKIP Godot**, the `GODOT_BIN` step did not take effect.
- [ ] **VS Code** (optional) with the *Claude Code* and *godot-tools* extensions.

What to look at once it runs: [docs/gates/G1_OWNER_CHECKLIST.md](gates/G1_OWNER_CHECKLIST.md).

## Before G3 (local models)

- [ ] Update the **NVIDIA driver**.
- [ ] llama.cpp Windows CUDA build and the bake-off model files: exact downloads and commands will be provided at G3 (D-20, D-21).
- [ ] Free disk space: ~3–8 GB per model file.

## Habits

- Open GitHub Desktop and **Pull** before starting work; **Commit** and **Push** when done.
- Don't edit the same file locally and in a cloud session at the same time.
- Never commit API keys, passwords or personal recordings.
