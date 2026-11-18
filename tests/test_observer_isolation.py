"""D-62 (HORIZON operational architecture, adopted now as design constraints): one logical
observer per avatar, with run- and observer-scoped state and observer-local track ids.

- Track ids are local to their observer: two observers watching the same visitor get different
  ids. The ids come from Godot's observer filter; godot_app/tests/test_main.gd checks the world
  side ("each observer needs its own anonymous track for the same visitor"); here the agent side.
- Nothing in one agent's runtime state is shared with or readable by another: memory, tracks,
  caches (persona prefixes), pulse state, staged and sent requests. Read-only configuration and
  the shared gateway/scheduler (attributable, labelled per observer) are the only shared objects.
- Scheduler jobs are labelled with observer, layer, evidence time, deadline and estimated cost.
No Godot, no model.
"""

from __future__ import annotations

import asyncio

from range_service.agents.gateway import FakeModel, ModelGateway
from range_service.agents.scheduler import SlotScheduler

from .agent_helpers import CONFIGS, Scene, accept

SHARED_OK = {"gateway", "tokenizer", "body", "pulse_cfg"}      # read-only config, or the labelled shared scheduler
IMMUTABLE = (str, bytes, int, float, bool, type(None), frozenset, tuple)


def _reachable(obj, seen: set[int], skip: set[int]) -> None:
    """Ids of every mutable object reachable from ``obj`` (containers, dataclasses, plain objects)."""
    if isinstance(obj, IMMUTABLE) and not isinstance(obj, tuple):
        return
    if id(obj) in seen or id(obj) in skip:
        return
    if not isinstance(obj, tuple):
        seen.add(id(obj))
    if isinstance(obj, dict):
        items = list(obj.keys()) + list(obj.values())
    elif isinstance(obj, (list, set, tuple)):
        items = list(obj)
    elif hasattr(obj, "__dict__"):
        items = list(vars(obj).values())
    else:
        return
    for item in items:
        _reachable(item, seen, skip)


def _config_ids() -> set[int]:
    ids: set[int] = set()
    _reachable(CONFIGS.items, ids, set())
    return ids


def _state(rt, skip: set[int]) -> set[int]:
    ids: set[int] = set()
    for name, value in vars(rt).items():
        if name in SHARED_OK:
            continue
        _reachable(value, ids, skip)
    return ids


def _two_robots(gateway=None):
    """Two robot observers built the way the factory builds Robot R, with the pulse on (so the
    pulse, presence, intent monitor and survey state exist), each with its own id."""
    from range_service import expressions as expression_rules
    from range_service.agents.factory import public_persona, setting_lines
    from range_service.agents.runtime import AgentRuntime

    out = []
    for agent_id, body_id in (("robot_legged", "legged_humanoid"), ("robot_quadruped", "quadruped")):
        body = CONFIGS.items["bodies"][body_id]
        out.append(AgentRuntime(
            agent_id, persona=public_persona(CONFIGS.items["personas"]["robot_r"]), body=body,
            directive=CONFIGS.items["directives"]["expo_assistant"]["directive"],
            expressions=expression_rules.available(body, CONFIGS.items["expressions"]),
            setting=setting_lines(CONFIGS.items["maps"]["sandbox_flats"]), task="Help visitors.", focal=True,
            controller="LLM_AGENT", gateway=gateway, pulse=CONFIGS.items["pulse"]["pulse"], seed=5,
            post={"x": 15.0, "z": 10.0}, post_duty=True,
            survey_area={"x_min": 0.0, "x_max": 30.0, "z_min": 0.0, "z_max": 20.0}))
    assert all(rt.pulse is not None and rt.presence is not None and rt.survey is not None for rt in out)
    return out[0], out[1]


def test_two_observers_watching_the_same_visitor_keep_their_own_tracks_and_memory():
    a, b = _two_robots()
    # The same visitor, seen and heard by both; each observer has its own anonymous id for them.
    sa, sb = Scene(observer=a.agent_id), Scene(observer=b.agent_id)
    for _ in range(3):
        accept(a, a.take_presence() + ([] if (j := a.observe(sa.see("anon_aaaaaaaa01", 15, 8.5)
                                                               .hear("anon_aaaaaaaa01", "Hello?").packet())) is None
                                       else a.decide_now(j) if j.proposals is not None else []))
        accept(b, b.take_presence() + ([] if (j := b.observe(sb.see("anon_bbbbbbbb02", 15, 8.5)
                                                               .hear("anon_bbbbbbbb02", "Hello?").packet())) is None
                                       else b.decide_now(j) if j.proposals is not None else []))
    assert set(a.ws.tracks) == {"anon_aaaaaaaa01"} and set(b.ws.tracks) == {"anon_bbbbbbbb02"}
    assert a.conversation.partner == "anon_aaaaaaaa01" and b.conversation.partner == "anon_bbbbbbbb02"
    assert not any("anon_bbbbbbbb02" in str(i) for i in a.memory.items)
    assert not any("anon_aaaaaaaa01" in str(i) for i in b.memory.items)
    import pytest
    with pytest.raises(ValueError):
        a.observe(sb.packet())                        # a runtime only reads its own packets


def test_no_runtime_state_is_shared_between_agents():
    gateway = ModelGateway(FakeModel(), scheduler=SlotScheduler(2, reserved=1))
    a, b = _two_robots(gateway)
    sa, sb = Scene(observer=a.agent_id), Scene(observer=b.agent_id)
    for rt, s in ((a, sa), (b, sb)):
        job = rt.observe(s.see("anon_cccccccc03", 15, 8.5).hear("anon_cccccccc03", "Where is the demo?").packet())
        out = rt.take_presence()
        if job is not None:
            out += asyncio.run(rt.decide(job)) if job.proposals is None else rt.decide_now(job)
        rt.persona_prefix("FOCAL")                     # fill the caches too
    skip = _config_ids()
    shared = _state(a, skip) & _state(b, skip)
    assert not shared, [type(o).__name__ for o in shared]
    # The check itself works: a planted shared list is found.
    a.pulse_log.append(planted := [1])
    b.pulse_log.append(planted)
    assert _state(a, skip) & _state(b, skip)


def test_scheduler_jobs_are_labelled_per_observer():
    sched = SlotScheduler(1, reserved=0)

    async def go():
        sched.busy.add(0)                              # the only slot is busy: the job waits
        task = asyncio.create_task(sched.acquire("robot_legged", "C2", 1e12,
                                                 label={"layer": "DELIBERATION", "evidence_ms": 4200,
                                                        "deadline_ms": 6000, "est_cost_tokens": 900}))
        await asyncio.sleep(0)
        labels = sched.waiting_labels()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return labels
    (label,) = asyncio.run(go())
    assert label["observer"] == "robot_legged" and label["layer"] == "DELIBERATION"
    assert {"evidence_ms", "deadline_ms", "est_cost_tokens"} <= set(label)
