"""Scroll behavior observation with scroll-linked motion detection."""

import json
import logging
from pathlib import Path

from observation.screenshot import capture_viewport

logger = logging.getLogger(__name__)

TRACKED_SELECTORS = "header, .hero, [class*='hero'], section, h1, [data-parallax]"


async def observe_scroll(page, output_dir: Path, steps: int = 11) -> list[dict]:
    observations: list[dict] = []
    runtime_dir = output_dir / "runtime" / "scroll"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    try:
        scroll_height = await page.evaluate("() => document.documentElement.scrollHeight")
        viewport_height = await page.evaluate("() => window.innerHeight")
        max_scroll = max(0, scroll_height - viewport_height)

        prev_positions: dict[str, float] = {}

        for i in range(steps):
            pct = i / (steps - 1) if steps > 1 else 0
            scroll_y = int(max_scroll * pct)
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await page.wait_for_timeout(400)

            snapshot = await page.evaluate(
                f"""() => {{
                    const tracked = Array.from(document.querySelectorAll('{TRACKED_SELECTORS}')).slice(0, 8);
                    const elements = tracked.map(el => {{
                        const r = el.getBoundingClientRect();
                        const s = getComputedStyle(el);
                        return {{
                            key: el.tagName + (el.id ? '#' + el.id : '') + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                            top: Math.round(r.top),
                            transform: s.transform,
                            position: s.position,
                        }};
                    }});
                    const sticky = Array.from(document.querySelectorAll('*')).filter(el => {{
                        return getComputedStyle(el).position === 'sticky' &&
                            el.getBoundingClientRect().top <= 1;
                    }}).map(el => el.tagName + (el.id ? '#' + el.id : ''));
                    const fixed = Array.from(document.querySelectorAll('*')).filter(el =>
                        getComputedStyle(el).position === 'fixed'
                    ).map(el => el.tagName + (el.id ? '#' + el.id : '')).slice(0, 5);
                    return {{
                        scrollY: window.scrollY,
                        elements,
                        sticky,
                        fixed,
                    }};
                }}"""
            )

            scroll_linked: list[dict] = []
            for el in snapshot.get("elements", []):
                key = el.get("key", "")
                top = el.get("top", 0)
                prev = prev_positions.get(key)
                if prev is not None and scroll_y > 0:
                    delta_y = top - prev
                    scroll_delta = scroll_y - (observations[-1]["scroll_y"] if observations else 0)
                    if scroll_delta > 0:
                        ratio = delta_y / scroll_delta if scroll_delta else 0
                        classification = "normal"
                        if el.get("position") == "sticky" or key in snapshot.get("sticky", []):
                            classification = "sticky"
                        elif el.get("position") == "fixed" or key in snapshot.get("fixed", []):
                            classification = "fixed"
                        elif ratio < -0.3:
                            classification = "parallax"
                        elif ratio > 0.1:
                            classification = "scroll-linked"
                        scroll_linked.append(
                            {
                                "element": key,
                                "delta_y": delta_y,
                                "scroll_delta": scroll_delta,
                                "ratio": round(ratio, 3),
                                "classification": classification,
                            }
                        )
                prev_positions[key] = top

            screenshot_path = output_dir / "screenshots" / "scroll" / f"scroll-{int(pct * 100):03d}.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            await capture_viewport(page, screenshot_path)

            observation = {
                "percent": int(pct * 100),
                "scroll_y": snapshot.get("scrollY", scroll_y),
                "sticky_elements": snapshot.get("sticky", []),
                "fixed_elements": snapshot.get("fixed", []),
                "scroll_linked_motion": scroll_linked,
                "screenshot": f"screenshots/scroll/scroll-{int(pct * 100):03d}.png",
            }
            observations.append(observation)

            trace_path = runtime_dir / f"scroll-{int(pct * 100):03d}.json"
            trace_path.write_text(json.dumps(observation, indent=2), encoding="utf-8")

        await page.evaluate("window.scrollTo(0, 0)")
        logger.info("[SCROLL] completed %d steps, scroll-linked samples collected", len(observations))
    except Exception as exc:
        logger.warning("[SCROLL] observation failed: %s", exc)
        observations.append({"error": str(exc)})

    return observations
