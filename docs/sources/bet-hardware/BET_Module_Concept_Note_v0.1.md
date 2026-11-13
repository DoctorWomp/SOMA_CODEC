# BET Module — Concept Note v0.1

Oct 6, 2026 · @DoctorWomp

## What it is

The BET module is a self-contained compute puck that plugs into any robot chassis and gives it a consistent expression layer: face, light, voice prosody, and a persistent persona. Think NUC or Mac mini class hardware, a small screen for emoji-style faces, an ARGB strip, a mic array and camera, and a portable battery, connected to the host robot over one USB-C or USB4 cable.

The host robot keeps everything about moving and staying safe. The module handles how the robot communicates: reading conversational cues, choosing an expressive state, and rendering it across face, light and voice. One module, many bodies.

The more important deliverable is the protocol, not the box. MIDI did not make synths better; it let any controller drive any synth. BET aims to do the same for expression: a published interface between "what the robot is doing" and "how it shows up to people." The puck is the reference implementation of that protocol.

## Why build it

Most robots are built to move well and communicate badly. A modular expression layer fixes the second problem once, instead of per robot.

- **Humor and character.** A small codebook with good timing carries a lot. WALL-E runs on two eyes and a handful of sounds; Jailbot-style personas show how much personality fits in minimal channels. Humor is also the release valve the MVSB names (the HAL failure mode).
- **Better interaction.** Turn-taking, noticing confusion, matching a person's dynamic range, and repairing misfires make a robot easier to work with, whatever its job.
- **Navigating human spaces.** Reading conversational mechanics (someone is mid-sentence, someone is waving it off, a group is crowding) helps a robot pick when to speak, wait or yield. This is interaction optimization, not judging people.
- **Persona continuity for vulnerable users.** Cloud companions can change overnight. In early 2023, Replika's abrupt behavior change left users describing grief. A persona that lives on a local module the user controls cannot be rewritten or deleted by a remote update.
- **Portability.** One validated module can move across chassis, so expression research done at tier 1 and 2 carries into tiers 3 and 4 without starting over.

## How it works

The host and the module split cleanly: the host owns motion and safety, the module owns expression, and a published protocol sits between them.

&#91;embedded content: BET module architecture · host, protocol, module\]

The host sends state (moving, docking, low battery, current task) and sensor context (proximity, positions of people). The module can send requests back, such as turning toward a speaker or slowing an approach, and the host is free to refuse them. Everything the module does inside runs locally: sense, decide, express, with the persona file underneath.

**Candidate local stack** (all choices to be benchmarked, not settled):

| Function | Candidate | Note |
| --- | --- | --- |
| Speech-to-text | Whisper-class model (e.g. whisper.cpp) | Runs at 16 kHz; fed a downsampled copy |
| Prosody features | openSMILE or Praat-style pitch and energy tracking | Runs on the 44.1 kHz stream |
| Reasoning and persona | Small local LLM (Gemma-class) | Time to first token is the main latency cost |
| Vision | Small vision-language model | Conversation mechanics only: attention, turn-taking |
| Voice out | Lightweight local TTS (Piper or Kokoro class) | Pitch, rate and warmth driven by the CC lanes |
| Face and light | Small screen plus ARGB strip on a microcontroller | Fastest lanes; carry reactions while words load |

The CDC mode templates map onto the Decide layer: the mode sets which lanes are active and which analysis windows run, which is where the buffer choices below come in.

## Audio and latency budget

44.1 kHz / 16-bit is more than enough for speech: 16-bit gives about 96 dB of dynamic range, and speech energy sits well below 20 kHz. The buffer sizes below are a good starting set, but they matter more as analysis windows than as a source of delay.

| Buffer (samples) | Duration at 44.1 kHz | FFT bin width | Best suited to |
| --- | --- | --- | --- |
| 256 | 5.8 ms | 172 Hz | Voice activity, onsets, barge-in detection, fast reactive protocols |
| 512 | 11.6 ms | 86 Hz | Loudness envelope, speech rate, general prosody tracking |
| 1024 | 23.2 ms | 43 Hz | Pitch (F0) and formants for most voices |
| 2048 | 46.4 ms | 21.5 Hz | Low voices, timbre and spectral color, slower context protocols |

