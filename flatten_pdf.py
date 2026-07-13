#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pymupdf>=1.24", "pillow>=10"]
# ///
"""Flatten a PDF by rasterizing every page and rebuilding the document.

This destroys ALL non-visual content: text layers, fonts, annotations,
attachments, scripts, metadata. Anything visually hidden (e.g. text behind
redaction boxes) cannot survive, because the output PDF is built solely
from rendered page images.

Each page is encoded both as lossless PNG (tiny for text pages with solid
redaction boxes) and JPEG (better for scans/photos); the smaller wins.
Pages without color content are stored grayscale.

Usage:
    ./flatten_pdf.py input.pdf                  # writes input.flattened.pdf
    ./flatten_pdf.py input.pdf -o out.pdf
    ./flatten_pdf.py input.pdf --dpi 300 --quality 70
    ./flatten_pdf.py input.pdf --bw             # 1-bit output, smallest
"""

import argparse
import io
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageChops

# Max channel difference below which a page counts as grayscale (tolerates
# slight colored fringing from subpixel-style rendering).
GRAY_TOLERANCE = 8
BW_THRESHOLD = 160


def encode_page(pix: pymupdf.Pixmap, quality: int, bw: bool) -> tuple[bytes, str]:
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    r, g, b = img.split()
    is_gray = (ImageChops.difference(r, g).getextrema()[1] <= GRAY_TOLERANCE
               and ImageChops.difference(g, b).getextrema()[1] <= GRAY_TOLERANCE)
    if is_gray:
        img = img.convert("L")

    if bw:
        mono = img.convert("L").point(lambda p: 255 if p > BW_THRESHOLD else 0)
        buf = io.BytesIO()
        mono.convert("1").save(buf, "PNG", optimize=True)
        return buf.getvalue(), "1-bit png"

    png_buf, jpg_buf = io.BytesIO(), io.BytesIO()
    img.save(png_buf, "PNG", optimize=True)
    img.save(jpg_buf, "JPEG", quality=quality)
    mode = "gray" if is_gray else "rgb"
    if len(png_buf.getvalue()) <= len(jpg_buf.getvalue()):
        return png_buf.getvalue(), f"{mode} png"
    return jpg_buf.getvalue(), f"{mode} jpeg"


def flatten(in_path: Path, out_path: Path, dpi: int, quality: int, bw: bool) -> None:
    src = pymupdf.open(in_path)
    out = pymupdf.open()

    for i, page in enumerate(src, start=1):
        pix = page.get_pixmap(dpi=dpi, annots=True)
        data, kind = encode_page(pix, quality, bw)
        # Page size in points, derived from the rendered image so that
        # rotation and cropping are baked in exactly as displayed.
        w, h = pix.width * 72 / dpi, pix.height * 72 / dpi
        new_page = out.new_page(width=w, height=h)
        new_page.insert_image(new_page.rect, stream=data)
        print(f"  page {i}/{src.page_count}: {dpi} dpi, {kind}, "
              f"{len(data) / 1024:.0f} KB", file=sys.stderr)

    src.close()
    out.set_metadata({})  # ensure no metadata carries over
    out.save(out_path, garbage=4, deflate=True)
    out.close()


def verify(out_path: Path) -> bool:
    """Confirm the output contains no extractable text on any page."""
    doc = pymupdf.open(out_path)
    leaked = [i for i, page in enumerate(doc, start=1) if page.get_text().strip()]
    doc.close()
    if leaked:
        print(f"WARNING: extractable text found on page(s) {leaked}!", file=sys.stderr)
        return False
    print("Verified: no extractable text in output.", file=sys.stderr)
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", type=Path, help="input PDF")
    ap.add_argument("-o", "--output", type=Path, default=None,
                    help="output PDF (default: <input>.flattened.pdf)")
    ap.add_argument("--dpi", type=int, default=600,
                    help="render resolution (default: 600)")
    ap.add_argument("--quality", type=int, default=85,
                    help="JPEG quality 1-100, used when JPEG beats PNG (default: 85)")
    ap.add_argument("--bw", action="store_true",
                    help="threshold to 1-bit black & white (smallest output; "
                         "only for pure text/line-art documents)")
    args = ap.parse_args()

    out_path = args.output or args.input.with_suffix(".flattened.pdf")
    if out_path.resolve() == args.input.resolve():
        sys.exit("error: output would overwrite input")

    flatten(args.input, out_path, args.dpi, args.quality, args.bw)
    ok = verify(out_path)
    print(out_path)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
