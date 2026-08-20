"""Central orchestrator for website analysis."""

import logging
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from agent.pipeline import analyze_page, merge_stage_results
from agent.state import AgentState
from ai.analyzer import run_ai_analysis
from config.settings import AnalysisOptions, Settings
from crawler.browser import BrowserManager
from crawler.depth_crawler import crawl_depth_summary, crawl_with_depth
from intelligence.normalizer import normalize_website_intelligence
from intelligence.schema import CrawlPageRecord, WebsiteIntelligence
from intelligence.validation import validate_analysis_output
from reports.generator import ReportGenerator
from utils.filesystem import ensure_dir, url_to_slug, write_json
from utils.logger import setup_logger

console = Console()
STAGES = [
    "Launching browser",
    "Loading website",
    "Discovering pages",
    "Inspecting DOM",
    "Analyzing design system",
    "Testing responsive layouts",
    "Observing animations",
    "Testing interactions",
    "Running AI analysis",
    "Validating results",
    "Generating reports",
    "Analysis complete",
]


class WebsiteAnalysisAgent:
    """Orchestrates the full website intelligence pipeline."""

    def __init__(self, options: AnalysisOptions, settings: Settings | None = None) -> None:
        self.options = options
        self.settings = settings or Settings()
        slug = url_to_slug(options.url)
        self.output_dir = Path(options.output or self.settings.output_dir) / slug
        self.state = AgentState(options=options, output_dir=self.output_dir)
        self.logger = setup_logger(
            "website-intelligence",
            log_file=self.output_dir / "analysis.log",
        )

    async def run(self) -> WebsiteIntelligence:
        ensure_dir(self.output_dir)
        for sub in (
            "screenshots/desktop",
            "screenshots/tablet",
            "screenshots/mobile",
            "screenshots/scroll",
            "runtime/interactions",
            "runtime/animations",
            "runtime/scroll",
            "runtime/preloader",
            "runtime/page-load",
            "runtime/cursor",
            "runtime/transitions",
            "runtime/responsive",
            "data",
        ):
            ensure_dir(self.output_dir / sub)

        browser = BrowserManager(self.settings, self.options)
        intelligence = WebsiteIntelligence(url=self.options.url)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(STAGES[0], total=len(STAGES))

            try:
                progress.update(task, description=STAGES[0])
                await browser.start()
                progress.advance(task)

                progress.update(task, description=STAGES[1])
                async with browser.new_context() as context:
                    page = await browser.new_page(context)
                    progress.update(task, description=STAGES[2])
                    crawl_records = await crawl_with_depth(page, self.options)
                    intelligence.crawl_pages = crawl_records
                    discovered = [r.url for r in crawl_records if r.status == "success"]
                    if not discovered:
                        discovered = [self.options.url]
                    self.state.discovered_urls = discovered
                    intelligence.sitemap_urls = discovered
                    depth_summary = crawl_depth_summary(crawl_records)
                    for depth, count in depth_summary.items():
                        self.logger.info("[CRAWL] Depth %d: %d pages", depth, count)
                    await page.close()
                progress.advance(task)

                pages_analyzed = []
                for i, page_url in enumerate(discovered[: self.options.max_pages]):
                    stage_idx = min(3 + (i % 4), 7)
                    progress.update(task, description=f"{STAGES[stage_idx]} ({page_url})")
                    self.logger.info("Analyzing page: %s", page_url)
                    page_result = await analyze_page(
                        browser, page_url, self.options, self.output_dir
                    )
                    pages_analyzed.append(page_result)
                    if not intelligence.title and page_result.title:
                        intelligence.title = page_result.title

                intelligence.pages = pages_analyzed
                intelligence.stage_results = merge_stage_results(pages_analyzed)
                progress.advance(task, advance=4)

                progress.update(task, description="Normalizing intelligence")
                intelligence = normalize_website_intelligence(intelligence)

                if self.options.ai:
                    progress.update(task, description=STAGES[8])
                    try:
                        intelligence.ai_interpretation = await run_ai_analysis(
                            intelligence, self.settings, self.output_dir
                        )
                    except Exception as exc:
                        self.logger.warning("AI analysis skipped: %s", exc)
                        intelligence.ai_interpretation = {
                            "full_analysis": (
                                f"AI analysis could not complete: {exc}\n\n"
                                "Technical analysis and reports were still generated."
                            ),
                            "reconstruction_prompt": "",
                        }
                    progress.advance(task)
                else:
                    progress.advance(task)

                progress.update(task, description=STAGES[10])
                self._save_json(intelligence)
                generator = ReportGenerator(intelligence, self.output_dir)
                generator.generate_all()
                progress.advance(task)

                progress.update(task, description=STAGES[9])
                validation = validate_analysis_output(
                    self.output_dir,
                    stage_results=intelligence.stage_results,
                )
                intelligence.analysis_status = validation["overall_status"]
                intelligence.stage_results["validation"] = validation
                # Persist validation status into website.json
                self._save_json(intelligence)
                progress.advance(task)

                progress.update(task, description=STAGES[11])
                progress.advance(task)

                self._print_summary(intelligence, validation)

            except Exception as exc:
                self.logger.error("Analysis failed: %s", exc)
                self.state.errors.append(str(exc))
                raise
            finally:
                await browser.stop()

        self.state.intelligence = intelligence
        return intelligence

    def _print_summary(self, intelligence: WebsiteIntelligence, validation: dict) -> None:
        responsive_count = sum(len(p.responsive) for p in intelligence.pages)
        interaction_count = sum(len(p.interactions) for p in intelligence.pages)
        depth_summary = crawl_depth_summary(intelligence.crawl_pages) if intelligence.crawl_pages else {}
        depth_lines = [f"  Depth {d}: {c} pages" for d, c in depth_summary.items()]

        interaction_meta = intelligence.stage_results.get("interactions", {})
        interaction_metrics = interaction_meta.get("metrics", {}) if isinstance(interaction_meta, dict) else {}
        candidates = interaction_metrics.get("candidates_discovered", interaction_count)
        tested = interaction_metrics.get("candidates_tested", interaction_count)
        state_changes = interaction_metrics.get("state_changes_observed", interaction_count)

        ai_status = "UNAVAILABLE"
        if self.options.ai:
            ai_interp = intelligence.ai_interpretation or {}
            if ai_interp.get("provider_used"):
                ai_status = "AVAILABLE"
            elif ai_interp.get("full_analysis"):
                ai_status = "PARTIAL" if "could not complete" in str(ai_interp.get("full_analysis", "")).lower() else "AVAILABLE"
            else:
                ai_status = "UNAVAILABLE"

        lines = [
            "",
            "==============================================",
            " AWWWARDS WEBSITE EXPERIENCE FORENSICS",
            "==============================================",
            f"URL: {intelligence.url}",
            f"Pages: {len(intelligence.pages)}",
            f"Depth: {self.options.depth}",
        ]
        lines.extend(depth_lines or ["  Depth 0: 1 page"])
        mi = intelligence.motion_intelligence
        score = (intelligence.design_intelligence.experience_score or {}).get("total")
        hover_n = len(mi.hover_motion)
        lines.extend([
            "",
            "Design:",
            "  [OK] Color / Typography / Layout",
            "",
            "Motion:",
            f"  Preloader       {'OBSERVED' if mi.preloader.observed else mi.preloader.type or 'NOT_OBSERVED'}",
            f"  Page Load       {'OBSERVED' if mi.page_load.phases else 'UNKNOWN'}",
            f"  Hero            {(mi.hero_animation or {}).get('status', 'UNKNOWN')}",
            f"  Scroll          {'OBSERVED' if mi.scrolltrigger_analysis else 'NOT_OBSERVED'}",
            f"  Scrub           {'OBSERVED' if any(getattr(f, 'scrub', None) == 'YES' for f in mi.scrolltrigger_analysis) else 'NOT_OBSERVED'}",
            f"  Parallax        {'OBSERVED' if mi.parallax else 'NOT_OBSERVED'}",
            f"  Pin             {'OBSERVED' if mi.pinning else 'NOT_OBSERVED'}",
            f"  Horizontal      {'OBSERVED' if mi.horizontal_scroll else 'NOT_OBSERVED'}",
            f"  Hover           {'OBSERVED' if hover_n else 'NOT_OBSERVED'} ({hover_n})",
            f"  Cursor          {'OBSERVED' if mi.cursor.custom_cursor else 'NOT_OBSERVED'}",
            f"  Transitions     {'OBSERVED' if any(t.observed for t in mi.page_transitions) else 'NOT_OBSERVED'}",
            "",
            f"Interactions: {candidates} candidates, {tested} tested, {state_changes} state changes",
            f"Responsive: {responsive_count} viewports",
            f"Technology: GSAP {mi.gsap_status} | ScrollTrigger {mi.scrolltrigger_status}",
            f"AI: {ai_status}",
            f"Experience Score: {score if score is not None else 'n/a'} / 100",
            f"Validation: {validation.get('overall_status', intelligence.analysis_status)}",
            "Reports: 11",
        ])
        for failure in validation.get("failures", []):
            lines.append(f"  FAILED - {failure}")
        for warning in validation.get("warnings", [])[:5]:
            lines.append(f"  WARN - {warning}")
        for err in validation.get("quality_errors", [])[:3]:
            lines.append(f"  QUALITY - {err}")
        for err in validation.get("semantic_errors", [])[:5]:
            lines.append(f"  SEMANTIC - {err}")
        lines.append(f"Output: {self.output_dir}")
        lines.append("==============================================")
        text = "\n".join(lines)
        try:
            console.print(text)
        except Exception:
            print(text.encode("ascii", "replace").decode("ascii"))

    def _save_json(self, intelligence: WebsiteIntelligence) -> None:
        data_dir = self.output_dir / "data"
        write_json(data_dir / "website.json", intelligence.model_dump(mode="json"))

        if intelligence.pages:
            write_json(
                data_dir / "pages.json",
                [p.model_dump(mode="json") for p in intelligence.pages],
            )
            write_json(
                data_dir / "components.json",
                [c.model_dump(mode="json") for p in intelligence.pages for c in p.components],
            )
            write_json(
                data_dir / "animations.json",
                [a.model_dump(mode="json") for p in intelligence.pages for a in p.animations],
            )
            write_json(
                data_dir / "interactions.json",
                [i.model_dump(mode="json") for p in intelligence.pages for i in p.interactions],
            )
            write_json(
                data_dir / "responsive.json",
                [r.model_dump(mode="json") for p in intelligence.pages for r in p.responsive],
            )
            write_json(
                data_dir / "technologies.json",
                [t.model_dump(mode="json") for t in intelligence.technologies],
            )
            if intelligence.crawl_pages:
                write_json(
                    data_dir / "crawl.json",
                    [c.model_dump(mode="json") for c in intelligence.crawl_pages],
                )
            scroll_data = [o for p in intelligence.pages for o in p.scroll_observations]
            if scroll_data:
                write_json(data_dir / "scroll.json", scroll_data)

            write_json(
                data_dir / "design.json",
                intelligence.design_intelligence.model_dump(mode="json"),
            )
            write_json(
                data_dir / "colors.json",
                intelligence.design_intelligence.color_system,
            )
            write_json(
                data_dir / "typography.json",
                intelligence.design_intelligence.typography_hierarchy,
            )

            # Prefer site-wide best preloader/page_load from motion intelligence
            mi = intelligence.motion_intelligence
            write_json(data_dir / "preloader.json", mi.preloader.model_dump(mode="json"))
            write_json(data_dir / "page_load.json", mi.page_load.model_dump(mode="json"))
            write_json(
                data_dir / "transitions.json",
                [t.model_dump(mode="json") for t in mi.page_transitions]
                or [t.model_dump(mode="json") for p in intelligence.pages for t in p.page_transitions],
            )

            from intelligence.experience_graph import build_experience_graph
            from intelligence.motion_aggregator import persist_motion_artifacts
            from intelligence.timeline_builder import build_complete_motion_timeline

            persist_motion_artifacts(intelligence, data_dir)
            graph = build_experience_graph(intelligence)
            write_json(data_dir / "experience_graph.json", graph)
            write_json(
                data_dir / "page_load_timeline.json",
                build_complete_motion_timeline(intelligence),
            )
            score = intelligence.design_intelligence.experience_score or {}
            if score:
                write_json(data_dir / "experience_score.json", score)

        self.logger.info("JSON data saved to %s", data_dir)
