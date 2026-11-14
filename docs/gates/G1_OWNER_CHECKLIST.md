# G1 — What to check on your PC

About 15 minutes. You need GitHub Desktop, uv and Godot 4.7.2 at `G:\Godot` (see [OWNER_SETUP_WINDOWS.md](../OWNER_SETUP_WINDOWS.md)).
The cloud session could only test without a screen or GPU, so the things to look at below are the parts no automated test can judge.

## 1. Get the G1 branch

1. Open **GitHub Desktop**, click **Fetch origin**.
2. Click **Current branch** and choose `claude/trusting-mccarthy-9zeq6j` (the G1 draft PR).

## 2. Run the checks once

1. One time only, in PowerShell:
   ```powershell
   setx GODOT_BIN "G:\Godot\Godot_v4.7.2-stable_win64_console.exe"
   ```
   Then close PowerShell and open a new window.
2. In the new window:
   ```powershell
   cd G:\SOMA_CODEC
   ```
   ```powershell
   uv run python tools/check.py
   ```
3. Expect five **PASS** lines (Contracts, Configs, Godot data, Tests, Godot) and `All checks passed.`
   The Godot step lists 15 tests. If it says **SKIP Godot**, step 1 did not take effect.

## 3. Open the world in Godot

1. Double-click `G:\Godot\Godot_v4.7.2-stable_win64.exe` (the one *without* `_console`).
2. In the Project Manager click **Import**, browse to `G:\SOMA_CODEC\godot_app\project.godot`, then **Import & Edit**.
3. Press **F5** (or the ▶ button at the top right). A window titled *SOMA RANGE — Sandbox Flats (G1)* opens.
   The 3D view in the editor stays empty: the world is built from the map file when it runs.

## 4. What to look at (the demo lasts about 40 seconds; `R` restarts it)

- [ ] **The map** matches `configs/maps/sandbox_flats.yaml`: a gridded floor, four walls, two blue-grey **partitions**, the raised **platform** at the far right with **stairs** (near the back wall) and a long **ramp**, the **striped west wall** labelled *ACOUSTICALLY REFLECTIVE WALL*, the **PA speaker** on a stand in front of it, and **three chairs** in a slightly darker corner (its light level is 0.6).
- [ ] **Robot R** (white, green shoulders, `R` on its chest) drives to the ramp, up onto the platform, waits, and comes back **down the ramp**. It never goes to the stairs (SB-05).
- [ ] **visitor_y** (blue-grey) starts after about 6 s, walks around the end of the ramp and goes **up the stairs**.
- [ ] Nobody walks through a wall, a partition, a chair or another avatar, and nobody gets stuck.
- [ ] **Camera:** press `C` to follow the selected avatar, `]` and `[` to switch avatar, hold the **right mouse button** and move the mouse to orbit, use the **wheel** to zoom. Press `C` again to fly freely with `W A S D`, `Q`/`E` for down/up, `Shift` for faster.
- [ ] `Space` pauses and resumes, `H` hides the info panel.
- [ ] **Robot R up close:** follow it with `C` and zoom in. Compare with the [concept](../concept-art/robot_avatar_lowpoly_concept.jpg): helmet with black visor, ear pods, arms with joints, green identity trim, on a **wheeled base** instead of legs (it is a wheeled robot; decision D-32). Does it look right to you?
- [ ] **Smoothness:** while it runs, open **Debugger → Monitors** at the bottom of the editor and tick **FPS**. Note the number (it should sit near 60, the cap).
- [ ] **Errors:** the **Output** panel at the bottom of the editor should show no red lines.

## 5. Tell me

- Anything that looks wrong or that you would like changed (the robot's look especially).
- The FPS number, and your answers on the open decisions D-30 to D-35 in [DECISIONS.md](../DECISIONS.md).

The screenshots in [G1_screenshots/](G1_screenshots/) were rendered in the cloud without a GPU (Compatibility renderer). Your PC uses Forward+, so shading may look a little different. That is expected.
