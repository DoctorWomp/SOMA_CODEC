"""An agent's own memory stores (CONTEXT_MEMORY_STRATEGY §3, D-13, D-24; Blueprint §11).

Every item follows contracts/memory_item.schema.json. Rules enforced here:

- **Overheard is not stored** (D-12): only speech addressed to the agent becomes memory
  (``remember_heard``, via the disclosure module).
- **Inferred never becomes observed:** an INFERRED item can only become CONTRADICTED or EXPIRED.
- **Corrections supersede:** the old item becomes CONTRADICTED; only the correction is active.
- **Commitments and refusals** live in their own store and are never compacted away. At most
  ``MAX_OPEN_COMMITMENTS`` stay open; beyond that the oldest is released and logged.
- **Nothing here comes from world truth or another agent's memory.** The agent's own
  ``reason_summary`` text is never stored (CONTEXT_MEMORY_STRATEGY §6, no self-feeding).
- **Raw heard speech is bounded** (owner decision 2026-11-19 on D-70, built in G3f; CONTEXT_MEMORY_STRATEGY
  §8): once a conversation is summarized into an episode card, its raw heard items expire after
  ``RAW_HEARD_RETENTION_MS`` (10 minutes); and at most ``MAX_RAW_HEARD`` raw heard items stay
  active per agent, the oldest NORMAL-importance one expiring first. Items tied to an open promise
  (heard from someone the agent promised) or to a correction never expire this way while that holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from range_service.comms import disclosure

STORES = ("IDENTITY_ANCHOR", "COMMITMENTS_AND_REFUSALS", "WORKING_SET", "EPISODIC_LEDGER",
          "RELATIONAL_LEDGER", "WORLD_KNOWLEDGE", "TRAIL_BUFFER")
MAX_OPEN_COMMITMENTS = 8
MAX_EPISODE_CARDS = 50          # CONTEXT_MEMORY_STRATEGY §8
COMMITMENT_TTL_MS = 300_000     # an unkept promise expires after 5 minutes (reported, never silently dropped)
IMPORTANCE_RANK = {"LOW": 0, "NORMAL": 1, "HIGH": 2, "CRITICAL": 3}
RAW_HEARD_RETENTION_MS = 600_000   # D-70 (owner 2026-11-19): raw heard items last 10 minutes after their card
MAX_RAW_HEARD = 40                 # D-70: raw heard items active per agent, at most


class MemoryRuleError(ValueError):
    """An attempted change that the memory rules forbid."""


@dataclass
class AgentMemory:
    agent_id: str
    items: list[dict[str, Any]] = field(default_factory=list)
    # Retrieval tags kept beside the contract items (topics, participants); never shown to others.
    tags: dict[str, set[str]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)   # releases, expiries (for logs)
    _seq: int = 0

    # ---------- adding ----------

    def _next_id(self) -> str:
        self._seq += 1
        return f"mem_{self.agent_id}_{self._seq:05d}"

    def add(self, store: str, text: str, *, now_ms: int, status: str = "OBSERVED", source_class: str = "OBSERVED",
            scope: str = "PUBLIC", importance: str = "NORMAL", untrusted: bool = False,
            expires_at_ms: int | None = None, shared_by: str | None = None, source_event_id: str | None = None,
            audience: list[str] | tuple[str, ...] = (), commitment_state: str | None = None,
            tags: set[str] | None = None, supersedes: str | None = None,
            memory_id: str | None = None) -> dict[str, Any]:
        if store not in STORES:
            raise MemoryRuleError(f"unknown store {store!r}")
        content: dict[str, Any] = {"text": text[:1000], "untrusted_text": untrusted}
        if commitment_state is not None:
            content["commitment_state"] = commitment_state
        item = {
            "schema_version": "1.0",
            "memory_id": memory_id or self._next_id(),
            "owner_id": self.agent_id,
            "store": store,
            "status": status,
            "source_class": source_class,
            "source_event_id": source_event_id,
            "observed_at_ms": now_ms,
            "expires_at_ms": expires_at_ms,
            "scope": scope,
            "audience_present": sorted(set(audience)),
            "shared_by": shared_by,
            "group_id": None,
            "importance": importance,
            "version": 1,
            "supersedes": supersedes,
            "content": content,
        }
        self.items.append(item)
        self.tags[item["memory_id"]] = set(tags or ())
        return item

    def remember_heard(self, speech_item: dict[str, Any], packet: dict[str, Any], topics: set[str]) -> dict[str, Any] | None:
        """Store speech addressed to this agent (REPORTED, untrusted); overheard speech returns None."""
        self._seq += 1
        item = disclosure.remember_speech(self.agent_id, speech_item, packet, self._seq)
        if item is None:
            self._seq -= 1
            return None
        item["memory_id"] = f"mem_{self.agent_id}_{self._seq:05d}"
        self.items.append(item)
        participants = {item["shared_by"]} if item["shared_by"] else set()
        self.tags[item["memory_id"]] = set(topics) | participants
        self._cap_raw_heard(item["observed_at_ms"])
        return item

    # ---------- raw heard speech: retention and cap (D-70, owner 2026-11-19) ----------

    @staticmethod
    def is_raw_heard(item: dict[str, Any]) -> bool:
        """Speech addressed to this agent, stored as heard (REPORTED, untrusted): not a card, a
        promise, a correction or a fact the agent discovered."""
        return item["source_class"] == "REPORTED" and item["store"] in ("EPISODIC_LEDGER", "RELATIONAL_LEDGER") \
            and item["content"].get("untrusted_text") is True and item["supersedes"] is None

    def _protected(self, item: dict[str, Any]) -> bool:
        """Tied to an open promise (heard from someone the agent promised) or to a correction."""
        if item["importance"] in ("HIGH", "CRITICAL") or item["status"] == "CONTRADICTED":
            return True
        if any(i.get("supersedes") == item["memory_id"] for i in self.items):
            return True
        who = item.get("shared_by")
        return who is not None and bool(self.commitments_to(who))

    def _active_raw_heard(self, now_ms: int) -> list[dict[str, Any]]:
        return [i for i in self.items if self.is_raw_heard(i) and i["status"] not in ("EXPIRED", "CONTRADICTED")
                and (i["expires_at_ms"] is None or i["expires_at_ms"] > now_ms)]

    def summarized(self, speakers: set[str], since_ms: int, now_ms: int,
                   retention_ms: int = RAW_HEARD_RETENTION_MS) -> list[str]:
        """A conversation with ``speakers`` from ``since_ms`` was summarized into an episode card:
        its raw heard items expire ``retention_ms`` from now (D-70). Returns their ids."""
        out = []
        for item in self._active_raw_heard(now_ms):
            # Every raw item heard from them so far without an expiry: earlier conversations with
            # them were summarized already, and the line that opened this one may carry an
            # observation time just before ``since_ms``.
            if item.get("shared_by") in speakers and item["observed_at_ms"] <= now_ms and item["expires_at_ms"] is None:
                item["expires_at_ms"] = now_ms + retention_ms
                item["version"] += 1
                out.append(item["memory_id"])
        if out:
            self.events.append({"event": "RAW_HEARD_SUMMARIZED", "count": len(out), "expires_at_ms": now_ms + retention_ms,
                                "at_ms": now_ms})
        return out

    def _cap_raw_heard(self, now_ms: int, cap: int = MAX_RAW_HEARD) -> None:
        active = self._active_raw_heard(now_ms)
        excess = len(active) - cap
        if excess <= 0:
            return
        candidates = sorted((i for i in active if i["importance"] == "NORMAL" and not self._protected(i)),
                            key=lambda i: (i["observed_at_ms"], i["memory_id"]))
        for item in candidates[:excess]:
            item["status"] = "EXPIRED"
            item["expires_at_ms"] = now_ms
            item["version"] += 1
            self.events.append({"event": "RAW_HEARD_CAP", "memory_id": item["memory_id"], "at_ms": now_ms})
        if len(candidates) < excess:
            self.events.append({"event": "RAW_HEARD_OVER_CAP", "count": len(active) - len(candidates[:excess]),
                                "reason": "the rest are tied to an open promise or a correction", "at_ms": now_ms})

    # ---------- reading ----------

    def get(self, memory_id: str) -> dict[str, Any]:
        for item in self.items:
            if item["memory_id"] == memory_id:
                return item
        raise KeyError(memory_id)

    def active(self, store: str | None = None, now_ms: int | None = None) -> list[dict[str, Any]]:
        """Items that are neither contradicted nor expired (as of now_ms, if given)."""
        out = []
        for item in self.items:
            if store is not None and item["store"] != store:
                continue
            if item["status"] in ("CONTRADICTED", "EXPIRED"):
                continue
            if now_ms is not None and item["expires_at_ms"] is not None and item["expires_at_ms"] <= now_ms:
                continue
            out.append(item)
        return out

    # ---------- lifecycle ----------

    def set_status(self, memory_id: str, status: str) -> None:
        item = self.get(memory_id)
        if item["source_class"] == "INFERRED" and status not in ("INFERRED", "CONTRADICTED", "EXPIRED"):
            raise MemoryRuleError("an inferred item can never become observed or reported (Blueprint §11 rule 5)")
        item["status"] = status
        item["version"] += 1

    def correct(self, memory_id: str, text: str, *, now_ms: int, source_class: str = "REPORTED",
                untrusted: bool = True, shared_by: str | None = None) -> dict[str, Any]:
        """A correction supersedes the old item; only the correction stays active."""
        old = self.get(memory_id)
        old["status"] = "CONTRADICTED"
        old["version"] += 1
        return self.add(old["store"], text, now_ms=now_ms, status="REPORTED" if source_class == "REPORTED" else "OBSERVED",
                        source_class=source_class, scope=old["scope"], importance="HIGH", untrusted=untrusted,
                        shared_by=shared_by if shared_by is not None else old["shared_by"],
                        tags=set(self.tags.get(memory_id, set())), supersedes=memory_id)

    def expire(self, now_ms: int) -> list[str]:
        """Mark items past their expiry; returns their ids. Open commitments expire too, and say so."""
        expired = []
        for item in self.items:
            if item["status"] in ("CONTRADICTED", "EXPIRED") or item["expires_at_ms"] is None:
                continue
            if item["expires_at_ms"] <= now_ms:
                if self.is_raw_heard(item) and self._protected(item):
                    # D-70: kept while tied to an open promise or a correction. Its expiry is cleared;
                    # the next card about that person (or the cap) sets it again.
                    item["expires_at_ms"] = None
                    item["version"] += 1
                    self.events.append({"event": "RAW_HEARD_KEPT", "memory_id": item["memory_id"], "at_ms": now_ms})
                    continue
                if item["store"] == "COMMITMENTS_AND_REFUSALS":
                    item["content"]["commitment_state"] = "EXPIRED"
                    self.events.append({"event": "COMMITMENT_EXPIRED", "memory_id": item["memory_id"], "at_ms": now_ms})
                item["status"] = "EXPIRED"
                item["version"] += 1
                expired.append(item["memory_id"])
        return expired

    # ---------- commitments and refusals (D-13) ----------

    def reserve_id(self) -> str:
        """An id for an item that will be added later, if at all (G3d, D-64: a promise is recorded
        only once the world accepts the action that made it, under the id it was given then)."""
        return self._next_id()

    def commit(self, text: str, to_track: str | None, *, now_ms: int, ttl_ms: int = COMMITMENT_TTL_MS,
               tags: set[str] | None = None, memory_id: str | None = None) -> dict[str, Any]:
        while len(self.open_commitments()) >= MAX_OPEN_COMMITMENTS:
            oldest = self.open_commitments()[0]
            self.set_commitment_state(oldest["memory_id"], "RELEASED")
            self.events.append({"event": "COMMITMENT_RELEASED_CAP", "memory_id": oldest["memory_id"], "at_ms": now_ms})
        return self.add("COMMITMENTS_AND_REFUSALS", text, now_ms=now_ms, source_class="SELF", scope="PUBLIC",
                        importance="CRITICAL", expires_at_ms=now_ms + ttl_ms, shared_by=None,
                        audience=[to_track] if to_track else [], commitment_state="OPEN",
                        tags=(tags or set()) | ({to_track} if to_track else set()), memory_id=memory_id)

    def refuse(self, text: str, to_track: str | None, *, now_ms: int) -> dict[str, Any]:
        return self.add("COMMITMENTS_AND_REFUSALS", text, now_ms=now_ms, source_class="SELF", scope="PUBLIC",
                        importance="HIGH", audience=[to_track] if to_track else [], commitment_state="DECLINED",
                        tags={to_track} if to_track else set())

    def open_commitments(self) -> list[dict[str, Any]]:
        return [i for i in self.items if i["store"] == "COMMITMENTS_AND_REFUSALS"
                and i["content"].get("commitment_state") == "OPEN" and i["status"] not in ("EXPIRED", "CONTRADICTED")]

    def set_commitment_state(self, memory_id: str, state: str) -> None:
        item = self.get(memory_id)
        if item["store"] != "COMMITMENTS_AND_REFUSALS":
            raise MemoryRuleError("only commitments and refusals have a commitment state")
        item["content"]["commitment_state"] = state
        item["version"] += 1

    def commitments_to(self, track: str) -> list[dict[str, Any]]:
        return [i for i in self.open_commitments() if track in i["audience_present"]]

    # ---------- episode cards (compression step 3) ----------

    def add_episode_card(self, text: str, *, now_ms: int, scope: str, participants: set[str], topics: set[str],
                         source_event_id: str | None) -> dict[str, Any]:
        cards = [i for i in self.active("EPISODIC_LEDGER") if "card" in self.tags.get(i["memory_id"], set())]
        while len(cards) >= MAX_EPISODE_CARDS:
            lowest = min(cards, key=lambda c: (IMPORTANCE_RANK[c["importance"]], c["observed_at_ms"]))
            self.set_status(lowest["memory_id"], "EXPIRED")
            cards.remove(lowest)
        return self.add("EPISODIC_LEDGER", text, now_ms=now_ms, status="OBSERVED", source_class="SELF", scope=scope,
                        importance="NORMAL", audience=sorted(participants), source_event_id=source_event_id,
                        tags={"card"} | participants | topics)
