"""GGUF headers, the pinned model catalog, the local registry and downloads (G3b; D-21, D-55).
No network: downloads are served from memory."""

from __future__ import annotations

import hashlib
import io
import struct
from pathlib import Path

import pytest
import yaml

from range_service.configs import load_and_check
from range_service.models import gguf
from range_service.models import registry as reg
from tools import install_llama


def _model(path: Path, quant_type: int = 15, arch: str = "qwen35", ctx: int = 4096) -> Path:
    gguf.write_minimal(path, {"general.architecture": arch, "general.name": path.stem, "general.size_label": "1B",
                              "general.file_type": quant_type, f"{arch}.context_length": ctx,
                              "tokenizer.ggml.tokens": ["a", "b", "c"]},
                       [("token_embd.weight", [64, 100]), ("blk.0.attn_q.weight", [64, 64]), ("output_norm.weight", [64])])
    return path


def _catalog(files: dict[str, Path]) -> dict:
    models = []
    for i, (model_id, path) in enumerate(files.items()):
        models.append({"id": model_id, "label": f"F{i + 1}", "set": "CORE", "role": "FOCAL", "model": model_id,
                       "quant": "Q4_K_M", "qat": False, "license": "apache-2.0",
                       "license_url": "https://huggingface.co/x/y",
                       "sources": [{"repo": "x/y", "revision": "a" * 40, "file": path.name,
                                    "size_bytes": path.stat().st_size,
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]})
    return {"schema_version": "1.0", "catalog_id": "catalog", "checked_on": "2026-11-16", "models": models}


# ---------- GGUF headers ----------

def test_header_reads_architecture_params_quant_and_context(tmp_path):
    info = gguf.read_header(_model(tmp_path / "m.gguf", quant_type=18, ctx=262144))
    assert (info.architecture, info.quantization, info.context_length) == ("qwen35", "Q6_K", 262144)
    assert info.parameter_count == 64 * 100 + 64 * 64 + 64
    assert info.size_label == "1B" and info.version == 3


@pytest.mark.parametrize("data, message", [
    (b"NOPE" + b"\x00" * 20, "wrong magic"),
    (b"GGUF" + struct.pack("<I", 9) + b"\x00" * 16, "version 9"),
    (b"GGUF" + struct.pack("<IQQ", 3, 0, 5), "ends inside its header"),
    (b"GGUF" + struct.pack("<IQQ", 3, 10**9, 1), "implausible"),
])
def test_damaged_or_foreign_files_are_refused(tmp_path, data, message):
    path = tmp_path / "bad.gguf"
    path.write_bytes(data)
    with pytest.raises(gguf.GGUFError, match=message):
        gguf.read_header(path)


def test_projectors_are_recognized():
    assert gguf.is_projector(Path("mmproj-BF16.gguf")) and gguf.is_projector(Path("gemma-4-E4B-it-mmproj.gguf"))
    assert not gguf.is_projector(Path("Qwen3.5-9B-Q4_K_M.gguf"))


# ---------- the committed catalog ----------

def test_committed_catalog_is_valid_and_pins_every_file():
    cs, problems = load_and_check()
    assert not problems
    catalog = cs.items["models"]["catalog"]
    core = [e for e in catalog["models"] if e["set"] == "CORE"]
    # D-55 core set; F2 dropped by the owner after the bake-off (2026-11-17, D-58)
    assert sorted(e["label"] for e in core) == ["F1", "F3", "N1", "N2", "N3", "S1", "S2"]
    for e in catalog["models"]:
        assert e["license"] == "apache-2.0", e["id"]
        for s in e["sources"]:
            assert len(s["revision"]) == 40 and len(s["sha256"]) == 64 and s["size_bytes"] > 1e8
    # QAT where the maker publishes it (D-55): every Gemma core entry is the official QAT file first.
    for e in core:
        if e["model"].startswith("Gemma"):
            assert e["qat"] and e["sources"][0]["repo"].startswith("google/"), e["id"]
    total = sum(e["sources"][0]["size_bytes"] for e in core)
    assert 25e9 < total < 32e9         # D-55 ~35-40 GB; 28.84 GB since F2 left the core set (2026-11-17)


def test_catalog_duplicates_are_reported(tmp_path):
    a = _model(tmp_path / "a.gguf")
    cat = _catalog({"model_a": a, "model_b": a})
    problems = reg.catalog_problems(cat)
    assert any("same SHA-256" in p for p in problems)


# ---------- scan and plan ----------

def test_scan_registers_files_in_place_and_matches_the_catalog(tmp_path):
    lm = tmp_path / "lmstudio" / "Qwen3.5-9B-GGUF"
    lm.mkdir(parents=True)
    known = _model(lm / "Qwen3.5-9B-Q4_K_M.gguf")
    other = _model(tmp_path / "lmstudio" / "Other-Q8_0.gguf", quant_type=7)
    (lm / "mmproj-Qwen3.5-9B-BF16.gguf").write_bytes(b"GGUF....")
    (lm / "broken.gguf").write_bytes(b"not a model")
    catalog = _catalog({"qwen35_9b_q4km": known})
    registry = reg.Registry.load(tmp_path / "registry.local.yaml")
    report = reg.scan(tmp_path / "lmstudio", registry, catalog)
    registry.save()
    assert len(report["added"]) == 2 and len(report["skipped"]) == 1 and len(report["unreadable"]) == 1
    saved = yaml.safe_load((tmp_path / "registry.local.yaml").read_text())
    by_id = {f["local_id"]: f for f in saved["files"]}
    assert by_id["qwen35_9b_q4km"]["path"] == known.resolve().as_posix()          # used in place, not copied
    assert by_id["qwen35_9b_q4km"]["catalog_id"] == "qwen35_9b_q4km"
    assert by_id["other_q8_0"]["catalog_id"] is None and by_id["other_q8_0"]["header"]["quantization"] == "Q8_0"
    # A second scan does not hash unchanged files again.
    again = reg.scan(tmp_path / "lmstudio", reg.Registry.load(tmp_path / "registry.local.yaml"), catalog)
    assert not again["added"] and len(again["unchanged"]) == 2
    p = reg.plan(catalog, reg.Registry.load(tmp_path / "registry.local.yaml"))
    assert p["rows"][0]["status"] == "FOUND" and p["download_bytes"] == 0
    assert [f["local_id"] for f in p["others"]] == ["other_q8_0"]


def test_plan_counts_what_is_missing(tmp_path):
    a, b = _model(tmp_path / "a.gguf"), _model(tmp_path / "b.gguf", quant_type=18)
    catalog = _catalog({"model_a": a, "model_b": b})
    p = reg.plan(catalog, reg.Registry([], tmp_path / "r.yaml"))
    assert [r["status"] for r in p["rows"]] == ["MISSING", "MISSING"]
    assert p["download_bytes"] == a.stat().st_size + b.stat().st_size


# ---------- download ----------

class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, status: int = 200) -> None:
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _opener(data: bytes, seen: list):
    def opener(request, timeout=0):
        seen.append(request)
        rng = request.get_header("Range")
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
            return FakeResponse(data[start:], 206)
        return FakeResponse(data)
    return opener


