"""Tests for URL utilities."""

from crawler.url_utils import (
    extract_domain,
    is_valid_http_url,
    normalize_url,
    same_origin,
    score_page_importance,
)


def test_normalize_url_removes_tracking():
    url = normalize_url("https://example.com/page?utm_source=test&id=1")
    assert url == "https://example.com/page?id=1"


def test_normalize_url_skips_mailto():
    assert normalize_url("mailto:test@example.com") is None


def test_normalize_url_resolves_relative():
    url = normalize_url("/about", "https://example.com")
    assert url == "https://example.com/about"


def test_same_origin():
    assert same_origin("https://example.com/about", "https://example.com")
    assert not same_origin("https://other.com", "https://example.com")


def test_extract_domain():
    assert extract_domain("https://www.example.com/path") == "www.example.com"


def test_is_valid_http_url():
    assert is_valid_http_url("https://example.com")
    assert not is_valid_http_url("ftp://example.com")


def test_score_page_importance():
    assert score_page_importance("https://example.com/") >= score_page_importance(
        "https://example.com/random-page"
    )
    assert score_page_importance("https://example.com/about") > 0
