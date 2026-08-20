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
        '[class*="cursor"], [id*="cursor"], [class*="pointer-follower"], [class*="mouse-follower"], [data-cursor]'
    )).slice(0, 20).map(el => {
        const s = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        const cls = String(el.className || '');
        return {
            key: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                (cls ? '.' + cls.split(' ')[0] : ''),
            className: cls.slice(0, 80),
            position: s.position,
            pointerEvents: s.pointerEvents,
            mixBlendMode: s.mixBlendMode,
            transform: s.transform,
            width: Math.round(r.width),
            height: Math.round(r.height),
            opacity: s.opacity,
            zIndex: s.zIndex,
            looksLikeCursor: /cursor|follower|pointer/i.test(cls + (el.id || '')),
        };
    });

    const hiddenNative = bodyCursor === 'none' || htmlCursor === 'none';
    const followers = candidates.filter(c =>
        c.looksLikeCursor &&
        (c.position === 'fixed' || c.position === 'absolute') &&
        c.width > 0 && c.width <= 120 &&
        c.height > 0 && c.height <= 120 &&
        c.pointerEvents === 'none'
    );
    const follower = followers[0] || null;

    return {
        bodyCursor,
        htmlCursor,
        hiddenNative,
        candidates: candidates.filter(c => c.looksLikeCursor).slice(0, 8),
        follower,
        magneticAttrs: document.querySelector('[data-magnetic], [class*="magnetic"]') !== null,
    };
}
"""


async def observe_cursor(page, output_dir: Path) -> CursorObservation:
    result = CursorObservation(
        custom_cursor=False,
        cursor_type="NOT_OBSERVED",
        confidence=ConfidenceLevel.OBSERVED,
    )
    runtime_dir = output_dir / "runtime" / "cursor"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = await page.evaluate(CURSOR_DETECT_JS)
        (runtime_dir / "cursor.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        result.evidence = ["runtime/cursor/cursor.json"]

        if data.get("follower"):
            result.custom_cursor = True
            result.cursor_type = "custom_follower"
            result.confidence = ConfidenceLevel.OBSERVED
            result.details = {
                "size": {"w": data["follower"].get("width"), "h": data["follower"].get("height")},
                "blend": data["follower"].get("mixBlendMode"),
                "element": data["follower"].get("key"),
            }
        elif data.get("hiddenNative"):
            # cursor:none alone is only INFERRED — may be CSS without a follower
            result.custom_cursor = True
            result.cursor_type = "native_cursor_hidden"
            result.confidence = ConfidenceLevel.INFERRED
            result.details = {
                "note": "document cursor is none but no follower element confirmed",
            }
        else:
            result.custom_cursor = False
            result.cursor_type = "NOT_OBSERVED"
            result.confidence = ConfidenceLevel.OBSERVED

        result.magnetic = bool(data.get("magneticAttrs"))

        if result.magnetic or (result.custom_cursor and result.cursor_type == "custom_follower"):
            try:
                magnetic = await page.evaluate(
                    """async () => {
                        const btn = document.querySelector(
                            '[data-magnetic], [class*="magnetic"], a.btn, .cta, button'
                        );
                        if (!btn) return null;
                        const before = btn.getBoundingClientRect();
                        const cx = before.left + before.width / 2;
                        const cy = before.top + before.height / 2;
                        const moveEvent = new MouseEvent('mousemove', {
                            clientX: cx + 30, clientY: cy + 20, bubbles: true
                        });
                        document.dispatchEvent(moveEvent);
                        btn.dispatchEvent(moveEvent);
                        await new Promise(r => setTimeout(r, 150));
                        const after = btn.getBoundingClientRect();
                        return {
                            element: btn.tagName.toLowerCase(),
                            dx: Math.round(after.left - before.left),
                            dy: Math.round(after.top - before.top),
                        };
                    }"""
                )
                if magnetic and (abs(magnetic.get("dx", 0)) > 2 or abs(magnetic.get("dy", 0)) > 2):
                    result.magnetic = True
                    result.details["magnetic"] = {
                        **magnetic,
                        "strength_status": "ESTIMATED",
                    }
                    result.evidence.append("runtime magnetic displacement sample")
            except Exception:
                pass

        logger.info(
            "[CURSOR] custom=%s type=%s conf=%s magnetic=%s",
            result.custom_cursor,
            result.cursor_type,
            result.confidence.value,
            result.magnetic,
        )
    except Exception as exc:
        logger.warning("[CURSOR] failed: %s", exc)
        result.confidence = ConfidenceLevel.UNKNOWN
        result.evidence = [str(exc)]

    return result
