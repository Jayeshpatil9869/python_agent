"""Application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_VIEWPORTS = [320, 375, 390, 414, 480, 768, 1024, 1280, 1440, 1920]

DEEP_VIEWPORT_TUPLES: list[tuple[int, int]] = [
    (320, 900),
    (375, 900),
    (390, 844),
    (414, 896),
    (480, 900),
    (768, 1024),
    (1024, 900),
    (1280, 900),
    (1440, 900),
    (1920, 1080),
]

MOBILE_VIEWPORT_TUPLES: list[tuple[int, int]] = [
    (320, 900),
    (375, 900),
    (390, 844),
    (414, 896),
    (480, 900),
]

TABLET_VIEWPORT_TUPLES: list[tuple[int, int]] = [
    (768, 1024),
    (1024, 900),
]

DESKTOP_VIEWPORT_TUPLES: list[tuple[int, int]] = [
    (1280, 900),
    (1440, 900),
    (1920, 1080),
]

FAST_VIEWPORT_TUPLES: list[tuple[int, int]] = [
    (375, 900),
    (768, 1024),
    (1280, 900),
    (1440, 900),
]


class Settings(BaseSettings):
    """Runtime settings loaded from environment and CLI overrides."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    ai_provider: Literal["openai", "anthropic", "gemini", "local", "none"] = "gemini"

    browser_headless: bool = True
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium"
    default_timeout: int = 30000
    max_pages: int = 10
    max_depth: int = 2
    output_dir: Path = Path("./output")

    desktop_viewport: tuple[int, int] = (1440, 900)
    tablet_viewport: tuple[int, int] = (768, 1024)
    mobile_viewport: tuple[int, int] = (375, 812)

    scroll_increments: int = 11
    stabilization_wait_ms: int = 1500
    same_origin_only: bool = True
    download_assets: bool = False
    respect_robots_txt: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


class AnalysisOptions:
    """Per-run analysis options merged from CLI and settings."""

    def __init__(
        self,
        url: str,
        depth: int = 2,
        max_pages: int = 10,
        timeout: int = 30000,
        headless: bool = True,
        browser: str = "chromium",
        mobile: bool = True,
        desktop: bool = True,
        tablet: bool = False,
        animations: bool = False,
        interactions: bool = False,
        ai: bool = False,
        deep: bool = False,
        output: Path | None = None,
        same_origin: bool = True,
    ) -> None:
        self.url = url
        self.depth = depth
        self.max_pages = max_pages
        self.timeout = timeout
        self.headless = headless
        self.browser = browser
        self.mobile = mobile
        self.desktop = desktop
        self.tablet = tablet
        self.animations = animations or deep
        self.interactions = interactions or deep
        self.ai = ai
        self.deep = deep
        self.output = output
        self.same_origin = same_origin

    @property
    def viewports(self) -> list[tuple[int, int]]:
        return self.resolve_viewports()

    def resolve_viewports(self) -> list[tuple[int, int]]:
        """Resolve viewport matrix from --deep, --mobile, --desktop, --tablet flags."""
        if self.deep:
            selected: list[tuple[int, int]] = []
            if self.mobile:
                selected.extend(MOBILE_VIEWPORT_TUPLES)
            if self.tablet:
                selected.extend(TABLET_VIEWPORT_TUPLES)
            if self.desktop:
                selected.extend(DESKTOP_VIEWPORT_TUPLES)
            if not selected:
                return DEEP_VIEWPORT_TUPLES
            # dedupe preserving order
            seen: set[tuple[int, int]] = set()
            unique: list[tuple[int, int]] = []
            for vp in selected:
                if vp not in seen:
                    seen.add(vp)
                    unique.append(vp)
            return unique

        selected = []
        if self.mobile:
            selected.append(MOBILE_VIEWPORT_TUPLES[1])  # 375
        if self.tablet:
            selected.append(TABLET_VIEWPORT_TUPLES[0])  # 768
        if self.desktop:
            selected.append(DESKTOP_VIEWPORT_TUPLES[1])  # 1440
        if not selected:
            return FAST_VIEWPORT_TUPLES
        seen: set[tuple[int, int]] = set()
        unique: list[tuple[int, int]] = []
        for vp in selected:
            if vp not in seen:
                seen.add(vp)
                unique.append(vp)
        return unique

    @property
    def viewport_widths(self) -> list[int]:
        return [w for w, _ in self.viewports]

    @property
    def scroll_steps(self) -> int:
        return 11 if self.deep else 5
