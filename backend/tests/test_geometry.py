from __future__ import annotations

import pytest

from app.geometry import (
    area,
    clamp_rect,
    contains_point,
    dedupe,
    intersection,
    iou,
    overlap_ratio,
)


def test_area_and_intersection():
    a = (0, 0, 10, 10)
    b = (5, 5, 15, 15)
    assert area(a) == 100
    assert intersection(a, b) == (5, 5, 10, 10)
    assert iou(a, b) == pytest.approx(25 / 175)


def test_overlap_ratio_is_relative_to_the_smaller_rect():
    small = (0, 0, 10, 10)
    big = (0, 0, 100, 100)
    assert overlap_ratio(small, big) == pytest.approx(1.0)


def test_contains_point_is_inside_only():
    assert contains_point((10, 10, 20, 20), 15, 15)
    assert not contains_point((10, 10, 20, 20), 25, 15)


def test_dedupe_keeps_larger_rect():
    small = (0, 0, 10, 10)
    big = (0, 0, 10.4, 10.4)
    assert dedupe([small, big]) == [big]
    assert dedupe([small, (0, 0, 12, 12)]) == [(0, 0, 12, 12), small]


def test_clamp_rect_trims_to_page_but_keeps_positive_size():
    assert clamp_rect((-5, -5, 20, 20), 100, 100) == (0, 0, 20, 20)
    assert clamp_rect((90, 90, 120, 120), 100, 100) == (90, 90, 100, 100)
