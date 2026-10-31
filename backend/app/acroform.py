"""Create real AcroForm widgets with PyMuPDF.

Original content is never rewritten: widgets are annotations on top of the
existing page content, so text, vectors, images and page boxes are preserved.
The only exception is a user-supplied image value, which is embedded as new
page content behind its transparent placeholder widget.

Coordinate note: PyMuPDF reports and accepts page coordinates in the
unrotated top-left space, which is the same canonical space the frontend
sends. No pixel math happens here.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

import pymupdf

from .models import FieldSpec

FLAG_REQUIRED = 1 << 1          # bit 2
FLAG_NO_EXPORT = 1 << 2         # bit 3
FLAG_READ_ONLY = 1 << 0         # bit 1
FLAG_MULTILINE = 1 << 12        # bit 13

Q_LEFT, Q_CENTER, Q_RIGHT = 0, 1, 2


@dataclass
class CreationReport:
    widget_count: int = 0
    field_names: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    by_type: dict[str, int] = field(default_factory=dict)


def _safe_name(name: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\-.]", "_", name or "").strip("_")
    return cleaned[:120] or fallback


def _colour(value, default):
    if value is None:
        return default
    return tuple(float(c) for c in value)


def _apply_common(widget: pymupdf.Widget, spec: FieldSpec, name: str, fill: bool = True) -> None:
    widget.field_name = name
    widget.rect = pymupdf.Rect(*spec.rect)
    widget.field_label = (spec.label or spec.tooltip or name)[:200]
    flags = 0
    if spec.required:
        flags |= FLAG_REQUIRED
    if spec.type == "multiline" or (spec.type == "address" and spec.rect[3] - spec.rect[1] > 24):
        flags |= FLAG_MULTILINE
    widget.field_flags = flags
    widget.text_font = "Helv"
    widget.text_fontsize = 0 if not spec.fontSize or spec.fontSize <= 0 else min(72.0, spec.fontSize)
    widget.text_color = (0, 0, 0)
    widget.fill_color = (1, 1, 1) if fill else None
    widget.border_color = (0, 0, 0) if fill else None
    widget.border_width = 0.5 if fill else 0


def _wants_fill(spec: FieldSpec) -> bool:
    return spec.background != "none"


def _quadding(spec: FieldSpec) -> int:
    return {"left": Q_LEFT, "center": Q_CENTER, "right": Q_RIGHT}.get(spec.alignment, Q_LEFT)


def _set_quadding(doc: pymupdf.Document, annot: pymupdf.Annot, spec: FieldSpec) -> None:
    q = _quadding(spec)
    try:
        doc.xref_set_key(annot.xref, "Q", str(q))
    except Exception:
        pass


def _add_text(page: pymupdf.Page, doc: pymupdf.Document, spec: FieldSpec, name: str, report: CreationReport) -> None:
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    _apply_common(widget, spec, name, _wants_fill(spec))
    value = spec.value if isinstance(spec.value, str) else ""
    widget.field_value = value
    if spec.maxLength and spec.maxLength > 0:
        widget.text_maxlen = min(10000, spec.maxLength)
    annot = page.add_widget(widget)
    _set_quadding(doc, annot, spec)
    report.widget_count += 1


def _add_checkbox(page: pymupdf.Page, spec: FieldSpec, name: str) -> None:
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    _apply_common(widget, spec, name, _wants_fill(spec))
    if spec.value is None:
        widget.field_value = bool(spec.checked)
    else:
        widget.field_value = bool(spec.value)
    widget.text_fontsize = 0
    page.add_widget(widget)


def _add_radio(page: pymupdf.Page, spec: FieldSpec, group_name: str, export_value: str, selected: bool) -> None:
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON
    _apply_common(widget, spec, group_name, _wants_fill(spec))
    widget.field_value = export_value if selected else False
    page.add_widget(widget)


def _add_choice(page: pymupdf.Page, spec: FieldSpec, name: str) -> None:
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
    _apply_common(widget, spec, name, True)
    options = [str(o) for o in spec.options if str(o).strip()]
    if not options:
        options = ["Option 1", "Option 2"]
    widget.choice_values = options
    if isinstance(spec.value, str) and spec.value in options:
        widget.field_value = spec.value
    page.add_widget(widget)


def _add_signature(page: pymupdf.Page, spec: FieldSpec, name: str) -> None:
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
    _apply_common(widget, spec, name, True)
    annot = page.add_widget(widget)
    # PyMuPDF stamps a coloured "SIGN" tag into the appearance stream. An
    # unsigned signature field does not need an appearance, and the tag would
    # change how the printed form looks.
    try:
        page.parent.xref_set_key(annot.xref, "AP", "null")
    except Exception:
        pass


def _add_image_button(page: pymupdf.Page, doc: pymupdf.Document, spec: FieldSpec, name: str) -> None:
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_BUTTON
    # A photo placeholder usually has its printed caption inside the box, so
    # never paint a fill: it would hide the caption (and any embedded image).
    _apply_common(widget, spec, name, False)
    widget.button_caption = ""
    annot = page.add_widget(widget)
    try:
        doc.xref_set_key(annot.xref, "AP", "null")
    except Exception:
        pass


DATA_IMAGE = re.compile(r"^data:image/(?:png|jpe?g);base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)
MAX_IMAGE_BYTES = 8_000_000


def _embed_images(doc: pymupdf.Document, fields: list[FieldSpec], report: CreationReport) -> None:
    for spec in fields:
        if spec.type != "image" or not isinstance(spec.value, str) or not spec.value:
            continue
        match = DATA_IMAGE.match(spec.value.strip())
        if not match:
            report.warnings.append(f"image field '{spec.name}': only PNG or JPEG data URLs are embedded")
            continue
        try:
            data = base64.b64decode(re.sub(r"\s+", "", match.group(1)), validate=True)
        except Exception:
            report.warnings.append(f"image field '{spec.name}': invalid base64 image data")
            continue
        if len(data) > MAX_IMAGE_BYTES:
            report.warnings.append(f"image field '{spec.name}': image is larger than {MAX_IMAGE_BYTES // 1_000_000} MB")
            continue
        if spec.page < 0 or spec.page >= doc.page_count:
            continue
        try:
            doc[spec.page].insert_image(pymupdf.Rect(*spec.rect), stream=data, keep_proportion=True)
        except Exception as exc:
            report.warnings.append(f"image field '{spec.name}': could not embed image ({exc})")


def create_widgets(doc: pymupdf.Document, fields: list[FieldSpec]) -> CreationReport:
    report = CreationReport()
    used: dict[str, int] = {}
    page_count = doc.page_count

    ordered = sorted(fields, key=lambda f: (f.page, f.rect[1], f.rect[0]))
    radio_widgets: list[tuple[FieldSpec, str, str, bool]] = []

    for idx, spec in enumerate(ordered):
        if spec.page < 0 or spec.page >= page_count:
            report.warnings.append(f"field '{spec.name}' references missing page {spec.page + 1}")
            continue
        page = doc[spec.page]
        base = _safe_name(spec.name or spec.label, f"field_{spec.page + 1}_{idx + 1}")
        used[base] = used.get(base, 0) + 1
        name = base if used[base] == 1 else f"{base}_{used[base]}"

        if spec.type == "radio":
            group = _safe_name(spec.group or spec.name or base, f"radio_{spec.page + 1}_{idx + 1}")
            export = str(spec.value or spec.label or f"option_{idx + 1}")
            radio_widgets.append((spec, group, export, spec.checked or spec.value is True))
            continue

        if spec.type in ("text", "multiline", "date", "number", "email", "address"):
            _add_text(page, doc, spec, name, report)
        elif spec.type == "checkbox":
            _add_checkbox(page, spec, name)
        elif spec.type == "dropdown":
            _add_choice(page, spec, name)
        elif spec.type == "signature":
            _add_signature(page, spec, name)
        elif spec.type == "image":
            _add_image_button(page, doc, spec, name)
        else:
            report.warnings.append(f"unsupported field type '{spec.type}'")
            continue
        report.by_type[spec.type] = report.by_type.get(spec.type, 0) + 1
        report.field_names.append(name)

    for spec, group, export, selected in radio_widgets:
        page = doc[spec.page]
        _add_radio(page, spec, group, export, selected)
        report.by_type["radio"] = report.by_type.get("radio", 0) + 1
        report.widget_count += 1
        if group not in report.field_names:
            report.field_names.append(group)

    _embed_images(doc, ordered, report)
    return report


def verify_document(doc: pymupdf.Document, expected: list[FieldSpec], tolerance: float = 1.5) -> dict:
    """Check that every widget exists in an open document where asked."""
    actual: dict[str, list[dict]] = {}
    total = 0
    for page_index, page in enumerate(doc):
        for widget in page.widgets():
            total += 1
            parent = widget.field_name or ""
            actual.setdefault(parent, []).append(
                {
                    "page": page_index,
                    "rect": [round(v, 2) for v in widget.rect],
                    "type": widget.field_type_string,
                    "value": widget.field_value,
                }
            )
    mismatches: list[str] = []
    for spec in expected:
        lookup = spec.group if spec.type == "radio" and spec.group else spec.name
        matches = actual.get(_safe_name(lookup, ""), [])
        if not matches:
            if spec.type != "radio":
                mismatches.append(f"missing widget for '{spec.name}'")
            continue
        same_page = [m for m in matches if m["page"] == spec.page]
        if not same_page:
            mismatches.append(f"'{spec.name}' on wrong page")
            continue
        ok = any(
            abs(m["rect"][0] - spec.rect[0]) <= tolerance
            and abs(m["rect"][1] - spec.rect[1]) <= tolerance
            and abs(m["rect"][2] - spec.rect[2]) <= tolerance
            and abs(m["rect"][3] - spec.rect[3]) <= tolerance
            for m in same_page
        )
        if not ok:
            mismatches.append(f"'{spec.name}' rect mismatch")
    return {"widgetCount": total, "mismatches": mismatches, "pages": doc.page_count}


def verify(path: str, expected: list[FieldSpec], tolerance: float = 1.5) -> dict:
    """Reopen the saved file and check that every widget exists where asked."""
    doc = pymupdf.open(path)
    try:
        return verify_document(doc, expected, tolerance)
    finally:
        doc.close()


def save(src_path: str, out_path: str, fields: list[FieldSpec], flatten: bool = False) -> dict:
    doc = pymupdf.open(src_path)
    report = create_widgets(doc, fields)
    result = verify_document(doc, fields)
    if flatten:
        doc.bake()
    doc.save(out_path, garbage=0, deflate=True, clean=False)
    doc.close()

    result.update(
        {
            "warnings": report.warnings + result["mismatches"],
            "byType": report.by_type,
        }
    )
    if flatten:
        result["widgetCount"] = 0
    return result


def extract_existing(path: str) -> list[dict]:
    """Return AcroForm widgets found in a PDF, in the app's field model."""
    doc = pymupdf.open(path)
    out: list[dict] = []
    radio_groups: dict[str, dict] = {}
    for page_index, page in enumerate(doc):
        for widget in page.widgets():
            name = widget.field_name or ""
            rect = widget.rect
            entry = {
                "page": page_index,
                "rect": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
                "name": name,
                "label": widget.field_label or name,
                "value": widget.field_value,
            }
            ftype = widget.field_type
            if ftype == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
                entry["type"] = "checkbox"
                checked = widget.field_value not in (None, False, "", "Off")
                entry["value"] = checked
                entry["checked"] = checked
            elif ftype == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                if name not in radio_groups:
                    selected = widget.field_value not in (None, "Off")
                    radio_groups[name] = {
                        "page": page_index,
                        "rect": entry["rect"],
                        "name": name,
                        "label": widget.field_label or name,
                        "type": "radio",
                        "options": [],
                        "value": str(widget.field_value) if selected else "",
                        "checked": selected,
                        "source": "existing",
                        "id": f"existing_{name}",
                    }
                    out.append(radio_groups[name])
                group = radio_groups[name]
                group["options"].append(str(widget.field_value))
                continue
            elif ftype in (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, pymupdf.PDF_WIDGET_TYPE_LISTBOX):
                entry["type"] = "dropdown"
                entry["options"] = list(widget.choice_values or [])
            elif ftype == pymupdf.PDF_WIDGET_TYPE_SIGNATURE:
                entry["type"] = "signature"
            elif ftype == pymupdf.PDF_WIDGET_TYPE_BUTTON:
                entry["type"] = "image"
            else:
                entry["type"] = "multiline" if (widget.field_flags or 0) & FLAG_MULTILINE else "text"
            entry["id"] = f"existing_{name}_{page_index}_{len(out)}"
            entry["source"] = "existing"
            out.append(entry)
    doc.close()
    return out
