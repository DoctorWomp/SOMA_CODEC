"""The models of one run: Robot R's gateway and the NPC gateway (G3c-1, D-59).

``--model`` chooses Robot R's model as before (D-50, D-57). ``--npc-model`` chooses what drives
NPCs promoted to C1/C2:

- ``auto`` (default): follow ``--model``. ``none`` → NPCs keep their templates (G3a behavior);
  ``fake*`` → a fake model for NPCs too (deterministic: it repeats the NPC templates' choice);
  ``replay:FILE`` → the same recording (it holds NPC calls too); ``llama`` / ``llama:MODEL`` →
  Option C from configs/inference.yaml (the NPC server); ``llama-attach:PORT`` → the same
  attached server (Option B: NPCs use its shared slots).
- ``none``: NPCs keep their templates. With ``llama``, also no NPC server (Option B setup, unused).
- any other model spec: a separate gateway for NPCs (``llama:MODEL`` with a llama ``--model``
  overrides the NPC server's model; ``llama-attach:PORT`` attaches a second running server).

G3f (D-75 to D-78): ``fake-gpu[:PROFILE]`` is a fake model on a simulated shared GPU (agents/simgpu.py)
for Robot R and, with ``--npc-model auto``, ``fake-gpu:N3`` for NPCs, both on one simulated GPU with
the schedulers and deadlines of configs/inference.yaml: a stand-in for Option C contention. The
conditions (Robot R's prompt layout and answer limits, the focal-first GPU guard) come from
configs/inference.yaml ``focal`` and ``gpu_guard`` unless a run overrides them (``Conditions``).

Robot R only ever gets ``focal``; NPCs only ever get ``npc``. In Option C the NPC gateway also
refuses FOCAL calls, so a routing mistake fails loudly instead of landing on the wrong server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .gateway import ModelGateway, ServerActivity, gateway_from_spec

FAKE_KINDS = ("fake", "fake-slow:", "fake-malformed")
ANSWERS = ("FULL", "SHORT", "LEAN")


def _is_fake(spec: str) -> bool:
    return spec == "fake" or spec == "fake-malformed" or spec.startswith("fake-slow:")


def _is_simgpu(spec: str) -> bool:
    return spec == "fake-gpu" or spec.startswith("fake-gpu:")


@dataclass
class Conditions:
    """G3f run conditions (D-76 to D-78); None = configs/inference.yaml."""
    prompt_layout: str | None = None      # ONE_MESSAGE or SYSTEM_PREFIX
    answer: str | None = None             # FULL, SHORT (G3f, D-77) or LEAN (G3g, D-85)
    gpu_guard: bool | None = None
    npc_cap: int | None = None
    guard_hold: str | None = None         # G3g (D-89): ALL or DECISIONS
    salvage: bool | None = None           # G3g (D-86): use a cut-off answer's complete actions

    def resolve(self, inf: dict[str, Any]) -> dict[str, Any]:
        focal = inf.get("focal", {}) or {}
        guard = inf.get("gpu_guard", {}) or {}
        out = {"prompt_layout": self.prompt_layout or focal.get("prompt_layout", "ONE_MESSAGE"),
               "answer": self.answer or focal.get("answer", "FULL"),
               "gpu_guard": guard.get("enabled", False) if self.gpu_guard is None else self.gpu_guard,
               "npc_cap": guard.get("npc_cap", 0) if self.npc_cap is None else self.npc_cap,
               "guard_hold": self.guard_hold or guard.get("hold", "ALL"),
               "salvage": inf.get("salvage", True) if self.salvage is None else self.salvage}
        if out["prompt_layout"] not in ("ONE_MESSAGE", "SYSTEM_PREFIX") or out["answer"] not in ANSWERS \
                or not 0 <= int(out["npc_cap"]) <= 16 or out["guard_hold"] not in ("ALL", "DECISIONS"):
            raise ValueError(f"unknown focal condition {out}")
        return out


def _is_llama(spec: str) -> bool:
    return spec == "llama" or spec.startswith("llama:")


@dataclass
class RunModels:
    focal: ModelGateway | None
    _npc: ModelGateway | None = None
    inference: Any = None                 # InferenceSet in Option C/B with llama-server
    npc_spec: str = "none"
    prewarm: bool = True
    events: list[dict[str, Any]] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)   # resolved G3f conditions (D-76 to D-78)
    guard: Any = None                                           # FocalGuard when the GPU guard is on
    simgpu: Any = None                                          # the simulated GPU of a fake-gpu run

    @property
    def npc(self) -> ModelGateway | None:
        if self.inference is not None:
            return self.inference.npc_gateway if self.npc_spec != "none" else None
        return self._npc

    @property
    def option(self) -> str | None:
        if self.inference is not None:
            return self.inference.option
        if self.npc is None:
            return None
        if self.simgpu is not None:
            return "C_SIM"          # the fake-gpu stand-in for Option C (G3f)
        return "B" if self.npc is self.focal else "SEPARATE"

    def _apply_conditions(self) -> None:
        """Robot R's prompt layout and answer limits on its gateway; the GPU guard between the two
        servers when both exist (Option C, or the fake-gpu stand-in). Never in Option B."""
        c = self.conditions
        if not c or self.focal is None:
            return
        self.focal.prompt_layout = c["prompt_layout"]
        self.focal.answer = c["answer"]
        npc = self.npc
        for gw in {id(g): g for g in (self.focal, npc) if g is not None}.values():
            gw.salvage = bool(c.get("salvage", True))
        if c["gpu_guard"] and npc is not None and npc is not self.focal and npc.scheduler is not None:
            from .scheduler import FocalGuard   # noqa: PLC0415

            self.guard = FocalGuard(int(c["npc_cap"]), c.get("guard_hold", "ALL"))
            self.focal.guard = self.guard
            npc.scheduler.set_guard(self.guard)
            self.events.append({"event": "GPU_GUARD_ON", "npc_cap": int(c["npc_cap"]), "hold": self.guard.hold})
        elif c["gpu_guard"]:
            # Asked for, but there is no second server to hold back (Option B, or no scheduler):
            # recorded as off, never claimed (G3f).
            c["gpu_guard"] = False
            self.events.append({"event": "GPU_GUARD_NOT_APPLIED", "reason": "no separate NPC server with a scheduler"})

    async def start(self) -> None:
        if self.inference is not None:
            await self.inference.start()
            self.events += self.inference.events
            if self.inference.option == "C" and self.inference.npc is not None:
                shared = ServerActivity()          # both servers share one GPU (G3c-2, D-60)
                self.inference.focal.gateway.activity = shared
                self.inference.npc.gateway.activity = shared
            self._apply_conditions()
            return
        if self.focal is not None:
            await self.focal.start()
        if self._npc is not None and self._npc is not self.focal:
            try:
                await self._npc.start()
            except Exception:
                if self.focal is not None:
                    await self.focal.stop()
                raise
        if self.simgpu is not None and self.focal is not None and self._npc is not None:
            shared = ServerActivity()              # the stand-in's two "servers" share one simulated GPU
            self.focal.activity = shared
            self._npc.activity = shared
        self._apply_conditions()

    async def stop(self) -> None:
        if self.inference is not None:
            await self.inference.stop()
            return
        try:
            if self._npc is not None and self._npc is not self.focal:
                await self._npc.stop()
        finally:
            if self.focal is not None:
                await self.focal.stop()

    def manifest_settings(self) -> dict[str, Any]:
        out: dict[str, Any] = {"npc_model": self.npc_spec[-200:], "npc.prewarm": self.prewarm}
        if self.conditions:
            out.update({"focal.prompt_layout": self.conditions["prompt_layout"], "focal.answer": self.conditions["answer"],
                        "gpu_guard.enabled": self.guard is not None,
                        "gpu_guard.npc_cap": int(self.conditions["npc_cap"]) if self.guard is not None else None,
                        "gpu_guard.hold": self.guard.hold if self.guard is not None else None,
                        "salvage": bool(self.conditions.get("salvage", True))})
        if self.inference is not None:
            out.update(self.inference.manifest_settings())
        else:
            setup = getattr(self.focal, "setup", None)
            if setup is not None:
                out.update(setup.manifest_settings())
            out["inference.option"] = self.option
        return out


def resolve_npc_spec(model: str, npc_model: str) -> str:
    if npc_model != "auto":
        return npc_model
    if model == "none":
        return "none"
    if _is_fake(model):
        return "fake"
    if _is_simgpu(model):
        return "fake-gpu:N3"
    return model          # replay:FILE, llama, llama:MODEL, llama-attach:PORT


def models_from_specs(model: str, npc_model: str = "auto", *, run_dir: Path | None = None, seed: int | None = None,
                      prewarm: bool | None = None, snapshots: bool | None = None,
                      conditions: Conditions | None = None) -> RunModels:
    """Build (not start) the gateways of a run. Raises ValueError for an unknown spec and
    ProviderError when a llama model is not on this machine."""
    npc_spec = resolve_npc_spec(model, npc_model)
    resolved = (conditions or Conditions()).resolve(_inference_or_default())
    if _is_simgpu(model):
        rm = _simgpu_models(model, npc_spec, prewarm)
        rm.conditions = resolved
        return rm
    if _is_llama(model):
        from .inference import build_inference, load_inference   # noqa: PLC0415

        inf = load_inference()
        cfg = inf.get("personas", {"snapshots": True, "prewarm": True})
        if npc_spec not in ("none",) and not _is_llama(npc_spec):
            raise ValueError("with a llama --model, --npc-model must be auto, none, llama or llama:MODEL")
        if npc_model in ("auto", "llama"):
            npc_override = None                          # the NPC server's model from configs/inference.yaml
        elif npc_spec == "none":
            npc_override = "none"
        else:
            npc_override = npc_spec.split(":", 1)[1]     # llama:MODEL, even when it is Robot R's model
        if snapshots is not None:
            inf = dict(inf, personas=dict(cfg, snapshots=snapshots))
        iset = build_inference(model.split(":", 1)[1] if ":" in model else None, npc_override, run_dir=run_dir, seed=seed,
                               inference=inf, snapshots=snapshots)
        iset.focal.gateway.setup = iset.focal   # type: ignore[attr-defined]
        return RunModels(iset.focal.gateway, None, iset, npc_spec,
                         cfg.get("prewarm", True) if prewarm is None else prewarm, conditions=resolved)
    log = (run_dir / "llama_server.log") if run_dir else None
    focal = gateway_from_spec(model, log_path=log, seed=seed)
    if npc_spec == "none":
        npc = None
    elif npc_spec == model and model.startswith("llama-attach:"):
        npc = focal                              # Option B on an attached server
    else:
        npc = gateway_from_spec(npc_spec, log_path=(run_dir / "llama_server_npc.log") if run_dir else None, seed=seed)
    if npc is not None and npc is not focal and npc.server is None:
        npc.server = "npc" if getattr(npc.provider, "name", "") == "LLAMA_SERVER" else None
    if focal is not None and focal.server is None and getattr(focal.provider, "name", "") == "LLAMA_SERVER":
        focal.server = "focal"
    return RunModels(focal, npc, None, npc_spec, True if prewarm is None else prewarm, conditions=resolved)


def _inference_or_default() -> dict[str, Any]:
    from .inference import load_inference   # noqa: PLC0415

    return load_inference()


def _simgpu_models(model: str, npc_spec: str, prewarm: bool | None) -> RunModels:
    """Robot R and the NPCs on one simulated GPU (agents/simgpu.py), with the schedulers, slots and
    deadlines of configs/inference.yaml, as in Option C."""
    from .inference import load_inference, make_scheduler   # noqa: PLC0415
    from .simgpu import PROFILES, SimGpu, SimGpuModel   # noqa: PLC0415

    inf = load_inference()
    gpu = SimGpu()
    focal_profile = model.split(":", 1)[1] if ":" in model else "F3"
    deadlines = {t: s["deadline_ms"] for t, s in inf["tiers"].items()}
    system_prefix = inf.get("personas", {}).get("system_prefix", True)
    if focal_profile not in PROFILES:
        raise ValueError(f"unknown fake-gpu profile {focal_profile!r}: one of {', '.join(PROFILES)}")
    focal = ModelGateway(SimGpuModel(gpu, focal_profile, system_prefix), deadlines_ms=deadlines,
                         max_concurrent=inf["servers"]["focal"]["parallel_slots"],
                         scheduler=make_scheduler(inf, "focal"), server="focal")
    npc = None
    if npc_spec != "none":
        if not _is_simgpu(npc_spec):
            raise ValueError("with --model fake-gpu, --npc-model must be auto, none or fake-gpu:PROFILE")
        npc_profile = npc_spec.split(":", 1)[1] if ":" in npc_spec else "N3"
        if npc_profile not in PROFILES:
            raise ValueError(f"unknown fake-gpu profile {npc_profile!r}: one of {', '.join(PROFILES)}")
        npc_server = "npc" if "npc" in inf["servers"] else "focal"
        npc = ModelGateway(SimGpuModel(gpu, npc_profile, system_prefix, server="npc"), deadlines_ms=deadlines,
                           max_concurrent=inf["servers"][npc_server]["parallel_slots"],
                           scheduler=make_scheduler(inf, npc_server), server="npc")
        npc.refuse_tiers = frozenset({"FOCAL"})
    rm = RunModels(focal, npc, None, npc_spec, True if prewarm is None else prewarm)
    rm.simgpu = gpu
    return rm
