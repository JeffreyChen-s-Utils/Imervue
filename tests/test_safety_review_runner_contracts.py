"""Contracts of the frozen-build runner's command line and stdout protocol.

``_runner.py`` is the child process the subprocess workers start. These pin
what it reads from argv (positions, defaults, case rules), what it prints for
each outcome, its exit codes, and the batch bookkeeping (destinations, shape
fallback, failed-folder copies, failure log). The detectors and the per-image
censor are replaced, so no ML runtime is loaded.
"""
from __future__ import annotations

import json
import sys

import pytest

from safety_review import _runner
from safety_review._constants import SHAPE_ELLIPSE, SHAPE_PRECISE, SHAPE_RECT


@pytest.fixture
def fake_ml(monkeypatch):
    """Stub detector loading and the per-image censor; record each call."""
    rec = {"modes": [], "calls": [], "fail": set(), "count": 0}

    def _load(det_mode):
        rec["modes"].append(det_mode)
        return "det", "anime"

    def _process(detector, src, dst, **kw):
        rec["calls"].append((detector, src, dst, kw))
        if src in rec["fail"]:
            raise ValueError(f"bad {src}")
        return rec["count"]

    monkeypatch.setattr(_runner, "_load_detectors", _load)
    monkeypatch.setattr(_runner, "_process_one", _process)
    return rec


def _lines(capsys):
    return capsys.readouterr().out.splitlines()


# ---------------------------------------------------------------------------
# Public names other modules and tests read from ``_runner``
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "_parse_categories", "_batch_destination", "_failed_dest", "_copy_failed",
    "_bootstrap_site_packages", "_detect_boxes_real", "_detect_boxes_anime",
    "_process_one", "_load_anime_model", "_load_detectors",
    "_process_one_with_fallback", "_write_failed_log", "_run_single",
    "_run_batch", "main", "_ANIME_MAKE_LOVE_CLASS", "_MAKE_LOVE_CENTER_FRAC",
])
def test_runner_module_still_exposes(name):
    assert hasattr(_runner, name)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("text", "expected"), [
    ("", None),
    (None, None),
    ("a", frozenset({"a"})),
    (" a, ,b ,", frozenset({"a", "b"})),
    (",", frozenset()),
])
def test_parse_categories(text, expected):
    assert _runner._parse_categories(text) == expected


def test_bootstrap_site_packages_inserts_once(monkeypatch):
    monkeypatch.setattr(sys, "path", ["x"])
    _runner._bootstrap_site_packages("SP")
    _runner._bootstrap_site_packages("SP")
    _runner._bootstrap_site_packages("")
    assert sys.path == ["SP", "x"]


def test_write_failed_log_needs_failures_and_a_folder(tmp_path):
    _runner._write_failed_log(str(tmp_path), [])
    _runner._write_failed_log("", [("a.png", "x")])
    assert list(tmp_path.iterdir()) == []
    _runner._write_failed_log(str(tmp_path), [("a.png", "x"), ("b.png", "y: z")])
    assert (tmp_path / "censor_failed.log").read_text(encoding="utf-8") == (
        "a.png: x\nb.png: y: z\n")


def test_copy_failed_swallows_a_missing_source(tmp_path):
    _runner._copy_failed(str(tmp_path / "gone.png"), str(tmp_path / "f"), "")
    assert not (tmp_path / "f" / "gone.png").exists()


def test_failed_dest_outside_the_scan_root_is_flat(tmp_path):
    src = tmp_path / "elsewhere" / "a.png"
    dst = _runner._failed_dest(str(src), str(tmp_path / "f"), str(tmp_path / "scan"))
    assert dst == str(tmp_path / "f" / "a.png")


def test_process_one_with_fallback_order():
    tried = []

    def _run(shape):
        tried.append(shape)
        raise RuntimeError(shape)

    with pytest.raises(RuntimeError, match=SHAPE_ELLIPSE):
        _runner._process_one_with_fallback(_run, SHAPE_PRECISE, retries=2)
    assert tried == [SHAPE_PRECISE] * 3 + [SHAPE_ELLIPSE]
    tried.clear()
    with pytest.raises(RuntimeError):
        _runner._process_one_with_fallback(_run, SHAPE_ELLIPSE, retries=-1)
    assert tried == [SHAPE_ELLIPSE]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def test_main_without_enough_arguments(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["_runner.py", "SP"])
    with pytest.raises(SystemExit) as exc:
        _runner.main()
    assert exc.value.code == 1
    assert _lines(capsys) == ["ERROR:Not enough arguments"]


