"""A small JSON Schema validator for the subset the ``.puppet`` schemas use.

Checks ``$ref`` (to ``#/$defs/...``), ``type``, ``enum``, ``const``,
``properties``, ``required``, ``additionalProperties``, ``items``,
``minItems``, ``maxItems``, ``minimum``, ``maximum``, ``minLength``,
``allOf``, ``anyOf`` and ``if`` / ``then`` — enough for
:mod:`Imervue.puppet.format_schema` without a third-party package, so the
CLI and the MCP server can validate a file with the default dependencies.
Other keywords are ignored. Every error names the JSON path it was found at.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

_TYPES: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(instance: Any, schema: dict, *, root: dict | None = None,
             path: str = "$") -> list[str]:
    """Every way *instance* breaks *schema*, as ``"<path>: <problem>"`` strings."""
    root = schema if root is None else root
    if "$ref" in schema:
        return validate(instance, _resolve(root, schema["$ref"]), root=root, path=path)
    errors = _check_type(instance, schema, path)
    if errors:
        return errors            # the other keywords assume the right type
    for check in (_check_value, _check_object, _check_array, _check_combinators):
        errors.extend(check(instance, schema, root, path))
    return errors


def _resolve(root: dict, ref: str) -> dict:
    if not ref.startswith("#/"):
        raise ValueError(f"only local references are supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _check_type(instance: Any, schema: dict, path: str) -> list[str]:
    expected = schema.get("type")
    if expected is None:
        return []
    names = expected if isinstance(expected, list) else [expected]
    if any(_TYPES[name](instance) for name in names):
        return []
    return [f"{path}: expected {' or '.join(names)}, got {_type_name(instance)}"]


def _type_name(value: Any) -> str:
    return next((name for name, test in _TYPES.items() if name != "number" and test(value)),
                "number" if _TYPES["number"](value) else type(value).__name__)


def _check_value(instance: Any, schema: dict, _root: dict, path: str) -> list[str]:
    errors = []
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if _TYPES["number"](instance):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is below the minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is above the maximum {schema['maximum']}")
    if isinstance(instance, str) and len(instance) < schema.get("minLength", 0):
        errors.append(f"{path}: shorter than {schema['minLength']} characters")
    return errors


def _check_object(instance: Any, schema: dict, root: dict, path: str) -> list[str]:
    if not isinstance(instance, dict):
        return []
    errors = [f"{path}: missing required key {key!r}"
              for key in schema.get("required", ()) if key not in instance]
    properties = schema.get("properties", {})
    extra = schema.get("additionalProperties", True)
    for key, value in instance.items():
        child = f"{path}.{key}"
        if key in properties:
            errors.extend(validate(value, properties[key], root=root, path=child))
        elif extra is False:
            errors.append(f"{child}: unknown key")
        elif isinstance(extra, dict):
            errors.extend(validate(value, extra, root=root, path=child))
    return errors


def _check_array(instance: Any, schema: dict, root: dict, path: str) -> list[str]:
    if not isinstance(instance, list):
        return []
    errors = []
    if len(instance) < schema.get("minItems", 0):
        errors.append(f"{path}: needs at least {schema['minItems']} items, has {len(instance)}")
    if "maxItems" in schema and len(instance) > schema["maxItems"]:
        errors.append(f"{path}: allows at most {schema['maxItems']} items, has {len(instance)}")
    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(instance):
            errors.extend(validate(item, items, root=root, path=f"{path}[{index}]"))
    return errors


def _check_combinators(instance: Any, schema: dict, root: dict, path: str) -> list[str]:
    errors = []
    for sub in schema.get("allOf", ()):
        errors.extend(validate(instance, sub, root=root, path=path))
    options = schema.get("anyOf")
    if options and all(validate(instance, sub, root=root, path=path) for sub in options):
        errors.append(f"{path}: matches none of the allowed shapes")
    condition = schema.get("if")
    if condition is not None and not validate(instance, condition, root=root, path=path):
        errors.extend(validate(instance, schema.get("then", {}), root=root, path=path))
    return errors
