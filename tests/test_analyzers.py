"""Tests for analyzers."""

from analyzers.color_analyzer import analyze_colors
from analyzers.dom_analyzer import analyze_dom
from analyzers.seo_analyzer import analyze_seo
from analyzers.typography_analyzer import analyze_typography


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Site</title>
    <meta name="description" content="A test website">
    <link rel="canonical" href="https://example.com">
</head>
<body>
    <header><nav><a href="/">Home</a></nav></header>
    <main>
        <h1>Hello World</h1>
        <h2>Subtitle</h2>
        <p>Body text here.</p>
        <button>Click me</button>
        <img src="test.jpg" alt="Test image">
    </main>
    <footer>Footer</footer>
</body>
</html>
"""


def test_dom_analyzer():
    result = analyze_dom(SAMPLE_HTML)
    assert result["headings"]["h1"] == 1
    assert result["semantic_elements"]["header"] == 1
    assert result["buttons_count"] >= 1
    assert result["dom_depth"] > 0


def test_color_analyzer():
    css = {"color_frequency": {"rgb(0, 0, 0)": 10, "rgb(255, 255, 255)": 5}}
    result = analyze_colors(css)
    assert result["primary"] == "rgb(0, 0, 0)"


def test_typography_analyzer():
    css = {
        "typography_samples": [
            {"font_family": "Inter", "font_size": "16px", "font_weight": "400", "role": "p"},
            {"font_family": "Inter", "font_size": "48px", "font_weight": "700", "role": "h1"},
        ]
    }
    result = analyze_typography(css)
    assert len(result["font_families"]) > 0
    assert len(result["roles"]) > 0


def test_seo_analyzer():
    result = analyze_seo(SAMPLE_HTML, "https://example.com")
    assert result.title == "Test Site"
    assert result.meta_description == "A test website"
    assert result.canonical == "https://example.com"
