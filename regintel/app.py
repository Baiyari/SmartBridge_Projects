"""
RegIntel — Streamlit Compliance Dashboard.

Run with:  streamlit run app.py

Lets a compliance officer upload circular PDFs, runs them through the
full RegIntel pipeline, and displays gap status, penalty exposure
scores, and remediation priority in a live, sortable view.
"""

from __future__ import annotations

# Import redirection hook to resolve environment package conflicts
import sys
try:
    import langchain_classic
    sys.modules["langchain"] = langchain_classic
except ImportError:
    pass

import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from config import Settings, REPORTS_DIR
from src.agent.orchestrator import RegIntelPipeline
from src.report.pdf_report import generate_gap_report
from src.report.excel_report import generate_gap_excel
from src.storage.audit_log import get_audit_history

st.set_page_config(
    page_title="RegIntel \u2014 Compliance Gap Engine",
    page_icon="\U0001f6e1\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# DESIGN TOKENS — extracted verbatim from frontend/styles.css
# ─────────────────────────────────────────────────────────────────────────────
DESIGN_CSS = """
<style>
/* == Google Fonts == */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* == Design Tokens == */
:root {
    --bg-primary:        #0A0D14;
    --bg-secondary:      #121620;
    --bg-tertiary:       #1A1F2D;
    --text-primary:      #F9F9FA;
    --text-secondary:    #A0A5B5;
    --text-muted:        #6B7280;
    --accent-teal:       #005B70;
    --accent-teal-light: #007A96;
    --accent-teal-dark:  #003D4A;
    --status-success:    #10B981;
    --status-warning:    #F59E0B;
    --status-error:      #EF4444;
    --status-info:       #3B82F6;
    --risk-critical:     #EF4444;
    --risk-high:         #F97316;
    --risk-med:          #F59E0B;
    --risk-low:          #10B981;
    --font-sans:         'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-serif:        'Playfair Display', Georgia, serif;
    --font-mono:         'JetBrains Mono', monospace;
    --radius-sm:         4px;
    --radius-md:         8px;
    --radius-lg:         12px;
    --radius-xl:         20px;
    --transition-fast:   0.15s ease;
    --transition-normal: 0.3s ease;
}

/* == Global App Shell == */
html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-sans) !important;
    -webkit-font-smoothing: antialiased;
}

[data-testid="stMain"], .main, .block-container {
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
    padding-top: 1.5rem !important;
}

.block-container {
    max-width: 1400px !important;
}

/* == Sidebar == */
[data-testid="stSidebar"] {
    background-color: var(--bg-secondary) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] * {
    color: var(--text-secondary) !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] strong {
    color: var(--text-primary) !important;
}

/* == Tabs == */
[data-testid="stTabs"] > div:first-child {
    border-bottom: 1px solid rgba(255,255,255,0.08) !important;
    background: transparent !important;
}
button[data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-secondary) !important;
    font-family: var(--font-sans) !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    padding: 0.6rem 1.25rem !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    transition: color var(--transition-fast) !important;
}
button[data-baseweb="tab"]:hover {
    color: var(--text-primary) !important;
    background: rgba(255,255,255,0.04) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--text-primary) !important;
    background: transparent !important;
    border-bottom: 2px solid var(--accent-teal-light) !important;
}
[data-testid="stTabPanel"] {
    padding-top: 1.5rem !important;
    background: transparent !important;
}

/* == Headings == */
h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-serif) !important;
    color: var(--text-primary) !important;
    line-height: 1.25 !important;
}

/* == Dividers == */
hr, .stDivider {
    border-color: rgba(255,255,255,0.07) !important;
}

/* == Primary Buttons == */
[data-testid="stButton"] > button[kind="primary"] {
    background-color: var(--accent-teal) !important;
    color: var(--text-primary) !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-sans) !important;
    font-weight: 500 !important;
    font-size: 0.95rem !important;
    padding: 0.65rem 1.5rem !important;
    transition: background-color var(--transition-normal), transform var(--transition-fast), box-shadow var(--transition-normal) !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    background-color: var(--accent-teal-light) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(0, 91, 112, 0.35) !important;
}

/* == Secondary Buttons == */
[data-testid="stButton"] > button:not([kind="primary"]) {
    background-color: rgba(255,255,255,0.05) !important;
    color: var(--text-primary) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-sans) !important;
    font-weight: 500 !important;
    transition: background-color var(--transition-fast), border-color var(--transition-fast) !important;
}
[data-testid="stButton"] > button:not([kind="primary"]):hover {
    background-color: rgba(255,255,255,0.09) !important;
    border-color: rgba(255,255,255,0.2) !important;
}

/* == Download Buttons == */
[data-testid="stDownloadButton"] > button {
    background-color: var(--accent-teal) !important;
    color: var(--text-primary) !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font-sans) !important;
    font-weight: 500 !important;
    transition: background-color var(--transition-normal), transform var(--transition-fast) !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background-color: var(--accent-teal-light) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0, 91, 112, 0.3) !important;
}

/* == File Uploader == */
[data-testid="stFileUploader"] {
    background: var(--bg-tertiary) !important;
    border: 2px dashed rgba(0, 91, 112, 0.4) !important;
    border-radius: var(--radius-lg) !important;
    padding: 0.5rem !important;
    transition: border-color var(--transition-normal) !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent-teal-light) !important;
}
[data-testid="stFileUploader"] * {
    color: var(--text-secondary) !important;
}
[data-testid="stFileUploader"] label {
    color: var(--text-primary) !important;
    font-weight: 500 !important;
}

/* == Metrics == */
[data-testid="stMetric"] {
    background: var(--bg-tertiary) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: var(--radius-lg) !important;
    padding: 1.1rem 1.25rem !important;
    transition: box-shadow var(--transition-normal), transform var(--transition-normal) !important;
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
    transform: translateY(-2px) !important;
}
[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}
[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-family: var(--font-serif) !important;
    font-size: 1.9rem !important;
}

/* == DataFrames == */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] > div {
    background: var(--bg-tertiary) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
}

/* == Select / Multiselect == */
[data-testid="stMultiSelect"] > div,
[data-testid="stSelectbox"] > div {
    background: var(--bg-tertiary) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
}
.stMultiSelect [data-baseweb="tag"] {
    background: rgba(0, 91, 112, 0.25) !important;
    border: 1px solid var(--accent-teal) !important;
    color: var(--text-primary) !important;
    border-radius: var(--radius-sm) !important;
}

/* == Alerts == */
[data-testid="stAlert"] {
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
}

/* == Caption == */
[data-testid="stCaptionContainer"], .stCaption {
    color: var(--text-muted) !important;
    font-size: 0.82rem !important;
}

/* == Plotly chart dark wrappers == */
.stPlotlyChart > div {
    background: var(--bg-tertiary) !important;
    border-radius: var(--radius-lg) !important;
    border: 1px solid rgba(255,255,255,0.05) !important;
    padding: 0.25rem !important;
}

/* == Custom card class == */
.ri-card {
    background: var(--bg-tertiary);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: var(--radius-lg);
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.25rem;
    transition: box-shadow var(--transition-normal);
}
.ri-card:hover {
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
}

/* == Section label == */
.ri-section-label {
    font-family: var(--font-sans);
    font-size: 0.73rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--accent-teal-light);
    margin-bottom: 0.3rem;
    margin-top: 0.2rem;
}

/* == Hero area == */
.ri-hero {
    padding: 1.75rem 0 1.5rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 1.5rem;
    background: radial-gradient(circle at 90% 10%, rgba(0, 91, 112, 0.12) 0%, transparent 55%);
}
.ri-hero-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 2.6rem;
    font-weight: 600;
    letter-spacing: -0.025em;
    color: #F9F9FA;
    line-height: 1.2;
    margin: 0;
}
.ri-hero-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 1rem;
    color: #A0A5B5;
    margin-top: 0.5rem;
    font-weight: 400;
    max-width: 680px;
}
.ri-hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 91, 112, 0.15);
    border: 1px solid rgba(0, 122, 150, 0.3);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.78rem;
    font-weight: 500;
    color: #007A96;
    margin-bottom: 0.75rem;
    font-family: 'Inter', sans-serif;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.ri-hero-badge::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #007A96;
    animation: pulse-dot 2s infinite;
    flex-shrink: 0;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* == Sidebar step cards == */
.sidebar-step {
    background: rgba(0, 91, 112, 0.08);
    border: 1px solid rgba(0, 91, 112, 0.2);
    border-radius: var(--radius-md);
    padding: 0.85rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.88rem;
    color: var(--text-secondary);
    line-height: 1.6;
}
.sidebar-step strong {
    color: var(--text-primary) !important;
}

/* == Explainability box == */
.ri-explain {
    background: rgba(0, 91, 112, 0.08);
    border: 1px solid rgba(0, 122, 150, 0.25);
    border-radius: var(--radius-md);
    padding: 1rem 1.25rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
    line-height: 1.7;
    margin-top: 0.5rem;
}
.ri-explain strong {
    color: var(--text-primary);
}

/* == Scrollbar == */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-secondary); }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.2); }
</style>
"""

st.markdown(DESIGN_CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Plotly dark theme applied to every chart
# ─────────────────────────────────────────────────────────────────────────────
_PLOTLY_LAYOUT = dict(
    paper_bgcolor="#1A1F2D",
    plot_bgcolor="#1A1F2D",
    font=dict(family="Inter, sans-serif", color="#A0A5B5", size=12),
    title_font=dict(family="Playfair Display, Georgia, serif", color="#F9F9FA", size=14),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.05)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zerolinecolor="rgba(255,255,255,0.05)"),
    colorway=["#005B70", "#007A96", "#F59E0B", "#EF4444"],
)


