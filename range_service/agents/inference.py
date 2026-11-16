"""Real-model setup from configs/inference.yaml (G3b; D-20, D-21, D-50, D-55).

Turns the inference settings and the local model registry into a started llama-server and a
ModelGateway, and describes the exact model file for run manifests (D-55: the quantization is
part of a model's identity; record file, quant, SHA-256, engine build and KV cache type).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from range_service import contracts
from range_service.configs import CONFIGS_DIR, load_yaml
from range_service.models import registry as reg

from .gateway import ModelGateway, ProviderError
from .llama import LlamaProvider, LlamaServer, ServerSettings, ServerTokenizer, default_binary

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
        }


def build_llama(model: str | None = None, *, server_name: str = "focal", kv_cache_type: str | None = None,
                log_path: Path | None = None, seed: int | None = None, inference: dict[str, Any] | None = None,
                binary: Path | None = None) -> LlamaSetup:
    """A not-yet-started llama-server setup. ``model``/``kv_cache_type`` override the config."""
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
                              thinking=inf["thinking"])
    sampling = dict(inf["sampling"])
    if sampling.get("seed", 0) == 0 and seed:
        sampling["seed"] = seed
    pinned = tuple(t for t, s in inf["tiers"].items() if s["pin_slot"] and s["server"] == server_name)
    provider = LlamaProvider(server=LlamaServer(binary, settings, log_path, inf["engine"]["startup_timeout_s"]),
                             pinned_tiers=pinned, sampling=sampling, structured_output=inf["structured_output"],
                             warm_up=inf["engine"]["warm_up"])
    gateway = ModelGateway(provider, deadlines_ms={t: s["deadline_ms"] for t, s in inf["tiers"].items()})
    return LlamaSetup(gateway, provider, resolved, server)
