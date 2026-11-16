# Rig step A — What to check on your PC

About 15 minutes. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` is already set). Nothing is downloaded and **no model is needed**. What was built and why: [D-56](../DECISIONS.md) and [RIG_PLAN.md](RIG_PLAN.md) step A.

## 1. Get the branch and update

1. GitHub Desktop → **Fetch origin** → **Current branch** → `claude/jolly-ramanujan-65cgh6`.
2. In PowerShell:
   ```powershell
   cd G:\SOMA_CODEC
   ```
   ```powershell
   uv sync --locked
   ```

## 2. Run the checks

```powershell
uv run python tools/check.py
```

Expect five **PASS** lines, `53 Godot tests passed`, and a line starting `PASS  scenarios: SB-04 deterministic` that ends with "one with posing off". About 3 minutes. It also proves the journal is byte-for-byte the same with posing on and off.

## 3. Watch every gesture

```powershell
& $env:GODOT_BIN --path godot_app --resolution 1600x900 res://dev/gesture_capture.tscn -- --out=G:\SOMA_CODEC\runs\rig_shots
```

A window opens, plays the 12 gestures one after another (about 40 seconds) and closes. It pauses briefly at each gesture's peak to save a picture into `G:\SOMA_CODEC\runs\rig_shots`.

- [ ] The humanoids raise their **right** hand for WAVE, SMALL_WAVE, RAISED_HAND and BECKON, and reach forward for POINT, OPEN_PALM (hand up) and HAND_OVER (palm up).
- [ ] The quadruped with arm unfolds its arm for WAVE, BECKON, RAISED_HAND (gripper open), POINT and HAND_OVER, then stows it flat again.
- [ ] NOD, SHAKE_HEAD and HEAD_TILT move only the head; BOW bends the upper body; SIT_IN_PLACE tips both quadrupeds back onto folded hind legs, feet staying put.
- [ ] Nothing snaps, jitters or passes through the body. Arms never bend the wrong way.
- [ ] The last picture: every robot turns its head toward the visitor.

Compare with the cloud renders in `docs\gates\RIG_A_screenshots\`. Your PC uses Forward+, so it may look richer. Tell me if a gesture reads wrong (for example, BECKON with the hand held high: that height comes from where the sense model expects a raised hand).

## 4. Watch SB-04 with poses

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --watch
```

- [ ] When Visitor Y waves, Robot R's **head turns toward Y and nods**, while R keeps facing X.
- [ ] When X leaves, R **bows** (upper body bends forward), then turns to Y.
- [ ] Robot R's wheels **roll** when it moves and turns, and stand still when it stops.

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --watch --body robot_r=quadruped
```

- [ ] The quadruped **tilts its sensor head** toward Y instead of nodding.

## 5. Watch the robots walk to the platform (optional)

```powershell
uv run python tools/run_scenario.py SB05_RAMP_VS_STAIRS --watch
```

- [ ] The wheeled robot's wheels roll up the ramp. The legged robot and the quadrupeds still **glide** up the stairs: walking legs are rig step B.

## 6. Frame rate

While a scenario runs, the window should feel as smooth as before. If it stutters where G3a did not, tell me (posing runs every tick for every robot).

## 7. Firewall

Same as before: everything talks only inside your computer (127.0.0.1). If Windows asks about **Python** or **Godot**, tick **Private networks** only, or click **Cancel**. Never allow Public networks.

## What to send back

The last lines of step 2 (or any FAIL), the boxes you could not tick, and any gesture that looks wrong.
