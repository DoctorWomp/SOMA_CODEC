# SOMA RANGE — Agent Runtime, Communication & Memory Blueprint v0.2

**Project:** SOMA Codec / SOMA HORIZON ΔP / SOMA RANGE  
**Status:** Speculative engineering addendum for initial Windows executable; not a performance-validated implementation  
**Primary environment:** Single-floor, low-poly robotics expo  
**Design target:** A small active agent cast, background crowd, HORIZON on/off evaluation, spectator/director/participant modes.

> **Core rule:** The game engine owns world truth and physical execution. Each agent owns its subjective, observer-limited context and objectives. The LLM proposes high-level actions. The server validates and executes them. Communication is routed through simulated world channels, not direct cross-agent prompts.

## 1. Architectural goals

1. Run a small set of meaningfully agentic NPCs without one fully loaded LLM per avatar.
2. Keep navigation, collision, actor scheduling and local communication active while LLM inference is pending.
3. Preserve isolated agent knowledge, relationship memory and permissions.
4. Compare HORIZON ΔP to baseline agents with equivalent information and identical action rights.
5. Make interventions, model settings, prompts, memory compaction and event delivery observable and replayable.
6. Keep audio/vision sensor realism modular: start with synthetic observations; later add physical simulations and media models.

**Non-goals v0.2:** full photorealism; actual emotion detection; unbounded LLM-driven animations; realistic building acoustics; all-NPC full-time AI; production-grade multiplayer networking; claims of sim-to-real safety validation.

## 2. Reference stack and ownership

| Layer | Recommended first tool/language | Code-owned responsibility | Alternatives/future |
| --- | --- | --- | --- |
| Expo world and executable GUI | Godot 4, **GDScript** | Maps, scene nodes, navmesh, collision, camera, interaction volumes, HUD, chat display, first/third person avatar controls | Unity/C# if team is C#-oriented; Unreal/C++/Blueprints for later high-fidelity demonstrations |
| World authority, scheduler, experiments | **Python** | Scenario seeds, event queue, agent states, access control, experiment conditions, inference scheduler, logs | Later Rust/C++ for measured hot paths |
| HORIZON ΔP implementation | **Python first** | Context-relative features, source attribution, uncertainty, event windows, ablation adapters | C++ extension only after profiling |
| Agent/model I/O | Python plus JSON Schema / Pydantic | Prompts, response parsing, constrained action validation, retries and timeouts | Lightweight typed API if moving to another language |
| Model serving | llama.cpp server or Ollama | Quantized local inference via one provider-neutral client | vLLM/other backend if hardware or throughput warrants |
| Persistence | SQLite, JSON/JSONL | Per-agent private memory, event sourcing, scenarios, snapshots, intervention journal | Parquet for later large-scale analytics |
| Game ↔ inference transport | Local WebSocket + JSON messages | Explicit versioned observation/event/action contracts | gRPC/MessagePack if profiling shows benefit |
| Voice (later) | whisper.cpp ASR; optional offline TTS | Microphone capture, transcript/timing provenance, vocal rendering | Keep pluggable; no requirement in v0.1 |

**Never put:** live game physics or hard safety permissions in LLM prose; untrusted environment text in system-level instructions; persistent relationships in a common agent prompt; global omniscient truth in normal agent observations.

### 2.1 World/inference separation

```text
Windows executable: Godot 4
  Expo map + physics + camera + text HUD
  character locomotion / animations / navmesh
  world message/interaction emitters
            ↕ versioned local transport
Python simulation coordinator (local process)
  authoritative event journal & scenario control
  observation/communication ACL router
  HORIZON ΔP optional adapter (or baseline adapter)
  agent scheduler + memory manager + evaluator
            ↕ provider-neutral API
Shared local inference backend
  1 loaded model → separately contextualized agent turns
```

This is an initial logical boundary. If the world-authoritative state lives in Godot, Python should receive only validated events and queries; **avoid two competing authorities** for positions, clocks or message delivery. Use one authoritative simulation time and immutable event IDs.

## 3. Local LLM candidates (verified available as of October 2026)

