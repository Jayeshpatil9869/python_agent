# Website Reverse-Engineering / Design Intelligence Agent

A production-quality Python application that performs deep browser-based analysis of public websites. Unlike simple HTML scrapers, this agent observes websites the way a designer, frontend developer, UX researcher, and motion designer would — collecting evidence through real browser rendering, then producing structured intelligence and Markdown reports.

## What It Does

Given a URL, the agent:

1. Launches a real browser (Playwright/Chromium)
2. Waits for page stabilization (fonts, layout, lazy content)
3. Discovers internal pages (nav, footer, sitemap)
4. Inspects DOM, CSS, computed styles, layout, typography, colors
5. Detects components, assets, technologies, SEO, accessibility
6. Captures screenshots at desktop/tablet/mobile viewports
7. (Deep mode) Tests responsive breakpoints, scroll behavior, hover states, animations
8. (AI mode) Adds design interpretation via OpenAI, Anthropic, or Gemini
9. Generates Markdown reports and JSON evidence

## Architecture

```
URL → Browser Automation → Runtime Observation → DOM/CSS Inspection
  → Responsive Testing → Interaction Testing → Animation Observation
  → Evidence Collection → Structured Intelligence → AI Interpretation → Markdown Reports
```

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# Clone or navigate to project
cd website-intelligence-agent

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Configure environment (optional, for AI mode)
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

## Usage

### Basic analysis (no AI required)

```bash
python main.py https://example.com
```

### With options

```bash
python main.py https://example.com \
  --depth 2 \
  --max-pages 10 \
  --deep \
  --animations \
  --interactions \
  --ai \
  --output ./output
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--depth` | Crawl depth (default: 2) |
| `--max-pages` | Maximum pages to analyze (default: 10) |
| `--timeout` | Page timeout in ms (default: 30000) |
| `--headless` / `--no-headless` | Browser visibility |
| `--browser` | chromium, firefox, or webkit |
| `--mobile` / `--no-mobile` | Include mobile viewports (default: on) |
| `--desktop` / `--no-desktop` | Include desktop viewports (default: on) |
| `--tablet` | Include tablet viewports (with `--deep`) |
| `--deep` | Enable full responsive, scroll, interaction, animation analysis |
| `--ai` | Enable AI interpretation |
| `--output` | Output directory |
| `--same-origin` | Restrict crawling to same domain |

## Output Structure

```
output/
└── example-com/
    ├── WEBSITE-ANALYSIS.md
    ├── DESIGN-SYSTEM.md
    ├── RESPONSIVE-SPEC.md
    ├── ANIMATION-SPEC.md
    ├── INTERACTION-MAP.md
    ├── COMPONENT-MAP.md
    ├── TECHNOLOGY-REPORT.md
    ├── RECONSTRUCTION-PROMPT.md
    ├── analysis.log
    ├── screenshots/
    │   ├── desktop/
    │   ├── tablet/
    │   └── mobile/
    └── data/
        ├── website.json
        ├── pages.json
        ├── crawl.json
        ├── components.json
        ├── animations.json
        ├── interactions.json
        ├── responsive.json
        ├── scroll.json
        ├── technologies.json
        └── validation.json
    └── runtime/
        ├── responsive/
        ├── interactions/
        ├── animations/
        └── scroll/
```

## Environment Variables

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
AI_PROVIDER=gemini
BROWSER_HEADLESS=true
DEFAULT_TIMEOUT=30000
MAX_PAGES=10
MAX_DEPTH=2
OUTPUT_DIR=./output
```

## Confidence System

Every finding is classified:

| Level | Meaning |
|-------|---------|
| **DETECTED** | Hard evidence (script tag, global object, etc.) |
| **OBSERVED** | Directly seen in browser (computed style, screenshot) |
| **INFERRED** | Logical conclusion from evidence |
| **ESTIMATED** | Approximate value (e.g., animation duration) |
| **UNKNOWN** | Could not be determined |

## Modes

### Fast Mode (default)

Basic crawl, DOM/CSS analysis, technology detection, screenshots.

### Deep Mode (`--deep`)

Performs full browser observation laboratory:

- Responsive viewports (mobile/tablet/desktop groups controlled by flags)
- **Preloader** early-frame sampling + timeline
- **Page-load** hero/nav choreography traces
- Scroll-linked motion (parallax / pin / horizontal / scrub-like)
- Color transitions across scroll
- Interaction lab (hover, focus, safe click toggles)
- Custom cursor / magnetic sampling
- Safe page-transition probe
- Runtime motion tracing + CSS animation analysis
- Depth-aware BFS crawling with per-page depth metadata
- Technology detection with weighted evidence scoring

Primary reports for experience forensics:
- `MOTION-INTELLIGENCE.md`
- `DESIGN-INTELLIGENCE.md`
- `ANIMATION-SPEC.md`
- `RECONSTRUCTION-PROMPT.md`

```bash
# Full matrix (mobile + desktop)
python main.py https://example.com --deep

# Mobile viewports only
python main.py https://example.com --deep --mobile --no-desktop

# Desktop viewports only
python main.py https://example.com --deep --no-mobile --desktop

# With AI motion interpretation
python main.py https://example.com --deep --ai
```

### Depth Crawling

`--depth` controls BFS traversal:

- `0` — starting URL only
- `1` — seed + direct internal links
- `2` — seed + links up to 2 hops

Crawl results are saved to `data/crawl.json` with `url`, `depth`, `parent_url`, `discovery_source`, and `status`.

### Validation

After analysis, validate evidence:

```bash
python validate_analysis.py output/example-com
```

The validator distinguishes **PASS**, **PARTIAL**, and **FAIL**:

- **PASS** — requested stages executed, evidence consistent
- **PARTIAL** — some stages failed or warnings present
- **FAIL** — critical pipeline stages failed or evidence missing

It also runs semantic linting on Markdown reports to flag unsupported claims (e.g., "definitely uses GSAP" without evidence).

### AI Mode (`--ai`)

Adds design interpretation and enhanced reconstruction prompt. Requires at least one API key. If all providers fail, technical analysis still completes with `AI: UNAVAILABLE`.

**Default provider:** Gemini (`AI_PROVIDER=gemini`)

**Auto-fallback:** If the primary provider fails (quota, auth error, etc.), the agent automatically tries others in this order:

```text
preferred provider → gemini → openai → anthropic
```

Only providers with a configured API key are attempted.

## Testing

```bash
pytest tests/ -v
```

Includes unit tests plus E2E tests against `tests/fixture_site/` (deterministic HTML for crawl depth, responsive flags, interactions, animations, and validation).

## Limitations

- Observational accessibility audit only (not a replacement for axe/WAVE)
- Core Web Vitals not measured (Lighthouse integration planned for V2)
- Animation duration/easing may be estimated when not explicitly defined
- Cookie banners and popups may affect analysis
- Respects same-origin by default; does not submit forms or perform destructive actions

## Troubleshooting

**Playwright browser not found:**
```bash
playwright install chromium
```

**Timeout errors:** Increase `--timeout 60000` or use `--no-headless` for debugging.

**Empty reports:** Check `analysis.log` in the output directory for errors.

**AI not working:** Ensure `.env` has at least one valid API key. Check `analysis.log` for fallback errors. Gemini keys from [Google AI Studio](https://aistudio.google.com/apikey) typically start with `AIza`.

## Future Roadmap (V2)

- Lighthouse / Core Web Vitals integration
- WebGL / Three.js scene detection
- Lottie extraction
- Visual similarity scoring
- Website comparison
- Figma export
- Web dashboard
- Automatic React/Next.js reconstruction

## License

MIT
