"""Start a packaged Invenux build and check that it opens its own window.

Usage: python scripts/smoke_window.py <path to the built executable>

With Qt WebEngine on Linux the DevTools endpoint is opened through
QTWEBENGINE_REMOTE_DEBUGGING, so the check waits for a page titled "Invenux"
served by the local server. pywebview sets the WebView2 arguments itself and
WKWebView has no such endpoint, so on Windows and macOS the check confirms that
the process stays up without falling back to the browser and, on Windows, that
the WebView2 runtime process started.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVTOOLS_PORT = 9333
TIMEOUT_SECONDS = 90
ALIVE_SECONDS = 20
FALLBACK_MARKER = "window unavailable"


def loaded_page() -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEVTOOLS_PORT}/json", timeout=2) as response:
            pages = json.load(response)
    except OSError:
        return None
    for page in pages:
        if page.get("title") == "Invenux" and page.get("url", "").startswith("http://127.0.0.1:"):
            return page
    return None


def webview2_running() -> bool:
    listing = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq msedgewebview2.exe", "/NH"],
        capture_output=True, text=True, check=False,
    ).stdout
    return "msedgewebview2.exe" in listing


def wait_for_devtools_page(process: subprocess.Popen) -> int:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(f"Invenux exited with status {process.returncode}", file=sys.stderr)
            return 1
        page = loaded_page()
        if page:
            print(f"Window loaded {page['url']}")
            return 0
        time.sleep(1)
    print(f"No Invenux page in the window after {TIMEOUT_SECONDS} s", file=sys.stderr)
    return 1


def check_window_without_devtools(process: subprocess.Popen, log_file: Path, log_start: int) -> int:
    time.sleep(ALIVE_SECONDS)
    if process.poll() is not None:
        print(f"Invenux exited with status {process.returncode}", file=sys.stderr)
        return 1
    fallbacks = []
    if log_file.exists():
        with log_file.open(encoding="utf-8", errors="replace") as log:
            log.seek(log_start)
            fallbacks = [line.strip() for line in log if FALLBACK_MARKER in line]
    if fallbacks:
        print("Invenux fell back to the browser:\n" + "\n".join(fallbacks), file=sys.stderr)
        return 1
    if sys.platform == "win32" and not webview2_running():
        print("msedgewebview2.exe is not running", file=sys.stderr)
        return 1
    print(f"Invenux window still open after {ALIVE_SECONDS} s")
    return 0


def main(executable: str) -> int:
    sys.path.insert(0, str(ROOT))
    import paths

    log_file = paths.get_logs_dir() / "invenux.log"
    log_start = log_file.stat().st_size if log_file.exists() else 0
    env = dict(os.environ)
    env["QTWEBENGINE_REMOTE_DEBUGGING"] = str(DEVTOOLS_PORT)
    process = subprocess.Popen([executable], env=env)
    try:
        if sys.platform.startswith("linux"):
            return wait_for_devtools_page(process)
        return check_window_without_devtools(process, log_file, log_start)
    finally:
        if sys.platform == "win32":
            # The onefile .exe is a bootloader whose child process runs the app.
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], check=False)
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
