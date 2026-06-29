import re
from config.settings import settings
from utils.page_data import ReadabilityResult


def _syllable_count(word):
    word = word.lower().strip(".:;?!")
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?:[^aeiou]es|ed|[^aeiou]e)$', '', word)
    word = re.sub(r'^y', '', word)
    return len(re.findall(r'[aeiou]+', word)) or 1


def _counts(text):
    sentences = len(re.findall(r'[.!?]+', text)) or 1
    words = re.findall(r'\b\w+\b', text)
    syllables = sum(_syllable_count(w) for w in words)
    return sentences, len(words) or 1, syllables


def flesch_reading_ease(text):
    sentences, words, syllables = _counts(text)
    return 206.835 - 1.015 * (words / sentences) - 84.6 * (syllables / words)


def gunning_fog(text):
    sentences, words, _ = _counts(text)
    word_list = re.findall(r'\b\w+\b', text)
    complex_words = sum(1 for w in word_list if _syllable_count(w) >= 3)
    return 0.4 * ((words / sentences) + 100 * (complex_words / words))


_GRADES = [
    (90, "Very easy"), (80, "Easy"), (70, "Fairly easy"),
    (60, "Standard"), (50, "Fairly difficult"),
    (30, "Difficult"), (0, "Very difficult"),
]


def _label(score: float) -> str:
    for threshold, label in _GRADES:
        if score >= threshold:
            return label
    return "Very difficult"


def score_readability(text: str) -> ReadabilityResult:
    if not text or len(text.split()) < 30:
        return ReadabilityResult(below_target=True, grade_label="Insufficient content")

    flesch = flesch_reading_ease(text)
    fog = gunning_fog(text)

    return ReadabilityResult(
        flesch_score=round(flesch, 2),
        grade_label=_label(flesch),
        gunning_fog=round(fog, 2),
        below_target=flesch < settings.readability_min,
    )
