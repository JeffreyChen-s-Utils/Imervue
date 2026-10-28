"""Sample single-parameter keys and merge overrides in document order."""
from __future__ import annotations

from typing import Any

from Imervue.puppet.document import Parameter, PuppetDocument
from Imervue.puppet.runtime_blends import sample_blend_forms
from Imervue.puppet.runtime_forms import _blend_forms_dicts, _copy_forms, _merge_form_dicts_into
from Imervue.puppet.runtime_interpolation import bracket


def sample_parameter_forms(
    parameter: Parameter, value: float,
) -> dict[str, dict[str, Any]]:
    """Return ``{deformer_id: form_override}`` interpolated at the
    given parameter value.

    Behaviour:
    * No keys → empty dict (parameter has no effect).
    * One key → that key's forms.
    * Below the lowest / above the highest key → clamp to the edge
      key's forms.
    * Otherwise → linear interpolation between the two surrounding
      keys, per-deformer, per-field.
    """
    keys = parameter.keys
    if not keys:
        return {}
    sorted_keys = sorted(keys, key=lambda k: k.value)
    lo, hi, t = bracket([key.value for key in sorted_keys], value)
    if lo == hi:
        return _copy_forms(sorted_keys[lo].forms)
    return _blend_forms_dicts(sorted_keys[lo].forms, sorted_keys[hi].forms, t)



def merge_parameter_samples(
    document: PuppetDocument, values: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """Aggregate every parameter's sampled forms into a single
    ``{deformer_id: merged_form}`` dict.

    When two parameters both override the same field on the same
    deformer the later parameter (in document.parameters order) wins.
    Most rigs avoid this by keying disjoint deformers per parameter,
    but the runtime stays defined either way.

    Multi-axis :class:`ParameterBlend` groups are sampled after the
    single-parameter keys so a blend can override the per-axis result
    when both target the same deformer — matches Live2D's "the more
    specific keyform wins" intuition.
    """
    out: dict[str, dict[str, Any]] = {}
    for param in document.parameters:
        if param.id not in values:
            continue
        sampled = sample_parameter_forms(param, float(values[param.id]))
        _merge_form_dicts_into(out, sampled)
    for blend in document.parameter_blends:
        sampled = sample_blend_forms(blend, values)
        _merge_form_dicts_into(out, sampled)
    return out


def default_parameter_values(document: PuppetDocument) -> dict[str, float]:
    """Map every parameter to its default value — used by the canvas
    to seed the parameter-values dict on document load."""
    return {p.id: float(p.default) for p in document.parameters}
