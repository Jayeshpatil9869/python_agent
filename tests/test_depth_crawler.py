"""Tests for depth crawler utilities."""

from intelligence.schema import CrawlPageRecord
from crawler.depth_crawler import crawl_depth_summary


def test_crawl_depth_summary():
    records = [
        CrawlPageRecord(url="https://example.com/", depth=0, status="success"),
        CrawlPageRecord(url="https://example.com/about", depth=1, status="success"),
        CrawlPageRecord(url="https://example.com/team", depth=2, status="success"),
        CrawlPageRecord(url="https://example.com/contact", depth=1, status="success"),
    ]
    summary = crawl_depth_summary(records)
    assert summary[0] == 1
    assert summary[1] == 2
    assert summary[2] == 1


def test_crawl_page_record_fields():
    record = CrawlPageRecord(
        url="https://example.com/about",
        depth=1,
        parent_url="https://example.com/",
        discovery_source="navigation",
        status="success",
    )
    assert record.depth == 1
    assert record.parent_url == "https://example.com/"
    assert record.discovery_source == "navigation"
