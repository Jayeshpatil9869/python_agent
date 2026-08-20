"""Runtime animation observation with motion trace sampling."""

import json
import logging
from pathlib import Path

from intelligence.analyzer_result import AnalyzerResult, StageStatus
from intelligence.confidence import ConfidenceLevel
from intelligence.schema import AnimationRecord

logger = logging.getLogger(__name__)

RUNTIME_OBSERVER_JS = """
async (sampleIntervalMs) => {
    const samples = [];
    const targets = Array.from(document.querySelectorAll(
        'h1, h2, .hero, [class*="hero"], [class*="reveal"], [class*="animate"], section, .card'
    )).slice(0, 8);

    const snapshot = (el, t) => {
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return {
            t,
            opacity: parseFloat(s.opacity) || 0,
            transform: s.transform,
            filter: s.filter,
            y: Math.round(r.top),
            x: Math.round(r.left),
            scale: s.transform.includes('matrix') ? s.transform : 'none',
            visibility: s.visibility,
        };
    };

    for (const el of targets) {
        const key = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
            (el.className ? '.' + String(el.className).split(' ')[0] : '');
        const trace = [];
        const intervals = [0, sampleIntervalMs, sampleIntervalMs * 2, sampleIntervalMs * 4, sampleIntervalMs * 7];
        for (const t of intervals) {
            if (t > 0) await new Promise(r => setTimeout(r, t === intervals[0] ? 0 : t - trace[trace.length - 1].t));
            trace.push(snapshot(el, t));
        }

        const first = trace[0];
        const last = trace[trace.length - 1];
        const changed = ['opacity', 'transform', 'y', 'x', 'visibility'].some(k => first[k] !== last[k]);
        if (changed) {
            let classification = 'fade';
            if (first.y !== last.y) classification = 'slide';
            if (first.transform !== last.transform && first.transform !== 'none') classification = 'scale';
            if (parseFloat(first.opacity) < parseFloat(last.opacity)) classification = 'reveal';

            samples.push({
                element: key,
                trigger: 'page_load',
                classification,
                duration_status: 'ESTIMATED',
                samples: trace,
            });
        }
    }
    return samples;
}
"""


async def observe_runtime_animations(
    page,
    output_dir: Path,
    page_slug: str = "page",
    sample_interval_ms: int = 50,
) -> tuple[list[AnimationRecord], AnalyzerResult]:
    result = AnalyzerResult(stage="animations_runtime")
    animations: list[AnimationRecord] = []
    runtime_dir = output_dir / "runtime" / "animations"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[ANIMATION] runtime motion tracing started (interval=%dms)", sample_interval_ms)

    try:
        observed = await page.evaluate(RUNTIME_OBSERVER_JS, sample_interval_ms)
        for idx, item in enumerate(observed):
            trace = item.get("samples", [])
            initial = trace[0] if trace else {}
            final = trace[-1] if trace else {}
            evidence_path = f"runtime/animations/motion-{idx:03d}.json"
            (runtime_dir / f"motion-{idx:03d}.json").write_text(
                json.dumps(item, indent=2),
                encoding="utf-8",
            )
            animations.append(
                AnimationRecord(
                    element=item.get("element", ""),
                    trigger=item.get("trigger", "page_load"),
                    initial_state=initial,
                    final_state=final,
                    duration=item.get("duration_status", "ESTIMATED"),
                    easing="UNKNOWN",
                    property="opacity, transform, position",
                    direction=item.get("classification", ""),
                    confidence=ConfidenceLevel.OBSERVED,
                    evidence=[evidence_path, "runtime motion trace"],
                )
            )
        result.metrics["runtime_observations"] = len(animations)
        result.metrics["motion_traces"] = len(observed)
    except Exception as exc:
        result.mark_failed(str(exc))
        logger.warning("[ANIMATION] runtime observation failed: %s", exc)
        return animations, result

    if animations:
        result.status = StageStatus.SUCCESS
    else:
        result.mark_no_data("No runtime animation changes observed on sampled elements")

    logger.info("[ANIMATION] runtime motion traces: %d", len(animations))
    return animations, result
