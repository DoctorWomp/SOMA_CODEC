"""Every contract's valid examples pass, and invalid examples fail for the intended reason."""

from __future__ import annotations

import pytest

from range_service import contracts

from .helpers import EXAMPLES, all_examples, example_files, load_json

VALID = all_examples("valid")
INVALID = all_examples("invalid")


def _id(item):
    name, path = item
    return f"{name}/{path.stem}"


@pytest.mark.parametrize("item", VALID, ids=[_id(i) for i in VALID])
def test_valid_example_passes(item):
    name, path = item
    found = contracts.problems(name, load_json(path))
    assert not found, "\n".join(map(str, found))


@pytest.mark.parametrize("item", INVALID, ids=[_id(i) for i in INVALID])
def test_invalid_example_fails_for_the_stated_reason(item):
    name, path = item
    expected_keyword = load_json(EXAMPLES / name / "invalid" / "_expect.json")[path.stem]
    keywords = contracts.failing_keywords(name, load_json(path))
    assert keywords, f"{name}/{path.name} should be rejected but passed"
    assert expected_keyword in keywords, (
        f"{name}/{path.name} failed, but not for the stated reason {expected_keyword!r} (got {sorted(keywords)})"
    )


@pytest.mark.parametrize("name", sorted({n for n, _ in INVALID}))
def test_expect_index_matches_invalid_files(name):
    expected = load_json(EXAMPLES / name / "invalid" / "_expect.json")
    assert set(expected) == {p.stem for p in example_files(name, "invalid")}


# The shared rules, checked across every message contract by mutating its first valid example.
MESSAGES = [n for n in contracts.schema_names() if contracts.audience(n) in ("agent", "evaluator", "transport")]


@pytest.mark.parametrize("name", MESSAGES)
def test_unknown_top_level_field_rejected(name):
    instance = load_json(example_files(name, "valid")[0])
    instance["unexpected_field"] = "x"
    assert not contracts.is_valid(name, instance)


@pytest.mark.parametrize("name", MESSAGES)
def test_negative_and_fractional_ticks_rejected(name):
    instance = load_json(example_files(name, "valid")[0])
    tick_fields = [k for k in instance if "tick" in k and isinstance(instance[k], int)]
    for field in tick_fields:
        for bad in (-1, 1.5):
            mutated = dict(instance, **{field: bad})
            assert not contracts.is_valid(name, mutated), f"{name}.{field}={bad} was accepted"


@pytest.mark.parametrize("name", MESSAGES)
def test_missing_required_field_rejected(name):
    instance = load_json(example_files(name, "valid")[0])
    for field in contracts.load_schema(name)["required"]:
        mutated = {k: v for k, v in instance.items() if k != field}
        assert not contracts.is_valid(name, mutated), f"{name} accepted a message without {field!r}"


def test_error_messages_are_readable():
    found = contracts.problems("persona", {"schema_version": "1.0", "persona_id": "x", "trust_score": 3})
    text = "\n".join(map(str, found))
    assert "unknown field(s) 'trust_score' are not allowed" in text
    assert "'display_name' is required but missing" in text
