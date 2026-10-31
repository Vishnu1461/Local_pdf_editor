from __future__ import annotations

import pymupdf

from app import acroform
from app.models import FieldSpec

BACKGROUND = (0.78, 0.918, 0.986)


def make_document(path):
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.draw_rect(pymupdf.Rect(0, 0, 400, 300), color=None, fill=BACKGROUND)
    doc.save(path)
    doc.close()


def fields() -> list[FieldSpec]:
    return [
        FieldSpec(page=0, rect=[40, 40, 200, 54], name="first_name", label="First Name", value="JOHN", fontSize=8),
        FieldSpec(page=0, rect=[40, 60, 200, 90], name="address", label="Address", type="multiline", value="1 MAIN ST"),
        FieldSpec(page=0, rect=[40, 100, 52, 112], name="agree", label="Agree", type="checkbox", checked=True),
        FieldSpec(page=0, rect=[40, 130, 52, 142], name="gender_m", label="Male", type="radio", group="gender", value="M", checked=True),
        FieldSpec(page=0, rect=[70, 130, 82, 142], name="gender_f", label="Female", type="radio", group="gender", value="F"),
        FieldSpec(page=0, rect=[40, 160, 200, 174], name="dob", label="Date of Birth", type="date", value="01/02/1990", maxLength=10),
        FieldSpec(page=0, rect=[40, 190, 200, 210], name="photo", label="Photo", type="image", background="none"),
        FieldSpec(page=0, rect=[40, 230, 200, 250], name="sign", label="Signature", type="signature"),
        FieldSpec(page=0, rect=[40, 265, 200, 279], name="dept", label="Department", type="dropdown", options=["Sales", "Ops"], value="Ops"),
    ]


def test_save_creates_verified_widgets(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "filled.pdf"
    make_document(src)

    result = acroform.save(str(src), str(out), fields())
    assert result["pages"] == 1
    assert result["mismatches"] == []
    assert result["widgetCount"] == 9  # 7 single widgets + one radio group of two

    doc = pymupdf.open(out)
    page = doc[0]
    widgets = list(page.widgets())
    assert len(widgets) == 9
    by_name = {w.field_name: w for w in widgets}
    assert by_name["first_name"].field_value == "JOHN"
    assert by_name["first_name"].rect == pymupdf.Rect(40, 40, 200, 54)
    assert by_name["address"].field_flags & acroform.FLAG_MULTILINE
    assert by_name["agree"].field_value == "Yes"
    assert any(w.field_value == "M" for w in widgets if w.field_name == "gender")
    assert by_name["dob"].text_maxlen == 10
    assert by_name["dept"].field_value == "Ops"
    doc.close()


def test_image_button_keeps_placeholder_transparent(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "filled.pdf"
    make_document(src)
    acroform.save(str(src), str(out), fields())

    doc = pymupdf.open(out)
    widget = next(w for w in doc[0].widgets() if w.field_name == "photo")
    assert widget.field_type_string == "Button"
    assert not widget.button_caption
    kind, value = doc.xref_get_key(widget.xref, "AP")
    assert kind == "null"
    doc.close()


def test_signature_has_no_default_appearance(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "filled.pdf"
    make_document(src)
    acroform.save(str(src), str(out), fields())

    doc = pymupdf.open(out)
    widget = next(w for w in doc[0].widgets() if w.field_name == "sign")
    kind, _ = doc.xref_get_key(widget.xref, "AP")
    assert kind == "null"
    doc.close()


def test_flatten_bakes_values_into_page_content(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "flat.pdf"
    make_document(src)
    result = acroform.save(str(src), str(out), fields(), flatten=True)
    assert result["widgetCount"] == 0
    assert result["warnings"] == []

    doc = pymupdf.open(out)
    assert not any(True for page in doc for _ in page.widgets())
    text = doc[0].get_text()
    assert "JOHN" in text
    assert "01/02/1990" in text
    doc.close()


def test_verify_reports_position_mismatch(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "filled.pdf"
    make_document(src)
    specs = fields()
    acroform.save(str(src), str(out), specs)
    specs[0] = specs[0].model_copy(update={"rect": [60, 40, 220, 54]})
    report = acroform.verify(str(out), specs)
    assert any("first_name" in m for m in report["mismatches"])


def test_extract_existing_round_trips_checked_state(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "filled.pdf"
    make_document(src)
    acroform.save(str(src), str(out), fields())

    existing = {entry["name"]: entry for entry in acroform.extract_existing(str(out))}
    assert existing["agree"]["type"] == "checkbox"
    assert existing["agree"]["checked"] is True
    assert existing["agree"]["value"] is True
    assert existing["gender"]["checked"] is True
    assert existing["gender"]["value"] == "M"
    assert existing["photo"]["type"] == "image"
    assert existing["first_name"]["value"] == "JOHN"


PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_image_value_is_embedded_as_page_content(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "filled.pdf"
    make_document(src)
    specs = [
        FieldSpec(page=0, rect=[40, 190, 200, 210], name="photo", type="image", background="none"),
        FieldSpec(page=0, rect=[40, 220, 200, 240], name="sig_image", type="image", value=PNG_1PX),
    ]
    acroform.save(str(src), str(out), specs)

    doc = pymupdf.open(out)
    assert len(doc[0].get_images(full=True)) == 1
    widget = next(w for w in doc[0].widgets() if w.field_name == "sig_image")
    assert doc.xref_get_key(widget.xref, "AP")[0] == "null"
    doc.close()


def test_rejects_non_image_data_url(tmp_path):
    src = tmp_path / "blank.pdf"
    out = tmp_path / "filled.pdf"
    make_document(src)
    specs = [
        FieldSpec(page=0, rect=[40, 190, 200, 210], name="photo", type="image", value="data:text/html;base64,PGgxPg=="),
    ]
    result = acroform.save(str(src), str(out), specs)
    assert any("photo" in warning for warning in result["warnings"])
    doc = pymupdf.open(out)
    assert not doc[0].get_images(full=True)
    doc.close()
