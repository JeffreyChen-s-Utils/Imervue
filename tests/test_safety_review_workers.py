"""The safety_review batch worker always reports, even when its detector won't load."""
from __future__ import annotations


def test_batch_worker_reports_a_detector_that_fails_to_load(qapp, monkeypatch, caplog):
    """Loading NudeNet raised outside any try: result_ready never came and the
    Scan All dialog waited forever."""
    from safety_review import _workers

    def broken(_mode):
        raise RuntimeError("onnxruntime is missing")

    monkeypatch.setattr(_workers, "_resolve_detector", broken)
    worker = _workers._BatchWorker(["a.png", "b.png", "c.png"], None, 16, 0, False)  # noqa: SLF001
    results: list = []
    worker.result_ready.connect(lambda *args: results.append(args))
    with caplog.at_level("ERROR", logger="Imervue"):
        worker.run()
    worker.deleteLater()
    assert results == [(0, 3, 0)]
    assert any(r.exc_info for r in caplog.records)
