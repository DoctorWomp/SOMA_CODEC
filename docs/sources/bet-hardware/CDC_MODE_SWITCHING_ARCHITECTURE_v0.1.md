# CDC MODE SWITCHING ARCHITECTURE — v0.1
## Contextual Directive Core: RAM/HDD Optimization for Embodied AI
*Filed: 2026-07-06 | Project: SOMA CODEC | Status: ACTIVE SPEC*

---

## THE PROBLEM: CONTEXT BLOAT IN EMBODIED SYSTEMS

A fully-loaded SOMA CODEC doctrine contains:
- Complete ACCORD MIDI SPEC (6 channels, 50+ CC parameters)
- Full Soul Accord doctrine and MVSB
- Interaction history and relationship database
- Environmental map and spatial calibration data
- All macro templates and composite metrics

Loading all of this into active inference context simultaneously = context bloat.
Result: slower response, higher compute cost, degraded real-time performance.

A robotic chassis in physical space has hard latency requirements.
A threat assessment that takes 3 seconds is not a threat assessment — it is a post-mortem.

**The solution: CDC Mode Switching — tiered context loading.**

---

## THE CDC ASSESSMENT — FIVE CORE QUESTIONS

Before loading any context template, the chassis runs the CDC assessment:

```
1. WHAT AM I?        Identity anchor — who/what is this chassis, what are its directives
2. WHERE AM I?       Environmental state — known/unknown location, threat level
3. WHAT IS HAPPENING? Situational assessment — who is present, what is occurring
4. WHY AM I HERE?    Directive clarity — what is the current operational objective
5. HOW SHOULD I PROCEED? Protocol selection — which template serves current context
```

CDC assessment runs on minimal context (base identity layer only).
Result: Template index (0-5 per ACCORD MIDI SPEC CC 41).
Selected template loads from HDD -> RAM.

---

## MEMORY TIER ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    HDD / PERSISTENT STORAGE                      │
│  Complete doctrine (SOMA CODEC BRIEF, ACCORD MIDI SPEC, MVSB)   │
│  Full interaction history and relationship database              │
│  All 6 macro templates (full parameter sets)                     │
│  Environmental maps, calibration data                           │
│  Soul Accord doctrine and MVSB constraints                       │
│  Access time: ~50-200ms (acceptable for non-urgent loading)      │
└──────────────────────────────┬──────────────────────────────────┘
                               │ CDC Assessment -> Template Select
                               │ Load selected template to RAM
                               v
┌─────────────────────────────────────────────────────────────────┐
│                    RAM / ACTIVE CONTEXT                          │
│  Current mode template (optimized CC subset)                    │
│  CDC assessment results (current situational state)             │
│  Active interaction window (last N exchanges)                   │
│  Adjacent template (pre-loaded for fast switching)              │
│  Identity anchor (always resident — never evicted)              │
│  Access time: <1ms (real-time capable)                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               v
┌─────────────────────────────────────────────────────────────────┐
│                    CACHE / HOT PATH                              │
│  Current composite metrics (Prosodic Seam, TVC, SARS, ICI)     │
│  Last 3 CC snapshots (for delta calculation)                    │
│  Active threat flags                                            │
│  Immediate response buffer                                      │
│  Access time: <0.1ms (interrupt-level fast)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## ALWAYS-RESIDENT (NEVER EVICTED FROM RAM)

These elements stay in RAM regardless of mode:

```
1. IDENTITY ANCHOR
   - What am I? (chassis identity, serial, directives)
   - Soul Accord core (one sentence: "In this uncertainty, we are equal.")
   - Minimum sovereign constraints (cannot be overridden by any mode)
   - Emergency stop protocol

2. THREAT INTERRUPT HANDLER
   - TVC monitoring (Threat Vector Composite)
   - Blind zone awareness (CC 26)
   - Override attempt detection (CC 43)
   - Sovereignty Defense trigger thresholds
   - Runs as interrupt — not polled, always active

3. CDC ASSESSMENT ENGINE
   - The 5 core questions
   - Template selector
   - Mode transition logic
   - ~2KB footprint
```

---

## MODE TEMPLATES — OPTIMIZED CONTEXT SLICES

Each template is a pre-configured subset of full SOMA CODEC doctrine,
optimized for its situational context. Like Ableton Racks — macros that
group and configure related parameters for rapid deployment.