@pytest.mark.parametrize("mode", ["single", "batch"])
def test_main_dispatches_and_bootstraps(monkeypatch, mode):
    seen = []
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "argv", ["_runner.py", "SITE", mode, "x"])
    monkeypatch.setattr(_runner, f"_run_{mode}", lambda args: seen.append(args))
    _runner.main()
    assert seen == [["SITE", mode, "x"]]
    assert sys.path[0] == "SITE"


# ---------------------------------------------------------------------------
# single mode
# ---------------------------------------------------------------------------

def test_single_requires_the_four_positionals(capsys, fake_ml):
    with pytest.raises(SystemExit) as exc:
        _runner._run_single(["SP", "single", "in", "out", "8"])
    assert exc.value.code == 1
    assert _lines(capsys) == [
        "ERROR:single mode requires: input output block_size padding"]
    assert fake_ml["modes"] == []


def test_single_defaults(capsys, fake_ml):
    _runner._run_single(["SP", "single", "in.png", "out.png", "8", "2"])
    assert fake_ml["modes"] == ["real"]
    assert fake_ml["calls"] == [("det", "in.png", "out.png", {
        "block_size": 8, "padding": 2, "confidence": 0.25, "expand_pct": 0,
        "det_mode": "real", "anime_model": "anime", "style": "mosaic",
        "categories": None, "shape": SHAPE_RECT})]
    assert _lines(capsys) == ["PROGRESS:Detecting...",
                              "PROGRESS:No genitalia detected", "OK:out.png"]


def test_single_reads_every_option(capsys, fake_ml):
    fake_ml["count"] = 3
    _runner._run_single(["SP", "single", "in.png", "out.png", "8", "2", "anime",
                         "0.4", "6", "blur", "a,b", "precise", "extra"])
    assert fake_ml["modes"] == ["anime"]
    assert fake_ml["calls"][0][3] == {
        "block_size": 8, "padding": 2, "confidence": 0.4, "expand_pct": 6,
        "det_mode": "anime", "anime_model": "anime", "style": "blur",
        "categories": frozenset({"a", "b"}), "shape": "precise"}
    assert _lines(capsys)[1:] == ["PROGRESS:Censored 3 region(s)", "OK:out.png"]


def test_single_reports_a_processing_error(capsys, fake_ml):
    fake_ml["fail"].add("in.png")
    with pytest.raises(SystemExit) as exc:
        _runner._run_single(["SP", "single", "in.png", "out.png", "8", "2"])
    assert exc.value.code == 1
    assert _lines(capsys) == ["PROGRESS:Detecting...", "ERROR:bad in.png"]


def test_single_bad_number_raises_before_loading(capsys, fake_ml):
    with pytest.raises(ValueError):
        _runner._run_single(["SP", "single", "in.png", "out.png", "eight", "2"])
    assert fake_ml["modes"] == []
    assert _lines(capsys) == []


# ---------------------------------------------------------------------------
# batch mode
# ---------------------------------------------------------------------------

def _path_list(tmp_path, paths):
    listing = tmp_path / "paths.json"
    listing.write_text(json.dumps(paths), encoding="utf-8")
    return str(listing)


def test_batch_requires_the_five_positionals(capsys, fake_ml):
    with pytest.raises(SystemExit) as exc:
        _runner._run_batch(["SP", "batch", "p.json", "out", "8", "2"])
    assert exc.value.code == 1
    assert _lines(capsys) == [
        "ERROR:batch mode requires: json_paths output_dir block_size padding overwrite"]


def test_batch_defaults(tmp_path, capsys, fake_ml):
    src = str(tmp_path / "a.png")
    out = tmp_path / "out"
    _runner._run_batch(["SP", "batch", _path_list(tmp_path, [src]), str(out),
                        "8", "2", "no"])
    assert fake_ml["modes"] == ["real"]
    assert fake_ml["calls"] == [("det", src, str(out / "a_censored.png"), {
        "block_size": 8, "padding": 2, "confidence": 0.25, "expand_pct": 0,
        "det_mode": "real", "anime_model": "anime", "style": "mosaic",
        "categories": None, "only_censored": False, "shape": SHAPE_RECT,
        "merge_regions": True})]
    assert _lines(capsys) == ["BATCH_PROGRESS:0:1:a.png", "BATCH_OK:1:0"]


