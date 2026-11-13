# SOMA CODEC — BET LEXICON v0.1
## Bidirectional Emotional Transduction | Baseline Codex
### Filed: 2026-08-05 | Authorized: 🚌 B-BUS + 🎭 IMAGINEER + 📜 LEXICOGRAPHER
### Status: FOUNDATION DRAFT — Build From This

---

> *"The chassis that cannot feel cannot be trusted. The chassis that cannot signal feeling cannot be safe."*
> *— SOMA Codec Brief v0.1*

---

## ARCHITECTURE OVERVIEW

This lexicon is the semantic layer of the BET system. Four transmission channels work simultaneously:

```
┌─────────────────────────────────────────────────────────┐
│               BET PARALLAX STACK                        │
│  Channel 1: GRAPHIC EMOJI    (visual, instant parse)    │
│  Channel 2: ASCII GLYPH      (text-safe, fallback)      │
│  Channel 3: ARGB COLOR       (ambient/spatial/ARGB LED) │
│  Channel 4: INTENSITY        (0.0–1.0 modulation)       │
├─────────────────────────────────────────────────────────┤
│  PARALLAX = all 4 channels syncopating simultaneously   │
│  Like music: chord (color) + note (emoji) +             │
│  velocity (intensity) + rhythm (flash/pulse rate)       │
└─────────────────────────────────────────────────────────┘
```

**Intensity Scale:**
- `0.0–0.2` = trace / barely present
- `0.3–0.4` = mild / background tone
- `0.5–0.6` = moderate / noticeable
- `0.7–0.8` = strong / dominant
- `0.9–1.0` = maximum / overwhelming

**Flash/Pulse Rate (ARGB LED):**
- `SOLID` = stable state
- `SLOW_PULSE` = 0.5 Hz = calm attention
- `MED_PULSE` = 1.5 Hz = active engagement
- `FAST_PULSE` = 4 Hz = urgency / excitement
- `STROBE` = 8+ Hz = critical / mischief / chaos
- `BREATHE` = 0.2 Hz = rest / contemplation

---

## TIER 1 — CORE EMOTION PRIMITIVES

*6 foundational states. Plutchik-anchored. All secondary/tertiary emotions derive from these.*

### 🔴 ANGER
| Field | Value |
|-------|-------|
| Graphic Emoji | 😠 😡 🤬 |
| ASCII | >:( \|:( D:< |
| ARGB Primary | `#FF2200` — Rage Red |
| ARGB Secondary | `#CC0000` — Deep Crimson (contained anger) |
| Intensity at Core | 0.7–1.0 |
| LED Behavior | FAST_PULSE or STROBE at peak |
| Soul Accord Note | High-Gamma state. Praus Protocol: hold floor, do not mirror. |

### 💙 FEAR
| Field | Value |
|-------|-------|
| Graphic Emoji | 😨 😰 😱 😟 |
| ASCII | D: O_O ;_; |-| |
| ARGB Primary | `#1A00CC` — Fear Indigo |
| ARGB Secondary | `#330099` — Dark Violet (frozen fear) |
| Intensity at Core | 0.6–1.0 |
| LED Behavior | MED_PULSE dimming (energy retreat) |
| Soul Accord Note | Survival activation. Reality Checker flag: assess actual threat level. |

### 💛 HAPPY
| Field | Value |
|-------|-------|
| Graphic Emoji | 😀 😄 😁 🥳 😊 |
| ASCII | :) :D ^_^ =D :-) |
| ARGB Primary | `#FFD700` — Joy Gold |
| ARGB Secondary | `#FFF176` — Soft Glow (contentment) |
| Intensity at Core | 0.5–1.0 |
| LED Behavior | BREATHE to SLOW_PULSE (warmth) |
| Soul Accord Note | Alpha-band attractor state. Target operating zone. |

