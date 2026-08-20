"""Agent state management."""

from dataclasses import dataclass, field
from pathlib import Path

from config.settings import AnalysisOptions
from intelligence.schema import WebsiteIntelligence


@dataclass
class AgentState:
    options: AnalysisOptions
    output_dir: Path
    intelligence: WebsiteIntelligence | None = None
    discovered_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stage: str = "init"
