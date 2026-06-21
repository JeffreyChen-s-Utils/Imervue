"""Plugin manifest schema + version / dependency compatibility checks.

Plugins declare metadata as class attributes (``plugin_name`` /
``plugin_version`` / …) but nothing validates them or checks whether a
plugin's required host version and pip packages are satisfied before the
manager loads it. These pure helpers parse a manifest, validate its shape, and
decide whether the host can load it — no Qt, no import side effects.

A plugin opts into compatibility checks with three optional class attributes:
``plugin_requires_imervue`` (a constraint like ``">=1.0,<2.0"``),
``plugin_requires_packages`` (a list of pip distribution names), and
``plugin_api_version``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_LEADING_INT = re.compile(r"\d+")
_CONSTRAINT = re.compile(r"^(>=|<=|==|!=|>|<)\s*(.+)$")


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a dotted version into a comparable int tuple.

    Stops at the first non-numeric segment, so pre-release suffixes are
    dropped: ``"1.2.3-rc1"`` → ``(1, 2, 3)``. An unparseable value yields an
    empty tuple (which sorts below any real version).
    """
    if not isinstance(version, str):
        return ()
    parts: list[int] = []
    for chunk in version.strip().split("."):
        match = _LEADING_INT.match(chunk)
        if match is None:
            break
        parts.append(int(match.group()))
    return tuple(parts)


def _compare(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    """Three-way compare two version tuples, zero-padding to equal length."""
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


_OPS = {
    ">=": lambda c: c >= 0, "<=": lambda c: c <= 0,
    ">": lambda c: c > 0, "<": lambda c: c < 0,
    "==": lambda c: c == 0, "!=": lambda c: c != 0,
}


def version_satisfies(version: str, constraint: str | None) -> bool:
    """True when *version* meets *constraint*.

    *constraint* is a comma-separated list of ``op version`` clauses, AND-ed
    together — e.g. ``">=1.0,<2.0"``. Supported ops: ``>= <= > < == !=``. An
    empty / ``None`` constraint always passes. Raises ``ValueError`` on a
    malformed clause.
    """
    if not constraint or not str(constraint).strip():
        return True
    current = parse_version(version)
    for raw_clause in str(constraint).split(","):
        clause = raw_clause.strip()
        if not clause:
            continue
        match = _CONSTRAINT.match(clause)
        if match is None:
            raise ValueError(f"invalid version constraint {clause!r}")
        op, target = match.group(1), parse_version(match.group(2))
        if not _OPS[op](_compare(current, target)):
            return False
    return True


@dataclass
class PluginManifest:
    """Declared identity + compatibility requirements of one plugin."""

    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    requires_imervue: str = ""
    requires_packages: list[str] = field(default_factory=list)
    api_version: str = ""


def manifest_from_plugin(plugin: object) -> PluginManifest:
    """Read a :class:`PluginManifest` from a plugin instance / class."""
    def attr(name: str, default: Any) -> Any:
        return getattr(plugin, name, default)

    packages = attr("plugin_requires_packages", []) or []
    return PluginManifest(
        name=str(attr("plugin_name", "") or ""),
        version=str(attr("plugin_version", "0.0.0") or "0.0.0"),
        description=str(attr("plugin_description", "") or ""),
        author=str(attr("plugin_author", "") or ""),
        requires_imervue=str(attr("plugin_requires_imervue", "") or ""),
        requires_packages=list(packages) if isinstance(packages, (list, tuple)) else [],
        api_version=str(attr("plugin_api_version", "") or ""),
    )


def validate_manifest(manifest: PluginManifest) -> list[str]:
    """Return a list of problems with *manifest* (empty list = valid)."""
    errors: list[str] = []
    if not manifest.name.strip():
        errors.append("plugin name is required")
    if not parse_version(manifest.version):
        errors.append(f"version {manifest.version!r} is not a valid dotted version")
    if manifest.requires_imervue:
        try:
            version_satisfies("1.0.0", manifest.requires_imervue)
        except ValueError as exc:
            errors.append(f"requires_imervue: {exc}")
    if not isinstance(manifest.requires_packages, list) or not all(
        isinstance(p, str) for p in manifest.requires_packages
    ):
        errors.append("requires_packages must be a list of strings")
    return errors


def _normalise_package(name: str) -> str:
    """Canonical distribution name for comparison (PEP 503-ish)."""
    return name.strip().lower().replace("_", "-")


def check_compatibility(
    manifest: PluginManifest,
    host_version: str,
    installed_packages: set[str],
) -> tuple[bool, list[str]]:
    """Return ``(can_load, reasons)`` for *manifest* against the host.

    *installed_packages* is the set of available distribution names (compared
    case- and separator-insensitively). A plugin with no requirements always
    loads.
    """
    reasons: list[str] = []
    if manifest.requires_imervue and not version_satisfies(
        host_version, manifest.requires_imervue,
    ):
        reasons.append(
            f"needs Imervue {manifest.requires_imervue} (host is {host_version})",
        )
    installed = {_normalise_package(p) for p in installed_packages}
    missing = [
        pkg for pkg in manifest.requires_packages
        if _normalise_package(pkg) not in installed
    ]
    if missing:
        reasons.append(f"missing packages: {', '.join(missing)}")
    return (not reasons, reasons)


def installed_packages() -> set[str]:
    """Return the set of installed distribution names (normalised)."""
    from importlib import metadata
    out: set[str] = set()
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") if dist.metadata else None
        if name:
            out.add(_normalise_package(name))
    return out
