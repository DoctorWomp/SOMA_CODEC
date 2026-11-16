"""The pinned model catalog and the local registry of model files (D-21, D-55; G3b).

- **Catalog** (``configs/models/catalog.yaml``, committed): which exact files count as each
  bake-off model, pinned by repository commit, size and SHA-256.
- **Registry** (``models/registry.local.yaml``, git-ignored): the GGUF files on this machine,
  used **in place** by path and SHA-256. A file the owner already has (for example in LM Studio's
  folder) is never copied or downloaded again.
- **Plan**: what the catalog needs, what is found, what is missing and how much to download.
- **Download**: only entries the owner confirmed, from the pinned commit, resumable, verified
  against the catalog's SHA-256 before it is used. Never automatic.
"""

from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from range_service import contracts
from range_service.configs import load_yaml
from range_service.models.gguf import GGUFError, is_projector, read_header, sha256_file

REPO = contracts.REPO_ROOT
CATALOG_PATH = REPO / "configs" / "models" / "catalog.yaml"
MODELS_DIR = REPO / "models"
REGISTRY_PATH = MODELS_DIR / "registry.local.yaml"
HF_BASE = "https://huggingface.co"

Progress = Callable[[int, int], None]


class ModelError(RuntimeError):
    pass


# ---------- catalog ----------

def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    data = load_yaml(path)
    found = contracts.problems("model_catalog", data)
    if found:
        raise ModelError(f"{path.name}: {found[0]}")
    problems = catalog_problems(data)
    if problems:
        raise ModelError(f"{path.name}: {problems[0]}")
    return data


def catalog_problems(data: dict[str, Any]) -> list[str]:
    """Duplicates the schema cannot see: ids, labels and file hashes are each used once."""
    found: list[str] = []
    seen: dict[str, dict[str, str]] = {"id": {}, "label": {}, "sha256": {}}
    for entry in data["models"]:
        for key in ("id", "label"):
            if entry[key] in seen[key]:
                found.append(f"models: {key} {entry[key]!r} is used twice")
            seen[key][entry[key]] = entry["id"]
        for src in entry["sources"]:
            if src["sha256"] in seen["sha256"]:
                found.append(f"models.{entry['id']}: file {src['file']} has the same SHA-256 as one of "
                             f"{seen['sha256'][src['sha256']]}'s files")
            seen["sha256"][src["sha256"]] = entry["id"]
    return found


def catalog_by_sha(catalog: dict[str, Any]) -> dict[str, str]:
    return {src["sha256"]: entry["id"] for entry in catalog["models"] for src in entry["sources"]}


def catalog_entry(catalog: dict[str, Any], model_id: str) -> dict[str, Any]:
    for entry in catalog["models"]:
        if entry["id"] == model_id or entry["label"] == model_id:
            return entry
    raise ModelError(f"no catalog entry {model_id!r}; see configs/models/catalog.yaml")


# ---------- registry ----------

