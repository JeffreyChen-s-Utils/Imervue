"""Optional-dependency manifest for the built-in puppet tab.

The tab's core (rendering, parameter system, motion playback,
PSD/Cubism import) runs on the default ``requirements.txt`` set. A
handful of input modalities pull in heavier third-party packages
that we keep optional so users who never touch them aren't forced
to install gigabytes of ML wheels:

* **Webcam tracking** — ``cv2`` (opencv-python) + ``mediapipe`` for
  the face-mesh + iris landmark stream.
* **Microphone lip-sync** — ``sounddevice`` for the low-latency
  input stream the viseme mapper consumes.

The lists are kept in :data:`FEATURE_PACKAGES` so the workspace can
hand them straight to
:func:`Imervue.plugin.pip_installer.ensure_dependencies` (which takes
``[(import_name, pip_name), ...]`` tuples) and tests can introspect
them without spinning Qt.
"""
from __future__ import annotations

import importlib.util

# (import-name, pip-name) — the importer probes ``import_name`` and
# falls back to ``pip install pip_name`` when the module isn't
# importable. Keeping both fields explicit because Python's import
# name doesn't always match the PyPI name (``cv2`` <-> ``opencv-python``).
WEBCAM_PACKAGES: list[tuple[str, str]] = [
    ("cv2", "opencv-python"),
    ("mediapipe", "mediapipe"),
]

LIPSYNC_PACKAGES: list[tuple[str, str]] = [
    ("sounddevice", "sounddevice"),
]

VIRTUAL_CAMERA_PACKAGES: list[tuple[str, str]] = [
    ("pyvirtualcam", "pyvirtualcam"),
]

NDI_PACKAGES: list[tuple[str, str]] = [
    ("NDIlib", "ndi-python"),
]

FEATURE_PACKAGES: dict[str, list[tuple[str, str]]] = {
    "webcam": WEBCAM_PACKAGES,
    "lipsync": LIPSYNC_PACKAGES,
    "virtual_camera": VIRTUAL_CAMERA_PACKAGES,
    "ndi": NDI_PACKAGES,
}


def missing_packages(
    packages: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return the subset of ``packages`` whose ``import_name`` isn't
    currently importable. Uses :func:`importlib.util.find_spec` so the
    probe doesn't actually execute the package — good for
    ``mediapipe``, which takes a couple of seconds to fully import."""
    return [pkg for pkg in packages if importlib.util.find_spec(pkg[0]) is None]


def all_optional_packages() -> list[tuple[str, str]]:
    """Union of every optional package across :data:`FEATURE_PACKAGES`,
    de-duplicated by ``import_name``. Powers the "install everything"
    toolbar action."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for packages in FEATURE_PACKAGES.values():
        for import_name, pip_name in packages:
            if import_name in seen:
                continue
            seen.add(import_name)
            out.append((import_name, pip_name))
    return out