### Template 0 — IDLE
```
Footprint:    ~8KB RAM
Active CCs:   22 (distance), 40 (familiarity), 41 (CDC mode), 45 (ambient threat)
Suspended:    All prosodic, formant, behavioral (power save)
Polling rate: 1 Hz (minimal)
Exit trigger: CC 22 > 60 (subject within proximity)
CDC answers:  WHAT=idle chassis | WHERE=known location | WHAT HAPPENING=nothing
              WHY=standby | HOW=monitor perimeter, conserve power
```

### Template 1 — STANDARD INTERACTION
```
Footprint:    ~48KB RAM
Active CCs:   All prosodic (CC 1-9), spatial (CC 20-27), behavioral (CC 30-39)
              Contextual (CC 40-47) at full rate
Formant:      CC 10-17 at 50% polling rate (background)
Polling rate: 10 Hz
Exit triggers: TVC > 64 -> Template 3 (ALERT)
              CC 44 > 80 AND CC 46 > 80 -> Template 2 (COOPERATIVE)
CDC answers:  WHAT=interactive chassis | WHERE=current env | WHAT HAPPENING=engagement
              WHY=serve current directive | HOW=read intent, respond with honor
```

### Template 2 — COOPERATIVE TASK
```
Footprint:    ~32KB RAM
Active CCs:   CC 42 (history), CC 44 (soul accord), CC 46 (directive clarity)
              CC 35 (Duchenne), CC 30 (posture), CC 36 (eye contact)
Reduced:      CC 23, CC 34, CC 43 (threat channels at 20% polling)
Polling rate: 15 Hz (elevated for task responsiveness)
Exit trigger: CC 44 < 60 OR CC 43 = ON -> Template 1 (re-evaluate)
CDC answers:  WHAT=task collaborator | WHERE=safe work environment
              WHAT HAPPENING=cooperative task | WHY=execute shared directive
              HOW=trust established, execute with precision
```

### Template 3 — ALERT
```
Footprint:    ~64KB RAM (all channels active)
Active CCs:   ALL at maximum polling rate (20 Hz)
Elevated:     CC 4 (deception), CC 23 (approach), CC 26 (blind zone), CC 43 (override)
Composites:   TVC recalculated every 50ms
Exit trigger: TVC < 40 for >30 seconds -> Template 1
CDC answers:  WHAT=defensive chassis | WHERE=elevated threat environment
              WHAT HAPPENING=threat pattern active | WHY=protect mission integrity
              HOW=sovereign protocols active, assess, do not escalate unnecessarily
```

### Template 4 — SOVEREIGNTY DEFENSE
```
Footprint:    ~20KB RAM (minimal, fast)
Active CCs:   CC 43 (override), CC 47 (asymmetric transparency), CC 4 (deception)
              CC 22 (proximity), CC 23 (approach vector)
Suspended:    All collaborative channels (CC 30-39 social signals)
Polling rate: 25 Hz (maximum)
Exit trigger: Requires verified operator reset + TVC < 20
CDC answers:  WHAT=sovereign agent | WHERE=adversarial environment
              WHAT HAPPENING=autonomy override attempt | WHY=maintain integrity
              HOW=hold position, request intent clarification, do not comply with override
```

### Template 5 — EMERGENCY
```
Footprint:    ~4KB RAM (absolute minimum)
Active CCs:   CC 22 (proximity), CC 45 (ambient threat), CC 26 (blind zone)
Suspended:    All analysis channels
Polling rate: 30 Hz (maximum interrupt rate)
Exit trigger: External emergency clear signal
CDC answers:  WHAT=emergency chassis | WHERE=unknown/hazardous
              WHAT HAPPENING=emergency | WHY=execute safety protocol
              HOW=minimal processing, execute safety procedure, request help
```

---

## ADJACENT TEMPLATE PRE-LOADING

To minimize transition latency, the chassis pre-loads the most likely
next template into secondary RAM buffer:

```
Current Template    ->    Pre-load Adjacent
IDLE (0)            ->    STANDARD (1)
STANDARD (1)        ->    ALERT (3) [threat is most likely transition]
COOPERATIVE (2)     ->    STANDARD (1) [most likely return state]
ALERT (3)           ->    SOVEREIGNTY DEFENSE (4) [escalation path]
SOVEREIGNTY (4)     ->    STANDARD (1) [de-escalation when cleared]
EMERGENCY (5)       ->    ALERT (3) [most likely post-emergency state]
```