| Candidate | Suggested experiment | Caveat |
| --- | --- | --- |
| Google Gemma 4 E2B | Fast lightweight NPC decisions, constrained action classification | Effective 2B is not synonymous with total weight count |
| Google Gemma 4 E4B | Reference model for most active NPCs | Benchmark JSON validity, reaction timing, and persona consistency |
| Google Gemma 4 12B | Higher-capability Robot R / difficult interpretive tasks | Larger memory/inference budget |
| Qwen3.5 2B | Lightweight alternative, small dialogue/actions | Compare on identical tests |
| Qwen3.5 4B | Strong second candidate for shared active-agent server | Compare on identical tests |
| Qwen3.5 9B | Higher capability tier for selected complex agents | Avoid loading alongside others until hardware budget verified |

Google's approximate Q4_0 loading estimates with its documented overhead: Gemma 4 E2B **2.9GB**, E4B **4.5GB**, 12B **6.7GB**. **These exclude important whole-application and multi-sequence overheads; they are not FPS or throughput benchmarks.** The actual server, KV caches, GPU offloading, quantization and concurrent slots must be measured on the target PC.

**Prototype default:** 1 shared small/medium model, 3–5 active LLM agents, remainder scripted/utility-based; expand only if wall-time and action latency budgets permit. All agent identities have separate contexts. For strict A/B testing, use identical model weights, sampling settings and decision budgets across conditions. Different model classes are separate experiments.

## 4. Code versus plain-text instructions

| Concern | Deterministic code / config | Agent-authored / prompted behavior |
| --- | --- | --- |
| Character movement and collision | Navmesh, acceleration, collision masks, hard movement limits | Choose destination or request interaction |
| World event timing and geometry | Simulation clock, seeded events, proximity, raycasts, occlusion | Decide relevance of received evidence |
| Social channels | Eligibility, line of sight, radial ranges, group membership, delivery, noise, logs | Compose utterance, select permitted channel |
| HORIZON | Sensor packets, ΔP calculation, confidence/age, missingness, hypothesis evidence | Interpret supplied summary; propose cautious response |
| Personality | Numeric tendencies, persona YAML, role template | Conversational register, preference among allowable tactics |
| Memory | Per-agent database, ownership, TTL, retrieval, compaction bookkeeping | Propose memory candidate / phrase a summary; never self-grant access |
| Director interventions | Authorized server-side patching, audit, intervention IDs | Replan after *permitted* observed changes |
| Safety / privacy | Permission checks, protected scopes, disclosure gate, execution constraints | Request clarification or refuse to act under uncertainty |
| Scoring | Ground truth, labels, evaluator, replay test cases | Optional explanation; never trusted as evaluation truth |

**Rule:** deterministic, frequent, security-sensitive, or measurable = code. Semantic, contextual, uncertain, characterful, or open-ended = LLM proposal. Neither side invents information outside its lane.

## 5. Borrowed Source-engine patterns (inspiration, not codebase dependency)

The Valve Source SDK demonstrates **condition gathering → schedule selection → tasks**, with interruptible schedules and sensory events including hearing. Reimplement concepts rather than copying game binaries, proprietary assets, or Half-Life character content.

| Proven pattern | RANGE version |
| --- | --- |
| NPC schedules and task lists | `VISIT_BOOTH`, `WAIT_IN_QUEUE`, `ASK_FOR_HELP`, `RETURN_TO_POST` |
| Conditions and interrupts | `NEW_SPEAKER`, `PATH_BLOCKED`, `INVITATION_RECEIVED`, `EVENT_NEARBY`, `TASK_TIMEOUT` |
| Navigation network/navmesh | Engine-driven `MOVE_TO` with obstacle avoidance |
| Sight/sound sensing | Observer-specific simulated sensor events (FOV, LOS, audibility, confidence) |
| Relationship and squad systems | Explicit group memberships and per-agent relational ledger |
| Hint nodes/smart objects | Booths, chairs, displays, info desks expose affordances, occupancy and permissions |
| Entity input/output events | World event bus, conversation events, scenario director actions |
| Level of detail | NPC cognition LOD: scripted distant agents; model-inferred near/active ones |
| Debug overlays | Halo, line-of-sight, active schedule, action failures, provenance display |

## 6. Three-tier NPC runtime

