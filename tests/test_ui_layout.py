"""Regression tests for the macOS utility UI, brand assets, and local API server."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import app
from snapshots import SnapshotStore


class DesktopUtilityUITests(unittest.TestCase):
    def test_brand_tokens_use_macos_dark_utility_palette(self):
        self.assertEqual(app.COLORS["bg_window"], "#1C1C1E")
        self.assertEqual(app.COLORS["bg_sidebar"], "#232326")
        self.assertEqual(app.COLORS["bg_card"], "#262629")
        self.assertEqual(app.COLORS["accent_blue"], "#0A84FF")
        self.assertEqual(app.COLORS["status_online"], "#30D158")
        self.assertEqual(app.APP_BRAND, "Invent-SSH")

        theme_path = Path(__file__).resolve().parents[1] / "brand" / "theme.json"
        theme = json.loads(theme_path.read_text(encoding="utf-8"))
        self.assertEqual(theme["palette"]["bg_window"], "#1C1C1E")
        self.assertEqual(theme["palette"]["accent_blue"], "#0A84FF")

    def test_brand_assets_use_geometric_mark_without_mascot(self):
        root = Path(__file__).resolve().parents[1]
        svg = (root / "brand" / "logo-mark.svg").read_text(encoding="utf-8")
        self.assertIn("Invent-SSH geometric mark", svg)
        self.assertIn("#0A84FF", svg)
        self.assertNotIn("penguin", svg.lower())
        self.assertTrue((root / "brand" / "invent-ssh-mark-64.png").is_file())
        self.assertTrue((root / "brand" / "invent-ssh-mark-128.png").is_file())
        self.assertTrue((root / "app.ico").is_file())

    def test_ui_html_contains_three_views_popovers_and_100vh_100vw(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertIn("width: 100vw;", html)
        self.assertIn("height: 100vh;", html)
        self.assertIn("Coleta", html)
        self.assertIn("Parque", html)
        self.assertIn("Snapshots", html)
        self.assertNotIn("Parque & Upgrade", html)
        self.assertNotIn("Snapshots & Diff", html)
        self.assertIn('id="popover-ssh"', html)
        self.assertIn('id="popover-targets"', html)
        self.assertIn('id="popover-export"', html)

    def test_local_http_server_enforces_token_and_loads_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg_path = tmp_path / "config.json"
            db_path = tmp_path / "snapshots.db"
            csv_path = tmp_path / "alvos.csv"
            csv_path.write_text(
                "IP,HOSTNAME,LOCATION\n10.24.8.104,srv-app-sp04,Matriz\n10.24.12.19,pdv-fl04-cx01,Filial 04\n",
                encoding="utf-8",
            )

            controller = app.InventoryController(
                config_path=cfg_path,
                snapshot_store=SnapshotStore(db_path),
            )
            server, url, token = app.create_http_server(controller)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.shutdown)
            self.addCleanup(server.server_close)

            # Root HTML injects session token
            with urllib.request.urlopen(url) as response:
                page = response.read().decode("utf-8")
            self.assertIn(token, page)

            # A foreign Host header (DNS rebinding) never receives the token
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(urllib.request.Request(url, headers={"Host": "attacker.example"}))
            self.assertEqual(ctx.exception.code, 403)

            # Unauthenticated API request is rejected with 403
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(url + "api/state")
            self.assertEqual(ctx.exception.code, 403)

            # Authenticated config update keeps password out of disk config
            req_cfg = urllib.request.Request(
                url + "api/config",
                data=json.dumps({
                    "ssh_user": "inv-reader",
                    "ssh_pass": "ephemeral-secret",
                    "max_workers": 24,
                    "ssh_timeout": 12,
                }).encode("utf-8"),
                headers={"X-Invent-Token": token, "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_cfg) as response:
                cfg_payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(cfg_payload["config"]["ssh_user"], "inv-reader")
            self.assertTrue(cfg_payload["config"]["has_password"])
            self.assertNotIn("ssh_pass", cfg_payload["config"])
            saved_disk = cfg_path.read_text(encoding="utf-8")
            self.assertNotIn("ephemeral-secret", saved_disk)

            # /api/open never hands arbitrary files to the desktop opener
            req_open = urllib.request.Request(
                url + "api/open",
                data=json.dumps({"path": str(csv_path)}).encode("utf-8"),
                headers={"X-Invent-Token": token, "Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req_open)
            self.assertEqual(ctx.exception.code, 400)

            # Load targets CSV via API
            req_load = urllib.request.Request(
                url + "api/targets/load",
                data=json.dumps({"filepath": str(csv_path)}).encode("utf-8"),
                headers={"X-Invent-Token": token, "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req_load) as response:
                state_payload = json.loads(response.read().decode("utf-8"))
            self.assertEqual(len(state_payload["records"]), 2)
            self.assertEqual(state_payload["analytics"]["total"], 2)
            self.assertEqual(state_payload["analytics"]["locations_count"], 2)


if __name__ == "__main__":
    unittest.main()
