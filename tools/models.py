"""Model files for real-model runs (G3b; D-21, D-55): register what you have, plan, download.

    uv run python tools/models.py scan "G:\\.lmstudio\\models\\lmstudio-community"
        Find every .gguf under the folder (vision projectors, mmproj-*, are skipped), read its
        header (architecture, parameter count, quantization, context length), compute its
        SHA-256 and record it in models/registry.local.yaml (git-ignored). Files are used in
        place: nothing is copied. A file already scanned and unchanged is not hashed again.

    uv run python tools/models.py plan [--all]
        Compare the registry with the pinned catalog (configs/models/catalog.yaml): which core
        models are found, which are missing, and how much a download would take. --all also
        lists the optional entries.

    uv run python tools/models.py download F3 N1 ...     (labels or ids from the plan)
    uv run python tools/models.py download --missing
        Download only what you name (or every missing core model), after showing the list and
        total size and asking you to type "yes". Files come from the pinned commit, are checked
        against the catalog's size and SHA-256, and are stored in models/. A stopped download
        resumes when you run the same command again.

    uv run python tools/models.py list
        Show the registry.

Nothing is ever downloaded without your confirmation (D-20, D-21).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from range_service.models import registry as reg  # noqa: E402


def _bar(prefix: str):
    state = {"last": -1}

    def show(done: int, total: int) -> None:
        pct = int(done * 100 / total) if total else 100
        if pct != state["last"]:
            state["last"] = pct
            print(f"\r  {prefix} {pct:3d}% of {reg.human_bytes(total)}", end="", flush=True)
            if done >= total:
                print()
    return show


def cmd_scan(args: argparse.Namespace) -> int:
    catalog = reg.load_catalog()
    registry = reg.Registry.load(args.registry)
    folder = Path(args.folder).expanduser()
    labels = {e["id"]: e["label"] for e in catalog["models"]}

    def on_file(what: str, path: Path) -> None:
        if what == "skip":
            print(f"  skip   {path.name} (vision projector; RANGE sends text only)")
        elif what == "bad":
            print(f"  ??     {path.name}: not a readable GGUF model file")
        elif what == "hash":
            print(f"  read   {path.name}")

    report = reg.scan(folder, registry, catalog, on_file, None if args.quiet else _bar("SHA-256"))
    registry.save()
    print()
    for entry in report["added"] + report["unchanged"]:
        h = entry["header"]
        params = f"{h['parameter_count'] / 1e9:.2f}B" if h["parameter_count"] else "?"
        cat = f"catalog {labels[entry['catalog_id']]} ({entry['catalog_id']})" if entry["catalog_id"] else "not in the catalog"
        print(f"  {entry['local_id']:<34} {h['architecture'] or '?':<12} {params:>7} {h['quantization'] or '?':<8} "
              f"ctx {h['context_length'] or '?':<7} {cat}")
    for path, why in report["unreadable"]:
        print(f"  could not read {path}: {why}")
    print(f"\n{len(report['added'])} file(s) hashed, {len(report['unchanged'])} unchanged, "
          f"{len(report['skipped'])} projector(s) skipped. Registry: {registry.path}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    catalog = reg.load_catalog()
    registry = reg.Registry.load(args.registry)
    sets = ("CORE", "EXTRA", "LATER", "SMOKE") if args.all else ("CORE",)
    p = reg.plan(catalog, registry, sets)
    print(f"Model plan (catalog checked {catalog['checked_on']}; D-55 core set{', plus optional' if args.all else ''}):\n")
    print(f"  {'':3} {'Label':5} {'Role':7} {'Model':12} {'Quant':7} {'QAT':4} {'License':11} Status")
    for r in p["rows"]:
        status = f"FOUND  {r['path']}" if r["status"] == "FOUND" else f"MISSING  {reg.human_bytes(r['download_bytes'])} from {r['source']}"
        print(f"  {'✓' if r['status'] == 'FOUND' else '·':3} {r['label']:5} {r['role']:7} {r['model']:12} {r['quant']:7} "
              f"{'yes' if r['qat'] else 'no':4} {r['license']:11} {status}")
    missing = [r for r in p["rows"] if r["status"] == "MISSING"]
    print(f"\nFound {len(p['rows']) - len(missing)} of {len(p['rows'])}. To download: {len(missing)} file(s), "
          f"{reg.human_bytes(p['download_bytes'])} into {reg.MODELS_DIR}.")
    try:
        free = shutil.disk_usage(reg.MODELS_DIR if reg.MODELS_DIR.exists() else reg.REPO).free
        print(f"Free disk space there: {reg.human_bytes(free)}.")
    except OSError:
        pass
    if p["others"]:
        print("\nOther models in the registry (usable by their local id, not part of the bake-off set):")
        for f in p["others"]:
            print(f"  {f['local_id']:<34} {f['header']['quantization'] or '?':<8} {f['path']}")
    if missing:
        labels = " ".join(r["label"] for r in missing)
        print(f"\nTo download them all: uv run python tools/models.py download {labels}")
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    catalog = reg.load_catalog()
    registry = reg.Registry.load(args.registry)
    if args.missing:
        wanted = [r["id"] for r in reg.plan(catalog, registry)["rows"] if r["status"] == "MISSING"]
    else:
        wanted = [reg.catalog_entry(catalog, name)["id"] for name in args.models]
    entries = []
    for model_id in dict.fromkeys(wanted):
        if registry.find(model_id):
            print(f"  {model_id}: already registered, nothing to download")
            continue
        entries.append(reg.catalog_entry(catalog, model_id))
    if not entries:
        print("Nothing to download.")
        return 0
    total = sum(e["sources"][0]["size_bytes"] for e in entries)
    print("About to download (pinned commit, SHA-256 checked):")
    for e in entries:
        s = e["sources"][0]
        print(f"  {e['label']:4} {e['model']} {e['quant']}{' QAT' if e['qat'] else ''}  {reg.human_bytes(s['size_bytes'])}  "
              f"{s['repo']}/{s['file']}  license {e['license']}")
    print(f"Total {reg.human_bytes(total)} into {reg.MODELS_DIR}")
    if not args.yes:
        answer = input('Type "yes" to download: ').strip().lower()
        if answer != "yes":
            print("Nothing downloaded.")
            return 1
    failed = 0
    for e in entries:
        print(f"\n{e['label']} {e['sources'][0]['file']}")
        try:
            entry = reg.download(e, registry, progress=_bar("download"))
            registry.save()
            print(f"  verified and registered as {entry['local_id']}")
        except reg.ModelError as exc:
            failed += 1
            print(f"  FAILED: {exc}")
    return 1 if failed else 0


def cmd_list(args: argparse.Namespace) -> int:
    registry = reg.Registry.load(args.registry)
    if not registry.files:
        print("The registry is empty. Run: uv run python tools/models.py scan <folder>")
        return 0
    for f in sorted(registry.files, key=lambda f: f["local_id"]):
        here = "" if Path(f["path"]).is_file() else "  (file missing)"
        print(f"  {f['local_id']:<34} {f['header']['quantization'] or '?':<8} {f['sha256'][:12]}  {f['path']}{here}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/models.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=reg.REGISTRY_PATH, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan", help="register the .gguf files in a folder")
    p_scan.add_argument("folder")
    p_scan.add_argument("--quiet", action="store_true")
    p_plan = sub.add_parser("plan", help="compare the registry with the catalog")
    p_plan.add_argument("--all", action="store_true")
    p_dl = sub.add_parser("download", help="download catalog models you name")
    p_dl.add_argument("models", nargs="*")
    p_dl.add_argument("--missing", action="store_true")
    p_dl.add_argument("--yes", action="store_true", help="do not ask (you confirmed the list already)")
    sub.add_parser("list", help="show the registry")
    args = parser.parse_args(argv)
    if args.command == "download" and not args.models and not args.missing:
        parser.error("name the models to download (labels such as F3 N1), or use --missing")
    try:
        return {"scan": cmd_scan, "plan": cmd_plan, "download": cmd_download, "list": cmd_list}[args.command](args)
    except reg.ModelError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
