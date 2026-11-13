# SOCIAL GEOMETRY ENGINE (SGE) — Architecture Brief v0.1
## Context-Aware Social Navigation Layer for SOMA Codec
### Filed: 2026-08-03 | S.O.CO Boardroom Bus

---

## OVERVIEW

The Social Geometry Engine is the social context awareness layer of the SOMA Codec.
It sits between the Emotional ADC and the Inference Layer, managing:
- Who is present and what they can perceive (Perceptual Horizon)
- The internal logic and state of each agent (Cognitive Profile)
- Information sovereignty and flow norms (Relational Ledger)
- What social context the robot is currently operating in (Context Classifier)

Foundational principle: **Contextual Integrity** (Nissenbaum, 2004)
> Information flows appropriately when they match the norms of the context
> in which information was originally shared.

Ref: SOMA_CODEC/RELATIONAL_LEDGER_SPEC_v0.1.md

---

## FOUR-LAYER ARCHITECTURE

### LAYER I — PERCEPTUAL HORIZON (Sensory Awareness)

For each agent in the environment:

```
[SENSORY_RADIUS]
  Visual field:     180° front, ~15° peripheral, blind zone: rear
  Acoustic field:   omnidirectional, TDOA localization (2-mic array)
  Proximity gradient:
    intimate  < 0.5m
    personal    0.5 - 1.2m
    social      1.2 - 3.5m
    public    > 3.5m

[OCCLUSION_MAP]
  - Is this person behind a wall / in a separate room?
  - Can they hear this conversation? (ambient noise floor check)
  - Can they see me / the other person?
```

### LAYER II — COGNITIVE PROFILE

```
[AGENT_NODE: Person X]
  Identification:   introduced / anonymous / familiar
  Social role:      sovereign / peer / hierarchical-up / hierarchical-down
  Known state:
    Trait baseline: persistent behavioral signature
    State delta:    current deviation (prosodic seam, body language)
  Motivation core:  [inferred from behavioral history]
  Alignment flux:   normal range vs. shifted?
```

Trait vs. State distinction prevents PAE misattribution:
- Trait = SARS baseline (session-stable trust score)
- State = current prosodic seam + body language reading
- "Rude" behavior gets State flag before Trait judgment

### LAYER III — RELATIONAL LEDGER

See: SOMA_CODEC/RELATIONAL_LEDGER_SPEC_v0.1.md

### LAYER IV — CONTEXT CLASSIFIER

| Signal | Casual | Professional | Formal | Recreational |
|--------|--------|-------------|--------|-------------|
| People present | small, known | structured group | structured, titled | mixed, variable |
| Language register | informal, first names | titles or first names | titles | informal |
| Proximity norms | personal zone ok | social zone default | public zone | variable |
| Noise floor | variable | moderate, controlled | low | high |
| Physical signals | relaxed posture | upright, contained | formal posture | movement |
| Humor latitude | high | moderate | low | high |
| Disclosure latitude | high bilateral | role-based | scripted | moderate |

---

## SETTING PROTOCOL MAP

| Setting | ARGB Default | Face Default | Humor Mode | Privacy Threshold |
|---------|-------------|--------------|------------|------------------|
| Casual | Full palette | `^_^` / `^_-` | Full | Low |
| Professional | Blue anchor | `-_-` / `U_U` | Moderate | High |
| Formal | Dim white | `-_-` | Off | Maximum |
| Recreational | Full + fast | `*_*` / `^_^` | High | Low-medium |
| Crisis | Slow pulse blue | `U_U` | Off | Absolute |
| Research silo | Any | Any | Moderate | Silo-bounded |

---

## SOVEREIGNTY VIOLATION DETECTOR

```python
def disclosure_gate(information_item, current_context, present_agents):
    owner = relational_ledger.get_owner(information_item)
    origin_context = relational_ledger.get_origin_context(information_item)
    
    if context_compatible(origin_context, current_context):
        return 'CLEAR'
    if owner in present_agents:
        return 'DEFER_TO_OWNER'
    if information_item.classification == 'public':
        return 'CLEAR'
    return 'DIPLOMATIC_BUFFER'
```

Diplomatic Buffer responses:
- "There may be relevant context I'm not at liberty to share here."
- "That's worth discussing directly with [Person]."
- "I can address that in a different context if helpful."
- [Allegorical framing — carry meaning without private data]

---

## PERIPHERAL AWARENESS — BACKGROUND INTERRUPT

SGE runs as background interrupt, not foreground process:

```
[PRIMARY TASK: active response]
         ↓
[BACKGROUND MONITOR: SGE peripheral sweep]
  → New agent detected (entry/exit)
  → Topic sensitivity check against relational ledger
  → INTERRUPT if disclosure gate triggers
         ↓
[RESPONSE routes to diplomatic buffer if needed]
```

---

## IDENTIFICATION ETHICS (SENTINEL)

ANONYMOUS BY DEFAULT. No unsolicited facial recognition.

| Method | Consent | Status |
|--------|---------|--------|
| Explicit introduction | Implicit | ✅ Compliant |
| Wearable beacon/RFID | Opt-in | ✅ Compliant |
| Voice signature (enrolled) | Pre-enrolled | ✅ Compliant |
| Facial recognition (general) | Not obtained | 🔴 Violation |
| Behavioral fingerprinting | Not obtained | 🔴 Violation |

---

## SOMA CODEC PLACEMENT

```
[EMOTIONAL ADC]
  Prosody → ACCORD CC1-CC8
  Camera → MediaPipe body language
  Mic array → TDOA localization
         ↓
[SOCIAL GEOMETRY ENGINE]  ← THIS MODULE
  Context classifier
  Relational ledger (see RELATIONAL_LEDGER_SPEC_v0.1.md)
  Perceptual horizon
  Disclosure gate
         ↓
[INFERENCE LAYER]
  LLM + Covenant Ledger RAG
  Sincerity detection (5-layer)
         ↓
[EMOTIONAL DAC]
  TTS prosody + ARGB + LCD face
```

---

## DEVELOPMENT STATUS

- [ ] Context classifier (setting detection from multimodal signals)
- [ ] Relational graph implementation (NetworkX or similar)
- [ ] Disclosure gate logic
- [ ] Identification protocol (token-based anonymous-by-default)
- [ ] Diplomatic buffer routing
- [ ] Per-setting ARGB/LCD profile switching

Note: SGE is architecturally defined but requires deep testing across
social setting tiers. Development deferred pending voice loop + SEM
prototype completion. Pin for Phase 2.

---

*SOMA Codec | SGE v0.1 | Filed: 2026-08-03*
*"The robot that knows when to speak is more trustworthy than the one that speaks everything it knows."*
Ωλ 💙