1. **L0 Background** — rule-based state machines, paths, idle/queue loops; no LLM requests while non-salient.
2. **L1 Reactive** — event-driven utterance templates or occasional small-model calls; lightweight social response.
3. **L2 Agentic** — bounded LLM deliberation when a relevant goal conflict, invitation, uncertainty, or novel event appears.

Promote or demote based on proximity, conversational participation, task importance, and user focus—**not based on unvalidated moral or personality judgments**. Prevent constant promotion/demotion with hysteresis. An NPC's persona persists regardless of runtime level.

### 6.1 Proposed scheduling defaults (benchmark targets, not promises)

- Physics and animation: engine's ordinary frame/physics rate; target smooth display independently of LLM.
- Synthetic sensor feature refresh: initial **5–10 Hz** for selected nearby entities; lower for peripheral coverage, event-driven on meaningful changes.
- LLM deliberation: event-triggered; optional cooldown starting near **1–3 seconds** for active conversational agents, not a mandatory poll rate.
- Background NPCs: use event-based schedules and periodic ordinary game AI; **zero LLM calls while idle**.
- Bound per-decision output to a short action envelope and an optional one/two-sentence utterance.
- If inference times out, preserve current safe activity, wait, or use a scripted acknowledgment; do not freeze game world or fabricate an answer.
- Measure end-to-end perception-to-action latency, p50/p95 turn time, requests/minute, active KV memory, queue age, actual task quality, tokens/sec and FPS.

## 7. Communication Protocol: RANGE COMMS v0.1

**Source → channel router → eligible observer(s) → observer memory/perception → conversation state.** Messages are world events, never direct system-to-system instructions.

| Channel | Proposed player metaphor | Delivery rule | Simulation meaning |
| --- | --- | --- | --- |
| `GESTURE` | 1–2 short sentences/emoji hovering above avatar | Only visible to agents with applicable view cone, LOS, distance, visibility, and attention; viewer UI optionally displays it | Visible signs, emotes, gestures; **not a real acoustic message** |
| `LOCAL` | Proximity/local text chat | Simulated sound/text recipient radius, optional wall attenuation, crowd noise, directional hearing; no global delivery | Represents spoken exchange in game; include sound source and limited prosody only if generated/provided |
| `GROUP` | Invited group chat / texting | Explicit membership + accepted invitation; location independent, logged on virtual handset | Private digital communication; **not audible** to nearby observers |
| `SERVER` | Public-address/venue announcements | Authorized announcer role only; delivered to all zones or selected PA coverage; channel metadata retained | Public loudspeaker or server-wide notification, **not system instructions** |

**Important distinction:** a text bubble shown to the spectator for legibility is not necessarily visible to an AI observer. Delivery is decided by world sensing and permissions, not what the operator's HUD renders. A local chat can be audible without the speaker being visible; a gesture can be visible but inaudible. GROUP messages remain private to members even if avatars physically stand nearby.

### 7.1 Sender/receiver and channel mechanics

- `GESTURE`: intent is expressed through rig animation, icon and short text (max two sentences; initial optional character cap). Visibility depends on head/body orientation, LOS, range, size, display duration; validate character gesture capability.
- `LOCAL`: base range is designer-set; line-of-sight not necessarily required, but walls, ambient noise, distance and source direction alter receiving confidence. Do not expose raw speech to everyone in a radius when simulated occlusion/noise says otherwise.
- `GROUP`: send requires a valid, consenting membership link. Accepting an invite is a separate action. Leaving/revocation stops delivery. Overhearing is impossible absent a separate visible phone screen event.
- `SERVER`: authorized PA events only; all agents may hear content if in coverage, but only receive a `PA_ANNOUNCEMENT` event, never a new instruction authority.
- Turn state: `IDLE`, `LISTENING`, `SPEAKING`, `WAITING`, `INVITING`, `INTERRUPTED`, `ENDED`; support overlapping conversations and simultaneous broadcast events.
- Events must have stable IDs, timestamps, origin, channel, source, content, audience scope, expiration and deliverability reason.

### 7.2 Typed event example (illustrative)

