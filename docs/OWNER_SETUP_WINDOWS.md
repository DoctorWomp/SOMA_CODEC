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

## GPU memory: other programs and the system-memory fallback (G3g, D-87)

Robot R's server (F3, ~7.6 GB) and the NPC server (N3, ~3.3 GB) share the 16 GB card with Godot and with
whatever else is running. In the G3f run, peak GPU memory was 15.3–15.9 GB of 16.4 GB, about 4.3 GB of it
not the models. When dedicated memory runs out, the Windows driver can quietly move some GPU memory into
system RAM (the "sysmem fallback"); everything that touches it then crosses PCIe and both servers slow down.

**What a run records now.** Every run's `summary.json` has `vram_hygiene`: the GPU memory in use **before
any model server started** (`other_programs_mib`: Windows, the browser, other apps), the memory in use
after the servers started, the card's total, and the free memory left. If that free memory is below the
reserve in `configs/inference.yaml` (`vram.reserve_mib`, 2048 MiB for Godot and headroom), the run prints a
**WARNING** and results.md shows "(below the reserve)" in the VRAM column of the live tables.

**Find what holds GPU memory** (before a bake-off or a watched run):
- [ ] Task Manager (Ctrl+Shift+Esc) → **Performance** → **GPU**: "Dedicated GPU memory" shows the total in use.
  With nothing of RANGE running it should be well under 1 GB.
- [ ] Task Manager → **Details** → right-click a column header → **Select columns** → tick **Dedicated GPU
  memory** (and **Shared GPU memory**) → sort by it. Usual holders: browsers with hardware acceleration
  (Chrome, Edge, Firefox), Discord, Steam and its overlay, video players, OBS, wallpaper or RGB tools,
  the Godot editor, and a `llama-server.exe` left over from an earlier run.
- [ ] Close what you do not need, then check the Performance graph again.
- [ ] `nvidia-smi` in PowerShell lists the processes using the GPU (on Windows their memory shows N/A; the
  list itself is still useful).

**Make llama-server fail loudly instead of spilling into system RAM** (optional; recommended for
measurements):
- [ ] NVIDIA Control Panel → **Manage 3D settings** → **Program Settings** → **Add** → browse to
  `llama-server.exe` (its path: `uv run python tools/install_llama.py --check`; normally
  `G:\SOMA_CODEC\.tools\llama\win-cuda12-b12443\llama-server.exe`).
- [ ] Set **CUDA - Sysmem Fallback Policy** to **Prefer No Sysmem Fallback** and Apply. (The setting needs
  NVIDIA driver 536.40 or newer.)
- With that set, a server that does not fit fails (normally while it starts, when it allocates its memory) instead of running slowly. If the NPC server
  fails, RANGE runs Option B (one server) and records why (`inference.fallback_reason` in the manifest);
  if Robot R's server fails, the run stops with the error. Either way the numbers are never quietly
  inflated by the fallback. Set it back to **Driver Default** if you prefer the old behavior.

## Habits

- Open GitHub Desktop and **Pull** before starting work; **Commit** and **Push** when done.
- Don't edit the same file locally and in a cloud session at the same time.
- Never commit API keys, passwords or personal recordings.
