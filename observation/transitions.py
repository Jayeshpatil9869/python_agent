"""Safe internal page-transition observation."""

import json
import logging
from pathlib import Path

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import TransitionObservation

logger = logging.getLogger(__name__)


async def observe_page_transition(
    page,
    output_dir: Path,
    max_wait_ms: int = 2500,
) -> TransitionObservation | None:
    """Click a safe same-origin nav link and sample transition evidence."""
    runtime_dir = output_dir / "runtime" / "transitions"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    result = TransitionObservation()

    try:
        from_url = page.url
        link = await page.evaluate(
            """() => {
                const anchors = Array.from(document.querySelectorAll('nav a[href], header a[href], a[href]'));
                for (const a of anchors) {
                    const href = a.getAttribute('href') || '';
                    if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) continue;
                    if (href.startsWith('javascript:')) continue;
                    try {
                        const u = new URL(href, location.href);
                        if (u.origin !== location.origin) continue;
                        if (u.pathname === location.pathname) continue;
                        return { href: u.href, text: (a.textContent || '').trim().slice(0, 40) };
                    } catch (e) {}
                }
                return null;
            }"""
        )
        if not link:
            result.observed = False
            result.type = "NOT_OBSERVED"
            result.confidence = ConfidenceLevel.OBSERVED
            result.evidence = ["no safe internal navigation link found"]
            return result

        before = await page.evaluate(
            """() => ({
                url: location.href,
                bodyOpacity: getComputedStyle(document.body).opacity,
                bodyTransform: getComputedStyle(document.body).transform,
                overlay: !!document.querySelector('[class*="transition"], [class*="page-transition"], [class*="overlay"]'),
            })"""
        )

        await page.locator(f'a[href="{link["href"]}"], a[href*="{Path(link["href"]).name}"]').first.click(timeout=3000)
        await page.wait_for_timeout(200)
        mid = await page.evaluate(
            """() => ({
                url: location.href,
                bodyOpacity: getComputedStyle(document.body).opacity,
                overlay: !!document.querySelector('[class*="transition"], [class*="page-transition"], [class*="overlay"]'),
                readyState: document.readyState,
            })"""
        )
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=max_wait_ms)
        except Exception:
            pass
        await page.wait_for_timeout(300)
        after = await page.evaluate(
            """() => ({
                url: location.href,
                bodyOpacity: getComputedStyle(document.body).opacity,
                title: document.title,
            })"""
        )

        payload = {"from": before, "mid": mid, "after": after, "link": link}
        (runtime_dir / "transition-001.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

        result.from_url = from_url
        result.to_url = after.get("url", "")
        navigated = after.get("url") and after.get("url") != from_url
        if navigated:
            result.observed = True
            if mid.get("overlay") or (before.get("bodyOpacity") != mid.get("bodyOpacity")):
                result.type = "overlay_or_fade_candidate"
                result.confidence = ConfidenceLevel.INFERRED
                result.sequence = ["exit_candidate", "navigation", "enter"]
            else:
                result.type = "standard_navigation"
                result.confidence = ConfidenceLevel.OBSERVED
                result.sequence = ["click", "navigation"]
            result.evidence = ["runtime/transitions/transition-001.json"]
        else:
            result.observed = False
            result.type = "NOT_OBSERVED"
            result.confidence = ConfidenceLevel.OBSERVED
            result.evidence = ["click did not navigate; SPA transition may be opaque"]

        logger.info("[TRANSITION] type=%s observed=%s", result.type, result.observed)
    except Exception as exc:
        logger.warning("[TRANSITION] failed: %s", exc)
        result.observed = False
        result.type = "NOT_OBSERVED"
        result.confidence = ConfidenceLevel.UNKNOWN
        result.evidence = [str(exc)]

    return result
