"""Render the brand sources in brand/ into PNG, ICO and ICNS files.

Needs Google Chrome (headless rendering of SVG/HTML with the Inter font) and Pillow.
Run from the repository root: python scripts/render_brand.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "brand"
ICONS = BRAND / "icons"
MEDIA = ROOT / "docs" / "media"
SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
SMALL_SIZES = {16, 24, 32}


def chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(name):
            return name
    sys.exit("Google Chrome or Chromium is required to render the brand assets.")


def render(source: Path, output: Path, width: int, height: int, profile: Path, scale: int = 1) -> None:
    """Screenshot an SVG or HTML file at an exact size with a transparent background."""
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [chrome(), "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
         f"--user-data-dir={profile}", "--default-background-color=00000000", f"--force-device-scale-factor={scale}",
         f"--window-size={width},{height}", f"--screenshot={output}", source.as_uri()],
        check=True, capture_output=True, timeout=120,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp)
        for size in SIZES:
            source = BRAND / ("icon-small.svg" if size in SMALL_SIZES else "icon.svg")
            render(source, ICONS / f"invenux-{size}.png", size, size, profile)
        images = {size: Image.open(ICONS / f"invenux-{size}.png").convert("RGBA") for size in SIZES}
        images[256].save(
            BRAND / "invenux.ico",
            sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)],
            append_images=[images[size] for size in (16, 24, 32, 48, 64, 128)],
        )
        images[1024].save(BRAND / "invenux.icns")
        for theme in ("dark", "light"):
            render(BRAND / f"wordmark-{theme}.html", MEDIA / f"wordmark-{theme}.png", 760, 200, profile, scale=2)
        render(BRAND / "social-preview.html", BRAND / "social-preview.png", 1280, 640, profile)
    print("Rendered icons, wordmarks and the social preview.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
