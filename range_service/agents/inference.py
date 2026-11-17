"""Real-model setup from configs/inference.yaml (G3b; D-20, D-21, D-50, D-55).

Turns the inference settings and the local model registry into a started llama-server and a
ModelGateway, and describes the exact model file for run manifests (D-55: the quantization is
part of a model's identity; record file, quant, SHA-256, engine build and KV cache type).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from range_service import contracts
from range_service.configs import CONFIGS_DIR, load_yaml
from range_service.models import registry as reg

from .gateway import ModelGateway, ProviderError
from .llama import LlamaProvider, LlamaServer, ServerSettings, ServerTokenizer, default_binary
from .scheduler import SlotScheduler

INFERENCE_PATH = CONFIGS_DIR / "inference.yaml"
ENGINE = "llama.cpp b12443"   # tools/install_llama.py VERSION


def load_inference(path: Path = INFERENCE_PATH) -> dict[str, Any]:
    data = load_yaml(path)
    found = contracts.problems("inference", data)
    if found:
        raise ProviderError(f"{path.name}: {found[0]}")
    return data


@dataclass
class ResolvedModel:
    model_id: str
    path: Path
    sha256: str
    quant: str | None
    catalog_label: str | None


def resolve_model(name: str, registry: reg.Registry | None = None, catalog: dict[str, Any] | None = None) -> ResolvedModel:
    """A catalog id or label, or a registry local id, to a file on this machine."""
    registry = registry or reg.Registry.load()
    catalog = catalog or reg.load_catalog()
    model_id = name
    label = None
    for entry in catalog["models"]:
        if name in (entry["id"], entry["label"]):
            model_id, label = entry["id"], entry["label"]
    found = registry.find(model_id)
    if found is None:
        raise ProviderError(f"model {name!r} is not on this machine. Run: uv run python tools/models.py plan "
                            "(then scan a folder that has it, or download it)")
    return ResolvedModel(found["local_id"], Path(found["path"]), found["sha256"], found["header"]["quantization"], label)


@dataclass
class LlamaSetup:
    gateway: ModelGateway
    provider: LlamaProvider
    model: ResolvedModel
    settings: dict[str, Any]

    def tokenizer(self) -> ServerTokenizer:
        return ServerTokenizer(self.provider.port, self.provider.api_key, self.model.model_id)

    def manifest_settings(self) -> dict[str, Any]:
        server = self.settings
        return {
            "model.engine": ENGINE, "model.file": self.model.path.name[:200], "model.id": self.model.model_id,
            "model.catalog_label": self.model.catalog_label, "model.quant": self.model.quant,
            "model.sha256": self.model.sha256, "model.kv_cache_type": server["kv_cache_type"],
            "model.parallel_slots": server["parallel_slots"], "model.context_per_slot": server["context_per_slot"],
            "model.thinking": self.provider.thinking, "model.structured_output": self.provider.structured_output,
            "model.temperature": self.provider.sampling.get("temperature"),
            "model.scheduler": "PRIORITY" if self.gateway.scheduler is not None else "FIFO",
        }


def build_llama(model: str | None = None, *, server_name: str = "focal", kv_cache_type: str | None = None,
                log_path: Path | None = None, seed: int | None = None, inference: dict[str, Any] | None = None,
                binary: Path | None = None, slot_save_path: Path | None = None,
                warm_up: bool | None = None) -> LlamaSetup:
    """A not-yet-started llama-server setup. ``model``/``kv_cache_type`` override the config.
    ``slot_save_path`` enables persona snapshots on this server (T5, ``--slot-save-path``)."""
    inf = inference or load_inference()
    server = dict(inf["servers"][server_name])
    if kv_cache_type:
        server["kv_cache_type"] = kv_cache_type
    resolved = resolve_model(model or server["model"])
    if binary is None:
        configured = inf["engine"]["binary"]
        binary = default_binary() if configured == "auto" else Path(configured)
    if binary is None:
        raise ProviderError("llama-server is not installed. Run: uv run python tools/install_llama.py")
    settings = ServerSettings(server_name, resolved.path, f"{resolved.model_id}@{resolved.sha256[:12]}",
                              resolved.sha256, server["parallel_slots"], server["context_per_slot"],
                              server["kv_cache_type"], server["flash_attention"], server["gpu_layers"],
                              thinking=inf["thinking"], slot_save_path=slot_save_path)
    sampling = dict(inf["sampling"])
    if sampling.get("seed", 0) == 0 and seed:
        sampling["seed"] = seed
    pinned = tuple(t for t, s in inf["tiers"].items() if s["pin_slot"] and s["server"] == server_name)
    provider = LlamaProvider(server=LlamaServer(binary, settings, log_path, inf["engine"]["startup_timeout_s"]),
                             pinned_tiers=pinned, sampling=sampling, structured_output=inf["structured_output"],
                             warm_up=inf["engine"]["warm_up"] if warm_up is None else warm_up,
                             system_prefix=inf.get("personas", {}).get("system_prefix", True))
    gateway = ModelGateway(provider, deadlines_ms={t: s["deadline_ms"] for t, s in inf["tiers"].items()},
                           max_concurrent=server["parallel_slots"], scheduler=make_scheduler(inf, server_name),
                           server=server_name)
    return LlamaSetup(gateway, provider, resolved, server)


def make_scheduler(inf: dict[str, Any], server_name: str = "focal") -> SlotScheduler | None:
    """Option B (PRIORITY) from configs/inference.yaml, or None for FIFO (Option A)."""
    sched = inf["scheduler"]
    if sched["mode"] != "PRIORITY":
        return None
    server = inf["servers"][server_name]
    pinned = tuple(t for t, s in inf["tiers"].items() if s["pin_slot"] and s["server"] == server_name)
    # Slots are reserved only on a server that pinned tiers use (Robot R's); the NPC server
    # shares all of its slots (Option C, G3c-1).
    return SlotScheduler(server["parallel_slots"], pinned_tiers=pinned, reserved=sched["reserved_slots"] if pinned else 0,
                         priorities=sched["priorities"], aging_ms=sched["aging_ms"],
                         min_service_ms=sched["min_service_ms"])


# ---------- Option C: a focal server and an NPC server (G3c-1, D-59; INFERENCE_STRATEGY T2) ----------

DEFAULT_VRAM = {"budget_mib": 16376, "reserve_mib": 2048, "compute_buffer_mib": 512, "over_budget": "FALLBACK"}
# Used when a model file's header does not give its KV size: about 8B-class GQA at f16.
KV_RULE_OF_THUMB_BYTES_F16 = 128 * 1024


def npc_server_name(inf: dict[str, Any]) -> str | None:
    """The server C1/C2 agents use, if it is not Robot R's (Option C); None in Option A/B."""
    focal = inf["tiers"]["FOCAL"]["server"]
    names = {inf["tiers"][t]["server"] for t in ("C2", "C1")} - {focal}
    if len(names) > 1:
        raise ProviderError("configs/inference.yaml: C2 and C1 must use the same NPC server")
    return next(iter(names), None)


