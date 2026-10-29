"""Expression parameter validation and expression-file JSON representation."""
from __future__ import annotations

from Imervue.puppet.document import EXPRESSION_MODES, SCHEMA_VERSION, Expression, ExpressionParam
from Imervue.puppet.format_schema import SCHEMA_FIELD, SCHEMA_URLS
from Imervue.puppet.format_values import PuppetFormatError, _dumps, _require_keys


def _parse_expression(name: str, raw: dict) -> Expression:
    return Expression(
        name=name,
        params=[_parse_expr_param(p) for p in raw.get("params", [])],
    )


def _parse_expr_param(raw: dict) -> ExpressionParam:
    _require_keys(raw, ("id", "value"), "expression param")
    mode = raw.get("mode", "additive")
    if mode not in EXPRESSION_MODES:
        raise PuppetFormatError(f"expression mode {mode!r} not in {EXPRESSION_MODES}")
    return ExpressionParam(id=str(raw["id"]), value=float(raw["value"]), mode=mode)


def _expression_json_bytes(expr: Expression) -> bytes:
    payload = {
        SCHEMA_FIELD: SCHEMA_URLS["expression"],
        "version": SCHEMA_VERSION,
        "params": [
            {"id": p.id, "value": p.value, "mode": p.mode}
            for p in expr.params
        ],
    }
    return _dumps(payload)
