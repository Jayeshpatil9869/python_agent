"""Page-load choreography via init-script early capture (before first paint animations finish)."""

import json
import logging
from pathlib import Path

from intelligence.schema import PageLoadTimeline

logger = logging.getLogger(__name__)

# Installed before navigation so samples exist from first script opportunity.
INIT_TRACE_JS = """
(() => {
  if (window.__wiaPageLoadInstalled) return;
  window.__wiaPageLoadInstalled = true;
  window.__wiaPageLoadTrace = [];
  window.__wiaPageLoadStart = performance.now();

  const pick = (sel) => document.querySelector(sel);
  const snap = (el) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
        (el.className ? '.' + String(el.className).split(' ')[0] : ''),
      opacity: s.opacity,
      transform: s.transform,
      visibility: s.visibility,
      top: Math.round(r.top),
      height: Math.round(r.height),
      clipPath: s.clipPath || 'none',
      filter: s.filter || 'none',
    };
  };

  const sample = () => {
    try {
      if (!document.body) return;
      window.__wiaPageLoadTrace.push({
        t: Math.round(performance.now() - window.__wiaPageLoadStart),
        readyState: document.readyState,
        nav: snap(pick('nav, header nav, [role="navigation"]')),
        hero: snap(pick('#hero, .hero, [class*="hero"], main > section:first-child, section:first-of-type')),
        h1: snap(pick('h1')),
        cta: snap(pick('a.btn, .cta, [class*="cta"], button')),
        media: snap(pick('#hero img, .hero img, [class*="hero"] img, #hero video, .hero video, main img')),
      });
    } catch (e) {}
  };

  sample();
  const id = setInterval(sample, 50);
  const stop = () => clearInterval(id);
  setTimeout(stop, 3500);
  document.addEventListener('DOMContentLoaded', sample);
  window.addEventListener('load', sample);
})();
"""

MEANINGFUL_KEYS = ("opacity", "transform", "clipPath", "visibility", "filter")


