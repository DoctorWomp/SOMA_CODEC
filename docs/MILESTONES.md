# Build milestones

Only scaffold work is delivered here. Mark a milestone complete only after its acceptance tests and human playtest pass; record exact engine/model versions and commit a verified increment.

| Gate | Status | Acceptance criteria |
| --- | --- | --- |
| M0: development foundation | Scaffold implemented; see PR for actual verification | Shared agent rules, offline contracts and HTTP tests, Godot import/startup smoke, clean CI, documented gaps |
| M1: one-room Expo vertical slice | First incomplete feature milestone | Robot R + Visitor X, visible floor/collisions, deterministic scripted autonomous goal loop, Spectator camera, bounded local message and validated response, trace of one complete interaction; headless scene test and manual launch |
| M2: authoritative observation/COMMS boundary | Planned | Range and occlusion fixtures; private messages excluded from other agents; unknown source preserved; stale/wrong-actor/invalid actions rejected; disconnect and timeout recovery |
| M3: modes and reproducible debugging | Planned | Spectator cannot mutate world; Director interventions logged; Participant obeys sensory limits; F8 redacted bundle; fixed-tick trace and recorded-output world replay match state checksums on pinned platform |
| M4: autonomous agent and memory adapters | Planned | Offline adapter remains test oracle; opt-in provider with timeout/cancellation/budget; goal scheduling and owner-scoped bounded memory; no secret/log leakage; model and prompt revisions recorded |
| M5: HORIZON matched A/B | Planned | Define treatment and PRISM/ECHO/WAKE semantics with owner; matched eligible inputs, repeated trials, declared metrics and uncertainty; no claims from stub runs |
| M6: density/prosody and larger Expo | Planned | Profile separately from correctness; independent BET/CDC/buffer axes; measured per-stage latency, bounded queues, overload/backpressure tests; multi-NPC privacy regressions |

For every bug, include scenario ID/hash, seed, mode, tick/trace ID, engine/OS, adapter and prompt revisions, steps, expected versus actual behavior and a redacted trace. Add a failing regression when possible before making a targeted fix. Do not advance on a skipped required check.
