# G3a — What to check on your PC

About 20 minutes. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` is already set). Nothing is downloaded in this step except Python packages already in the lockfile, and **no model is needed**.

## 1. Get the branch and update

1. GitHub Desktop → **Fetch origin** → **Current branch** → `claude/busy-heisenberg-xfliyo`.
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

Expect five **PASS** lines, `45 Godot tests passed`, and a line starting `PASS  scenarios: SB-04 deterministic`. This takes about 2 minutes: it also runs SB-04 twice and SB-05 once in the background (no window opens).

## 3. Watch SB-04, the polite bid

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --watch
```

A Godot window opens and closes by itself after 90 simulated seconds. Press `H` if the panel is in the way, `]` to select an avatar, `F2` to see what it sees and hears.

- [ ] Visitor X (in front of the robot) asks three questions; Robot R turns to X, its **visor shows `o_o`** with **blue ear pods**, and it answers. For "Does it start soon?" it says it **does not know**.
- [ ] Visitor Y walks up to the side and waves. R does **not** interrupt X: it **nods** toward Y (blue light), and keeps talking with X.
- [ ] X says goodbye and leaves; R bows with a purple light, then **turns to Y**: "Thanks for waiting. How can I help?"
- [ ] Y asks about the café; R says it doesn't know of one and suggests the chairs.
- [ ] Nothing stutters. The world pauses for a split second at each decision ("stepped" mode); that is expected.

The PowerShell window prints a summary and the run folder (under `G:\SOMA_CODEC\runs\`). Inside it, `sidecar\prompts.jsonl` shows exactly what Robot R was shown for each decision.

## 4. Watch SB-05 and a robot body swap

```powershell
uv run python tools/run_scenario.py SB05_RAMP_VS_STAIRS --watch
```

- [ ] The wheeled robot takes the **ramp**; the legged robot and the quadruped take the **stairs**; all three end on the platform. The summary lists the links each used.

```powershell
uv run python tools/run_scenario.py SB04_POLITE_BID --watch --body robot_r=quadruped
```

- [ ] Now Robot R is the quadruped: no visor face. Its **light strip above the camera lenses** shows small symbols (`o o`, `^ ^`) in the Beacon color, and the thin bar under the lenses lights up. It cannot nod, so it tilts its head toward Y instead.

## 5. Look at the Beacon up close (optional)

Open `docs\gates\G3a_screenshots\` to compare with the cloud renders. Your PC uses the better renderer (Forward+), so colors may look richer. Tell me if a glyph is hard to read or hidden by the helmet from the front.

## 6. Firewall

Same as G2b: everything talks only inside your computer (127.0.0.1). If Windows asks about **Python** or **Godot**, tick **Private networks** only, or click **Cancel**. Never allow Public networks.

## 7. Tell me

- What looked wrong or confusing in steps 3–5.
- Your answers on decisions **D-47 to D-53** in `docs\DECISIONS.md` (D-47 is the flaky-test fix).
- One open question (D-51): when NPCs get a model in G3c, may an NPC's **own** private goal go into **its own** prompt (it needs it to act its part), while still never reaching Robot R? Today no private goal goes into any prompt.
- The quadruped-with-arm question in D-36's amendment: allow a gripper wave, beckon and raised-gripper "stop"?
