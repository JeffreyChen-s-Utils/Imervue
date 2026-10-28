"""Audio-file lip-sync motion creation and feedback."""
from __future__ import annotations
from pathlib import Path
from Imervue.gui.file_filters import translated_filter
from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.puppet.document import Parameter
from Imervue.puppet.motion_recorder import append_motion

class PuppetAudioMixin:
    def _lipsync_from_audio_file(self) -> None:  # pragma: no cover - Qt file dialog
        """Live > Lip-sync from Audio File…: pick a WAV and add a motion that mimes it."""
        from PySide6.QtWidgets import QFileDialog

        from Imervue.puppet.standard_params import PARAM_MOUTH_OPEN_Y
        doc = self._canvas.document()
        if doc is None:
            self._announce("puppet_lipsync_audio_no_doc", "Load a puppet first.")
            return
        mouth = next((p for p in doc.parameters if p.id == PARAM_MOUTH_OPEN_Y), None)
        if mouth is None:
            self._announce(
                "puppet_lipsync_audio_no_mouth",
                "This rig has no {param} parameter to drive.", param=PARAM_MOUTH_OPEN_Y,
            )
            return
        lang = language_wrapper.language_word_dict
        path, _ = QFileDialog.getOpenFileName(
            self, lang.get("puppet_lipsync_audio", "Lip-sync from Audio File…"), "",
            translated_filter("file_filter_wav", "WAV audio", ("wav",)),
        )
        if path:
            self._add_lipsync_motion(Path(path), mouth)

    def _add_lipsync_motion(self, path: Path, mouth: Parameter) -> None:
        """Add a motion opening *mouth* with *path*'s loudness, playing the file; report it."""
        import wave

        from Imervue.puppet.audio_lipsync import lipsync_motion
        wide = mouth.max if mouth.max > mouth.default else mouth.min
        try:
            motion = lipsync_motion(path, name=f"lipsync_{path.stem}", param_id=mouth.id,
                                    mouth_range=(mouth.default, wide))
        except (OSError, EOFError, ValueError, wave.Error) as exc:
            self._announce("puppet_lipsync_audio_failed", "Could not read {name}: {error}",
                           name=path.name, error=exc)
            return
        if motion is None:
            self._announce("puppet_lipsync_audio_silent", "{name} is silent — no motion added.",
                           name=path.name)
            return
        append_motion(self._canvas, motion)
        self._motion_dock.select_motion(motion.name)
        self._announce(
            "puppet_lipsync_audio_done",
            "Added lip-sync motion '{name}' ({duration:.1f}s); it plays with its sound.",
            name=motion.name, duration=motion.duration,
        )
