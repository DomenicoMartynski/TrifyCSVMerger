"""Generate the app icon (PNG + .icns + .ico) from code.

Run once (or whenever you want to tweak the look):
    python build/make_icon.py

Produces:  assets/icon.png, assets/icon.icns (macOS), assets/icon.ico (Windows)
Requires Pillow (a build-time dependency only, not needed at runtime).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

SIZE = 1024
BG_TOP = (37, 99, 235)      # accent blue
BG_BOT = (29, 78, 216)      # darker blue
PAGE = (255, 255, 255)
PAGE_EDGE = (219, 234, 254)


def rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def make_png() -> Path:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Vertical gradient tile.
    for y in range(SIZE):
        t = y / SIZE
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

    # Mask to a rounded square (macOS-style squircle-ish).
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE, SIZE], radius=225, fill=255)
    tile = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    tile.paste(img, (0, 0), mask)

    d = ImageDraw.Draw(tile)

    # Two source pages merging into one — a simple, legible "merge" motif.
    def page(x, y, w, h, alpha=255, lines=True):
        edge = (*PAGE_EDGE, alpha)
        body = (*PAGE, alpha)
        d.rounded_rectangle([x, y, x + w, y + h], radius=34, fill=body, outline=edge, width=6)
        if lines:
            for i in range(3):
                ly = y + 70 + i * 78
                d.rounded_rectangle(
                    [x + 60, ly, x + w - 60, ly + 26], radius=13,
                    fill=(191, 219, 254, alpha),
                )

    # Back pages (offset), then the merged front page.
    page(250, 190, 300, 400, alpha=150, lines=False)
    page(470, 250, 300, 400, alpha=200, lines=False)
    page(360, 400, 380, 470, alpha=255, lines=True)

    out = ASSETS / "icon.png"
    tile.save(out)
    return out


def make_icns(png: Path) -> None:
    """macOS: build .icns via iconutil (falls back to sips if needed)."""
    iconset = ASSETS / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    base = Image.open(png)
    specs = [
        (16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
        (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
        (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x"),
    ]
    for px, name in specs:
        base.resize((px, px), Image.LANCZOS).save(iconset / f"icon_{name}.png")
    try:
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "icon.icns")], check=True)
        print("Wrote", ASSETS / "icon.icns")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("iconutil unavailable — skipping .icns (fine on non-macOS build hosts).")
    finally:
        for f in iconset.glob("*.png"):
            f.unlink()
        iconset.rmdir()


def make_ico(png: Path) -> None:
    base = Image.open(png)
    base.save(ASSETS / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Wrote", ASSETS / "icon.ico")


def main() -> None:
    png = make_png()
    print("Wrote", png)
    make_ico(png)
    if sys.platform == "darwin":
        make_icns(png)


if __name__ == "__main__":
    main()
