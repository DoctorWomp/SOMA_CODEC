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
