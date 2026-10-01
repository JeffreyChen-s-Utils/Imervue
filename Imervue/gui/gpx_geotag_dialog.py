"""Extra Tools > Library & Metadata > Geotag from GPX Track: GPS from a recorded track.

Pick the ``.gpx`` a phone or GPS logger recorded, say how far the camera's
clock runs from UTC, and every selected photo whose EXIF capture time falls on
the track gets its position (interpolated between track points, nothing across
a gap longer than the limit). The matching is
:mod:`Imervue.library.gpx_geotag`; the GPS write is
:func:`Imervue.image.gps_geotag.write_gps` (JPEG and WebP).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from Imervue.gpu_image_view.actions.select import selection_or_all
from Imervue.gui.file_filters import translated_filter
from Imervue.image.gps_geotag import write_gps
from Imervue.library.capture_time import exif_capture_time
from Imervue.library.gpx_geotag import TrackPoint, match_photos, parse_gpx
from Imervue.multi_language.language_wrapper import language_wrapper

if TYPE_CHECKING:
    from Imervue.Imervue_main_window import ImervueMainWindow

_SECONDS_PER_HOUR = 3600


def load_track(path: str | Path) -> list[TrackPoint]:
    """The time-stamped points of the GPX file at *path*.

    Raises ``OSError`` for an unreadable file and ``ValueError`` (which a
    non-UTF-8 file's ``UnicodeDecodeError`` is) for one that isn't GPX.
    """
    return parse_gpx(Path(path).read_text(encoding="utf-8"))


def write_matches(matches: list[tuple[str, tuple[float, float] | None]]) -> tuple[int, int]:
    """Write every matched position; returns ``(written, failed)`` (unmatched ones are skipped)."""
    written = failed = 0
    for path, coords in matches:
        if coords is None:
            continue
        if write_gps(path, *coords):
            written += 1
        else:
            failed += 1
    return written, failed


class GpxGeotagDialog(QDialog):
    """Match *paths* against a GPX track and write the positions that fall on it."""

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        lang = language_wrapper.language_word_dict
        self.setWindowTitle(lang.get("gpx_title", "Geotag from GPX Track"))
        self.setMinimumWidth(460)
        self._times = [(path, exif_capture_time(path)) for path in paths]
        self._track: list[TrackPoint] = []
        self._matches: list[tuple[str, tuple[float, float] | None]] = []
        layout = QVBoxLayout(self)
        layout.addLayout(self._build_form(lang))
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._write_btn = buttons.addButton(lang.get("gpx_write", "Write GPS"),
                                            QDialogButtonBox.ButtonRole.ApplyRole)
        self._write_btn.clicked.connect(self.write)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.rematch()

    def _build_form(self, lang: dict) -> QFormLayout:
        form = QFormLayout()
        row = QHBoxLayout()
        self._track_edit = QLineEdit()
        self._track_edit.setReadOnly(True)
        row.addWidget(self._track_edit, 1)
        browse = QPushButton(lang.get("gpx_browse", "Browse…"))
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        form.addRow(lang.get("gpx_track", "Track:"), row)
        self._tz = QDoubleSpinBox()
        self._tz.setRange(-14.0, 14.0)
        self._tz.setSingleStep(0.5)
        self._tz.setDecimals(2)
        self._tz.setToolTip(lang.get(
            "gpx_tz_tooltip", "How far the camera's clock ran ahead of UTC, e.g. 8 for UTC+8"))
        form.addRow(lang.get("gpx_tz", "Camera time zone (hours from UTC):"), self._tz)
        self._gap = QSpinBox()
        self._gap.setRange(10, 3600)
        self._gap.setValue(120)
        self._gap.setSuffix(" s")
        self._gap.setToolTip(lang.get(
            "gpx_gap_tooltip",
            "A photo further than this from the track, or between two points further apart, "
            "gets no position"))
        form.addRow(lang.get("gpx_gap", "Furthest from a track point:"), self._gap)
        self._interpolate = QCheckBox(lang.get("gpx_interpolate",
                                               "Interpolate between track points"))
        self._interpolate.setChecked(True)
        form.addRow("", self._interpolate)
        for signal in (self._tz.valueChanged, self._gap.valueChanged, self._interpolate.toggled):
            signal.connect(self.rematch)
        return form

    def _browse(self) -> None:  # pragma: no cover - Qt file dialog
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self, lang.get("gpx_title", "Geotag from GPX Track"), "",
            translated_filter("file_filter_gpx", "GPX track", ("gpx",)))
        if path:
            self.open_track(path)

    def open_track(self, path: str) -> bool:
        """Load the track at *path* and match the photos against it; False if it can't be read."""
        lang = language_wrapper.language_word_dict
        try:
            track = load_track(path)
        except (OSError, ValueError) as exc:
            self._track = []
            self.rematch()
            self._summary.setText(lang.get("gpx_bad_track", "Could not read the track: {error}")
                                  .format(error=exc))
            return False
        self._track_edit.setText(path)
        self._track = track
        self.rematch()
        return True

    def rematch(self, *_args) -> None:
        """Match every photo against the loaded track with the current settings."""
        lang = language_wrapper.language_word_dict
        self._matches = match_photos(
            self._times, self._track, max_gap_s=self._gap.value(),
            interpolate=self._interpolate.isChecked(),
            tz_offset_s=round(self._tz.value() * _SECONDS_PER_HOUR))
        matched = sum(1 for _, coords in self._matches if coords is not None)
        self._write_btn.setEnabled(matched > 0)
        if not self._track:
            self._summary.setText(lang.get("gpx_pick_track", "Pick a GPX track to match {total} "
                                           "photo(s) against.").format(total=len(self._times)))
            return
        self._summary.setText(lang.get(
            "gpx_summary",
            "{matched} of {total} photo(s) fall on the track ({points} points); "
            "{untimed} have no EXIF capture time.",
        ).format(matched=matched, total=len(self._times), points=len(self._track),
                 untimed=sum(1 for _, when in self._times if when is None)))

    def matches(self) -> list[tuple[str, tuple[float, float] | None]]:
        """``(path, (lat, lon) or None)`` for every photo, as last matched."""
        return list(self._matches)

    def write(self) -> tuple[int, int]:
        """Write the matched positions and report it; ``(written, failed)``."""
        written, failed = write_matches(self._matches)
        self._summary.setText(language_wrapper.language_word_dict.get(
            "gpx_done",
            "Wrote GPS to {written} photo(s); {failed} could not be written (only JPEG and "
            "WebP can be, and the file must be writable).",
        ).format(written=written, failed=failed))
        return written, failed


def open_gpx_geotag(ui: ImervueMainWindow) -> None:
    """Open the dialog on the selection, or on every image the viewer lists."""
    GpxGeotagDialog(selection_or_all(getattr(ui, "viewer", None)), ui).exec()
