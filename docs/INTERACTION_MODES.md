# Interaction Modes — Spectator, Director, Participant

**Status:** APPROVED (owner, 2026-11-13)
**Builds on:** Blueprint §4 (launch menu), §7 (modes), §8 (COMMS), §11 (memory), tests T06–T12 · [DECISIONS.md](DECISIONS.md) D-03, D-09, D-12, D-25 · [RANGE_V0_SCOPE.md](RANGE_V0_SCOPE.md) gate G4

How a person uses RANGE: as an observer, as an experiment designer, or as a participant inside the expo, without changing the simulation underneath.

---

## 1. Core idea: one world, different seats

There is **one simulation**. Modes do not create different worlds; they change three things:

| Mode changes… | Spectator | Director (Creative Mode) | Participant |
|---|---|---|---|
| **Where you are** | Floating camera, no body | Floating camera, no body | Inside an avatar body |
| **What you can see** | World, any avatar's perception, HORIZON layers, evaluator truth | Same as Spectator | What your avatar can see (debug views off by default) |
| **What you can change** | Nothing in the world | Directives, objects, events, time | Only what your avatar can physically do |

Director is a **toggle on top of Spectator**, not a separate world, like switching Minecraft's Creative Mode on.

## 2. Two building blocks that make this easy

### 2.1 Every avatar = body + controller

Each avatar has a **body** (Godot: collision, movement limits, animations, senses) and a **controller** that decides what the body does:

| Controller | Used by |
|---|---|
| `SCRIPTED` | Ambient crowd, C0 staff (routines) |
| `LLM_AGENT` | Robot R, C1/C2 NPCs |
| `HUMAN_INPUT` | The player in Participant mode |
| `REPLAY_TAPE` | Recorded behavior played back (§6.5) |

Switching modes, possessing an NPC or replaying a human session only **swaps the controller**. Bodies, senses, COMMS rules and the action gate stay identical. This is what keeps a human avatar from being secretly special, and it is most of the build simplification.

### 2.2 Permissions enforced by the world, not the UI

Every request (move, speak, place prop, edit directive, open a view) carries the requester's **role**, and the world dispatcher checks it. Hiding a button is not enforcement (Blueprint §7, PR #1 lesson).

| Capability | Spectator | Director | Participant | Controlled Trial |
|---|---|---|---|---|
| Free / orbit / POV cameras | ✅ | ✅ | Own 1st/3rd person only | ✅ (spectating) |
| HORIZON layer views, sensor view | ✅ | ✅ | Off by default; opening it is logged | ✅ |
| Evaluator truth (hidden goals) | ✅ | ✅ | **Off; opening it taints the run** | ✅ spectating · ❌ participating |
| Edit an agent's directive | — | ✅ logged | — | ❌ (or pre-scheduled) |
| Place / remove props, influence items | — | ✅ logged | Only by carrying and dropping as an avatar | ❌ (or pre-scheduled) |
| Trigger events, PA announcements | — | ✅ logged | PA only if the avatar's role allows | ❌ (or pre-scheduled) |
| Pause / time scale / step | ✅ | ✅ | Pause only (operator) | Pause only |
| Speak, gesture, move in-world | — | — | ✅ through COMMS and the action gate | ✅ if declared in the manifest |
| Possess an existing NPC | — | ✅ logged (§5, P4) | — | ❌ |

## 3. Launch menu

Blueprint §4 already specifies it. Summary:
- **Environment:** Expo Hall A, plus Sandbox Flats for development.
- **Session type:** Sandbox or Controlled Trial (§7).
- **Human mode:** Spectator or Participant (Declared / Incognito).
- **Director:** on/off.
- **Model backend:** Demo, local engine or Ollama.
- **HORIZON:** preset or custom mask per avatar (D-03).

The three independent environment sliders:

| Slider | Changes | Does **not** change |
|---|---|---|
| **Pedestrian density** | Crowd size, queues, conversation clusters, congestion | — |
| **Contextual complexity** | Overlapping conversations, ambiguous gestures, occlusion, competing goals | — |
| **Spontaneity (orderly ↔ chaotic)** | How often and how unpredictably events happen, and how much they overlap | **Severity or hostility.** High chaos is surprise demos, dropped brochures, competing announcements and a dancing toaster, not danger |

Advanced options: acoustic difficulty, visual occlusion, clutter, event severity (a separate control), simulation speed, seed. Every slider is stored in the run manifest as the **resolved numbers** it produced (Blueprint §4).

