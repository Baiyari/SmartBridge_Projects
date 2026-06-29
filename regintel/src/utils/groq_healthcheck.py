"""
Startup health check for the configured Groq model.

RegIntel's pipeline depends on two things working together:
  1. The configured Groq model existing and being callable with this API key.
  2. That model's tool-call output being something LangChain's
     `create_tool_calling_agent` / `AgentExecutor` can actually parse.

Both have broken in practice — (1) when Groq deprecates a model out from
under a pinned config value, and (2) when a newly-chosen replacement model
uses a tool-call format LangChain's agent scaffold doesn't handle cleanly
(this happened with `openai/gpt-oss-120b`, which uses OpenAI's "Harmony"
response format and is documented to throw a `KeyError: '_type'` deep in
LangChain's serializer under `create_tool_calling_agent`).

Either failure mode used to surface only when a real audit hit `/api/audit`,
as an opaque 500 with no clear cause. This module runs the *same* code path
(a minimal LangChain tool-calling agent against the real configured model)
at startup, with a trivial dummy tool, so a bad model choice is caught
immediately with a clear, specific diagnosis instead of three layers deep
inside a real pipeline run.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from config import Settings


@dataclass
class HealthCheckResult:
    ok: bool
    message: str
    detail: str | None = None


def _build_probe_agent(settings: Settings) -> AgentExecutor:
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.0,
        # Mirror the real pipeline's LLM config exactly (see
        # obligation_extractor._build_llm) so this probe catches
        # thinking-mode-related failures too, not just auth/deprecation.
        model_kwargs={"reasoning_effort": "none"},
    )

    @tool
    def ping(value: str) -> str:
        """Echo back the given value. Used only to verify tool-calling works."""
        return f"pong:{value}"

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You must call the `ping` tool exactly once with value='healthcheck', "
                "then report its result in one short sentence.",
            ),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, [ping], prompt)
    return AgentExecutor(agent=agent, tools=[ping], verbose=False, max_iterations=3)


def check_groq_model(settings: Settings) -> HealthCheckResult:
    """Run a minimal tool-calling round trip against the configured Groq
    model. Returns a HealthCheckResult; never raises — all failure modes
    are caught and translated into a clear message."""
    try:
        executor = _build_probe_agent(settings)
    except Exception as exc:
        return HealthCheckResult(
            ok=False,
            message=(
                f"Could not build a LangChain agent for Groq model "
                f"'{settings.groq_model}'. Check GROQ_API_KEY and GROQ_MODEL "
                f"in your .env file."
            ),
            detail=str(exc),
        )

    try:
        outcome = executor.invoke({"input": "Run the health check."})
    except Exception as exc:
        exc_text = str(exc)
        lower = exc_text.lower()

        if "decommissioned" in lower or "model_decommissioned" in lower:
            message = (
                f"Groq model '{settings.groq_model}' has been decommissioned. "
                f"Check https://console.groq.com/docs/deprecations for the "
                f"current recommended replacement and update GROQ_MODEL in .env."
            )
        elif "non-json output" in lower or "<think>" in exc_text:
            message = (
                f"Groq model '{settings.groq_model}' is emitting <think>...</think> "
                f"reasoning text instead of calling tools cleanly, even with "
                f"reasoning_effort='none' set. This model's thinking mode may not "
                f"be fully suppressible. Try a non-reasoning model in GROQ_MODEL."
            )
        elif "_type" in exc_text or "tool_use_failed" in lower or "harmony" in lower:
            message = (
                f"Groq model '{settings.groq_model}' responded, but its "
                f"tool-call output isn't compatible with LangChain's "
                f"create_tool_calling_agent. This is a known issue with some "
                f"models (e.g. openai/gpt-oss-120b uses a response format that "
                f"breaks this agent type). Try a different model in GROQ_MODEL, "
                f"e.g. qwen/qwen3.6-27b."
            )
        elif "api key" in lower or "unauthorized" in lower or "401" in exc_text:
            message = (
                "Groq rejected the API key. Check GROQ_API_KEY in your .env file."
            )
        else:
            message = (
                f"Groq model '{settings.groq_model}' failed during a startup "
                f"tool-calling check. See detail below for the raw error."
            )

        return HealthCheckResult(ok=False, message=message, detail=exc_text)

    output_text = str(outcome.get("output", ""))
    if "pong" not in output_text.lower():
        return HealthCheckResult(
            ok=False,
            message=(
                f"Groq model '{settings.groq_model}' completed the health check "
                f"without an error, but never actually called the test tool — it "
                f"answered in plain text instead. This model likely won't "
                f"reliably drive RegIntel's multi-step tool-calling pipeline. "
                f"Try a different model in GROQ_MODEL."
            ),
            detail=f"Agent output: {output_text[:300]}",
        )

    return HealthCheckResult(
        ok=True,
        message=f"Groq model '{settings.groq_model}' passed the tool-calling health check.",
    )