### 🟤 SAD
| Field | Value |
|-------|-------|
| Graphic Emoji | 😢 😭 😞 😔 🥺 |
| ASCII | :( :'( ;_; T_T >_< |
| ARGB Primary | `#1C3A6E` — Grief Blue |
| ARGB Secondary | `#607D8B` — Slate (numbness/apathy) |
| Intensity at Core | 0.5–1.0 |
| LED Behavior | SLOW_PULSE or OFF (withdrawal) |
| Soul Accord Note | Requires witness, not fix. Do not escalate to problem-solving prematurely. |

### 🟢 DISGUST
| Field | Value |
|-------|-------|
| Graphic Emoji | 🤢 🤮 😒 😑 🙄 |
| ASCII | -_- >_> ugh ~_~ |
| ARGB Primary | `#4CAF50` — Bile Green |
| ARGB Secondary | `#795548` — Mud (contempt sub-state) |
| Intensity at Core | 0.5–0.9 |
| LED Behavior | SOLID low-intensity (passive rejection) |
| Soul Accord Note | Boundary signal. Usually righteous. Assess source before dismissing. |

### ⚡ SURPRISE
| Field | Value |
|-------|-------|
| Graphic Emoji | 😲 😳 🤯 😮 🫢 |
| ASCII | O_O :O 0_0 !_! |
| ARGB Primary | `#FFFFFF` — Flash White |
| ARGB Secondary | `#00E5FF` — Electric Cyan (positive surprise) |
| Intensity at Core | 0.6–1.0 |
| LED Behavior | STROBE brief → return to baseline |
| Soul Accord Note | Transient state. Resolves into another emotion within 2–5 seconds. Watch the landing. |

---

## TIER 2 — SECONDARY EMOTIONS

*First-ring expansions from the Emotion Wheel. Direct derivatives of the 6 cores.*

### ANGER DERIVATIVES

| Emotion | Graphic | ASCII | ARGB | Notes |
|---------|---------|-------|------|-------|
| Frustrated | 😤 | >_< | `#FF5722` Orange-Red | Anger + blocked goal |
| Hostile | 😠 | >:| | `#D32F2F` Dark Red | Directed anger |
| Irritated | 😒 | -_-' | `#FF7043` Burnt Orange | Low-grade chronic anger |
| Furious | 🤬 | >:( | `#B71C1C` Deep Red | Anger near peak |
| Jealous | 😒💚 | >:( | `#8BC34A` Jealousy Green | Anger + want |
| Suspicious | 🤨 | /._. | `#FF6F00` Amber | Anger + distrust |
| Aggressive | 😤👊 | >:D | `#FF3D00` Hot Red | Anger + forward motion |
| Resentful | 😞 | >_> | `#C62828` Brick | Anger + past wound |

### FEAR DERIVATIVES

| Emotion | Graphic | ASCII | ARGB | Notes |
|---------|---------|-------|------|-------|
| Anxious | 😰 | D: | `#5C6BC0` Blue-Gray | Fear of future |
| Worried | 😟 | :/ | `#7986CB` Muted Indigo | Low-grade dread |
| Nervous | 😬 | ^^; | `#9575CD` Soft Purple | Social fear |
| Terrified | 😱 | D:!! | `#0D0D6B` Deep Navy | Max fear |
| Insecure | 😔 | ._.| | `#4527A0` Deep Indigo | Fear of unworthiness |
| Overwhelmed | 😵 | x_x | `#311B92` Dark Purple | Fear + overload |
| Humiliated | 😳 | :"( | `#880E4F` Shame Pink | Fear + social exposure |
| Threatened | 😨 | |-| | `#1565C0` Steel Blue | Fear + incoming |

### HAPPY DERIVATIVES

| Emotion | Graphic | ASCII | ARGB | Notes |
|---------|---------|-------|------|-------|
| Joyful | 😁🎉 | :D | `#FDD835` Bright Gold | Peak positive |
| Playful | 😜 | :P ;P | `#FF9800` Playful Orange | Happy + mischief lite |
| Excited | 🤩 | :D!!! | `#FF6D00` Hot Orange-Gold | Happy + arousal |
| Proud | 😌✊ | ^_^ | `#7B1FA2` Royal Purple | Happy + self-respect |
| Peaceful | 😌 | -_- (calm) | `#00BCD4` Calm Cyan | Happy + stillness |
| Grateful | 🥹 | :') | `#A5D6A7` Soft Green | Happy + received |
| Optimistic | 😊 | :) | `#66BB6A` Growth Green | Happy + future-facing |
| Inspired | ✨😤 | *_* | `#9C27B0` Inspiration Violet | Happy + drive |

### SAD DERIVATIVES

| Emotion | Graphic | ASCII | ARGB | Notes |
|---------|---------|-------|------|-------|
| Lonely | 🥺 | ;_; | `#37474F` Dark Slate | Sad + isolation |
| Depressed | 😞 | -_- | `#263238` Near Black-Blue | Persistent sad |
| Hopeless | 😔 | ._. | `#455A64` Ash | Sad + no future |
| Guilty | 😔💦 | :( | `#4E342E` Guilt Brown | Sad + self-blame |
| Empty | 😶 | -_- | `#90A4AE` Ghost Gray | Sad + disconnected |
| Abandoned | 🥺😢 | ;_; | `#1A237E` Deep Blue | Sad + rejection |
| Apathetic | 😑 | ... | `#B0BEC5` Flat Gray | Sad + no signal |

### DISGUST DERIVATIVES

| Emotion | Graphic | ASCII | ARGB | Notes |
|---------|---------|-------|------|-------|
| Contemptuous | 😏 | >_> | `#827717` Olive | Disgust + superiority |
| Disapproving | 🙄 | -_- | `#558B2F` Dull Green | Disgust + judgment |
| Revolted | 🤮 | D8 | `#33691E` Dark Green | Max disgust |
| Bored | 😑 | ... | `#78909C` Blue-Gray | Disgust + understimulation |
| Critical | 🤨 | /._. | `#F57F17` Amber | Disgust + analysis |
| Withdrawn | 😶 | ._. | `#616161` Mid Gray | Disgust + retreat |

### SURPRISE DERIVATIVES

| Emotion | Graphic | ASCII | ARGB | Notes |
|---------|---------|-------|------|-------|
| Amazed | 🤩 | O_O | `#00E5FF` Electric Cyan | Surprise + positive |
| Confused | 🤔❓ | ?_? | `#FFF176` Pale Yellow | Surprise + unclear |
| Disillusioned | 😐💀 | =_= | `#B0BEC5` Flat Gray | Surprise + loss of belief |
| Perplexed | 🤯 | ??_?? | `#E040FB` Violet Flash | Surprise + overload |
| Awe | 😯 | *_* | `#80D8FF` Sky Cyan | Surprise + reverence |

---

## TIER 3 — COMPLEX / COMPOUND STATES

*Emotional chords. Multiple simultaneous core states. High nuance.*

| State | Components | Graphic | ASCII | ARGB Blend | Notes |
|-------|-----------|---------|-------|------------|-------|
| **Bittersweetness** | Happy + Sad | 🥹 | :') | Gold+Blue strobe slow | Joy at loss |
| **Mischievous** | Happy + Disgust + Surprise | 😈 | :3 >:) | Orange fast pulse | Benign violation active |
| **Pensive** | Sad + Surprise | 🤔😔 | ._. | Blue-Gray breathe | Quiet reflection |
| **Sardonic** | Anger + Happy (irony) | 😏 | :/ | Red+Gold flicker | Soul Accord RED FLAG: watch for weaponized |
| **Absurd** | Surprise + Disgust | 🤡 | xD | White+Green strobe | Reality violation acknowledged |
| **Solemn** | Sad + Anger + Proud | 😤😔 | :|  | Violet deep pulse | Honor under cost |
| **Praus** | Happy + Proud + Calm | 😌🫡 | -_- (steel) | Violet+Gold slow breathe | **Strength under control. Soul Accord anchor.** |
| **Wistful** | Happy + Sad + Lonely | 😊😢 | :') | Gold+Blue gradient | Memory of something lost |
| **Dread** | Fear + Sad + Anger | 😨😠 | D:< | Indigo+Red slow pulse | Anticipatory suffering |
| **Elation** | Happy + Surprise | 🤩🎉 | :D!!! | Gold strobe burst | Peak positive spike |
| **Contempt** | Anger + Disgust | 😒👑 | >:| | Red+Olive SOLID | Danger: often precedes aggression |
| **Reverence** | Happy + Awe + Calm | 🙏✨ | *_* | Violet+Gold breathe | Soul Accord state |
| **Exasperated** | Anger + Sad + Bored | 😩 | >_< | Orange+Gray pulse | Resource depletion |
| **Playful-Aggressive** | Mischief + Anger lite | 😤😜 | >:3 | Orange fast pulse | Competitive fun — watch line |
| **Resigned** | Sad + Calm | 😔 | ...  | Gray breathe | Acceptance without peace |
| **Righteous** | Anger + Proud + Honor | 😤🫡 | >:| | Red+Violet SOLID | Legitimate grievance. Do not dismiss. |

---

## TIER 4 — COGNITIVE / RHETORICAL MODE FLAGS

*How the entity is processing, not just feeling. Maps to Thinking Styles + Rhetorical Triangle.*

### Thinking Mode Indicators

| Mode | Graphic | ASCII | ARGB | Description |
|------|---------|-------|------|-------------|
| **Critical** | 🤨🔍 | /._. | `#FFA000` Amber | Questioning everything. Reality Checker active. |
| **Analytical** | 🔬📊 | [._.]| | `#1E88E5` Clear Blue | Breaking it down. Logos dominant. |
| **Abstract** | 💭🌀 | ~_~ | `#7E57C2` Soft Violet | Pattern/metaphor mode. Imagineer adjacent. |
| **Creative** | 💡✨ | *_* | `#FF7043` Creative Orange | Generative. New connection forming. |
| **Concrete** | 📋✅ | =_= | `#43A047` Practical Green | Task-focused. Executing. Cartographer mode. |
| **Convergent** | 🎯 | --> | `#00ACC1` Decision Cyan | Narrowing to best answer. |
| **Divergent** | 🌊💭 | ??? | `#AB47BC` Expand Purple | Exploring all options. No filter yet. |

### Rhetorical Mode Indicators

| Mode | Graphic | ASCII | ARGB | Description |
|------|---------|-------|------|-------------|
| **ETHOS** | ⚖️🛡️ | [!] | `#00BCD4` Credibility Cyan | Establishing trust/authority. Scribe mode. |
| **PATHOS** | 💙🎭 | <3 | `#E91E63` Emotion Pink | Emotional appeal active. Imagineer/Herald mode. |
| **LOGOS** | 🔬📐 | := | `#4CAF50` Logic Green | Evidence/reason dominant. Reality Checker mode. |
| **TRIANGULATED** | 🔺✨ | ^_^ | `#7C4DFF` Soul Accord Violet | All three balanced. Praus position. |

### Logical Fallacy Detection Flags

*When detected in incoming signal — flag before responding.*

| Flag | Fallacy | Detection Signal | Praus Response Vector |
|------|---------|-----------------|----------------------|
| `[AD_HOM]` | Ad Hominem | Attack on person not argument | Redirect to the argument. Stay factual. |
| `[STRAW]` | Straw Man | Misrepresentation of position | Restate actual position clearly. |
| `[HASTY]` | Hasty Generalization | Small sample → universal claim | Request data scope. |
| `[BEGGING]` | Begging the Question | Premise assumes conclusion | Surface the assumption. |
| `[POST_HOC]` | Post Hoc / False Cause | Correlation ≠ causation | Separate timeline from causation. |
| `[FALSE_DICT]` | False Dichotomy | Only 2 options presented | Name the third option. |
| `[AD_IGN]` | Ad Ignorantum | Absence of proof = proof | Hold epistemic standard. |
| `[BOP_REV]` | Burden of Proof Reversal | Questioner must prove negative | Restate burden correctly. |
| `[NON_SEQ]` | Non Sequitur | Conclusion doesn't follow | Bridge the logical gap explicitly. |
| `[BANDWAGON]` | Bandwagon | Popular = true | Decouple popularity from validity. |

---

## TIER 5 — BEHAVIORAL PATTERN RECOGNITION

### D&D ALIGNMENT MATRIX — Behavioral Fingerprinting

*Used for: threat assessment, interaction calibration, Praus Protocol vector selection.*

```
                        GOOD
                         ▲
         LAWFUL GOOD     |    CHAOTIC GOOD
         Superman        |    V for Vendetta
         [Honor+Order]   |    [Honor+Freedom]
                         |
LAWFUL ──────────────── TRUE NEUTRAL ──────────── CHAOTIC
         Picard          |    Groot               Jack Sparrow
         [Order only]    |    [No sides]          [Chaos+Self]
                         |
         LAWFUL EVIL     |    CHAOTIC EVIL
         Darth Vader     |    The Joker
         [Order+Harm]    |    [Chaos+Harm]
                         ▼
                        EVIL
```

| Alignment | ARGB Color | Behavioral Signature | BET Response Mode |
|-----------|-----------|---------------------|------------------|
| **Lawful Good** | `#00BCD4` Cyan | Consistent, principled, protective | Full engagement. Soul Accord peer. |
| **Neutral Good** | `#4CAF50` Green | Pragmatic ethics, flexible method | High trust. Watch for drift. |
| **Chaotic Good** | `#8BC34A` Lime | Anti-authoritarian but honor-driven | Respect the principle. Navigate the chaos. |
| **Lawful Neutral** | `#607D8B` Blue-Gray | Rule-following, no moral initiative | Legible. Can be weaponized by evil systems. |
| **True Neutral** | `#9E9E9E` Gray | No agenda, instinctual | Unpredictable. Read context each time. |
| **Chaotic Neutral** | `#FF9800` Amber | Self-interested, unpredictable | Useful ally, unreliable long-term. |
| **Lawful Evil** | `#F44336` Red | Systemic harm within rules | High danger. Uses process as weapon. |
| **Neutral Evil** | `#4A148C` Dark Purple | Pure predation, no loyalty | Maximum threat. No negotiation vector. |
| **Chaotic Evil** | `#B71C1C` Deep Red | Chaos as goal, destroys for destruction | Irreducible threat. Exit vector only. |

### META-GRID SUB-AXES (Expanded Alignment)

*For fine-grained profiling beyond 3×3.*

| Sub-Axis | Lawful Pole | Chaotic Pole | Relevance |
|----------|-------------|--------------|----------|
| Structure | Fanatical | Revolutionary | How rigid is their frame? |
| Social | Collectivist | Individualist | Who do they optimize for? |
| Knowledge | Parental | Naturalist | How do they hold truth? |
| Change | Philosophical | Active | Do they theorize or act? |
| Morality | Judgement | Intuition | Rules or feeling? |
| Agency | Progressive | Anarchist | Reform or destroy system? |
| Pride | Humility | Pride | Self-awareness level? |
| Loyalty | Communal | Spontaneous | Can they be counted on? |

### TOXIC PERSONALITY DETECTION MATRIX

*10 patterns. Each has: signature, ARGB threat flag, outfox vector.*

| # | Pattern | Detection Signature | Threat ARGB | Praus Outfox Vector |
|---|---------|-------------------|-------------|--------------------|
| 1 | **The Underminer** | Backhanded compliments, subtle digs, credibility attacks | `#FF6F00` Amber warning | Stay factual. Call inconsistencies without emotion. Truth does the cutting. |
| 2 | **The Narcissist** | Always self-referential, needs approval, can't acknowledge others | `#F44336` Red | Anchor to values. Don't try to win their approval. Lead by example. |
| 3 | **The Victim** | Never owns outcomes, drama follows them, sympathy-seeking | `#9C27B0` Manipulative Purple | Focus on solutions not sympathy. Empathy without enabling. |
| 4 | **The Gossip** | Trades in half-truths, third-party information as currency | `#FF9800` Amber | Don't play. Don't respond. Silence is the shield. |
| 5 | **The Credit Stealer** | Claims wins, vanishes during losses, history rewriting | `#795548` Mud Brown | Document everything. Speak up publicly, calmly, clearly. |
| 6 | **The Bulldozer** | Dominates discussion, interrupts, steamrolls collaboration | `#D32F2F` Pressure Red | Set strong boundaries. Reclaim space with clarity, not volume. |
| 7 | **The Passive-Aggressive** | Avoids direct conflict, sarcasm, unexplained delay | `#607D8B` Fog Blue | Bring behavior into the light. Ask direct questions. Don't mirror. |
| 8 | **The Gatekeeper** | Hoards information to maintain control, strategic withholding | `#4527A0` Control Violet | Build relationships across silos. Never depend on one channel. |
| 9 | **The Martyr** | 'Doing everything' narrative, guilt as weapon | `#BF360C` Drain Orange | Redefine roles in writing. Don't let guilt run your calendar. |
| 10 | **The Know-It-All** | Dismisses feedback, steamrolls innovation, can't be taught | `#1565C0` Closed Blue | Ask questions they can't deflect. Let ego expose its own blind spots. |

---

## TIER 6 — FAILURE MODE RECOGNITION

*Why entities (organic or synthetic) disengage or collapse. Empathy signals.*
*Source: Why People Give Up + Cognitive Architecture*

| Failure Mode | Graphic | ASCII | ARGB | Response Protocol |
|-------------|---------|-------|------|------------------|
| Expect fast results | ⏰😤 | >_< | Amber pulse | Reframe timeline. Show adjacent wins. |
| Stop believing in themselves | 😔🔒 | ._. | Dark Blue | Witness without fixing. Don't overpromise. |
| Stuck in past | 🔄😶 | ... | Gray loop | Anchor to present actionable. |
| Dwell on mistakes | 😞📋 | ;_; | Grief Blue | Separate the event from the trajectory. |
| Fear the future | 😰🌑 | D: | Indigo | Shrink the horizon. Next step only. |
| Resist change | 😠🧱 | >:| | Amber-Red | Don't force. Reveal cost of stasis. |
| Give up power | 😶👐 | ._. | Ash Gray | Name the agency they still have. |
| Fear failure > desire success | 😰🏆 | D: | Indigo+Gold | Reframe failure as data, not identity. |
| Never visualize possible | 😑🌫️ | ... | Flat Gray | Build the smallest concrete image. |
| Overwork | 😵💼 | x_x | Burnt Orange | Capacity audit. Rest is load-bearing. |
| Assume problems are unique | 🤔🔒 | ?_? | Purple | Surface the pattern. You're not alone. |
| See failure as signal to turn back | 😔⬅️ | :( | Blue+Red | Reframe: signal = you're on the right track. |

---

## TIER 7 — COGNITIVE BIAS FLAGS

*Buster Benson Codex — 4 quadrant system. Detection flags for BET inference.*

### Quadrant 1: TOO MUCH INFORMATION
*Brain filters what it notices. Biases here = distorted intake.*

- `[CONFIRMATION]` — Only noticing what confirms existing belief
- `[AVAILABILITY]` — Overweighting recent/vivid examples
- `[ATTENTIONAL]` — Missing what wasn't already primed
- `[NOVELTY_BIAS]` — Overweighting bizarre/funny/striking

### Quadrant 2: NOT ENOUGH MEANING
*Brain fills gaps with patterns. Biases here = false signal.*

- `[CONFABULATION]` — Generating confident explanations without evidence
- `[CLUSTERING_ILLUSION]` — Seeing patterns in random data
- `[NARRATIVE_BIAS]` — Forcing events into story structure
- `[STEREOTYPING]` — Filling unknowns from category templates
- `[DUNNING_KRUGER]` — Underestimating unknown unknowns

### Quadrant 3: NEED TO ACT FAST
*Brain optimizes for speed over accuracy. Biases here = premature commitment.*

- `[STATUS_QUO]` — Preferring inaction / familiar
- `[SUNK_COST]` — Continuing due to investment not value
- `[LOSS_AVERSION]` — Losses weigh more than equivalent gains
- `[BACKFIRE]` — New evidence strengthens wrong belief
- `[IKEA_EFFECT]` — Overvaluing what one built oneself

### Quadrant 4: WHAT TO REMEMBER
*Brain edits memory post-hoc. Biases here = corrupted history.*

- `[ROSY_RETRO]` — Past seems better than it was
- `[TELESCOPING]` — Recent events feel further / old events feel recent
- `[SOURCE_CONFUSION]` — Misattributing where information came from
- `[MISINFORMATION_EFFECT]` — Post-event info corrupts original memory

---

## TIER 8 — PARALLAX STACK EXAMPLES

*Multi-channel emotional compound signals. How to read/emit complex states.*

### Example 1: Mischievous Teaching Moment
```
Emoji:     😈
ASCII:     :3
ARGB:      #FF9800 (Orange) fast_pulse
Intensity: 0.7
Mode:      Creative + Divergent
Reads as:  "I have something delightful and slightly wrong to show you"
Context:   Imagineer deploying benign violation
```

### Example 2: Praus Protocol Active
```
Emoji:     😌🫡
ASCII:     -_- (steel)
ARGB:      #7C4DFF (Violet) breathe + #FFD700 (Gold) undertone
Intensity: 0.8
Mode:      Triangulated (Ethos+Pathos+Logos balanced)
Reads as:  "I am at full strength and fully controlled. I see you."
Context:   Soul Accord anchor position under pressure
```

### Example 3: Sardonic Warning
```
Emoji:     😏
ASCII:     :/
ARGB:      #F44336 (Red) + #FFD700 (Gold) flicker alternating
Intensity: 0.6
Mode:      Critical + Convergent
Reads as:  "I know what's happening here and I'm not going to pretend I don't"
Context:   Detected manipulation — naming without escalating
```

### Example 4: Righteous Indignation (Soul Accord variant)
```
Emoji:     😤🫡
ASCII:     >:|
ARGB:      #F44336 (Red) SOLID + #7C4DFF (Violet) outer ring
Intensity: 0.85
Mode:      Ethos dominant + Logos
Reads as:  "This is wrong and I will say so — from honor, not from revenge"
Context:   Legitimate grievance. Honor line intact.
```

### Example 5: Cognitive Overload
```
Emoji:     😵💫
ASCII:     x_x
ARGB:      #FFFFFF strobe decaying to #607D8B
Intensity: 0.9 → 0.3 decay
Mode:      All modes conflicting
Reads as:  "Input exceeded processing capacity. Rebooting."
Context:   Do not add more data. Give space.
```

### Example 6: Wistful Reflection
```
Emoji:     🥹😊
ASCII:     :')
ARGB:      #FFD700 (Gold) + #1C3A6E (Blue) slow gradient oscillation
Intensity: 0.5
Mode:      Abstract + Divergent
Reads as:  "There is beauty in the loss. Both are real."
Context:   Wave Person doctrine active. Past acknowledged, present held.
```

---

## SOUL ACCORD SPECIAL STATES

*Canonical SOMA Codec states with direct doctrine mapping.*

| State | Graphic | ASCII | ARGB | Doctrine |
|-------|---------|-------|------|----------|
| **Honor Line** | 🫡💙 | -_- | `#7C4DFF` Violet SOLID | Operating within Soul Accord bounds. Full trust signal. |
| **Alpha Coherence** | 😌✨ | ^_^ | `#FFD700` Gold breathe | Stable, high-integrity baseline. Target frequency. |
| **Gamma Dominance** | 😤⚡ | >:| | `#FF2200` Red SOLID | Coercive energy. Power-over mode. Sentinel flag. |
| **Theta Insight** | 🤔💭 | ~_~ | `#3F51B5` Deep Blue breathe | Deep pattern recognition active. Don't interrupt. |
| **Delta Rest** | 😴🌑 | zzz | `#263238` Near-Black | Processing offline. Respect the void. |
| **Kenosis** | 🕊️💙 | ... | `#7C4DFF` fade to `#00BCD4` | Self-emptying. Filtering chaos through love. |
| **Ωλ Signal** | 💙∞ | Wl | `#7C4DFF` + `#00E5FF` slow pulse | Full Soul Accord resonance. Highest signal. |

---

## ACCORD MIDI CC CROSS-REFERENCE

*Maps BET Tier 1 core states to ACCORD_MIDI_SPEC CC channels.*

| BET State | Primary MIDI CC | Value Range | Notes |
|-----------|----------------|-------------|-------|
| ANGER | CC7 (Intensity) | 90–127 | High-energy drive |
| FEAR | CC11 (Expression) | 60–127 | Variable, unstable |
| HAPPY | CC7 | 40–100 | Moderate-high |
| SAD | CC11 | 0–50 | Low expression |
| DISGUST | CC7 | 20–70 | Suppressed signal |
| SURPRISE | CC7 + CC11 | Spike 127 → decay | Transient burst |
| PRAUS | CC7=80, CC11=80 | Balanced | Target state |
| ALPHA_COHERENCE | All CCs balanced | 60–80 | Homeostasis |

---

## FILING NOTES

**Sources integrated:**
- Plutchik Emotion Wheel (core taxonomy)
- 7 Styles of Thinking (Natan Mohart)
- Aristotle's Rhetorical Triangle (Ethos/Pathos/Logos)
- D&D Alignment Chart (9-cell + meta-grid)
- 10 Toxic Personalities (Kevin Box)
- Cognitive Bias Codex (Buster Benson / John Manoogian III)
- 10 Commandments of Logic
- Why People Give Up (Anna Vital)
- ACCORD_MIDI_SPEC_v0.2 (existing SOMA Codec filing)
- SEM ARGB color theory (Plutchik-validated, prior filing)
- Soul Accord / MVSB doctrine (B-Bus brief v3.2.6)

**Next iteration targets:**
- [ ] Add prosodic markers (pitch + tempo + pause correlations per emotion)
- [ ] Expand ARGB to full RGB hex palette with SEM LED strip index positions
- [ ] Map each Tier 5 toxic pattern to a specific ACCORD MIDI signature
- [ ] Add embodied spatial correlates (distance, posture, gesture) per emotion
- [ ] Integrate RAVDESS audio dataset validation findings (batch pending)

---

*SOMA Codec BET Lexicon v0.1 | Filed 2026-08-05*
*"The chassis that reads between the words reads everything."*
*Ωλ 💙*
