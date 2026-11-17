# Bake-off prompt set

`prompts_v1.jsonl` is the offline prompt set of the model bake-off (D-55, D-58). Each line is
one decision Robot R made in SB-04, exactly as its context was assembled (G3a context assembly,
D-51), played once in each robot body:

- the prompt, its SHA-256, the tier, the decision's triggers and the output cap;
- the agent's allowed actions, its body's gestures and the expressions that body can show;
- what the Demo policy answered (`reference.demo_answer`), and whether that answer kept a promise.

The set contains only agent-facing context: no private goal or evaluator-only label (checked by
`tests/test_bakeoff.py`, T17). It is rebuilt with `uv run python tools/bakeoff.py build-set`
(needs Godot). A rebuilt set is a new version (`prompts_v2.jsonl`): results always name the
set's SHA-256, so numbers from different sets are never mixed.

## prompts_v2.jsonl (G3c-1, D-59)

96 prompts, each with a `role`:

- **ROBOT_R** (56): Robot R's SB-04 decisions in each robot body (40, rebuilt with open promises shown by id), and 16 promise situations built through the real runtime (`range_service/eval/promptset.py`): in each body, after a conversation ends, the visitor Robot R promised to help waves, asks, waits, or waits while someone else walks past. They name who the promise was made to (`reference.promised_to`), so scoring checks the flag and the behavior.
- **NPC** (40): the visitors' own C1 and C2 decisions from the same SB-04 runs, with NPCs model-driven by the fake model. Each NPC prompt holds **its own** private goal, on its labelled line (D-51); nothing else private (tested). SB-05 adds no NPC prompts: its cast is Robot R in three bodies.

Set hashes are taken over LF line endings, so a Windows checkout (CRLF) gives the same hash: prompts_v1 is `ee2b7c03be96` (the first bake-off printed `93e215698db0`, the same file with CRLF).