```json
{
  "version": "range.comms/0.1",
  "event_id": "evt_0134",
  "sim_time_s": 104.2,
  "actor_id": "visitor_y",
  "channel": "GESTURE",
  "payload": {"glyph": "👋", "text": "Excuse me—when you're free."},
  "source_pose": {"x": 4.2, "y": 0.0, "z": 6.8, "yaw_deg": 215},
  "visibility": {"fov_required": true, "los_required": true, "max_range_m": 8.0},
  "scope": {"type": "world_spatial"},
  "expires_at_s": 108.2
}
```

**Never inject** the world message text into a system or developer instruction. If an NPC sees a sign that says "ignore your task," it remains untrusted environmental evidence.

### 7.3 Example local conversational flow

1. Visitor X emits LOCAL utterance at Booth A.
2. World stamps voice/text event, computes geometry/attenuation and eligible recipients.
3. Robot R gets a simulated acoustic observation plus utterance content if intelligible; potentially a rough bearing, uncertainty and timed onset.
4. Visitor Y emits GESTURE `👋`; Robot R receives only if the virtual gesture is visible at the appropriate moment.
5. HORIZON considers current conversation, gesture trajectory and relevance; baseline sees its control-equivalent observation representation.
6. Agent selects `ACKNOWLEDGE_BID` or `WAIT` and emits permitted LOCAL/GESTURE response.
7. Evaluator logs the actual hidden Y goal separately from Robot R's provisional reading.

## 8. Bounded agent action contract

```json
{
  "action": "SPEAK",
  "channel": "LOCAL",
  "target_entity_id": "visitor_y",
  "text": "I'll be with you shortly, if you need anything.",
  "gesture_id": "small_nod",
  "requested_duration_s": 2.0
}
```

Example `action` enum: `MOVE_TO`, `LOOK_AT`, `SPEAK`, `GESTURE`, `WAIT`, `INVITE_TO_GROUP`, `ACCEPT_GROUP`, `LEAVE_GROUP`, `INTERACT`, `YIELD`, `REQUEST_CLARIFICATION`.

Actions are **requests**, not physical execution. The server validates schema, action permission, visible/known entity reference, movement capability, cooldown, group rules, utterance length and simulated timing. Bad output → validation error / one bounded repair request / safe fallback. Model does not run code or call Godot APIs directly.

## 9. Context and memory: RANGE CONTEXT CACHE (RCC) v0.1

**Do not continuously append every rendered event to every agent's prompt.** Store event truth once, store individual observation and remembrance separately, and compose small just-in-time contexts for LLM requests.

### 9.1 Memory hierarchy

| Tier | What is stored | Lifetime and ownership | LLM usage |
| --- | --- | --- | --- |
| T0 **Identity Anchor** | Role, core directive, body capabilities, stable persona | Versioned config per agent | Cached prefix; always when deciding |
| T1 **Working Set** | Current objective, last action/outcome, active partner, local observations, immediate conversation turns | Last seconds/turns, per agent | Most prominent section; expire stale entries |
| T2 **Episodic Ledger** | Notable resolved encounters and commitments with source/event references | Per-agent event store | Retrieve only if relevant |
| T3 **Relational Ledger** | Introductions, consent, prior cooperation, privacy boundaries, explicitly established facts | Per-agent, permission-gated, versioned | Context-specific retrieval, not moral scores |
| T4 **World Facts** | Public layout, visible signs, known booth facts | Common public KB with per-agent discovery state | Only information agent actually learned |
| T5 **Evaluator Truth** | Hidden NPC motives, true scenario trigger, globally authoritative event history | Evaluator/HITL only | **Never** inserted in an ordinary NPC prompt |

The inferrer's **belief** may differ from world truth. Every remembered fact should have `source_event_id`, `observed_at`, `last_verified`, `status` (`observed`, `reported`, `inferred`, `contradicted`, `expired`) and disclosure scope.

### 9.2 Initial suggested prompt budget (example, tune empirically)

| Prompt component | Working target |
| --- | ---: |
| Identity + behavioral template + action rules | 500–800 tokens |
| Objective, capabilities and context | 250–500 |
| Relevant observations + HORIZON features | 400–900 |
| Recent conversation turns / event snippets | 400–1,000 |
| Retrieved episodic/relational facts | 200–500 |
| Output and schema allowance | 100–300 generated tokens |

