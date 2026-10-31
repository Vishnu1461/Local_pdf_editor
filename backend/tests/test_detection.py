from __future__ import annotations

import pymupdf
import pytest

from app import detection
from app.inspector import inspect_page

BACKGROUND = (0.78, 0.918, 0.986)


def synthetic_page():
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.draw_rect(pymupdf.Rect(0, 0, 400, 300), color=None, fill=BACKGROUND)
    page.insert_text((20, 58), "First Name", fontsize=8)
    page.draw_rect(pymupdf.Rect(90, 45, 250, 59), color=None, fill=(1, 1, 1))
    page.insert_text((20, 83), "Date of Birth", fontsize=8)
    page.draw_rect(pymupdf.Rect(90, 70, 250, 84), color=None, fill=(1, 1, 1))
    page.insert_text((98, 81), "D D M M Y Y Y Y", fontsize=7)
    page.insert_text((20, 110), "Yes", fontsize=8)
    page.draw_rect(pymupdf.Rect(90, 100, 98, 108), color=None, fill=(1, 1, 1))
    page.insert_text((20, 140), "Nominee Name ______________", fontsize=8)
    page.draw_rect(pymupdf.Rect(90, 160, 180, 240), color=None, fill=(1, 1, 1))
    page.insert_text((100, 230), "Photograph", fontsize=7)
    return doc, page


def test_detects_labelled_box_as_date():
    doc, page = synthetic_page()
    fields = detection.detect_page(inspect_page(page, 0))
    dates = [f for f in fields if f.type == "date"]
    assert dates, [f.label for f in fields]
    assert any(abs(f.rect[1] - 70) <= 1.5 and f.rect[2] >= 245 for f in dates)
    assert "date" in (dates[0].label + " date of birth").lower()
    doc.close()


def test_detects_checkbox_next_to_its_label():
    doc, page = synthetic_page()
    fields = detection.detect_page(inspect_page(page, 0))
    boxes = [f for f in fields if f.type == "checkbox"]
    assert len(boxes) == 1
    assert boxes[0].label.lower().startswith("yes")
    assert boxes[0].rect[0] == pytest.approx(90, abs=1)
    doc.close()


def test_detects_underscore_run_as_transparent_field():
    doc, page = synthetic_page()
    fields = detection.detect_page(inspect_page(page, 0))
    nominee = [f for f in fields if "nominee" in f.label.lower()]
    assert nominee, [f.label for f in fields]
    assert nominee[0].background == "none"
    doc.close()


def test_detects_captioned_photo_box_as_image():
    doc, page = synthetic_page()
    fields = detection.detect_page(inspect_page(page, 0))
    images = [f for f in fields if f.type == "image"]
    assert images, [(f.type, f.label) for f in fields]
    assert images[0].label.lower().startswith("photograph")
    doc.close()
