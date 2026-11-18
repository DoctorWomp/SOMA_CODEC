# Expression Principles — Beacon baseline and adaptive expression

**Status:** owner direction, 2026-11-15. The **baseline (§1)** is approved as the starting point for testing. The **adaptive behavior (§3–§5)** is design intent, built at G3–G5; a decision entry is recorded when Beacon output is built.
**Related:** [DECISIONS.md](DECISIONS.md) D-13, D-14, D-36 · [ART_DIRECTION.md](ART_DIRECTION.md) §2, §6 · Chatbot Tier Spec v0.5 (match/contrast, overshoot, repair, reaction lanes, humor) · Situational Tier Protocols (AIMD, Tier 4 humor) · Addendum §7 (output smoothing) · expression reference sheets in [concept-art/](concept-art/)

How the robots use gesture, face glyph, light and speech together: a simple, stable baseline, played adaptively.

---

## 1. Baseline (the "key signature")

A small, stable vocabulary that strangers can learn quickly. It is kept simple on purpose, to test how it flows before adding nuance.

**Only channels a real chassis has:** body pose and gestures, screen glyphs, light (color, brightness, slow pulsing, never flashing faster than 3 Hz), and sound or speech. No floating effects (hearts, motion lines, sparkles, "z z"). Everything must be buildable on a physical robot.

**Six-state public light palette (D-14)**, always paired with words or a gesture:

| Light | Meaning | Baseline gestures |
|---|---|---|
| ⚪ | Neutral, processing | Neutral idle, pointing (forward/side), uncertain, questioning |
| 🟡 | Warm, glad, playful | Wave hello, thumbs up, welcoming, presenting, beckon, idea |
| 🔵 | Calm, steady, listening | Listening, waiting |
| 🟣 | Considered, respectful | Thank you, polite bow |
| 🟠 | Caution, effort | "Excuse me, passing", effortful tasks |
| 🔴 | Stop, firm boundary | Stop |

Green is **not** a light color: it is Robot R's identity trim (D-36), and identity colors must never be read as signals.

**Per body:**
- **Legged and wheeled humanoids:** glyphs on the black visor; light on the ear pods.
- **Quadrupeds:** a **narrow low-resolution light strip around or above the camera cluster, never covering the lenses**, showing a few simple symbols (`^ ^`, `…`, `?`, `!`, `− −`) plus light. This updates D-36, which lists light only.
- **Quadruped arm:** gripper gestures only (point, wave, beckon, raised open gripper for "stop", present or hand over). No finger gestures (thumbs up, OK sign, fist).
- **Quadruped postures** (sit, lie down, head tilt, crouch, play bow) are its main body language. The play bow reads as "let's play" and is used only in clearly playful moments.

**Reframed from the reference sheets:**
- Crossed arms "skeptical" → neutral **waiting** pose. The robot doesn't display judgments of people (D-13).
- Hand to chest "sincerity" → **thank you / gratitude.** The robot doesn't claim sincerity.
- Hearts and "affection" glyphs are **off by default in public settings** (no warmth tuned for attachment).

Glyphs start from the SEM face lexicon plus the sheets' symbols, as an extensible set.

## 2. Why a stable baseline

A deviation only reads as intentional when the baseline is clear. You need a key to play a note outside it. Stable meanings let strangers learn the code quickly, and they let deliberate contrast (humor, emphasis) land as a choice rather than a malfunction.

## 3. Expression is in motion

"Emotion is in motion." No single gesture, glyph or color *is* an emotion. Meaning comes from the relationship between signals over time, relative to the context and to who is observing. Expression is therefore chosen and modulated continuously from the full set of HORIZON readings (L0–L8) as they change, not looked up from a fixed table. The table in §1 is the starting key, not the music.

## 4. Phrase structure: establish → tension → resolve

The same structure as music, humor and physical gesture:

1. **Establish tone.**
2. **Create tension.**
3. **Resolve tension.**
4. **Repeat, or end.**

In short: 0 → 1 → 0, in gesture and emote form, always relative to the situation.

