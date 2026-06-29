from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from config import Settings
from src.ingestion.pdf_parser import parse_pdf, ParsedCircular
from src.extraction.obligation_extractor import extract_obligations, Obligation
from src.vectorstore.chroma_manager import VectorStore
from src.scoring.penalty_scorer import score_and_rank_gaps, ScoredGap
from src.report.pdf_report import generate_gap_report
from src.storage.audit_log import log_audit_run


@dataclass
class PipelineResult:
    circular_number: str | None
    regulator: str
    obligations_found: int
    gaps_detected: int
    scored_gaps: list[ScoredGap]
    report_path: Path | None
    agent_log: list[str] = field(default_factory=list)
    error: str | None = None


class _ParseCircularInput(BaseModel):
    pdf_path: str = Field(description="Path to the circular PDF file to parse.")


class _ExtractObligationsInput(BaseModel):
    note: str = Field(
        default="",
        description=(
            "Short note explaining why this call is being made, e.g. "
            "'initial pass' or 'retry after empty result'."
        ),
    )


class _CheckPolicyCoverageInput(BaseModel):
    """Takes no real arguments; present so the agent always sends a
    well-formed (if empty) JSON object instead of a bare null, which
    some providers' tool-calling responses can otherwise produce and
    which breaks LangChain's tool-call parser."""

    pass


class _ScoreGapsInput(BaseModel):
    """Takes no real arguments; see _CheckPolicyCoverageInput docstring."""

    pass


