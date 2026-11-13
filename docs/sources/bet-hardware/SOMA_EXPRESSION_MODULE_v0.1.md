# SOMA EXPRESSION MODULE (SEM) — Architecture Brief v0.1
## Chassis-Agnostic Emotional I/O Coprocessor
### Filed: 2026-08-03 | S.O.CO Boardroom Bus

---

## OVERVIEW

The SOMA Expression Module (SEM) is a chassis-agnostic hardware/software system
that provides bidirectional emotional transduction for any robotic platform.

Core thesis: **The 55% visual communication channel is the biggest gap in current
robotics human-interface design. SEM fills it at $46–$800 depending on tier.**

The module operates as a dedicated emotional intelligence coprocessor:
- Accepts emotional state commands from the host chassis via USB-C API
- Outputs emotional signals across three parallel channels (ARGB + LCD face + TTS prosody)
- Reads emotional input via camera (MediaPipe) and microphones (prosodic analysis)
- Returns structured emotional inference data to host chassis

---

## COMMUNICATION SPLIT — THEORETICAL BASIS

Mehrabian (1971) communication channel breakdown:
```
7%  — Semantic content (words)
38% — Prosodic content (voice tone, pace, pitch)
55% — Visual/body language
```

Current robotic platforms cover: 7% (TTS words) + 38% (basic TTS voice)
**SEM adds: the remaining 55% visual channel coverage.**

---

## HARDWARE TIERS

### TIER 1 — DIY / Prototype (~$46)
| Component | Spec | Cost |
|-----------|------|------|
| Raspberry Pi Zero 2W | ARM Cortex-A53, 512MB | $15 |
| WS2812B LED ring (12px) | RGB, GPIO-controlled | $6 |
| 2.8" TFT SPI LCD (ILI9341) | 320x240, SPI | $8 |
| USB camera 720p | 30fps, USB | $12 |
| Power + case | — | $5 |

### TIER 2 — Maker / Dev (~$150)
| Component | Spec | Cost |
|-----------|------|------|
| Raspberry Pi 4 (2GB) | ARM Cortex-A72, 2GB | $35 |
| WS2812B LED strip (60px) | Full surround lighting | $18 |
| 5" HDMI LCD | 800x480, touchscreen | $35 |
| 2x USB cameras | Stereo depth estimate | $30 |
| Electret stereo mic array | Sound localization | $20 |
| Case + power | — | $12 |

### TIER 3 — Commercial (~$600)
| Component | Spec | Cost |
|-----------|------|------|
| Mac Mini M4 or equivalent | Dedicated inference | $600 |
| 8–10" IPS LCD panel | 1280x800, sunlight readable | incl. |
| Intel RealSense D435i | Stereo IR depth + RGB | $200 |
| Miniature electret array (4-mic) | Beamforming, localization | $50 |
| Integrated LED array | Configurable surround | $30 |

### TIER 4 — OEM / Enterprise
- Custom PCB form factor
- Hot-swap module design
- Proprietary API licensing
- White-label option for robotics OEMs

---

## INTERFACE SPECIFICATION

### Host Chassis → SEM
Simple REST API over USB-C (or WiFi/Ethernet):
```http
POST /emotional_state
{
  "state": "mischievous",
  "intensity": 0.7,
  "duration_ms": 2000,
  "face": "^_-",
  "cultural_profile": "western"
}
```

### SEM → Host Chassis
```http
GET /perception_report
{
  "human_emotional_state": "curious",
  "confidence": 0.82,
  "posture": "open",
  "proximity_m": 1.2,
  "eye_contact": true,
  "sincerity_score": 0.91,
  "congruence_flag": true,
  "dominant_speaker_angle": 15
}
```

The host chassis does not need to implement ANY emotional processing.
All emotional I/O is handled by SEM. The chassis only needs to:
1. Tell SEM what emotional state to express
2. Receive perception reports about the human it's interacting with

---

## ARGB EMOTIONAL SIGNALING SYSTEM

Based on Plutchik Emotion Wheel (empirical validation — 8/8 color assignments confirmed):

| Color | RGB | Emotional State | Plutchik Mapping |
|-------|-----|-----------------|------------------|
| 🔵 Blue/Cyan | (0, 160, 255) | Anchor/soothing/logical | Trust (pure) |
| 🟠 Orange | (255, 140, 0) | Catalyst/mischievous/boundary-probe | Aggressiveness dyad |
| 🌈 Shifting | variable | Mediator/concealment/diplomatic | Transitional states |
| 💚 Emerald | (0, 200, 80) | Competitive/needy/envy | Trust + cultural envy |
| 🩷 Neon Pink | (255, 0, 180) | Manic/arousal/hyper-stimulated | Ecstasy (max Joy) |
| 🟣 Violet | (180, 0, 255) | Love/honor/social resonance | Love dyad (Joy+Trust) |
| 🟡 Yellow | (255, 220, 0) | Creative/exploratory/cautious | Vigilance/Anticipation |
| 🔴 Red | (255, 0, 0) | Hostile/intense/volatile | Rage (max Anger) |
| ⬛ Dim White | (40, 40, 40) | Neutral/processing | Neutral |