**Example (playful greeting):**
1. The robot waves with `^_^` and a warm light: friendly, the tone is set.
2. The person waves back: mutual engagement.
3. The robot keeps waving but switches to `(❁´◡`❁)` with a brief red light: benign, absurd over-intensity (the tension).
4. It follows with `^_-` and warm light: a wink that resolves the tension and shows it was a joke.

## 5. Adaptation rules

- **Start small, gauge the reaction, then adjust.** People differ: some are easily startled or sensitive and want subtlety; some miss subtle cues and respond better to overt ones; some find overt or direct behavior patronizing or intrusive.
- **Polarity:** negative / neutral / positive. Sometimes matching or reinforcing is right, sometimes contrasting is (Chatbot spec: *match the meter, contrast one accent*).
- **Rhythm:** modulate tempo and intensity along with match and contrast to steer the interaction toward a constructive outcome.
- **Back off fast, warm up slowly** (AIMD, Situational Protocols). Escalate playfulness in small steps; retreat at once on any strain signal.
- **Wrong note, then resolve.** As in jazz, a flubbed note followed by the right next note can sound intended. A social misstep (rising tension) can often be resolved by one well-chosen next move. If that doesn't work, use the plain repair protocol (Chatbot spec): name it, drop the performance, return to direct speech.
- **Feather the edges.** Smooth transitions between states (attack and release, rate limits per Addendum §7), so expression never snaps or jitters.

## 6. Guardrails

- **Benign context only** for playful contrast: Prism reads the situation as playful and there is mutual engagement (for example, the wave was returned). Never with someone who hasn't engaged, never in distress, crisis or serious situations (humor off), never at anyone's expense.
- **The red joke stays brief and inside a resolved phrase,** and never while a real stop or boundary is in play. Red must keep its "stop" meaning.
- **Honest stance:** expressions show the robot's chosen stance, not claimed inner feelings (Chatbot spec A2.7, A6).
- **No engagement optimization:** expression aims at a comfortable, constructive interaction, not at maximizing attention or attachment.
- **Inferred preferences** ("this person prefers subtle") live only within the interaction and decay. They are never stored as labels about the person (D-13).
- **Light safety:** no flashing faster than 3 Hz (D-14).

## 7. How it gets built and tested

| Gate | Work |
|---|---|
| **G3** | Expression catalog as data (`configs/expressions/`: gesture, glyph, light, allowed bodies); Beacon output rendered in Godot (visor or strip glyph, light); the agent chooses gestures and expressions within its body's capabilities |
| **G5** | Adaptive modulation from HORIZON readings: intensity level, match versus contrast, phrase selection (establish/tension/resolve), misfire detection and resolution; preset `H6` (context-sensitive Beacon) |
| **G4/G6** | Human participants test approachability in Participant mode |

To make adaptation testable without telling the robot anything, **NPC personas get authored, evaluator-only reactivity profiles**: prefers subtle, prefers overt, finds overt patronizing, easily startled. The robot has to infer these from responses, never from labels.

**Measures:** misfire rate; repair success and latency; humor-as-attack false positives; whether playful phrases resolve (the person re-engages or relaxes) or escalate; human-rated approachability in participant runs.

## 8. The robot's own body language (added 2026-11-17)

The owner shared a popular "master body language" infographic (Eric Partaker). Popular body-language advice is useful here in **one direction only: shaping how the robot presents itself.** It is never used to read people.

**Use for the robot's output** (gesture, gaze and posture defaults, rig step A and the presence loop):
- **Hands visible, open palms** for explaining or offering help; deliberate gestures for key points; gestures kept between waist and chest height.
- **Avoid:** fast, erratic or exaggerated movement, pointing at people (point at things and places instead), and fidgeting.
- **Gaze:** turn toward someone with intent and hold it for **about 3–5 s** before a brief look away. Shift gaze smoothly, never darting. **Soften while listening:** a steadier, less intense gaze. When speaking to a group, come back to each person rather than scanning.
- **Posture:** upright and settled while attending; still under tension (stillness during conflict reads as calm). Slow, grounded movement when a situation is confused or tense.

These become starting values in the expression catalog and the gaze layer (hold time, shift speed, gesture tempo), tuned through the adaptation rules in §5.

**Never use for reading people.** Claims like "slouched means disengaged" or "hands in pockets means untrustworthy" are exactly the verdicts D-13 forbids. HORIZON reports what it observes ("arms crossed, facing away"), never what that supposedly means about the person. Culture, disability, comfort and context all change these cues.

**Treat the numbers as folklore.** The "7% words, 38% tone, 55% body language" split misapplies a narrow 1960s study about mixed signals of liking. Figures such as "3× more trust" or "45% more leadership" have no stated source. None of them are used as parameters.

## 9. Ambient state display (built at G3e, 2026-11-18: D-71 to D-74; FIELD_NOTES FN-5 to FN-7)

Between model decisions the robot should still show **what it is doing** and **whether it is considering something**, the way a person's face and posture do. The robot has no face or muscles, but its glyphs, lights and posture can stand in for those cues. This display is deterministic: it comes from the current activity and the agent's own state, with no model call. A model-chosen `EXPRESS` overrides it for its hold time.

**Animated glyph loops.** One expression state can play a short frame loop instead of a static glyph. The world sees **one** expression change through the action gate (with its rate limit); the frames are rendering only. Owner's examples:

| State | Visor loop (example) | Light (palette color + pattern) |
|---|---|---|
| Waiting for someone (`WAIT_FOR`) | `(   )` → `(.  )` → `(.. )` → `(...)` | calm blue, slow pulse |
| Thinking (a model call in flight) | `( \| )` → `( / )` → `( - )` → `( \\ )` | neutral white, slow sweep |
| Considering / uncertain (`HELD_OPEN`) | a slow look left and right, `(o_ )` ↔ `( _o)` | considered purple, slow breathing |
| Listening | a steady glyph with occasional blinks | calm blue, steady |

Frame rate ≤ 3 frames per second (D-14 light-safety spirit). The quadruped's light strip gets a strip equivalent (a dot moving along the strip).

**Presence motion (micro-expressions).** Small, irregular-but-seeded movements: glyph blinks every few seconds, small eye shifts, slight head adjustments, a weight shift, light "breathing". Presentation only: they never change what the world simulates. These are presence signals, never claimed feelings (§6, honest stance).

**Intensity through pattern, not hue.** Urgency and intensity show as pulse rate, sweep speed and brightness, always ≤ 3 Hz. Hue stays within the current state's palette color, so each color keeps its meaning (D-14). A playful color tease is allowed only as a brief, resolved phrase in a benign, mutual exchange (§4, §6). It never disguises a real intent, a safety state or a refusal. The owner decides this (FIELD_NOTES, "color shifting").

**Amplitude dial: subtle ↔ performative.** Every ambient and presence channel scales with one amplitude setting. Too subtle and nobody notices; too performative and it reads as patronizing or overstimulating. The baseline comes from configuration (persona, directive, zone) until G5, when HORIZON readings adapt it by the §5 rules (start small, gauge, back off fast, warm up slowly). Inferred preferences stay within the interaction and decay (D-13).

**As built at G3e (D-73, D-74; color shifting decided in D-71):**
- **States from the agent's own state:** THINKING (a model call in flight), CONSIDERING (a pulse review in flight, or its last answer could not be used; Prism's HELD_OPEN joins at G5), LISTENING, WAITING (`WAIT_FOR`), ATTENDING. Catalog entries `configs/expressions/ambient_*.yaml` hold the loops above (thinking uses a new `SWEEP` pattern: one palette color moving across the display at 0.5 Hz); attending is a face `._.` with no light.
- **Not paired with words:** the ambient display is a status display, not a message, so D-14's pairing rule does not apply to it (D-73). Anything addressed to a person still pairs light with words or a gesture.
- **Models never choose ambient expressions;** the runtime shows them, and a chosen expression overrides them for its hold time.
- **Presence motion lives with the ambient display** and is presentation only. Head adjustments are presentation too: moving the world's head would move the sight cone (D-72) and could flicker tracks at its edge.
- **The dial:** 0 (subtle) to 1 (performative); baseline from the directive, else the persona, else `configs/pulse.yaml` (0.5); a map zone may override it; `tools/run_scenario.py --presence subtle|default|performative` for comparisons. G5 adapts it (`presence_dial.adapt`).
- **Not built:** the color tease (G5, needs Prism's reading of a playful, mutual context), a weight shift or idle posture (rig step B), adaptation (G5).