def test_download_verifies_and_registers(tmp_path):
    (tmp_path / "src").mkdir()
    src = _model(tmp_path / "src" / "Model-Q4_K_M.gguf")
    data = src.read_bytes()
    catalog = _catalog({"model_a": src})
    registry = reg.Registry([], tmp_path / "r.yaml")
    seen: list = []
    entry = reg.download(catalog["models"][0], registry, tmp_path / "models", opener=_opener(data, seen))
    assert (tmp_path / "models" / "Model-Q4_K_M.gguf").read_bytes() == data
    assert entry["origin"] == "DOWNLOADED" and entry["catalog_id"] == "model_a"
    assert seen[0].full_url == f"https://huggingface.co/x/y/resolve/{'a' * 40}/Model-Q4_K_M.gguf"   # the pinned commit


def test_download_resumes_a_partial_file(tmp_path):
    (tmp_path / "src").mkdir()
    src = _model(tmp_path / "src" / "M.gguf")
    data = src.read_bytes()
    catalog = _catalog({"model_a": src})
    models = tmp_path / "models"
    models.mkdir()
    (models / "M.gguf.part").write_bytes(data[:50])
    seen: list = []
    reg.download(catalog["models"][0], reg.Registry([], tmp_path / "r.yaml"), models, opener=_opener(data, seen))
    assert seen[0].get_header("Range") == "bytes=50-"
    assert (models / "M.gguf").read_bytes() == data and not (models / "M.gguf.part").exists()