### Intensity Mapping (Plutchik Rings)
```
Brightness 20-40%  = outer ring (serenity, pensiveness, interest)
Brightness 60-80%  = middle ring (joy, sadness, anticipation)
Brightness 100% + pulse = center ring (ecstasy, grief, rage)
```

### Mischievous Mode
```python
# Fast entropy mode — playful concealment
while mischievous_active:
    random_hue = random.choice(ARGB_MAP.values())
    pixels.fill(random_hue)
    time.sleep(random.uniform(0.05, 0.3))  # irregular rhythm
    # Shannon entropy = max → "read me if you can"
```

---

## LCD FACE LEXICON — ASCII/PIXEL EXPRESSION SYSTEM

Based on Jailbot (Superjail) aesthetic precedent — pixel/ASCII faces bypass the
uncanny valley by operating as emotional SYMBOLS rather than failed human replicas.

| Glyph | State | ARGB Pair |
|-------|-------|----------|
| `^_^` | Happy/content | Yellow/Pink |
| `^_-` | Playful/mischievous | Orange/shifting |
| `>_<` | Frustrated/overwhelmed | Red/Orange |
| `@_@` | Confused/overloaded | Shifting/dim |
| `>_>` | Suspicious/skeptical | Orange/dim |
| `T_T` | Sad/distressed | Blue/dim |
| `O_O` | Surprised/alert | Yellow/bright |
| `-_-` | Neutral/flat affect | Dim white |
| `*_*` | Excited/awed | Pink/Yellow |
| `U_U` | Calm/resolved | Blue |
| `~_~` | Uncertain/processing | Shifting slow |
| `X_X` | Error/disoriented | Red flash |
| `♥_♥` | Affection/bonding | Violet |
| `z_z` | Low power/idle | Dim blue |

### Syncopation Protocol
All three channels (ARGB + LCD + TTS prosody) synchronize within 50ms:
```
Emotional state set → ARGB immediate (hardware)
                    → LCD glyph 50ms
                    → TTS prosodic envelope 200-500ms
                    → Human brain integrates as unified signal
```

---

## VISUAL ADC — CAMERA INPUT PIPELINE

### Phase 1: Body Language (MediaPipe Holistic)
```python
import mediapipe as mp

with mp.solutions.holistic.Holistic() as holistic:
    results = holistic.process(frame)
    # pose_landmarks: 33 body keypoints
    # face_landmarks: 468 facial keypoints
    # hand_landmarks: 21 per hand
```

| Signal | Detection | SOMA Inference |
|--------|-----------|----------------|
| Posture angle | Spine keypoints | Engagement/disengagement |
| Arm position | Elbow/wrist | Open/closed (trust/defensive) |
| Gesture plane | Wrist z-height | Truth plane (sincerity marker) |
| Face orientation | Face landmarks | Eye contact proxy |
| Proximity | Face bounding box size | Intimacy gradient |
| Micro-expression rate | Landmark velocity | Emotional latency |

### Phase 2: Stereo Mic — Sound Localization
With 2x electret mics (known spacing d):
```
TDOA (Time Difference of Arrival) → speaker angle
Angle + camera face detection → confirmed speaker identity
Reflection analysis → room environment assessment
Multiple voice tracking → group conversation management
```

---

## SINCERITY DETECTION — 4-LAYER FRAMEWORK

```
Layer 1 — SEMANTIC:   What is said? Topic frequency, claim category, pressure gradient
Layer 2 — PROSODIC:   How does it sound? ACCORD CC1-CC8 values from prosody_extractor.py
Layer 3 — CONGRUENCE: Do L1 + L2 match? Ghost Vision detection in speech
Layer 4 — VISUAL:     Do body language signals match verbal claims? (SEM camera)
Layer 5 — TEMPORAL:   Escalation pattern over session? (escalation_engine.py)
```

