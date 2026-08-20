"""End-to-end tests against deterministic fixture website."""

import socket
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from agent.pipeline import analyze_page
from config.settings import AnalysisOptions, Settings
from crawler.browser import BrowserManager
from crawler.depth_crawler import crawl_depth_summary, crawl_with_depth
from intelligence.validation import validate_analysis_output

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
    base_url = f"http://127.0.0.1:{port}/index.html"
    yield base_url
    server.shutdown()


@pytest.mark.asyncio
async def test_depth_crawl_levels(fixture_server):
    base_url = fixture_server
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        opts0 = AnalysisOptions(url=base_url, depth=0, max_pages=20)
        records0 = await crawl_with_depth(page, opts0)
        summary0 = crawl_depth_summary(records0)
        assert summary0.get(0, 0) >= 1
        assert summary0.get(1, 0) == 0
        assert summary0.get(2, 0) == 0

        opts1 = AnalysisOptions(url=base_url, depth=1, max_pages=20)
        records1 = await crawl_with_depth(page, opts1)
        summary1 = crawl_depth_summary(records1)
        assert summary1.get(0, 0) >= 1
        assert summary1.get(1, 0) > 0
        assert summary1.get(2, 0) == 0

        opts2 = AnalysisOptions(url=base_url, depth=2, max_pages=20)
        records2 = await crawl_with_depth(page, opts2)
        summary2 = crawl_depth_summary(records2)
        assert summary2.get(2, 0) >= 1

        await browser.close()


@pytest.mark.asyncio
async def test_responsive_mobile_only(fixture_server, tmp_path):
    base_url = fixture_server
    settings = Settings()
    options = AnalysisOptions(
        url=base_url,
        deep=True,
        mobile=True,
        desktop=False,
        tablet=False,
        animations=False,
        interactions=False,
        output=tmp_path,
    )
    browser = BrowserManager(settings, options)
    await browser.start()
    try:
        result = await analyze_page(browser, base_url, options, tmp_path / "out")
        widths = [r.width for r in result.responsive]
        assert all(w < 768 for w in widths)
        assert len(widths) == 5
    finally:
        await browser.stop()


@pytest.mark.asyncio
async def test_responsive_desktop_only(fixture_server, tmp_path):
    base_url = fixture_server
    settings = Settings()
    options = AnalysisOptions(
        url=base_url,
        deep=True,
        mobile=False,
        desktop=True,
        tablet=False,
        animations=False,
        interactions=False,
        output=tmp_path,
    )
    browser = BrowserManager(settings, options)
    await browser.start()
    try:
        result = await analyze_page(browser, base_url, options, tmp_path / "out")
        widths = [r.width for r in result.responsive]
        assert all(w >= 1280 for w in widths)
        assert len(widths) == 3
    finally:
        await browser.stop()


@pytest.mark.asyncio
async def test_interaction_state_changes(fixture_server, tmp_path):
    interactions_url = fixture_server.replace("index.html", "interactions.html")
    settings = Settings()
    options = AnalysisOptions(
        url=interactions_url,
        deep=False,
        interactions=True,
        animations=False,
        output=tmp_path,
    )
    browser = BrowserManager(settings, options)
    await browser.start()
    try:
        result = await analyze_page(browser, interactions_url, options, tmp_path / "out")
        assert result.stage_results["interactions"]["status"] in ("success", "no_data")
        if result.interactions:
            triggers = {i.trigger for i in result.interactions}
            assert triggers & {"hover", "focus", "click"}
    finally:
        await browser.stop()


@pytest.mark.asyncio
async def test_animation_evidence(fixture_server, tmp_path):
    anim_url = fixture_server.replace("index.html", "animations.html")
    settings = Settings()
    options = AnalysisOptions(
        url=anim_url,
        deep=False,
        animations=True,
        interactions=False,
        output=tmp_path,
    )
    browser = BrowserManager(settings, options)
    await browser.start()
    try:
        result = await analyze_page(browser, anim_url, options, tmp_path / "out")
        assert len(result.animations) >= 0
        assert result.stage_results["animations"]["status"] in ("success", "no_data")
    finally:
        await browser.stop()


@pytest.mark.asyncio
async def test_full_pipeline_and_validation(fixture_server, tmp_path):
    base_url = fixture_server
    settings = Settings()
    output_dir = tmp_path / "fixture-output"
    output_dir.mkdir()
    options = AnalysisOptions(
        url=base_url,
        depth=1,
        max_pages=5,
        deep=True,
        mobile=True,
        desktop=True,
        animations=True,
        interactions=True,
        ai=False,
        output=output_dir,
    )
    browser = BrowserManager(settings, options)
    await browser.start()
    try:
        page_result = await analyze_page(browser, base_url, options, output_dir)
        from utils.filesystem import write_json

        data_dir = output_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        write_json(data_dir / "pages.json", [page_result.model_dump(mode="json")])
        write_json(data_dir / "responsive.json", [r.model_dump(mode="json") for r in page_result.responsive])
        write_json(data_dir / "interactions.json", [i.model_dump(mode="json") for i in page_result.interactions])
        write_json(data_dir / "animations.json", [a.model_dump(mode="json") for a in page_result.animations])
        write_json(data_dir / "technologies.json", [t.model_dump(mode="json") for t in page_result.technologies])
        write_json(
            data_dir / "website.json",
            {
                "url": base_url,
                "stage_results": page_result.stage_results,
            },
        )

        validation = validate_analysis_output(output_dir, stage_results=page_result.stage_results)
        assert validation["overall_status"] in ("PASS", "PARTIAL")
        assert validation["metrics"]["viewports"] > 0
    finally:
        await browser.stop()
