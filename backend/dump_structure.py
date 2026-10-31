"""Dump per-page words, vector drawings and images to JSON for analysis."""
import json
import sys

import pymupdf

src = sys.argv[1]
out = sys.argv[2]

doc = pymupdf.open(src)
data = {
    "page_count": doc.page_count,
    "pages": [],
}

for i, page in enumerate(doc):
    words = [
        {"x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3], "text": w[4], "block": w[5], "line": w[6], "wn": w[7]}
        for w in page.get_text("words")
    ]
    drawings = []
    for d in page.get_drawings():
        items = []
        for it in d["items"]:
            if it[0] == "re":
                items.append({"t": "re", "r": [it[1].x0, it[1].y0, it[1].x1, it[1].y1]})
            elif it[0] == "l":
                items.append({"t": "l", "p1": [it[1].x, it[1].y], "p2": [it[2].x, it[2].y]})
            elif it[0] == "qu":
                items.append({"t": "qu", "q": [it[1].ul.x, it[1].ul.y, it[1].ur.x, it[1].ur.y, it[1].lr.x, it[1].lr.y, it[1].ll.x, it[1].ll.y]})
        drawings.append({
            "rect": [d["rect"].x0, d["rect"].y0, d["rect"].x1, d["rect"].y1],
            "type": d["type"],
            "width": d.get("width"),
            "color": d.get("color"),
            "fill": d.get("fill"),
            "items": items,
        })
    data["pages"].append({
        "index": i,
        "rotation": page.rotation,
        "mediabox": list(page.mediabox),
        "cropbox": list(page.cropbox),
        "words": words,
        "drawings": drawings,
        "images": [{"xref": im[0], "bbox": list(page.get_image_bbox(im))} for im in page.get_images(full=True)],
    })

with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f)
print("written", out, "pages", data["page_count"],
      "zeros", [len(p["words"]) for p in data["pages"]],
      "draws", [len(p["drawings"]) for p in data["pages"]])