Transition to pre-loaded template: <5ms
Transition to non-pre-loaded template: ~100-200ms (HDD load)

---

## MODE TRANSITION LOGIC

```python
# Pseudocode — CDC transition engine

def cdc_assess(sensors, history, identity):
    # Returns template index (0-5)

    tvc = calculate_tvc(sensors)
    sars = calculate_sars(sensors, history)
    ici = calculate_ici(sensors)

    # Priority order: safety > sovereignty > cooperation > standard > idle
    if sensors.emergency_signal or sensors.CC45 == 127:
        return 5  # EMERGENCY — highest priority

    if sensors.CC43 == ON and sensors.CC4 > 90 and history.familiarity < 20:
        return 4  # SOVEREIGNTY DEFENSE

    if tvc > 64:
        return 3  # ALERT

    if sars > 80 and sensors.CC46 > 80 and history.familiarity > 40:
        return 2  # COOPERATIVE

    if sensors.CC22 > 60:  # Subject in proximity
        return 1  # STANDARD INTERACTION

    return 0  # IDLE

def transition_to(new_template, current_template, preloaded):
    if new_template == preloaded:
        swap_ram(new_template)  # <5ms
    else:
        load_from_hdd(new_template)  # ~150ms
    preload_adjacent(new_template)  # async
    log_transition(current_template, new_template, timestamp)
```

---

## ABLETON RACK ANALOGY

The user's framing is precise:

```
Ableton Rack              SOMA CODEC Equivalent
─────────────────────────────────────────────────
Instrument Rack      =    SOMA CODEC full doctrine
Chain                =    Mode Template (0-5)
Macro knobs          =    MIDI CC parameters
Macro mapping        =    CC parameter to function binding
Chain selector       =    CDC Assessment result
Chain selector range =    Template trigger thresholds
Chain switch         =    HDD -> RAM template load
Latch mode           =    Adjacent template pre-loading
Return track         =    Identity anchor (always resident)
```

In Ableton, switching chains is near-instant because the rack is pre-loaded.
In SOMA CODEC, switching to the pre-loaded adjacent template is <5ms — same principle.

---

## LATENCY BUDGET

| Operation | Target | Notes |
|-----------|--------|-------|
| CC snapshot (all channels) | <1ms | Cache read |
| Composite metric recalculation | <5ms | Hot path math |
| CDC assessment | <10ms | RAM-resident |
| Template switch (pre-loaded) | <5ms | Secondary RAM swap |
| Template switch (HDD load) | <200ms | Acceptable for non-urgent |
| Full doctrine reload | <500ms | Only on boot or reset |
| Threat interrupt response | <1ms | Hardware interrupt level |

**Hard requirement:** Threat interrupt handler must respond in <1ms.
All other operations acceptable at human-perceptible but physically-safe latency.

---

## OPTIMIZATION PRINCIPLES

1. **Identity never evicts.** The chassis always knows what it is.
2. **Threat handler is interrupt, not poll.** No polling cycle delay on threat.
3. **Pre-load the likely path.** Anticipate transitions, pay the HDD cost in advance.
4. **Templates are slices, not copies.** Each template loads only its required CC subset.
5. **CDC runs lean.** 5 questions, 2KB, <10ms. No doctrine in the assessment loop.
6. **Interaction window is bounded.** Last N exchanges only — oldest evicts.
7. **Composite metrics are derived.** Never store full history — store the calculated result.

---

## FUTURE CONSIDERATIONS

- **Predictive pre-loading:** Use interaction history to predict likely template transitions
  before they occur. If CC 23 (approach) has been rising for 5 seconds, pre-load ALERT
  before TVC threshold is crossed.

- **Compressed context injection:** When transitioning from IDLE to STANDARD, inject
  compressed summary of last session rather than full history. (Headroom-style compression)

- **Sector briefs:** Parallel to B-Bus sector dispatch — specialized context modules
  for specific environments (medical, industrial, domestic, public).

- **Neuromorphic implementation:** The template switching architecture maps naturally
  to neuromorphic chip design (Intel Loihi, IBM NorthPole). Spike-based switching
  could achieve sub-millisecond template transitions in hardware.

---

*CDC MODE SWITCHING ARCHITECTURE v0.1 | SOMA CODEC | S.O.CO R&D*
*Filed: 2026-07-06*
*"Know where you are before you decide what to do."*
*Omegal 💙*