def estimate_server_mib(model: ResolvedModel, server: dict[str, Any], vram: dict[str, Any]) -> dict[str, Any]:
    """VRAM estimate for one server: model file + KV cache for all its slots + a compute buffer.
    The KV size comes from the GGUF header where it can (an upper bound for sliding-window and
    hybrid models), else a stated rule of thumb. An estimate, never a measurement."""
    from range_service.models import gguf   # noqa: PLC0415

    file_mib = model.path.stat().st_size / 2**20 if model.path.is_file() else None
    tokens = server["parallel_slots"] * server["context_per_slot"]
    per_token, source = None, "rule of thumb (128 KiB per token at f16)"
    try:
        per_token, source = gguf.kv_bytes_per_token(gguf.read_meta(model.path), server["kv_cache_type"])
    except (OSError, gguf.GGUFError):
        source = "model header unreadable; rule of thumb (128 KiB per token at f16)"
    if per_token is None:
        per_token = KV_RULE_OF_THUMB_BYTES_F16 * gguf.KV_BYTES[server["kv_cache_type"]] / 2
        source = f"rule of thumb (128 KiB per token at f16); {source}"
    kv_mib = per_token * tokens / 2**20
    total = (file_mib or 0) + kv_mib + vram["compute_buffer_mib"]
    return {"model_mib": round(file_mib) if file_mib is not None else None, "kv_mib": round(kv_mib),
            "kv_source": source, "compute_buffer_mib": vram["compute_buffer_mib"], "total_mib": round(total)}


