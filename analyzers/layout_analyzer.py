"""Layout analysis."""

LAYOUT_JS = """
() => {
    const containers = [];
    const grids = [];
    const sticky = [];
    const fixed = [];

    for (const el of document.querySelectorAll('body *')) {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        if (rect.width < 100) continue;

        if (style.maxWidth && style.maxWidth !== 'none' && rect.width > 600) {
            containers.push({ maxWidth: style.maxWidth, width: Math.round(rect.width), tag: el.tagName });
        }
        if (style.display === 'grid') {
            grids.push({
                columns: style.gridTemplateColumns,
                gap: style.gap,
                tag: el.tagName,
            });
        }
        if (style.position === 'sticky') {
            sticky.push({ tag: el.tagName, top: style.top, selector: el.id ? '#' + el.id : el.tagName });
        }
        if (style.position === 'fixed') {
            fixed.push({ tag: el.tagName, selector: el.id ? '#' + el.id : el.tagName });
        }
    }

    const bodyStyle = getComputedStyle(document.body);
    return {
        containers: containers.slice(0, 5),
        grid: grids.slice(0, 5),
        sticky_elements: sticky.slice(0, 10),
        fixed_elements: fixed.slice(0, 10),
        spacing: {
            body_padding: bodyStyle.padding,
            body_margin: bodyStyle.margin,
        },
        border_radius: [],
        shadows: [],
        gradients: [],
    };
}
"""


async def analyze_layout(page) -> dict:
    try:
        result = await page.evaluate(LAYOUT_JS)
        css_data = await page.evaluate(
            """() => {
                const radii = new Set(), shadows = new Set();
                for (const el of document.querySelectorAll('body *')) {
                    const s = getComputedStyle(el);
                    if (s.borderRadius !== '0px') radii.add(s.borderRadius);
                    if (s.boxShadow !== 'none') shadows.add(s.boxShadow);
                }
                return {
                    border_radius: Array.from(radii).slice(0, 10),
                    shadows: Array.from(shadows).slice(0, 10),
                };
            }"""
        )
        if css_data:
            result["border_radius"] = css_data.get("border_radius", [])
            result["shadows"] = css_data.get("shadows", [])
        return result or {}
    except Exception:
        return {}
