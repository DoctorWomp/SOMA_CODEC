"""Install the pinned llama.cpp `llama-server` into .tools/llama/ (D-21; G3b).

    uv run python tools/install_llama.py                 # Windows: CUDA 12 build + CUDA runtime
    uv run python tools/install_llama.py --check         # report what is installed, change nothing
    uv run python tools/install_llama.py --from-source   # Linux / cloud: build the pinned commit (CPU)

The same pattern as tools/install_godot.py: one pinned release, downloaded from the official
GitHub release, checked against a SHA-256 before anything is unpacked, installed into
.tools/llama/ only. Nothing is installed system-wide and nothing else is downloaded.

Pinned release: llama.cpp b12443 (commit 301db633702f1d2c107d4feaa4268f07c0b508c5, 2026-11-16).
Asset names were read from that commit's .github/workflows/release.yml and release-publish.yml.

**Checksums.** The two Windows files are pinned below (the owner recorded them on install and
checked them against the release page, 2026-11-17): a download that does not match is deleted
and nothing is installed. Files without a pinned checksum (the Linux release tarball) are refused
unless you pass --record-hashes: the installer then prints each file's SHA-256 and size, asks you
to compare them with the "sha256:" shown next to the file on
https://github.com/ggml-org/llama.cpp/releases/tag/b12443, and only installs if you type yes.
Those values are saved in .tools/llama/recorded_hashes.json, so later installs are checked
against them.

**NVIDIA driver.** The CUDA 12 build ships the CUDA 12.4 runtime. CUDA 12.4 asks for driver
551.61 or newer on Windows; through CUDA's minor-version compatibility, 12.x builds usually also
run on 528.33 or newer. --check prints your driver version (from nvidia-smi) and compares.

**From source** (Linux, used in cloud sessions for smoke tests): clones the pinned tag, checks
that it is exactly the pinned commit, and builds the llama-server target for the CPU with CMake.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALL_DIR = REPO / ".tools" / "llama"
RECORDED = INSTALL_DIR / "recorded_hashes.json"

VERSION = "b12443"
COMMIT = "301db633702f1d2c107d4feaa4268f07c0b508c5"
SOURCE_URL = "https://github.com/ggml-org/llama.cpp"
BASE_URL = f"{SOURCE_URL}/releases/download/{VERSION}/"
MIN_DRIVER = {"required": "551.61", "minor_compat": "528.33", "cuda": "12.4"}

# Release assets per build. sha256 None = not pinned yet (see the module docstring).
BUILDS = {
    "windows-cuda12": {
        "folder": f"win-cuda12-{VERSION}",
        "binary": "llama-server.exe",
        "assets": [
            # Pinned 2026-11-17 from the owner's install, checked against the release page (D-57).
            {"file": f"llama-{VERSION}-bin-win-cuda-12.4-x64.zip",
             "sha256": "a0cfc4695a254da9b26cec6d861494443668fa99a2badbaf71be717281dde62c"},
            {"file": "cudart-llama-bin-win-cuda-12.4-x64.zip",                     # CUDA 12.4 runtime DLLs
             "sha256": "8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6"},
        ],
    },
    "linux-cpu": {
        "folder": f"linux-cpu-{VERSION}",
        "binary": "llama-server",
        "assets": [{"file": f"llama-{VERSION}-bin-ubuntu-x64.tar.gz", "sha256": None}],
    },
}
SOURCE_FOLDER = f"linux-src-{VERSION}"


def platform_build() -> str | None:
    system, machine = platform.system().lower(), platform.machine().lower()
    if machine not in ("x86_64", "amd64"):
        return None
    return {"windows": "windows-cuda12", "linux": "linux-cpu"}.get(system)


def installed_binary() -> Path | None:
    """The llama-server this script installed (release build first, then a source build)."""
    candidates = []
    build = platform_build()
    if build:
        candidates.append(INSTALL_DIR / BUILDS[build]["folder"] / BUILDS[build]["binary"])
    candidates.append(INSTALL_DIR / SOURCE_FOLDER / "llama-server")
    for path in candidates:
        if path.is_file():
            return path
    return None


def _recorded() -> dict[str, str]:
    try:
        return json.loads(RECORDED.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _download(url: str, dest: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(url, headers={"User-Agent": "soma-range-install-llama/1"})
    with urllib.request.urlopen(request, timeout=300) as response, dest.open("wb") as out:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
            size += len(chunk)
            print(f"\r  {size / 1e6:8.1f} MB", end="", flush=True)
    print()
    return digest.hexdigest(), size


def _unpack(archive: Path, target: Path) -> None:
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if member.startswith("/") or ".." in Path(member).parts:
                    raise RuntimeError(f"unsafe path in {archive.name}: {member}")
            zf.extractall(target)
    else:
        with tarfile.open(archive) as tf:
            tf.extractall(target, filter="data")
        # The Linux tarball holds one folder (llama-bNNNN/); flatten it.
        inner = target / f"llama-{VERSION}"
        if inner.is_dir():
            for item in inner.iterdir():
                shutil.move(str(item), target / item.name)
            inner.rmdir()


def install_release(build_name: str, record: bool, assume_yes: bool) -> int:
    build = BUILDS[build_name]
    target = INSTALL_DIR / build["folder"]
    if (target / build["binary"]).is_file():
        print(f"llama-server {VERSION} is already installed: {target / build['binary']}")
        return 0
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    recorded = _recorded()
    downloads = []
    for asset in build["assets"]:
        expected = asset["sha256"] or recorded.get(asset["file"])
        if expected is None and not record:
            print(f"error: the SHA-256 of {asset['file']} is not pinned yet.\n"
                  "Run again with --record-hashes to see it, compare it with the release page, and confirm.")
            return 1
        dest = INSTALL_DIR / asset["file"]
        print(f"Downloading {BASE_URL}{asset['file']}")
        try:
            sha, size = _download(BASE_URL + asset["file"], dest)
        except OSError as exc:
            print(f"error: download failed: {exc}")
            dest.unlink(missing_ok=True)
            return 1
        if expected is not None and sha != expected:
            dest.unlink()
            print(f"error: SHA-256 of {asset['file']} does not match; the download was deleted\n"
                  f"  expected {expected}\n  got      {sha}")
            return 1
        downloads.append((asset, dest, sha, size, expected is None))
    unverified = [d for d in downloads if d[4]]
    if unverified:
        print("\nThese files have no pinned checksum yet. Compare each SHA-256 with the \"sha256:\" shown next to")
        print(f"the file on {SOURCE_URL}/releases/tag/{VERSION} (it must match exactly):\n")
        for asset, _, sha, size, _ in unverified:
            print(f"  {asset['file']}\n    sha256 {sha}\n    size   {size} bytes")
        answer = "yes" if assume_yes else input('\nType "yes" if they match: ').strip().lower()
        if answer != "yes":
            for _, dest, *_ in downloads:
                dest.unlink(missing_ok=True)
            print("Nothing installed; the downloads were deleted.")
            return 1
        recorded.update({asset["file"]: sha for asset, _, sha, _, _ in unverified})
        RECORDED.write_text(json.dumps(recorded, indent=2) + "\n", encoding="utf-8")
        print(f"Recorded in {RECORDED}. Please paste the lines above back so they can be pinned.")
    target.mkdir(parents=True, exist_ok=True)
    for _, dest, *_ in downloads:
        _unpack(dest, target)
        dest.unlink()
    binary = target / build["binary"]
    if not binary.is_file():
        print(f"error: {build['binary']} was not in the release files; nothing usable was installed")
        return 1
    binary.chmod(binary.stat().st_mode | 0o111)
    print(f"Installed and verified: {binary}")
    return 0


def install_from_source(jobs: int) -> int:
    target = INSTALL_DIR / SOURCE_FOLDER
    if (target / "llama-server").is_file():
        print(f"llama-server {VERSION} (built from source) is already installed: {target / 'llama-server'}")
        return 0
    for tool in ("git", "cmake"):
        if shutil.which(tool) is None:
            print(f"error: {tool} is needed to build from source")
            return 1
    src = INSTALL_DIR / f"src-{VERSION}"
    if not src.is_dir():
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", VERSION, SOURCE_URL, str(src)],
                       check=True, env=dict(os.environ, GIT_LFS_SKIP_SMUDGE="1"))
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if head != COMMIT:
        print(f"error: tag {VERSION} points at {head}, not the pinned commit {COMMIT}; stopping")
        return 1
    build = src / "build"
    generator = ["-G", "Ninja"] if shutil.which("ninja") else []
    try:
        subprocess.run(["cmake", "-S", str(src), "-B", str(build), *generator, "-DCMAKE_BUILD_TYPE=Release",
                        "-DLLAMA_CURL=OFF", "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=OFF",
                        "-DBUILD_SHARED_LIBS=OFF"], check=True)
        subprocess.run(["cmake", "--build", str(build), "--target", "llama-server", "-j", str(jobs)], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"error: the build failed ({exc.cmd[0]} exited with {exc.returncode}); see the output above.\n"
              f"Delete {build} and try again if it was left over from an earlier build.")
        return 1
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / "bin" / "llama-server", target / "llama-server")   # static: needs nothing else
    shutil.rmtree(src, ignore_errors=True)
    print(f"Built commit {COMMIT[:12]} and installed: {target / 'llama-server'}")
    return 0


def driver_version() -> str | None:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    try:
        out = subprocess.run([exe, "--query-gpu=driver_version,name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


def check() -> int:
    binary = installed_binary()
    print(f"Pinned: llama.cpp {VERSION} ({COMMIT[:12]}); CUDA {MIN_DRIVER['cuda']} runtime on Windows.")
    print(f"Installed: {binary if binary else 'no'}")
    info = driver_version()
    if info is None:
        print("NVIDIA driver: not found (nvidia-smi missing): fine for the CPU build, needed for CUDA.")
    else:
        first = info.splitlines()[0]
        driver = first.split(",")[0].strip()
        print(f"NVIDIA GPU: {first}")
        if _version_tuple(driver) >= _version_tuple(MIN_DRIVER["required"]):
            print(f"Driver {driver} meets CUDA {MIN_DRIVER['cuda']}'s minimum ({MIN_DRIVER['required']}).")
        elif _version_tuple(driver) >= _version_tuple(MIN_DRIVER["minor_compat"]):
            print(f"Driver {driver} is below {MIN_DRIVER['required']} but above {MIN_DRIVER['minor_compat']}: "
                  "it should work through CUDA minor-version compatibility; update the driver if the server fails.")
        else:
            print(f"Driver {driver} is too old for CUDA {MIN_DRIVER['cuda']}: update to {MIN_DRIVER['required']} or newer.")
    if binary:
        try:
            out = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=60)
            print("Server says: " + " | ".join(line for line in (out.stdout + out.stderr).splitlines() if line.strip())[:300])
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"error: the installed server did not run: {exc}")
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/install_llama.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report what is installed and the driver; change nothing")
    parser.add_argument("--from-source", action="store_true", help="build the pinned commit with CMake (Linux, CPU)")
    parser.add_argument("--record-hashes", action="store_true", help="install unpinned files after you compare their SHA-256")
    parser.add_argument("--yes", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 2, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.check:
        return check()
    if args.from_source:
        return install_from_source(args.jobs)
    build = platform_build()
    if build is None:
        print(f"error: no pinned llama-server build for {platform.system()} {platform.machine()}")
        return 1
    return install_release(build, args.record_hashes, args.yes)


if __name__ == "__main__":
    sys.exit(main())
