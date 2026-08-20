"""Hover state observation."""

from intelligence.confidence import ConfidenceLevel


async def observe_hover_states(page) -> list[dict]:
    results: list[dict] = []

    try:
        targets = await page.evaluate(
            """() => Array.from(document.querySelectorAll(
                'button, a, [role="button"], .card, [class*="card"]'
            )).slice(0, 15).map((el, i) => ({
                index: i,
                tag: el.tagName.toLowerCase(),
                text: (el.textContent || '').trim().slice(0, 30),
            }))"""
        )

        for target in targets:
            idx = target["index"]
            try:
                before = await page.evaluate(
                    f"""() => {{
                        const els = document.querySelectorAll(
                            'button, a, [role="button"], .card, [class*="card"]'
                        );
                        const el = els[{idx}];
                        if (!el) return null;
                        const s = getComputedStyle(el);
                        return {{
                            color: s.color,
                            backgroundColor: s.backgroundColor,
                            transform: s.transform,
                            boxShadow: s.boxShadow,
                            opacity: s.opacity,
                        }};
                    }}"""
                )
                if not before:
                    continue

                selector = f"button, a, [role='button'], .card, [class*='card'] >> nth={idx}"
                await page.hover(selector, timeout=2000)
                await page.wait_for_timeout(300)

                after = await page.evaluate(
                    f"""() => {{
                        const els = document.querySelectorAll(
                            'button, a, [role="button"], .card, [class*="card"]'
                        );
                        const el = els[{idx}];
                        if (!el) return null;
                        const s = getComputedStyle(el);
                        return {{
                            color: s.color,
                            backgroundColor: s.backgroundColor,
                            transform: s.transform,
                            boxShadow: s.boxShadow,
                            opacity: s.opacity,
                        }};
                    }}"""
                )

                changes = {}
                if after:
                    for key in before:
                        if before.get(key) != after.get(key):
                            changes[key] = {"before": before[key], "after": after[key]}

                if changes:
                    results.append(
                        {
                            "element": f"{target['tag']}: {target['text']}",
                            "changes": changes,
                            "confidence": ConfidenceLevel.OBSERVED.value,
                        }
                    )
            except Exception:
                continue
    except Exception:
        pass

    return results
