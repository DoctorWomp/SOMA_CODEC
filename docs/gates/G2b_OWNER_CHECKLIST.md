# G2b — What to check on your PC

About 15 minutes. Repository at `G:\SOMA_CODEC`, Godot at `G:\Godot` (`GODOT_BIN` is already set from G1).

## 1. Get the branch and update

1. GitHub Desktop → **Fetch origin** → **Current branch** → `claude/trusting-mccarthy-9zeq6j`.
2. In PowerShell (this installs the one new Python package, `websockets`):
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

Expect five **PASS** lines and `39 Godot tests passed`. This step starts two small Python helper programs for the link tests and stops them again.

## 3. If Windows Firewall asks about Godot or Python

Everything in RANGE talks only to itself on your own computer (127.0.0.1); nothing goes to your network or the internet, and Windows Firewall does not block that.

- If a **Windows Security / Windows Defender Firewall** window asks about **Python** or **Godot**: tick **Private networks** only (untick Public) and click **Allow access**, or simply click **Cancel**. Either is safe, and the checks and the demo work either way.
- Never allow it on **Public networks**, and do not turn the firewall off.
- If something then says it cannot connect, copy what it said and tell me.

## 4. See Godot and Python talk

```powershell
uv run python tools/run_link_demo.py
```

The Godot window opens with the demo (the PowerShell window stays open and prints a summary at the end).

- [ ] The panel at the top left shows `Python link: CONNECTED`.
- [ ] At about 16 seconds, the mauve visitor (`visitor_z`) stands below the platform and waves at the robots. The robots' Python agents answer: robot_legged waves back and both say **«Hello!»**. Select `robot_quadruped` (`]`) and press **F2**: for 3 seconds its panel line shows `heard «Hello!»` (from the other robot).
- [ ] The quadruped tries to wave back too, but it has no arm: the world refuses that (its «Hello!» still goes through).
- [ ] Nothing stutters: the demo runs as smoothly as without Python.
- Close the Godot window. PowerShell then lists what the robots asked for and the answers, for example `robot_quadruped: … -> CAPABILITY_DENIED`.

## 5. What if Python goes away or is slow

You do not need to try this: the checks in step 2 already test it with real Python helpers (one that drops the connection, one that answers slowly, one with a wrong token). The demo keeps running at full speed in each case, and the link reconnects by itself.

## 6. Tell me

What looked wrong or confusing, whether the firewall asked anything, and your answers on decisions **D-43 to D-46** in `docs/DECISIONS.md`.
