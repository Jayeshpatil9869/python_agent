"""Analysis pipeline stages."""

import logging
from pathlib import Path
from typing import Any

from analyzers.accessibility_analyzer import analyze_accessibility
from analyzers.animation_analyzer import analyze_animations
from analyzers.asset_analyzer import analyze_assets
from analyzers.component_analyzer import analyze_components
from analyzers.css_analyzer import analyze_css
from analyzers.dom_analyzer import analyze_dom
from analyzers.layout_analyzer import analyze_layout
from analyzers.performance_analyzer import analyze_performance
from analyzers.responsive_analyzer import analyze_responsive
from analyzers.seo_analyzer import analyze_seo
from analyzers.technology_analyzer import analyze_technology
from config.settings import AnalysisOptions
from crawler.browser import BrowserManager
from crawler.page_loader import load_page
from intelligence.analyzer_result import StageStatus
from intelligence.schema import PageAnalysis
from observation.cursor import observe_cursor
from observation.interaction import run_interaction_lab
from observation.mutation_observer import observe_runtime_animations
from observation.page_load import install_page_load_tracer, observe_page_load
from observation.preloader import observe_preloader
from observation.scroll import observe_scroll
from observation.screenshot import capture_full_page
from observation.transitions import observe_page_transition

logger = logging.getLogger(__name__)