Two trade-offs follow from the table. Pitch tracking needs about two periods of the lowest voice; a low voice near 70 Hz has a 14 ms period, so 256 alone is too short for pitch and should be paired with overlapping longer frames. And the speech-to-text step usually wants 16 kHz mono, so capture at 44.1 kHz for prosody and downsample a copy for transcription.

**Where latency actually lives.** Audio buffering adds 6 to 46 ms. The big costs sit elsewhere, and the figures below are ballpark guesses to be measured, not specs:

- End-of-turn detection: roughly 200 to 700 ms (deciding the person has finished is the slowest step)
- Speech-to-text: roughly 100 to 300 ms
- Local language model, time to first token: roughly 100 to 500 ms on Mac mini class hardware
- Text-to-speech, first audio out: roughly 50 to 200 ms

People typically start replying around 200 ms after the other person stops, so a spoken reply will usually arrive late. The fix is the face and light lanes: they can react inside about 100 ms (a nod, a listening glow, a raised eyebrow) while words are still being prepared. That is the stinger from the game-music model, covering the gap the way a human "mm" does.

The CDC doc's sub-millisecond threat interrupt should not live on this module. Physical safety belongs on the host robot's own controller, keyed to physical events; the BET module is never in the safety-critical path.

## Persona continuity requirements

The persona runs locally and belongs to the user. Local must not mean frozen: it has to stay fixable without becoming rewritable from outside.

1. **Local by default.** Persona, expression state and relationship memory run on the module with no cloud dependency. Network loss or a vendor shutdown changes nothing about who the robot is.
2. **User-controlled updates.** Updates are offered, never pushed. Each comes with a plain-language changelog that says what will feel different, and the user can decline or defer.
3. **Versioned with rollback.** Every persona version is kept, and the user can return to an earlier one.
4. **Safety fixes still get a path in.** Security and safety patches can be marked urgent, but they change the engine, not the character. A safety patch that alters personality must say so.
5. **Portable state.** The persona is an exportable file the user owns. If the hardware dies, it restores onto new hardware.
6. **Transparent on request.** The persona can say what it is tracking and why, matching the spec's "transparency on request" rule.

For companion and therapy uses, continuity carries a second duty: the robot should make it easier for someone to reach human support, never stand in for it. The spec's "no hidden engagement optimization" rule applies with more force here.

## Boundaries and guardrails

The module expresses; it does not judge or act physically. These limits carry over from the Chatbot Tier spec and the session handoff.

- **Never in the safety loop.** It cannot command motion or force. It can only ask the host for things, and the host can refuse.
- **Hooks, not verdicts.** The host decides state; the module expresses it. The expression layer never decides that someone is a threat.
- **No deception detection or alignment labels.** Incongruence between channels can trigger a soft check-in ("did I read that right?"), never a verdict about a person.
- **Reads are ephemeral.** Dynamic range and register estimates decay within the conversation and are not stored as labels about anyone without consent.
- **No manipulation or engagement tuning.** Warmth is never optimized for time spent or attachment.
- **Camera and mic are for conversation mechanics.** Turn-taking, attention and confusion, processed on the module; nothing leaves the module unless the user turns it on.
- **Metaphors stay labeled as metaphors.** EEG-band, harmonic and key-character mappings are design inspiration, not measurement.

## Open questions and next steps

**Open questions**

- 44.1 kHz or 48 kHz? Many USB mics and video pipelines run natively at 48 kHz, which avoids a resampling step.
- What is the measured mic-to-first-sound latency on Mac mini class hardware with a small local model, and is it under one second?
- Which buffer and window sizes map to which CDC templates once tested, rather than estimated?
- How small can the face codebook be while staying readable to strangers (tier 4) and still grow for trusted users (tier 3)?
- Does the protocol carry CC-style continuous values, discrete state events, or both?

**Next steps**

- [ ] Consolidate the Accord MIDI CC map and fix the collisions (CC1, CC25, CC27, CC32) before defining the module protocol on top of it
- [ ] Draft the host/module protocol: message types, rates and who owns what
- [ ] Build a bench prototype: laptop, USB mic, small screen, ARGB strip, local ASR, LLM and TTS
- [ ] Measure the end-to-end latency budget and replace the ballpark figures above
- [ ] Test whether fast face and light reactions make slower spoken replies feel natural to listeners
- [ ] Define the persona file format: export, restore, versions and changelog