@dataclass
class InferenceSet:
    """The model servers of one run. ``option`` is C (focal + NPC server) or B (one server: NPCs
    use the focal server's shared slots). Robot R only ever uses ``focal``. Both servers are
    127.0.0.1-only children with their own port and API key, started and stopped together. If
    the NPC server is not configured, would not fit the VRAM budget, or fails to start, the run
    falls back to Option B and says so in ``events`` (never silently)."""

    focal: LlamaSetup
    npc: LlamaSetup | None
    inference: dict[str, Any]
    option: str = "C"
    events: list[dict[str, Any]] = field(default_factory=list)
    vram: dict[str, Any] = field(default_factory=dict)
    npc_off_reason: str = "no NPC server configured (C1/C2 tiers use the focal server)"

    @property
    def npc_gateway(self) -> ModelGateway:
        return self.npc.gateway if self.npc is not None and self.option == "C" else self.focal.gateway

    def _event(self, kind: str, **data: Any) -> None:
        self.events.append({"event": kind, "at_unix_s": round(time.time(), 3), **data})

    def _fallback(self, reason: str) -> None:
        self.option = "B"
        self._event("OPTION_C_FALLBACK", option="B", reason=reason[:300])

    async def start(self) -> None:
        from range_service.eval.bakeoff import gpu_memory_used_mib, vram_mib   # noqa: PLC0415

        vram_cfg = dict(DEFAULT_VRAM, **self.inference.get("vram", {}))
        est = {"focal": estimate_server_mib(self.focal.model, self.focal.settings, vram_cfg)}
        if self.npc is not None:
            est["npc"] = estimate_server_mib(self.npc.model, self.npc.settings, vram_cfg)
        est_total = sum(e["total_mib"] for e in est.values()) + vram_cfg["reserve_mib"]
        self.vram = {"budget_mib": vram_cfg["budget_mib"], "reserve_mib": vram_cfg["reserve_mib"],
                     "estimate": est, "estimate_total_mib": est_total, "measured": {}}
        before = gpu_memory_used_mib()
        await self.focal.gateway.start()                        # Robot R's server is required
        proc = self.focal.provider.server.process if self.focal.provider.server else None
        focal_mib, focal_note = vram_mib(proc.pid if proc else None, before)
        self.vram["measured"]["focal"] = {"mib": focal_mib, "note": focal_note}
        if self.npc is None:
            self._fallback(self.npc_off_reason)
            return
        # Robot R's server is running now, so its real use replaces the estimate where it can be
        # measured. The header estimate is an upper bound that can be far too high for
        # sliding-window models (Gemma 4 12B: ~17 GB estimated on the owner's PC, 2026-11-17).
        focal_basis, focal_label = est["focal"]["total_mib"], "focal"
        if focal_mib is not None:
            focal_basis, focal_label = focal_mib, "focal measured"
        need = focal_basis + est["npc"]["total_mib"] + vram_cfg["reserve_mib"]
        self.vram["fit_check_mib"] = need
        self.vram["fit_check_basis"] = "focal measured + NPC estimate" if focal_mib is not None else "estimates"
        if need > vram_cfg["budget_mib"]:
            msg = (f"VRAM {need} MiB ({focal_label} {focal_basis} + NPC estimate {est['npc']['total_mib']} "
                   f"+ reserve {vram_cfg['reserve_mib']}) is over the {vram_cfg['budget_mib']} MiB budget")
            if vram_cfg["over_budget"] == "FALLBACK":
                self.npc = None
                self._fallback(msg)
                return
            self._event("VRAM_ESTIMATE_OVER_BUDGET", detail=msg)
        mid = gpu_memory_used_mib()
        try:
            await self.npc.gateway.start()
        except ProviderError as exc:
            await self.npc.gateway.stop()
            self.npc = None
            self._fallback(f"the NPC server did not start: {exc}")
            return
        proc = self.npc.provider.server.process if self.npc.provider.server else None
        npc_mib, npc_note = vram_mib(proc.pid if proc else None, mid)
        self.vram["measured"]["npc"] = {"mib": npc_mib, "note": npc_note}
        if focal_mib is not None and npc_mib is not None:
            used = focal_mib + npc_mib + vram_cfg["reserve_mib"]
            self.vram["measured_total_mib"] = used
            if used > vram_cfg["budget_mib"]:
                self._event("VRAM_MEASURED_OVER_BUDGET", detail=f"{focal_mib} + {npc_mib} + reserve "
                            f"{vram_cfg['reserve_mib']} MiB is over the {vram_cfg['budget_mib']} MiB budget")
        self.npc.gateway.refuse_tiers = frozenset({"FOCAL"})   # Robot R never lands on the NPC server
        self._event("OPTION_C_STARTED", option="C")

    async def stop(self) -> None:
        """Stop both servers (only the processes this run started), whatever happened."""
        try:
            if self.npc is not None:
                await self.npc.gateway.stop()
        finally:
            await self.focal.gateway.stop()

    def manifest_settings(self) -> dict[str, Any]:
        out = self.focal.manifest_settings()
        out["inference.option"] = self.option
        fallback = next((e for e in self.events if e["event"] == "OPTION_C_FALLBACK"), None)
        out["inference.fallback_reason"] = fallback["reason"][:200] if fallback else None
        out["vram.budget_mib"] = self.vram.get("budget_mib")
        out["vram.estimate_total_mib"] = self.vram.get("estimate_total_mib")
        out["vram.focal_mib"] = self.vram.get("measured", {}).get("focal", {}).get("mib")
        out["vram.npc_mib"] = self.vram.get("measured", {}).get("npc", {}).get("mib")
        notes = {k: v.get("note") for k, v in self.vram.get("measured", {}).items() if v.get("note")}
        out["vram.note"] = "; ".join(f"{k}: {v}" for k, v in sorted(notes.items()))[:200] or None
        if self.npc is not None and self.option == "C":
            n = self.npc
            out.update({"npc_model.file": n.model.path.name[:200], "npc_model.id": n.model.model_id,
                        "npc_model.catalog_label": n.model.catalog_label, "npc_model.quant": n.model.quant,
                        "npc_model.sha256": n.model.sha256, "npc_model.kv_cache_type": n.settings["kv_cache_type"],
                        "npc_model.parallel_slots": n.settings["parallel_slots"],
                        "npc_model.context_per_slot": n.settings["context_per_slot"]})
        return out


