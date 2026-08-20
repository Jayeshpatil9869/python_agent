"""DOM analysis."""

from bs4 import BeautifulSoup


def analyze_dom(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    def count_tags(name: str) -> int:
        return len(soup.find_all(name))

    headings = {f"h{i}": count_tags(f"h{i}") for i in range(1, 7)}
    semantic = {
        tag: count_tags(tag)
        for tag in ["header", "nav", "main", "section", "article", "aside", "footer"]
    }

    all_tags = [el.name for el in soup.find_all(True)]
    div_count = all_tags.count("div")
    total = len(all_tags) or 1

    max_depth = _max_depth(soup)

    sections = []
    for tag in soup.find_all(["header", "nav", "main", "section", "footer"]):
        sections.append(
            {
                "tag": tag.name,
                "id": tag.get("id", ""),
                "classes": tag.get("class", []),
                "child_count": len(list(tag.children)),
            }
        )

    return {
        "dom_depth": max_depth,
        "section_count": len(sections),
        "headings": headings,
        "semantic_elements": semantic,
        "div_heavy_ratio": round(div_count / total, 3),
        "links_count": count_tags("a"),
        "buttons_count": count_tags("button") + len(soup.find_all("input", {"type": "submit"})),
        "forms_count": count_tags("form"),
        "images_count": count_tags("img"),
        "videos_count": count_tags("video"),
        "svgs_count": count_tags("svg"),
        "iframes_count": count_tags("iframe"),
        "scripts_count": count_tags("script"),
        "stylesheets_count": len(soup.find_all("link", rel="stylesheet")),
        "sections": sections[:20],
        "aria_attributes": _count_aria(soup),
        "data_attributes_count": _count_data_attrs(soup),
    }


def _max_depth(soup: BeautifulSoup) -> int:
    def depth(element, current=0):
        if not hasattr(element, "children"):
            return current
        child_depths = [depth(child, current + 1) for child in element.children if getattr(child, "name", None)]
        return max(child_depths) if child_depths else current

    return depth(soup)


def _count_aria(soup: BeautifulSoup) -> int:
    count = 0
    for el in soup.find_all(True):
        for attr in el.attrs:
            if attr.startswith("aria-"):
                count += 1
    return count


def _count_data_attrs(soup: BeautifulSoup) -> int:
    count = 0
    for el in soup.find_all(True):
        for attr in el.attrs:
            if attr.startswith("data-"):
                count += 1
    return count
