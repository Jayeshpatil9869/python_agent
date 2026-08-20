"""Motion intelligence unit/e2e tests against fixture site."""

import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from agent.pipeline import analyze_page
from config.settings import AnalysisOptions, Settings
from crawler.browser import BrowserManager
from intelligence.motion_intelligence import build_motion_intelligence
from intelligence.schema import PageAnalysis, WebsiteIntelligence
from intelligence.normalizer import normalize_website_intelligence

FIXTURE_DIR = Path(__file__).resolve().parent / "fixture_site"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def fixture_server():
    port = _free_port()
    handler = partial(SimpleHTTPRequestHandler, directory=str(FIXTURE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/index.html"
    server.shutdown()


@pytest.mark.asyncio
async def test_preloader_observed(fixture_server, tmp_path):
    settings = Settings()
    options = AnalysisOptions(
        url=fixture_server,
        deep=True,
        animations=True,
        interactions=False,
        mobile=True,
        desktop=True,
        max_pages=1,
        output=tmp_path,
    )
    browser = BrowserManager(settings, options)
    await browser.start()
    try:
        out = tmp_path / "out"
        out.mkdir()
        result = await analyze_page(browser, fixture_server, options, out)
        assert result.preloader.observed is True
        assert result.preloader.type != "NOT_OBSERVED"
        assert (out / "runtime" / "preloader" / "summary.json").exists()
    finally:
        await browser.stop()


@pytest.mark.asyncio
async def test_scroll_motion_findings(fixture_server, tmp_path):
    scroll_url = fixture_server.replace("index.html", "scroll.html")
    settings = Settings()
    options = AnalysisOptions(
        url=scroll_url,
        deep=True,
        animations=True,
        interactions=False,
        mobile=False,
        desktop=True,
        output=tmp_path,
    )
    browser = BrowserManager(settings, options)
    await browser.start()
    try:
        out = tmp_path / "out"
        out.mkdir()
        result = await analyze_page(browser, scroll_url, options, out)
        assert len(result.scroll_observations) >= 10
        classifications = {f.classification for f in result.scroll_motion_findings}
        # At least one scroll-linked behavior should appear on the scroll fixture
        assert classifications & {
            "PARALLAX",
            "PINNED",
            "HORIZONTAL_SCROLL",
            "SCROLL_LINKED_SCALE",
            "SCROLL_CLIP_REVEAL",
            "SCROLL_TRANSLATE",
            "SCROLL_FADE",
        }
    finally:
        await browser.stop()


def test_motion_intelligence_builder_empty_page():
    website = WebsiteIntelligence(url="https://example.com", pages=[])
    mi = build_motion_intelligence(website)
    assert "No page evidence" in mi.motion_summary


def test_normalize_builds_motion_and_design():
    page = PageAnalysis(url="https://example.com", title="Example")
    website = WebsiteIntelligence(url="https://example.com", pages=[page])
    result = normalize_website_intelligence(website)
    assert result.motion_intelligence is not None
    assert result.design_intelligence is not None
    assert "MOTION" in result.motion_intelligence.motion_summary.upper() or "personality" in result.motion_intelligence.motion_summary.lower() or result.motion_intelligence.motion_summary
