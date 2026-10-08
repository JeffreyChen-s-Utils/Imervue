"""Cross-entry output policy: real encoders, conflicts, privacy and retained results."""
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest
from PIL import Image, ImageCms

from Imervue import cli
from Imervue.cli_output import plan_targets, process_output, write_report
from Imervue.image.export_metadata import export_save_options
from Imervue.system.job_state import JobItem


def photo(path, colour="red"):
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    exif[271] = "Camera"
    exif[274] = 6
    exif.get_ifd(34853)[1] = "N"
    exif[34853] = 0
    Image.new("RGB", (8, 4), colour).save(path, exif=exif)
    return path


@pytest.mark.parametrize("jobs", [1, 4])
def test_same_names_partial_failure_report_and_originals(tmp_path, jobs):
    a, b = photo(tmp_path / "a" / "same.png"), photo(tmp_path / "b" / "same.png", "blue")
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"broken")
    report, out = tmp_path / "result.json", tmp_path / "out"
    assert cli.main(["convert", str(a), str(b), str(bad), "--format", "PNG",
                     "--out", str(out), "-j", str(jobs), "--result-report", str(report)]) == 1
    rows = json.loads(report.read_text(encoding="utf-8"))["items"]
    successes = [row for row in rows if row["status"] == "succeeded"]
    assert len(successes) == 2
    assert {Path(row["output"]).name for row in successes} == {"same.png", "same_1.png"}
    assert all(row["output_uri"].startswith("file:///") for row in successes)
    assert rows[-1]["status"] == "failed" and rows[-1]["error"]
    assert Image.open(a).getpixel((0, 0)) == (255, 0, 0)
    assert Image.open(b).getpixel((0, 0)) == (0, 0, 255)
    assert len(list(out.iterdir())) == 2


@pytest.mark.parametrize("policy", ["all", "no_location", "none"])
def test_cli_metadata_matches_gui_options(tmp_path, policy):
    src = photo(tmp_path / "src.png")
    out = tmp_path / "out"
    assert cli.main(["convert", str(src), "--format", "PNG", "--out", str(out),
                     "--export-metadata", policy]) == 0
    with Image.open(out / src.name) as image:
        options = export_save_options(src, policy)
        assert image.info.get("icc_profile") == options.get("icc_profile")
        if policy == "none":
            assert not image.getexif()
        else:
            assert image.getexif()[271] == "Camera" and 274 not in image.getexif()
            assert bool(image.getexif().get_ifd(34853)) == (policy == "all")
            import io
            profile = ImageCms.ImageCmsProfile(io.BytesIO(image.info["icc_profile"]))
            assert "srgb" in ImageCms.getProfileDescription(profile).lower()


def test_cancel_during_encode_keeps_original_and_no_stage(tmp_path):
    src = photo(tmp_path / "src.png")
    before = src.read_bytes()
    cancel = Event()
    args = SimpleNamespace(dry_run=False, overwrite=True, export_metadata=None)
    def encode(_src, stage, _args):
        stage.write_bytes(b"encoded")
        cancel.set()
    item = process_output(src, src, encode, args, cancel.is_set)
    assert item.status == "cancelled" and not item.output
    assert src.read_bytes() == before and list(tmp_path.iterdir()) == [src]


def test_ctrl_c_returns_partial_report_without_new_outputs(tmp_path, monkeypatch):
    a, b = photo(tmp_path / "a.png"), photo(tmp_path / "b.png")
    original = cli.op_resize
    def interrupt(src, stage, args):
        if src == b:
            stage.write_bytes(b"partial")
            raise KeyboardInterrupt
        original(src, stage, args)
    monkeypatch.setattr(cli, "op_resize", interrupt)
    monkeypatch.setitem(cli._WRITE_SPEC, "resize", (interrupt, "_resize", lambda _a: None))
    report = tmp_path / "report.json"
    assert cli.main(["resize", str(a), str(b), "--max", "4", "--out", str(tmp_path / "out"),
                     "--result-report", str(report)]) == 130
    rows = json.loads(report.read_text(encoding="utf-8"))["items"]
    assert [row["status"] for row in rows] == ["succeeded", "cancelled"]
    assert [p.name for p in (tmp_path / "out").iterdir()] == ["a.png"]


def test_report_cannot_replace_source_and_atomic_report_round_trip(tmp_path):
    src = photo(tmp_path / "src.png")
    before = src.read_bytes()
    assert cli.main(["resize", str(src), "--max", "4", "--result-report", str(src)]) == 2
    assert src.read_bytes() == before
    report = tmp_path / "report.json"
    write_report(report, [JobItem(str(src), "failed", error="disk full")])
    row = json.loads(report.read_text(encoding="utf-8"))["items"][0]
    assert row["error"] == "disk full" and not row["output_uri"]
    assert JobItem(**{key: value for key, value in row.items() if key != "output_uri"}) == (
        JobItem(str(src), "failed", error="disk full"))
    assert plan_targets([]) == []
    assert plan_targets([src, src])[1] == src.with_name("src_1.png")