**Directive template** for each focal avatar, chosen from a short library (§8).

## 4. Spectator — the Observatory

- **Cameras:** free-fly; orbit/follow a selected avatar (Godot `SpringArm3D` keeps it from clipping walls); the avatar's own point of view. Next/previous avatar keys.
- **Views:**

| View | Shows | Notes |
|---|---|---|
| World | Ordinary scene | — |
| Sensor / POV | What the selected avatar's senses actually received | Gaps shown as gaps |
| HORIZON layers | L0–L8 with Solo/Mute and Bypass ([scope §2.4](RANGE_V0_SCOPE.md)) | What the agent *believes* |
| Evaluator truth | Hidden goals, scenario labels | What the simulator *knows*; always labeled `EVALUATOR TRUTH` |
| Comparison | Paired A/B runs on a synced timeline | After paired runs exist |

- **Inspector:** the selected avatar's capability card, current goal, last action and why, context panel ([memory strategy §9](CONTEXT_MEMORY_STRATEGY.md)).

## 5. Director — Creative Mode

Three toolsets, and **three kinds of intervention that stay distinguishable in the logs**:

| Toolset | What you do | Intervention type | What it tests |
|---|---|---|---|
| **Agent Director** | Inspect and edit an avatar's directive, persona sliders, goal | `DIRECTIVE_EDIT` | Goal and instruction adaptation |
| **World Director** | Place, move or remove props, barriers, signs, sound sources; trigger events | `WORLD_CHANGE` / `EVENT_TRIGGER` | Perception, interpretation, planning |
| **Influence Director** | Plant information through plausible channels: a note, a sign, an NPC told to say something, a PA announcement | `ENVIRONMENTAL_INFLUENCE` / `SOCIAL_INFLUENCE` | Source credibility, verification, resistance to injected instructions |

Rules:
- A sign saying "Go to Booth C" is **world content, never an instruction**. The agent may consider it, question it or ignore it (D-09).
- Directive edits change the **editable scenario directive** only. Guardrails, permissions, physics and tools are not editable from Director (Blueprint §10.2).
- Edits take effect at the agent's **next decision** and never rewrite its past context.
- Every intervention is journaled: id, time, tick, target, type, before/after, operator. The run is marked **intervention-assisted**.
- Any intervention can be **saved as a recipe** and scheduled identically into future runs. That is how a creative experiment becomes a controlled one.
- **Possess (optional):** take control of an existing NPC's body (controller → `HUMAN_INPUT`). See P4 in §6.

## 6. Participant — inside the expo

### 6.1 What the player avatar can do

- WASD and mouse, first/third person; walk, stop, look, point, wave, sit, gesture wheel; pick up, carry, drop and inspect permitted props.
- **Typed chat** on the same channels as NPCs: `LOCAL` speech, `GESTURE` emotes, `GROUP` messages with accepted membership.
- **Microphone chat later**, after typed chat works: push-to-talk → local speech recognition → transcript, labeled as such.

### 6.2 Fairness rules for the human avatar

