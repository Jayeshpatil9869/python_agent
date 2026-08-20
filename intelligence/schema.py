"""Intelligence schema models."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from intelligence.confidence import ConfidenceLevel


class CrawlPageRecord(BaseModel):
    url: str
    depth: int = 0
    parent_url: str | None = None
    discovery_source: str = "link"
    status: str = "pending"


class ColorToken(BaseModel):
    value: str
    usage: str = ""
    count: int = 0
    role: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.OBSERVED


class TypographyToken(BaseModel):
    role: str = ""
    font_family: str = ""
    font_size: str = ""
    font_weight: str = ""
    line_height: str = ""
    letter_spacing: str = ""
    text_transform: str = ""
    count: int = 0
    confidence: ConfidenceLevel = ConfidenceLevel.OBSERVED


class DesignSystem(BaseModel):
    colors: list[ColorToken] = Field(default_factory=list)
    typography: list[TypographyToken] = Field(default_factory=list)
    spacing: dict[str, Any] = Field(default_factory=dict)
    grid: dict[str, Any] = Field(default_factory=dict)
    containers: dict[str, Any] = Field(default_factory=dict)
    border_radius: list[str] = Field(default_factory=list)
    shadows: list[str] = Field(default_factory=list)
    gradients: list[str] = Field(default_factory=list)


class TechnologyDetection(BaseModel):
    name: str
    status: str = "unknown"
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    evidence: list[str] = Field(default_factory=list)


class AnimationRecord(BaseModel):
    element: str = ""
    trigger: str = ""
    initial_state: dict[str, Any] = Field(default_factory=dict)
    final_state: dict[str, Any] = Field(default_factory=dict)
    duration: str = ""
    delay: str = ""
    easing: str = ""
    property: str = ""
    direction: str = ""
    viewport_dependency: str = ""
    mobile_behavior: str = ""
    scroll_start: str = ""
    scroll_end: str = ""
    scrub: str = ""
    pin: str = ""
    stagger: str = ""
    classification: str = ""
    library_evidence: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    evidence: list[str] = Field(default_factory=list)


class PreloaderObservation(BaseModel):
    observed: bool = False
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    type: str = "NOT_OBSERVED"
    duration_ms: int | None = None
    duration_status: str = "UNKNOWN"
    initial_state: dict[str, Any] = Field(default_factory=dict)
    progress_behavior: str = "UNKNOWN"
    exit_animation: str = "UNKNOWN"
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class PageLoadTimeline(BaseModel):
    phases: list[dict[str, Any]] = Field(default_factory=list)
    hero_animation: dict[str, Any] = Field(default_factory=dict)
    navigation_animation: dict[str, Any] = Field(default_factory=dict)
    total_duration_ms: int | None = None
    duration_status: str = "ESTIMATED"
    evidence: list[str] = Field(default_factory=list)


class ScrollMotionFinding(BaseModel):
    element: str = ""
    classification: str = ""
    scroll_start: int | None = None
    scroll_end: int | None = None
    property_changes: dict[str, Any] = Field(default_factory=dict)
    scrub: str = "UNKNOWN"
    pin: str = "UNKNOWN"
    parallax_ratio: float | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    evidence: list[str] = Field(default_factory=list)


class ColorTransition(BaseModel):
    from_scroll: int = 0
    to_scroll: int = 0
    from_color: str = ""
    to_color: str = ""
    transition_type: str = "UNKNOWN"
    confidence: ConfidenceLevel = ConfidenceLevel.OBSERVED
    evidence: list[str] = Field(default_factory=list)


class CursorObservation(BaseModel):
    custom_cursor: bool = False
    cursor_type: str = "NOT_OBSERVED"
    magnetic: bool = False
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    details: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)


class TransitionObservation(BaseModel):
    observed: bool = False
    type: str = "NOT_OBSERVED"
    from_url: str = ""
    to_url: str = ""
    sequence: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    evidence: list[str] = Field(default_factory=list)


class DesignIntelligence(BaseModel):
    design_direction: str = ""
    color_system: dict[str, Any] = Field(default_factory=dict)
    color_transitions: list[ColorTransition] = Field(default_factory=list)
    typography_hierarchy: list[dict[str, Any]] = Field(default_factory=list)
    layout_system: dict[str, Any] = Field(default_factory=dict)
    image_language: dict[str, Any] = Field(default_factory=dict)
    visual_effects: dict[str, Any] = Field(default_factory=dict)
    section_rhythm: list[str] = Field(default_factory=list)
    visual_hierarchy: list[str] = Field(default_factory=list)
    design_patterns: list[str] = Field(default_factory=list)
    design_motion_relationship: str = ""
    experience_score: dict[str, Any] = Field(default_factory=dict)
    confidence: ConfidenceLevel = ConfidenceLevel.INFERRED
    evidence: list[str] = Field(default_factory=list)


class MotionIntelligence(BaseModel):
    motion_summary: str = ""
    motion_personality: list[str] = Field(default_factory=list)
    preloader: PreloaderObservation = Field(default_factory=PreloaderObservation)
    page_load: PageLoadTimeline = Field(default_factory=PageLoadTimeline)
    hero_animation: dict[str, Any] = Field(default_factory=dict)
    navigation_animation: dict[str, Any] = Field(default_factory=dict)
    scroll_system: dict[str, Any] = Field(default_factory=dict)
    scrolltrigger_analysis: list[ScrollMotionFinding] = Field(default_factory=list)
    parallax: list[ScrollMotionFinding] = Field(default_factory=list)
    pinning: list[ScrollMotionFinding] = Field(default_factory=list)
    horizontal_scroll: list[ScrollMotionFinding] = Field(default_factory=list)
    text_animation: list[dict[str, Any]] = Field(default_factory=list)
    image_animation: list[dict[str, Any]] = Field(default_factory=list)
    video_animation: list[dict[str, Any]] = Field(default_factory=list)
    hover_motion: list[dict[str, Any]] = Field(default_factory=list)
    cursor: CursorObservation = Field(default_factory=CursorObservation)
    magnetic_interactions: list[dict[str, Any]] = Field(default_factory=list)
    micro_interactions: list[dict[str, Any]] = Field(default_factory=list)
    section_transitions: list[dict[str, Any]] = Field(default_factory=list)
    page_transitions: list[TransitionObservation] = Field(default_factory=list)
    mobile_motion: dict[str, Any] = Field(default_factory=dict)
    motion_hierarchy: dict[str, list[str]] = Field(default_factory=dict)
    complete_timeline: list[dict[str, Any]] = Field(default_factory=list)
    gsap_status: str = "UNKNOWN"
    scrolltrigger_status: str = "UNKNOWN"
    implementation_hypotheses: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.INFERRED
    evidence: list[str] = Field(default_factory=list)


class InteractionRecord(BaseModel):
    element: str = ""
    trigger: str = ""
    behavior: str = ""
    animation: str = ""
    mobile: str = ""
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    evidence: list[str] = Field(default_factory=list)


class ComponentRecord(BaseModel):
    name: str
    purpose: str = ""
    selector: str = ""
    visual_structure: str = ""
    children: list[str] = Field(default_factory=list)
    styles: dict[str, Any] = Field(default_factory=dict)
    responsive_behavior: str = ""
    interactions: list[str] = Field(default_factory=list)
    animations: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.INFERRED


class ResponsiveViewportData(BaseModel):
    width: int
    screenshot: str = ""
    dom_width: int = 0
    dom_height: int = 0
    navigation_state: str = ""
    notes: list[str] = Field(default_factory=list)
    element_snapshots: dict[str, Any] = Field(default_factory=dict)


class AssetRecord(BaseModel):
    url: str
    asset_type: str = ""
    format: str = ""
    width: int | None = None
    height: int | None = None
    alt: str = ""
    loading: str = ""


class SEOData(BaseModel):
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    robots: str = ""
    open_graph: dict[str, str] = Field(default_factory=dict)
    twitter_cards: dict[str, str] = Field(default_factory=dict)
    structured_data: list[dict[str, Any]] = Field(default_factory=list)
    heading_structure: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class AccessibilityData(BaseModel):
    aria_usage: int = 0
    landmarks: list[str] = Field(default_factory=list)
    heading_issues: list[str] = Field(default_factory=list)
    missing_alt_images: int = 0
    form_label_issues: int = 0
    focusable_elements: int = 0
    notes: list[str] = Field(default_factory=list)


class PerformanceData(BaseModel):
    dom_content_loaded_ms: float | None = None
    load_ms: float | None = None
    resource_count: int = 0
    js_size_kb: float = 0
    css_size_kb: float = 0
    large_images: list[str] = Field(default_factory=list)
    lazy_loading_detected: bool = False
    preload_detected: bool = False
    notes: list[str] = Field(default_factory=list)


class PageAnalysis(BaseModel):
    url: str
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    viewport: str = ""
    html_size: int = 0
    dom_depth: int = 0
    section_count: int = 0
    headings: dict[str, int] = Field(default_factory=dict)
    links_count: int = 0
    buttons_count: int = 0
    forms_count: int = 0
    images_count: int = 0
    videos_count: int = 0
    svgs_count: int = 0
    iframes_count: int = 0
    scripts_count: int = 0
    stylesheets_count: int = 0
    fonts: list[str] = Field(default_factory=list)
    dom_summary: dict[str, Any] = Field(default_factory=dict)
    css_summary: dict[str, Any] = Field(default_factory=dict)
    layout_summary: dict[str, Any] = Field(default_factory=dict)
    components: list[ComponentRecord] = Field(default_factory=list)
    animations: list[AnimationRecord] = Field(default_factory=list)
    interactions: list[InteractionRecord] = Field(default_factory=list)
    responsive: list[ResponsiveViewportData] = Field(default_factory=list)
    assets: list[AssetRecord] = Field(default_factory=list)
    seo: SEOData = Field(default_factory=SEOData)
    accessibility: AccessibilityData = Field(default_factory=AccessibilityData)
    performance: PerformanceData = Field(default_factory=PerformanceData)
    technologies: list[TechnologyDetection] = Field(default_factory=list)
    screenshots: dict[str, str] = Field(default_factory=dict)
    scroll_observations: list[dict[str, Any]] = Field(default_factory=list)
    preloader: PreloaderObservation = Field(default_factory=PreloaderObservation)
    page_load: PageLoadTimeline = Field(default_factory=PageLoadTimeline)
    cursor: CursorObservation = Field(default_factory=CursorObservation)
    page_transitions: list[TransitionObservation] = Field(default_factory=list)
    scroll_motion_findings: list[ScrollMotionFinding] = Field(default_factory=list)
    color_transitions: list[ColorTransition] = Field(default_factory=list)
    stage_results: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class WebsiteIntelligence(BaseModel):
    url: str
    title: str = ""
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    pages: list[PageAnalysis] = Field(default_factory=list)
    crawl_pages: list[CrawlPageRecord] = Field(default_factory=list)
    sitemap_urls: list[str] = Field(default_factory=list)
    design_system: DesignSystem = Field(default_factory=DesignSystem)
    design_intelligence: DesignIntelligence = Field(default_factory=DesignIntelligence)
    motion_intelligence: MotionIntelligence = Field(default_factory=MotionIntelligence)
    technologies: list[TechnologyDetection] = Field(default_factory=list)
    motion_system: dict[str, Any] = Field(default_factory=dict)
    responsive_system: dict[str, Any] = Field(default_factory=dict)
    ai_interpretation: dict[str, str] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    analysis_status: str = "UNKNOWN"
    stage_results: dict[str, Any] = Field(default_factory=dict)
