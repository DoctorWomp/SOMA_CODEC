"""Agent runtime (G3a): memory stores, context assembly, cognition levels, the Demo policy and
the model gateway. See docs/gates/G3_PLAN.md and decisions D-48 to D-53.

Agents only ever see their own observation packets, their own memory and the public parts of
their persona. Nothing here reads evaluator-only data or world truth.
"""
