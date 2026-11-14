"""Download the pinned Godot build into .tools/godot/ and verify it (D-06, D-34).

    uv run python tools/install_godot.py

Used by CI and cloud sessions. On a PC that already has Godot 4.7.2, you do not need
this: point GODOT_BIN at your copy instead (see docs/BUILD_AND_RUN.md).

The download is checked against the SHA-512 published with the release; a mismatch
deletes the file and stops. Nothing is installed system-wide.
"""

from __future__ import annotations

import hashlib
import platform
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALL_DIR = REPO / ".tools" / "godot"
VERSION = "4.7.2-stable"
BASE_URL = f"https://github.com/godotengine/godot-builds/releases/download/{VERSION}/"

# From SHA512-SUMS.txt of the 4.7.2-stable release (checked 2026-11-14).
BUILDS = {
    "linux": {
        "zip": "Godot_v4.7.2-stable_linux.x86_64.zip",
        "sha512": "9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b14"
                  "67edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65",
        "binary": "Godot_v4.7.2-stable_linux.x86_64",
    },
    "windows": {
        "zip": "Godot_v4.7.2-stable_win64.exe.zip",
        "sha512": "83decd58fdf67b9d657958a1ae6bf1929c20785315a81effe245874cdc57acb7"
                  "09bf868e00778a96984338c1b29dafdb453c6847747694621c6ecf5da2259993",
        # The console build prints to the terminal, which the checks need.
        "binary": "Godot_v4.7.2-stable_win64_console.exe",
    },
}


def build_for_this_machine() -> dict[str, str] | None:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "linux" and machine in ("x86_64", "amd64"):
        return BUILDS["linux"]
    if system == "windows" and machine in ("x86_64", "amd64"):
        return BUILDS["windows"]
    return None


def installed_binary() -> Path | None:
    """Path of the Godot binary installed by this script, if present."""
    build = build_for_this_machine()
    if build is None:
        return None
    path = INSTALL_DIR / build["binary"]
    return path if path.is_file() else None


def main() -> int:
    build = build_for_this_machine()
    if build is None:
        print(f"error: no pinned Godot build for {platform.system()} {platform.machine()}")
        return 1
    existing = installed_binary()
    if existing is not None:
        print(f"Godot {VERSION} is already installed: {existing}")
        return 0
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    archive = INSTALL_DIR / build["zip"]
    print(f"Downloading {BASE_URL}{build['zip']}")
    with urllib.request.urlopen(BASE_URL + build["zip"], timeout=300) as response, archive.open("wb") as out:
        digest = hashlib.sha512()
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != build["sha512"]:
        archive.unlink()
        print("error: SHA-512 does not match the published checksum; the download was deleted")
        return 1
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(INSTALL_DIR)
    archive.unlink()
    binary = INSTALL_DIR / build["binary"]
    binary.chmod(binary.stat().st_mode | 0o111)
    print(f"Installed and verified: {binary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
