"""Verify hosted complexity against every current runtime Python source."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode, urlparse
from urllib.request import urlopen

THRESHOLD = 20
RUNTIME_ROOTS = ("Imervue", "plugins")
_REPOSITORY = "organizations/gh/JeffreyChen-s-Utils/repositories/Imervue"
_API = "https://app.codacy.com/api/v3/"
_DATA_NODES = {
    ast.Module, ast.Expr, ast.Assign, ast.Name, ast.Load, ast.Store, ast.Constant,
    ast.Dict, ast.List, ast.Tuple, ast.Set, ast.UnaryOp, ast.USub, ast.UAdd,
    ast.BinOp, ast.Add,
}


def git_output(root: Path, *args: str, data: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], input=data, capture_output=True, check=True,
    ).stdout


def read_snapshot(path: Path) -> tuple[str, dict[str, int]]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    return validate_snapshot(raw)


def validate_snapshot(raw: dict) -> tuple[str, dict[str, int]]:
    revision = raw["revision"]
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("snapshot requires a full analysis commit SHA")
    scores = {}
    for row in raw["files"]:
        name, score = row["path"], row["complexity"]
        if not isinstance(name, str) or any(char in name for char in "\\\n\r\t\0"):
            raise ValueError("snapshot paths must be relative POSIX paths")
        canonical = PurePosixPath(name)
        if canonical.as_posix() != name:
            raise ValueError(f"noncanonical snapshot path: {name}")
        parts = canonical.parts
        if not parts or parts[0] not in RUNTIME_ROOTS or ".." in parts:
            raise ValueError(f"snapshot path outside runtime roots: {name}")
        if name in scores:
            raise ValueError(f"duplicate snapshot path: {name}")
        if isinstance(score, bool) or not isinstance(score, int) or score < 0:
            raise ValueError(f"invalid complexity for {name}")
        scores[name] = score
    if not scores:
        raise ValueError("empty hosted analysis is not verification")
    return revision, scores


def _https_urlopen(url: str):
    if urlparse(url).scheme != "https":
        raise ValueError("hosted analysis requires HTTPS")
    return urlopen(url, timeout=30)  # nosec B310  # scheme validated above


def fetch_json(url: str) -> dict:
    for attempt in range(3):
        try:
            with _https_urlopen(url) as response:
                return json.load(response)
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("unreachable request retry state")


def analyzed_revision(metadata: dict, branch: str) -> str:
    data = metadata["data"]
    selected = data["selectedBranch"]
    commit = data["lastAnalysedCommit"]
    if selected["name"] != branch or selected["lastCommit"] != commit["sha"]:
        raise ValueError("requested branch head has not finished analysis")
    if not commit.get("endedAnalysis"):
        raise ValueError("hosted analysis is still running")
    return commit["sha"]


def capture_snapshot(branch: str, fetch=fetch_json) -> dict:
    metadata_url = _API + "analysis/" + _REPOSITORY + "?" + urlencode({"branch": branch})
    revision = analyzed_revision(fetch(metadata_url), branch)
    files, pages = [], []
    for area in RUNTIME_ROOTS:
        cursor, seen = None, set()
        while True:
            query = {"branch": branch, "search": area + "/", "sort": "filename",
                     "direction": "asc", "limit": 100}
            if cursor is not None:
                query["cursor"] = cursor
            page = fetch(_API + _REPOSITORY + "/files?" + urlencode(query))
            rows = page["data"]
            files.extend({"path": row["path"], "complexity": row.get("complexity")}
                         for row in rows if row["path"].endswith(".py"))
            following = page["pagination"].get("cursor")
            pages.append({"scope": area, "cursor": cursor,
                          "next_cursor": following, "rows": len(rows)})
            if following is None:
                break
            if not isinstance(following, str) or not following or following in seen:
                raise ValueError("invalid or repeated hosted pagination cursor")
            seen.add(following)
            cursor = following
    if analyzed_revision(fetch(metadata_url), branch) != revision:
        raise ValueError("analysis revision changed during capture")
    snapshot = {"revision": revision, "branch": branch,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "source": _API + _REPOSITORY + "/files", "pages": pages, "files": files}
    validate_snapshot(snapshot)
    return snapshot


def revision_blobs(root: Path, revision: str) -> dict[str, str]:
    output = git_output(root, "ls-tree", "-r", "-z", revision, "--", *RUNTIME_ROOTS)
    blobs = {}
    for record in output.split(b"\0"):
        if record:
            metadata, name = record.split(b"\t", 1)
            blobs[name.decode("utf-8")] = metadata.split()[2].decode("ascii")
    return blobs


def _scan_error(error: OSError) -> None:
    raise error


def _reject_link(path: Path) -> None:
    if path.is_symlink() or path.resolve() != path:
        raise ValueError(f"runtime source link is not allowed: {path}")


def current_sources(root: Path) -> list[Path]:
    sources = []
    for area in RUNTIME_ROOTS:
        directory = root / area
        if not directory.is_dir():
            raise ValueError(f"missing runtime directory: {directory}")
        _reject_link(directory)
        for folder, directories, files in os.walk(directory, onerror=_scan_error):
            for name in directories:
                _reject_link(Path(folder) / name)
            for name in files:
                if name.endswith(".py"):
                    path = Path(folder) / name
                    _reject_link(path)
                    sources.append(path)
    if not sources:
        raise ValueError("empty source tree is not verification")
    return sorted(sources)


def inspect_source(source: bytes, *, name: str, score: int | None, unchanged: bool) -> dict:
    tree = ast.parse(source.decode("utf-8-sig"), filename=name)
    data_only = all(type(node) in _DATA_NODES for node in ast.walk(tree))
    if score is None:
        state = "data_only" if data_only else "missing_analysis"
    elif not unchanged:
        state = "changed_since_analysis"
    else:
        state = "over_threshold" if score > THRESHOLD else "verified"
    return {"state": state, "hosted_complexity": score,
            "sha256": hashlib.sha256(source).hexdigest()}


def inventory(root: Path, snapshot: Path) -> dict:
    root = root.resolve()
    actual_root = Path(git_output(root, "rev-parse", "--show-toplevel").decode().strip())
    if actual_root.resolve() != root:
        raise ValueError("root must be the Git worktree root")
    revision, scores = read_snapshot(snapshot)
    blobs = revision_blobs(root, revision)
    paths = current_sources(root)
    contents = {path.relative_to(root).as_posix(): path.read_bytes() for path in paths}
    files = {}
    for name, source in contents.items():
        blob = git_output(root, "hash-object", "--stdin", f"--path={name}",
                          data=source).decode().strip()
        files[name] = inspect_source(source, name=name, score=scores.get(name),
                                     unchanged=blobs.get(name) == blob)
    if paths != current_sources(root):
        raise ValueError("runtime source paths changed during inventory")
    for name, source in contents.items():
        if (root / name).read_bytes() != source:
            raise ValueError(f"runtime source changed during inventory: {name}")
    groups = {state: [name for name, row in files.items() if row["state"] == state]
              for state in ("verified", "data_only", "over_threshold",
                            "missing_analysis", "changed_since_analysis")}
    incomplete = bool(groups["missing_analysis"] or groups["changed_since_analysis"])
    status = "inconclusive" if incomplete else (
        "not_verified" if groups["over_threshold"] else "verified")
    return {"status": status, "analysis_revision": revision, "threshold": THRESHOLD,
            "counts": {state: len(names) for state, names in groups.items()},
            "groups": groups, "files": files}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refresh-from-branch")
    args = parser.parse_args(argv)
    try:
        if args.refresh_from_branch:
            snapshot = capture_snapshot(args.refresh_from_branch)
            args.snapshot.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
        report = inventory(args.root, args.snapshot)
    except (
        ValueError, KeyError, TypeError, OSError, SyntaxError, subprocess.CalledProcessError,
    ) as exc:
        report = {"status": "inconclusive", "error": str(exc)}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ("groups", "files")}, ensure_ascii=False))
    return {"verified": 0, "not_verified": 1, "inconclusive": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
