"""`latest` names the newest run folder (owner's checklists, 2026-11-25: placeholders such as
runs\\<the run folder> were typed literally, twice)."""

from __future__ import annotations

import os

import pytest

from range_service.eval.run_paths import RunPathError, resolve_run
from tools import recipe


def _run(root, name, mtime):
    d = root / name
    d.mkdir(parents=True)
    m = d / "run_manifest.json"
    m.write_text("{}", encoding="utf-8")
    os.utime(m, (mtime, mtime))
    return d


def test_latest_is_the_newest_run_folder(tmp_path):
    _run(tmp_path, "sb04_a", 1000)
    newest = _run(tmp_path, "sb04_b", 3000)
    _run(tmp_path, "sb04_c", 2000)
    (tmp_path / "not_a_run").mkdir()
    assert resolve_run("latest", tmp_path) == newest.resolve()
    assert resolve_run("LATEST", tmp_path) == newest.resolve()


def test_a_path_is_made_absolute_and_a_missing_one_explains_itself(tmp_path, monkeypatch):
    d = _run(tmp_path, "sb04_a", 1000)
    monkeypatch.chdir(tmp_path)
    assert resolve_run("sb04_a") == d.resolve()
    with pytest.raises(RunPathError, match="as printed after 'Run folder:'"):
        resolve_run("runs/<the run folder>")
    with pytest.raises(RunPathError, match="no run folder"):
        resolve_run("latest", tmp_path / "empty")


def test_recipe_show_names_the_known_recipes_instead_of_a_traceback(capsys):
    assert recipe.main(["show", "no_such_recipe"]) == 2
    out = capsys.readouterr().out
    assert "no recipe 'no_such_recipe'" in out and "sign_booth_c" in out
