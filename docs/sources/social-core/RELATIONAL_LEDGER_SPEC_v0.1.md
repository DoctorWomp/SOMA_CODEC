# RELATIONAL LEDGER SPECIFICATION v0.1
## Information Sovereignty Map for SOMA Codec SGE
### Filed: 2026-08-03 | S.O.CO Boardroom Bus

---

## OVERVIEW

The Relational Ledger is the information sovereignty component of the
Social Geometry Engine. It maintains a dynamic graph of agents, their
disclosed information, trust scores, and relationship vectors.

Gemma 4 12B (independent validation):
> "You are building the Social Spectrometer. It allows the AI to see
> the invisible threads of information, secrets, and power that connect
> people."

---

## THREE-BUFFER ARCHITECTURE

```
┌─────────────────────────────────────────────────────┐
│  PUBLIC BUFFER                                       │
│  Information everyone present knows                 │
│  Free to reference in any context                   │
├─────────────────────────────────────────────────────┤
│  SEMI-PUBLIC BUFFER                                  │
│  Information shared with a defined group            │
│  Free within group, restricted across group boundary │
├─────────────────────────────────────────────────────┤
│  PRIVATE VAULTS [per person]                        │
│  What Person X told agent in confidence             │
│  NEVER cross-transferred without explicit consent   │
└─────────────────────────────────────────────────────┘
          ↓
  HIDDEN VECTORS (PAE Zone)
  What Person B believes is true but may be wrong
  → Do NOT correct in public without diplomatic routing
  → Flag internally, route via allegorical buffer
```

---

## DATA SCHEMA

```python
class AgentNode:
    id: str                    # UUID or introduced name
    identification: str        # 'introduced' | 'anonymous' | 'familiar'
    social_role: str           # 'peer' | 'hierarchical_up' | 'hierarchical_down'
    trust_score: float         # 0.0 - 1.0, updated per interaction
    vault: list[InformationItem]  # private disclosures
    known_relationships: dict  # {other_id: RelationshipEdge}
    trait_baseline: dict       # persistent behavioral signature
    state_delta: dict          # current deviation from baseline

class RelationshipEdge:
    agent_a: str
    agent_b: str
    relationship_type: str     # 'friendly' | 'competitive' | 'hierarchical' | 'unknown'
    shared_buffer: list        # topics safe in both agents' presence
    power_delta: float         # -1.0 (A dominant) to +1.0 (B dominant)
    conflict_history: int      # count of flagged interactions

class InformationItem:
    content: str
    owner_id: str
    origin_context: str        # 'casual' | 'professional' | 'formal' | 'private'
    classification: str        # 'public' | 'semi_public' | 'private'
    timestamp: datetime
    recipients: list[str]      # who was present when disclosed
```

---

## INFORMATION ASYMMETRY TYPES

| Type | Description | Handling |
|------|-------------|----------|
| **Type A — Audience-Only** | Agent knows X; Person doesn't | Timing + diplomatic framing |
| **Type B — Character vs Character** | Person A knows secret about Person B | Private vault; never cross-transfer |
| **Type C — Total Obscurity** | Nobody including agent knows truth | Flag as Hidden Vector |
| **Type D — PAE Zone** | Person believes X; X is false | Allegorical correction; avoid direct contradiction in public |

---

## DYNAMIC RELATIONAL GRAPH

Example state after multi-person interaction:

```
Node: Person A
  Trust: 0.87
  Role: peer / introduced / familiar
  Vault: ["stressed about manager", "looking for new job"]
  Relationships: A↔B (friendly), A⊥C (competitive)

Node: Person B
  Trust: 0.71
  Role: hierarchical_down / introduced
  Vault: []

Edge: A → B
  Type: friendly, collaborative
  Shared buffer: [general topics]
  Power delta: 0.0 (neutral)

Edge: A → C
  Type: competitive, low-trust
  Conflict flags: 2
  Power delta: +0.6 (C above A)
  → All A vault data restricted in C's presence
```

---

## DISCLOSURE GATE ALGORITHM

```python
def disclosure_gate(item: InformationItem, context: str, present: list[str]):
    """
    Pre-output sovereignty check.
    Returns: 'CLEAR' | 'DEFER_TO_OWNER' | 'DIPLOMATIC_BUFFER' | 'BLOCK'
    """
    if context_compatible(item.origin_context, context):
        return 'CLEAR'
    
    if item.owner_id in present:
        return 'DEFER_TO_OWNER'  # Let owner choose
    
    if item.classification == 'public':
        return 'CLEAR'
    
    if item.classification == 'private':
        return 'DIPLOMATIC_BUFFER'
    
    # Semi-public: check if all present are in original recipient list
    if all(p in item.recipients for p in present):
        return 'CLEAR'
    
    return 'DIPLOMATIC_BUFFER'
```

---

## TRUST SCORE UPDATE RULES

| Event | Delta |
|-------|-------|
| Sincere disclosure (congruent prosody) | +0.05 |
| Cooperative interaction | +0.02 |
| Congruence mismatch detected | -0.05 |
| Escalation pattern detected | -0.10 |
| Sovereignty violation attempt | -0.20 |
| Explicit consent given | +0.10 |
| Session reset (anonymous) | → 0.50 (neutral baseline) |

---

## IMPLEMENTATION NOTES

- Use NetworkX (Python graph library) for relational graph
- Persist ledger state via JSON (session-scoped) or SQLite (persistent)
- Anonymous by default — no node created until introduction protocol
- Ledger is agent-private — never exposed to external query without consent
- HARVEST DOCTRINE: ledger data must not be exfiltrated to third parties

---

*SOMA Codec | Relational Ledger v0.1 | Filed: 2026-08-03*
*"Sovereignty Cartographer: maps the invisible geometry of who owns what."*
Ωλ 💙
