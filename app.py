# -*- coding: utf-8 -*-
"""Invent-SSH application entry point, local API controller, and native window shell."""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable
from urllib.parse import urlparse

from core import InventoryEngine
from i18n import get_language, set_language
from paths import (
    get_config_path,
    get_documents_dir,
    get_logs_dir,
    get_reports_dir,
    get_snapshots_db_path,
    get_user_data_dir,
    save_user_config,
)
from reporting import create_template_workbook, save_report, save_snapshot_diff
from snapshots import SnapshotStore, compute_fleet_analytics

APP_BRAND = "Invent-SSH"
APP_VERSION = "0.5.0"
# Browsers throttle timers in hidden tabs to about one per minute.
BROWSER_IDLE_TIMEOUT_SECONDS = 180

COLORS = {
    "bg_window": "#1C1C1E",
    "bg_sidebar": "#232326",
    "bg_toolbar": "#252528",
    "bg_card": "#262629",
    "bg_control": "#36363A",
    "text_primary": "#F5F5F7",
    "text_secondary": "#98989D",
    "text_tertiary": "#6E6E73",
    "accent_blue": "#0A84FF",
    "status_online": "#30D158",
    "status_warning": "#FF9F0A",
    "status_offline": "#FF453A",
}


def resource_path(relative_path: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative_path


def setup_logging() -> None:
    log_dir = get_logs_dir()
    log_file = log_dir / "invent-ssh.log"
    handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    dta = out.get("dta_atualizacao")
    if hasattr(dta, "isoformat") and not isinstance(dta, str):
        try:
            out["dta_atualizacao"] = dta.isoformat(sep=" ", timespec="seconds")
        except TypeError:
            out["dta_atualizacao"] = dta.isoformat()
    return out


class InventoryController:
    """State and collection coordinator for the local web/desktop interface."""

    def __init__(
        self,
        config_path: Path | None = None,
        snapshot_store: SnapshotStore | None = None,
    ) -> None:
        self.lock = threading.Lock()
        self.config_path = config_path or get_config_path()
        self.snapshot_store = snapshot_store or SnapshotStore(get_snapshots_db_path())
        self.config: dict[str, Any] = self._load_config()
        self.records: list[dict[str, Any]] = []
        self.scanning: bool = False
        self.status_text: str = "Pronto para coleta"
        self.targets_info: dict[str, Any] = {}
        self.active_engine: InventoryEngine | None = None
        self._bootstrap_initial_records()

    def _load_config(self) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "filepath": "",
            "ssh_user": "",
            "ssh_key_path": "",
            "ssh_pass": "",
            "max_workers": 32,
            "ssh_timeout": 15,
            "trust_unknown_hosts": True,
            "include_sensitive_identifiers": False,
            "output_format": "XLSX",
            "language": get_language(),
        }
        try:
            if self.config_path.is_file():
                saved = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    defaults["filepath"] = str(saved.get("last_file_path") or saved.get("filepath") or "")
                    defaults["ssh_user"] = str(saved.get("last_ssh_user") or saved.get("ssh_user") or "")
                    defaults["ssh_key_path"] = str(saved.get("last_ssh_key_path") or saved.get("ssh_key_path") or "")
                    defaults["max_workers"] = max(1, min(int(saved.get("max_workers", 32)), 128))
                    defaults["ssh_timeout"] = max(2, min(int(saved.get("ssh_timeout", 15)), 120))
                    defaults["trust_unknown_hosts"] = bool(saved.get("trust_unknown_hosts", True))
                    defaults["include_sensitive_identifiers"] = bool(saved.get("include_sensitive_identifiers", False))
                    defaults["output_format"] = str(saved.get("report_format") or saved.get("output_format") or "XLSX").upper()
                    if saved.get("language"):
                        set_language(str(saved["language"]))
                        defaults["language"] = get_language()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return defaults

    def _persist_non_secret_config(self) -> None:
        persisted = {
            "last_file_path": self.config.get("filepath", ""),
            "last_ssh_user": self.config.get("ssh_user", ""),
            "last_ssh_key_path": self.config.get("ssh_key_path", ""),
            "max_workers": int(self.config.get("max_workers", 32)),
            "ssh_timeout": int(self.config.get("ssh_timeout", 15)),
            "trust_unknown_hosts": bool(self.config.get("trust_unknown_hosts", True)),
            "include_sensitive_identifiers": bool(self.config.get("include_sensitive_identifiers", False)),
            "report_format": str(self.config.get("output_format", "XLSX")).upper(),
            "language": get_language(),
        }
        try:
            if self.config_path == get_config_path():
                save_user_config(persisted)
            else:
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                self.config_path.write_text(json.dumps(persisted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass

    def _bootstrap_initial_records(self) -> None:
        snapshots = self.snapshot_store.list_snapshots(limit=1)
        if snapshots:
            latest = self.snapshot_store.get_snapshot(snapshots[0]["id"])
            if latest and latest.get("records"):
                self.records = list(latest["records"])
                online = latest["online_hosts"]
                total = latest["total_hosts"]
                pct = round((online / total) * 100, 1) if total else 0.0
                self.status_text = (
                    f"Concluído em {str(latest['duration_seconds']).replace('.', ',')} s · "
                    f"{str(pct).replace('.', ',')}% acessíveis"
                )
                return

        filepath = self.config.get("filepath", "")
        if filepath and Path(filepath).is_file():
            try:
                self.load_targets(filepath)
            except ValueError:
                pass

    def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            if "ssh_user" in updates:
                self.config["ssh_user"] = str(updates["ssh_user"] or "").strip()
            if "ssh_key_path" in updates:
                self.config["ssh_key_path"] = str(updates["ssh_key_path"] or "").strip()
            if "ssh_pass" in updates:
                self.config["ssh_pass"] = str(updates["ssh_pass"] or "")
            if "max_workers" in updates:
                self.config["max_workers"] = max(1, min(int(updates["max_workers"]), 128))
            if "ssh_timeout" in updates:
                self.config["ssh_timeout"] = max(2, min(int(updates["ssh_timeout"]), 120))
            if "trust_unknown_hosts" in updates:
                self.config["trust_unknown_hosts"] = bool(updates["trust_unknown_hosts"])
            if "include_sensitive_identifiers" in updates:
                self.config["include_sensitive_identifiers"] = bool(updates["include_sensitive_identifiers"])
            self._persist_non_secret_config()
            return self.public_config()

    def public_config(self) -> dict[str, Any]:
        cfg = dict(self.config)
        cfg.pop("ssh_pass", None)
        cfg["has_password"] = bool(self.config.get("ssh_pass"))
        return cfg

    def get_state(self) -> dict[str, Any]:
        with self.lock:
            records_copy = list(self.records)
            scanning = self.scanning
            status_text = self.status_text
            cfg = self.public_config()
        return {
            "config": cfg,
            "records": records_copy,
            "analytics": compute_fleet_analytics(records_copy),
            "snapshots": self.snapshot_store.list_snapshots(limit=50),
            "scanning": scanning,
            "status_text": status_text,
            "targets_info": dict(self.targets_info),
            "paths": {
                "home": str(Path.home()),
                "reports": str(get_reports_dir()),
                "documents": str(get_documents_dir()),
                "data": str(get_user_data_dir()),
                "logs": str(get_logs_dir()),
            },
        }

    def load_targets(self, filepath: str) -> dict[str, Any]:
        resolved = Path(filepath).expanduser()
        if not resolved.is_file():
            raise ValueError(f"Arquivo de alvos não encontrado: {filepath}")

        q: Queue = Queue()
        engine = InventoryEngine({"filepath": str(resolved)}, q)
        terminals = engine._load_from_spreadsheet()
        if not terminals:
            errors = []
            while not q.empty():
                level, msg, _ = q.get_nowait()
                if level == "ERROR":
                    errors.append(msg)
            raise ValueError(errors[-1] if errors else "Nenhum alvo válido encontrado na planilha.")

        summary = engine.load_summary
        notes = []
        if summary["rows_without_target"]:
            notes.append(f"linhas sem IP ignoradas: {_row_list(summary['rows_without_target'])}")
        if summary["duplicate_rows"]:
            notes.append(f"IPs repetidos ignorados: {_row_list(summary['duplicate_rows'])}")
        with self.lock:
            self.config["filepath"] = str(resolved)
            self._persist_non_secret_config()
            self.records = [_serialize_record(asdict(term)) for term in terminals]
            self.targets_info = {"filename": resolved.name, "count": len(terminals), **summary}
            self.status_text = f"{len(self.records)} máquinas carregadas de {resolved.name}"
            if notes:
                self.status_text += " · " + " · ".join(notes)
        return self.get_state()

    def upload_targets(self, filename: str, content_base64: str) -> dict[str, Any]:
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename or "targets.xlsx"))
        upload_dir = get_user_data_dir() / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / safe_name
        raw = base64.b64decode(content_base64)
        dest.write_bytes(raw)
        return self.load_targets(str(dest))

    def create_template(self, destination: Path | None = None) -> Path:
        target = destination or (get_reports_dir() / "modelo_alvos_invent_ssh.xlsx")
        path = create_template_workbook(target, language=get_language())
        with self.lock:
            self.status_text = f"Modelo salvo em {path}"
        return path

    def export_current(self, output_format: str = "XLSX") -> Path:
        with self.lock:
            records_copy = list(self.records)
        if not records_copy:
            raise ValueError("Não há máquinas na tabela para exportar.")
        path = save_report(
            records_copy,
            output_format,
            output_dir=get_reports_dir(),
            language=get_language(),
        )
        with self.lock:
            self.status_text = f"Relatório exportado: {path.name}"
        return path

    def open_location(self, target: str = "", path: str = "") -> None:
        folders = {"reports": get_reports_dir(), "data": get_user_data_dir(), "logs": get_logs_dir()}
        if path:
            chosen = Path(path).resolve()
            if chosen.parent != folders["reports"].resolve() or not chosen.is_file():
                raise ValueError("Só é possível abrir arquivos da pasta de relatórios.")
        elif target in folders:
            chosen = folders[target]
        else:
            raise ValueError("Local desconhecido.")
        _open_in_file_manager(chosen)

    def export_snapshot_diff(self, snapshot_id: int) -> Path:
        changes = self.snapshot_store.compute_diff(snapshot_id)["changes"]
        if not changes:
            raise ValueError("Não há alterações neste snapshot para exportar.")
        return save_snapshot_diff(changes, get_reports_dir(), snapshot_id)

    def load_snapshot_into_workspace(self, snapshot_id: int) -> dict[str, Any]:
        snap = self.snapshot_store.get_snapshot(snapshot_id)
        if snap is None:
            raise ValueError(f"Snapshot #{snapshot_id} não encontrado.")
        with self.lock:
            self.records = list(snap.get("records", []))
            self.status_text = f"Visualizando snapshot de {snap['created_at']}"
        return self.get_state()

    def start_scan(self) -> dict[str, Any]:
        with self.lock:
            if self.scanning:
                raise ValueError("Uma coleta já está em andamento.")
            filepath = str(self.config.get("filepath", "")).strip()
            if not filepath or not Path(filepath).expanduser().is_file():
                raise ValueError("Selecione uma planilha de alvos válida antes de iniciar.")
            ssh_user = str(self.config.get("ssh_user", "")).strip()
            if not ssh_user:
                raise ValueError("Informe o Usuário SSH antes de iniciar a coleta.")
            ssh_key = str(self.config.get("ssh_key_path", "")).strip()
            ssh_pass = str(self.config.get("ssh_pass", ""))
            if not ssh_key and not ssh_pass:
                raise ValueError("Informe uma Chave Privada SSH ou Senha SSH.")
            if ssh_key and not Path(ssh_key).expanduser().is_file():
                raise ValueError(f"Chave SSH não encontrada: {ssh_key}")

            run_config = dict(self.config)
            run_config["filepath"] = str(Path(filepath).expanduser())
            if ssh_key:
                run_config["ssh_key_path"] = str(Path(ssh_key).expanduser())

            q: Queue = Queue()
            engine = InventoryEngine(run_config, q)
            terminals = engine._load_from_spreadsheet()
            if not terminals:
                raise ValueError("Nenhum destino válido encontrado na planilha.")

            self.records = [_serialize_record(asdict(term)) for term in terminals]
            self.scanning = True
            self.active_engine = engine
            self.status_text = f"Coletando 0/{len(self.records)} (0,0%)..."

        worker = threading.Thread(
            target=self._run_scan_worker,
            args=(engine, q, Path(filepath).name),
            daemon=True,
            name="invent-ssh-scan-coordinator",
        )
        worker.start()
        return self.get_state()

    def cancel_scan(self) -> dict[str, Any]:
        with self.lock:
            if self.active_engine is not None:
                self.active_engine.cancel()
                self.status_text = "Cancelando coleta..."
        return self.get_state()

    def _run_scan_worker(self, engine: InventoryEngine, q: Queue, source_name: str) -> None:
        started = time.monotonic()
        runner = threading.Thread(target=engine.run_inventory, daemon=True)
        runner.start()

        index_by_ip: dict[str, int] = {}
        with self.lock:
            for idx, rec in enumerate(self.records):
                index_by_ip[str(rec.get("ip"))] = idx
            total = len(self.records)

        processed = 0
        while runner.is_alive() or not q.empty():
            try:
                level, message, value = q.get(timeout=0.1)
            except Empty:
                continue

            if level == "HOST_RESULT" and isinstance(value, dict):
                serialized = _serialize_record(value)
                ip = str(serialized.get("ip"))
                processed += 1
                pct = round((processed / total) * 100, 1) if total else 100.0
                with self.lock:
                    idx = index_by_ip.get(ip)
                    if idx is not None and idx < len(self.records):
                        self.records[idx] = serialized
                    else:
                        self.records.append(serialized)
                    self.status_text = (
                        f"Coletando {processed}/{total} ({str(pct).replace('.', ',')}%)..."
                    )

        runner.join(timeout=1.0)
        elapsed = max(0.1, round(time.monotonic() - started, 1))
        with self.lock:
            final_records = [dict(r) for r in self.records if str(r.get("status", "")).upper() != "PENDING"]
            all_records = list(self.records)
            self.scanning = False
            self.active_engine = None

            online = sum(str(r.get("status", "")).upper() == "ONLINE" for r in all_records)
            avail = round((online / len(all_records)) * 100, 1) if all_records else 0.0
            self.status_text = (
                f"Concluído em {str(elapsed).replace('.', ',')} s · "
                f"{str(avail).replace('.', ',')}% acessíveis"
            )

        if final_records:
            try:
                self.snapshot_store.save_snapshot(
                    all_records,
                    source_name=source_name,
                    duration_seconds=elapsed,
                )
            except Exception:
                logging.getLogger(__name__).warning("Failed to save local snapshot", exc_info=True)


