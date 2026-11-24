"""Who may do what (G4a, D-90; INTERACTION_MODES §2.2).

The table is ``configs/permissions.yaml`` (contract ``permissions``). Godot's world dispatcher
(``godot_app/scripts/comms/world_dispatcher.gd``) enforces it for every request; this module is its
Python mirror, used to filter the viewer feed (``feed.py``) and by the tests, which compare both
sides answer for answer. Keep ``check`` and ``world_dispatcher.gd``'s ``decide`` the same.

Result codes:
- ``OK``                the principal may do it (``logged``: the use goes to the operator log)
- ``PERMISSION_DENIED`` the principal has no grant for the capability
- ``NOT_OWN_AVATAR``    a participant asked about a body that is not its own
- ``NOT_CONTROLLED``    the agent session asked about an avatar it does not drive
- ``NOT_BUILT``         allowed, but the gate that builds it has not been built (``gate``)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

SEATS = ("SPECTATOR", "DIRECTOR", "PARTICIPANT", "EVALUATOR")
INTERNAL = ("AGENT", "HOST")
PRINCIPALS = SEATS + INTERNAL
CODES = ("OK", "PERMISSION_DENIED", "NOT_OWN_AVATAR", "NOT_CONTROLLED", "NOT_BUILT")
# Controllers the agent session runs (D-91). HUMAN_INPUT is a participant's; REPLAY_TAPE plays itself.
AGENT_CONTROLLERS = ("SCRIPTED", "LLM_AGENT")
CONTROLLERS = ("SCRIPTED", "LLM_AGENT", "HUMAN_INPUT", "REPLAY_TAPE")


@dataclass(frozen=True)
class Decision:
    code: str
    logged: bool = False
    gate: str | None = None

    @property
    def ok(self) -> bool:
        return self.code == "OK"


def load_table(config_set: Any = None) -> dict[str, Any]:
    """The checked permissions table (configs/permissions.yaml)."""
    if config_set is None:
        from range_service.configs import load_and_check   # noqa: PLC0415

        config_set, problems = load_and_check()
        if problems:
            raise ValueError(f"configs have problems: {problems[0]}")
    return config_set.items["permissions"]["permissions"]


def check(table: dict[str, Any], principal: str, capability: str, target: str | None = None,
          own_avatar: str | None = None, controlled: Iterable[str] = ()) -> Decision:
    """May ``principal`` use ``capability`` on ``target`` (an avatar id, or None)?

    ``own_avatar``: the participant seat's own body; ``controlled``: the avatars the agent session
    drives (linked, with a controller in AGENT_CONTROLLERS)."""
    cap = table["capabilities"].get(capability)
    if cap is None or principal not in PRINCIPALS:
        return Decision("PERMISSION_DENIED")
    scope = cap["grants"].get(principal)
    if scope is None:
        return Decision("PERMISSION_DENIED")
    if scope == "OWN_AVATAR" and (own_avatar is None or target != own_avatar):
        return Decision("NOT_OWN_AVATAR")
    if scope == "CONTROLLED" and target not in set(controlled):
        return Decision("NOT_CONTROLLED")
    logged = principal in cap.get("logged_for", [])
    if not cap["built"]:
        return Decision("NOT_BUILT", logged=logged, gate=cap.get("gate"))
    return Decision("OK", logged=logged)


def audiences_for(table: dict[str, Any], principal: str, observer: str | None = None,
                  own_avatar: str | None = None) -> set[str]:
    """Which viewer-record audiences (OBSERVER, EVALUATOR) ``principal`` may read for ``observer``."""
    return {aud for aud, cap in table["audiences"].items()
            if check(table, principal, cap, target=observer, own_avatar=own_avatar).ok}


def readable(table: dict[str, Any], principal: str, records: Iterable[dict[str, Any]],
             own_avatar: str | None = None) -> list[dict[str, Any]]:
    """The viewer records ``principal`` may read; everything else is left out, never masked."""
    out = []
    for record in records:
        observer = record.get("observer")
        if record["audience"] in audiences_for(table, principal, observer, own_avatar):
            out.append(record)
    return out


def matrix(table: dict[str, Any]) -> dict[str, str]:
    """Every principal x capability x target case as "PRINCIPAL CAPABILITY CASE" -> code. Godot's
    dispatcher computes the same matrix in its tests; tools/godot_check.py compares them."""
    cases = {"any": ("visitor_y", None, ()), "own": ("visitor_y", "visitor_y", ()),
             "other": ("robot_r", "visitor_y", ()), "controlled": ("robot_r", None, ("robot_r",)),
             "not_controlled": ("visitor_y", None, ("robot_r",))}
    out = {}
    for principal in PRINCIPALS:
        for capability in sorted(table["capabilities"]):
            for case, (target, own, ctl) in cases.items():
                out[f"{principal} {capability} {case}"] = check(table, principal, capability, target, own, ctl).code
    return out


def table_problems(table: dict[str, Any]) -> list[str]:
    """Rules the schema cannot say: scopes fit their principals; internal principals only act."""
    problems = []
    for name, cap in sorted(table["capabilities"].items()):
        for principal, scope in sorted(cap["grants"].items()):
            if scope == "CONTROLLED" and principal != "AGENT":
                problems.append(f"capabilities.{name}: only AGENT has the CONTROLLED scope, not {principal}")
            if scope == "OWN_AVATAR" and principal != "PARTICIPANT":
                problems.append(f"capabilities.{name}: only PARTICIPANT has the OWN_AVATAR scope, not {principal}")
            if principal in INTERNAL and name != "ACT_IN_WORLD":
                problems.append(f"capabilities.{name}: {principal} is internal and may only act in the world "
                                "(agents never open a view, D-90)")
        for principal in cap.get("logged_for", []):
            if principal not in cap["grants"]:
                problems.append(f"capabilities.{name}.logged_for: {principal} has no grant to log")
    truth = table["capabilities"].get("VIEW_EVALUATOR_TRUTH", {}).get("grants", {})
    if set(truth) != {"EVALUATOR"}:
        problems.append("capabilities.VIEW_EVALUATOR_TRUTH: only the EVALUATOR seat may hold it (D-90)")
    return problems
