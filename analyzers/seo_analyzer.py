"""SEO analysis."""

from bs4 import BeautifulSoup

from intelligence.schema import SEOData


def analyze_seo(html: str, url: str) -> SEOData:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", rel="canonical")
    robots = soup.find("meta", attrs={"name": "robots"})

    og = {}
    for prop in ("og:title", "og:description", "og:image", "og:type", "og:url"):
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            og[prop.replace("og:", "")] = tag["content"]

    twitter = {}
    for name in ("twitter:card", "twitter:title", "twitter:description", "twitter:image"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            twitter[name.replace("twitter:", "")] = tag["content"]

    structured = []
    for script in soup.find_all("script", type="application/ld+json"):
        if script.string:
            structured.append({"raw": script.string[:500]})

    headings = []
    for i in range(1, 7):
        for h in soup.find_all(f"h{i}"):
            headings.append(f"H{i}: {(h.get_text(strip=True) or '')[:80]}")

    issues = []
    if not title_tag or not title_tag.get_text(strip=True):
        issues.append("Missing title tag")
    if not meta_desc or not meta_desc.get("content"):
        issues.append("Missing meta description")
    if not canonical:
        issues.append("No canonical URL")

    return SEOData(
        title=title_tag.get_text(strip=True) if title_tag else "",
        meta_description=meta_desc.get("content", "") if meta_desc else "",
        canonical=canonical.get("href", "") if canonical else "",
        robots=robots.get("content", "") if robots else "",
        open_graph=og,
        twitter_cards=twitter,
        structured_data=structured,
        heading_structure=headings[:20],
        issues=issues,
    )
