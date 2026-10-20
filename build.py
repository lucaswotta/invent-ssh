"""Build a native Invent-SSH bundle with PyInstaller on the current OS.

This script deliberately does not install packages, remove old distributions, or
write binaries into the source tree. Install requirements-build.txt explicitly
in a virtual environment before running it.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENTRY_POINT = ROOT / "app.py"
BRAND_DIR = ROOT / "brand"
ICON_ICO = ROOT / "app.ico"
APP_SLUG = "invent-ssh"
REQUIREMENTS_BUILD = ROOT / "requirements-build.txt"


def read_app_version() -> str:
    """Read APP_VERSION from source without importing the GUI/Tk stack."""
    tree = ast.parse(ENTRY_POINT.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "APP_VERSION"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise RuntimeError("APP_VERSION was not found in app.py.")


def build_command(console: bool = False) -> list[str]:
    """Create the platform-native PyInstaller command and keep resources explicit."""
    version = read_app_version()
    build_root = ROOT / "build" / f"pyinstaller-{platform.system().lower()}"
    dist_root = ROOT / "dist"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        f"{APP_SLUG}-v{version}",
        "--distpath",
        str(dist_root),
        "--workpath",
        str(build_root),
        "--specpath",
        str(build_root),
        "--collect-all",
        "customtkinter",
        "--add-data",
        f"{BRAND_DIR}{os.pathsep}brand",
        "--hidden-import",
        "paramiko.transport",
        "--hidden-import",
        "paramiko.ed25519key",
        "--hidden-import",
        "paramiko.ecdsakey",
        "--hidden-import",
        "paramiko.rsakey",
        "--hidden-import",
        "PIL._tkinter_finder",
        "--hidden-import",
        "cryptography.hazmat.bindings._rust",
    ]

    if console:
        command.append("--console")
    else:
        command.append("--windowed")

    system = platform.system()
    if system == "Windows" and ICON_ICO.is_file():
        command.extend(["--icon", str(ICON_ICO)])
    elif system == "Darwin":
        # PyInstaller converts a PNG icon to a native .icns resource on macOS.
        icon_png = BRAND_DIR / "invent-ssh-mark.png"
        if icon_png.is_file():
            command.extend(["--icon", str(icon_png), "--osx-bundle-identifier", "io.lucasmotta.inventssh"])

    if system != "Darwin":
        command.extend(["--exclude-module", "darkdetect._mac_detect"])
    if system != "Windows":
        command.extend(["--exclude-module", "darkdetect._windows_detect"])

    command.append(str(ENTRY_POINT))
    return command


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build Invent-SSH for the current operating system (Windows, macOS, or Linux)."
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Keep a console attached for diagnostics; normal GUI distributions are windowed.",
    )
    args = parser.parse_args(argv)

    if not ENTRY_POINT.is_file() or not BRAND_DIR.is_dir():
        print("Build failed: app.py or the brand/ resources directory are missing.", file=sys.stderr)
        return 2

    if importlib.util.find_spec("PyInstaller") is None:
        print(
            "PyInstaller is not installed in this Python environment.\n"
            f"Run: {sys.executable} -m pip install -r {REQUIREMENTS_BUILD.name}",
            file=sys.stderr,
        )
        return 2

    try:
        version = read_app_version()
        command = build_command(console=args.console)
        print(f"Building {APP_SLUG} v{version} for {platform.system()} / {platform.machine()}")
        print(f"Build work directory: {ROOT / 'build' / f'pyinstaller-{platform.system().lower()}'}")
        print("Distribution destination: " + str(ROOT / "dist"))
        print("Existing source files and unrelated distributions will not be deleted.")
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode:
            print(f"PyInstaller exited with status {completed.returncode}.", file=sys.stderr)
            return completed.returncode

        print("Build completed. Inspect the dist/ directory for the native executable/app bundle.")
        return 0
    except (OSError, SyntaxError, RuntimeError, ValueError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
