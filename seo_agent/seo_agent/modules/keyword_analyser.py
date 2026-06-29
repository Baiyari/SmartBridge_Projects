import re
from collections import Counter

from config.settings import settings
from utils.page_data import KeywordResult

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "is", "was", "are", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should", "may",
    "might", "this", "that", "it", "its", "from", "by", "not", "are", "if",
    "as", "so", "we", "you", "he", "she", "they", "our", "your", "their",
}


def _tokens(text: str) -> list[str]:
    return [
        w.lower() for w in re.findall(r"\b[a-zA-Z]{%d,}\b" % settings.keyword_min_length, text)
        if w.lower() not in _STOPWORDS
    ]


def analyse_keywords(text: str) -> KeywordResult:
    tokens = _tokens(text)
    if not tokens:
        return KeywordResult(underoptimised=True)

    total = len(tokens)
    counts = Counter(tokens)
    top = counts.most_common(settings.keyword_top_n)

    return KeywordResult(
        top_keywords=[(w, round(c / total, 4)) for w, c in top],
        overstuffed=[w for w, c in top if c / total > settings.density_overuse],
        underoptimised=(top[0][1] / total < settings.density_underuse) if top else True,
    )
