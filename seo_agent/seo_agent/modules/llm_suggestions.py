import json
import logging
import re
import requests

from config.settings import settings
from utils.page_data import PageResult

log = logging.getLogger(__name__)

_SYSTEM_CRITICAL = (
    "You are an SEO expert. A web page has CRITICAL SEO failures that will severely hurt search rankings. "
    "Output ONLY a JSON object with a 'suggestions' key containing an array of exactly 2 strings. "
    "Each string must start with [CRITICAL] and give a specific, actionable fix in under 15 words. "
    'Example: {"suggestions": ["[CRITICAL] Add a <title> tag with the primary keyword between 30-65 characters."]}'
)

_SYSTEM_HIGH = (
    "You are an SEO expert. A web page has HIGH priority SEO issues that are hurting search visibility. "
    "Output ONLY a JSON object with a 'suggestions' key containing an array of exactly 2 strings. "
    "Each string must start with [HIGH] and give a specific, actionable fix in under 15 words. "
    'Example: {"suggestions": ["[HIGH] Write a unique 150-160 character meta description including the target keyword."]}'
)

_SYSTEM_LOW = (
    "You are an SEO expert. A web page has LOW priority SEO improvements available. "
    "Output ONLY a JSON object with a 'suggestions' key containing an array of exactly 2 strings. "
    "Each string must start with [LOW] and give a specific, actionable improvement in under 15 words. "
    'Example: {"suggestions": ["[LOW] Add Open Graph og:image tag sized 1200x630px for social sharing previews."]}'
)


def _classify_severity(result: PageResult) -> str:
    m = result.meta
    if m.missing_title or m.missing_meta_desc:
        return "critical"
    if m.title_too_short or m.title_too_long or m.missing_canonical or result.broken_links:
        return "high"
    return "low"


def _build_prompt(result: PageResult) -> str:
    lines = [f"Page URL: {result.url}", "Issues found:"]
    m = result.meta
    if m.missing_title:       lines.append("- Missing <title> tag entirely")
    if m.title_too_short:     lines.append("- Title tag too short (under 30 chars)")
    if m.title_too_long:      lines.append("- Title tag too long (over 65 chars)")
    if m.missing_meta_desc:   lines.append("- Missing meta description tag")
    if m.duplicate_meta_desc: lines.append("- Meta description duplicated across pages")
    if m.missing_canonical:   lines.append("- No canonical link tag present")
    if m.malformed_canonical: lines.append("- Canonical href is not an absolute URL")
    if m.missing_og_title:    lines.append("- Missing og:title Open Graph tag")
    if m.missing_og_desc:     lines.append("- Missing og:description Open Graph tag")
    if m.missing_og_image:    lines.append("- Missing og:image Open Graph tag")
    for kw in result.keywords.overstuffed[:2]:
        lines.append(f"- Keyword '{kw}' overstuffed above 4% density")
    if result.keywords.underoptimised:
        lines.append("- Page content is thin or keyword-poor")
    if result.readability.below_target:
        lines.append(f"- Low readability score: Flesch {round(result.readability.flesch_score, 1)}")
    if result.broken_links:
        lines.append(f"- {len(result.broken_links)} broken link(s) detected on page")
    return "\n".join(lines)


def _normalize(parsed: list) -> list[str]:
    """Convert any dict items like {'priority':'CRITICAL','action':'...'} to '[CRITICAL] ...' strings."""
    out = []
    for item in parsed:
        if isinstance(item, dict):
            priority = item.get("priority", item.get("level", "HIGH")).upper()
            action = item.get("action", item.get("text", item.get("fix", str(item))))
            out.append(f"[{priority}] {action}")
        else:
            out.append(str(item))
    return out


def _call_ollama(system_prompt: str, user_prompt: str) -> list[str] | None:
    try:
        response = requests.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.3},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            },
            timeout=90,
        )
        raw = response.json()["message"]["content"].strip()
        raw = re.sub(r"```[\w]*", "", raw).strip("`").strip()
        parsed = json.loads(raw)

        # Some models wrap arrays in a JSON object when format=json is used
        if isinstance(parsed, dict):
            # Try to find the first list value in the dict
            for val in parsed.values():
                if isinstance(val, list):
                    parsed = val
                    break

        if isinstance(parsed, list) and parsed:
            return _normalize(parsed)
    except requests.exceptions.Timeout:
        log.error("Ollama timed out (90s)")
    except json.JSONDecodeError as e:
        log.error(f"LLM invalid JSON: {e}\nRaw output: {raw}")
    except Exception as e:
        log.error(f"LLM call failed: {e}")
    return None


def generate_suggestions(result: PageResult) -> list[str]:
    prompt = _build_prompt(result)
    issue_count = prompt.count("\n- ")

    if issue_count == 0:
        return ["[LOW] No issues detected. Maintain current optimisation and monitor rankings."]

    severity = _classify_severity(result)
    system = _SYSTEM_CRITICAL if severity == "critical" else (_SYSTEM_HIGH if severity == "high" else _SYSTEM_LOW)

    suggestions = _call_ollama(system, prompt)
    if suggestions:
        return suggestions

    # Rule-based fallback — always returns real suggestions
    fallbacks = []
    m = result.meta
    if m.missing_title:
        fallbacks.append("[CRITICAL] Add a <title> tag with primary keyword, 30-65 characters long.")
    if m.missing_meta_desc:
        fallbacks.append("[CRITICAL] Write a unique meta description of 150-160 characters.")
    if m.missing_canonical:
        fallbacks.append("[HIGH] Add <link rel='canonical'> to prevent duplicate content penalties.")
    if result.broken_links:
        fallbacks.append(f"[HIGH] Fix {len(result.broken_links)} broken link(s) to avoid crawl errors.")
    if m.missing_og_title or m.missing_og_desc or m.missing_og_image:
        fallbacks.append("[MEDIUM] Add Open Graph tags (og:title, og:description, og:image) for social sharing.")
    if result.keywords.underoptimised:
        fallbacks.append("[LOW] Expand page content with relevant keywords to improve search relevancy.")

    return fallbacks if fallbacks else ["[HIGH] Review SEO issues listed above and fix by priority."]