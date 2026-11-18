"""G3d fix 5 (D-67): the idle budget caps attempted background work.

Before: a pulse review was debited only when its decision completed with an idle activity, so
reviews that were cancelled or pre-empted (the sidecar cancels a pending review when a real event
arrives) never counted and the budget did not cap the model work actually started. Now a
background job is debited when it is admitted. No Godot, no model.
"""

from __future__ import annotations

import asyncio

from range_service.agents.gateway import FakeModel, ModelGateway, ModelRequest, ModelResponse

from .agent_helpers import accept
from .test_pulse import CFG, Q, Scene, robot


class BlocksPulseReviews(FakeModel):
    """Answers real decisions at once; a pulse review thinks until it is cancelled."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        if "decide because: pulse review" in request.prompt:
            await asyncio.Event().wait()
        return ModelResponse(self.responder(request), "blocks-pulse")


def _admit_and_preempt(rt, s) -> int:
    """Run quiet packets until a pulse review is admitted, then cancel it as the sidecar does on
    a real event. Returns how many reviews were admitted and cancelled."""
    async def go() -> int:
        cancelled = 0
        for i in range(400):
            s.see(Q, 25, 18)                                   # someone far away, always in view
            if i % 12 == 11:
                # Talk far away (not to it, beyond conversation range): a change for triage, not a wake.
                s.hear(Q, "Look at that robot.", addressed=None, x=25, z=18)
            job = rt.observe(s.packet(advance=60))
            accept(rt, rt.take_presence())
            if job is None:
                continue
            if job.triggers == ["PULSE_REVIEW"]:
                task = asyncio.create_task(rt.decide(job))
                await asyncio.sleep(0.01)
                task.cancel()                                  # pre-empted: it never completes
                await asyncio.gather(task, return_exceptions=True)
                cancelled += 1
                if cancelled == CFG["pulse"]["idle_budget_per_min"]:
                    return cancelled
                continue
            accept(rt, await rt.decide(job))
        return cancelled
    return asyncio.run(go())


def test_cancelled_pulse_reviews_count_against_the_idle_budget():
    model = BlocksPulseReviews()
    rt = robot(ModelGateway(model), task=None, post_duty=True)
    s = Scene()
    cancelled = _admit_and_preempt(rt, s)
    assert cancelled == CFG["pulse"]["idle_budget_per_min"]
    reviews = [r for r in model.calls if "decide because: pulse review" in r.prompt]
    assert len(reviews) == cancelled and not any(r["triggers"] == ["PULSE_REVIEW"] for r in rt.records)
    debits = [e for e in rt.pulse_log if e["event"] == "IDLE_DEBIT"]
    assert len(debits) == cancelled                                      # debited at admission
    assert rt.pulse.model_reviews_at[-1] == debits[-1]["at_ms"]
    rt.pulse.budget = 1                                                  # one review a minute:
    assert rt.pulse.over_budget(rt.ws.now_ms)                            # the cancelled one used it up
