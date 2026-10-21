"""Release check, verified download and in-place Linux install."""
import hashlib
import io
import json
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import updates
from i18n import get_language, set_language
from snapshots import SnapshotStore


def fake_response(body: bytes) -> io.BytesIO:
    return io.BytesIO(body)


def release(tag: str, names: list[str]) -> dict:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/lucaswotta/invenux/releases/tag/{tag}",
        "assets": [{"name": name, "browser_download_url": f"https://example.test/{name}"} for name in names],
    }


class VersionTests(unittest.TestCase):
    def test_versions_compare_numerically(self):
        self.assertGreater(updates.parse_version("v0.10.0"), updates.parse_version("0.9.1"))
        self.assertEqual(updates.parse_version("nightly"), ())

    def test_package_names_follow_release_workflow(self):
        self.assertEqual(updates.package_name("0.9.0", "Linux", "x86_64"), "invenux-0.9.0-linux-x86_64.tar.xz")
        self.assertEqual(updates.package_name("0.9.0", "Windows", "AMD64"), "invenux-0.9.0-windows-x86_64.exe")
        self.assertEqual(updates.package_name("0.9.0", "Darwin", "arm64"), "invenux-0.9.0-macos-arm64.zip")
        self.assertEqual(updates.package_name("0.9.0", "Darwin", "x86_64"), "invenux-0.9.0-macos-x86_64.zip")
        self.assertIsNone(updates.package_name("0.9.0", "Linux", "aarch64"))


class CheckTests(unittest.TestCase):
    def test_newer_release_reports_this_system_package(self):
        names = ["invenux-0.9.1-linux-x86_64.tar.xz", "SHA256SUMS"]
        body = json.dumps(release("v0.9.1", names)).encode()
        with (
            patch("updates.urllib.request.urlopen", return_value=fake_response(body)),
            patch("updates.platform.system", return_value="Linux"),
            patch("updates.platform.machine", return_value="x86_64"),
        ):
            info = updates.check("0.9.0")
        self.assertEqual(info["version"], "0.9.1")
        self.assertEqual(info["package"], names[0])
        self.assertTrue(info["sums_url"].endswith("SHA256SUMS"))

    def test_same_or_older_release_is_not_an_update(self):
        body = json.dumps(release("v0.9.0", [])).encode()
        with patch("updates.urllib.request.urlopen", return_value=fake_response(body)):
            self.assertIsNone(updates.check("0.9.0"))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        previous = get_language()
        set_language("en")
        self.addCleanup(set_language, previous)
        self.package = b"package bytes"
        self.info = {
            "package": "invenux-0.9.1-linux-x86_64.tar.xz",
            "package_url": "https://example.test/pkg",
            "sums_url": "https://example.test/sums",
        }

    def serve(self, sums: str):
        def urlopen(request, timeout):
            return fake_response(sums.encode() if request.full_url.endswith("sums") else self.package)
        return patch("updates.urllib.request.urlopen", side_effect=urlopen)

    def test_verified_download_is_kept(self):
        digest = hashlib.sha256(self.package).hexdigest()
        with tempfile.TemporaryDirectory() as directory, self.serve(f"{digest}  {self.info['package']}\n"):
            path = updates.download(self.info, Path(directory))
            self.assertEqual(path.read_bytes(), self.package)
            self.assertEqual([p.name for p in Path(directory).iterdir()], [self.info["package"]])

    def test_checksum_mismatch_leaves_nothing_behind(self):
        with tempfile.TemporaryDirectory() as directory, self.serve(f"{'0' * 64}  {self.info['package']}\n"):
            with self.assertRaisesRegex(ValueError, "does not match SHA256SUMS"):
                updates.download(self.info, Path(directory))
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipIf(os.name == "nt", "install.sh needs a POSIX shell")
    def test_linux_package_runs_its_install_script(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "installed"
            folder = root / "invenux-0.9.1-linux-x86_64"
            folder.mkdir()
            (folder / "install.sh").write_text(f"touch '{marker}'\n")
            archive = root / "pkg.tar.xz"
            with tarfile.open(archive, "w:xz") as bundle:
                bundle.add(folder, arcname=folder.name)

            updates.install_linux_package(archive)

            self.assertTrue(marker.exists())


class ControllerTests(unittest.TestCase):
    def make_controller(self, directory: str) -> app.InventoryController:
        return app.InventoryController(
            config_path=Path(directory) / "config.json",
            snapshot_store=SnapshotStore(Path(directory) / "s.db"),
        )

    def test_theme_and_update_check_choice_are_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make_controller(directory).update_config({"theme": "light", "check_updates": False})
            reloaded = self.make_controller(directory)
            self.assertEqual(reloaded.config["theme_choice"], "light")
            self.assertFalse(reloaded.config["check_updates"])
            reloaded.update_config({"theme": "anything"})
            self.assertEqual(reloaded.config["theme_choice"], "system")

    def test_state_reports_version_and_available_update(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.make_controller(directory)
            info = {"version": "9.9.9", "page": "https://example.test", "package": None,
                    "package_url": None, "sums_url": None}
            with patch("app.release_updates.check", return_value=info):
                state = controller.check_for_update()
        self.assertEqual(state["version"], app.APP_VERSION)
        self.assertEqual(state["update"]["state"], "available")
        self.assertEqual(state["update"]["version"], "9.9.9")

    def test_source_checkout_opens_the_release_page_instead_of_installing(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = self.make_controller(directory)
            controller.update_info = {"state": "available", "version": "9.9.9", "page": "https://example.test/r"}
            with patch("app.webbrowser.open") as browser_open, patch("app.release_updates.download") as download:
                state = controller.install_update()
        browser_open.assert_called_once_with("https://example.test/r")
        download.assert_not_called()
        self.assertEqual(state["update"]["state"], "page")


if __name__ == "__main__":
    unittest.main()
