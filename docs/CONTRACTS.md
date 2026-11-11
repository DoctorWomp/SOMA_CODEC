# Wire protocol v1

Transport: development-only HTTP JSON at `127.0.0.1:8765`. `GET /health` identifies `offline-stub`. `POST /v1/decision` accepts exactly `{ "observation": <Observation>, "horizon_arm": "A" | "B" }` and returns a Decision. Unknown paths return 404; invalid payloads return 400 without echoing content. Request body limit is 16 KiB; read timeout is five seconds. This is not a hardened service. No credentials, user sessions, bulk world state, live model API or persistent memory is attached to HTTP.

Normative machine-readable shapes are in `contracts/*.schema.json`; Python dataclasses and validation live in `sidecar/soma_range/contracts.py`. All objects reject extra fields. JSON tick numbers must be nonnegative integers; booleans are invalid. Identifiers are nonblank strings up to 128 characters. Empty observation content is allowed, up to 4096 characters. `source_id` and `target_id` may be null.

Observation: `protocol`, `trace_id`, `tick`, `recipient_id`, `source_id`, `channel` (speech/gesture/environment), `visibility` (public/private), `content`.

Communication: `protocol`, `trace_id`, `tick`, `sender_id`, nullable `recipient_id`, `channel` (speech/gesture), `visibility`, `content`. Private sends require a named recipient; public sends may be unaddressed. This typed send proposal has validation only, no HTTP send endpoint or routing implementation yet. Godot must check range/occlusion and derive source attribution before converting a send into each recipient's observation. An actual sender identity in privileged routing state does not imply an NPC knows the source.

Decision: `protocol`, `trace_id`, `tick`, `actor_id`, `observation_trace_id`, `action` (acknowledge/wait), `target_id`, `horizon_arm`. Decisions inherit actor and tick from the observation; trace ID is SHA-256 of observation trace ID. Trace IDs must be unique within a run. The stub neither moves avatars nor synthesizes dialogue. No arbitrary code/tool execution or movement action exists.

The Godot consumer checks protocol, actor, observation correlation and supported action before display. Full action validation, trusted actor/session identity, source confidence, multi-recipient communication envelopes, per-stage latency, experiment manifest and version negotiation belong to later milestones. Do not treat the present client checks as world authorization.

The sample config contains synthetic prefiltered observations. It is not a world simulation or proof that occlusion/range/privacy routing works. `scripts/demo.py` emits one matched run per arm with canonical trace digests. Replay rejects malformed decisions, duplicate trace IDs and decreasing ticks, and hashes recorded outputs without re-inference. Digests differ between arms because the arm metadata differs; this is not a behavioral difference or score.