def build_inference(focal_model: str | None = None, npc_model: str | None = None, *, run_dir: Path | None = None,
                    seed: int | None = None, inference: dict[str, Any] | None = None, binary: Path | None = None,
                    snapshots: bool | None = None) -> InferenceSet:
    """Option C from configs/inference.yaml: Robot R's server and (if configured) the NPC server.
    ``npc_model`` overrides the NPC server's model; "none" means no NPC server (Option B)."""
    inf = inference or load_inference()
    focal_name = inf["tiers"]["FOCAL"]["server"]
    npc_name = npc_server_name(inf)
    persona_cfg = inf.get("personas", {"snapshots": True, "prewarm": True})
    use_snapshots = persona_cfg.get("snapshots", True) if snapshots is None else snapshots
    log = (lambda name: run_dir / f"llama_server_{name}.log") if run_dir else (lambda name: None)
    focal = build_llama(focal_model, server_name=focal_name, log_path=log(focal_name), seed=seed, inference=inf,
                        binary=binary)
    npc = None
    if npc_name is not None and npc_model != "none":
        npc = build_llama(npc_model, server_name=npc_name, log_path=log(npc_name), seed=seed, inference=inf,
                          binary=binary,
                          slot_save_path=(run_dir / "slot_snapshots") if (use_snapshots and run_dir) else None)
    if npc is None:
        # Option B: one server. Its scheduler already serves C1/C2 from the shared slots.
        tiers = {t: dict(s, server=focal_name) for t, s in inf["tiers"].items()}
        inf = dict(inf, tiers=tiers)
    iset = InferenceSet(focal, npc, inf)
    if npc_name is not None and npc_model == "none":
        iset.npc_off_reason = "the NPC server was switched off for this run (--npc-model none)"
    return iset
