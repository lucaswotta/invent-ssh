"""Native window launcher and packaging tests."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
import build


class PackagingTests(unittest.TestCase):
    def test_windows_builds_one_exe_and_other_systems_a_folder(self):
        for system, mode in (("Windows", "--onefile"), ("Linux", "--onedir"), ("Darwin", "--onedir")):
            with self.subTest(system=system), patch("build.platform.system", return_value=system):
                command = build.build_command()
            self.assertIn(mode, command)
            self.assertNotIn("--onefile" if mode == "--onedir" else "--onedir", command)

    def test_unused_qt_modules_are_excluded(self):
        command = build.build_command()
        excluded = {command[i + 1] for i, arg in enumerate(command) if arg == "--exclude-module"}
        self.assertIn("PySide6.QtQml", excluded)
        self.assertNotIn("PySide6.QtWebEngineWidgets", excluded)

    def test_prune_keeps_app_locales_and_drops_other_qt_files(self):
        with tempfile.TemporaryDirectory() as directory:
            qt = Path(directory) / "_internal" / "PySide6" / "Qt"
            locales = qt / "translations" / "qtwebengine_locales"
            locales.mkdir(parents=True)
            (qt / "resources").mkdir()
            for name in ("pt-BR.pak", "en-US.pak", "es.pak", "es-419.pak", "de.pak"):
                (locales / name).write_bytes(b"x")
            (qt / "translations" / "qtbase_pt_BR.qm").write_bytes(b"x")
            (qt / "resources" / "qtwebengine_devtools_resources.pak").write_bytes(b"x")
            (qt / "resources" / "qtwebengine_resources.pak").write_bytes(b"x")

            freed = build.prune_qt_resources(Path(directory))

            self.assertEqual(freed, 3)
            self.assertEqual(
                sorted(p.name for p in locales.iterdir()),
                ["en-US.pak", "es-419.pak", "es.pak", "pt-BR.pak"],
            )
            self.assertEqual([p.name for p in (qt / "resources").iterdir()], ["qtwebengine_resources.pak"])


class LauncherTests(unittest.TestCase):
    def test_linux_without_display_skips_the_window_and_uses_the_browser(self):
        webview = MagicMock()
        on_close = MagicMock()
        environment = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict(os.environ, environment, clear=True),
            patch.dict(sys.modules, {"webview": webview}),
            patch("app.webbrowser.open") as browser_open,
            patch("builtins.print"),
        ):
            app.launch_desktop_window("http://127.0.0.1:1/", on_close, lambda: 10_000.0)

        webview.create_window.assert_not_called()
        browser_open.assert_called_once_with("http://127.0.0.1:1/")
        on_close.assert_called_once()

    def test_window_allows_text_selection_and_closes_the_server(self):
        webview = MagicMock()
        on_close = MagicMock()
        closed_event = webview.create_window.return_value.events.closed
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict(sys.modules, {"webview": webview}),
            patch("app.webbrowser.open") as browser_open,
        ):
            app.launch_desktop_window("http://127.0.0.1:1/", on_close, lambda: 0.0)

        self.assertTrue(webview.create_window.call_args.kwargs["text_select"])
        closed_event.__iadd__.assert_called_once_with(on_close)
        webview.start.assert_called_once()
        # WinForms raises on a PNG icon and kills the process (0xE0434352).
        self.assertIsNone(webview.start.call_args.kwargs["icon"])
        browser_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