def _row_list(rows: list[int], limit: int = 5) -> str:
    shown = ", ".join(str(row) for row in rows[:limit])
    return shown + (f" e mais {len(rows) - limit}" if len(rows) > limit else "")


def _open_in_file_manager(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _pick_local_file(title: str, patterns: list[str] | None = None) -> str | None:
    """Open a native OS file picker without requiring tkinter when zenity/kdialog is available."""
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", f"--title={title}"]
        if patterns:
            cmd.append(f"--file-filter={' '.join(patterns)}")
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
        return None
    if shutil.which("kdialog"):
        cmd = ["kdialog", "--getopenfilename", str(Path.home())]
        if patterns:
            cmd.append(" ".join(patterns))
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if completed.returncode == 0 and completed.stdout.strip():
            return completed.stdout.strip()
        return None
    return None


def create_http_server(
    controller: InventoryController,
    host: str = "127.0.0.1",
    port: int = 0,
) -> tuple[ThreadingHTTPServer, str, str]:
    """Create a thread-safe local HTTP server with session-token protection."""
    session_token = secrets.token_urlsafe(24)
    ui_html_path = resource_path("ui/index.html")

    class RequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _check_host(self) -> bool:
            # A DNS-rebinding page reaches this port under its own host name.
            self.server.last_request_at = time.monotonic()
            port = self.server.server_address[1]
            if self.headers.get("Host", "") in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                return True
            self._send_json({"error": "Host não autorizado."}, status=HTTPStatus.FORBIDDEN)
            return False

        def _check_token(self) -> bool:
            provided = self.headers.get("X-Invent-Token", "")
            if not secrets.compare_digest(provided, session_token):
                self._send_json({"error": "Sessão não autorizada."}, status=HTTPStatus.FORBIDDEN)
                return False
            return True

        def _read_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            if length > 25_000_000:
                raise ValueError("Payload excede o limite permitido.")
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def do_GET(self) -> None:
            if not self._check_host():
                return
            parsed = urlparse(self.path)
            path = parsed.path
            if path in {"/", "/index.html"}:
                html_text = ui_html_path.read_text(encoding="utf-8")
                injected = html_text.replace(
                    "<head>",
                    f'<head>\n<script>window.__INVENT_TOKEN__ = {json.dumps(session_token)};</script>',
                    1,
                )
                body = injected.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            if not self._check_token():
                return

            if path == "/api/state":
                self._send_json(controller.get_state())
                return

            if path == "/api/ping":
                self._send_json({})
                return

            if path == "/api/snapshots":
                self._send_json({"snapshots": controller.snapshot_store.list_snapshots()})
                return

            match_diff = re.fullmatch(r"/api/snapshots/(\d+)/diff", path)
            if match_diff:
                try:
                    snap_id = int(match_diff.group(1))
                    self._send_json(controller.snapshot_store.compute_diff(snap_id))
                except ValueError as exc:
                    self._send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
                return

            self._send_json({"error": "Rota não encontrada."}, status=HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._check_host() or not self._check_token():
                return
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                payload = self._read_body()
                if path == "/api/config":
                    cfg = controller.update_config(payload)
                    self._send_json({"config": cfg})
                    return

                if path == "/api/targets/load":
                    state = controller.load_targets(str(payload.get("filepath", "")))
                    self._send_json(state)
                    return

                if path == "/api/targets/upload":
                    state = controller.upload_targets(
                        str(payload.get("filename", "targets.xlsx")),
                        str(payload.get("content_base64", "")),
                    )
                    self._send_json(state)
                    return

                if path == "/api/open":
                    controller.open_location(str(payload.get("target", "")), str(payload.get("path", "")))
                    self._send_json({})
                    return

                if path == "/api/targets/template":
                    out_path = controller.create_template()
                    self._send_json({"path": str(out_path)})
                    return

                if path == "/api/export":
                    fmt = str(payload.get("format", "XLSX")).upper()
                    out_path = controller.export_current(fmt)
                    self._send_json({"path": str(out_path)})
                    return

                if path == "/api/scan/start":
                    state = controller.start_scan()
                    self._send_json(state)
                    return

                if path == "/api/scan/cancel":
                    state = controller.cancel_scan()
                    self._send_json(state)
                    return

                if path == "/api/dialog/targets":
                    chosen = _pick_local_file("Selecionar lista de máquinas", ["*.xlsx", "*.xlsm", "*.csv"])
                    if chosen:
                        self._send_json({"filepath": chosen})
                    else:
                        self._send_json({"filepath": None, "fallback_upload": True})
                    return

                if path == "/api/dialog/key":
                    chosen = _pick_local_file("Selecionar Chave Privada SSH")
                    self._send_json({"filepath": chosen})
                    return

                match_export = re.fullmatch(r"/api/snapshots/(\d+)/diff/export", path)
                if match_export:
                    out_path = controller.export_snapshot_diff(int(match_export.group(1)))
                    self._send_json({"path": str(out_path)})
                    return

                match_load = re.fullmatch(r"/api/snapshots/(\d+)/load", path)
                if match_load:
                    snap_id = int(match_load.group(1))
                    self._send_json(controller.load_snapshot_into_workspace(snap_id))
                    return

                self._send_json({"error": "Rota não encontrada."}, status=HTTPStatus.NOT_FOUND)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                logging.getLogger(__name__).exception("API error on %s", path)
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    server = ThreadingHTTPServer((host, port), RequestHandler)
    server.last_request_at = time.monotonic()
    bound_host, bound_port = server.server_address[:2]
    url = f"http://{bound_host}:{bound_port}/"
    return server, url, session_token


def launch_desktop_window(
    url: str, on_close: Callable[[], None], seconds_since_request: Callable[[], float]
) -> None:
    """Open the Invent-SSH desktop window via pywebview, GTK WebKit2, or default browser."""
    try:
        import webview  # type: ignore

        window = webview.create_window(
            APP_BRAND,
            url,
            width=1440,
            height=880,
            min_size=(720, 520),
            background_color=COLORS["bg_window"],
        )
        window.events.closed += on_close
        webview.start()
        return
    except Exception:
        pass

    try:
        import gi  # type: ignore

        gi.require_version("Gtk", "3.0")
        try:
            gi.require_version("WebKit2", "4.1")
        except ValueError:
            gi.require_version("WebKit2", "4.0")
        from gi.repository import Gdk, Gtk, WebKit2  # type: ignore

        win = Gtk.Window(title=APP_BRAND)
        win.set_default_size(1440, 880)
        win.set_size_request(720, 520)
        display = Gdk.Display.get_default()
        if display is not None and display.get_n_monitors():
            workarea = display.get_monitor(0).get_workarea()
            if workarea.width < 1440 or workarea.height < 880:
                win.maximize()
        icon_path = resource_path("brand/invent-ssh-mark-128.png")
        if icon_path.is_file():
            try:
                win.set_icon_from_file(str(icon_path))
            except Exception:
                pass

        webview_widget = WebKit2.WebView()
        rgba = Gdk.RGBA()
        rgba.parse(COLORS["bg_window"])
        webview_widget.set_background_color(rgba)
        webview_widget.load_uri(url)
        win.add(webview_widget)

        def _handle_destroy(*_args: Any) -> None:
            on_close()
            Gtk.main_quit()

        win.connect("destroy", _handle_destroy)
        win.show_all()
        Gtk.main()
        return
    except Exception:
        pass

    # Without a window there is no close event; stop once the tab stops pinging.
    print(f"{APP_BRAND} v{APP_VERSION} ativo em {url}")
    webbrowser.open(url)
    try:
        while seconds_since_request() < BROWSER_IDLE_TIMEOUT_SECONDS:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    on_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{APP_BRAND} — Inventário de hardware Linux via SSH.")
    parser.add_argument("--port", type=int, default=0, help="Porta local do servidor HTTP (padrão: automática).")
    parser.add_argument("--no-window", action="store_true", help="Executa apenas o servidor local sem abrir janela.")
    parser.add_argument("--input", type=str, help="Executa coleta via linha de comando a partir da planilha informada.")
    parser.add_argument("--user", type=str, help="Usuário SSH para coleta via linha de comando.")
    parser.add_argument("--key", type=str, help="Caminho da chave privada SSH para coleta via linha de comando.")
    parser.add_argument("--output-format", type=str, default="XLSX", choices=["XLSX", "CSV", "HTML"])
    args = parser.parse_args(argv)

    setup_logging()
    controller = InventoryController()

    if args.input:
        try:
            controller.load_targets(args.input)
            if args.user:
                controller.update_config({"ssh_user": args.user})
            if args.key:
                controller.update_config({"ssh_key_path": args.key})
            controller.start_scan()
            while controller.get_state()["scanning"]:
                time.sleep(0.2)
            report = controller.export_current(args.output_format)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        print(str(report))
        return 0

    server, url, _token = create_http_server(controller, port=args.port)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    if args.no_window:
        print(f"{APP_BRAND} v{APP_VERSION} disponível em {url}", flush=True)
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            server.shutdown()
        return 0

    launch_desktop_window(
        url,
        on_close=server.shutdown,
        seconds_since_request=lambda: time.monotonic() - server.last_request_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
