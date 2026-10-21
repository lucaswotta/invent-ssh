"""Find a newer Invenux release on GitHub and fetch the package for this system.

Only the public releases API is contacted. Downloads are checked against the
release's SHA256SUMS before anything is opened or installed.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from i18n import t
from paths import external_program_env

LATEST_RELEASE_API = "https://api.github.com/repos/lucaswotta/invenux/releases/latest"
LINUX_INSTALL_DIR = Path.home() / ".local" / "lib" / "invenux"
_USER_AGENT = "invenux-update-check"


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.9.1' -> (0, 9, 1); anything else -> () so it never counts as newer."""
    match = re.fullmatch(r"v?(\d+(?:\.\d+)*)", str(text).strip())
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def package_name(version: str, system: str | None = None, machine: str | None = None) -> str | None:
    """Release asset for this OS and CPU, as release.yml names it."""
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if system == "Linux" and machine in {"x86_64", "amd64"}:
        return f"invenux-{version}-linux-x86_64.tar.xz"
    if system == "Windows" and machine in {"x86_64", "amd64"}:
        return f"invenux-{version}-windows-x86_64.exe"
    if system == "Darwin":
        return f"invenux-{version}-macos-{'arm64' if machine == 'arm64' else 'x86_64'}.zip"
    return None


def _get(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(request, timeout=timeout)


def check(current_version: str, timeout: float = 6.0) -> dict[str, Any] | None:
    """Return the latest release when it is newer than current_version, else None."""
    with _get(LATEST_RELEASE_API, timeout) as response:
        release = json.load(response)
    latest = str(release.get("tag_name", "")).lstrip("v")
    if parse_version(latest) <= parse_version(current_version):
        return None
    assets = {asset["name"]: asset["browser_download_url"] for asset in release.get("assets", [])}
    name = package_name(latest)
    return {
        "version": latest,
        "page": release.get("html_url", ""),
        "package": name if name in assets else None,
        "package_url": assets.get(name or ""),
        "sums_url": assets.get("SHA256SUMS"),
    }


def download(info: dict[str, Any], destination_dir: Path, timeout: float = 30.0) -> Path:
    """Download the package into destination_dir and verify it against SHA256SUMS."""
    if not info.get("package_url") or not info.get("sums_url"):
        raise ValueError(t("update_no_package"))
    with _get(info["sums_url"], timeout) as response:
        sums = response.read().decode("utf-8")
    expected = next(
        (line.split()[0] for line in sums.splitlines() if line.split()[-1:] == [info["package"]]),
        None,
    )
    if not expected:
        raise ValueError(t("update_no_checksum", name=info["package"]))

    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / info["package"]
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    try:
        with _get(info["package_url"], timeout) as response, partial.open("wb") as handle:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                handle.write(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(t("update_checksum_mismatch", name=info["package"]))
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(target)
    return target


def installed_with_install_sh(executable: Path) -> bool:
    """True when this binary is the copy that packaging/linux/install.sh placed."""
    return executable.resolve().parent == LINUX_INSTALL_DIR.resolve()


def install_linux_package(archive: Path) -> None:
    """Unpack a verified .tar.xz and run its install.sh, which replaces LINUX_INSTALL_DIR."""
    with tempfile.TemporaryDirectory(prefix="invenux-update-") as directory:
        with tarfile.open(archive, "r:xz") as bundle:
            bundle.extractall(directory, filter="data")
        folders = [path for path in Path(directory).iterdir() if (path / "install.sh").is_file()]
        if len(folders) != 1:
            raise ValueError(t("update_bad_package", name=archive.name))
        completed = subprocess.run(
            ["sh", str(folders[0] / "install.sh")],
            capture_output=True, text=True, check=False, env=external_program_env(),
        )
        if completed.returncode:
            raise ValueError(t("update_install_failed", error=(completed.stderr or completed.stdout).strip()))

