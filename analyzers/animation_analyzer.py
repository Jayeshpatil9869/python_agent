"""Animation detection and observation."""

from intelligence.confidence import ConfidenceLevel
from intelligence.schema import AnimationRecord


ANIMATION_JS = """
() => {
    const results = [];
    const elements = Array.from(document.querySelectorAll('body *')).slice(0, 200);

    for (const el of elements) {
        const style = getComputedStyle(el);
        const animName = style.animationName;
        const transProps = style.transitionProperty;
        const duration = style.animationDuration !== '0s' ? style.animationDuration :
            (style.transitionDuration !== '0s' ? style.transitionDuration : '');
        const easing = style.animationTimingFunction !== 'ease' ? style.animationTimingFunction :
            style.transitionTimingFunction;

        if ((animName && animName !== 'none') || (transProps && transProps !== 'all' && style.transitionDuration !== '0s')) {
            results.push({
                element: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
                    (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                trigger: animName !== 'none' ? 'css-animation' : 'css-transition',
                property: transProps || animName,
                duration: duration,
                easing: easing,
                initial: {
                    opacity: style.opacity,
                    transform: style.transform,
                },
            });
        }
    }
    return results.slice(0, 25);
}
"""


async def analyze_animations(page) -> list[AnimationRecord]:
    animations: list[AnimationRecord] = []

    try:
        detected = await page.evaluate(ANIMATION_JS)
        for item in detected:
            duration = item.get("duration", "")
            confidence = ConfidenceLevel.OBSERVED if duration else ConfidenceLevel.ESTIMATED
            animations.append(
                AnimationRecord(
                    element=item.get("element", ""),
                    trigger=item.get("trigger", ""),
                    initial_state=item.get("initial", {}),
                    final_state={},
                    duration=str(duration) if duration else "unknown",
                    easing=item.get("easing", "unknown"),
                    property=item.get("property", ""),
                    confidence=confidence,
                    evidence=["computed CSS animation/transition"],
                )
            )
    except Exception:
        pass

    try:
        keyframes = await page.evaluate(
            """() => {
                const sheets = Array.from(document.styleSheets);
                const names = [];
                for (const sheet of sheets) {
                    try {
                        for (const rule of sheet.cssRules || []) {
                            if (rule.type === CSSRule.KEYFRAMES_RULE) {
                                names.push(rule.name);
                            }
                        }
                    } catch (e) {}
                }
                return names.slice(0, 20);
            }"""
        )
        for name in keyframes:
            animations.append(
                AnimationRecord(
                    element=f"@keyframes {name}",
                    trigger="css-keyframes",
                    confidence=ConfidenceLevel.DETECTED,
                    evidence=[f"@keyframes {name}"],
                )
            )
    except Exception:
        pass

    return animations
