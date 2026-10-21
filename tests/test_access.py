"""Per-machine SSH access from the target spreadsheet."""
import base64
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from core import Terminal
from i18n import get_language, set_language
from snapshots import SnapshotStore


class AccessCheckTests(unittest.TestCase):
    def setUp(self):
        previous = get_language()
        set_language("en")
        self.addCleanup(set_language, previous)
        self.terminals = [Terminal(ip="10.0.0.1"), Terminal(ip="10.0.0.2")]

    def test_panel_is_optional_when_every_row_has_user_and_password(self):
        credentials = {ip: {"user": "pdv", "password": "x"} for ip in ("10.0.0.1", "10.0.0.2")}
        app._check_access(self.terminals, credentials, panel_user="", panel_auth=False)

    def test_rows_without_access_are_named(self):
        credentials = {"10.0.0.1": {"user": "pdv", "password": "x"}}
        with self.assertRaisesRegex(ValueError, r"1 machines have no user .*10\.0\.0\.2"):
            app._check_access(self.terminals, credentials, panel_user="", panel_auth=True)
        with self.assertRaisesRegex(ValueError, r"1 machines have no password .*10\.0\.0\.2"):
            app._check_access(self.terminals, credentials, panel_user="root", panel_auth=False)

    def test_without_access_columns_the_panel_messages_stay(self):
        with self.assertRaisesRegex(ValueError, "Enter the SSH user"):
            app._check_access(self.terminals, {}, panel_user="", panel_auth=True)
        with self.assertRaisesRegex(ValueError, "Enter an SSH private key"):
            app._check_access(self.terminals, {}, panel_user="root", panel_auth=False)


class UploadTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_uploaded_copy_is_private_and_status_mentions_sheet_access(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b"IP,USER,PASSWORD\n10.0.0.1,pdv,secret\n10.0.0.2,,\n"
            with patch("app.get_user_data_dir", return_value=Path(directory)):
                controller = app.InventoryController(
                    config_path=Path(directory) / "config.json",
                    snapshot_store=SnapshotStore(Path(directory) / "snapshots.db"),
                )
                state = controller.upload_targets("lojas.csv", base64.b64encode(content).decode())
            mode = stat.S_IMODE((Path(directory) / "uploads" / "lojas.csv").stat().st_mode)

        self.assertEqual(mode, 0o600)
        self.assertEqual(state["targets_info"]["credential_columns"], ["USER", "PASSWORD"])
        self.assertNotIn("secret", repr(state))


if __name__ == "__main__":
    unittest.main()
