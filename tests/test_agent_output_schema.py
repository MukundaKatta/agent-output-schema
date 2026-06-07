"""Tests for agent-output-schema."""

from __future__ import annotations

import pytest

from agent_output_schema import FieldSpec, OutputSchema, SchemaError, SchemaResult
from agent_output_schema.core import (
    between,
    max_length,
    max_value,
    min_length,
    min_value,
    one_of,
    regex_match,
)

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_min_length_pass():
    assert min_length(3)("hello") is None


def test_min_length_fail():
    msg = min_length(5)("hi")
    assert msg is not None
    assert "5" in msg


def test_max_length_pass():
    assert max_length(10)("hello") is None


def test_max_length_fail():
    msg = max_length(3)("toolong")
    assert msg is not None
    assert "3" in msg


def test_min_value_pass():
    assert min_value(0.0)(0.5) is None


def test_min_value_fail():
    msg = min_value(1.0)(0.5)
    assert msg is not None
    assert "0.5" in msg


def test_max_value_pass():
    assert max_value(1.0)(0.9) is None


def test_max_value_fail():
    msg = max_value(1.0)(1.5)
    assert msg is not None
    assert "1.5" in msg


def test_between_pass():
    assert between(0.0, 1.0)(0.5) is None


def test_between_fail_low():
    msg = between(0.0, 1.0)(-0.1)
    assert msg is not None


def test_between_fail_high():
    msg = between(0.0, 1.0)(1.1)
    assert msg is not None


def test_one_of_pass():
    assert one_of("a", "b", "c")("b") is None


def test_one_of_fail():
    msg = one_of("a", "b")("z")
    assert msg is not None
    assert "z" in msg


def test_regex_match_pass():
    assert regex_match(r"^\d+$")("123") is None


def test_regex_match_fail():
    msg = regex_match(r"^\d+$")("abc")
    assert msg is not None


def test_min_length_non_string_with_len():
    # also works on lists
    assert min_length(2)([1, 2, 3]) is None
    msg = min_length(5)([1, 2])
    assert msg is not None


# ---------------------------------------------------------------------------
# FieldSpec
# ---------------------------------------------------------------------------


def test_field_spec_defaults():
    fs = FieldSpec("name", str)
    assert fs.required is True
    assert fs.validators == []


def test_field_spec_optional():
    fs = FieldSpec("score", float, required=False)
    assert not fs.required


# ---------------------------------------------------------------------------
# SchemaError
# ---------------------------------------------------------------------------


def test_schema_error_to_dict():
    e = SchemaError(field="title", message="too short")
    d = e.to_dict()
    assert d["field"] == "title"
    assert d["message"] == "too short"


def test_schema_error_repr():
    e = SchemaError(field="x", message="bad")
    r = repr(e)
    assert "x" in r
    assert "bad" in r


# ---------------------------------------------------------------------------
# SchemaResult
# ---------------------------------------------------------------------------


def test_schema_result_valid():
    result = SchemaResult(errors=[])
    assert result.is_valid


def test_schema_result_invalid():
    result = SchemaResult(errors=[SchemaError("x", "bad")])
    assert not result.is_valid


def test_schema_result_errors_for():
    e1 = SchemaError("a", "err1")
    e2 = SchemaError("b", "err2")
    result = SchemaResult(errors=[e1, e2])
    assert len(result.errors_for("a")) == 1
    assert len(result.errors_for("b")) == 1
    assert len(result.errors_for("c")) == 0


def test_schema_result_summary_valid():
    result = SchemaResult(errors=[])
    assert result.summary() == "(valid)"


def test_schema_result_summary_with_errors():
    result = SchemaResult(errors=[SchemaError("score", "too high")])
    s = result.summary()
    assert "score" in s
    assert "too high" in s


def test_schema_result_to_dict():
    result = SchemaResult(errors=[])
    d = result.to_dict()
    assert d["is_valid"] is True
    assert d["errors"] == []


def test_schema_result_repr():
    result = SchemaResult(errors=[])
    assert "SchemaResult" in repr(result)


# ---------------------------------------------------------------------------
# OutputSchema construction
# ---------------------------------------------------------------------------


def test_output_schema_field_names():
    schema = OutputSchema([FieldSpec("a", str), FieldSpec("b", int)])
    assert schema.field_names == ["a", "b"]


def test_output_schema_repr():
    schema = OutputSchema([FieldSpec("x", str)])
    assert "OutputSchema" in repr(schema)


def test_output_schema_duplicate_field_raises():
    with pytest.raises(ValueError, match="Duplicate"):
        OutputSchema([FieldSpec("a", str), FieldSpec("a", int)])


# ---------------------------------------------------------------------------
# OutputSchema.validate — required fields
# ---------------------------------------------------------------------------


def test_validate_empty_dict_required():
    schema = OutputSchema([FieldSpec("title", str, required=True)])
    result = schema.validate({})
    assert not result.is_valid
    assert len(result.errors_for("title")) == 1


def test_validate_required_none_value():
    schema = OutputSchema([FieldSpec("title", str, required=True)])
    result = schema.validate({"title": None})
    assert not result.is_valid


def test_validate_required_present():
    schema = OutputSchema([FieldSpec("title", str, required=True)])
    result = schema.validate({"title": "Hello"})
    assert result.is_valid


def test_validate_optional_absent():
    schema = OutputSchema([FieldSpec("tag", str, required=False)])
    result = schema.validate({})
    assert result.is_valid


