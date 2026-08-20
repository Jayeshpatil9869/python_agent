"""Preloader forensics with overlay classification and longer observation windows."""

from __future__ import annotations

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
    "[aria-busy='true'], [class*='progress-bar'], [class*='progress__'], "
    "[class*='cookie'], [id*='cookie'], [class*='consent'], "
    "[role='dialog'], [class*='modal'], [class*='overlay']"
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
            classified: [],
        };
    }
    const body = document.body;
    const candidates = Array.from(document.querySelectorAll(selectors)).slice(0, 16);
    const overlays = candidates.map(el => {
        if (!el) return null;
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        const z = parseInt(s.zIndex, 10);
        const text = (el.textContent || '').trim().slice(0, 80);
        const cls = ((el.className && String(el.className)) || '') + ' ' + (el.id || '');
        const key = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
            (el.className ? '.' + String(el.className).split(' ')[0] : '');
        const coversViewport = r.width >= window.innerWidth * 0.85 && r.height >= window.innerHeight * 0.85;
        const visible = s.display !== 'none' && s.visibility !== 'hidden' && parseFloat(s.opacity) > 0.05;
        const positioned = s.position === 'fixed' || s.position === 'absolute';
        let kind = 'UNKNOWN_OVERLAY';
        const lower = (cls + ' ' + text).toLowerCase();
        if (/cookie|consent|gdpr|privacy/.test(lower)) kind = 'COOKIE_BANNER';
        else if (/modal|dialog|popup/.test(lower) && !coversViewport) kind = 'MODAL';
        else if (/loader|preloader|loading|splash|progress/.test(lower)) kind = 'PRELOADER_CANDIDATE';
        else if (coversViewport && positioned) kind = 'LOADING_OVERLAY';
        return {
            key,
            kind,
            display: s.display,
            visibility: s.visibility,
            opacity: s.opacity,
            transform: s.transform,
            zIndex: s.zIndex,
            position: s.position,
            width: Math.round(r.width),
            height: Math.round(r.height),
            coversViewport,
            highZ: !Number.isNaN(z) && z >= 50,
            text,
            visible,
            positioned,
        };
    }).filter(Boolean);

    let percentageText = null;
    for (const el of candidates) {
        const m = (el.textContent || '').match(/\\b(\\d{1,3})\\s*%/);
        if (m) { percentageText = m[0]; break; }
    }

    const active = overlays.filter(o =>
        o.coversViewport &&
        o.positioned &&
        o.visible &&
        o.kind !== 'COOKIE_BANNER' &&
        o.kind !== 'MODAL'
    );

    return {
        readyState: document.readyState,
        bodyOverflow: getComputedStyle(body).overflow,
        bodyBg: getComputedStyle(body).backgroundColor,
        percentageText,
        overlays,
        fixedFullScreen: active,
        classified: overlays.filter(o => o.visible).map(o => ({ key: o.key, kind: o.kind })),
    };
}
"""


def _parse_pct(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"(\d{1,3})", value)
    return int(m.group(1)) if m else None


def _classify_persistent_overlay(timeline: list[dict]) -> str:
    """When overlay never exits, classify without claiming PRELOADER."""
    kinds: list[str] = []
    for s in timeline:
        for item in s.get("classified") or []:
            kinds.append(item.get("kind") or "UNKNOWN_OVERLAY")
        for o in s.get("fixedFullScreen") or []:
            kinds.append(o.get("kind") or "LOADING_OVERLAY")
    if not kinds:
        return "NOT_OBSERVED"
    if kinds.count("COOKIE_BANNER") >= max(1, len(kinds) // 3):
        return "COOKIE_BANNER"
    if "PRELOADER_CANDIDATE" in kinds or "LOADING_OVERLAY" in kinds:
        return "UNKNOWN_OVERLAY"
    return "UNKNOWN_OVERLAY"


async def observe_preloader(
    page,
    url: str,
    output_dir: Path,
    sample_ms: int = 200,
    max_samples: int = 24,
) -> PreloaderObservation:
    """
    Sample early frames over a longer window (~4.8s default).

    Require overlay dismissal or advancing loader percentage to claim PRELOADER.
    Persistent overlays are classified separately (COOKIE / UNKNOWN), not as preloaders.
    """
    result = PreloaderObservation(
        observed=False,
        type="NOT_OBSERVED",
        confidence=ConfidenceLevel.OBSERVED,
        duration_status="UNKNOWN",
    )
    runtime_dir = output_dir / "runtime" / "preloader"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    timeline: list[dict] = []

    logger.info("[PRELOADER] observation started (window=%dms)", sample_ms * max_samples)
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

        # Extra late sample after load for delayed dismissals
        try:
            await page.wait_for_load_state("load", timeout=8000)
        except Exception:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
        await page.wait_for_timeout(600)
        late = await page.evaluate(SNAPSHOT_JS, PRELOADER_SELECTORS)
        late_t = (timeline[-1]["t"] + 600) if timeline else 600
        late_entry = {"t": late_t, **late}
        timeline.append(late_entry)
        (runtime_dir / f"sample-{late_t:04d}.json").write_text(
            json.dumps(late_entry, indent=2), encoding="utf-8"
        )

        evidence = [f"runtime/preloader/sample-{e['t']:04d}.json" for e in timeline[:3]]
        if timeline:
            evidence.append(f"runtime/preloader/sample-{timeline[-1]['t']:04d}.json")

        overlay_counts = [len(s.get("fixedFullScreen") or []) for s in timeline]
        had_overlay = any(c > 0 for c in overlay_counts)
        overlay_gone = had_overlay and overlay_counts[-1] == 0

        # Detect mid-window disappearance even if a different overlay reappears
        first_overlay_idx = next((i for i, c in enumerate(overlay_counts) if c > 0), None)
        first_gone_idx = None
        if first_overlay_idx is not None:
            for i in range(first_overlay_idx + 1, len(overlay_counts)):
                if overlay_counts[i] == 0:
                    first_gone_idx = i
                    break
        mid_dismissed = first_gone_idx is not None

        pct_nums = [_parse_pct(s.get("percentageText")) for s in timeline]
        pct_present = [p for p in pct_nums if p is not None]
        pct_changing = len(set(pct_present)) >= 2 and max(pct_present) > min(pct_present)
        pct_progressed = pct_changing and max(pct_present) >= 5

        # Opacity/transform exit on labeled preloader candidates
        style_exit = _detect_style_exit(timeline)

        valid = (
            (had_overlay and overlay_gone)
            or (had_overlay and mid_dismissed)
            or (had_overlay and pct_progressed)
            or pct_progressed
            or style_exit
        )

        result.timeline = [
            {
                "t": s["t"],
                "overlays": len(s.get("fixedFullScreen") or []),
                "pct": s.get("percentageText"),
                "classified": s.get("classified") or [],
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
                result.progress_behavior = (
                    f"percentage advanced {min(pct_present)}% → {max(pct_present)}%"
                )
            elif style_exit:
                result.type = "fullscreen_overlay"
                result.progress_behavior = "preloader candidate style exit OBSERVED"
            else:
                result.type = "fullscreen_overlay"
                result.progress_behavior = "fullscreen overlay present then dismissed"

            exit_t = None
            if first_gone_idx is not None:
                exit_t = timeline[first_gone_idx]["t"]
            else:
                for s in timeline:
                    if had_overlay and not (s.get("fixedFullScreen") or []):
                        exit_t = s["t"]
                        break
            result.duration_ms = exit_t if exit_t is not None else (timeline[-1]["t"] if timeline else None)
            result.duration_status = "OBSERVED" if exit_t is not None else "ESTIMATED"
            result.exit_animation = "overlay dismissed" if (overlay_gone or mid_dismissed) else "UNKNOWN"
        else:
            result.observed = False
            if had_overlay and not overlay_gone and not mid_dismissed:
                kind = _classify_persistent_overlay(timeline)
                result.type = kind
                result.progress_behavior = (
                    f"persistent overlay classified as {kind} (not confirmed preloader exit)"
                )
            elif pct_present and not pct_progressed:
                result.type = "NOT_OBSERVED"
                result.progress_behavior = "static percentage text found but did not progress"
            else:
                result.type = "NOT_OBSERVED"

        (runtime_dir / "summary.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info("[PRELOADER] observed=%s type=%s", result.observed, result.type)
    except Exception as exc:
        logger.warning("[PRELOADER] failed: %s", exc)
        result.confidence = ConfidenceLevel.UNKNOWN
        result.evidence = [str(exc)]

    return result


def _detect_style_exit(timeline: list[dict]) -> bool:
    """True if a PRELOADER_CANDIDATE goes from visible/opaque to hidden/transparent."""
    by_key: dict[str, list[dict]] = {}
    for s in timeline:
        for o in s.get("overlays") or []:
            if o.get("kind") not in ("PRELOADER_CANDIDATE", "LOADING_OVERLAY"):
                continue
            by_key.setdefault(o.get("key") or "?", []).append(
                {
                    "t": s.get("t"),
                    "opacity": float(o.get("opacity") or 0),
                    "visible": bool(o.get("visible")),
                    "covers": bool(o.get("coversViewport")),
                }
            )
    for samples in by_key.values():
        if len(samples) < 2:
            continue
        start, end = samples[0], samples[-1]
        if start["covers"] and start["opacity"] > 0.4 and (
            not end["visible"] or end["opacity"] < 0.1 or not end["covers"]
        ):
            return True
    return False
