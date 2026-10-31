from __future__ import annotations

import pytest

from app import templates


def _pages(sizes: list[list[float]]) -> list[dict]:
    return [
        {"index": index, "width": float(size[0]), "height": float(size[1]), "rotation": 0}
        for index, size in enumerate(sizes)
    ]


def _synthetic_template() -> dict:
    return {
        "id": "synthetic",
        "name": "Synthetic form",
        "pageCount": 2,
        "pageSizes": [[400, 300], [400, 300]],
        "fields": [
            {"page": 0, "rect": [20, 20, 200, 34], "type": "text", "name": "first_name", "label": "First name"},
            {"page": 1, "rect": [20, 40, 60, 80], "type": "image", "name": "photo", "label": "Photo"},
        ],
    }


def test_apply_template_sets_defaults_and_keeps_geometry():
    template = _synthetic_template()
    pages = _pages(template["pageSizes"])
    assert templates.matches_page_layout(template, pages)

    fields = templates.apply_template(template, pages)
    assert [field.name for field in fields] == ["first_name", "photo"]
    assert all(field.source == "template" for field in fields)
    assert all(field.confidence == 1.0 for field in fields)
    assert all(field.fontSize == 7.0 for field in fields)
    assert fields[0].rect == [20.0, 20.0, 200.0, 34.0]
    assert fields[0].id == "tpl_synthetic_0"


def test_layout_mismatch_is_rejected():
    template = _synthetic_template()
    pages = _pages(template["pageSizes"])
    pages[0]["width"] += templates.SIZE_TOLERANCE * 2
    assert not templates.matches_page_layout(template, pages)
    with pytest.raises(ValueError):
        templates.apply_template(template, pages)


def test_bundled_templates_are_valid_if_present():
    """Local templates are optional in a public checkout."""
    loaded = templates.load_templates()
    if not loaded:
        pytest.skip("no local templates present")

    for template in loaded.values():
        pages = _pages(template["pageSizes"])
        assert template["pageCount"] == len(template["pageSizes"])
        assert templates.matches_page_layout(template, pages)

        fields = templates.apply_template(template, pages)
        assert len(fields) == len(template["fields"])

        for field in fields:
            width, height = template["pageSizes"][field.page]
            x0, y0, x1, y1 = field.rect
            assert -0.5 <= x0 < x1 <= width + 0.5
            assert -0.5 <= y0 < y1 <= height + 0.5
