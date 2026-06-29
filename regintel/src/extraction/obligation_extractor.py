"""
Obligation clause extraction using Llama 3 served by Groq's free-tier API.

Identifies binding regulatory language ("shall", "must", "within N days",
etc.) inside a circular's text and returns structured, typed obligation
records suitable for embedding and gap analysis downstream.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from textwrap import dedent

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from config import Settings

_SYSTEM_PROMPT = dedent(
    """\
    You are a regulatory compliance analyst for an Indian bank. Your job is
    to read excerpts of RBI/SEBI/FEMA circulars and extract every BINDING
    OBLIGATION clause — language such as "shall", "must", "is required to",
    or "within N days" that creates a concrete duty for a regulated entity.

    For each obligation found, return a JSON object with these exact keys:
      - "clause_text": the obligation sentence, verbatim, max 60 words
      - "obligation_type": one of
            ["reporting", "disclosure", "capital_liquidity", "kyc_aml",
             "governance", "deadline", "other"]
      - "deadline_text": the deadline phrase if stated, else null
      - "applicable_entity": who must comply, e.g. "Scheduled Commercial
            Banks", "NBFCs", "AIFs" — null if not specified

    Respond with ONLY a JSON array of such objects, no commentary, no
    markdown code fences. If no obligations are present, return [].
    """
)


@dataclass
class Obligation:
    clause_text: str
    obligation_type: str
    deadline_text: str | None
    applicable_entity: str | None
    circular_number: str | None = None
    regulator: str | None = None
    source_path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _build_llm(settings: Settings) -> ChatGroq:
    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.0,  # deterministic extraction, not creative writing
        max_retries=2,
        # Some Groq models (e.g. qwen/qwen3.6-27b) default to "thinking mode"
        # and prepend a <think>...</think> reasoning block before the actual
        # answer, which breaks the strict-JSON parsing below. reasoning_effort
        # is harmless to send to models that don't support it.
        model_kwargs={"reasoning_effort": "none"},
    )


def _chunk_text(text: str, max_chars: int = 6000) -> list[str]:
    """Split long circular text into LLM-context-friendly chunks,
    breaking on paragraph boundaries where possible."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_chars:
            if current:
                chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    reraise=True,
)
def _call_llm(llm: ChatGroq, chunk: str) -> list[dict]:
    response = llm.invoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"Circular excerpt:\n\n{chunk}"),
        ]
    )
    raw = response.content.strip()

    # Defensive cleanup: some reasoning-capable models (e.g. qwen/qwen3.6-27b)
    # still emit a <think>...</think> block before the actual answer even
    # with reasoning_effort="none" set on the request. Strip it so a stray
    # thinking block never breaks JSON parsing below.
    if "<think>" in raw:
        if "</think>" not in raw:
            # The model ran out of output tokens while still reasoning and
            # never produced an actual answer. There's nothing to recover —
            # raise a clear, specific error instead of a confusing JSON one.
            raise ValueError(
                "Model ran out of tokens while still inside a <think> block "
                "and never produced an answer. This usually means "
                "reasoning_effort isn't being honored, or max_tokens is too "
                "low for this model's reasoning overhead."
            )
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Defensive cleanup: some models wrap JSON in markdown fences anyway.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    if not raw:
        return []

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model returned non-JSON output: {raw[:200]}") from exc

    if not isinstance(parsed, list):
        raise ValueError("Model response was not a JSON array as instructed.")
    return parsed


def extract_obligations(
    circular_text: str,
    *,
    circular_number: str | None = None,
    regulator: str | None = None,
    source_path: str | None = None,
    settings: Settings | None = None,
) -> list[Obligation]:
    """Extract structured obligations from full circular text.

    Long circulars are chunked to stay within model context limits;
    obligations from all chunks are merged into a single flat list.
    """
    settings = settings or Settings.load()
    llm = _build_llm(settings)

    obligations: list[Obligation] = []
    for chunk in _chunk_text(circular_text):
        raw_items = _call_llm(llm, chunk)
        for item in raw_items:
            try:
                obligations.append(
                    Obligation(
                        clause_text=item["clause_text"],
                        obligation_type=item.get("obligation_type", "other"),
                        deadline_text=item.get("deadline_text"),
                        applicable_entity=item.get("applicable_entity"),
                        circular_number=circular_number,
                        regulator=regulator,
                        source_path=source_path,
                    )
                )
            except KeyError:
                # Skip malformed items rather than failing the whole batch.
                continue

    return obligations