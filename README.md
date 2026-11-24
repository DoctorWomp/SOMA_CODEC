# SOMA_CODEC

**SOMA HORIZON** is a proposed advisory sensory layer for embodied AI: nine layers (L0–L8) that help a robot notice who is around it, what it does and doesn't know, and when to act, wait, clarify or step back, so it can complete tasks in a way that fits the people around it.

**SOMA RANGE** is the simulated environment (Godot + Python) where HORIZON is being built and A/B tested, with a layer-by-layer viewer so people can see what the agent perceives and why it acts.

**Status:** G0 to G3 are complete (G3 closed 2026-11-23): the Godot sandbox with four robot bodies, senses, channels and the Python link (G0–G2), and an agent runtime (G3) in which Robot R and the visitors decide through local models on the owner's GPU, in real time: Robot R on Gemma 4 12B with lean answers, visitors on Qwen3.5-4B, a pulse that keeps robots visibly present between decisions, a head that looks while the body walks, an ambient display, and tools that measure speed, memory and GPU use. G4a is merged: seats with permissions enforced by the world (only an Evaluator seat sees hidden goals and prompts), Spectator cameras, a Sensor view, and a 2D layer viewer that explains each decision from logged evidence, live or on replay, without changing what agents do. G4b is on a draft PR: a Director seat that edits an agent's directive, places props, signs and sounds, makes announcements and has an NPC say something, every change journaled and saved as a recipe to schedule again; planted text reaches agents only through their senses, as untrusted evidence. Next: G4c (Participant); then HORIZON itself (G5). See [Build and run](docs/BUILD_AND_RUN.md) and the [decisions](docs/DECISIONS.md).

## Start here

- [RANGE v0 scope](docs/RANGE_V0_SCOPE.md): what is being built first, and in what order
- [Decisions](docs/DECISIONS.md): settled answers to conflicts across the design documents
- [Source index](docs/SOURCES.md): all design documents with dates, status and precedence
- [Inference strategy](docs/INFERENCE_STRATEGY.md): how local models stay fast enough for live interaction
- [Interaction modes](docs/INTERACTION_MODES.md): Spectator, Director (Creative Mode) and Participant, with awareness protocols
- [Context & memory strategy](docs/CONTEXT_MEMORY_STRATEGY.md): long memory without long prompts, so runs don't slow down
- [Pulse protocol](docs/PULSE_PROTOCOL.md): continuous behavior between model decisions, without constant prompting
- [HORIZON operational architecture](docs/HORIZON_OPERATIONAL_ARCHITECTURE.md): one HORIZON observer per avatar, and the first G5 experiment (proposed, D-62)
- [Field notes](docs/FIELD_NOTES.md): what real runs show, and which layer or gate fixes each gap
- [Art direction](docs/ART_DIRECTION.md): low-poly look, rendering budget, environment that affects perception
- [G0 plan](docs/gates/G0_PLAN.md): the first build gate
- [Windows setup](docs/OWNER_SETUP_WINDOWS.md): what to install on the development PC, and when
- [Concept art](docs/concept-art/)

HORIZON is research, not a validated emotion-recognition or safety system. Physical safety always belongs to the robot host.

## License

No license has been chosen yet: the code and documents are public to read, but all rights are reserved (D-28).
