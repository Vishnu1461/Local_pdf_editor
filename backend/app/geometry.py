from __future__ import annotations

Rect = tuple[float, float, float, float]


def make_rect(x0: float, y0: float, x1: float, y1: float) -> Rect:
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def width(r: Rect) -> float:
    return r[2] - r[0]


def height(r: Rect) -> float:
    return r[3] - r[1]


def area(r: Rect) -> float:
    return width(r) * height(r)


def center(r: Rect) -> tuple[float, float]:
    return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)


def intersection(a: Rect, b: Rect) -> Rect | None:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def iou(a: Rect, b: Rect) -> float:
    inter = intersection(a, b)
    if inter is None:
        return 0.0
    union = area(a) + area(b) - area(inter)
    return area(inter) / union if union else 0.0


def contains_point(r: Rect, x: float, y: float) -> bool:
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def contains_rect(outer: Rect, inner: Rect) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def overlap_ratio(inner: Rect, outer: Rect) -> float:
    inter = intersection(inner, outer)
    if inter is None:
        return 0.0
    a = area(inner)
    return area(inter) / a if a else 0.0


def dedupe(rects: list[Rect], threshold: float = 0.85) -> list[Rect]:
    """Remove near-duplicate rectangles, keeping the largest of each cluster."""
    ordered = sorted(rects, key=area, reverse=True)
    kept: list[Rect] = []
    for r in ordered:
        if any(iou(r, k) >= threshold for k in kept):
            continue
        kept.append(r)
    return kept


def expand(r: Rect, dx: float, dy: float | None = None) -> Rect:
    dy = dx if dy is None else dy
    return (r[0] - dx, r[1] - dy, r[2] + dx, r[3] + dy)


def clamp_rect(r: Rect, page_w: float, page_h: float) -> Rect:
    return (
        max(0.0, min(r[0], page_w)),
        max(0.0, min(r[1], page_h)),
        max(0.0, min(r[2], page_w)),
        max(0.0, min(r[3], page_h)),
    )
