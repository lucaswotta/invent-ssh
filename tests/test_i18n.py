"""Locale preference tests: explicit app preference first, OS locale on first run."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import i18n


class LanguageResolutionTests(unittest.TestCase):
    def test_language_environment_prefers_first_supported_locale(self):
        with (
            patch.dict(os.environ, {
                "LANGUAGE": "pt_BR:en_US",
                "LC_ALL": "en_US.UTF-8",
                "LC_MESSAGES": "en_US.UTF-8",
                "LANG": "en_US.UTF-8",
            }, clear=True),
            patch("i18n.locale.getlocale", return_value=(None, None)),
        ):
            self.assertEqual(i18n._system_language(), "pt-br")

    def test_os_locale_is_used_when_environment_has_no_supported_language(self):
        with (
            patch.dict(os.environ, {"LANG": "C.UTF-8"}, clear=True),
            patch("i18n.locale.getlocale", return_value=("English_United States", "1252")),
        ):
            self.assertEqual(i18n._system_language(), "en")

    def test_pt_br_locale_inherits_portuguese(self):
        with (
            patch.dict(os.environ, {"LANG": "pt_BR.UTF-8"}, clear=True),
            patch("i18n.locale.getlocale", return_value=(None, None)),
        ):
            self.assertEqual(i18n._system_language(), "pt-br")

    def test_spanish_locale_is_supported(self):
        with (
            patch.dict(os.environ, {"LANG": "es_ES.UTF-8"}, clear=True),
            patch("i18n.locale.getlocale", return_value=(None, None)),
        ):
            self.assertEqual(i18n._system_language(), "es")

    def test_unsupported_locale_falls_back_to_english(self):
        with (
            patch.dict(os.environ, {"LANG": "de_DE.UTF-8"}, clear=True),
            patch("i18n.locale.getlocale", return_value=("de_DE", "UTF-8")),
        ):
            self.assertEqual(i18n._system_language(), "en")

    def test_every_language_has_every_message(self):
        keys = set(i18n.STRINGS["en"])
        for language in i18n.SUPPORTED_LANGUAGES:
            self.assertEqual(set(i18n.STRINGS[language]), keys, language)

    def test_explicit_saved_preference_overrides_system_language(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text(json.dumps({"language_choice": "en"}), encoding="utf-8")
            with (
                patch("i18n.CONFIG_FILE", str(config)),
                patch("i18n._system_language", return_value="pt-br"),
            ):
                self.assertEqual(i18n._load_saved_language(), "en")

    def test_first_run_without_saved_language_inherits_system_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            with (
                patch("i18n.CONFIG_FILE", str(config)),
                patch("i18n._system_language", return_value="en"),
            ):
                self.assertEqual(i18n._load_saved_language(), "en")


if __name__ == "__main__":
    unittest.main()
