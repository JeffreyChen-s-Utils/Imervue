"""Paint workspace — MediBang-style painting tab.

The package is intentionally split so each sub-module has one
responsibility:

* :mod:`tool_state` — Qt-free model of the current tool, colours,
  brush settings, and history. Persisted via ``user_setting_dict``.
* :mod:`canvas` — the central drawing surface. Reuses
  :class:`Imervue.gpu_image_view.gpu_image_view.GPUImageView` for
  hardware-accelerated image display and adds overlay-paint hooks.
* :mod:`dock_panels` — QDockWidget subclasses for Layers, Colour,
  Brush, Navigator and History.
* :mod:`tool_bar` — left icon bar + top context-sensitive options strip.
* :mod:`paint_workspace` — top-level widget that assembles everything.
"""
