"""Option B scheduling (INFERENCE_STRATEGY step 3; T4, T12; G3b-2), against the stand-in server.
No model, no network."""

from __future__ import annotations

import asyncio
import statistics

import pytest

from range_service.agents.gateway import ModelGateway
from range_service.agents.inference import load_inference, make_scheduler
from range_service.agents.llama import LlamaProvider
from range_service.agents.scheduler import Dropped, SlotScheduler
from tests.test_llama_provider import ACTIONS, StandIn


@pytest.fixture
def slow_standin():
    s = StandIn(mode="slow", delay_ms=150)
    yield s
    s.close()


async def _decide(gateway: ModelGateway, agent_id: str, tier: str) -> dict:
    result = await gateway.decide(agent_id=agent_id, tier=tier, prompt=f"## NOW\n{agent_id} decides",
                                  prompt_sha256="0" * 64, max_tokens=64, allowed_actions=ACTIONS, tick=1)
    return result.model_calls[0]


def _gateway(standin: StandIn, scheduler: SlotScheduler | None, slots: int = 2) -> ModelGateway:
    provider = LlamaProvider.attach(standin.port, standin.key, parallel_slots=slots, warm_up=False)
    return ModelGateway(provider, deadlines_ms={"FOCAL": 4000, "C2": 6000, "C1": 3000}, max_concurrent=slots,
                        scheduler=scheduler)


async def _load(gateway: ModelGateway, rounds: int = 4, npcs: int = 6) -> tuple[list[int], list[dict]]:
    """Robot R decides every 200 ms while six NPCs keep the server busy. Returns R's queue times."""
    focal_queue: list[int] = []
    npc_calls: list[dict] = []

    async def npc(i: int) -> None:
        for _ in range(rounds):
            npc_calls.append(await _decide(gateway, f"npc_{i}", "C2" if i % 2 else "C1"))

    async def robot() -> None:
        await asyncio.sleep(0.05)
        for _ in range(rounds):
            call = await _decide(gateway, "robot_r", "FOCAL")
            focal_queue.append(call["timings"]["queue_ms"])
            await asyncio.sleep(0.2)

    await asyncio.gather(robot(), *(npc(i) for i in range(npcs)))
    return focal_queue, npc_calls


def test_focal_never_waits_behind_npcs_and_npcs_never_take_its_slot(slow_standin):
    gateway = _gateway(slow_standin, SlotScheduler(2, reserved=1))
    focal_queue, _ = asyncio.run(_load(gateway))
    assert max(focal_queue) <= 20, focal_queue                    # pinned slot: no queue at all
    slots = {}
    for body in slow_standin.b.requests:
        agent = body["messages"][0]["content"].split("\n")[1].split()[0]
        slots.setdefault(agent, set()).add(body["id_slot"])
    assert slots["robot_r"] == {0}                                # T4: the same slot every time
    assert all(s == {1} for a, s in slots.items() if a != "robot_r")   # NPCs never evict R's cache


def test_option_b_beats_option_a_on_focal_latency_under_load(slow_standin):
    """INFERENCE_STRATEGY step 3's measure: focal queue time under NPC load, FIFO vs PRIORITY."""
    fifo, _ = asyncio.run(_load(_gateway(slow_standin, None)))
    prio, _ = asyncio.run(_load(_gateway(slow_standin, SlotScheduler(2, reserved=1))))
    assert statistics.median(prio) < statistics.median(fifo)
    assert max(prio) < max(fifo)


def test_priority_and_aging_order_the_shared_slot():
    async def run() -> list[str]:
        clock = {"t": 0.0}
        s = SlotScheduler(1, reserved=0, aging_ms=1000, clock=lambda: clock["t"])
        first = await s.acquire("busy", "C1", 100.0)               # takes the only slot
        order: list[str] = []

        async def ask(agent: str, tier: str) -> None:
            slot = await s.acquire(agent, tier, 100.0)
            order.append(agent)
            s.release(slot)

        old_c1 = asyncio.create_task(ask("old_c1", "C1"))
        await asyncio.sleep(0)
        clock["t"] = 1.5                                          # old_c1 has waited 1.5 s (priority 2 - 1.5)
        c2 = asyncio.create_task(ask("new_c2", "C2"))             # priority 1, newer
        await asyncio.sleep(0)
        clock["t"] = 3.0                                          # old_c1: 2 - 3 = -1; new_c2: 1 - 1.5 = -0.5
        s.release(first)
        await asyncio.gather(old_c1, c2)
        return order

    assert asyncio.run(run()) == ["old_c1", "new_c2"]


def test_priority_wins_without_aging():
    async def run() -> list[str]:
        s = SlotScheduler(1, reserved=0, aging_ms=0)
        first = await s.acquire("busy", "C1", 1e9)
        order: list[str] = []

        async def ask(agent: str, tier: str) -> None:
            slot = await s.acquire(agent, tier, 1e9)
            order.append(agent)
            s.release(slot)

        tasks = [asyncio.create_task(ask("c1", "C1")), asyncio.create_task(ask("c2", "C2"))]
        await asyncio.sleep(0)
        s.release(first)
        await asyncio.gather(*tasks)
        return order

    assert asyncio.run(run()) == ["c2", "c1"]


def test_stale_calls_are_dropped_before_the_model(slow_standin):
    async def run():
        gateway = _gateway(slow_standin, SlotScheduler(2, reserved=1, min_service_ms=300),)
        gateway.deadlines_ms["C1"] = 400
        # Keep the shared slot busy for 150 ms per call; the next C1 call cannot start in time.
        calls = await asyncio.gather(*(_decide(gateway, f"npc_{i}", "C1") for i in range(4)))
        return calls

    calls = asyncio.run(run())
    dropped = [c for c in calls if c["outcome"] == "TIMEOUT" and "dropped before reaching the model" in (c["error"] or "")]
    assert dropped, [c["outcome"] for c in calls]
    assert len(slow_standin.b.requests) == 4 - len(dropped)     # dropped calls never reached the server


def test_a_newer_request_supersedes_a_queued_one():
    async def run():
        s = SlotScheduler(1, reserved=0)
        first = await s.acquire("busy", "C2", 1e9)
        stale = asyncio.create_task(s.acquire("npc_1", "C1", 1e9))
        await asyncio.sleep(0)
        fresh = asyncio.create_task(s.acquire("npc_1", "C1", 1e9))
        await asyncio.sleep(0)
        with pytest.raises(Dropped, match="superseded"):
            await stale
        s.release(first)
        assert await fresh == 0
        return s.stats

    stats = asyncio.run(run())
    assert stats["dropped_superseded"] == 1


def test_a_cancelled_waiter_leaves_the_queue():
    async def run():
        s = SlotScheduler(1, reserved=0)
        first = await s.acquire("busy", "C2", 1e9)
        waiter = asyncio.create_task(s.acquire("npc", "C1", 1e9))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert not s.waiting
        s.release(first)
        assert not s.busy

    asyncio.run(run())


def test_configured_scheduler_is_option_b_with_one_reserved_slot():
    inf = load_inference()
    s = make_scheduler(inf)
    assert isinstance(s, SlotScheduler) and s.reserved == 1 and s.slots == inf["servers"]["focal"]["parallel_slots"]
    inf["scheduler"]["mode"] = "FIFO"
    assert make_scheduler(inf) is None
