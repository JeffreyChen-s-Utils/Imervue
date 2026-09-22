"""Version constraints applied to every plugin dependency install.

All OpenCV distributions (opencv-python, -headless, -contrib, -contrib-headless)
install into one shared ``cv2`` directory. Plugins pull different ones —
nudenet wants the headless build, ultralytics the plain one, mediapipe contrib —
so without a constraint pip resolves the newest release for whichever is
missing, and an OpenCV 5 wheel overwrites the files of the 4.x ones already
there. OpenCV 5 also dropped the Haar cascades the main program's face
detection uses. Keeping every distribution below 5 keeps ``cv2`` one version.

A constraint only limits the version of a package that gets installed anyway;
it never installs anything by itself.
"""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

OPENCV_DISTRIBUTIONS = (
    "opencv-python",
    "opencv-python-headless",
    "opencv-contrib-python",
    "opencv-contrib-python-headless",
)
PIP_CONSTRAINTS = tuple(f"{name}<5" for name in OPENCV_DISTRIBUTIONS)
CONSTRAINTS_FILENAME = "imervue-constraints.txt"


def write_constraints_file(directory: Path) -> Path:
    """Write :data:`PIP_CONSTRAINTS` into *directory* and return the file path."""
    path = Path(directory) / CONSTRAINTS_FILENAME
    path.write_text("\n".join(PIP_CONSTRAINTS) + "\n", encoding="utf-8")
    return path


def install_command(
    python: str,
    package: str,
    constraints_file: Path,
    extra_args: Sequence[str] = (),
) -> list[str]:
    """Build the ``pip install`` argv for one *package* under *constraints_file*."""
    return [
        python, "-m", "pip", "install",
        "--no-input",
        "--disable-pip-version-check",
        "-c", str(constraints_file),
        package,
        *extra_args,
    ]
