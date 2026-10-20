"""Cross-platform per-user path and legacy-config tests."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import paths


class UserPathTests(unittest.TestCase):
    def test_linux_respects_xdg_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_DATA_HOME": str(root / "data"),
            }
            with (
                patch("paths.platform.system", return_value="Linux"),
                patch.dict(os.environ, environment, clear=False),
                patch("pathlib.Path.home", return_value=root / "home"),
            ):
                config = paths.get_config_dir()
                data = paths.get_user_data_dir()
                logs = paths.get_logs_dir()

            self.assertEqual(config, root / "config" / "invent-ssh")
            self.assertEqual(data, root / "data" / "invent-ssh")
            self.assertEqual(logs, root / "data" / "invent-ssh" / "logs")
            self.assertTrue(config.is_dir())
            self.assertTrue(logs.is_dir())

    def test_config_migration_whitelists_preferences_and_drops_unknown_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_root = root / "legacy"
            legacy_root.mkdir()
            old_config = {
                "language": "en",
                "max_workers": 22,
                "last_ssh_user": "inventory-reader",
                "last_ssh_key_path": "/home/user/.ssh/id_ed25519",
                "ssh_pass": "must-not-be-migrated",
                "legacy_private_secret": "must-not-be-migrated",
                "customer_inventory": ["sensitive-host"],
            }
            (legacy_root / "config.json").write_text(json.dumps(old_config), encoding="utf-8")

            with (
                patch("paths.__file__", str(legacy_root / "paths.py")),
                patch("paths.platform.system", return_value="Linux"),
                patch.dict(os.environ, {"XDG_CONFIG_HOME": str(root / "new-config")}, clear=False),
                patch("pathlib.Path.home", return_value=root / "home"),
            ):
                config_path = paths.get_config_path()
                migrated = json.loads(config_path.read_text(encoding="utf-8"))

            self.assertEqual(migrated["language"], "en")
            self.assertEqual(migrated["max_workers"], 22)
            self.assertEqual(migrated["last_ssh_user"], "inventory-reader")
            self.assertNotIn("ssh_pass", migrated)
            self.assertNotIn("legacy_private_secret", migrated)
            self.assertNotIn("customer_inventory", migrated)
            self.assertEqual(config_path.parent, root / "new-config" / "invent-ssh")

    def test_reports_live_in_documents_not_the_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("pathlib.Path.home", return_value=root):
                reports = paths.get_reports_dir()
            self.assertEqual(reports, root / "Documents" / "Invent-SSH Reports")
            self.assertTrue(reports.is_dir())


if __name__ == "__main__":
    unittest.main()
