"""A passing inventory requires fresh analysis of every runtime code file."""
import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts.complexity_inventory import inventory, main, read_snapshot
from scripts import complexity_inventory as module


@pytest.mark.parametrize("url", ["http://example.com", "file:///tmp/data", "ftp://example.com"])
def test_hosted_transport_rejects_non_https(url):
    with pytest.raises(ValueError, match="HTTPS"):
        module._https_urlopen(url)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "Imervue").mkdir()
    (root / "plugins").mkdir()
    (root / "Imervue/example.py").write_text("def value():\n    return 42\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "core.autocrlf", "false"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "Imervue/example.py"], check=True)
    subprocess.run([
        "git", "-C", str(root), "-c", "user.name=Fixture", "-c",
        "user.email=fixture@example.invalid", "commit", "-qm", "baseline",
    ], check=True)
    revision = subprocess.check_output([
        "git", "-C", str(root), "rev-parse", "HEAD",
    ], text=True).strip()
    (root / ".audit").mkdir()
    snapshot = root / ".audit/snapshot.json"
    snapshot.write_text(json.dumps({"revision": revision, "files": [
        {"path": "Imervue/example.py", "complexity": 1},
    ]}), encoding="utf-8")
    return root, snapshot


def test_fresh_complete_analysis_passes(project):
    report = inventory(*project)
    assert report["status"] == "verified"
    assert report["groups"]["verified"] == ["Imervue/example.py"]


def test_above_threshold_is_not_verified_even_when_other_files_pass(project):
    root, snapshot = project
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    raw["files"][0]["complexity"] = 21
    snapshot.write_text(json.dumps(raw), encoding="utf-8")
    report = inventory(root, snapshot)
    assert report["status"] == "not_verified"
    assert report["groups"]["over_threshold"] == ["Imervue/example.py"]


def test_same_paths_and_counts_cannot_hide_changed_code(project):
    root, snapshot = project
    (root / "Imervue/example.py").write_text("def value():\n    return 43\n", encoding="utf-8")
    report = inventory(root, snapshot)
    assert report["status"] == "inconclusive"
    assert report["groups"]["changed_since_analysis"] == ["Imervue/example.py"]


@pytest.mark.parametrize("area", ["Imervue", "plugins"])
def test_untracked_runtime_code_is_not_silently_omitted(project, area):
    root, snapshot = project
    (root / area / "new.py").write_text("def added():\n    return 7\n", encoding="utf-8")
    report = inventory(root, snapshot)
    assert report["status"] == "inconclusive"
    assert report["groups"]["missing_analysis"] == [f"{area}/new.py"]


def test_simple_translation_assignments_can_be_proven_without_hosted_metrics(project):
    root, snapshot = project
    language = root / "plugins/language.py"
    language.write_text('LABEL = "Open"\nWORDS = {"open": LABEL}\n', encoding="utf-8")
    report = inventory(root, snapshot)
    assert report["status"] == "verified"
    assert report["groups"]["data_only"] == ["plugins/language.py"]
    language.write_text('WORDS = load_translations()\n', encoding="utf-8")
    report = inventory(root, snapshot)
    assert report["groups"]["missing_analysis"] == ["plugins/language.py"]


@pytest.mark.parametrize("score", [None, True, -1, 2.5, "1"])
def test_missing_or_invalid_metrics_are_not_treated_as_zero(project, score):
    _, snapshot = project
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    raw["files"][0]["complexity"] = score
    snapshot.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid complexity"):
        read_snapshot(snapshot, root=snapshot.parent.parent)


def test_duplicate_pagination_rows_are_rejected(project):
    _, snapshot = project
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    raw["files"] *= 2
    snapshot.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate snapshot path"):
        read_snapshot(snapshot, root=snapshot.parent.parent)


def test_cli_reports_invalid_source_as_inconclusive(project, tmp_path):
    root, snapshot = project
    (root / "Imervue/example.py").write_text("def broken(:", encoding="utf-8")
    output = root / ".audit/report.json"
    code = main(["--root", str(root), "--snapshot", str(snapshot), "--output", str(output)])
    assert code == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "inconclusive"
    assert "invalid syntax" in report["error"]


@pytest.mark.parametrize("target", ["../outside.json", "Imervue/manifest.json", ".git/config"])
def test_cli_cannot_overwrite_files_outside_metadata_directories(project, target, capsys):
    root, snapshot = project
    destination = root / target
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(b"preserved")
    original = destination.read_bytes()
    code = main(["--root", str(root), "--snapshot", str(snapshot), "--output", target])
    assert code == 2
    assert destination.read_bytes() == original
    assert json.loads(capsys.readouterr().out)["status"] == "inconclusive"


def test_snapshot_outside_worktree_is_rejected(project, tmp_path):
    root, snapshot = project
    outside = tmp_path / "outside.json"
    outside.write_bytes(snapshot.read_bytes())
    with pytest.raises(ValueError, match="inside the worktree"):
        inventory(root, outside)


def test_metadata_link_cannot_escape_worktree(project, tmp_path, monkeypatch):
    root, _ = project
    link = root / ".audit/link.json"
    original = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda path, **kw: (
        tmp_path / "outside.json" if path == link else original(path, **kw)
    ))
    with pytest.raises(ValueError, match="inside the worktree"):
        module.metadata_path(root, link)