def test_validate_optional_none():
    schema = OutputSchema([FieldSpec("tag", str, required=False)])
    result = schema.validate({"tag": None})
    assert result.is_valid


# ---------------------------------------------------------------------------
# OutputSchema.validate — type checks
# ---------------------------------------------------------------------------


def test_validate_type_correct():
    schema = OutputSchema([FieldSpec("score", float)])
    result = schema.validate({"score": 0.5})
    assert result.is_valid


def test_validate_type_wrong():
    schema = OutputSchema([FieldSpec("score", float)])
    result = schema.validate({"score": "high"})
    assert not result.is_valid
    msg = result.errors_for("score")[0].message
    assert "float" in msg
    assert "str" in msg


def test_validate_type_none_accepts_any():
    schema = OutputSchema([FieldSpec("data", None)])
    result = schema.validate({"data": [1, 2, 3]})
    assert result.is_valid


def test_validate_list_type():
    schema = OutputSchema([FieldSpec("items", list)])
    assert schema.validate({"items": [1, 2]}).is_valid
    assert not schema.validate({"items": "not a list"}).is_valid


def test_validate_dict_type():
    schema = OutputSchema([FieldSpec("meta", dict)])
    assert schema.validate({"meta": {"k": "v"}}).is_valid
    assert not schema.validate({"meta": [1, 2]}).is_valid


# ---------------------------------------------------------------------------
# OutputSchema.validate — validators
# ---------------------------------------------------------------------------


def test_validate_with_min_length():
    schema = OutputSchema([FieldSpec("title", str, validators=[min_length(5)])])
    assert not schema.validate({"title": "Hi"}).is_valid
    assert schema.validate({"title": "Hello there"}).is_valid


def test_validate_with_between():
    schema = OutputSchema([FieldSpec("score", float, validators=[between(0.0, 1.0)])])
    assert schema.validate({"score": 0.5}).is_valid
    assert not schema.validate({"score": 1.5}).is_valid


def test_validate_multiple_validators_both_fail():
    schema = OutputSchema(
        [FieldSpec("name", str, validators=[min_length(3), max_length(5)])]
    )
    result = schema.validate({"name": "toolongvalue"})
    assert not result.is_valid
    assert len(result.errors_for("name")) >= 1


def test_validate_one_of_validator():
    schema = OutputSchema(
        [FieldSpec("status", str, validators=[one_of("ok", "error", "pending")])]
    )
    assert schema.validate({"status": "ok"}).is_valid
    assert not schema.validate({"status": "unknown"}).is_valid


# ---------------------------------------------------------------------------
# OutputSchema.validate — complex case
# ---------------------------------------------------------------------------


def test_validate_full_schema():
    schema = OutputSchema(
        [
            FieldSpec("title", str, required=True, validators=[min_length(3)]),
            FieldSpec("score", float, required=True, validators=[between(0.0, 1.0)]),
            FieldSpec("tags", list, required=False),
            FieldSpec("summary", str, required=False, validators=[max_length(200)]),
        ]
    )

    # Valid
    result = schema.validate({"title": "Analysis", "score": 0.8})
    assert result.is_valid

    # Invalid: title too short, score out of range
    result = schema.validate({"title": "Hi", "score": 2.0})
    assert not result.is_valid
    assert len(result.errors_for("title")) >= 1
    assert len(result.errors_for("score")) >= 1


def test_validate_extra_keys_ignored():
    schema = OutputSchema([FieldSpec("x", str)])
    result = schema.validate({"x": "hello", "extra": 42})
    assert result.is_valid


# ---------------------------------------------------------------------------
# OutputSchema.validate — documented edge-case contracts
# ---------------------------------------------------------------------------


def test_validate_validators_run_on_wrong_type():
    # When a value has the wrong type but still triggers a validator (a list
    # has __len__), both the type error and the validator error are reported.
    schema = OutputSchema([FieldSpec("title", str, validators=[min_length(5)])])
    result = schema.validate({"title": ["a", "b"]})
    assert not result.is_valid
    messages = [e.message for e in result.errors_for("title")]
    assert any("expected type 'str'" in m for m in messages)
    assert any("min_length=5" in m for m in messages)


def test_validate_optional_wrong_type_still_reported():
    # An optional field that is present but the wrong type is still type-checked.
    schema = OutputSchema([FieldSpec("score", float, required=False)])
    result = schema.validate({"score": "high"})
    assert not result.is_valid


def test_min_value_skips_non_numeric():
    # min_value is type-guarded: non-numeric values pass through untouched.
    assert min_value(0.0)("abc") is None
    assert min_value(0.0)([1, 2, 3]) is None


def test_max_value_skips_non_numeric():
    assert max_value(1.0)("abc") is None
    assert max_value(1.0)(None) is None


def test_regex_match_skips_non_string():
    # regex_match only applies to str values; non-strings pass.
    assert regex_match(r"^\d+$")(123) is None
    assert regex_match(r"^\d+$")(None) is None


def test_max_length_skips_lenless_value():
    # max_length only constrains values that have __len__.
    assert max_length(3)(42) is None


def test_result_errors_attribute_exposes_all_errors():
    # The README documents direct access to result.errors as the primary API.
    schema = OutputSchema(
        [
            FieldSpec("title", str, required=True, validators=[min_length(3)]),
            FieldSpec("score", float, required=True, validators=[between(0.0, 1.0)]),
        ]
    )
    result = schema.validate({"title": "Hi", "score": 1.5})
    assert not result.is_valid
    fields = {e.field for e in result.errors}
    assert fields == {"title", "score"}
