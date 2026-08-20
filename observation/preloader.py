"""Preloader observation — sample early page states after navigation."""

import json
import logging
from pathlib import Path

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import PreloaderObservation

logger = logging.getLogger(__name__)

PRELOADER_SELECTORS = (
    "[class*='loader'], [class*='preloader'], [class*='loading'], "
    "[id*='loader'], [id*='preloader'], [class*='splash'], "
    "[aria-busy='true'], .progress, [class*='progress']"
)

SNAPSHOT_JS = """
(selectors) => {
    const body = document.body;
    const html = document.documentElement;
    const candidates = Array.from(document.querySelectorAll(selectors)).slice(0, 8);
    const overlays = candidates.map(el => {
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return {
            key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                (el.className ? '.' + String(el.className).split(' ')[0] : ''),
            display: s.display,
            visibility: s.visibility,
            opacity: s.opacity,
            transform: s.transform,
            zIndex: s.zIndex,
            position: s.position,
            width: Math.round(r.width),
            height: Math.round(r.height),
            coversViewport: r.width >= window.innerWidth * 0.9 && r.height >= window.innerHeight * 0.9,
            text: (el.textContent || '').trim().slice(0, 40),
        };
    });
    const pctMatch = (document.body.innerText || '').match(/\\b(\\d{1,3})\\s*%/);
    return {
        readyState: document.readyState,
        bodyOverflow: getComputedStyle(body).overflow,
        htmlOverflow: getComputedStyle(html).overflow,
        bodyBg: getComputedStyle(body).backgroundColor,
        percentageText: pctMatch ? pctMatch[0] : null,
        overlays,
        fixedFullScreen: overlays.filter(o => o.coversViewport &&
            (o.position === 'fixed' || o.position === 'absolute') &&
            o.display !== 'none' && o.visibility !== 'hidden' && parseFloat(o.opacity) > 0.05),
    };
}
"""


async def observe_preloader(
    page,
    url: str,
    output_dir: Path,
    sample_ms: int = 200,
    max_samples: int = 12,
) -> PreloaderObservation:
    """Reload page and sample early frames for preloader presence."""
    result = PreloaderObservation()
    runtime_dir = output_dir / "runtime" / "preloader"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    timeline: list[dict] = []

    logger.info("[PRELOADER] observation started")
    try:
        await page.goto(url, wait_until="commit", timeout=45000)
        for i in range(max_samples):
            t = i * sample_ms
            snap = await page.evaluate(SNAPSHOT_JS, PRELOADER_SELECTORS)
            entry = {"t": t, **snap}
            timeline.append(entry)
            (runtime_dir / f"sample-{t:04d}.json").write_text(
                json.dumps(entry, indent=2), encoding="utf-8"
            )
            await page.wait_for_timeout(sample_ms)

        # Wait for network idle-ish after sampling
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        evidence = [f"runtime/preloader/sample-{e['t']:04d}.json" for e in timeline[:3]]
        evidence.append(f"runtime/preloader/sample-{timeline[-1]['t']:04d}.json")

        early = timeline[0] if timeline else {}
        late = timeline[-1] if timeline else {}
        early_overlays = early.get("fixedFullScreen") or []
        late_overlays = late.get("fixedFullScreen") or []
        had_overlay = len(early_overlays) > 0
        overlay_gone = had_overlay and len(late_overlays) == 0
        pct_values = [s.get("percentageText") for s in timeline if s.get("percentageText")]
        pct_changing = len(set(pct_values)) > 1
        had_pct = pct_changing

        if had_overlay or had_pct:
            result.observed = True
            result.confidence = ConfidenceLevel.OBSERVED
            if had_pct:
                result.type = "percentage_loader"
                result.progress_behavior = "percentage counter observed"
            elif early_overlays:
                result.type = "fullscreen_overlay"
                result.progress_behavior = "fullscreen overlay present then dismissed" if overlay_gone else "overlay persisted"
            else:
                result.type = "loader_candidate"

            exit_t = None
            for s in timeline:
                if had_overlay and not (s.get("fixedFullScreen") or []):
                    exit_t = s["t"]
                    break
            result.duration_ms = exit_t if exit_t is not None else timeline[-1]["t"] if timeline else None
            result.duration_status = "OBSERVED" if exit_t is not None else "ESTIMATED"
            result.initial_state = {
                "overlays": early_overlays,
                "body_bg": early.get("bodyBg"),
                "percentage": early.get("percentageText"),
            }
            result.exit_animation = "overlay dismissed" if overlay_gone else "UNKNOWN"
            result.timeline = [
                {"t": s["t"], "overlays": len(s.get("fixedFullScreen") or []), "pct": s.get("percentageText")}
                for s in timeline
            ]
            result.evidence = evidence
        else:
            result.observed = False
            result.type = "NOT_OBSERVED"
            result.confidence = ConfidenceLevel.OBSERVED
            result.timeline = [{"t": s["t"], "overlays": 0} for s in timeline[:4]]
            result.evidence = evidence[:2]
            result.duration_status = "UNKNOWN"

        (runtime_dir / "summary.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info("[PRELOADER] observed=%s type=%s", result.observed, result.type)
    except Exception as exc:
        logger.warning("[PRELOADER] failed: %s", exc)
        result.confidence = ConfidenceLevel.UNKNOWN
        result.evidence = [str(exc)]

    return result
