"""Headless test world: sight, frames and reproducibility (D-04)."""

from __future__ import annotations

import math

import pytest

from range_service import contracts
from range_service.configs import load_and_check
from range_service.testworld import Avatar, Command, TestWorld, Vec2, Wall, bearing, forward

# ---- geometry conventions (D-29: Godot frame) ----


def test_yaw_zero_faces_negative_z_and_positive_yaw_turns_left():
    f0 = forward(0.0)
    assert (f0.x, f0.z) == pytest.approx((0.0, -1.0))
    f90 = forward(math.pi / 2)
    assert (f90.x, f90.z) == pytest.approx((-1.0, 0.0))  # facing -z, left is -x
    origin = Vec2(0, 0)
    assert bearing(origin, 0.0, Vec2(0, -5)) == pytest.approx(0.0)
    assert bearing(origin, 0.0, Vec2(-5, 0)) == pytest.approx(math.pi / 2)  # left is positive
    assert bearing(origin, 0.0, Vec2(5, 0)) == pytest.approx(-math.pi / 2)
    assert abs(bearing(origin, 0.0, Vec2(0, 5))) == pytest.approx(math.pi)


# ---- line of sight (Assessment first-session test) ----


def _two_avatars(walls, target_at, fov=120.0, rng=20.0):
    world = TestWorld(seed=1, walls=walls)
    world.add_avatar(Avatar("robot_r", Vec2(0, 0), yaw_rad=0.0, fov_deg=fov, visual_range_m=rng))
    world.add_avatar(Avatar("visitor", target_at))
    return world


def test_avatar_in_view_is_observed():
    world = _two_avatars([], Vec2(0, -5))
    packet = world.observe("robot_r")
    contracts.validate("observation", packet)
    [item] = packet["observations"]
    assert item["kind"] == "VISUAL_PRESENCE"
    assert item["position_estimate"] == {"x": 0.0, "y": 0.0, "z": -5.0}
    assert item["validity"] == "OBSERVED"


def test_avatar_behind_wall_is_not_observed():
    wall = Wall("partition", Vec2(-2, -2.5), Vec2(2, -2.5), blocks_sight=True)
    world = _two_avatars([wall], Vec2(0, -5))
    assert world.observe("robot_r")["observations"] == []
    assert not world.can_see("robot_r", "visitor")


def test_wall_that_does_not_block_sight_is_ignored():
    glass = Wall("glass", Vec2(-2, -2.5), Vec2(2, -2.5), blocks_sight=False)
    assert _two_avatars([glass], Vec2(0, -5)).can_see("robot_r", "visitor")


def test_wall_beside_the_line_does_not_block():
    wall = Wall("partition", Vec2(1, -2.5), Vec2(3, -2.5), blocks_sight=True)
    assert _two_avatars([wall], Vec2(0, -5)).can_see("robot_r", "visitor")


def test_outside_field_of_view_is_not_observed():
    # 120° FOV facing -z: a target directly to the right (bearing -90°) is outside it.
    assert not _two_avatars([], Vec2(5, 0)).can_see("robot_r", "visitor")
    assert _two_avatars([], Vec2(5, 0), fov=360).can_see("robot_r", "visitor")


def test_out_of_range_is_not_observed():
    assert not _two_avatars([], Vec2(0, -30), rng=20.0).can_see("robot_r", "visitor")


def test_sandbox_flats_partition_blocks_sight():
    config_set, problems = load_and_check()
    assert not problems
    world = TestWorld.from_map_config(config_set.items["maps"]["sandbox_flats"], seed=1)
    # Robot west of partition_a (x=10, z 6..12) facing east (+x is yaw -90°).
    # The sight line to "behind" crosses x=10 at z=7 (inside the partition);
    # the line to "visible" crosses at z=4 (past its end).
    world.add_avatar(Avatar("robot_r", Vec2(7, 5), yaw_rad=-math.pi / 2, fov_deg=120))
    world.add_avatar(Avatar("behind", Vec2(13, 9)))
    world.add_avatar(Avatar("visible", Vec2(13, 3)))
    seen = world.observe("robot_r")["observations"]
    assert [o["track_id"] for o in seen] == [world.track_id("robot_r", "visible")]
    # "behind" is in range and field of view, so only the partition hides it.
    world.walls = [w for w in world.walls if w.wall_id != "partition_a"]
    assert world.can_see("robot_r", "behind")


