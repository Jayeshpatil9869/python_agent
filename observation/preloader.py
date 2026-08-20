"""Preloader observation with strict evidence requirements."""

import json
import logging
import re
from pathlib import Path

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import PreloaderObservation

logger = logging.getLogger(__name__)

PRELOADER_SELECTORS = (
    "[class*='loader'], [class*='preloader'], [class*='loading'], "
    "[id*='loader'], [id*='preloader'], [class*='splash'], "
    "[aria-busy='true'], [class*='progress-bar'], [class*='progress__']"
)

SNAPSHOT_JS = """
(selectors) => {
    if (!document.body || !document.documentElement) {
        return {
            readyState: document.readyState,
            bodyOverflow: null,
            bodyBg: null,
            percentageText: null,
            overlays: [],
            fixedFullScreen: [],
        };
    }
    const body = document.body;
    const html = document.documentElement;
    const candidates = Array.from(document.querySelectorAll(selectors)).slice(0, 12);
    const overlays = candidates.map(el => {
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        const z = parseInt(s.zIndex, 10);
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
            coversViewport: r.width >= window.innerWidth * 0.85 && r.height >= window.innerHeight * 0.85,
            highZ: !Number.isNaN(z) && z >= 50,
            text: (el.textContent || '').trim().slice(0, 60),
        };
    }).filter(Boolean);

    // Prefer percentage text inside loader candidates, not whole body
    let percentageText = null;
    for (const el of candidates) {
        const m = (el.textContent || '').match(/\\b(\\d{1,3})\\s*%/);
        if (m) { percentageText = m[0]; break; }
    }

    const active = overlays.filter(o =>
        o.coversViewport &&
        (o.position === 'fixed' || o.position === 'absolute') &&
        o.display !== 'none' &&
        o.visibility !== 'hidden' &&
        parseFloat(o.opacity) > 0.05 &&
        (o.highZ || true)
    );

    return {
        readyState: document.readyState,
        bodyOverflow: getComputedStyle(body).overflow,
        bodyBg: getComputedStyle(body).backgroundColor,
        percentageText,
        overlays,
        fixedFullScreen: active,
    };
}
"""


def _parse_pct(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"(\d{1,3})", value)
    return int(m.group(1)) if m else None


async def observe_preloader(
    page,
    url: str,
    output_dir: Path,
    sample_ms: int = 150,
    max_samples: int = 16,
) -> PreloaderObservation:
    """Sample early frames. Require overlay dismissal or changing loader percentage."""
    result = PreloaderObservation(
        observed=False,
        type="NOT_OBSERVED",
        confidence=ConfidenceLevel.OBSERVED,
        duration_status="UNKNOWN",
    )
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

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

        evidence = [f"runtime/preloader/sample-{e['t']:04d}.json" for e in timeline[:3]]
        if timeline:
            evidence.append(f"runtime/preloader/sample-{timeline[-1]['t']:04d}.json")

        overlay_counts = [len(s.get("fixedFullScreen") or []) for s in timeline]
        had_overlay = any(c > 0 for c in overlay_counts)
        overlay_gone = had_overlay and overlay_counts[-1] == 0

        pct_nums = [_parse_pct(s.get("percentageText")) for s in timeline]
        pct_present = [p for p in pct_nums if p is not None]
        pct_changing = len(set(pct_present)) >= 2 and max(pct_present) > min(pct_present)
        # Require progress to move meaningfully (not stuck at 0)
        pct_progressed = pct_changing and max(pct_present) >= 5

        # Strict: overlay that later dismisses, OR percentage that advances inside loader
        valid = (had_overlay and overlay_gone) or (had_overlay and pct_progressed) or pct_progressed

        result.timeline = [
            {
                "t": s["t"],
                "overlays": len(s.get("fixedFullScreen") or []),
                "pct": s.get("percentageText"),
            }
            for s in timeline
        ]
        result.evidence = evidence
        result.initial_state = {
            "overlays": (timeline[0].get("fixedFullScreen") if timeline else []) or [],
            "body_bg": timeline[0].get("bodyBg") if timeline else None,
            "percentage": timeline[0].get("percentageText") if timeline else None,
        }

        if valid:
            result.observed = True
            result.confidence = ConfidenceLevel.OBSERVED
            if pct_progressed:
                result.type = "percentage_loader"
                result.progress_behavior = f"percentage advanced {min(pct_present)}% → {max(pct_present)}%"
            else:
                result.type = "fullscreen_overlay"
                result.progress_behavior = "fullscreen overlay present then dismissed"

            exit_t = None
            for s in timeline:
                if had_overlay and not (s.get("fixedFullScreen") or []):
                    exit_t = s["t"]
                    break
            result.duration_ms = exit_t if exit_t is not None else (timeline[-1]["t"] if timeline else None)
            result.duration_status = "OBSERVED" if exit_t is not None else "ESTIMATED"
            result.exit_animation = "overlay dismissed" if overlay_gone else "UNKNOWN"
        else:
            result.observed = False
            result.type = "NOT_OBSERVED"
            # Record near-miss for debugging without claiming observation
            if had_overlay and not overlay_gone:
                result.progress_behavior = "overlay candidates persisted (not confirmed as preloader exit)"
            elif pct_present and not pct_progressed:
                result.progress_behavior = "static percentage text found but did not progress"

        (runtime_dir / "summary.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info("[PRELOADER] observed=%s type=%s", result.observed, result.type)
    except Exception as exc:
        logger.warning("[PRELOADER] failed: %s", exc)
        result.confidence = ConfidenceLevel.UNKNOWN
        result.evidence = [str(exc)]

    return result
