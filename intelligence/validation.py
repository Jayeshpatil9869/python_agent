"""Analysis output validation with PASS/PARTIAL/FAIL and semantic linting."""

import json
import re
from pathlib import Path
from typing import Any

from utils.filesystem import write_json

UNSUPPORTED_PHRASES = [
    (r"\bdefinitely uses?\b", "Use 'detected from runtime evidence' when supported"),
    (r"\buses an? \d+ms animation\b", "Use 'estimated at approximately Xms' unless observed"),
    (r"\bbuilt with (Angular|React|Vue|Next\.js)\b", "Use framework status labels from evidence"),
    (r"\bGSAP animation\b", "Use 'GSAP detected' or 'GSAP-like motion possible'"),
]

CONFIDENCE_CONTRADICTIONS = [
    (r"Bootstrap detected", "bootstrap", 0.7),
    (r"Angular detected", "angular", 0.7),
    (r"GSAP detected", "gsap", 0.7),
]


def validate_analysis_output(
    output_dir: Path,
    stage_results: dict | None = None,
) -> dict[str, Any]:
    """Validate collected evidence and distinguish PASS/PARTIAL/FAIL."""
    result: dict[str, Any] = {
        "output_dir": str(output_dir),
        "overall_status": "PASS",
        "checks": [],
        "metrics": {},
        "failures": [],
        "warnings": [],
        "quality_errors": [],
        "semantic_lint": [],
    }

    data_dir = output_dir / "data"
    required_json = [
        "website.json",
        "pages.json",
        "responsive.json",
        "animations.json",
        "interactions.json",
        "technologies.json",
    ]
    for name in required_json:
        path = data_dir / name
        ok = path.exists()
        result["checks"].append({"file": name, "exists": ok})
        if not ok:
            result["failures"].append(f"Missing {name}")

    responsive = _load_json_list(data_dir / "responsive.json")
    interactions = _load_json_list(data_dir / "interactions.json")
    animations = _load_json_list(data_dir / "animations.json")
    pages = _load_json_list(data_dir / "pages.json")
    technologies = _load_json_list(data_dir / "technologies.json")
    crawl_pages = _load_json_list(data_dir / "crawl.json")

    result["metrics"] = {
        "pages": len(pages),
        "viewports": len(responsive),
        "interactions": len(interactions),
        "animations": len(animations),
        "technologies": len(technologies),
        "crawl_pages": len(crawl_pages),
    }

    screenshots = list((output_dir / "screenshots").rglob("*.png")) if (output_dir / "screenshots").exists() else []
    result["metrics"]["screenshots"] = len(screenshots)

    stage_meta = stage_results or _load_stage_results(data_dir / "website.json")

    # Responsive quality gate
    responsive_status = stage_meta.get("responsive", "unknown")
    responsive_meta = _load_stage_meta(data_dir / "website.json", "responsive")
    requested = responsive_meta.get("metrics", {}).get("viewports_requested", len(responsive))
    analyzed = responsive_meta.get("metrics", {}).get("viewports_analyzed", len([r for r in responsive if r.get("dom_width", 0) > 0]))
    successful_shots = len([r for r in responsive if r.get("screenshot")])

    result["metrics"]["responsive_requested"] = requested
    result["metrics"]["responsive_executed"] = len(responsive)
    result["metrics"]["responsive_successful"] = successful_shots

    if responsive_status == "failed":
        result["failures"].append("Responsive analyzer FAILED")
    elif requested > 0 and successful_shots == 0:
        result["failures"].append("Responsive requested but no successful screenshots")
    elif requested > 0 and analyzed == 0:
        result["failures"].append("Responsive analyzer produced no viewport evidence")
    elif responsive_status in ("partial",) or (requested > 0 and analyzed < requested):
        result["warnings"].append(
            f"Responsive partial: requested={requested}, analyzed={analyzed}, screenshots={successful_shots}"
        )
    else:
        result["checks"].append({"stage": "responsive", "status": "ok", "count": len(responsive)})

    interaction_status = stage_meta.get("interactions", "unknown")
    if interaction_status == "failed":
        result["failures"].append("Interaction analyzer FAILED")
    elif len(interactions) == 0 and interaction_status not in ("skipped", "no_data"):
        result["warnings"].append("Interaction evidence empty — verify analyzer executed")

    animation_status = stage_meta.get("animations", "unknown")
    if animation_status == "failed":
        result["failures"].append("Animation analyzer FAILED")
    elif len(animations) == 0 and animation_status not in ("skipped", "no_data"):
        result["warnings"].append("Animation evidence empty — verify analyzer executed")

    reports = [
        "WEBSITE-ANALYSIS.md",
        "DESIGN-INTELLIGENCE.md",
        "DESIGN-SYSTEM.md",
        "MOTION-INTELLIGENCE.md",
        "ANIMATION-SPEC.md",
        "RESPONSIVE-SPEC.md",
        "INTERACTION-MAP.md",
        "COMPONENT-MAP.md",
        "TECHNOLOGY-REPORT.md",
        "RECONSTRUCTION-PROMPT.md",
    ]
    missing_reports = [r for r in reports if not (output_dir / r).exists()]
    if missing_reports:
        result["failures"].append(f"Missing reports: {', '.join(missing_reports)}")

    if not screenshots and not result["failures"]:
        result["warnings"].append("No screenshots found")

    # Semantic motion quality gates
    preloader = _load_json_obj(data_dir / "preloader.json")
    if preloader.get("observed"):
        timeline = preloader.get("timeline") or []
        overlays = [t.get("overlays", 0) for t in timeline]
        pcts = [t.get("pct") for t in timeline if t.get("pct")]
        unique_pcts = {p for p in pcts}
        if max(overlays or [0]) == 0 and len(unique_pcts) <= 1:
            result["quality_errors"].append(
                "Preloader marked observed but no overlay dismissal and no progressing percentage"
            )
        if preloader.get("type") == "percentage_loader" and len(unique_pcts) <= 1:
            result["quality_errors"].append(
                "percentage_loader claimed but percentage did not advance"
            )

    motion = _load_json_obj(data_dir / "motion.json")
    if motion:
        result["metrics"]["scroll_findings"] = len(motion.get("scrolltrigger_analysis") or [])
        result["metrics"]["preloader_observed"] = bool((motion.get("preloader") or {}).get("observed"))
        result["metrics"]["hero_status"] = (motion.get("hero_animation") or {}).get("status")

    # Tech wording vs confidence
    for tech in technologies:
        name = (tech.get("name") or "").lower()
        status = (tech.get("status") or "").upper()
        conf = float(tech.get("confidence") or 0)
        if status == "POSSIBLE" and conf >= 0.7:
            result["warnings"].append(f"{tech.get('name')}: status POSSIBLE with confidence {conf}")
        if name == "gsap" and status in ("DETECTED", "HIGH_CONFIDENCE"):
            evidence = " ".join(tech.get("evidence") or [])
            if "window.gsap" not in evidence and "window.ScrollTrigger" not in evidence:
                if evidence.startswith("resource/path:") or "resource/path:gsap" in evidence:
                    result["quality_errors"].append(
                        "GSAP claimed DETECTED/HIGH_CONFIDENCE from path-only evidence"
                    )

    # Semantic report linting
    tech_by_name = {t.get("name", "").lower(): t for t in technologies}
    for report_name in reports:
        report_path = output_dir / report_name
        if not report_path.exists():
            continue
        text = report_path.read_text(encoding="utf-8", errors="ignore")
        for pattern, suggestion in UNSUPPORTED_PHRASES:
            if re.search(pattern, text, re.IGNORECASE):
                result["semantic_lint"].append(
                    {"file": report_name, "issue": pattern, "suggestion": suggestion}
                )
        for phrase, tech_key, min_conf in CONFIDENCE_CONTRADICTIONS:
            if phrase.lower() in text.lower():
                tech = tech_by_name.get(tech_key)
                if tech and tech.get("confidence", 0) < min_conf:
                    result["quality_errors"].append(
                        f"{report_name}: '{phrase}' contradicts low confidence ({tech.get('confidence')})"
                    )

    # Determine overall status
    critical_failures = [
        f for f in result["failures"]
        if any(x in f.lower() for x in ("failed", "missing website.json", "missing pages.json", "no successful"))
    ]
    if critical_failures or (not pages and not result["metrics"].get("pages")):
        result["overall_status"] = "FAIL"
    elif result["failures"] or result["quality_errors"]:
        result["overall_status"] = "PARTIAL"
    elif result["warnings"] or result["semantic_lint"]:
        result["overall_status"] = "PARTIAL"
    else:
        result["overall_status"] = "PASS"

    validation_path = data_dir / "validation.json"
    write_json(validation_path, result)
    return result


def _load_json_obj(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_json_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _load_stage_results(website_path: Path) -> dict[str, str]:
    if not website_path.exists():
        return {}
    try:
        data = json.loads(website_path.read_text(encoding="utf-8"))
        stages = data.get("stage_results") or {}
        return {k: v.get("status", "unknown") if isinstance(v, dict) else str(v) for k, v in stages.items()}
    except Exception:
        return {}


def _load_stage_meta(website_path: Path, stage: str) -> dict[str, Any]:
    if not website_path.exists():
        return {}
    try:
        data = json.loads(website_path.read_text(encoding="utf-8"))
        stages = data.get("stage_results") or {}
        meta = stages.get(stage, {})
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}
