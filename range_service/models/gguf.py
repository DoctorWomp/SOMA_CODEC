"""Read a GGUF model file's header: architecture, name, parameter count, quantization, context.

Only the header and the tensor table are read (a few MB at most), never the weights. Pure
Python, no dependencies. Format: https://github.com/ggml-org/ggml/blob/master/docs/gguf.md
(versions 2 and 3). File-type numbers follow llama.cpp's ``llama_ftype`` (include/llama.h at
the pinned release, tools/install_llama.py).
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable

MAGIC = b"GGUF"

# llama_ftype -> the name model pages use for the quantization.
FILE_TYPES = {
    0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 7: "Q8_0", 8: "Q5_0", 9: "Q5_1", 10: "Q2_K",
    11: "Q3_K_S", 12: "Q3_K_M", 13: "Q3_K_L", 14: "Q4_K_S", 15: "Q4_K_M", 16: "Q5_K_S", 17: "Q5_K_M",
    18: "Q6_K", 19: "IQ2_XXS", 20: "IQ2_XS", 21: "Q2_K_S", 22: "IQ3_XS", 23: "IQ3_XXS", 24: "IQ1_S",
    25: "IQ4_NL", 26: "IQ3_S", 27: "IQ3_M", 28: "IQ2_S", 29: "IQ2_M", 30: "IQ4_XS", 31: "IQ1_M",
    32: "BF16", 36: "TQ1_0", 37: "TQ2_0", 38: "MXFP4_MOE", 39: "NVFP4", 40: "Q1_0", 41: "Q2_0",
    42: "F8_E4M3",
}

# GGUF value types: struct format and size (strings and arrays are handled separately).
_SCALARS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
_STRING, _ARRAY = 8, 9
# Limits that keep a damaged or hostile file from making us read gigabytes of "header".
MAX_KV = 100_000
MAX_TENSORS = 1_000_000
MAX_STRING = 16 * 1024 * 1024
MAX_ARRAY = 10_000_000


class GGUFError(ValueError):
    """The file is not a readable GGUF model."""


@dataclass
class GGUFInfo:
    version: int
    architecture: str | None
    name: str | None
    size_label: str | None
    quantization: str | None
    file_type: int | None
    context_length: int | None
    parameter_count: int
    tensor_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "architecture": self.architecture, "name": self.name, "size_label": self.size_label,
            "quantization": self.quantization, "file_type": self.file_type,
            "context_length": self.context_length, "parameter_count": self.parameter_count,
            "gguf_version": self.version,
        }


class _Reader:
    def __init__(self, fh: BinaryIO) -> None:
        self.fh = fh

    def take(self, n: int) -> bytes:
        data = self.fh.read(n)
        if len(data) != n:
            raise GGUFError("the file ends inside its header")
        return data

    def scalar(self, fmt: str) -> Any:
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self) -> str:
        n = self.scalar("<Q")
        if n > MAX_STRING:
            raise GGUFError(f"a header string claims {n} bytes")
        return self.take(n).decode("utf-8", errors="replace")

    def value(self, vtype: int, keep: bool = True) -> Any:
        if vtype in _SCALARS:
            return self.scalar(_SCALARS[vtype])
        if vtype == _STRING:
            return self.string()
        if vtype == _ARRAY:
            itype = self.scalar("<I")
            count = self.scalar("<Q")
            if count > MAX_ARRAY:
                raise GGUFError(f"a header array claims {count} items")
            if itype in _SCALARS and not keep:
                self.take(struct.calcsize(_SCALARS[itype]) * count)   # skip (token tables are large)
                return None
            items = [self.value(itype, keep) for _ in range(count)]
            return items if keep else None
        raise GGUFError(f"unknown value type {vtype} in the header")


def read_header(path: Path) -> GGUFInfo:
    """Parse ``path``'s GGUF header and tensor table. Raises GGUFError if it is not GGUF."""
    with path.open("rb") as fh:
        r = _Reader(fh)
        if r.take(4) != MAGIC:
            raise GGUFError("not a GGUF file (wrong magic bytes)")
        version = r.scalar("<I")
        if version not in (2, 3):
            raise GGUFError(f"GGUF version {version} is not supported (2 or 3)")
        tensor_count = r.scalar("<Q")
        kv_count = r.scalar("<Q")
        if kv_count > MAX_KV or tensor_count > MAX_TENSORS:
            raise GGUFError("the header claims an implausible number of entries")
        meta: dict[str, Any] = {}
        for _ in range(kv_count):
            key = r.string()
            vtype = r.scalar("<I")
            # Arrays (vocabularies, merges) are skipped; every key we need is a scalar or string.
            meta[key] = r.value(vtype, keep=vtype != _ARRAY)
        params = 0
        for _ in range(tensor_count):
            r.string()                                   # tensor name
            n_dims = r.scalar("<I")
            if n_dims > 8:
                raise GGUFError(f"a tensor claims {n_dims} dimensions")
            count = 1
            for _ in range(n_dims):
                count *= r.scalar("<Q")
            r.scalar("<I")                               # tensor type
            r.scalar("<Q")                               # data offset
            params += count
    arch = meta.get("general.architecture")
    file_type = meta.get("general.file_type")
    ctx = meta.get(f"{arch}.context_length") if isinstance(arch, str) else None
    return GGUFInfo(
        version=version,
        architecture=arch if isinstance(arch, str) else None,
        name=meta.get("general.name") if isinstance(meta.get("general.name"), str) else None,
        size_label=meta.get("general.size_label") if isinstance(meta.get("general.size_label"), str) else None,
        quantization=FILE_TYPES.get(file_type) if isinstance(file_type, int) else None,
        file_type=file_type if isinstance(file_type, int) else None,
        context_length=int(ctx) if isinstance(ctx, int) else None,
        parameter_count=params,
        tensor_count=tensor_count,
    )


def is_projector(path: Path) -> bool:
    """Vision projector files (``mmproj-*.gguf``) are skipped: RANGE sends text only."""
    return "mmproj" in path.name.lower()


def sha256_file(path: Path, progress: Callable[[int, int], None] | None = None, chunk: int = 8 << 20) -> str:
    total = path.stat().st_size
    digest = hashlib.sha256()
    done = 0
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
            done += len(block)
            if progress:
                progress(done, total)
    return digest.hexdigest()


# ---------- a tiny writer, for tests and the stand-in server (never used on real models) ----------

def _w_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def write_minimal(path: Path, meta: dict[str, Any], tensors: list[tuple[str, list[int]]]) -> None:
    """Write a header-only GGUF v3 file with string/int metadata and the given tensor shapes."""
    out = bytearray(MAGIC + struct.pack("<IQQ", 3, len(tensors), len(meta)))
    for key, value in meta.items():
        out += _w_string(key)
        if isinstance(value, str):
            out += struct.pack("<I", _STRING) + _w_string(value)
        elif isinstance(value, list):
            out += struct.pack("<IIQ", _ARRAY, _STRING, len(value)) + b"".join(_w_string(v) for v in value)
        else:
            out += struct.pack("<I", 4) + struct.pack("<I", int(value))
    for name, dims in tensors:
        out += _w_string(name) + struct.pack("<I", len(dims)) + b"".join(struct.pack("<Q", d) for d in dims)
        out += struct.pack("<IQ", 0, 0)
    path.write_bytes(bytes(out))
