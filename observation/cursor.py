"""Custom cursor and magnetic interaction observation."""

import json
import logging
from pathlib import Path

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import CursorObservation

logger = logging.getLogger(__name__)

CURSOR_DETECT_JS = """
() => {
    const bodyCursor = getComputedStyle(document.body).cursor;
    const htmlCursor = getComputedStyle(document.documentElement).cursor;
    const candidates = Array.from(document.querySelectorAll(
        '[class*="cursor"], [id*="cursor"], [class*="pointer-follower"], [class*="mouse"], [data-cursor]'
    )).slice(0, 10).map(el => {
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return {
            key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                (el.className ? '.' + String(el.className).split(' ')[0] : ''),
            position: s.position,
            pointerEvents: s.pointerEvents,
            mixBlendMode: s.mixBlendMode,
            transform: s.transform,
            width: Math.round(r.width),
            height: Math.round(r.height),
            opacity: s.opacity,
            zIndex: s.zIndex,
        };
    });
    const hiddenNative = bodyCursor === 'none' || htmlCursor === 'none';
    const follower = candidates.find(c =>
        (c.position === 'fixed' || c.position === 'absolute') && c.width > 0 && c.width < 120
    );
    return {
        bodyCursor,
        htmlCursor,
        hiddenNative,
        candidates,
        follower: follower || null,
        magneticAttrs: document.querySelector('[data-magnetic], [class*="magnetic"]') !== null,
    };
}
"""


async def observe_cursor(page, output_dir: Path) -> CursorObservation:
    result = CursorObservation()
    runtime_dir = output_dir / "runtime" / "cursor"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = await page.evaluate(CURSOR_DETECT_JS)
        (runtime_dir / "cursor.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

        if data.get("hiddenNative") and data.get("follower"):
            result.custom_cursor = True
            result.cursor_type = "custom_follower"
            result.confidence = ConfidenceLevel.OBSERVED
            result.details = {
                "size": {"w": data["follower"].get("width"), "h": data["follower"].get("height")},
                "blend": data["follower"].get("mixBlendMode"),
                "element": data["follower"].get("key"),
            }
        elif data.get("follower"):
            result.custom_cursor = True
            result.cursor_type = "cursor_element_candidate"
            result.confidence = ConfidenceLevel.INFERRED
            result.details = {"element": data["follower"].get("key")}
        elif data.get("hiddenNative"):
            result.custom_cursor = True
            result.cursor_type = "native_cursor_hidden"
            result.confidence = ConfidenceLevel.INFERRED
        else:
            result.custom_cursor = False
            result.cursor_type = "NOT_OBSERVED"
            result.confidence = ConfidenceLevel.OBSERVED

        result.magnetic = bool(data.get("magneticAttrs"))
        result.evidence = ["runtime/cursor/cursor.json"]

        # Magnetic displacement estimate (safe, non-destructive)
        if result.magnetic or result.custom_cursor:
            try:
                magnetic = await page.evaluate(
                    """async () => {
                        const btn = document.querySelector('a.btn, .cta, button, [data-magnetic], [class*="magnetic"]');
                        if (!btn) return null;
                        const before = btn.getBoundingClientRect();
                        const cx = before.left + before.width / 2;
                        const cy = before.top + before.height / 2;
                        const moveEvent = new MouseEvent('mousemove', {
                            clientX: cx + 30, clientY: cy + 20, bubbles: true
                        });
                        document.dispatchEvent(moveEvent);
                        btn.dispatchEvent(moveEvent);
                        await new Promise(r => setTimeout(r, 120));
                        const after = btn.getBoundingClientRect();
                        return {
                            element: btn.tagName.toLowerCase(),
                            dx: Math.round(after.left - before.left),
                            dy: Math.round(after.top - before.top),
                        };
                    }"""
                )
                if magnetic and (abs(magnetic.get("dx", 0)) > 1 or abs(magnetic.get("dy", 0)) > 1):
                    result.magnetic = True
                    result.details["magnetic"] = {
                        **magnetic,
                        "strength_status": "ESTIMATED",
                    }
                    result.evidence.append("runtime magnetic displacement sample")
            except Exception:
                pass

        logger.info("[CURSOR] custom=%s type=%s magnetic=%s", result.custom_cursor, result.cursor_type, result.magnetic)
    except Exception as exc:
        logger.warning("[CURSOR] failed: %s", exc)
        result.confidence = ConfidenceLevel.UNKNOWN
        result.evidence = [str(exc)]

    return result