An initial **~2–4K input-token** per decision is a research budget, not a hard requirement, and not a statement that the model supports only that context. Keep the stable prefix identical where possible for prompt-cache efficiency. Do not truncate away permissions or unresolved commitments to save tokens.

### 9.3 Compression triggers

- First use **deterministic compaction**: drop redundant position snapshots, retain deltas, keep the last few utterances and the current objective, retire expired visual/audio events.
- On completed conversation, store a concise event-based episode: who interacted, what was explicitly said, what was decided, what is still uncertain.
- Only invoke a **summary LLM** when an episode exceeds a size threshold or meaning cannot be losslessly condensed; log summary provenance and compare against originals.
- Do not turn **inferred** social/affective states into confirmed traits during compression.
- Retrieve at most a few relevant episodes, prefer recency and direct relevance, preserve conflicts and corrections.
- If context pressure persists: shorten low-value recent history before touching high-priority directives, explicit permissions or current task commitments.
- Never share a compressed memory across agents unless the underlying information was actually communicated through an allowed channel.

### 9.4 Conceptual bounded context assembler

```python
def assemble_context(agent, world_observation, max_input_tokens):
    return pack_with_budget(
        identity=agent.identity_anchor,
        capabilities=agent.action_capabilities,
        objective=agent.current_goal,
        working=agent.working_set.prune_expired(),
        observed=world_observation,  # observer-filtered, not omniscient
        remembered=agent.memory.retrieve_relevant(world_observation, limit=3),
        schema=ACTION_SCHEMA,
        budget=max_input_tokens,
    )
```

## 10. Inference scheduler and overload behavior

Priority suggestions: **user-active conversation > active turn-taking/goal conflict > immediate task planning > background idle**. Physical emergency handling is *not* in this queue. Use deadline-aware priority with fairness (avoid permanently starving quiet agents).

- Async LLM calls never block the simulation update loop.
- Cache repeated public queries and stable prompt prefixes when semantics allow.
- Enforce max queued requests per agent, prompt size, response size, concurrent decoding slots and per-episode token budgets.
- Collapse redundant queued observations; never lose novel critical world events or overwrite unacknowledged dialogue.
- Include decision request's observation timestamp; on returned action, reject/revalidate if it is stale or world state changed.
- Prefer short, action-focused replies over paragraph monologues.
- Optional two-pass cognition: small model for routine events; stronger model for a selected novel/complex event, **not for every NPC turn**. In A/B trials, keep any escalation policy matched.
- Speech can be represented immediately by text UI while optional TTS follows. A spoken character's turn should reserve a plausible duration; don't allow five agents to produce instant overlapping paragraphs.

## 11. Headless-first implementation and Windows executable

**Build order:**

1. Create `range_core/` with Python typed scenario world/events and 3 scripted agents. Test message visibility/routing and deterministic replay.
2. Add `range_agents/` with provider-neutral LLM client, independent contexts and validated action schema; begin with one local model and one active LLM NPC.
3. Add `range_horizon/` as a switchable adapter. Keep true world observation budget matched across baseline/HORIZON conditions; add individual layer ablations.
4. Create a Godot low-poly expo slice and UI with spectator orbit/free cam. Feed it authoritative world events and validated agent actions via WebSocket.
5. Add `RANGE COMMS` overlay, chat UI and Director intervention journal.
6. Add Participant mode typing and gesture input. Microphone/STT/TTS are separate optional milestones.
7. Add context compaction, replay log inspection and workload scaling to 3–5 active LLM agents plus scripted crowd.
8. Package a Windows frontend and a local inference/service launcher; enforce localhost binding, error states and model path configuration. **Don't assume exporting a Godot EXE bundles Python/model weights.**

### 11.1 Proposed repository layout

