"""Geometric field detection.

Detection proposes fields; it never commits them. Every candidate carries
a confidence score and its evidence (label, placeholder, geometry), and
low-confidence geometry is dropped rather than guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .geometry import Rect, clamp_rect, height, width
from .inspector import PagePrimitives, Word
from .models import FieldSpec

PLACEHOLDER_PHRASES = {
    "INCAPITAL",
    "INCAPITALLETTERS",
    "INCAPITALLETTERSONLY",
    "NUMBER",
    "EXTN",
    "DDMMYYYY",
    "DDMMYY",
    "MDDYYYY",
    "YYYYMMDD",
    "DMY",
    "HHMM",
    "HMM",
}

DATE_HINTS = (
    "date",
    "dob",
    "d.o.b",
    "birth",
    "expiry",
    "expires",
    "expiration",
    "valid till",
    "valid upto",
    "issued on",
    "incorporation",
    "date of",
)
EMAIL_HINTS = ("e-mail", "email", "e mail")
PHONE_HINTS = ("mobile", "phone", "tel", "contact no", "cell")
NUMBER_HINTS = ("amount", "income", "salary", "gross", "annual", "number of", "count")
ADDRESS_HINTS = (
    "address",
    "flat",
    "bldg",
    "building",
    "landmark",
    "city",
    "state",
    "country",
    "pin",
    "postal",
    "zip",
    "street",
    "road",
    "village",
    "district",
)
SIGNATURE_HINTS = ("signature", "signed", "sign")
IMAGE_HINTS = ("photo", "photograph", "image", "portrait", "passport size")


def normalise(text: str) -> str:
    return re.sub(r"\s+", "", text).upper()


def is_placeholder_text(text: str) -> bool:
    compact = normalise(text)
    if not compact:
        return False
    if compact in PLACEHOLDER_PHRASES:
        return True
    # e.g. "D D M M Y Y Y Y", "H H M M", "1- 2-"
    if all(c in "DMYHI0123456789-/:.#" for c in compact):
        return True
    return False


def is_substantive(text: str) -> bool:
    if is_placeholder_text(text):
        return False
    letters = re.sub(r"[^A-Za-z]", "", text)
    return len(letters) >= 2


def clean_label(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip(" :;.,-*^#%")
    return text.strip()


def _line_words(words: list[Word], y_center: float, tolerance: float = 3.5) -> list[Word]:
    return [w for w in words if abs((w.rect[1] + w.rect[3]) / 2 - y_center) <= tolerance]


def find_left_label(rect: Rect, words: list[Word], max_gap: float = 340) -> str:
    cy = (rect[1] + rect[3]) / 2
    candidates = [w for w in words if w.rect[2] <= rect[0] + 1.5 and rect[0] - w.rect[2] <= max_gap]
    if not candidates:
        return ""
    # Centre within the field's vertical span, or close to it.
    near = [w for w in candidates if rect[1] - 4 <= (w.rect[1] + w.rect[3]) / 2 <= rect[3] + 4]
    if not near:
        return ""
    y = min(near, key=lambda w: abs((w.rect[1] + w.rect[3]) / 2 - cy))
    row = [w for w in near if abs((w.rect[1] + w.rect[3]) / 2 - (y.rect[1] + y.rect[3]) / 2) <= 2.5]
    row.sort(key=lambda w: w.rect[0], reverse=True)
    chunk: list[Word] = []
    cursor = rect[0]
    for w in row:
        if cursor - w.rect[2] > 13 and chunk:
            break
        chunk.append(w)
        cursor = w.rect[0]
        if len(chunk) >= 8:
            break
    chunk.reverse()
    label = clean_label(" ".join(w.text for w in chunk))
    return "" if is_placeholder_text(label) else label


def find_above_label(rect: Rect, words: list[Word], max_gap: float = 16) -> str:
    candidates = [
        w
        for w in words
        if rect[1] - max_gap <= w.rect[3] <= rect[1] + 2.5 and w.rect[2] > rect[0] and w.rect[0] < rect[2]
    ]
    if not candidates:
        return ""
    baseline = max(w.rect[3] for w in candidates)
    row = [w for w in candidates if baseline - w.rect[3] <= 3.0]
    row.sort(key=lambda w: w.rect[0])
    label = clean_label(" ".join(w.text for w in row[:10]))
    return "" if is_placeholder_text(label) else label


def find_right_label(rect: Rect, words: list[Word], max_gap: float = 190) -> str:
    near = [
        w
        for w in words
        if w.rect[0] >= rect[2] - 1.5
        and w.rect[0] - rect[2] <= max_gap
        and rect[1] - 4 <= (w.rect[1] + w.rect[3]) / 2 <= rect[3] + 4
    ]
    if not near:
        return ""
    y = min(near, key=lambda w: abs((w.rect[1] + w.rect[3]) / 2 - (rect[1] + rect[3]) / 2))
    row = [w for w in near if abs((w.rect[1] + w.rect[3]) / 2 - (y.rect[1] + y.rect[3]) / 2) <= 2.5]
    row.sort(key=lambda w: w.rect[0])
    chunk: list[Word] = []
    cursor = rect[2]
    for w in row:
        if w.rect[0] - cursor > 14 and chunk:
            break
        chunk.append(w)
        cursor = w.rect[2]
        if len(chunk) >= 6:
            break
    label = clean_label(" ".join(w.text for w in chunk))
    return "" if is_placeholder_text(label) else label


def classify(label: str, placeholder: str, w: float, h: float) -> tuple[str, float]:
    text = f"{label} {placeholder}".lower()
    bonus = 0.0
    if any(k in text for k in IMAGE_HINTS) and w >= 35 and h >= 25 and w / max(h, 1) < 3.2:
        return "image", 0.15
    if any(k in text for k in SIGNATURE_HINTS) and w >= 50 and w / max(h, 1) >= 2.0:
        return "signature", 0.15
    if any(k in text for k in SIGNATURE_HINTS) and h >= 25:
        return "signature", 0.15
    if any(k in text for k in DATE_HINTS) or "DDMMYYYY" in normalise(placeholder):
        return "date", 0.1
    if any(k in text for k in EMAIL_HINTS):
        return "email", 0.1
    if any(k in text for k in PHONE_HINTS):
        return "number", 0.05
    if any(k in text for k in ADDRESS_HINTS):
        return ("multiline", 0.05) if h >= 24 else ("address", 0.05)
    if any(k in text for k in NUMBER_HINTS):
        return "number", 0.0
    if h >= 28:
        return "multiline", 0.0
    return "text", bonus


@dataclass
class Candidate:
    rect: Rect
    kind: str  # box | checkbox | underline | image
    label: str
    placeholder: str = ""
    confidence: float = 0.0
    field_type: str = "text"


def _box_candidates(prims: PagePrimitives) -> list[Candidate]:
    out: list[Candidate] = []
    for rect in prims.white_rects:
        w, h = width(rect), height(rect)
        if w < 18 or w > prims.width * 0.97:
            continue
        if h < 9 or h > 170:
            continue
        inside = prims.words_inside(rect)
        texts = [wd.text for wd in inside]
        substantive = [t for t in texts if is_substantive(t)]
        placeholder = " ".join(texts)
        caption_label = ""
        if substantive:
            # Large photo/signature areas carry a printed caption inside the
            # box. Keep them only when the box is tall and the text is sparse.
            coverage = sum((wd.rect[2] - wd.rect[0]) * (wd.rect[3] - wd.rect[1]) for wd in inside)
            sparse = coverage / max(1.0, w * h) < 0.45
            caption = " ".join(texts).lower()
            if not (h >= 24 and sparse and any(k in caption for k in IMAGE_HINTS + SIGNATURE_HINTS)):
                continue
            caption_label = clean_label(" ".join(texts))[:80]
        label = find_left_label(rect, prims.words) or find_above_label(rect, prims.words)
        label = label or caption_label
        ftype, delta = classify(label, placeholder, w, h)
        if h > 120 and ftype not in ("image", "signature", "multiline"):
            continue
        confidence = 0.35
        if label:
            confidence += 0.22
        if placeholder and is_placeholder_text(placeholder):
            confidence += 0.18
        if 10 <= h <= 20:
            confidence += 0.08
        if w >= 45:
            confidence += 0.05
        confidence = min(0.97, confidence + delta)
        if not label and not placeholder:
            # Bare empty white rectangle with no evidence: too weak to propose.
            confidence -= 0.25
        if confidence < 0.45:
            continue
        out.append(Candidate(rect, "box", label, placeholder, confidence, ftype))
    return out


def _checkbox_candidates(prims: PagePrimitives) -> list[Candidate]:
    """Checkbox labels run from the box to the next box (or a wide gap)."""
    out: list[Candidate] = []
    squares = sorted(prims.small_squares, key=lambda r: (round((r[1] + r[3]) / 2, 0), r[0]))
    for rect in squares:
        cy = (rect[1] + rect[3]) / 2
        row = [s for s in squares if abs((s[1] + s[3]) / 2 - cy) <= 2.5 and s[0] > rect[2] - 1]
        boundary = min((s[0] for s in row), default=rect[2] + 95)
        boundary = min(boundary, rect[2] + 200)
        words = [
            w
            for w in prims.words
            if w.rect[0] >= rect[2] - 1.5
            and w.rect[2] <= boundary - 0.5
            and abs((w.rect[1] + w.rect[3]) / 2 - cy) <= 3.0
        ]
        words.sort(key=lambda w: w.rect[0])
        chunk: list[Word] = []
        cursor = rect[2]
        for w in words:
            if w.rect[0] - cursor > 13 and chunk:
                break
            chunk.append(w)
            cursor = w.rect[2]
            if len(chunk) >= 7:
                break
        label = clean_label(" ".join(w.text.replace("_", " ") for w in chunk))
        if not label or not is_substantive(label):
            label = find_left_label(rect, prims.words, max_gap=90)
        if not label or not is_substantive(label):
            continue
        out.append(Candidate(rect, "checkbox", label, "", 0.72, "checkbox"))
    return out


def _underline_candidates(prims: PagePrimitives) -> list[Candidate]:
    out: list[Candidate] = []
    for y, x0, x1 in prims.horizontal_lines:
        length = x1 - x0
        if length < 26 or length > prims.width * 0.92:
            continue
        # Text sitting on the line means it is a table border under a row of
        # text, not a blank to write on.
        above = [
            w
            for w in prims.words
            if w.rect[0] < x1
            and w.rect[2] > x0
            and y - 9.5 <= (w.rect[1] + w.rect[3]) / 2 <= y - 0.5
            and is_substantive(w.text)
        ]
        if above:
            continue
        label_words = [
            w
            for w in prims.words
            if w.rect[2] <= x0 + 2.5
            and x0 - w.rect[2] <= 170
            and abs((w.rect[1] + w.rect[3]) / 2 - (y - 6)) <= 8
            and is_substantive(w.text)
        ]
        if not label_words:
            continue
        label_words.sort(key=lambda w: w.rect[0], reverse=True)
        chunk: list[Word] = []
        cursor = x0
        for w in label_words:
            if cursor - w.rect[2] > 40 and chunk:
                break
            chunk.append(w)
            cursor = w.rect[0]
            if len(chunk) >= 8:
                break
        chunk.reverse()
        label = clean_label(" ".join(w.text for w in chunk))
        if is_placeholder_text(label):
            continue
        start = max(x0, chunk[-1].rect[2] + 3) if chunk else x0
        if x1 - start < 24:
            continue
        rect = (start, y - 12.5, x1, y - 1.0)
        ftype, delta = classify(label, "", width(rect), height(rect))
        out.append(Candidate(rect, "underline", label, "", min(0.9, 0.5 + delta + 0.08), ftype))
    return out


def _underscore_candidates(prims: PagePrimitives) -> list[Candidate]:
    out: list[Candidate] = []
    for run in prims.underscore_runs:
        x0, y0, x1, y1 = run
        if x1 - x0 < 22:
            continue
        cy = (y0 + y1) / 2
        left = [
            w
            for w in prims.words
            if w.rect[2] <= x0 + 1.5 and x0 - w.rect[2] <= 190 and abs((w.rect[1] + w.rect[3]) / 2 - cy) <= 5
        ]
        left.sort(key=lambda w: w.rect[0], reverse=True)
        chunk: list[Word] = []
        cursor = x0
        for w in left:
            if cursor - w.rect[2] > 22 and chunk:
                break
            chunk.append(w)
            cursor = w.rect[0]
            if len(chunk) >= 8:
                break
        chunk.reverse()
        label = clean_label(" ".join(w.text.replace("_", "") for w in chunk))
        if not is_substantive(label):
            continue
        top = y0 - 1.0
        bottom = max(y1 + 1.5, top + 9.0)
        rect = (x0, top, x1, bottom)
        ftype, delta = classify(label, "", x1 - x0, bottom - top)
        out.append(Candidate(rect, "underscore", label, "", min(0.92, 0.62 + delta), ftype))
    return out


def detect_page(prims: PagePrimitives) -> list[FieldSpec]:
    candidates = (
        _box_candidates(prims)
        + _checkbox_candidates(prims)
        + _underline_candidates(prims)
        + _underscore_candidates(prims)
    )
    candidates.sort(key=lambda c: (round(c.rect[1], 1), c.rect[0]))

    fields: list[FieldSpec] = []
    used_names: set[str] = set()
    for idx, cand in enumerate(candidates):
        rect = clamp_rect(cand.rect, prims.width, prims.height)
        if width(rect) < 4 or height(rect) < 4:
            continue
        label = cand.label
        base = _slug(label) or cand.kind
        name = base
        n = 2
        while name in used_names:
            name = f"{base}_{n}"
            n += 1
        used_names.add(name)

        font_size = 0
        if height(rect) <= 22:
            font_size = _fit_font_size(height(rect))
        fields.append(
            FieldSpec(
                id=f"p{prims.index}_{idx}",
                page=prims.index,
                rect=[round(v, 2) for v in rect],
                type=cand.field_type,  # type: ignore[arg-type]
                name=name,
                label=label,
                fontSize=font_size,
                background="none" if cand.kind in ("underline", "underscore") else "white",
                confidence=round(cand.confidence, 2),
                source="detected",
                tooltip=label[:120],
            )
        )
    return fields


def _fit_font_size(box_height: float) -> float:
    size = max(5.0, min(10.0, box_height * 0.62))
    return round(size, 1)


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:48]
