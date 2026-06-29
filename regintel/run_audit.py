"""
Command-line entry point for RegIntel.

Usage:
    python run_audit.py path/to/circular.pdf
    python run_audit.py path/to/circular.pdf --policies data/policies
"""

from __future__ import annotations

# Import redirection hook to resolve environment package conflicts
import sys
try:
    import langchain_classic
    sys.modules["langchain"] = langchain_classic
except ImportError:
    pass

import argparse
from pathlib import Path

from config import Settings
from src.agent.orchestrator import RegIntelPipeline
from src.utils.groq_healthcheck import check_groq_model


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a RegIntel compliance gap audit on a single circular PDF."
    )
    parser.add_argument("pdf_path", type=Path, help="Path to the circular PDF")
    parser.add_argument(
        "--policies",
        type=Path,
        default=Path("data/policies"),
        help="Directory of internal policy .txt files (default: data/policies)",
    )
    args = parser.parse_args()

    try:
        settings = Settings.load()
    except EnvironmentError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    print(f"Running Groq health check against model '{settings.groq_model}'...")
    health = check_groq_model(settings)
    if not health.ok:
        print("=" * 70, file=sys.stderr)
        print("GROQ HEALTH CHECK FAILED — aborting before running the audit.", file=sys.stderr)
        print(health.message, file=sys.stderr)
        if health.detail:
            print(f"Detail: {health.detail}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        return 1
    print(health.message)

    pipeline = RegIntelPipeline(settings)

    if args.policies.exists():
        n_chunks = pipeline.ingest_policies(args.policies)
        print(f"Indexed {n_chunks} policy chunks from {args.policies}")
    else:
        print(f"Warning: policy directory {args.policies} not found — skipping.")

    print(f"Running audit on {args.pdf_path} ...")
    result = pipeline.run(args.pdf_path)

    print()
    if result.error:
        print(f"AUDIT FAILED: {result.error}")
    else:
        print(f"Regulator:          {result.regulator}")
        print(f"Circular number:    {result.circular_number}")
        print(f"Obligations found:  {result.obligations_found}")
        print(f"Gaps detected:      {result.gaps_detected}")
        print(f"Report saved to:    {result.report_path}")
        print()

        for i, gap in enumerate(result.scored_gaps, start=1):
            print(f"  [{i}] {gap.risk_band:8s} score={gap.penalty_score:5.1f}  {gap.clause_text[:90]}")

    return 0 if not result.error else 1


if __name__ == "__main__":
    sys.exit(main())