def test_download_with_a_wrong_hash_is_deleted(tmp_path):
    (tmp_path / "src").mkdir()
    src = _model(tmp_path / "src" / "M.gguf")
    catalog = _catalog({"model_a": src})
    tampered = bytearray(src.read_bytes())
    tampered[-1] ^= 0xFF
    with pytest.raises(reg.ModelError, match="does not match"):
        reg.download(catalog["models"][0], reg.Registry([], tmp_path / "r.yaml"), tmp_path / "models",
                     opener=_opener(bytes(tampered), []))
    assert not list((tmp_path / "models").glob("M.gguf*"))


def test_download_command_asks_before_fetching(tmp_path, monkeypatch, capsys):
    from tools import models as cli

    monkeypatch.setattr("builtins.input", lambda _prompt: "no")
    monkeypatch.setattr(reg, "download", lambda *a, **k: pytest.fail("downloaded without confirmation"))
    assert cli.main(["--registry", str(tmp_path / "r.yaml"), "download", "S2"]) == 1
    out = capsys.readouterr().out
    assert "Qwen3.5-2B" in out and "Nothing downloaded" in out


# ---------- installer pins ----------

def test_installer_pins_one_release_and_its_assets():
    assert install_llama.VERSION == "b12443" and len(install_llama.COMMIT) == 40
    win = install_llama.BUILDS["windows-cuda12"]["assets"]
    assert [a["file"] for a in win] == ["llama-b12443-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"]
    assert install_llama.MIN_DRIVER == {"required": "551.61", "minor_compat": "528.33", "cuda": "12.4"}
    # Pinned from the owner's install (2026-11-17, D-57).
    assert [a["sha256"] for a in win] == ["a0cfc4695a254da9b26cec6d861494443668fa99a2badbaf71be717281dde62c",
                                          "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"]


def test_installer_refuses_unpinned_files_without_confirmation(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(install_llama, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(install_llama, "RECORDED", tmp_path / "recorded_hashes.json")
    monkeypatch.setattr(install_llama, "_download", lambda *a: pytest.fail("downloaded an unpinned file"))
    assert install_llama.install_release("linux-cpu", record=False, assume_yes=False) == 1
    assert "not pinned yet" in capsys.readouterr().out


def test_installer_deletes_a_windows_download_that_does_not_match_its_pin(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(install_llama, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(install_llama, "RECORDED", tmp_path / "recorded_hashes.json")

    def fake_download(url, dest):
        dest.write_bytes(b"tampered")
        return hashlib.sha256(b"tampered").hexdigest(), 8
    monkeypatch.setattr(install_llama, "_download", fake_download)
    monkeypatch.setattr("builtins.input", lambda _p: pytest.fail("asked to confirm a pinned file"))
    assert install_llama.install_release("windows-cuda12", record=False, assume_yes=False) == 1
    assert "does not match" in capsys.readouterr().out and not list(tmp_path.glob("*.zip"))


def test_installer_checks_recorded_hashes(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(install_llama, "INSTALL_DIR", tmp_path)
    monkeypatch.setattr(install_llama, "RECORDED", tmp_path / "recorded_hashes.json")
    (tmp_path / "recorded_hashes.json").write_text('{"llama-b12443-bin-ubuntu-x64.tar.gz": "' + "0" * 64 + '"}')

    def fake_download(url, dest):
        dest.write_bytes(b"tampered")
        return hashlib.sha256(b"tampered").hexdigest(), 8
    monkeypatch.setattr(install_llama, "_download", fake_download)
    assert install_llama.install_release("linux-cpu", record=False, assume_yes=False) == 1
    assert "does not match" in capsys.readouterr().out and not list(tmp_path.glob("*.tar.gz"))
