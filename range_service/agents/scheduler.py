"""Priority scheduling of model calls (INFERENCE_STRATEGY step 3, T4 and T12; Option B; G3b-2).

The engine has a few parallel slots. Without a scheduler (Option A) calls wait in arrival order
on a semaphore, so Robot R can wait behind a queue of NPC chatter. With this scheduler:

- **Pinned slots** (T4): each agent of a pinned tier (FOCAL) owns one slot, starting at 0, so its
  prompt prefix stays cached and it never waits behind anyone else. Other agents only use the
  remaining shared slots and never touch a pinned slot (their prompts would evict its cache).
  A pinned agent beyond the reserved count shares like everyone else.
- **Priority with aging**: shared slots go to the waiting call with the best priority (FOCAL 0,
  C2 1, C1 2 by default); every ``aging_ms`` spent waiting counts as one priority step better,
  so a C1 call cannot starve forever.
- **Deadlines and stale-drop**: a call whose deadline is closer than ``min_service_ms`` when it
  would start is dropped before it reaches the model: its answer could only arrive late, and a
  late answer is discarded anyway (T25). The caller gets ``Dropped`` and does WAIT.
- **One pending call per agent**: if an agent asks again while its earlier call is still queued,
  the earlier one is dropped (superseded); only the newest situation matters.

- **Slot affinity** (G3c-1, INFERENCE_STRATEGY §3.2 "LRU affinity"): a shared slot remembers the
  agent it last served. An agent gets its own slot back when it is free (its prompt prefix may
  still be cached there); otherwise the least recently used free slot. Pre-warming (T6) uses
  ``try_acquire`` and never waits or takes a pinned slot.

Slot ids are real llama-server slot ids: the provider sends the granted id as ``id_slot``.
In Option C (G3c-1) each server has its own scheduler; the NPC server's has no pinned slots.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable

DEFAULT_PRIORITIES = {"FOCAL": 0, "C2": 1, "C1": 2}


class Dropped(Exception):
    """The call was dropped before it reached the model (stale or superseded)."""


@dataclass(order=True)
class _Waiter:
    sort_key: tuple = field(init=False, repr=False)
    priority: int
    enqueued: float
    seq: int
    agent_id: str = field(compare=False)
    deadline: float = field(compare=False)
    future: asyncio.Future = field(compare=False)

    def __post_init__(self) -> None:
        self.sort_key = (self.priority, self.enqueued, self.seq)


class SlotScheduler:
    def __init__(self, slots: int, *, pinned_tiers: tuple[str, ...] = ("FOCAL",), reserved: int = 1,
                 priorities: dict[str, int] | None = None, aging_ms: int = 2000, min_service_ms: int = 300,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if slots < 1:
            raise ValueError("at least one slot")
        self.slots = slots
        self.pinned_tiers = pinned_tiers
        self.reserved = min(reserved, slots - 1) if slots > 1 else 0   # always keep one shared slot
        self.priorities = dict(DEFAULT_PRIORITIES, **(priorities or {}))
        self.aging_ms = aging_ms
        self.min_service_ms = min_service_ms
        self.clock = clock
        self.pins: dict[str, int] = {}
        self.busy: set[int] = set()
        self.affinity: dict[str, int] = {}          # agent -> the shared slot it last used
        self._last_used: dict[int, int] = {}        # slot -> order of last grant (LRU)
        self._uses = 0
        self.waiting: list[_Waiter] = []
        self._seq = 0
        self.stats = {"granted": 0, "dropped_stale": 0, "dropped_superseded": 0}

    # ---------- public ----------

    def pinned_slot(self, agent_id: str, tier: str) -> int | None:
        if tier not in self.pinned_tiers:
            return None
        if agent_id not in self.pins and len(self.pins) < self.reserved:
            self.pins[agent_id] = len(self.pins)
        return self.pins.get(agent_id)

    async def acquire(self, agent_id: str, tier: str, deadline_at: float) -> int:
        """Wait for a slot; returns its id. Raises Dropped if the call should not run any more."""
        for old in [w for w in self.waiting if w.agent_id == agent_id]:
            self.waiting.remove(old)
            self.stats["dropped_superseded"] += 1
            if not old.future.done():
                old.future.set_exception(Dropped("superseded by a newer request from the same agent"))
        pinned = self.pinned_slot(agent_id, tier)
        if pinned is not None:
            if pinned in self.busy:   # only possible if the agent overlaps its own calls; wait for it
                while pinned in self.busy:
                    await asyncio.sleep(0.005)
            self._check_deadline(deadline_at)
            self.busy.add(pinned)
            self.stats["granted"] += 1
            return pinned
        self._seq += 1
        waiter = _Waiter(self.priorities.get(tier, 9), self.clock(), self._seq, agent_id, deadline_at,
                         asyncio.get_running_loop().create_future())
        self.waiting.append(waiter)
        self._dispatch()
        try:
            return await waiter.future
        except asyncio.CancelledError:
            if waiter in self.waiting:
                self.waiting.remove(waiter)
            elif waiter.future.done() and not waiter.future.cancelled() and waiter.future.exception() is None:
                self.release(waiter.future.result())   # granted just as we were cancelled: give it back
            raise

    def try_acquire(self, agent_id: str, keep_free: int = 1) -> int | None:
        """A free shared slot right now, or None; never waits, never a pinned slot, only when
        nobody is queued, and only if ``keep_free`` other shared slots stay free for a real call
        that may arrive meanwhile (G3c-2: pre-warming must never delay a real call). Prefers the
        agent's own slot."""
        if self.waiting:
            return None
        free = self._shared_free()
        if len(free) <= keep_free:
            return None
        slot = self._pick(agent_id, free)
        self.busy.add(slot)
        self._granted(agent_id, slot)
        return slot

    def release(self, slot: int) -> None:
        self.busy.discard(slot)
        self._dispatch()

    # ---------- inside ----------

    def _shared_free(self) -> list[int]:
        pinned = set(range(self.reserved))
        return [s for s in range(self.slots) if s not in pinned and s not in self.busy]

    def _pick(self, agent_id: str, free: list[int]) -> int:
        own = self.affinity.get(agent_id)
        if own in free:
            return own
        return min(free, key=lambda s: (self._last_used.get(s, -1), s))

    def _granted(self, agent_id: str, slot: int) -> None:
        self._uses += 1
        self._last_used[slot] = self._uses
        if slot >= self.reserved:
            self.affinity[agent_id] = slot

    def _check_deadline(self, deadline_at: float) -> None:
        if (deadline_at - self.clock()) * 1000 < self.min_service_ms:
            self.stats["dropped_stale"] += 1
            raise Dropped("stale: the deadline would pass before an answer could arrive")

    def _effective(self, w: _Waiter, now: float) -> tuple:
        aged = w.priority - (now - w.enqueued) * 1000 / self.aging_ms if self.aging_ms else w.priority
        return (aged, w.enqueued, w.seq)

    def _dispatch(self) -> None:
        now = self.clock()
        for w in list(self.waiting):                         # stale-drop first
            if (w.deadline - now) * 1000 < self.min_service_ms:
                self.waiting.remove(w)
                self.stats["dropped_stale"] += 1
                if not w.future.done():
                    w.future.set_exception(Dropped("stale: the deadline would pass before an answer could arrive"))
        free = self._shared_free()
        while free and self.waiting:
            best = min(self.waiting, key=lambda w: self._effective(w, now))
            self.waiting.remove(best)
            if best.future.done():
                continue
            slot = self._pick(best.agent_id, free)
            free.remove(slot)
            self.busy.add(slot)
            self._granted(best.agent_id, slot)
            self.stats["granted"] += 1
            best.future.set_result(slot)
