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
