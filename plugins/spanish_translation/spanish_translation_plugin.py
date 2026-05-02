"""Spanish (Español) translation plugin.

Registers Spanish as a runtime-installable language. The plugin loads
its full dictionary from ``spanish.py`` and registers it via
``language_wrapper.register_language``. Once registered, the language
appears in the Language menu just like the five built-in choices.

Plugin-vs-main note: this plugin owns the entire Spanish translation
surface, including translations for keys that *other* plugins use
(AI Denoise, Portrait Mode, etc.). That preload is necessary because
``language_wrapper.merge_translations`` only writes to language dicts
that already exist — when the AI Denoise plugin loads later and tries
to merge its translations, it provides only the five built-in
languages, never Spanish. By pre-filling ``spanish_word_dict`` with
every plugin key we know about, the Spanish UI stays complete even
though no other plugin knows Spanish exists.
"""
from __future__ import annotations

import logging

from Imervue.multi_language.language_wrapper import language_wrapper
from Imervue.plugin.plugin_base import ImervuePlugin

from spanish_translation.spanish import spanish_word_dict

logger = logging.getLogger("Imervue.plugin.spanish_translation")


class SpanishTranslationPlugin(ImervuePlugin):
    plugin_name = "Spanish Translation"
    plugin_version = "1.0.0"
    plugin_description = "Adds Spanish (Español) to the Language menu."
    plugin_author = "Imervue"

    def on_plugin_loaded(self) -> None:
        language_wrapper.register_language(
            "Spanish", "Español", spanish_word_dict,
        )
        logger.info(
            "Spanish translation registered (%d entries)",
            len(spanish_word_dict),
        )
