"""The sidecar end of the link (D-05, D-43), tested with a Python WebSocket client standing in
for Godot. The Godot end is tested in godot_app/tests/ through tools/godot_check.py."""

from __future__ import annotations

import asyncio
import json

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from range_service import contracts
from range_service.link.sidecar import CLOSE_BUSY, CLOSE_UNAUTHORIZED, MAX_MESSAGE_BYTES, TOKEN_HEADER, Sidecar

TOKEN = "t" * 32


def envelope(kind: str, payload: dict, tick: int = 600) -> str:
    return json.dumps({"schema_version": "1.0", "message_id": f"msg_{tick:06d}", "type": kind, "tick_id": tick,
                       "sim_time_ms": tick * 1000 // 60, "source": "godot_world", "payload": payload})


HELLO = {"protocol": "range-link/1", "agents": ["robot_legged", "robot_quadruped"], "tick_hz": 60, "sample_hz": 10,
         "map_id": "sandbox_flats"}


def packet(observer: str, items: list[dict], tick: int = 600) -> dict:
    return {"schema_version": "1.0", "observer_id": observer, "based_on_tick_id": tick, "sim_time_ms": tick * 1000 // 60,
            "coordinate_frame": "world_meters_xyz", "observer_pose": {"x": 15.0, "y": 0.0, "z": 15.5, "yaw_rad": 0.0},
            "observations": items}


def wave(track: str, n: int = 1) -> dict:
    return {"observation_id": f"obs_{n:06d}", "event_id": "evt_000001", "kind": "VISUAL_GESTURE", "track_id": track,
            "source_entity_id": None, "position_estimate": {"x": 15.0, "y": 0.0, "z": 12.5}, "bearing_rad": 0.0,
            "range_m": 3.0, "value": {"gesture": "WAVE", "direction": "TOWARD_OBSERVER"}, "observed_at_ms": 10000,
            "expires_at_ms": 11000, "validity": "OBSERVED", "quality": 0.8, "provenance": "synthetic_visual_multipoint_v1"}


def speech(text: str, addressed, track: str | None = "anon_visitor0001", n: int = 2) -> dict:
    return {"observation_id": f"obs_{n:06d}", "event_id": f"evt_{n:06d}", "kind": "AUDIO_SPEECH", "track_id": track,
            "source_entity_id": None, "position_estimate": {"x": 15.0, "y": 0.0, "z": 14.0} if track else None,
            "bearing_rad": 0.0, "range_m": 1.5 if track else None,
            "value": {"channel": "LOCAL", "text": text, "addressed_to_observer": addressed}, "observed_at_ms": 10000,
            "expires_at_ms": 11000, "validity": "OBSERVED" if track else "UNKNOWN_SOURCE", "quality": 0.9,
            "provenance": "synthetic_acoustic_v1"}


def presence(track: str, n: int = 3, range_m: float = 1.5) -> dict:
    return {"observation_id": f"obs_{n:06d}", "event_id": None, "kind": "VISUAL_PRESENCE", "track_id": track,
            "source_entity_id": None, "position_estimate": {"x": 15.0, "y": 0.0, "z": 14.0}, "bearing_rad": 0.0,
            "range_m": range_m, "value": {}, "observed_at_ms": 10000, "expires_at_ms": 11000, "validity": "OBSERVED",
            "quality": 0.9, "provenance": "synthetic_visual_multipoint_v1"}


def run(coro):
    return asyncio.run(coro)


async def started(**kwargs) -> Sidecar:
    sidecar = Sidecar(TOKEN, {"robot_legged": "greeter", "robot_quadruped": "quiet"}, **kwargs)
    await sidecar.start()
    return sidecar


def url(sidecar: Sidecar) -> str:
    return f"ws://127.0.0.1:{sidecar.port}"


def test_binds_loopback_only():
    async def go():
        sidecar = await started()
        hosts = sidecar.bound_hosts()
        await sidecar.stop()
        return hosts
    assert run(go()) == ["127.0.0.1"]


async def closed_with(sidecar: Sidecar, headers: dict) -> int | None:
    """Connect, try to talk, and return the close code the sidecar sent."""
    async with connect(url(sidecar), additional_headers=headers) as ws:
        try:
            await ws.send(envelope("link.hello", HELLO))
            await asyncio.wait_for(ws.recv(), 2)
        except ConnectionClosed as closed:
            return closed.rcvd.code if closed.rcvd else None
    return None


@pytest.mark.parametrize("headers", [{}, {TOKEN_HEADER: "wrong-token-wrong-token"}, {TOKEN_HEADER: TOKEN[:-1]}])
def test_missing_or_wrong_token_is_refused(headers):
    async def go():
        sidecar = await started()
        try:
            code = await closed_with(sidecar, headers)
            return code, sidecar.refused, sidecar.connections, sidecar.received
        finally:
            await sidecar.stop()
    code, refused, connections, received = run(go())
    assert code == CLOSE_UNAUTHORIZED and refused == 1 and connections == 0
    assert received == []      # nothing it sent was read


def test_short_tokens_are_not_accepted_at_all():
    with pytest.raises(ValueError):
        Sidecar("short", {})


def test_greeter_answers_a_wave_with_valid_action_requests(tmp_path):
    async def go():
        sidecar = await started(record_dir=tmp_path)
        async with connect(url(sidecar), additional_headers={TOKEN_HEADER: TOKEN}) as ws:
            await ws.send(envelope("link.hello", HELLO))
            await ws.send(envelope("world.observation", packet("robot_legged", [wave("anon_visitor0001")])))
            replies = [json.loads(await asyncio.wait_for(ws.recv(), 2)) for _ in range(3)]
        await sidecar.stop()
        return replies
    hello, *replies = run(go())
    # The sidecar answers link.hello with the agents it runs (G3a, D-48).
    assert hello["type"] == "link.hello" and hello["payload"]["agents"] == ["robot_legged", "robot_quadruped"]
    assert [r["payload"]["action"] for r in replies] == ["GESTURE", "SPEAK"]
    for r in replies:
        assert r["type"] == "agent.action_request" and contracts.problems("envelope", r) == []
        assert r["payload"]["agent_id"] == "robot_legged" and "token" not in json.dumps(r).lower()
    assert replies[0]["payload"]["args"]["target_id"] == "anon_visitor0001"


def test_invalid_and_unknown_messages_are_ignored_not_acted_on(tmp_path):
    async def go():
        sidecar = await started(record_dir=tmp_path)
        async with connect(url(sidecar), additional_headers={TOKEN_HEADER: TOKEN}) as ws:
            await ws.send("not json")
            await ws.send(envelope("world.weather", {}))
            await ws.send(envelope("link.hello", dict(HELLO, session_token=TOKEN)))   # a token in an envelope
            leaked = packet("robot_legged", [wave("anon_visitor0001")])
            leaked["private_goal"] = "find the cafe"                                  # evaluator-only field
            await ws.send(envelope("world.observation", leaked))
            await ws.send(envelope("link.heartbeat", {}))
            reply = json.loads(await asyncio.wait_for(ws.recv(), 2))
        await sidecar.stop()
        return sidecar, reply
    sidecar, reply = run(go())
    assert reply["type"] == "link.heartbeat"     # still connected and answering
    assert len(sidecar.problems) == 4
    assert sidecar.agents == {}                  # the invalid hello created nobody
    assert (tmp_path / "sidecar_problems.jsonl").is_file()


def test_oversized_messages_close_the_connection():
    async def go():
        sidecar = await started()
        try:
            async with connect(url(sidecar), additional_headers={TOKEN_HEADER: TOKEN}, max_size=None) as ws:
                await ws.send("x" * (MAX_MESSAGE_BYTES + 1))
                with pytest.raises(ConnectionClosed) as err:
                    await asyncio.wait_for(ws.recv(), 2)
                return err.value.rcvd.code if err.value.rcvd else None
        finally:
            await sidecar.stop()
    assert run(go()) == 1009   # message too big


def test_one_client_at_a_time():
    async def go():
        sidecar = await started()
        try:
            async with connect(url(sidecar), additional_headers={TOKEN_HEADER: TOKEN}) as first:
                await first.send(envelope("link.heartbeat", {}))
                await asyncio.wait_for(first.recv(), 2)
                return await closed_with(sidecar, {TOKEN_HEADER: TOKEN})
        finally:
            await sidecar.stop()
    assert run(go()) == CLOSE_BUSY


def test_t17_agents_keep_private_memories(tmp_path):
    """T17: a secret told to one agent stays in that agent's memory; another agent never gets it,
    and overheard speech is never stored by anyone."""
    async def go():
        sidecar = await started(record_dir=tmp_path)
        async with connect(url(sidecar), additional_headers={TOKEN_HEADER: TOKEN}) as ws:
            await ws.send(envelope("link.hello", HELLO))
            told = packet("robot_legged", [presence("anon_visitor0001"), speech("My locker code is 4417.", True)])
            overheard = packet("robot_quadruped", [speech("Meet me at the back door.", False, n=5)])
            await ws.send(envelope("world.observation", told))
            await ws.send(envelope("world.observation", overheard))
            await ws.send(envelope("link.heartbeat", {}))
            await asyncio.wait_for(ws.recv(), 2)
        await sidecar.stop()
        return json.loads((tmp_path / "agent_memory.json").read_text())
    memory = run(go())
    legged, quad = memory["robot_legged"], memory["robot_quadruped"]
    assert len(legged) == 1 and legged[0]["scope"] == "ONE_TO_ONE" and legged[0]["shared_by"] == "anon_visitor0001"
    assert contracts.problems("memory_item", legged[0]) == []
    assert quad == []                                 # overheard: not stored
    assert "4417" not in json.dumps(quad)