def _slug(stem: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    if not s or not s[0].isalpha():
        s = "m_" + s
    return s[:48]


@dataclass
class Registry:
    files: list[dict[str, Any]]
    path: Path = REGISTRY_PATH

    @classmethod
    def load(cls, path: Path = REGISTRY_PATH) -> "Registry":
        if not path.is_file():
            return cls([], path)
        data = load_yaml(path) or {}
        found = contracts.problems("model_registry", data)
        if found:
            raise ModelError(f"{path}: {found[0]} (delete the file and scan again)")
        return cls(list(data["files"]), path)

    def save(self) -> None:
        data = {"schema_version": "1.0", "files": sorted(self.files, key=lambda f: f["local_id"])}
        found = contracts.problems("model_registry", data)
        if found:
            raise ModelError(f"registry would be invalid: {found[0]}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = ("# Local model registry: written by tools/models.py, git-ignored (paths are personal).\n"
                "# Files are used in place, by path and SHA-256 (D-21).\n")
        self.path.write_text(text + yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def find(self, model_id: str) -> dict[str, Any] | None:
        """A file by its catalog id or local id (the first that still exists on disk)."""
        for f in self.files:
            if (f["catalog_id"] == model_id or f["local_id"] == model_id) and Path(f["path"]).is_file():
                return f
        return None

    def _unique_id(self, wanted: str, path: str) -> str:
        taken = {f["local_id"] for f in self.files if f["path"] != path}
        candidate, n = wanted, 2
        while candidate in taken:
            candidate = f"{wanted[:44]}_{n}"
            n += 1
        return candidate

    def add(self, path: Path, sha: str, header: dict[str, Any], catalog_id: str | None, origin: str) -> dict[str, Any]:
        p = path.resolve().as_posix()
        stat = path.stat()
        entry = {
            "local_id": self._unique_id(catalog_id or _slug(path.stem), p),
            "path": p, "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": sha,
            "catalog_id": catalog_id, "origin": origin, "header": header,
        }
        self.files = [f for f in self.files if f["path"] != p] + [entry]
        return entry


def scan(folder: Path, registry: Registry, catalog: dict[str, Any],
         on_file: Callable[[str, Path], None] | None = None, progress: Progress | None = None) -> dict[str, list]:
    """Register every model .gguf under ``folder`` (vision projectors skipped). A file whose path,
    size and modification time match an earlier scan is not hashed again."""
    if not folder.is_dir():
        raise ModelError(f"{folder} is not a folder")
    by_sha = catalog_by_sha(catalog)
    report: dict[str, list] = {"added": [], "unchanged": [], "skipped": [], "unreadable": []}
    known = {f["path"]: f for f in registry.files}
    for path in sorted(folder.rglob("*.gguf")):
        if is_projector(path):
            report["skipped"].append(path)
            if on_file:
                on_file("skip", path)
            continue
        p = path.resolve().as_posix()
        stat = path.stat()
        old = known.get(p)
        if old and old["size_bytes"] == stat.st_size and old["mtime_ns"] == stat.st_mtime_ns:
            old["catalog_id"] = by_sha.get(old["sha256"])
            report["unchanged"].append(old)
            if on_file:
                on_file("same", path)
            continue
        try:
            header = read_header(path).as_dict()
        except (GGUFError, OSError) as exc:
            report["unreadable"].append((path, str(exc)))
            if on_file:
                on_file("bad", path)
            continue
        if on_file:
            on_file("hash", path)
        sha = sha256_file(path, progress)
        report["added"].append(registry.add(path, sha, header, by_sha.get(sha), "SCANNED"))
    return report


# ---------- plan ----------

def plan(catalog: dict[str, Any], registry: Registry, sets: tuple[str, ...] = ("CORE",)) -> dict[str, Any]:
    rows = []
    for entry in catalog["models"]:
        if entry["set"] not in sets:
            continue
        have = registry.find(entry["id"])
        src = entry["sources"][0]
        rows.append({
            "id": entry["id"], "label": entry["label"], "role": entry["role"], "model": entry["model"],
            "quant": entry["quant"], "qat": entry["qat"], "license": entry["license"],
            "status": "FOUND" if have else "MISSING", "path": have["path"] if have else None,
            "download_bytes": 0 if have else src["size_bytes"], "source": f"{src['repo']}/{src['file']}",
        })
    in_catalog = {e["id"] for e in catalog["models"]}
    others = [f for f in registry.files if f["catalog_id"] not in in_catalog and Path(f["path"]).is_file()]
    return {"rows": rows, "download_bytes": sum(r["download_bytes"] for r in rows), "others": others}


# ---------- download ----------

def download_url(src: dict[str, Any]) -> str:
    return f"{HF_BASE}/{src['repo']}/resolve/{src['revision']}/{src['file']}"


def download(entry: dict[str, Any], registry: Registry, models_dir: Path = MODELS_DIR,
             progress: Progress | None = None, opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    """Fetch an entry's first source into ``models_dir``, resuming a partial download, and check its
    size and SHA-256 against the catalog before registering it. A mismatch deletes the file."""
    src = entry["sources"][0]
    models_dir.mkdir(parents=True, exist_ok=True)
    final = models_dir / src["file"]
    part = final.with_name(final.name + ".part")
    if not final.is_file():
        start = part.stat().st_size if part.is_file() else 0
        if start > src["size_bytes"]:
            part.unlink()
            start = 0
        if start < src["size_bytes"]:
            request = urllib.request.Request(download_url(src), headers={"User-Agent": "soma-range-models/1"})
            if start:
                request.add_header("Range", f"bytes={start}-")
            try:
                with opener(request, timeout=120) as response, part.open("ab" if start else "wb") as out:
                    if start and getattr(response, "status", 206) != 206:
                        out.truncate(0)
                        start = 0
                    done = start
                    while chunk := response.read(4 << 20):
                        out.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, src["size_bytes"])
            except (urllib.error.URLError, OSError) as exc:
                raise ModelError(f"download of {src['file']} stopped ({exc}); run the same command again "
                                 "to resume") from exc
        if part.stat().st_size != src["size_bytes"]:
            raise ModelError(f"{src['file']}: got {part.stat().st_size} bytes, the catalog says {src['size_bytes']}; "
                             "run the same command again to resume")
        sha = sha256_file(part)
        if sha != src["sha256"]:
            part.unlink()
            raise ModelError(f"{src['file']}: SHA-256 does not match the catalog; the download was deleted")
        os.replace(part, final)
    else:
        sha = sha256_file(final)
        if sha != src["sha256"]:
            raise ModelError(f"{final} exists but its SHA-256 does not match the catalog; move it away and retry")
    try:
        header = read_header(final).as_dict()
    except GGUFError as exc:
        raise ModelError(f"{final}: {exc}") from exc
    return registry.add(final, sha, header, entry["id"], "DOWNLOADED")


def human_bytes(n: int) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB"


def now_stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime())
