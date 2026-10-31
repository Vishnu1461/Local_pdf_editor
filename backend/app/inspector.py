"""Low-level page inspection.

All geometry is returned in canonical page space: origin at the cropbox
top-left corner, y grows downwards, units are PDF points. PyMuPDF reports
text and drawing coordinates in this unrotated space even for rotated
pages (page.rect reports the rotated width/height, which is why the
cropbox -- not page.rect -- defines the canonical size).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

from .geometry import Rect, dedupe, make_rect

NEAR_WHITE = 0.95


@dataclass
class Word:
    rect: Rect
    text: str


@dataclass
class PagePrimitives:
    index: int
    width: float
    height: float
    rotation: int
    words: list[Word] = field(default_factory=list)
    white_rects: list[Rect] = field(default_factory=list)
    small_squares: list[Rect] = field(default_factory=list)
    horizontal_lines: list[tuple[float, float, float]] = field(default_factory=list)
    underscore_runs: list[Rect] = field(default_factory=list)
    images: list[Rect] = field(default_factory=list)

    def words_inside(self, rect: Rect) -> list[Word]:
        x0, y0, x1, y1 = rect
        out = []
        for w in self.words:
            cx = (w.rect[0] + w.rect[2]) / 2
            cy = (w.rect[1] + w.rect[3]) / 2
            if x0 - 0.5 <= cx <= x1 + 0.5 and y0 - 0.5 <= cy <= y1 + 0.5:
                out.append(w)
        return out


def canonical_size(page: pymupdf.Page) -> tuple[float, float]:
    crop = page.cropbox
    return crop.width, crop.height


def _is_near_white(color) -> bool:
    return color is not None and len(color) == 3 and min(color) >= NEAR_WHITE


def _is_strong_fill(color) -> bool:
    return color is not None and len(color) == 3 and max(color) < 0.6


def inspect_page(page: pymupdf.Page, index: int) -> PagePrimitives:
    width, height = canonical_size(page)
    prims = PagePrimitives(index=index, width=width, height=height, rotation=page.rotation)

    for w in page.get_text("words"):
        text = w[4].strip()
        if text:
            prims.words.append(Word(rect=(float(w[0]), float(w[1]), float(w[2]), float(w[3])), text=text))

    white: list[Rect] = []
    squares: list[Rect] = []
    h_segments: list[tuple[float, float, float]] = []

    for drawing in page.get_drawings():
        fill = drawing.get("fill")
        near_white = _is_near_white(fill)
        for item in drawing["items"]:
            kind = item[0]
            if kind == "re":
                r = item[1]
                rect = (float(r.x0), float(r.y0), float(r.x1), float(r.y1))
                w = rect[2] - rect[0]
                h = rect[3] - rect[1]
                if near_white:
                    if w >= 18 and h >= 6:
                        white.append(rect)
                    if 3.5 <= w <= 12 and 3.5 <= h <= 12 and abs(w - h) <= 1.5:
                        squares.append(rect)
                if h <= 2.2 and w >= 12:
                    h_segments.append(((rect[1] + rect[3]) / 2, rect[0], rect[2]))
            elif kind == "l":
                p1, p2 = item[1], item[2]
                if abs(p1.y - p2.y) <= 0.6 and abs(p1.x - p2.x) >= 12:
                    h_segments.append(((p1.y + p2.y) / 2, min(p1.x, p2.x), max(p1.x, p2.x)))

    for img in page.get_images(full=True):
        try:
            b = page.get_image_bbox(img)
            prims.images.append((float(b.x0), float(b.y0), float(b.x1), float(b.y1)))
        except ValueError:
            continue

    prims.white_rects = dedupe(white)
    prims.small_squares = dedupe(squares, threshold=0.6)
    prims.horizontal_lines = _merge_horizontal(h_segments)
    prims.underscore_runs = _extract_underscore_runs(page)
    return prims


def _extract_underscore_runs(page: pymupdf.Page) -> list[Rect]:
    """Runs of '_' characters are the blank lines printed inside sentences."""
    runs: list[Rect] = []
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            current: list[float] | None = None
            count = 0
            for span in line["spans"]:
                for ch in span["chars"]:
                    x0, y0, x1, y1 = ch["bbox"]
                    if ch["c"] == "_":
                        count += 1
                        if current is None:
                            current = [x0, y0, x1, y1]
                        else:
                            current[2] = max(current[2], x1)
                            current[1] = min(current[1], y0)
                            current[3] = max(current[3], y1)
                    else:
                        if current is not None and count >= 4:
                            runs.append(tuple(current))  # type: ignore[arg-type]
                        current, count = None, 0
            if current is not None and count >= 4:
                runs.append(tuple(current))  # type: ignore[arg-type]
    return dedupe(runs, threshold=0.5)


def _merge_horizontal(segments: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    ordered = sorted(segments, key=lambda s: (round(s[0], 1), s[1]))
    merged: list[list[float]] = []
    for y, x0, x1 in ordered:
        if merged and abs(merged[-1][0] - y) <= 1.0 and x0 <= merged[-1][2] + 2.5:
            merged[-1][2] = max(merged[-1][2], x1)
        else:
            merged.append([y, x0, x1])
    return [(m[0], m[1], m[2]) for m in merged]
