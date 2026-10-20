"""Cross-platform user paths for configuration, logs, and exported reports.

Mutable application data is never written beside the source code or a PyInstaller
bundle. The report directory is human-visible under the user's Documents folder.
"""
from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any


APP_SLUG = "invent-ssh"
APP_DISPLAY_NAME = "Invent-SSH"
LEGACY_CONFIG_NAMES = ("config.json",)


def get_user_data_dir() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or home / "AppData" / "Local")
        path = root / APP_DISPLAY_NAME
    elif system == "Darwin":
        path = home / "Library" / "Application Support" / APP_DISPLAY_NAME
    else:
        path = Path(os.environ.get("XDG_DATA_HOME") or home / ".local" / "share") / APP_SLUG
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_dir() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        root = Path(os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or home / "AppData" / "Roaming")
        path = root / APP_DISPLAY_NAME
    elif system == "Darwin":
        path = home / "Library" / "Application Support" / APP_DISPLAY_NAME
    else:
        path = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / APP_SLUG
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path() -> Path:
    destination = get_config_dir() / "config.json"
    if destination.exists():
        return destination

    # Migrate only known, non-secret preferences from an old source-tree config.
    # Never copy unknown keys or credential material into the new config.
    for name in LEGACY_CONFIG_NAMES:
        legacy = Path(__file__).resolve().parent / name
        if not legacy.is_file():
            continue
        try:
            candidate = json.loads(legacy.read_text(encoding="utf-8"))
            if not isinstance(candidate, dict):
                continue
            allowed = {
                "last_file_path", "report_format", "spreadsheet_format", "language",
                "last_ssh_user", "last_ssh_key_path", "max_workers", "ssh_timeout",
                "show_welcome_modal", "trust_unknown_hosts", "include_sensitive_identifiers",
            }
            sanitized = {key: candidate[key] for key in allowed if key in candidate}
            destination.write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                destination.chmod(0o600)
            except OSError:
                pass
            break
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return destination


def get_logs_dir() -> Path:
    path = get_user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_known_hosts_path() -> Path:
    return get_user_data_dir() / "known_hosts"


def get_snapshots_db_path() -> Path:
    return get_user_data_dir() / "snapshots.db"


def get_reports_dir() -> Path:
    path = Path.home() / "Documents" / "Invent-SSH Reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_user_config(config: dict[str, Any]) -> None:
    path = get_config_path()
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