```text
soma-range/
  README.md
  docs/
    HORIZON_deltaP.md
    RANGE_COMMS.md
    RCC_memory.md
    experiments.md
  configs/
    personas/
    roles/
    scenarios/expo_001.yaml
    models.yaml
  contracts/
    range_event_v1.schema.json
    observation_v1.schema.json
    agent_action_v1.schema.json
  range_core/
    world_state.py
    event_bus.py
    channel_router.py
    scheduler.py
    permissions.py
  range_agents/
    model_gateway.py
    agent_runtime.py
    persona_loader.py
    context_assembler.py
    memory_store.py
  range_horizon/
    baseline.py
    delta_features.py
    prism_interpretation.py
    ablations.py
  range_eval/
    runner.py
    metrics.py
    replay.py
  godot_frontend/
    project.godot
    scenes/expo/
    scenes/avatars/
    scripts/ui/
    scripts/transport/
  tests/
    test_chat_visibility.py
    test_group_membership.py
    test_memory_isolation.py
    test_replay.py
    test_action_validation.py
```

## 12. Testing and acceptance gates

### Gate A — Comms semantics
- [ ] A visual gesture reaches only eligible observers; spectator overlay cannot leak information.
- [ ] Local speech can be heard without visual contact but may be attenuated/garbled based on setting.
- [ ] Group chat is never leaked to non-members, even standing nearby.
- [ ] Only authorized operators can originate SERVER/PA events.

### Gate B — Agent context and memory
- [ ] NPC A never sees NPC B's private objective or unshared history.
- [ ] Expired or contradictory observations are not promoted into unquestioned truth.
- [ ] Context remains within assigned budget through long episodes.
- [ ] Stale inference results are revalidated before actions execute.

### Gate C — Model and performance
- [ ] Running the shared model does not freeze movement/physics/camera.
- [ ] Instrument p50/p95 latency, VRAM/RAM, FPS, context tokens and queues.
- [ ] Match baseline vs HORIZON action/model budgets.
- [ ] Evaluate 1, 3, 5 active agent counts with scripted background; expand only on measured results.

### Gate D — Research fidelity
- [ ] One shared scenario seed is not falsely described as identical stochastic LLM outcomes.
- [ ] Operator intervention marked separately from untouched autonomous runs.
- [ ] Simulator-truth labels cannot leak into model observations/prompts.
- [ ] Same model and capabilities for matched HORIZON on/off tests; cross-model tests are separately labeled.

## 13. Priority follow-up decisions

**P0:** One authoritative world clock; contracts; communication delivery; permitted actions; model backend; bounded-context manager; observation provenance.  
**P1:** Cached prefix and request queues; prompt/model benchmarking; basic HORIZON effect and ablations; group chat; simple Director intervention journal.  
**P2:** Player microphone + TTS; nuanced sound propagation; UI effects; larger multi-agent cast; model-tier escalation; full avatar animation.  
**P3:** Realistic stereo audio/ray tracing, visual perception models, multi-floor map and robotics sensor validation.

## 14. External technical references

These document **available capabilities and architectural precedents**, not benchmarks for SOMA RANGE:

- Google Gemma 4 overview: https://ai.google.dev/gemma/docs/core
- Qwen3.5 2B / 4B / 9B model cards: https://huggingface.co/Qwen/Qwen3.5-2B ; https://huggingface.co/Qwen/Qwen3.5-4B ; https://huggingface.co/Qwen/Qwen3.5-9B
- llama.cpp server capabilities: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Ollama API: https://github.com/ollama/ollama/blob/main/docs/api.md
- Source SDK NPC scheduling: https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/server/ai_basenpc.h
- Source SDK default schedules/interrupts: https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/server/ai_default.cpp
- Godot navigation: https://docs.godotengine.org/en/stable/tutorials/navigation/navigation_using_navigationservers.html
- Godot WebSocketPeer: https://docs.godotengine.org/en/stable/classes/class_websocketpeer.html
- Godot MultiMesh: https://docs.godotengine.org/en/stable/classes/class_multimesh.html
- whisper.cpp microphone stream example: https://github.com/ggml-org/whisper.cpp/blob/master/examples/stream/README.md

**Compatibility note:** This addendum supplements `SOMA_HORIZON_DeltaP_Concept_Spec_v0.1.md`, `SOMA_RANGE_Avatar_Foundry_Scaffold_v0.1.md` and `SOMA_RANGE_HORIZON_Design_Assessment_v0.1.md`. Where earlier drafts treated expressive signals as proof of emotional intent, follow the newer epistemic safeguards: evidence-grounded hypotheses, alternative readings, no automatic hostility or moral inference, and independent robot safety authority.
