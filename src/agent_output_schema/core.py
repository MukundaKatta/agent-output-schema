"""Validate structured agent outputs against a declared field schema.

Define the shape of your agent's final output once.  Validate any dict
against that shape and get a clear list of every field-level error.
No external dependencies — works with plain Python dicts.

Example::

    from agent_output_schema import FieldSpec, OutputSchema

    schema = OutputSchema([
        FieldSpec("title",    str,   required=True,  validators=[min_length(3)]),
        FieldSpec("score",    float, required=True,  validators=[between(0.0, 1.0)]),
        FieldSpec("tags",     list,  required=False),
        FieldSpec("summary",  str,   required=False, validators=[max_length(200)]),
    ])

    result = schema.validate({
        "title": "Hi",
        "score": 1.5,
    })

    print(result.is_valid)   # False
    for e in result.errors:
        print(e.field, e.message)
    # title  value too short (min_length=3)
    # score  value 1.5 is above maximum 1.0
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Validator helpers  (return None on success, str on failure)
# ---------------------------------------------------------------------------

ValidatorFn = Callable[[Any], str | None]


def min_length(n: int) -> ValidatorFn:
    """Value must have ``len() >= n``."""

    def _check(v: Any) -> str | None:
        if hasattr(v, "__len__") and len(v) < n:
            return f"value too short (min_length={n}, got {len(v)})"
        return None

    return _check


def max_length(n: int) -> ValidatorFn:
    """Value must have ``len() <= n``."""

    def _check(v: Any) -> str | None:
        if hasattr(v, "__len__") and len(v) > n:
            return f"value too long (max_length={n}, got {len(v)})"
        return None

    return _check


def min_value(lo: float) -> ValidatorFn:
    """Numeric value must be ``>= lo``."""

    def _check(v: Any) -> str | None:
        if isinstance(v, (int, float)) and v < lo:
            return f"value {v} is below minimum {lo}"
        return None

    return _check


def max_value(hi: float) -> ValidatorFn:
    """Numeric value must be ``<= hi``."""

    def _check(v: Any) -> str | None:
        if isinstance(v, (int, float)) and v > hi:
            return f"value {v} is above maximum {hi}"
        return None

    return _check


def between(lo: float, hi: float) -> ValidatorFn:
    """Numeric value must be ``lo <= v <= hi``."""
    _lo = min_value(lo)
    _hi = max_value(hi)

    def _check(v: Any) -> str | None:
        return _lo(v) or _hi(v)

    return _check


def one_of(*allowed: Any) -> ValidatorFn:
    """Value must be in *allowed*."""

    def _check(v: Any) -> str | None:
        if v not in allowed:
            return f"value {v!r} not in allowed set {list(allowed)}"
        return None

    return _check


def regex_match(pattern: str) -> ValidatorFn:
    """String value must match *pattern*."""
    _pat = re.compile(pattern)

    def _check(v: Any) -> str | None:
        if isinstance(v, str) and not _pat.search(v):
            return f"value {v!r} does not match pattern {pattern!r}"
        return None

    return _check


# ---------------------------------------------------------------------------
# FieldSpec
# ---------------------------------------------------------------------------

# Mapping from Python type to human-readable name
_TYPE_NAMES: dict[type, str] = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    list: "list",
    dict: "dict",
}


@dataclass
class FieldSpec:
    """Specification for a single field in an output schema.

    Attributes:
        name:       Field name (key in the output dict).
        type_:      Expected Python type.  ``None`` means any type accepted.
        required:   If ``True``, the field must be present and non-``None``.
        validators: Optional list of callables ``(value) -> error_str | None``.
    """

    name: str
    type_: type | None = None
    required: bool = True
    validators: list[ValidatorFn] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SchemaError
# ---------------------------------------------------------------------------


@dataclass
class SchemaError:
    """A single field-level validation error.

    Attributes:
        field:   Name of the offending field.
        message: Human-readable description of the problem.
    """

    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable dict."""
        return {"field": self.field, "message": self.message}

    def __repr__(self) -> str:
        return f"SchemaError(field={self.field!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# SchemaResult
# ---------------------------------------------------------------------------


@dataclass
class SchemaResult:
    """Outcome of validating a dict against an :class:`OutputSchema`.

    Attributes:
        errors: All detected :class:`SchemaError` objects.
    """

    errors: list[SchemaError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """``True`` when no errors were found."""
        return not self.errors

    def errors_for(self, field_name: str) -> list[SchemaError]:
        """Return errors for a specific field name."""
        return [e for e in self.errors if e.field == field_name]

    def summary(self) -> str:
        """Return a compact human-readable summary."""
        if not self.errors:
            return "(valid)"
        return "\n".join(f"{e.field}: {e.message}" for e in self.errors)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict."""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
        }

    def __repr__(self) -> str:
        return f"SchemaResult(is_valid={self.is_valid}, errors={len(self.errors)})"


# ---------------------------------------------------------------------------
# OutputSchema
# ---------------------------------------------------------------------------


class OutputSchema:
    """A collection of :class:`FieldSpec` objects that defines the expected
    shape of an agent's output dict.

    Args:
        fields: Sequence of :class:`FieldSpec` objects.

    Raises:
        ValueError: If two fields share the same name.
    """

    def __init__(self, fields: list[FieldSpec]) -> None:
        names = [f.name for f in fields]
        if len(names) != len(set(names)):
            dupes = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate field names: {sorted(set(dupes))}")
        self._fields = list(fields)

    @property
    def field_names(self) -> list[str]:
        """Names of all declared fields."""
        return [f.name for f in self._fields]

    def validate(self, data: dict[str, Any]) -> SchemaResult:
        """Validate *data* against this schema.

        Args:
            data: The dict to validate.

        Returns:
            A :class:`SchemaResult` with all detected errors.
        """
        errors: list[SchemaError] = []

        for spec in self._fields:
            present = spec.name in data
            value = data.get(spec.name)

            # Missing required field
            if spec.required and (not present or value is None):
                errors.append(
                    SchemaError(
                        field=spec.name,
                        message="required field is missing or None",
                    )
                )
                continue  # no point checking type/validators

            # Skip optional absent fields
            if not present or value is None:
                continue

            # Type check
            if spec.type_ is not None and not isinstance(value, spec.type_):
                expected = _TYPE_NAMES.get(spec.type_, spec.type_.__name__)
                actual = type(value).__name__
                errors.append(
                    SchemaError(
                        field=spec.name,
                        message=f"expected type {expected!r}, got {actual!r}",
                    )
                )
                # Still run validators — they may produce useful messages
                # even for wrong types (e.g., wrong-type strings still have len)

            # Run validators
            for validator in spec.validators:
                msg = validator(value)
                if msg:
                    errors.append(SchemaError(field=spec.name, message=msg))

        return SchemaResult(errors=errors)

    def __repr__(self) -> str:
        return f"OutputSchema(fields={self.field_names})"
