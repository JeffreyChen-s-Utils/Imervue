"""
Spanish Language Plugin for Imervue
====================================

Adds Spanish (Español) language support to Imervue.

This is also a reference for plugin developers who want to create
their own language plugins. To create a new language plugin:

1. Copy this folder and rename it (e.g. ``french_language``).
2. Replace all Spanish strings with your target language.
3. Update ``__init__.py`` to point to your new class.
4. Place the folder in the ``plugins/`` directory and restart Imervue.
"""

from __future__ import annotations

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

spanish_word_dict = {
    "main_window_current_filename_format": "Nombre de archivo actual: {name}",
    # File menu
    "main_window_open_image": "Abrir archivo",
    "main_window_current_filename": "Nombre de archivo actual:",
    "main_window_current_file": "Archivo",
    "main_window_open_folder": "Abrir carpeta",
    "main_window_exit": "Salir",
    "main_window_tile_size": "Tamaño de miniatura",
    "main_window_select_folder": "Seleccionar carpeta",
    "main_window_current_folder_format": "Carpeta actual: {path}",
    "main_window_remove_undo_stack": "Eliminar archivos temporales de deshacer",
    # Language Menubar
    "menu_bar_language": "Idioma",
    "language_menu_bar_please_restart_messagebox": "Por favor, reinicie la aplicación",
    "language_menu_bar_english": "Inglés",
    "language_menu_bar_traditional_chinese": "Chino tradicional",
    "language_menu_bar_chinese": "Chino simplificado",
    "language_menu_bar_koren": "Coreano",
    "language_menu_bar_japanese": "Japonés",
    # Tip menu
    "main_window_tip_menu": "Instrucciones",
    "main_window_mouse_tip_menu": "Control del ratón",
    "main_window_keyboard_tip_menu": "Control del teclado",
    "mouse_control_middle_tip": "Puede desplazarse usando el botón central del ratón",
    "mouse_control_left_tip": "Haga clic en una imagen con el botón izquierdo para entrar en el modo Deep Zoom",
    "mouse_control_multi_select_tip": "Mantenga presionado el botón izquierdo del ratón para seleccionar múltiples imágenes en el modo de miniaturas",
    "keyboard_control_esc_tip": "Presione ESC para salir del modo Deep Zoom",
    "keyboard_control_tile_arrow_up_tip": "En el modo de miniaturas, use la tecla de flecha arriba para moverse hacia arriba",
    "keyboard_control_tile_arrow_down_tip": "En el modo de miniaturas, use la tecla de flecha abajo para moverse hacia abajo",
    "keyboard_control_tile_arrow_left_tip": "En el modo de miniaturas, use la tecla de flecha izquierda para moverse a la izquierda",
    "keyboard_control_tile_arrow_right_tip": "En el modo de miniaturas, use la tecla de flecha derecha para moverse a la derecha",
    "keyboard_control_delete_tip": "Puede usar la tecla Suprimir para eliminar imágenes tanto en el modo de miniaturas como en Deep Zoom",
    "keyboard_r_tip": "Presione la tecla R del teclado para restablecer las coordenadas",
    # Right click menu
    "right_click_menu_go_to_parent_folder": "Ir a la carpeta principal",
    "right_click_menu_next_image": "Imagen siguiente",
    "right_click_menu_previous_image": "Imagen anterior",
    "right_click_menu_delete_current": "Eliminar imagen actual",
    "right_click_menu_delete_selected": "Eliminar imágenes seleccionadas",
    "right_click_menu_image_info": "Información de la imagen",
    # Image info
    "image_info_filename": "Nombre de archivo: {info}\n",
    "image_info_fullpath": "Ruta completa: {full_path}\n",
    "image_info_image_size": "Tamaño: {width} x {height}\n",
    "image_info_file_size": "Tamaño de archivo: {file_size_mb} MB\n",
    "image_info_file_created_time": "Fecha de creación: {created_time}\n",
    "image_info_file_modified_time": "Fecha de modificación: {modified_time}\n",
    "image_info_messagebox_title": "Información de la imagen",
    # Image info exif
    "image_info_exif_datatime_original": "Fecha de captura: {DateTimeOriginal}\n",
    "image_info_exif_camera_model": "Cámara: {Make} {Model}\n",
    "image_info_exif_camera_lens_model": "Lente: {LensModel}\n",
    "image_info_exif_camera_focal_length": "Distancia focal: {FocalLength}\n",
    "image_info_exif_camera_fnumber": "Apertura: {FNumber}\n",
    "image_info_exif_exposure_time": "Obturador: {ExposureTime}\n",
    "image_info_exif_iso": "ISO: {ISOSpeedRatings}",
    # Recent menu
    "recent_menu_title": "Menú de abiertos recientes",
    # Plugin
    "plugin_menu_title": "Complementos",
    "plugin_menu_loaded": "Complementos cargados",
    "plugin_menu_no_plugins": "No se han cargado complementos",
    "plugin_menu_reload": "Recargar complementos",
    "plugin_menu_open_folder": "Abrir carpeta de complementos",
    "plugin_info_name": "Nombre: {name}",
    "plugin_info_version": "Versión: {version}",
    "plugin_info_author": "Autor: {author}",
    "plugin_info_description": "Descripción: {description}",
}


class SpanishLanguagePlugin(ImervuePlugin):
    """Adds Spanish (Español) language support to Imervue."""

    plugin_name = "Spanish Language"
    plugin_version = "1.0.0"
    plugin_description = "Adds Spanish (Español) language support to Imervue."
    plugin_author = "Imervue Team"

    def on_plugin_loaded(self) -> None:
        language_wrapper.register_language(
            language_code="Spanish",
            display_name="Español",
            word_dict=spanish_word_dict,
        )