async def analyze_page(
    browser: BrowserManager,
    url: str,
    options: AnalysisOptions,
    output_dir: Path,
) -> PageAnalysis:
    """Run full analysis pipeline on a single page with staged evidence."""
    page_analysis = PageAnalysis(url=url, errors=[], stage_results={})
    stage_results: dict[str, dict] = {}

    async with browser.new_context() as context:
        page = await browser.new_page(context)
        try:
            # P0: Early motion — install tracer, capture preloader + page-load from first paint
            if options.deep or options.animations:
                logger.info("[PRELOADER] analyzing %s", url)
                await install_page_load_tracer(page)
                page_analysis.preloader = await observe_preloader(page, url, output_dir)
                stage_results["preloader"] = {
                    "status": (
                        StageStatus.SUCCESS.value
                        if page_analysis.preloader.observed
                        else StageStatus.NO_DATA.value
                    ),
                    "metrics": {
                        "observed": page_analysis.preloader.observed,
                        "type": page_analysis.preloader.type,
                    },
                }

                logger.info("[PAGE-LOAD] collecting early choreography trace")
                # Tracer already ran during preloader nav; harvest buffer, then soft reload if empty
                page_analysis.page_load = await observe_page_load(page, output_dir, wait_ms=500)
                if len(page_analysis.page_load.phases) < 3:
                    page_analysis.page_load = await observe_page_load(
                        page, output_dir, wait_ms=2800, url=url
                    )
                stage_results["page_load"] = {
                    "status": (
                        StageStatus.SUCCESS.value
                        if page_analysis.page_load.hero_animation.get("status") == "OBSERVED"
                        else StageStatus.NO_DATA.value
                    ),
                    "metrics": {
                        "phases": len(page_analysis.page_load.phases),
                        "hero": page_analysis.page_load.hero_animation.get("status"),
                        "nav": page_analysis.page_load.navigation_animation.get("status"),
                    },
                }
            else:
                stage_results["preloader"] = {"status": StageStatus.SKIPPED.value}
                stage_results["page_load"] = {"status": StageStatus.SKIPPED.value}

            logger.info("[CRAWL] loading page %s", url)
            load_metrics = await load_page(page, url, browser.settings.stabilization_wait_ms)
            html = await page.content()
            page_analysis.html_size = len(html)
            page_analysis.title = await page.title()

            meta = await page.evaluate(
                """() => ({
                    description: document.querySelector('meta[name="description"]')?.content || '',
                    canonical: document.querySelector('link[rel="canonical"]')?.href || '',
                    viewport: document.querySelector('meta[name="viewport"]')?.content || '',
                })"""
            )
            page_analysis.meta_description = meta.get("description", "")
            page_analysis.canonical = meta.get("canonical", "")
            page_analysis.viewport = meta.get("viewport", "")

            logger.info("[DOM] analyzing %s", url)
            dom = analyze_dom(html)
            page_analysis.dom_depth = dom.get("dom_depth", 0)
            page_analysis.section_count = dom.get("section_count", 0)
            page_analysis.headings = dom.get("headings", {})
            page_analysis.links_count = dom.get("links_count", 0)
            page_analysis.buttons_count = dom.get("buttons_count", 0)
            page_analysis.forms_count = dom.get("forms_count", 0)
            page_analysis.images_count = dom.get("images_count", 0)
            page_analysis.videos_count = dom.get("videos_count", 0)
            page_analysis.svgs_count = dom.get("svgs_count", 0)
            page_analysis.iframes_count = dom.get("iframes_count", 0)
            page_analysis.scripts_count = dom.get("scripts_count", 0)
            page_analysis.stylesheets_count = dom.get("stylesheets_count", 0)
            page_analysis.dom_summary = dom
            stage_results["dom"] = {"status": StageStatus.SUCCESS.value, "metrics": {"depth": dom.get("dom_depth")}}

            logger.info("[CSS] analyzing %s", url)
            css_summary = await analyze_css(page)
            page_analysis.css_summary = css_summary
            layout = await analyze_layout(page)
            page_analysis.layout_summary = layout
            stage_results["design"] = {"status": StageStatus.SUCCESS.value}

            page_analysis.components = await analyze_components(page)
            page_analysis.assets = await analyze_assets(page)

            logger.info("[TECHNOLOGY] analyzing %s", url)
            page_analysis.technologies = await analyze_technology(page, html)
            stage_results["technology"] = {
                "status": StageStatus.SUCCESS.value if page_analysis.technologies else StageStatus.NO_DATA.value,
                "metrics": {"count": len(page_analysis.technologies)},
            }

            page_analysis.seo = analyze_seo(html, url)
            page_analysis.accessibility = analyze_accessibility(html)
            page_analysis.performance = await analyze_performance(page, load_metrics)

            for category in ("desktop", "tablet", "mobile"):
                if category == "mobile" and not options.mobile:
                    continue
                if category == "desktop" and not options.desktop:
                    continue
                if category == "tablet" and not (options.tablet or options.deep):
                    continue
                vp = {"desktop": (1440, 900), "tablet": (768, 1024), "mobile": (375, 812)}[category]
                await page.set_viewport_size({"width": vp[0], "height": vp[1]})
                await page.wait_for_timeout(500)
                shot_path = output_dir / "screenshots" / category / "full.png"
                await capture_full_page(page, shot_path)
                page_analysis.screenshots[category] = f"screenshots/{category}/full.png"

            viewports = options.viewports
            if viewports:
                page_analysis.responsive, responsive_result = await analyze_responsive(
                    page,
                    url,
                    viewports,
                    output_dir,
                    browser.settings.stabilization_wait_ms,
                    reload_each=options.deep,
                )
                stage_results["responsive"] = responsive_result.model_dump(mode="json")
            else:
                stage_results["responsive"] = {"status": StageStatus.SKIPPED.value}

            if options.animations:
                logger.info("[ANIMATION] static css analysis")
                css_anims = await analyze_animations(page)
                runtime_anims, runtime_result = await observe_runtime_animations(page, output_dir)
                page_analysis.animations = css_anims + runtime_anims
                stage_results["animations"] = {
                    "status": (
                        StageStatus.SUCCESS.value
                        if page_analysis.animations
                        else StageStatus.NO_DATA.value
                    ),
                    "metrics": {
                        "css_animations": len(css_anims),
                        "runtime_animations": len(runtime_anims),
                    },
                    "runtime": runtime_result.model_dump(mode="json"),
                }
            else:
                stage_results["animations"] = {"status": StageStatus.SKIPPED.value}

            if options.interactions:
                interactions, interaction_result = await run_interaction_lab(page, output_dir)
                page_analysis.interactions = interactions
                stage_results["interactions"] = interaction_result.model_dump(mode="json")
            else:
                stage_results["interactions"] = {"status": StageStatus.SKIPPED.value}

            # Cursor / magnetic (deep or interactions)
            if options.deep or options.interactions:
                page_analysis.cursor = await observe_cursor(page, output_dir)
                stage_results["cursor"] = {
                    "status": StageStatus.SUCCESS.value if page_analysis.cursor.custom_cursor else StageStatus.NO_DATA.value,
                    "metrics": {
                        "custom_cursor": page_analysis.cursor.custom_cursor,
                        "magnetic": page_analysis.cursor.magnetic,
                    },
                }
            else:
                stage_results["cursor"] = {"status": StageStatus.SKIPPED.value}

            if options.deep:
                logger.info("[SCROLL] observing scroll behavior")
                observations, findings, color_transitions = await observe_scroll(
                    page, output_dir, options.scroll_steps, deep=True
                )
                page_analysis.scroll_observations = observations
                page_analysis.scroll_motion_findings = findings
                page_analysis.color_transitions = color_transitions
                stage_results["scroll"] = {
                    "status": (
                        StageStatus.SUCCESS.value
                        if observations and not (len(observations) == 1 and observations[0].get("error"))
                        else StageStatus.NO_DATA.value
                    ),
                    "metrics": {
                        "steps": len(observations),
                        "findings": len(findings),
                        "color_transitions": len(color_transitions),
                    },
                }

                # Safe page transition sample (optional, after scroll)
                transition = await observe_page_transition(page, output_dir)
                if transition:
                    page_analysis.page_transitions = [transition]
                stage_results["transitions"] = {
                    "status": (
                        StageStatus.SUCCESS.value
                        if transition and transition.observed
                        else StageStatus.NO_DATA.value
                    ),
                }
            else:
                stage_results["scroll"] = {"status": StageStatus.SKIPPED.value}
                stage_results["transitions"] = {"status": StageStatus.SKIPPED.value}

        except Exception as exc:
            logger.warning("Page analysis error for %s: %s", url, exc)
            page_analysis.errors.append(str(exc))
            stage_results["pipeline"] = {"status": StageStatus.FAILED.value, "error": str(exc)}
        finally:
            await page.close()

    page_analysis.stage_results = stage_results
    return page_analysis


def merge_stage_results(pages: list[PageAnalysis]) -> dict[str, Any]:
    """Aggregate stage statuses across pages."""
    merged: dict[str, Any] = {}
    if not pages:
        return merged
    keys = pages[0].stage_results.keys()
    for key in keys:
        statuses = [p.stage_results.get(key, {}).get("status", "unknown") for p in pages]
        if any(s == StageStatus.FAILED.value for s in statuses):
            overall = StageStatus.FAILED.value
        elif any(s == StageStatus.PARTIAL.value for s in statuses):
            overall = StageStatus.PARTIAL.value
        elif any(s == StageStatus.SUCCESS.value for s in statuses):
            overall = StageStatus.SUCCESS.value
        elif any(s == StageStatus.NO_DATA.value for s in statuses):
            overall = StageStatus.NO_DATA.value
        else:
            overall = statuses[0]
        merged[key] = {"status": overall, "pages": len(pages)}
    return merged