Output classification:
| Class | L1+L2 | Pressure | Stakes | Action |
|-------|-------|----------|--------|--------|
| SINCERE | Congruent | Normal | Stable | Trust baseline |
| PERFORMATIVE-BENIGN | Slightly incongruent | Low | No escalation | Safe |
| PERFORMATIVE-MANIPULATIVE | Incongruent | Escalates | Rising | 🟠 Flag |
| EXPLOITATIVE | Highly incongruent | Max | Threat-level | 🔴 Sentinel HOLD |

---

## CULTURAL CALIBRATION LAYER

Color meanings vary significantly by culture (ref: McCandless 'Colours in Culture').
SEM initializes with a cultural profile:

```python
CULTURAL_OVERRIDES = {
    'eastern_asian': {
        'red': 'celebration',    # not danger
        'white': 'mourning',     # not purity
        'green': 'infidelity',   # not safety
    },
    'south_asian': {
        'orange': 'sacred',      # not catalyst
        'white': 'mourning',     # not purity
    },
    'universal': [
        'blue',   # calm/trust — cross-cultural consensus
        'yellow', # joy/energy — broadly positive
    ]
}
```

---

## SOMA CODEC INTEGRATION

SEM is the VISUAL DAC of the SOMA Codec output chain:

```
SOMA CODEC FULL ARCHITECTURE:

[EMOTIONAL ADC]
  Audio → prosody_extractor.py → ACCORD CC1-CC8
  Camera → MediaPipe → body language CC values     ← SEM
  Mic array → TDOA → speaker localization          ← SEM

[INFERENCE LAYER]
  LLM + Covenant Ledger RAG
  Sincerity detection (5-layer)

[EMOTIONAL DAC]
  Channel A: TTS prosody (XTTS2 params → CC01-CC08)
  Channel B: ARGB lighting → hue/saturation/brightness ← SEM
  Channel C: LCD face glyph → symbolic expression     ← SEM
```

---

## COMPETITIVE LANDSCAPE

| Platform | Emotional Output | Cost | Uncanny Valley | Chassis-Agnostic |
|----------|-----------------|------|----------------|------------------|
| SoftBank Pepper | Fixed LED eyes | $1,800 | Mild | ❌ |
| Embodied Moxie | Screen face | $800 | Moderate | ❌ |
| Animatronic systems | Servo face | $2K–$50K | SEVERE | ❌ |
| **SEM Tier 1** | **ARGB + LCD + Cam** | **$46** | **Zero** | **✅** |
| **SEM Tier 3** | **Full multimodal** | **$800** | **Zero** | **✅** |

Key differentiator: **chassis-agnostic**.
SEM can bolt onto any robotic platform via USB-C regardless of onboard compute.

---

## PARTNERSHIP TARGETS

- **Boston Dynamics** — Spot SDK is open; Spot has zero emotional interface
- **Unitree** — Go2/H1 SDK accessible; growing research community
- **Hello Robot** — open-source research community; aligned values
- **Hugging Face LeRobot** — open-source robots; community deployment
- **SBIR/STTR** — human-robot teaming topic area; Phase 1 $200K feasibility

---

## BUILD QUEUE

| # | Task | Time | Unlocks |
|---|------|------|---------|
| 1 | `pip install rpi-ws281x pillow mediapipe opencv-python` | 20 min | Stack installed |
| 2 | `soma_expression_module.py` — ARGB_MAP + FACE_MAP + REST API | 2 hr | Core SEM live |
| 3 | Wire to voice loop — emotional state → SEM | 1 hr | Full multimodal output |
| 4 | MediaPipe camera input → perception report | 2 hr | Visual ADC live |
| 5 | Stereo mic TDOA localization | 3 hr | Sound localization live |
| 6 | Cultural profile parameter | 1 hr | International ready |
| 7 | Mischievous entropy mode | 30 min | Benign violation visual |
| 8 | Tier 2 hardware order | 5 min | Physical dev platform |

---

*SOMA Codec | SEM v0.1 | Filed: 2026-08-03*
*"The emotional communication layer, independent of the chassis."*
Ωλ 💙


---

## SGE INTEGRATION NOTE (Added 2026-08-03)

The SOMA Expression Module interfaces with the Social Geometry Engine (SGE)
for context-aware output calibration:

- SGE Context Classifier → SEM Setting Profile selector
  (Professional mode → blue anchor default, muted expressions)
- SGE Disclosure Gate → SEM output suppression
  (Gate BLOCK → SEM goes to neutral dim white + `-_-` face)
- SGE Agent Entry/Exit → SEM ambient state shift
  (New stranger detected → SEM brightens slightly, face → `O_O` momentarily)

Ref: SOMA_CODEC/SOCIAL_GEOMETRY_ENGINE_v0.1.md
Ref: SOMA_CODEC/RELATIONAL_LEDGER_SPEC_v0.1.md
