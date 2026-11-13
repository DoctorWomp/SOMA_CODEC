# Build and run

Exact commands to set up the project and run every check. G0 has no app to launch yet: Godot arrives at G1.

## One-time setup

You need **uv** (it installs the right Python for you). On Windows, see [OWNER_SETUP_WINDOWS.md](OWNER_SETUP_WINDOWS.md). On Linux/macOS:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, in the repository folder, install the exact dependency versions from the lockfile:

```bash
uv sync --locked
```

## Run every check

This is the one command that must pass before any change is merged. CI runs it on Python 3.12 and 3.13 for every push and pull request.

```bash
uv run python tools/check.py
```

It runs three steps and prints a summary:

1. **Contracts**: every schema in `contracts/` is valid, every valid example passes and every invalid example fails for its stated reason.
2. **Configs**: every file in `configs/` matches its contract, and everything it refers to exists.
3. **Tests**: the full `pytest` suite.

`All checks passed.` and exit code 0 means green.

## Smaller commands

Check only the content files (useful after editing a YAML file):

```bash
uv run python tools/validate_configs.py
```

Run only the tests, or one test file:

```bash
uv run pytest
```

```bash
uv run pytest tests/test_delta.py -v
```

Run the checks on a specific Python version (uv downloads it if needed):

```bash
uv run --python 3.12 python tools/check.py
```

## Adding or changing a dependency

Dependencies are kept minimal (`jsonschema`, `pyyaml`, `pytest`). If one is truly needed, add it with uv so the lockfile updates, and commit both files:

```bash
uv add <package>
```
