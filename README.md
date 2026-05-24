# agent-output-schema

Validate structured agent outputs against a declared field schema. Zero dependencies.

## Install

```bash
pip install agent-output-schema
```

## Quick start

```python
from agent_output_schema import FieldSpec, OutputSchema
from agent_output_schema.core import between, min_length, max_length, one_of

schema = OutputSchema([
    FieldSpec("title",   str,   required=True,  validators=[min_length(3)]),
    FieldSpec("score",   float, required=True,  validators=[between(0.0, 1.0)]),
    FieldSpec("status",  str,   required=True,  validators=[one_of("ok", "error")]),
    FieldSpec("summary", str,   required=False, validators=[max_length(200)]),
])

result = schema.validate({"title": "Hi", "score": 1.5, "status": "ok"})
print(result.is_valid)   # False
for e in result.errors:
    print(e.field, e.message)
# title  value too short (min_length=3, got 2)
# score  value 1.5 is above maximum 1.0
```

## API

### `OutputSchema(fields)`

Define the expected shape of an output dict.

Raises `ValueError` if two fields share the same name.

### `OutputSchema.validate(data) → SchemaResult`

Validate a dict. Returns a `SchemaResult`.

### `FieldSpec`

| Argument | Type | Description |
|---|---|---|
| `name` | `str` | Key in the output dict |
| `type_` | `type \| None` | Expected Python type (`None` = any type) |
| `required` | `bool` | Default `True`; missing/`None` is an error |
| `validators` | `list` | List of validator callables |

### `SchemaResult`

| Attribute/Method | Description |
|---|---|
| `is_valid` | `True` when no errors found |
| `errors` | List of `SchemaError` objects |
| `errors_for(field)` | Errors for a specific field |
| `summary()` | Human-readable text |
| `to_dict()` | JSON-serialisable representation |

### Built-in validators

```python
from agent_output_schema.core import (
    min_length, max_length,   # for str / list
    min_value, max_value,     # for int / float
    between,                  # min_value + max_value combined
    one_of,                   # membership check
    regex_match,              # regex pattern
)
```

Any callable `(value) -> str | None` works as a validator — return `None` for pass, a string for fail.

## License

MIT