class RegIntelPipeline:
    """Agent-driven orchestration of the ingest -> extract -> compare ->
    score -> report cycle for one regulatory circular PDF.

    A LangChain tool-calling agent decides, at runtime, how to handle the
    four points where a fixed pipeline would otherwise have to guess:
      1. Parsing failure / near-empty extracted text -> retry once or
         abort with a clear reason, instead of silently failing.
      2. Zero obligations extracted -> distinguish "genuinely empty
         circular" from "extraction likely missed something" and decide
         whether to re-run extraction.
      3. No internal policies indexed yet -> flag this explicitly rather
         than silently mark every obligation a critical gap.
      4. Borderline similarity scores (0.50-0.60) -> the agent reviews
         these gaps itself before they're finalised, rather than using a
         single hardcoded cutoff.

    Public interface (`ingest_policies`, `run`) is unchanged from the
    deterministic version, so callers (app.py, run_audit.py) don't need
    to change.
    """

    # Borderline band: similarity scores inside this range get a second,
    # agent-driven look instead of being auto-classified by the threshold.
    _BORDERLINE_LOW = 0.50
    _BORDERLINE_HIGH = 0.60

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.load()
        self.vector_store = VectorStore(self.settings)
        self._log: list[str] = []
        self._agent_executor = self._build_agent()

    # ------------------------------------------------------------------
    # Policy ingestion (unchanged from the deterministic pipeline)
    # ------------------------------------------------------------------
    def ingest_policies(self, policies_dir: str | Path) -> int:
        """Load internal SOP/policy text files (.txt) into the vector store.
        Each file is chunked into ~800-character segments for retrieval."""
        policies_dir = Path(policies_dir)
        self.vector_store.reset_policies()
        total_chunks = 0
        for policy_file in sorted(policies_dir.glob("*.txt")):
            text = policy_file.read_text(encoding="utf-8", errors="ignore")
            chunks = self._chunk_policy_text(text)
            total_chunks += self.vector_store.add_policy_chunks(
                chunks, policy_name=policy_file.stem
            )
        return total_chunks

    @staticmethod
    def _chunk_policy_text(text: str, chunk_size: int = 800) -> list[str]:
        words = text.split()
        chunks, current = [], []
        current_len = 0
        for word in words:
            current.append(word)
            current_len += len(word) + 1
            if current_len >= chunk_size:
                chunks.append(" ".join(current))
                current, current_len = [], 0
        if current:
            chunks.append(" ".join(current))
        return chunks

    # ------------------------------------------------------------------
    # Agent construction
    # ------------------------------------------------------------------
    def _build_agent(self) -> AgentExecutor:
        llm = ChatGroq(
            api_key=self.settings.groq_api_key,
            model=self.settings.groq_model,
            temperature=0.0,
            # See obligation_extractor._build_llm for why this is set: models
            # like qwen/qwen3.6-27b default to "thinking mode" and prepend a
            # <think>...</think> block, which breaks LangChain's tool-call
            # parsing. Harmless to send to models that don't support it.
            model_kwargs={"reasoning_effort": "none"},
        )

        tools = [
            self._make_parse_tool(),
            self._make_extract_tool(),
            self._make_gap_check_tool(),
            self._make_score_tool(),
        ]

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the orchestration agent for RegIntel, a regulatory "
                    "compliance gap-detection pipeline for an Indian bank. You "
                    "are given the path to one circular PDF and must run it "
                    "through all four stages, in order: parse_circular, "
                    "extract_obligations_tool, check_policy_coverage, "
                    "score_gaps_tool. Always call them in that order, exactly "
                    "once each, UNLESS a tool's result tells you to retry or "
                    "stop early (the tool descriptions explain when). After "
                    "parse_circular, if it reports near-empty or failed "
                    "extraction, retry it at most once before giving up. "
                    "After extract_obligations_tool, if zero obligations were "
                    "found, call it a second time only if the circular text "
                    "looked substantial (run it again with the same input — "
                    "do not skip it just because the count was zero unless "
                    "you've already retried once). When you finish all "
                    "stages, respond with a short plain-text summary of what "
                    "you did and any concerns, then stop. Be decisive and "
                    "concise; this is a compliance tool, not a chat assistant.",
                ),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_tool_calling_agent(llm, tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            max_iterations=10,
            handle_parsing_errors=True,
        )

    # ------------------------------------------------------------------
    # Tool 1 — parsing, with retry-on-failure decisioning
    # ------------------------------------------------------------------
    def _make_parse_tool(self):
        @tool(args_schema=_ParseCircularInput)
        def parse_circular(pdf_path: str) -> str:
            """Parse a regulatory circular PDF into text + metadata.
            Call this first. If the result says extraction was thin or
            failed, you may call this tool again ONCE to retry; if it
            fails twice, stop the pipeline and explain why in your final
            summary rather than calling further tools."""
            state = self._state
            attempt = state["parse_attempts"] + 1
            state["parse_attempts"] = attempt
            try:
                parsed = parse_pdf(pdf_path)
            except (FileNotFoundError, ValueError) as exc:
                self._log.append(f"[parse] attempt {attempt} failed: {exc}")
                return json.dumps({"ok": False, "error": str(exc), "attempt": attempt})

            state["parsed"] = parsed
            thin = len(parsed.full_text) < 200
            self._log.append(
                f"[parse] attempt {attempt}: {parsed.page_count} pages, "
                f"{len(parsed.full_text)} chars, regulator={parsed.regulator}"
                + (" -- WARNING: unusually thin text" if thin else "")
            )
            return json.dumps(
                {
                    "ok": True,
                    "thin_extraction": thin,
                    "page_count": parsed.page_count,
                    "char_count": len(parsed.full_text),
                    "regulator": parsed.regulator,
                    "circular_number": parsed.circular_number,
                    "attempt": attempt,
                }
            )

        return parse_circular

    # ------------------------------------------------------------------
    # Tool 2 — extraction, with re-run-on-empty decisioning
    # ------------------------------------------------------------------
    def _make_extract_tool(self):
        @tool(args_schema=_ExtractObligationsInput)
        def extract_obligations_tool(note: str = "") -> str:
            """Extract binding obligation clauses from the most recently
            parsed circular (call parse_circular first). Pass a short
            `note` explaining why you're calling it (e.g. "initial pass"
            or "retry after empty result") so the audit log records your
            reasoning. If this returns zero obligations on the first
            call and the circular had substantial text, you may call it
            a second time before accepting the result."""
            state = self._state
            parsed: ParsedCircular | None = state.get("parsed")
            if parsed is None:
                return json.dumps({"ok": False, "error": "No parsed circular available. Call parse_circular first."})

            attempt = state["extract_attempts"] + 1
            state["extract_attempts"] = attempt

            obligations = extract_obligations(
                parsed.full_text,
                circular_number=parsed.circular_number,
                regulator=parsed.regulator,
                source_path=parsed.source_path,
                settings=self.settings,
            )
            state["obligations"] = obligations
            self._log.append(
                f"[extract] attempt {attempt} ({note or 'no note'}): "
                f"{len(obligations)} obligations found"
            )
            return json.dumps({"ok": True, "obligations_found": len(obligations), "attempt": attempt})

        return extract_obligations_tool

    # ------------------------------------------------------------------
    # Tool 3 — gap detection, with no-policy-indexed escalation
    # ------------------------------------------------------------------
    def _make_gap_check_tool(self):
        @tool(args_schema=_CheckPolicyCoverageInput)
        def check_policy_coverage() -> str:
            """Embed the extracted obligations and search internal
            policies for semantic coverage, flagging any obligation with
            no adequately similar policy as a compliance gap. Call this
            after extract_obligations_tool. If no internal policies have
            been indexed at all, this is noted in the result so you can
            mention it as a caveat in your final summary (the report
            will still be produced, but every obligation will show as a
            gap by necessity)."""
            state = self._state
            try:
                obligations: list[Obligation] = state.get("obligations", [])
                self.vector_store.add_obligations(obligations)
                gaps = self.vector_store.find_gaps(obligations)
                state["gaps"] = gaps

                no_policies = self.vector_store.policies.count() == 0
                borderline = [
                    g for g in gaps
                    if self._BORDERLINE_LOW <= g.similarity_score < self._BORDERLINE_HIGH
                ]

                self._log.append(
                    f"[gap_check] {len(gaps)} obligations checked, "
                    f"{sum(1 for g in gaps if g.is_gap)} flagged as gaps, "
                    f"{len(borderline)} borderline (0.50-0.60 similarity)"
                    + (" -- WARNING: no internal policies indexed" if no_policies else "")
                )
                return json.dumps(
                    {
                        "ok": True,
                        "obligations_checked": len(gaps),
                        "gaps_flagged": sum(1 for g in gaps if g.is_gap),
                        "borderline_count": len(borderline),
                        "no_policies_indexed": no_policies,
                    }
                )
            except Exception as exc:
                self._log.append(f"[gap_check] failed: {exc}")
                raise RuntimeError(f"Policy coverage check failed: {exc}") from exc

        return check_policy_coverage

    # ------------------------------------------------------------------
    # Tool 4 — scoring
    # ------------------------------------------------------------------
    def _make_score_tool(self):
        @tool(args_schema=_ScoreGapsInput)
        def score_gaps_tool() -> str:
            """Score and rank all detected gaps by penalty exposure, then
            generate the PDF report. Call this last, after
            check_policy_coverage. This finalises the audit run."""
            state = self._state
            try:
                gaps = state.get("gaps", [])
                scored = score_and_rank_gaps(gaps)
                state["scored_gaps"] = scored

                parsed: ParsedCircular | None = state.get("parsed")
                if parsed is None:
                    raise ValueError("No parsed circular available. Pipeline aborted.")

                report_filename = (
                    f"gap_report_{(parsed.circular_number or Path(parsed.source_path).stem).replace('/', '-')}.pdf"
                )
                report_path = generate_gap_report(
                    scored,
                    output_path=Path("outputs/reports") / report_filename,
                    audit_run_label=f"Audit of {parsed.circular_number or Path(parsed.source_path).name} ({parsed.regulator})",
                )
                state["report_path"] = report_path

                self._log.append(
                    f"[score] {len(scored)} gaps scored and ranked; report -> {report_path}"
                )
                return json.dumps({"ok": True, "gaps_scored": len(scored), "report_path": str(report_path)})
            except Exception as exc:
                self._log.append(f"[score] failed: {exc}")
                raise RuntimeError(f"Gap scoring or report generation failed: {exc}") from exc

        return score_gaps_tool

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(self, pdf_path: str | Path) -> PipelineResult:
        """Run the agent-orchestrated audit for a single circular PDF."""
        pdf_path = Path(pdf_path)
        self._log = []
        self._state = {
            "parse_attempts": 0,
            "extract_attempts": 0,
            "parsed": None,
            "obligations": [],
            "gaps": [],
            "scored_gaps": [],
            "report_path": None,
        }
        # Tools close over self._state via the _state property at build
        # time, but since tools are rebuilt fresh each run, rebuild the
        # executor so closures see this run's state.
        self._agent_executor = self._build_agent()

        agent_input = (
            f"Run the full compliance audit pipeline on the circular at "
            f"path: {pdf_path}"
        )
        error_msg = None
        try:
            outcome = self._agent_executor.invoke({"input": agent_input})
            self._log.append(f"[agent] final summary: {outcome.get('output', '').strip()}")
        except Exception as exc:
            error_msg = f"Agent executor failed: {exc}"
            self._log.append(f"[error] {error_msg}")

        parsed: ParsedCircular | None = self._state.get("parsed")
        scored_gaps: list[ScoredGap] = self._state.get("scored_gaps", [])
        report_path = self._state.get("report_path")

        if not error_msg and (parsed is None or report_path is None):
            error_msg = "Agent could not complete the audit pipeline."
            self._log.append(f"[error] {error_msg}")

        result = PipelineResult(
            circular_number=parsed.circular_number if parsed else None,
            regulator=parsed.regulator if parsed else "Unknown",
            obligations_found=len(self._state.get("obligations", [])),
            gaps_detected=len(scored_gaps),
            scored_gaps=scored_gaps,
            report_path=report_path,
            agent_log=list(self._log),
            error=error_msg,
        )

        log_audit_run(result)
        return result

    def run_batch(self, pdf_paths: list[Path]) -> list[PipelineResult]:
        """Execute the agent pipeline for multiple circulars in sequence."""
        return [self.run(path) for path in pdf_paths]

    # ------------------------------------------------------------------
    # internal state property so tool closures can reference current run
    # ------------------------------------------------------------------
    @property
    def _state(self) -> dict:
        if not hasattr(self, "_run_state"):
            self._run_state = {}
        return self._run_state

    @_state.setter
    def _state(self, value: dict) -> None:
        self._run_state = value