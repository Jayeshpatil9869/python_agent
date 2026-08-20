"""Unit tests for hero page-load animation classification."""

from observation.page_load import _animated_change, _layout_only_change, _meaningful_change


def test_top_only_change_is_not_animation():
    a = {
        "opacity": "1",
        "transform": "none",
        "clipPath": "none",
        "visibility": "visible",
        "filter": "none",
        "top": 100,
        "height": 80,
    }
    b = {**a, "top": 140}
    assert _animated_change(a, b) is False
    assert _meaningful_change(a, b) is False
    assert _layout_only_change(a, b) is True


def test_opacity_change_is_animation():
    a = {
        "opacity": "0",
        "transform": "none",
        "clipPath": "none",
        "visibility": "visible",
        "filter": "none",
        "top": 100,
    }
    b = {**a, "opacity": "1"}
    assert _animated_change(a, b) is True
    assert _layout_only_change(a, b) is False


def test_transform_change_is_animation():
    a = {
        "opacity": "1",
        "transform": "matrix(1, 0, 0, 1, 0, 80)",
        "clipPath": "none",
        "visibility": "visible",
        "filter": "none",
        "top": 100,
    }
    b = {**a, "transform": "none"}
    assert _animated_change(a, b) is True
