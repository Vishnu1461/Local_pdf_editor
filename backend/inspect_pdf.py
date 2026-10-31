"""Inspect a PDF's pages, words, drawings and widgets. Not part of the app.

Usage: python inspect_pdf.py <file.pdf>
"""
import sys

import pymupdf

if len(sys.argv) < 2:
    raise SystemExit("usage: python inspect_pdf.py <file.pdf>")

doc = pymupdf.open(sys.argv[1])

print(f"pages={doc.page_count} is_form={doc.is_form_pdf} encrypted={doc.is_encrypted} metadata={doc.metadata.get('producer')}")
for i, page in enumerate(doc):
    r = page.rect
    print(f"\n=== PAGE {i+1} rot={page.rotation} media={page.mediabox} crop={page.cropbox} rect={r} ===")
    print(f"images={len(page.get_images(full=True))} draws={len(page.get_drawings())} widgets={len(list(page.widgets()))}")
    words = page.get_text("words")
    print(f"words={len(words)} blocks={len(page.get_text('blocks'))}")
    # Print text lines with coordinates
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            spans = line["spans"]
            text = "".join(s["text"] for s in spans)
            if not text.strip():
                continue
            x0, y0, x1, y1 = line["bbox"]
            font = spans[0]["font"]
            size = spans[0]["size"]
            print(f"  L ({x0:7.2f},{y0:7.2f},{x1:7.2f},{y1:7.2f}) sz={size:4.1f} {font[:22]:22s} | {text[:110]}")
