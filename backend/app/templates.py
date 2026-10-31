"""Document templates: curated field maps for recurring forms."""

from __future__ import annotations

import json
from pathlib import Path

from .models import FieldSpec, TemplateSummary

TEMPLATE_DIR = Path(__file__).parent / "templates"
SIZE_TOLERANCE = 2.0


def load_templates() -> dict[str, dict]:
    templates: dict[str, dict] = {}
    if not TEMPLATE_DIR.exists():
        return templates
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if "id" in data and "fields" in data:
            templates[data["id"]] = data
    return templates


def summaries() -> list[TemplateSummary]:
    out = []
    for data in load_templates().values():
        out.append(
            TemplateSummary(
                id=data["id"],
                name=data.get("name", data["id"]),
                description=data.get("description", ""),
                pageCount=int(data.get("pageCount", 0)),
                fieldCount=len(data.get("fields", [])),
                pageSizes=data.get("pageSizes", []),
            )
        )
    return out


def matches_page_layout(template: dict, pages: list[dict]) -> bool:
    expected = template.get("pageSizes") or []
    if len(expected) != len(pages):
        return False
    for size, page in zip(expected, pages):
        if abs(float(size[0]) - page["width"]) > SIZE_TOLERANCE:
            return False
        if abs(float(size[1]) - page["height"]) > SIZE_TOLERANCE:
            return False
    return True


def find_match(pages: list[dict], sha256: str) -> dict | None:
    for data in load_templates().values():
        if data.get("sha256") == sha256:
            return data
    for data in load_templates().values():
        if matches_page_layout(data, pages):
            return data
    return None


def apply_template(template: dict, pages: list[dict]) -> list[FieldSpec]:
    if not matches_page_layout(template, pages):
        raise ValueError("template page layout does not match this document")
    fields: list[FieldSpec] = []
    for index, raw in enumerate(template.get("fields", [])):
        field = dict(raw)
        field.setdefault("id", f"tpl_{template['id']}_{index}")
        field.setdefault("source", "template")
        field.setdefault("confidence", 1.0)
        field.setdefault("fontSize", 7.0)
        field.pop("rect_normalized", None)
        fields.append(FieldSpec(**field))
    return fields