def test_relative_cli_paths_belong_to_selected_worktree(project, monkeypatch, tmp_path):
    root, snapshot = project
    monkeypatch.chdir(tmp_path)
    assert main(["--root", str(root), "--snapshot", ".audit/snapshot.json",
                 "--output", ".audit/report.json"]) == 0
    assert json.loads((snapshot.parent / "report.json").read_text())["status"] == "verified"


def test_report_cannot_replace_its_input_snapshot(project):
    root, snapshot = project
    original = snapshot.read_bytes()
    assert main(["--root", str(root), "--snapshot", str(snapshot),
                 "--output", str(snapshot)]) == 2
    assert snapshot.read_bytes() == original


def test_git_unavailable_produces_inconclusive_cli_result(project, monkeypatch, capsys):
    root, snapshot = project
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    assert main(["--root", str(root), "--snapshot", str(snapshot),
                 "--output", ".audit/report.json"]) == 2
    assert "Git is required" in json.loads(capsys.readouterr().out)["error"]


def test_git_helper_refuses_noninspection_commands(project):
    root, _ = project
    with pytest.raises(ValueError, match="read-only"):
        module.git_output(root, "reset", "--hard")


@pytest.mark.parametrize("arguments", [
    ("hash-object", "-w", "--stdin"),
    ("hash-object", "--stdin", "--path=../outside.py"),
    ("rev-parse", "--git-dir"),
    ("ls-tree", "-r", "-z", "HEAD", "--", "Imervue", "plugins"),
])
def test_git_inspection_rejects_write_flags_and_unvalidated_arguments(project, arguments):
    with pytest.raises(ValueError):
        module.git_output(project[0], *arguments)


@pytest.mark.parametrize("target", [".audit/snapshot.json", "Imervue/example.py"])
def test_report_cannot_modify_hard_linked_snapshot_or_source(project, target, capsys):
    root, snapshot = project
    original = (root / target).read_bytes()
    output = root / ".audit/report.json"
    output.hardlink_to(root / target)
    assert main(["--root", str(root), "--snapshot", str(snapshot),
                 "--output", str(output)]) == 2
    assert (root / target).read_bytes() == original
    assert output.read_bytes() == original
    assert json.loads(capsys.readouterr().out)["status"] == "inconclusive"


def test_refresh_cannot_modify_hard_linked_external_file(project, tmp_path, monkeypatch):
    root, snapshot = project
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    outside = tmp_path / "original.json"
    outside.write_bytes(b"preserved")
    linked = root / ".audit/linked.json"
    linked.hardlink_to(outside)
    monkeypatch.setattr(module, "capture_snapshot", lambda branch: raw)
    assert main(["--root", str(root), "--snapshot", str(linked),
                 "--output", ".audit/report.json", "--refresh-from-branch", "test"]) == 2
    assert outside.read_bytes() == b"preserved"
    report = json.loads((root / ".audit/report.json").read_text(encoding="utf-8"))
    assert "hard links" in report["error"]


def test_missing_report_parent_returns_inconclusive(project, capsys):
    root, snapshot = project
    assert main(["--root", str(root), "--snapshot", str(snapshot),
                 "--output", ".audit/missing/report.json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "inconclusive"


def test_report_write_failure_preserves_previous_report(project, monkeypatch, capsys):
    root, snapshot = project
    output = root / ".audit/report.json"
    output.write_bytes(b"previous report")

    def denied(*args):
        raise PermissionError("write denied")

    monkeypatch.setattr(module, "write_text_atomically", denied)
    assert main(["--root", str(root), "--snapshot", str(snapshot),
                 "--output", str(output)]) == 2
    assert output.read_bytes() == b"previous report"
    assert json.loads(capsys.readouterr().out)["error"] == "write denied"


def test_unreadable_directory_cannot_disappear_from_source_inventory(project, monkeypatch):
    root, snapshot = project
    original = module.os.scandir

    def fail_scan(path):
        if str(path) == str(root / "plugins"):
            raise PermissionError("blocked plugin directory")
        return original(path)

    monkeypatch.setattr(module.os, "scandir", fail_scan)
    with pytest.raises(PermissionError, match="blocked plugin directory"):
        inventory(root, snapshot)


def test_source_changed_during_git_hashing_is_inconclusive(project, monkeypatch):
    root, snapshot = project
    original = module.git_output

    def change_after_hash(directory, *args, data=None):
        result = original(directory, *args, data=data)
        if args[0] == "hash-object":
            (root / "Imervue/example.py").write_text(
                "def value():\n    return 99\n", encoding="utf-8",
            )
        return result

    monkeypatch.setattr(module, "git_output", change_after_hash)
    with pytest.raises(ValueError, match="source changed during inventory"):
        inventory(root, snapshot)


@pytest.mark.parametrize("alias", ["Imervue//example.py", "Imervue/./example.py"])
def test_path_aliases_cannot_bypass_duplicate_detection(project, alias):
    _, snapshot = project
    raw = json.loads(snapshot.read_text(encoding="utf-8"))
    raw["files"].append({"path": alias, "complexity": 1})
    snapshot.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="noncanonical snapshot path"):
        read_snapshot(snapshot, root=snapshot.parent.parent)


def test_python_code_in_cache_named_directory_is_still_in_scope(project):
    root, snapshot = project
    folder = root / "plugins/__pycache__"
    folder.mkdir()
    (folder / "hidden.py").write_text("def hidden():\n    return 1\n", encoding="utf-8")
    report = inventory(root, snapshot)
    assert report["groups"]["missing_analysis"] == ["plugins/__pycache__/hidden.py"]


def test_git_freshness_uses_the_same_bytes_as_the_report(project, monkeypatch):
    root, snapshot = project
    original = Path.read_bytes
    changed = b"def value(x):\n    if x:\n        return 43\n    return 42\n"

    def different_source(path):
        return changed if path == root / "Imervue/example.py" else original(path)

    monkeypatch.setattr(Path, "read_bytes", different_source)
    report = inventory(root, snapshot)
    assert report["status"] == "inconclusive"
    assert report["groups"]["changed_since_analysis"] == ["Imervue/example.py"]


def test_directory_links_are_rejected_before_descent(project, monkeypatch):
    root, snapshot = project
    alias = root / "plugins/alias"
    alias.mkdir()
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == alias or original(path))
    with pytest.raises(ValueError, match="source link is not allowed"):
        inventory(root, snapshot)


