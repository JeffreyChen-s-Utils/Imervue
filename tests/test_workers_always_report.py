"""A QThread worker's ``run()`` reports every failure, or its dialog waits forever.

A tool dialog disables its button and waits for the worker's ``done`` signal.
A ``try`` in ``run()`` that caught only ``(OSError, ValueError)`` let the rest
escape - ``DecompressionBombError`` (a picture over Pillow's pixel limit is no
``OSError``), ``MemoryError``, ``cv2.error``, an ``ImportError`` from an
optional backend - so the signal never fired and the button stayed dead. So
every top-level ``try`` in a ``QThread.run`` ends with a broad, logged handler
(as ``gui/_apply_save.EffectWorker`` does) or emits from its ``finally``.
Workers without a top-level ``try`` (per-item loops) are not checked here.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
_BROAD = {"Exception", "BaseException"}


def _is_qthread(cls: ast.ClassDef) -> bool:
    return any(ast.unparse(base).endswith("QThread") for base in cls.bases)


def _reports_everything(block: ast.Try) -> bool:
    for handler in block.handlers:
        if handler.type is None or ast.unparse(handler.type) in _BROAD:
            return True
    return any(".emit(" in ast.unparse(stmt) for stmt in block.finalbody)


def _narrow_worker_tries() -> list[str]:
    found = []
    for folder in ("Imervue", "plugins"):
        for path in sorted((_ROOT / folder).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and _is_qthread(n)):
                for run in (f for f in cls.body if isinstance(f, ast.FunctionDef) and f.name == "run"):
                    for block in (s for s in run.body if isinstance(s, ast.Try)):
                        if not _reports_everything(block):
                            where = path.relative_to(_ROOT).as_posix()
                            found.append(f"{where}:{block.lineno} {cls.name}.run")
    return found


def test_every_worker_try_ends_in_a_broad_handler():
    assert _narrow_worker_tries() == []


def test_a_tool_worker_reports_a_picture_over_the_pixel_limit(qapp, tmp_path, monkeypatch):
    from Imervue.gui import clahe_dialog

    def too_big(_path):
        raise Image.DecompressionBombError("too many pixels")

    monkeypatch.setattr(clahe_dialog, "load_rgba", too_big)
    results = []
    worker = clahe_dialog._ClaheWorker(str(tmp_path / "a.png"), 2.0, 8, str(tmp_path / "out.png"))  # noqa: SLF001
    worker.done.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()
    worker.deleteLater()
    assert results == [(False, "too many pixels")]


@pytest.mark.parametrize("error", [RuntimeError("tesseract crashed"), MemoryError()])
def test_the_ocr_worker_reports_an_unexpected_error(qapp, monkeypatch, caplog, error):
    from Imervue.gui import ocr_dialog

    def fail(_path):
        raise error

    monkeypatch.setattr(ocr_dialog, "extract_text", fail)
    results = []
    worker = ocr_dialog._OcrWorker("a.png")  # noqa: SLF001
    worker.done.connect(lambda ok, msg: results.append((ok, msg)))
    with caplog.at_level("ERROR", logger="Imervue"):
        worker.run()
    worker.deleteLater()
    assert results == [(False, str(error))]
    assert any(r.exc_info for r in caplog.records)
