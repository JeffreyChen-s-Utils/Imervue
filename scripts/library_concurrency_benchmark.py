"""Isolated 100k catalog: foreground latency with a held scanner transaction."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.performance_support import measure, summarize, write_json  # noqa: E402


def run(repeats: int) -> dict:
    from Imervue.library import image_index as index
    with tempfile.TemporaryDirectory(prefix="imervue-library-concurrency-") as folder:
        index.set_db_path(Path(folder) / "catalog.db")
        try:
            with index.write_batch():
                index.conn().executemany(
                    "INSERT INTO images(path,parent,name,ext,size,mtime,taken_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    [(f"photos/image-{i:06}.jpg", "photos", f"image-{i:06}.jpg",
                      "jpg", 128, 1700000000.0, None)
                     for i in range(100000)],
                )
            query = index.ImageQuery(name_contains="image-", limit=100)
            single = measure(lambda: index.search_images(query), repeats=repeats)
            durations, errors = [], []
            for _ in range(repeats):
                ready, release = threading.Event(), threading.Event()

                def write(ready=ready, release=release):
                    try:
                        with index.write_batch():
                            index.upsert_image("uncommitted.jpg")
                            ready.set()
                            release.wait(.250)
                            raise ValueError("intentional chunk rollback")
                    except ValueError:
                        pass
                    except Exception as exc:  # noqa: BLE001 - propagate worker errors to caller
                        errors.append(str(exc))
                        ready.set()

                writer = threading.Thread(target=write)
                writer.start()
                try:
                    if not ready.wait(10):
                        raise TimeoutError("writer did not start")
                    start = time.perf_counter()
                    result = index.search_images(query)
                    durations.append((time.perf_counter() - start) * 1000)
                    if len(result) != 100 or index.get_image("uncommitted.jpg") is not None:
                        raise RuntimeError("reader observed uncommitted rows")
                finally:
                    release.set()
                    writer.join(10)
                if writer.is_alive():
                    raise TimeoutError("writer did not finish")
            if errors:
                raise RuntimeError(errors)
            return {"rows": index.count_images(), "single_reader": single,
                    "held_writer_search": summarize(durations), "writer_hold_max_ms": 250,
                    "boundary": ("fresh file DB; 100k deterministic rows; "
                                 "rollback per sample; no user data")}
        finally:
            index.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=30)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    report = run(args.repeats)
    write_json(args.output, report)
    print(json.dumps(report, indent=2))

