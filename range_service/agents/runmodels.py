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

Robot R only ever gets ``focal``; NPCs only ever get ``npc``. In Option C the NPC gateway also
refuses FOCAL calls, so a routing mistake fails loudly instead of landing on the wrong server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .gateway import ModelGateway, gateway_from_spec

FAKE_KINDS = ("fake", "fake-slow:", "fake-malformed")


def _is_fake(spec: str) -> bool:
    return spec == "fake" or spec == "fake-malformed" or spec.startswith("fake-slow:")


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
        return "B" if self.npc is self.focal else "SEPARATE"

    async def start(self) -> None:
        if self.inference is not None:
            await self.inference.start()
            self.events += self.inference.events
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
    return model          # replay:FILE, llama, llama:MODEL, llama-attach:PORT


def models_from_specs(model: str, npc_model: str = "auto", *, run_dir: Path | None = None, seed: int | None = None,
                      prewarm: bool | None = None) -> RunModels:
    """Build (not start) the gateways of a run. Raises ValueError for an unknown spec and
    ProviderError when a llama model is not on this machine."""
    npc_spec = resolve_npc_spec(model, npc_model)
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
        iset = build_inference(model.split(":", 1)[1] if ":" in model else None, npc_override, run_dir=run_dir, seed=seed,
                               inference=inf)
        iset.focal.gateway.setup = iset.focal   # type: ignore[attr-defined]
        return RunModels(iset.focal.gateway, None, iset, npc_spec,
                         cfg.get("prewarm", True) if prewarm is None else prewarm)
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
    return RunModels(focal, npc, None, npc_spec, True if prewarm is None else prewarm)