@st.cache_resource(show_spinner=False)
def get_pipeline() -> RegIntelPipeline:
    return RegIntelPipeline(Settings.load())


def _risk_color_map() -> dict[str, str]:
    return {
        "Critical": "#EF4444",
        "High":     "#F97316",
        "Medium":   "#F59E0B",
        "Low":      "#10B981",
    }


def _apply_plotly_theme(fig, title: str | None = None) -> None:
    """Apply the RegIntel dark theme to any Plotly figure in-place."""
    fig.update_layout(**_PLOTLY_LAYOUT)
    if title:
        fig.update_layout(title_text=title)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:1.2rem;">
                <span style="font-size:1.4rem;">\U0001f6e1\ufe0f</span>
                <span style="font-family:\'Playfair Display\',serif;font-size:1.35rem;
                             font-weight:600;color:#F9F9FA;letter-spacing:-0.01em;">RegIntel</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="ri-section-label">Quick Setup</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="sidebar-step"><strong>Step 1</strong><br>
            Place internal policy <code>.txt</code> files in <code>data/policies/</code>
            before your first audit.</div>
            <div class="sidebar-step"><strong>Step 2</strong><br>
            Upload one or more RBI / SEBI / FEMA circular PDFs.</div>
            <div class="sidebar-step"><strong>Step 3</strong><br>
            Click <strong>\u25b6\ufe0f Run Compliance Audit</strong> to analyse gaps.</div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown(
            '<span style="color:#6B7280;font-size:0.78rem;line-height:1.6;">'
            "Powered by Llama\u00a03 (Groq) \u00b7 LangChain \u00b7 ChromaDB \u00b7 "
            "Sentence-Transformers \u00b7 Streamlit</span>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Hero header
# ─────────────────────────────────────────────────────────────────────────────
def render_hero() -> None:
    st.markdown(
        """
        <div class="ri-hero">
            <div class="ri-hero-badge">Live Dashboard \u00b7 RBI / SEBI / FEMA</div>
            <div class="ri-hero-title">Compliance, Verified Automatically.</div>
            <div class="ri-hero-subtitle">
                Agentic AI gap-detection for Indian banks and NBFCs \u2014 extract obligations
                from regulatory circulars, map to internal policies, score exposure risk.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Policy ingestion
# ─────────────────────────────────────────────────────────────────────────────
def render_policy_ingestion(pipeline: RegIntelPipeline) -> None:
    st.markdown('<div class="ri-section-label">Policy Library</div>', unsafe_allow_html=True)
    st.subheader("\U0001f4c2 Internal Policy Library")
    policies_dir = Path("data/policies")
    existing = list(policies_dir.glob("*.txt"))

    col1, col2 = st.columns([3, 1])
    with col1:
        if existing:
            st.success(f"**{len(existing)}** policy file(s) loaded from `data/policies/`.")
        else:
            st.warning(
                "No policy files found in `data/policies/`. "
                "Every obligation will be flagged as a gap until policies are added."
            )
    with col2:
        if st.button("\U0001f504 Re-index Policies", use_container_width=True):
            with st.spinner("Embedding policy documents\u2026"):
                try:
                    count = pipeline.ingest_policies(policies_dir)
                    st.success(f"Indexed {count} policy chunks.")
                    st.toast(f"\u2705 Indexed {count} policy chunks.")
                except Exception as e:
                    st.error(f"Failed to index policies: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Upload & Run
# ─────────────────────────────────────────────────────────────────────────────
def render_upload_and_run(pipeline: RegIntelPipeline) -> None:
    st.markdown(
        '<div class="ri-section-label" style="margin-top:1rem;">Audit Engine</div>',
        unsafe_allow_html=True,
    )
    st.subheader("\U0001f4c4 New Circular Audit")
    uploaded_files = st.file_uploader(
        "Upload regulatory circular PDFs",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("\u25b6\ufe0f Run Compliance Audit", type="primary"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_paths = []
            for uf in uploaded_files:
                tmp_path = Path(tmp_dir) / uf.name
                tmp_path.write_bytes(uf.getvalue())
                tmp_paths.append(tmp_path)

            with st.spinner("Parsing PDFs \u00b7 Extracting obligations \u00b7 Detecting gaps\u2026"):
                results = pipeline.run_batch(tmp_paths)

        st.session_state["last_results"] = results
        successful_results = [r for r in results if not r.error]
        failed_results     = [r for r in results if r.error]

        for r in failed_results:
            st.error(
                f"Failed to audit circular "
                f"{getattr(r, 'filename', 'Unknown') or 'Unknown'}: {r.error}"
            )

        # Pre-generate Excel files for individual runs
        for r in successful_results:
            if r.report_path:
                excel_path = r.report_path.with_suffix(".xlsx")
            else:
                circ_name  = r.circular_number or "Unknown_Circular"
                excel_name = f"gap_report_{circ_name.replace('/', '-')}.xlsx"
                excel_path = REPORTS_DIR / excel_name
            try:
                generate_gap_excel(r.scored_gaps, excel_path)
                r.excel_path = excel_path
            except Exception as e:
                st.error(f"Failed to generate Excel report for {r.circular_number}: {e}")
                r.excel_path = None

        # Pre-generate combined reports if multiple circulars audited
        if len(successful_results) > 1:
            all_scored_gaps: list = []
            for r in successful_results:
                all_scored_gaps.extend(r.scored_gaps)
            try:
                combined_pdf_path = REPORTS_DIR / "combined_gap_report.pdf"
                generate_gap_report(
                    all_scored_gaps,
                    output_path=combined_pdf_path,
                    audit_run_label="Batch Audit Run",
                )
                st.session_state["combined_pdf_path"] = combined_pdf_path
            except Exception as e:
                st.error(f"Failed to generate combined PDF report: {e}")
                st.session_state["combined_pdf_path"] = None
            try:
                combined_excel_path = REPORTS_DIR / "combined_gap_report.xlsx"
                generate_gap_excel(all_scored_gaps, combined_excel_path)
                st.session_state["combined_excel_path"] = combined_excel_path
            except Exception as e:
                st.error(f"Failed to generate combined Excel report: {e}")
                st.session_state["combined_excel_path"] = None
        else:
            st.session_state.pop("combined_pdf_path",  None)
            st.session_state.pop("combined_excel_path", None)

        total_gaps = sum(r.gaps_detected     for r in successful_results)
        total_obs  = sum(r.obligations_found  for r in successful_results)
        if successful_results:
            st.success(
                f"\u2705 Audit complete \u2014 **{total_obs}** obligations found, "
                f"**{total_gaps}** gap(s) detected across "
                f"**{len(successful_results)}** circular(s)."
            )


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────
def render_results() -> None:
    results = st.session_state.get("last_results")
    if not results:
        st.markdown(
            '<div class="ri-card" style="text-align:center;padding:2.5rem 1.75rem;">'
            '<span style="font-size:2.5rem;">\U0001f4cb</span><br>'
            '<p style="color:#A0A5B5;margin-top:0.75rem;font-size:1rem;">'
            'Upload circular PDF(s) above and click '
            '<strong style="color:#F9F9FA;">\u25b6\ufe0f Run Compliance Audit</strong> '
            "to see gap analysis results here.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div class="ri-section-label" style="margin-top:1rem;">Results</div>',
        unsafe_allow_html=True,
    )
    st.subheader("\U0001f4ca Combined Audit Results")

    successful_results = [r for r in results if not r.error]
    if not successful_results:
        st.warning("All uploaded circulars failed processing. No results to display.")
        return

    all_scored_gaps: list = []
    for r in successful_results:
        all_scored_gaps.extend(r.scored_gaps)

    total_obs  = sum(r.obligations_found for r in successful_results)
    total_gaps = sum(r.gaps_detected     for r in successful_results)
    regulators = sorted({r.regulator for r in successful_results if r.regulator})

    col1, col2, col3 = st.columns(3)
    col1.metric("Regulator(s)",      ", ".join(regulators) if regulators else "\u2014")
    col2.metric("Obligations Found", total_obs)
    col3.metric("Gaps Detected",     total_gaps)

    if not all_scored_gaps:
        st.success("\U0001f389 No compliance gaps detected \u2014 existing policies cover all obligations.")
        return

    # ── Visual Insights ──────────────────────────────────────────────────────
    st.markdown(
        '<div class="ri-section-label" style="margin-top:1.5rem;">Visual Insights</div>',
        unsafe_allow_html=True,
    )
    st.subheader("\U0001f4ca Compliance Visual Insights")

    risk_order = ["Critical", "High", "Medium", "Low"]
    color_map  = _risk_color_map()

    # Chart 1 — Gaps by Risk Severity (donut)
    risk_counts  = pd.DataFrame([{"Risk Band": g.risk_band} for g in all_scored_gaps])
    risk_summary = risk_counts.groupby("Risk Band").size().reset_index(name="Count")
    for band in risk_order:
        if band not in risk_summary["Risk Band"].values:
            risk_summary = pd.concat(
                [risk_summary, pd.DataFrame([{"Risk Band": band, "Count": 0}])],
                ignore_index=True,
            )
    risk_summary["Risk Band"] = pd.Categorical(
        risk_summary["Risk Band"], categories=risk_order, ordered=True
    )
    risk_summary = risk_summary.sort_values("Risk Band")

    fig_donut = px.pie(
        risk_summary,
        names="Risk Band",
        values="Count",
        hole=0.45,
        color="Risk Band",
        color_discrete_map=color_map,
    )
    fig_donut.update_traces(
        textinfo="percent+label",
        textfont=dict(family="Inter, sans-serif", color="#F9F9FA"),
    )
    _apply_plotly_theme(fig_donut, "Gaps by Risk Severity")
    fig_donut.update_layout(showlegend=False, height=320, margin=dict(t=48, b=10, l=10, r=10))

    # Chart 2 — Gaps by Regulator (donut)
    reg_df      = pd.DataFrame([{"Regulator": g.regulator or "Unknown"} for g in all_scored_gaps])
    reg_summary = reg_df.groupby("Regulator").size().reset_index(name="Count")
    fig_reg = px.pie(
        reg_summary,
        names="Regulator",
        values="Count",
        hole=0.45,
        color_discrete_sequence=["#005B70", "#007A96", "#F59E0B", "#F97316", "#EF4444"],
    )
    fig_reg.update_traces(
        textinfo="percent+label",
        textfont=dict(family="Inter, sans-serif", color="#F9F9FA"),
    )
    _apply_plotly_theme(fig_reg, "Gaps by Regulator")
    fig_reg.update_layout(showlegend=False, height=320, margin=dict(t=48, b=10, l=10, r=10))

    # Chart 3 — Gaps by circular (stacked bar)
    circ_df = pd.DataFrame([
        {"Circular": g.circular_number or "Unknown", "Risk Band": g.risk_band}
        for g in all_scored_gaps
    ])
    circ_summary = (
        circ_df.groupby(["Circular", "Risk Band"], observed=False)
        .size()
        .reset_index(name="Count")
    )
    circ_summary["Risk Band"] = pd.Categorical(
        circ_summary["Risk Band"], categories=risk_order, ordered=True
    )
    circ_summary = circ_summary.sort_values("Risk Band")

    fig_circ = px.bar(
        circ_summary,
        x="Circular",
        y="Count",
        color="Risk Band",
        color_discrete_map=color_map,
    )
    _apply_plotly_theme(fig_circ, "Gaps Count by Circular")
    fig_circ.update_layout(
        xaxis_title=None,
        yaxis_title="Gap Count",
        height=320,
        margin=dict(t=48, b=40, l=10, r=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(color="#A0A5B5"),
        ),
    )

    # Chart 4 — Top-5 highest-risk gaps (horizontal bar)
    top_n    = 5
    top_gaps = sorted(all_scored_gaps, key=lambda x: x.penalty_score, reverse=True)[:top_n]
    top_df   = pd.DataFrame([
        {
            "Penalty Score": g.penalty_score,
            "Gap Detail":    f"[{g.circular_number or 'Unk'}] {g.clause_text[:40]}\u2026",
            "Risk Band":     g.risk_band,
        }
        for g in top_gaps
    ]).iloc[::-1].reset_index(drop=True)

    fig_bar = px.bar(
        top_df,
        x="Penalty Score",
        y="Gap Detail",
        color="Risk Band",
        color_discrete_map=color_map,
        orientation="h",
    )
    _apply_plotly_theme(fig_bar, "Top 5 Highest Risk Gaps (Priority Remediation)")
    fig_bar.update_layout(
        yaxis_title=None,
        xaxis_title="Penalty/Risk Score (0\u2013100)",
        showlegend=False,
        height=320,
        margin=dict(t=48, b=40, l=10, r=10),
    )

    # Render 2\xd72 grid
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(fig_donut, use_container_width=True)
    with chart_col2:
        st.plotly_chart(fig_reg,   use_container_width=True)

    chart_col3, chart_col4 = st.columns(2)
    with chart_col3:
        st.plotly_chart(fig_circ, use_container_width=True)
    with chart_col4:
        st.plotly_chart(fig_bar,  use_container_width=True)

    # ── Upcoming Deadlines ───────────────────────────────────────────────────
    upcoming = [g for g in all_scored_gaps if g.days_remaining is not None]
    if upcoming:
        st.markdown(
            '<div class="ri-section-label" style="margin-top:1rem;">Deadlines</div>',
            unsafe_allow_html=True,
        )
        st.subheader("\u23f1\ufe0f Upcoming Deadlines")
        upcoming_sorted = sorted(upcoming, key=lambda x: x.days_remaining)
        up_df = pd.DataFrame([{
            "Days Remaining":    g.days_remaining,
            "Risk Band":         g.risk_band,
            "Circular":          g.circular_number or "\u2014",
            "Obligation Clause": g.clause_text,
        } for g in upcoming_sorted])
        st.dataframe(up_df, hide_index=True, use_container_width=True)

    # ── Gap Filters ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="ri-section-label" style="margin-top:1rem;">Filter &amp; Explore</div>',
        unsafe_allow_html=True,
    )
    st.subheader("\U0001f50d Filter Gaps")

    df_raw = [
        {
            "Risk Band":         g.risk_band,
            "Penalty Score":     g.penalty_score,
            "Regulator":         g.regulator or "\u2014",
            "Applicable Entity": g.applicable_entity or "\u2014",
            "Circular":          g.circular_number or "\u2014",
            "Obligation Clause": g.clause_text,
            "Deadline":          g.deadline_text or "\u2014",
            "_gap_id":           g.obligation_id,
        }
        for g in all_scored_gaps
    ]
    df = pd.DataFrame(df_raw)

    colA, colB = st.columns(2)
    with colA:
        regs     = sorted(df["Regulator"].unique().tolist())
        sel_regs = st.multiselect("Regulator", regs, default=regs)
    with colB:
        entities     = sorted(df["Applicable Entity"].unique().tolist())
        sel_entities = st.multiselect("Applicable Entity", entities, default=entities)

    filtered_df = df[
        df["Regulator"].isin(sel_regs) & df["Applicable Entity"].isin(sel_entities)
    ].copy()
    sorted_df = filtered_df.sort_values("Penalty Score", ascending=False).reset_index(drop=True)

    st.markdown(
        '<div class="ri-section-label" style="margin-top:1rem;">Gap Table</div>',
        unsafe_allow_html=True,
    )
    st.subheader("\U0001f4cb Gap Analysis Table")
    st.caption("Click a row to view the explainability breakdown.")

    st.dataframe(
        sorted_df,
        use_container_width=True,
        hide_index=True,
        column_config={"_gap_id": None},
        on_select="rerun",
        selection_mode="single-row",
        key="gap_table",
    )

    # ── Explainability ───────────────────────────────────────────────────────
    if st.session_state.gap_table and st.session_state.gap_table.selection.rows:
        selected_idx = st.session_state.gap_table.selection.rows[0]
        gap_id       = sorted_df.iloc[selected_idx]["_gap_id"]
        gap          = next((g for g in all_scored_gaps if g.obligation_id == gap_id), None)
        if gap:
            st.markdown(
                f"""
                <div class="ri-explain">
                    <strong>Explainability Breakdown</strong><br><br>
                    <strong>Score Components:</strong>
                    Severity:\u00a0{gap.severity_component} +
                    Urgency:\u00a0{gap.urgency_component} +
                    Staleness:\u00a0{gap.staleness_component}
                    = <strong>{gap.penalty_score}</strong> ({gap.risk_band})<br><br>
                    <strong>Closest Internal Policy Match</strong>
                    (Similarity:\u00a0{gap.similarity_score}):<br>
                    <em style="color:#A0A5B5;">{gap.best_policy_match or "None found"}</em>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Export Reports ───────────────────────────────────────────────────────
    st.markdown(
        '<div class="ri-section-label" style="margin-top:1.5rem;">Export</div>',
        unsafe_allow_html=True,
    )
    st.subheader("\U0001f4e5 Export Reports")

    st.markdown("**\U0001f4c4 Individual Circular Reports**")
    for idx, r in enumerate(successful_results):
        circ_name = r.circular_number or "Unknown Circular"
        st.markdown(
            f'<div style="color:#A0A5B5;font-size:0.9rem;margin-bottom:0.4rem;">'
            f'<strong style="color:#F9F9FA;">Circular: {circ_name}</strong>'
            f" ({r.regulator}) \u2014 {r.gaps_detected} gap(s) detected</div>",
            unsafe_allow_html=True,
        )

        pdf_path   = r.report_path
        excel_path = getattr(r, "excel_path", None)
        if not excel_path and pdf_path:
            excel_path = pdf_path.with_suffix(".xlsx")

        dl_col_pdf, dl_col_xlsx = st.columns(2)
        if pdf_path and pdf_path.exists():
            with open(pdf_path, "rb") as f:
                dl_col_pdf.download_button(
                    label=f"\u2b07\ufe0f Download PDF ({circ_name})",
                    data=f.read(),
                    file_name=pdf_path.name,
                    mime="application/pdf",
                    key=f"dl_pdf_{idx}_{circ_name.replace('/', '_')}",
                    use_container_width=True,
                )
        else:
            dl_col_pdf.warning("PDF report not found")

        if excel_path and excel_path.exists():
            with open(excel_path, "rb") as f:
                dl_col_xlsx.download_button(
                    label=f"\u2b07\ufe0f Download Excel ({circ_name})",
                    data=f.read(),
                    file_name=excel_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"dl_xlsx_{idx}_{circ_name.replace('/', '_')}",
                    use_container_width=True,
                )
        else:
            dl_col_xlsx.warning("Excel report not found")
        st.divider()

    combined_pdf_path   = st.session_state.get("combined_pdf_path")
    combined_excel_path = st.session_state.get("combined_excel_path")

    if len(successful_results) > 1:
        st.markdown("**\U0001f4c1 Combined Session Report (Batch Audit)**")
        st.caption("Includes compliance gap details from all audited circulars in this session.")
        comb_col1, comb_col2 = st.columns(2)
        with comb_col1:
            if (
                combined_pdf_path
                and combined_pdf_path.exists()
                and combined_pdf_path.stat().st_size > 0
            ):
                with open(combined_pdf_path, "rb") as f:
                    st.download_button(
                        "\u2b07\ufe0f Download Combined PDF Report",
                        data=f.read(),
                        file_name="combined_gap_report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_comb_pdf",
                    )
            else:
                st.warning("Combined PDF report not found")
        with comb_col2:
            if (
                combined_excel_path
                and combined_excel_path.exists()
                and combined_excel_path.stat().st_size > 0
            ):
                with open(combined_excel_path, "rb") as f:
                    st.download_button(
                        "\u2b07\ufe0f Download Combined Excel Report",
                        data=f.read(),
                        file_name="combined_gap_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="dl_comb_xlsx",
                    )
            else:
                st.warning("Combined Excel report not found")


# ─────────────────────────────────────────────────────────────────────────────
# Audit History
# ─────────────────────────────────────────────────────────────────────────────
def render_audit_history() -> None:
    st.markdown('<div class="ri-section-label">Audit History</div>', unsafe_allow_html=True)
    st.subheader("\U0001f552 Audit History")
    history = get_audit_history()

    if not history:
        st.markdown(
            '<div class="ri-card" style="text-align:center;padding:2.5rem 1.75rem;">'
            '<span style="font-size:2rem;">\U0001f552</span><br>'
            '<p style="color:#A0A5B5;margin-top:0.75rem;">'
            "No audit history yet. Run an audit to log data.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    df_hist = pd.DataFrame(history)
    df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])
    df_hist = df_hist.sort_values("timestamp")

    hist_col1, hist_col2 = st.columns(2)

    with hist_col1:
        st.markdown("**Gaps Detected Over Time**")
        fig_gaps = px.line(df_hist, x="timestamp", y="gaps_detected", markers=True)
        fig_gaps.update_traces(line_color="#007A96", marker_color="#007A96")
        _apply_plotly_theme(fig_gaps)
        fig_gaps.update_layout(xaxis_title=None, yaxis_title="Total Gaps", height=280)
        st.plotly_chart(fig_gaps, use_container_width=True)

    with hist_col2:
        st.markdown("**Risk Band Composition Over Time**")
        risk_cols = [
            "critical_gaps_count", "high_gaps_count",
            "medium_gaps_count",   "low_gaps_count",
        ]
        for col in risk_cols:
            if col not in df_hist.columns:
                df_hist[col] = 0
            df_hist[col] = df_hist[col].fillna(0).astype(int)

        df_melted = pd.melt(
            df_hist,
            id_vars=["timestamp"],
            value_vars=risk_cols,
            var_name="Risk Band",
            value_name="Count",
        )
        band_mapping = {
            "critical_gaps_count": "Critical",
            "high_gaps_count":     "High",
            "medium_gaps_count":   "Medium",
            "low_gaps_count":      "Low",
        }
        df_melted["Risk Band"] = df_melted["Risk Band"].map(band_mapping)
        df_melted["Risk Band"] = pd.Categorical(
            df_melted["Risk Band"],
            categories=["Critical", "High", "Medium", "Low"],
            ordered=True,
        )
        fig_comp = px.bar(
            df_melted,
            x="timestamp",
            y="Count",
            color="Risk Band",
            color_discrete_map=_risk_color_map(),
        )
        _apply_plotly_theme(fig_comp)
        fig_comp.update_layout(
            xaxis_title=None,
            yaxis_title="Gap Count",
            height=280,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(color="#A0A5B5"),
            ),
        )
        st.plotly_chart(fig_comp, use_container_width=True)

    st.markdown("**Past Audit Runs**")
    display_cols = [
        "timestamp", "circular_number", "regulator",
        "obligations_found", "gaps_detected", "avg_penalty_score",
    ]
    st.dataframe(
        df_hist[display_cols].sort_values("timestamp", ascending=False),
        hide_index=True,
        use_container_width=True,
    )

    st.divider()
    st.markdown(
        '<div class="ri-section-label">Past Reports</div>', unsafe_allow_html=True
    )
    st.subheader("\U0001f4e5 Retrieve Past Reports")
    st.caption("Select a logged audit run below to retrieve its original PDF/Excel gap reports.")

    run_options: list[str] = []
    run_dict: dict         = {}
    for _, row in df_hist.sort_values("timestamp", ascending=False).iterrows():
        ts_str = pd.to_datetime(row["timestamp"]).strftime("%Y-%m-%d %H:%M")
        label  = (
            f"{ts_str} \u2014 {row['circular_number']} "
            f"({row['regulator']}) \u2014 {row['gaps_detected']} gaps"
        )
        run_options.append(label)
        run_dict[label] = row

    if run_options:
        selected_label = st.selectbox("Select Past Run", run_options)
        selected_run   = run_dict[selected_label]

        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Gaps Detected",    selected_run["gaps_detected"])
        m_col2.metric(
            "Avg Penalty Score",
            f"{selected_run['avg_penalty_score']:.1f}"
            if pd.notnull(selected_run["avg_penalty_score"]) else "\u2014",
        )
        m_col3.metric("Obligations Found", selected_run["obligations_found"])

        pdf_path_str = selected_run.get("report_path")
        if pdf_path_str:
            pdf_path   = Path(pdf_path_str)
            excel_path = pdf_path.with_suffix(".xlsx")

            dl_col1, dl_col2 = st.columns(2)
            if pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    dl_col1.download_button(
                        label=f"\u2b07\ufe0f Download PDF ({selected_run['circular_number']})",
                        data=f.read(),
                        file_name=pdf_path.name,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"dl_past_pdf_{selected_run['id']}",
                    )
            else:
                dl_col1.warning("Original PDF report file not found on disk.")

            if excel_path.exists():
                with open(excel_path, "rb") as f:
                    dl_col2.download_button(
                        label=f"\u2b07\ufe0f Download Excel ({selected_run['circular_number']})",
                        data=f.read(),
                        file_name=excel_path.name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"dl_past_xlsx_{selected_run['id']}",
                    )
            else:
                dl_col2.warning("Original Excel report file not found on disk.")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    render_sidebar()
    render_hero()

    try:
        pipeline = get_pipeline()
    except EnvironmentError as exc:
        st.error(str(exc))
        st.stop()

    tab1, tab2 = st.tabs(["\U0001f680 Audit Engine", "\U0001f552 Audit History"])

    with tab1:
        render_policy_ingestion(pipeline)
        st.divider()
        render_upload_and_run(pipeline)
        st.divider()
        render_results()

    with tab2:
        render_audit_history()


if __name__ == "__main__":
    main()