def _metadata(revision="a" * 40):
    return {"data": {"selectedBranch": {"name": "main", "lastCommit": revision},
                     "lastAnalysedCommit": {"sha": revision, "endedAnalysis": "complete"}}}


def _page(path="Imervue/example.py", cursor=None):
    pagination = {} if cursor is None else {"cursor": cursor}
    return {"data": [{"path": path, "complexity": 1}], "pagination": pagination}


def test_hosted_capture_uses_stable_sort_and_all_pages():
    responses = iter([_metadata(), _page(cursor="next"), _page("Imervue/second.py"),
                      _page("plugins/example.py"), _metadata()])
    urls = []

    def fetch(url):
        urls.append(url)
        return next(responses)

    captured = module.capture_snapshot("main", fetch)
    assert [row["path"] for row in captured["files"]] == [
        "Imervue/example.py", "Imervue/second.py", "plugins/example.py",
    ]
    queries = [parse_qs(urlsplit(url).query) for url in urls[1:-1]]
    assert all(query["sort"] == ["filename"] for query in queries)
    assert queries[1]["cursor"] == ["next"]
    assert len(captured["pages"]) == 3


def test_hosted_capture_rejects_analysis_revision_change():
    responses = iter([_metadata(), _page(), _page("plugins/example.py"), _metadata("b" * 40)])
    with pytest.raises(ValueError, match="revision changed during capture"):
        module.capture_snapshot("main", lambda _url: next(responses))


def test_hosted_capture_rejects_duplicate_rows_across_pages():
    responses = iter([_metadata(), _page(cursor="next"), _page(),
                      _page("plugins/example.py"), _metadata()])
    with pytest.raises(ValueError, match="duplicate snapshot path"):
        module.capture_snapshot("main", lambda _url: next(responses))


def test_hosted_capture_rejects_repeating_cursor():
    responses = iter([_metadata(), _page(cursor="repeat"), _page(cursor="repeat")])
    with pytest.raises(ValueError, match="repeated hosted pagination cursor"):
        module.capture_snapshot("main", lambda _url: next(responses))


def test_hosted_capture_cannot_certify_unanalyzed_branch_head():
    metadata = _metadata()
    metadata["data"]["selectedBranch"]["lastCommit"] = "b" * 40
    with pytest.raises(ValueError, match="head has not finished analysis"):
        module.capture_snapshot("main", lambda _url: metadata)


@pytest.mark.parametrize("page", [
    {"data": [{"path": None, "complexity": 1}], "pagination": {}},
    {"data": [], "pagination": []},
    {"data": None, "pagination": {}},
    {"data": [None], "pagination": {}},
    [],
])
def test_malformed_hosted_pages_produce_inconclusive_cli_reports(project, monkeypatch, page):
    root, snapshot = project
    original = snapshot.read_bytes()
    responses = iter([_metadata(), page])
    capture = module.capture_snapshot
    monkeypatch.setattr(module, "capture_snapshot", lambda branch: (
        capture(branch, lambda _url: next(responses))))
    assert main(["--root", str(root), "--snapshot", str(snapshot),
                 "--output", ".audit/report.json", "--refresh-from-branch", "main"]) == 2
    report = json.loads((root / ".audit/report.json").read_text(encoding="utf-8"))
    assert report["status"] == "inconclusive"
    assert "invalid hosted" in report["error"]
    assert snapshot.read_bytes() == original