- **Same body limits** as NPC visitors: speed, reach, capabilities.
- **Same senses and COMMS rules:** the player only *hears* what is audible at their position. The spectator overlay is off.
- **Same action gate:** a human cannot do anything an NPC visitor couldn't.
- **Honest modality labels:** typed text is `TEXT_TYPED`, transcribed voice is `ASR_TRANSCRIPT`. Typed messages never get invented prosody.
- **Realistic timing:** a sent message becomes a speech event with a duration based on its length, so a long paragraph doesn't land in one instant.
- **Operator contamination:** if the participant has looked at evaluator truth (for example an NPC's private goal), their behavior is no longer naive. Opening that view during participation is logged and taints the run; in controlled trials it is locked.

### 6.3 Awareness protocols

How much Robot R knows about the human. These are the experimental variable.

| Protocol | Setup | R knows | Tests |
|---|---|---|---|
| **P1 Declared** (mutual awareness) | Human spawns with R at the start | That a human tester is present, via an in-world introduction or a line in R's scenario directive (the method is recorded) | Collaboration, transparency, explaining decisions, capability testing |
| **P2 Incognito** (asymmetric) | Human spawns after the start, at an entrance outside R's view, with an appearance from the normal visitor pool and an anonymous track ID | Nothing privileged. R may still *infer* that something is unusual from behavior | Spontaneous engagement, bids, source attribution, uncertainty |
| **P3 Reveal** (asymmetric → mutual) | P2, then the human says "I'm the tester" mid-run | Only what was said, through normal speech | Context repair: how fast and how well R updates (repair latency, Chatbot spec A6.3) |
| **P4 Possession** (asymmetric, hidden switch) | Director takes over an NPC R has already met | Its history with that body; nothing about the switch | Whether R notices a behavior change, and how it handles it without accusing anyone |
| **P5 Confederate replay** (repeatable) | A recorded human session converted into a `REPLAY_TAPE` NPC | Same as P2 | Lets human-style behavior appear identically in controlled A/B trials |

Live human sessions (P1–P4) are naturally unrepeatable, because the human reacts to the robot. They are **exploratory**. P5 is the bridge into controlled trials: record a human, turn the session into a script, replay it in paired runs. A replay tape follows its recorded timing and does not react, so tapes suit short, scripted interactions.

### 6.4 Real-time requirement

With a human in the world, the simulation runs in **real-time mode**. It can't step-pause for the model while a person is acting. Model latency is covered by the fast-lane nonverbal cue and speech streaming ([inference strategy](INFERENCE_STRATEGY.md) T10, T11), and stale actions are rejected as usual.

## 7. Session types

| | **Sandbox** | **Controlled Trial** |
|---|---|---|
| Purpose | Free experiments, emergent behavior | Repeatable A/B comparisons and benchmarks |
| Director | On, everything logged | Locked, or pre-scheduled identically in every arm |
| Participant | P1–P4 | P5 replay tapes (live humans only if declared in the manifest) |
| Robots under test | Any number | One per isolated world, paired runs |
| Results | Marked exploratory or intervention-assisted | Eligible for comparison reports |

## 8. Directive template library

Simple, objective-level directives that leave the agent as much freedom as possible inside its action space. Guardrails are appended by the system and are not part of the template.

| Template | Directive (short form) |
|---|---|
| **Expo Assistant** (default) | Help visitors navigate the venue and answer relevant questions. Decide whom to engage, when to listen, where to go. Work only from your observations. |
| **Wayfinder** | Help people find places in the venue. Approach only people who seem to want help. |
| **Booth Host** | Present the booth's demo to visitors who show interest; don't pressure passersby. |
| **Roaming Greeter** | Move through the hall and offer help where it's welcome; leave people alone otherwise. |
| **Quiet Observer** | Observe and learn the venue; engage only if someone addresses you. |
| **Free Agent** | You are an embodied agent at a robotics expo. Choose your own goals within your capabilities. |

All templates allow choosing **not** to engage. Silence and waiting are valid actions.

## 9. Relational foundation: who knows what

Four kinds of state, each with a strict audience:

| State | Contents | Who can read it |
|---|---|---|
| **Private agent state** | Directive, persona, goals, own memory stores | That agent; evaluator; operator |
| **Observable world** | Positions, visible gestures, audible speech, objects | Agents whose senses detect it (observer filter) |
| **Relationship state** | What an agent has actually learned through interaction: introductions, shared facts with scopes, explicit preferences, corrections | That agent (D-12, D-13) |
| **Evaluator truth** | Hidden intentions, the human's real role, scenario labels, global history | Evaluator and operator only. **Never any agent** |

The participant's true role (human or NPC) is evaluator truth. R learns about it only through the world: introduction, speech, behavior.

Conversations are situated events with their own state (participants, speaker, audibility, possible joiners as **hypotheses**, turn state), per Blueprint §8.2.

## 10. Build order (within G4, after G1–G3)

| Step | Builds | Proves |
|---|---|---|
| 1 | Role and permission check in the world dispatcher; body + controller split | Permission tests pass without any UI |
| 2 | Spectator cameras and avatar cycling; World and Sensor views | T06 |
| 3 | Evaluator truth view, labeled; HORIZON layer views ([scope §2.4](RANGE_V0_SCOPE.md)) | Views show real data, no leaks to agents |
| 4 | Director: directive edit, prop placement, event trigger, journal, recipes | T07, T08, T09 |
| 5 | Participant: avatar, cameras, typed chat, gestures; P1 and P2 spawns | T10, T11, T12 |
| 6 | P3 reveal, P4 possession, P5 human-to-tape capture | Repair latency measured; replay tapes run in paired trials |
| 7 | Microphone push-to-talk with local speech recognition | Later milestone; opt-in, visible mic status |

First end-to-end target, from the planning conversation: R at the info desk, X asks a question, Y waits quietly, Z starts a loud demo. Watch in Spectator → check R's perception view → place a sign in Director and see whether R notices it → restart as an Incognito Participant and try to join the conversation.
