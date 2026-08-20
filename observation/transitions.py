"""Safe internal page-transition observation (MPA + SPA-aware)."""

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import TransitionObservation

logger = logging.getLogger(__name__)


async def observe_page_transition(
    page,
    output_dir: Path,
    max_wait_ms: int = 3000,
) -> TransitionObservation:
    """Click a safe same-origin nav link and sample transition evidence."""
    runtime_dir = output_dir / "runtime" / "transitions"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    result = TransitionObservation(
        observed=False,
        type="NOT_OBSERVED",
        confidence=ConfidenceLevel.OBSERVED,
    )

    try:
        from_url = page.url
        link = await page.evaluate(
            """() => {
                const base = location.href;
                const basePath = location.pathname.replace(/\\/$/, '') || '/';
                const anchors = Array.from(document.querySelectorAll(
                    'nav a[href], header a[href], footer a[href], a[href]'
                ));
                for (const a of anchors) {
                    const raw = a.getAttribute('href') || '';
                    if (!raw || raw.startsWith('#') || raw.startsWith('mailto:') ||
                        raw.startsWith('tel:') || raw.startsWith('javascript:')) continue;
                    try {
                        const u = new URL(raw, base);
                        if (u.origin !== location.origin) continue;
                        const path = u.pathname.replace(/\\/$/, '') || '/';
                        if (path === basePath && !u.search) continue;
                        const r = a.getBoundingClientRect();
                        if (r.width < 2 || r.height < 2) continue;
                        return {
                            href: u.href,
                            text: (a.textContent || '').trim().slice(0, 40),
                            selectorHint: a.id ? '#' + a.id : (a.className ? a.tagName.toLowerCase() + '.' + String(a.className).split(' ')[0] : 'a'),
                        };
                    } catch (e) {}
                }
                return null;
            }"""
        )
        if not link:
            result.evidence = ["no safe internal navigation link found"]
            (runtime_dir / "transition-001.json").write_text(
                json.dumps({"status": "NOT_OBSERVED", "reason": "no_link"}, indent=2),
                encoding="utf-8",
            )
            return result

        before = await page.evaluate(
            """() => ({
                url: location.href,
                title: document.title,
                bodyOpacity: getComputedStyle(document.body).opacity,
                bodyTransform: getComputedStyle(document.body).transform,
                overlay: !!document.querySelector(
                    '[class*="transition"], [class*="page-transition"], [class*="curtain"], [class*="overlay"]'
                ),
            })"""
        )

        # Prefer href navigation for reliability
        clicked = False
        try:
            locator = page.locator(f'a[href="{link["href"]}"]')
            if await locator.count() == 0:
                # Relative href match
                path = urlparse(link["href"]).path
                locator = page.locator(f'a[href="{path}"], a[href$="{path}"]')
            await locator.first.click(timeout=3000, force=False)
            clicked = True
        except Exception:
            try:
                await page.goto(link["href"], wait_until="commit", timeout=max_wait_ms)
                clicked = True
            except Exception as exc:
                result.evidence = [f"navigation failed: {exc}"]
                return result

        await page.wait_for_timeout(250)
        mid = await page.evaluate(
            """() => ({
                url: location.href,
                bodyOpacity: getComputedStyle(document.body).opacity,
                overlay: !!document.querySelector(
                    '[class*="transition"], [class*="page-transition"], [class*="curtain"], [class*="overlay"]'
                ),
                readyState: document.readyState,
            })"""
        )
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=max_wait_ms)
        except Exception:
            pass
        await page.wait_for_timeout(400)
        after = await page.evaluate(
            """() => ({
                url: location.href,
                title: document.title,
                bodyOpacity: getComputedStyle(document.body).opacity,
            })"""
        )

        payload = {"from": before, "mid": mid, "after": after, "link": link, "clicked": clicked}
        (runtime_dir / "transition-001.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

        result.from_url = from_url
        result.to_url = after.get("url", "")
        same_path = _same_path(from_url, result.to_url)
        title_changed = (before.get("title") or "") != (after.get("title") or "")
        navigated = (not same_path) or title_changed

        if navigated:
            result.observed = True
            if mid.get("overlay") or before.get("bodyOpacity") != mid.get("bodyOpacity"):
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
            result.evidence = [
                "runtime/transitions/transition-001.json",
                "URL/title did not change after click (SPA soft nav may be opaque)",
            ]

        logger.info("[TRANSITION] type=%s observed=%s", result.type, result.observed)
    except Exception as exc:
        logger.warning("[TRANSITION] failed: %s", exc)
        result.observed = False
        result.type = "NOT_OBSERVED"
        result.confidence = ConfidenceLevel.UNKNOWN
        result.evidence = [str(exc)]

    return result


def _same_path(a: str, b: str) -> bool:
    try:
        pa, pb = urlparse(a), urlparse(b)
        return (pa.path.rstrip("/") or "/") == (pb.path.rstrip("/") or "/")
    except Exception:
        return a == b
