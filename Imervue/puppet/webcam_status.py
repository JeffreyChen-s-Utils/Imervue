"""Device lifecycle snapshots shared by capture workers and their controls."""

from dataclasses import dataclass
from enum import Enum


class WebcamPhase(str, Enum):
    """Observed capture lifecycle, with errors classified only from known evidence."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    MISSING_DEPENDENCY = "missing_dependency"
    DEVICE_UNAVAILABLE = "device_unavailable"
    PERMISSION_DENIED = "permission_denied"
    FAILED = "failed"


@dataclass(frozen=True)
class WebcamStatus:
    """Small immutable status; diagnostic detail is separate from translated guidance."""

    phase: WebcamPhase = WebcamPhase.STOPPED
    device: int = 0
    detail: str = ""

    @property
    def active(self) -> bool:
        """Whether capture has been requested and has not failed or begun stopping."""
        return self.phase in {WebcamPhase.STARTING, WebcamPhase.RUNNING}


STATUS_TEXT = {
    WebcamPhase.STOPPED: ("webcam_stopped", "Camera stopped"),
    WebcamPhase.STARTING: ("webcam_starting", "Starting camera…"),
    WebcamPhase.RUNNING: ("webcam_running", "Camera running"),
    WebcamPhase.STOPPING: ("webcam_stopping", "Stopping camera… Please wait before retrying."),
    WebcamPhase.MISSING_DEPENDENCY: (
        "webcam_missing_dependency", "Tracking packages are missing. Install them to continue.",
    ),
    WebcamPhase.DEVICE_UNAVAILABLE: (
        "webcam_device_unavailable",
        "Cannot open this camera. Choose another device or close other camera apps, then retry.",
    ),
    WebcamPhase.PERMISSION_DENIED: (
        "webcam_permission_denied",
        "Camera access was denied. Allow access in system settings, then retry.",
    ),
    WebcamPhase.FAILED: (
        "webcam_failed", "Camera tracking failed. Review diagnostics, then retry.",
    ),
}


def status_text(status: WebcamStatus, language: dict) -> str:
    """Translate actionable guidance without guessing a cause from driver text."""
    key, fallback = STATUS_TEXT[status.phase]
    return language.get(key, fallback)
