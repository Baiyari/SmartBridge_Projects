from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetaIssues:
    missing_title: bool = False
    title_too_short: bool = False
    title_too_long: bool = False
    missing_meta_desc: bool = False
    duplicate_meta_desc: bool = False
    missing_canonical: bool = False
    malformed_canonical: bool = False
    missing_og_title: bool = False
    missing_og_desc: bool = False
    missing_og_image: bool = False

    def count(self) -> int:
        return sum(1 for v in vars(self).values() if v is True)

    def to_str(self) -> str:
        found = [k.replace("_", " ") for k, v in vars(self).items() if v is True]
        return ", ".join(found) if found else "none"


@dataclass
class KeywordResult:
    top_keywords: list[tuple[str, float]] = field(default_factory=list)
    overstuffed: list[str] = field(default_factory=list)
    underoptimised: bool = False

    def to_str(self) -> str:
        parts = []
        if self.overstuffed:
            parts.append(f"overstuffed: {', '.join(self.overstuffed)}")
        if self.underoptimised:
            parts.append("underoptimised")
        return "; ".join(parts) if parts else "none"


@dataclass
class ReadabilityResult:
    flesch_score: float = 0.0
    grade_label: str = ""
    gunning_fog: float = 0.0
    below_target: bool = False


@dataclass
class BrokenLink:
    url: str
    element: str
    status_code: Optional[int] = None
    error: Optional[str] = None


@dataclass
class PageResult:
    url: str
    status_code: int = 200
    title: str = ""
    meta: MetaIssues = field(default_factory=MetaIssues)
    keywords: KeywordResult = field(default_factory=KeywordResult)
    readability: ReadabilityResult = field(default_factory=ReadabilityResult)
    broken_links: list[BrokenLink] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    score: int = 0

    def compute_score(self) -> int:
        s = 100
        s -= self.meta.count() * 8
        s -= len(self.keywords.overstuffed) * 5
        s -= 10 if self.keywords.underoptimised else 0
        s -= 10 if self.readability.below_target else 0
        s -= min(len(self.broken_links) * 7, 30)
        self.score = max(s, 0)
        return self.score
