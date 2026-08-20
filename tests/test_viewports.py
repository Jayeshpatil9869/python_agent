"""Tests for viewport resolution."""

from config.settings import (
    DESKTOP_VIEWPORT_TUPLES,
    MOBILE_VIEWPORT_TUPLES,
    AnalysisOptions,
    DEEP_VIEWPORT_TUPLES,
)


def test_mobile_only_viewports():
    opts = AnalysisOptions(url="https://example.com", deep=True, mobile=True, desktop=False, tablet=False)
    vps = opts.resolve_viewports()
    assert vps == MOBILE_VIEWPORT_TUPLES


def test_desktop_only_viewports():
    opts = AnalysisOptions(url="https://example.com", deep=True, mobile=False, desktop=True, tablet=False)
    vps = opts.resolve_viewports()
    assert vps == DESKTOP_VIEWPORT_TUPLES


def test_mobile_and_desktop_combined():
    opts = AnalysisOptions(url="https://example.com", deep=True, mobile=True, desktop=True, tablet=False)
    vps = opts.resolve_viewports()
    assert len(vps) == len(MOBILE_VIEWPORT_TUPLES) + len(DESKTOP_VIEWPORT_TUPLES)


def test_deep_default_all_groups():
    opts = AnalysisOptions(url="https://example.com", deep=True, mobile=True, desktop=True, tablet=True)
    vps = opts.resolve_viewports()
    assert len(vps) == len(DEEP_VIEWPORT_TUPLES)


def test_fast_mode_respects_flags():
    opts = AnalysisOptions(url="https://example.com", deep=False, mobile=True, desktop=False)
    vps = opts.resolve_viewports()
    assert len(vps) == 1
    assert vps[0][0] == 375
