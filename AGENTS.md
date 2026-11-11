# SOMA RANGE development rules

Read `docs/ARCHITECTURE.md`, `docs/MILESTONES.md`, and `docs/CONTRACTS.md` before editing. This is a scaffold, not a completed simulator. Preserve existing content and keep research claims separate from measured behavior.

- Implement one acceptance-tested milestone at a time; start at the first incomplete milestone. Work on a feature branch, commit verified increments, and use draft PRs. Do not merge without human review.
- Godot owns the world, physics, sensing eligibility and action authority. Python owns agent adapters, per-agent memory and HORIZON experiments. Neither an LLM nor HORIZON gets privileged world state.
- Spectator observes; Director interventions are explicit recorded events; Participant acts through the same bounded channels as NPCs. UI mode labels alone do not enforce permissions.
- Every observation, decision and communication needs a trace ID, tick, recipient and source provenance. Keep private memory scoped to its owner. Unknown source is unknown, not an inferred identity asserted as fact.
- Replay consumes recorded decisions; a seed alone cannot reproduce live model inference or cross-platform physics. A/B trials share scenario, seed, model, prompts and inputs, changing only the declared treatment.
- No provider calls, telemetry, microphone capture or paid services by default. Never commit credentials, private conversations, real sensor recordings or unredacted bug bundles.
- For bugs: reproduce, locate the responsible boundary, add a meaningful regression test, make the smallest correction, then run `python scripts/check.py`. Use `--require-godot` for the complete gate. Report skips and unverified behavior honestly. Never remove a check to hide failure.
- Keep JSON Schemas, Python validation, GDScript consumers, examples and tests aligned when changing a wire contract. Bump the protocol version for incompatible changes.
- Before completing work: inspect the diff, document implemented versus planned behavior, list test evidence and remaining limitations. Do not rewrite unrelated systems or broaden scope silently.
