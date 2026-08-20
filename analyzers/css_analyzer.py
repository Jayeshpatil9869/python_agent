"""CSS and computed style analysis."""

from collections import Counter


CSS_SAMPLE_JS = """
() => {
    const props = [
        'color', 'backgroundColor', 'borderColor', 'fontFamily', 'fontSize',
        'fontWeight', 'lineHeight', 'letterSpacing', 'textTransform',
        'padding', 'margin', 'gap', 'borderRadius', 'boxShadow',
        'display', 'gridTemplateColumns', 'flexDirection', 'maxWidth'
    ];
    const elements = Array.from(document.querySelectorAll('body *')).slice(0, 300);
    const samples = [];
    const colorFreq = {};
    const typography = [];
    const radii = new Set();
    const shadows = new Set();
    const gradients = new Set();

    for (const el of elements) {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) continue;

        for (const prop of ['color', 'backgroundColor', 'borderColor']) {
            const val = style[prop];
            if (val && val !== 'rgba(0, 0, 0, 0)' && val !== 'transparent') {
                colorFreq[val] = (colorFreq[val] || 0) + 1;
            }
        }

        if (style.fontSize && style.fontFamily) {
            typography.push({
                font_family: style.fontFamily.split(',')[0].replace(/['"]/g, '').trim(),
                font_size: style.fontSize,
                font_weight: style.fontWeight,
                line_height: style.lineHeight,
                letter_spacing: style.letterSpacing,
                text_transform: style.textTransform,
                role: el.tagName.toLowerCase(),
            });
        }

        if (style.borderRadius && style.borderRadius !== '0px') {
            radii.add(style.borderRadius);
        }
        if (style.boxShadow && style.boxShadow !== 'none') {
            shadows.add(style.boxShadow);
        }
        const bg = style.backgroundImage || '';
        if (bg.includes('gradient')) {
            gradients.add(bg.slice(0, 120));
        }
    }

    return {
        color_frequency: colorFreq,
        typography_samples: typography.slice(0, 50),
        border_radius: Array.from(radii).slice(0, 10),
        shadows: Array.from(shadows).slice(0, 10),
        gradients: Array.from(gradients).slice(0, 10),
    };
}
"""


async def analyze_css(page) -> dict:
    try:
        result = await page.evaluate(CSS_SAMPLE_JS)
        return result or {}
    except Exception:
        return {}


def rank_colors(color_frequency: dict) -> list[dict]:
    counter = Counter(color_frequency)
    return [{"color": c, "count": n} for c, n in counter.most_common(20)]