# ---- L0 frames (Atlas L0 test, SB-01 simplified) ----


def test_rotating_robot_keeps_stationary_avatar_fixed_in_world():
    world = TestWorld(seed=3)
    world.add_avatar(Avatar("robot_r", Vec2(15, 10), yaw_rad=0.0, fov_deg=360))
    world.add_avatar(Avatar("speaker", Vec2(15, 6)))
    turns = [Command(tick=t, op="TURN_BY", avatar_id="robot_r", dyaw_rad=math.radians(30)) for t in range(1, 12)]
    journal = world.run(turns, ticks=12, observers=["robot_r"])

    packets = [e["payload"] for e in journal.entries if e["kind"] == "OBSERVATION_DELIVERED"]
    assert len(packets) == 12
    positions = {(p["observations"][0]["position_estimate"]["x"], p["observations"][0]["position_estimate"]["z"])
                 for p in packets}
    assert positions == {(15.0, 6.0)}  # world position never moves
    bearings = [p["observations"][0]["bearing_rad"] for p in packets]
    assert len({round(b, 6) for b in bearings}) == 12  # robot-relative bearing changes every tick
    for p in packets:
        yaw = p["observer_pose"]["yaw_rad"]
        # bearing + robot yaw always points at the same world direction (straight to -z)
        assert math.remainder(p["observations"][0]["bearing_rad"] + yaw, math.tau) == pytest.approx(0.0, abs=1e-5)


# ---- reproducibility (Blueprint T28 groundwork) ----


def _scripted_run(seed):
    world = TestWorld(seed=seed)
    world.add_avatar(Avatar("robot_r", Vec2(0, 0), fov_deg=360, dropout_rate=0.3))
    for i in range(5):
        world.add_avatar(Avatar(f"visitor_{i}", Vec2(i - 2.0, -4.0)))
    script = [
        Command(tick=2, op="MOVE_BY", avatar_id="visitor_0", dx=0.5, dz=0.0),
        Command(tick=4, op="TURN_BY", avatar_id="robot_r", dyaw_rad=0.4),
        Command(tick=6, op="SET_POSE", avatar_id="visitor_4", x=3.0, z=-1.0, yaw_rad=1.0),
    ]
    return world.run(script, ticks=20, observers=["robot_r"])


def test_same_seed_and_inputs_give_identical_journal_hash():
    a, b = _scripted_run(42), _scripted_run(42)
    assert a.to_jsonl() == b.to_jsonl()
    assert a.sha256() == b.sha256()


def test_different_seed_gives_different_journal_beyond_the_header():
    a, b = _scripted_run(42), _scripted_run(43)
    assert a.sha256() != b.sha256()
    # The difference must come from seeded behavior, not only from the seed in RUN_STARTED.
    body_a = a.to_jsonl().splitlines()[1:]
    body_b = b.to_jsonl().splitlines()[1:]
    assert body_a != body_b


def test_every_journal_line_matches_the_contract(tmp_path):
    journal = _scripted_run(42)
    kinds = set()
    for entry in journal.entries:
        contracts.validate("journal_entry", entry)
        kinds.add(entry["kind"])
    assert {"RUN_STARTED", "COMMAND_APPLIED", "OBSERVATION_DELIVERED", "OBSERVATION_DROPPED", "RUN_ENDED"} <= kinds
    out = journal.write(tmp_path / "journal.jsonl")
    assert out.read_text(encoding="utf-8") == journal.to_jsonl()
    assert [e["seq"] for e in journal.entries] == list(range(len(journal.entries)))


def test_bad_inputs_are_rejected():
    with pytest.raises(ValueError):
        TestWorld(seed=-1)
    with pytest.raises(ValueError):
        Command(tick=-1, op="MOVE_BY", avatar_id="a")
    with pytest.raises(ValueError):
        Command(tick=0, op="TELEPORT", avatar_id="a")
