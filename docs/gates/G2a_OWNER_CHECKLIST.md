# G2a — What to check on your PC

About 15 minutes. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` is already set from G1).
The cloud tests prove the rules; these steps are for what only a person can judge: does it look right, and does it feel right.

## 1. Get the branch and run the checks

1. GitHub Desktop → **Fetch origin** → **Current branch** → `claude/trusting-mccarthy-9zeq6j`.
2. In PowerShell:
   ```powershell
   cd G:\SOMA_CODEC
   ```
   ```powershell
   uv run python tools/check.py
   ```
3. Expect five **PASS** lines, `30 Godot tests passed`, and a line saying the journal lines and observation packets from Godot match the contracts.

## 2. If Windows Firewall asks about Godot or Python

G2a opens no network connections. Godot's editor talks to the running game on your own computer only (127.0.0.1), and from G2b the Python link will too; Windows Firewall does not block that kind of traffic.

- If a **Windows Security / Windows Defender Firewall** window asks whether to allow *Godot* or *Python*: tick **Private networks** only (untick Public) and click **Allow access**, or simply click **Cancel**. Either is safe; nothing in RANGE needs to reach the internet or other computers.
- Never allow it on **Public networks**.
- If something later says it cannot connect, tell me what it said; do not turn the firewall off.

## 3. Watch the senses

1. Open the project in Godot (`G:\Godot\Godot_v4.7.2-stable_win64.exe`) and press **F5**.
2. Press `]` until the panel says `Selected: robot_legged`, then press **F2**.
   - [ ] Thin cyan lines run from its head to the people it sees, each labelled **seen** or **partly seen: …**. When someone it saw goes behind something, the line turns grey and says **lost: …** for up to 3 seconds.
   - [ ] On the platform the robots greet each other: for 3 seconds after each greeting, the panel line `senses` shows what the selected robot **heard** (for robot_legged, «Hello from up here.» at about 7 s and «And I came up the ramp.» at about 18 s). It does not hear its own words.
3. Select `robot_quadruped` (`]`) and watch its lines: its sensors are low (0.55 m), so the **low divider** (`divider_low`, near the striped wall) and other bodies hide people from it that the humanoids see.
4. The quadruped tries to **wave** on the platform and is refused (it has no arm); it tilts its sensor head instead. Nothing in the world shows the refused wave.
5. [ ] Nobody bumps into anybody: avatars steer around each other.
6. Note the **FPS** and **video memory** (Debugger → Monitors) and any red lines in the Output panel.

## 4. The journal (optional)

Each run writes a journal of everything that happened. In File Explorer, paste this in the address bar and press Enter:

```text
%APPDATA%\Godot\app_userdata\SOMA RANGE\journals
```

Each `.jsonl` file is one run, one line per event (open with Notepad). Only the newest 10 are kept.

## 5. Tell me

What looks or feels wrong, the FPS and video memory numbers, and your answers on decisions **D-39 to D-42** in `docs/DECISIONS.md`. Then G2b (channels, the disclosure gate and the link to Python) can start.
