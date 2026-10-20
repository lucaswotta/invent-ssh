"""Build a native Invenux bundle with PyInstaller on the current OS.

This script deliberately does not install packages, remove old distributions, or
write binaries into the source tree; it only prunes unused Qt files from the
bundle it just built. Install requirements-build.txt explicitly
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
UI_DIR = ROOT / "ui"
# pywebview's Qt backend uses only the widgets-based web engine; the hooks would
# otherwise follow these bindings into hundreds of MB of QML, 3D and charts.
QT_UNUSED_MODULES = (
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtDataVisualization",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtDBus",
)
# Chromium UI strings (context menu) for the app languages; the other 50 locales add 40 MB.
QT_WEBENGINE_LOCALES = ("en-US.pak", "es.pak", "es-419.pak", "pt-BR.pak")
ICON_ICO = BRAND_DIR / "invenux.ico"
ICON_ICNS = BRAND_DIR / "invenux.icns"
APP_SLUG = "invenux"
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
    system = platform.system()
    build_root = ROOT / "build" / f"pyinstaller-{platform.system().lower()}"
    dist_root = ROOT / "dist"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        # A single Windows .exe is the expected download; on Linux and macOS a onefile
        # build would unpack the 300 MB Qt/WebKit runtime to a temp folder on every launch.
        "--onefile" if system == "Windows" else "--onedir",
        "--name",
        f"{APP_SLUG}-v{version}",
        "--distpath",
        str(dist_root),
        "--workpath",
        str(build_root),
        "--specpath",
        str(build_root),
        "--add-data",
        f"{BRAND_DIR}{os.pathsep}brand",
        "--add-data",
        f"{UI_DIR}{os.pathsep}ui",
        "--hidden-import",
        "paramiko.transport",
        "--hidden-import",
        "paramiko.ed25519key",
        "--hidden-import",
        "paramiko.ecdsakey",
        "--hidden-import",
        "paramiko.rsakey",
        "--hidden-import",
        "cryptography.hazmat.bindings._rust",
    ]
    for module in QT_UNUSED_MODULES:
        command.extend(["--exclude-module", module])

    if console:
        command.append("--console")
    else:
        command.append("--windowed")

    if system == "Windows" and ICON_ICO.is_file():
        command.extend(["--icon", str(ICON_ICO)])
    elif system == "Darwin":
        if ICON_ICNS.is_file():
            command.extend(["--icon", str(ICON_ICNS), "--osx-bundle-identifier", "io.lucasmotta.invenux"])

    command.append(str(ENTRY_POINT))
    return command


def prune_qt_resources(dist_root: Path) -> int:
    """Drop Qt files the window never loads: Qt's own translations (no QTranslator is
    installed), extra Chromium locales and the DevTools frontend. Returns bytes freed."""
    freed = 0
    for translations in dist_root.glob("**/PySide6/Qt/translations"):
        for path in translations.rglob("*"):
            unused = path.suffix == ".qm" or (
                path.suffix == ".pak" and path.name not in QT_WEBENGINE_LOCALES
            )
            if path.is_file() and unused:
                freed += path.stat().st_size
                path.unlink()
    for devtools in dist_root.glob("**/PySide6/Qt/resources/qtwebengine_devtools_resources*.pak"):
        freed += devtools.stat().st_size
        devtools.unlink()
    return freed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build Invenux for the current operating system (Windows, macOS, or Linux)."
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Keep a console attached for diagnostics; normal GUI distributions are windowed.",
    )
    args = parser.parse_args(argv)

    if not ENTRY_POINT.is_file() or not BRAND_DIR.is_dir() or not UI_DIR.is_dir():
        print("Build failed: app.py, brand/, or ui/ directory is missing.", file=sys.stderr)
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

        freed = prune_qt_resources(ROOT / "dist" / f"{APP_SLUG}-v{version}")
        if freed:
            print(f"Removed {freed / 1_000_000:.0f} MB of unused Qt translations and DevTools files.")
        print("Build completed. Inspect the dist/ directory for the native executable/app bundle.")
        return 0
    except (OSError, SyntaxError, RuntimeError, ValueError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
