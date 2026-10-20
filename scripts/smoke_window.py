"""Start a packaged Invenux build and check that its native window loads the UI.

Usage: python scripts/smoke_window.py <path to the built executable>

On Linux (Qt WebEngine) and Windows (WebView2) the web engine exposes the
DevTools endpoint, so the check waits for a page titled "Invenux" served by the
local server. WKWebView on macOS has no such endpoint; there the check only
confirms that the process is still running after the window opened.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

DEVTOOLS_PORT = 9333
TIMEOUT_SECONDS = 90
MACOS_ALIVE_SECONDS = 20


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


def main(executable: str) -> int:
    env = dict(os.environ)
    env["QTWEBENGINE_REMOTE_DEBUGGING"] = str(DEVTOOLS_PORT)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEVTOOLS_PORT}"
    process = subprocess.Popen([executable], env=env)
    try:
        if sys.platform == "darwin":
            time.sleep(MACOS_ALIVE_SECONDS)
            if process.poll() is not None:
                print(f"Invenux exited with status {process.returncode}", file=sys.stderr)
                return 1
            print(f"Invenux still running after {MACOS_ALIVE_SECONDS} s")
            return 0

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