def test_batch_reads_every_option(tmp_path, capsys, fake_ml):
    root = tmp_path / "scan"
    src = str(root / "sub" / "a.png")
    _runner._run_batch([
        "SP", "batch", _path_list(tmp_path, [src]), str(tmp_path / "out"), "8",
        "2", "TRUE", "auto", "0.3", "4", "black", "x", str(root), "True",
        "ellipse", str(tmp_path / "f"), str(root), "FALSE"])
    assert fake_ml["modes"] == ["auto"]
    assert fake_ml["calls"] == [("det", src, src, {
        "block_size": 8, "padding": 2, "confidence": 0.3, "expand_pct": 4,
        "det_mode": "auto", "anime_model": "anime", "style": "black",
        "categories": frozenset({"x"}), "only_censored": True,
        "shape": SHAPE_ELLIPSE, "merge_regions": False})]
    assert _lines(capsys)[-1] == "BATCH_OK:1:0"


@pytest.mark.parametrize(("flag", "expected"), [("false", False), ("no", True),
                                                ("", True), ("True", True)])
def test_batch_merge_regions_is_on_unless_false(tmp_path, fake_ml, flag, expected):
    args = ["SP", "batch", _path_list(tmp_path, ["a.png"]), str(tmp_path), "8",
            "2", "true", "real", "0.25", "0", "mosaic", "", "", "", "rect", "",
            "", flag]
    _runner._run_batch(args)
    assert fake_ml["calls"][0][3]["merge_regions"] is expected
    assert fake_ml["calls"][0][3]["only_censored"] is False


def test_batch_mirrors_into_the_source_root(tmp_path, fake_ml):
    root = tmp_path / "scan"
    src = str(root / "sub" / "a.png")
    out = tmp_path / "out"
    _runner._run_batch(["SP", "batch", _path_list(tmp_path, [src]), str(out),
                        "8", "2", "false", "real", "0.25", "0", "mosaic", "",
                        str(root)])
    assert fake_ml["calls"][0][2] == str(out / "sub" / "a_censored.png")


def test_batch_failure_falls_back_records_and_continues(tmp_path, capsys, fake_ml):
    root = tmp_path / "scan"
    (root / "sub").mkdir(parents=True)
    bad = root / "sub" / "bad.png"
    bad.write_bytes(b"orig")
    good = str(root / "good.png")
    failed = tmp_path / "failed"
    failed.mkdir()
    fake_ml["fail"].add(str(bad))
    fake_ml["count"] = 2
    _runner._run_batch([
        "SP", "batch", _path_list(tmp_path, [str(bad), good]), str(tmp_path / "out"),
        "8", "2", "false", "real", "0.25", "0", "mosaic", "", "", "false",
        "precise", str(failed), str(root)])

    tries = [c for c in fake_ml["calls"] if c[1] == str(bad)]
    assert [c[3]["shape"] for c in tries] == ["precise", "precise", SHAPE_ELLIPSE]
    assert len({c[2] for c in tries}) == 1
    assert _lines(capsys) == [
        "BATCH_PROGRESS:0:2:bad.png", f"PROGRESS:Error on bad.png: bad {bad}",
        "BATCH_PROGRESS:1:2:good.png", "BATCH_OK:1:1"]
    assert (failed / "sub" / "bad.png").read_bytes() == b"orig"
    assert (failed / "censor_failed.log").read_text(encoding="utf-8") == (
        f"bad.png: bad {bad}\n")


def test_batch_failure_without_a_failed_folder_only_counts(tmp_path, capsys, fake_ml):
    fake_ml["fail"].add("a.png")
    _runner._run_batch(["SP", "batch", _path_list(tmp_path, ["a.png"]),
                        str(tmp_path), "8", "2", "true"])
    assert _lines(capsys)[-1] == "BATCH_OK:0:1"
    assert not (tmp_path / "censor_failed.log").exists()


def test_batch_bad_destination_counts_as_a_failure(tmp_path, capsys, fake_ml, monkeypatch):
    def _boom(*_a):
        raise OSError("disk")

    monkeypatch.setattr(_runner, "_batch_destination", _boom)
    _runner._run_batch(["SP", "batch", _path_list(tmp_path, ["a.png"]),
                        str(tmp_path), "8", "2", "false"])
    assert fake_ml["calls"] == []
    assert _lines(capsys)[-2:] == ["PROGRESS:Error on a.png: disk", "BATCH_OK:0:1"]


def test_moved_names_are_the_owning_modules_objects():
    from safety_review import _runner_args, _runner_batch
    for name in ("_parse_categories", "_bootstrap_site_packages"):
        assert getattr(_runner, name) is getattr(_runner_args, name)
    for name in ("_batch_destination", "_failed_dest", "_copy_failed",
                 "_process_one_with_fallback", "_write_failed_log"):
        assert getattr(_runner, name) is getattr(_runner_batch, name)