def _meaningful_change(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    # Ignore tiny top jitter (< 8px) as layout thrash
    top_delta = abs((a.get("top") or 0) - (b.get("top") or 0))
    style_changed = any(a.get(k) != b.get(k) for k in MEANINGFUL_KEYS)
    return style_changed or top_delta >= 8


def _opacity(el: dict | None) -> float:
    if not el:
        return 1.0
    try:
        return float(el.get("opacity") or 1)
    except Exception:
        return 1.0


async def install_page_load_tracer(page) -> None:
    """Call before navigation so early frames are recorded."""
    await page.add_init_script(INIT_TRACE_JS)


async def observe_page_load(
    page,
    output_dir: Path,
    wait_ms: int = 2800,
    url: str | None = None,
) -> PageLoadTimeline:
    """
    Collect early page-load timeline.

    Prefer init-script buffer. If empty (script blocked), fall back to post-nav sampling.
    Optionally pass url to navigate after installing tracer.
    """
    timeline = PageLoadTimeline()
    runtime_dir = output_dir / "runtime" / "page-load"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    logger.info("[PAGE-LOAD] observation started")
    try:
        await install_page_load_tracer(page)

        if url:
            await page.goto(url, wait_until="commit", timeout=45000)

        await page.wait_for_timeout(wait_ms)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass

        phases = await page.evaluate("() => window.__wiaPageLoadTrace || []")
        if not phases:
            # Fallback: active sampling (late, but better than empty)
            phases = await _fallback_sample(page)

        for p in phases:
            t = int(p.get("t") or 0)
            (runtime_dir / f"t-{t:04d}.json").write_text(
                json.dumps(p, indent=2), encoding="utf-8"
            )

        hero_anim = {"status": "NOT_OBSERVED"}
        nav_anim = {"status": "NOT_OBSERVED"}

        if phases:
            first = phases[0]
            last = phases[-1]
            # Find earliest low-opacity hero/h1 and latest settled state
            h1_series = [p.get("h1") for p in phases if p.get("h1")]
            hero_series = [p.get("hero") for p in phases if p.get("hero")]
            nav_series = [p.get("nav") for p in phases if p.get("nav")]

            target_series = h1_series or hero_series
            if target_series and len(target_series) >= 2:
                start = target_series[0]
                end = target_series[-1]
                # Prefer a frame where opacity was low as true initial
                for sample in target_series:
                    if _opacity(sample) < 0.95:
                        start = sample
                        break
                if _meaningful_change(start, end) or (_opacity(start) < 0.95 and _opacity(end) >= 0.99):
                    reveal_t = None
                    for p in phases:
                        el = p.get("h1") or p.get("hero")
                        if el and _opacity(el) >= 0.99:
                            reveal_t = p.get("t")
                            break
                    hero_anim = {
                        "status": "OBSERVED",
                        "element": end.get("key", "hero"),
                        "initial": start,
                        "final": end,
                        "trigger": "page_load",
                        "duration_status": "OBSERVED" if reveal_t is not None else "ESTIMATED",
                        "reveal_at_ms": reveal_t,
                        "duration_ms": reveal_t if reveal_t is not None else (last.get("t") if last else None),
                    }

            if nav_series and len(nav_series) >= 2:
                n0, n1 = nav_series[0], nav_series[-1]
                if _meaningful_change(n0, n1) and (
                    any(n0.get(k) != n1.get(k) for k in MEANINGFUL_KEYS)
                    or abs((n0.get("top") or 0) - (n1.get("top") or 0)) >= 8
                ):
                    nav_anim = {
                        "status": "OBSERVED",
                        "element": n1.get("key", "nav"),
                        "initial": n0,
                        "final": n1,
                        "trigger": "page_load",
                        "duration_status": "ESTIMATED",
                    }

        timeline.phases = [
            {
                "t": p.get("t"),
                "readyState": p.get("readyState"),
                "h1_opacity": (p.get("h1") or {}).get("opacity"),
                "nav_opacity": (p.get("nav") or {}).get("opacity"),
                "hero_opacity": (p.get("hero") or {}).get("opacity"),
            }
            for p in phases
        ]
        timeline.hero_animation = hero_anim
        timeline.navigation_animation = nav_anim
        timeline.total_duration_ms = phases[-1].get("t") if phases else wait_ms
        timeline.duration_status = "OBSERVED" if hero_anim.get("status") == "OBSERVED" else "ESTIMATED"
        timeline.evidence = [
            f"runtime/page-load/t-{int(phases[0].get('t') or 0):04d}.json" if phases else "runtime/page-load/",
            f"runtime/page-load/t-{int(phases[-1].get('t') or 0):04d}.json" if phases else "runtime/page-load/",
            "init_script_trace",
        ]

        (runtime_dir / "summary.json").write_text(
            timeline.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info(
            "[PAGE-LOAD] samples=%d hero=%s nav=%s",
            len(phases),
            hero_anim.get("status"),
            nav_anim.get("status"),
        )
    except Exception as exc:
        logger.warning("[PAGE-LOAD] failed: %s", exc)
        timeline.evidence = [str(exc)]

    return timeline


async def _fallback_sample(page) -> list[dict]:
    samples = []
    js = """() => {
        const pick = (sel) => document.querySelector(sel);
        const snap = (el) => {
            if (!el) return null;
            const s = getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return {
                key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                    (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                opacity: s.opacity, transform: s.transform, visibility: s.visibility,
                top: Math.round(r.top), height: Math.round(r.height),
                clipPath: s.clipPath || 'none', filter: s.filter || 'none',
            };
        };
        return {
            readyState: document.readyState,
            nav: snap(pick('nav, header nav, [role="navigation"]')),
            hero: snap(pick('#hero, .hero, [class*="hero"], main > section:first-child')),
            h1: snap(pick('h1')),
            cta: snap(pick('a.btn, .cta, button')),
            media: snap(pick('main img, .hero img')),
        };
    }"""
    for i in range(12):
        snap = await page.evaluate(js)
        samples.append({"t": i * 100, **snap})
        await page.wait_for_timeout(100)
    return samples
