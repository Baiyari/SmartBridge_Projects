# RegIntel — Regulatory Document Intelligence Engine

Agentic AI system for automated RBI/SEBI/FEMA compliance gap detection.
Runs entirely on free-tier infrastructure — no GPU, no paid API, no cloud server.

---

## What this project does

1. **Ingests** an RBI/SEBI/FEMA circular PDF (PyMuPDF)
2. **Extracts** binding obligation clauses using a Groq-hosted LLM (LangChain)
3. **Embeds** obligations and your internal policies into a local vector DB (ChromaDB + Sentence-Transformers)
4. **Detects gaps** between regulatory obligations and existing internal policy coverage
5. **Scores and ranks** each gap by penalty exposure
6. **Orchestrates all four steps above as a LangChain tool-calling agent** — not a fixed script — so it can retry a thin PDF extraction, re-run obligation extraction on a suspiciously empty result, or flag a missing policy library, instead of failing silently
7. **Reports** results in a live Flask-based Audit Console dashboard, a downloadable PDF, and a persistent SQLite audit history

---

## 1. Install Anaconda (if you don't have it)

Download and install Miniconda (lightweight, recommended) from:
https://docs.conda.io/en/latest/miniconda.html

Verify the install:

```bash
conda --version
```

---

## 2. Create the project environment

From a terminal, navigate into the `regintel` project folder, then run:

```bash
conda create -n regintel python=3.10 -y
conda activate regintel
```

You should now see `(regintel)` at the start of your terminal prompt — that means the environment is active. **Every command below must be run inside this activated environment.**

---

## 3. Install all dependencies (LangChain, ChromaDB, Flask, etc.)

Everything needed is pinned in `requirements.txt`. Install it in one shot:

```bash
pip install -r requirements.txt
```

This installs, among others:
- `langchain`, `langchain-groq`, `langchain-community` — agentic orchestration + Groq LLM client
- `chromadb`, `sentence-transformers` — local vector database + free CPU embeddings
- `pymupdf` — PDF parsing
- `reportlab`, `openpyxl` — PDF and Excel report generation
- `flask` — backend API + Audit Console dashboard
- `streamlit`, `plotly`, `pandas` — legacy dashboard (see note below)

If you only want LangChain + the Groq integration on their own (e.g. to test in a separate script), you can install just those with:

```bash
pip install langchain langchain-groq
```

---

## 4. Get a free Groq API key

Groq hosts fast open-weight LLMs for free, with generous rate limits and no credit card required.

1. Go to **https://console.groq.com**
2. Sign up / log in (Google or GitHub login works)
3. Click **API Keys** in the left sidebar
4. Click **Create API Key**, name it (e.g. `regintel-dev`), and copy the key
   - it looks like `gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - **you will only see it once** — copy it immediately

---

## 5. Configure your environment variables

Create a `.env` file in the project root with the following keys:

```
GROQ_API_KEY=gsk_your_real_key_here
GROQ_MODEL=llama-3.3-70b-versatile
CHROMA_PERSIST_DIR=data/chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

`.env` is already excluded from version control via `.gitignore` — never commit your real key.

> **A note on `GROQ_MODEL`:** any Groq-hosted model works for raw text generation, but the orchestration agent specifically needs a model whose tool-calling output LangChain's `create_tool_calling_agent` can parse cleanly. `llama-3.3-70b-versatile` is the recommended default. Some reasoning-mode models (e.g. `qwen/qwen3.6-27b`) prepend a `<think>...</think>` block that can break tool-call parsing even with `reasoning_effort` set to `"none"`; if you swap models, run the app once and check the startup health-check output (see Step 7) before relying on it.

---

## 6. Add your internal policy documents (optional but recommended)

Drop your bank/NBFC's internal SOP or policy documents as plain `.txt` files into:

```
data/policies/
```

This folder ships empty. Without at least one policy file indexed, every extracted obligation will be flagged as a gap by necessity — the agent will note this explicitly as a caveat rather than failing, but it isn't useful for testing real coverage. Add a policy file before running your first real audit.

A handful of real regulatory circular PDFs are already bundled in `data/circulars/` as ready-to-use test assets — `generate_dummy_circular.py` is also included if you want to generate a synthetic one.

---

## 7. Run the application

```bash
python flask_app.py
```

This starts the Flask backend on `http://127.0.0.1:5000`. On startup, it runs a health check against your configured Groq model — watch the terminal for either `RegIntelPipeline successfully initialized` or a specific failure message — before the Audit Console becomes usable.

From the browser:

1. Open `http://127.0.0.1:5000`
2. On the **Run Audit** tab, drag and drop a circular PDF (or click **Browse files**)
3. Watch the agent step through parsing → obligation extraction → policy gap-checking → penalty scoring
4. Review the ranked gaps, severity charts, and risk bands, and download the generated PDF report
5. Switch to the **Audit History** tab to review past runs, logged automatically to a local SQLite database

> **Legacy dashboard:** `app.py` still contains an earlier Streamlit-based dashboard (`streamlit run app.py`) wired to the same `RegIntelPipeline`. It is kept for reference but is not the primary interface — use `flask_app.py` for the current Audit Console experience.

---

## 8. Run from the command line (alternative to the dashboard)

```bash
python run_audit.py data/circulars/<your_circular>.pdf
```

This runs the exact same `RegIntelPipeline` used by the Flask backend, prints a ranked gap summary to the terminal, and saves a PDF report to `outputs/reports/`.

---

## 9. Run the test suite

Pure-logic unit tests (no API calls, run instantly):

```bash
pip install pytest
pytest tests/ -v
```

---

## Project structure

```
regintel/
├── flask_app.py                 # Flask backend + Audit Console API (primary entry point)
├── app.py                       # Legacy Streamlit dashboard (kept for reference)
├── run_audit.py                 # CLI entry point
├── config.py                    # Centralised settings loader (.env)
├── requirements.txt
├── .env                         # Your Groq key + model + vector store config (not committed)
├── data/
│   ├── circulars/                # Regulatory PDFs to audit
│   ├── policies/                 # Drop internal SOP .txt files here (ships empty)
│   ├── chroma_db/                # Local persistent vector store (auto-created)
│   └── audit_log.db              # SQLite audit history (auto-created)
├── outputs/
│   └── reports/                  # Auto-generated PDF gap reports
├── frontend/
│   ├── index.html                # Audit Console UI
│   ├── app.js                    # Upload handling, agent-trace animation, charts
│   └── styles.css                # Dashboard styling
├── src/
│   ├── ingestion/pdf_parser.py            # PDF parsing (PyMuPDF)
│   ├── extraction/obligation_extractor.py # LLM obligation extraction (Groq/LangChain)
│   ├── vectorstore/chroma_manager.py      # Embeddings + gap detection (ChromaDB)
│   ├── scoring/penalty_scorer.py          # Penalty exposure scoring
│   ├── report/pdf_report.py               # PDF report generation (ReportLab)
│   ├── report/excel_report.py             # Excel report generation (openpyxl)
│   ├── storage/audit_log.py               # SQLite audit run history
│   ├── utils/groq_healthcheck.py          # Startup model/tool-calling health check
│   └── agent/orchestrator.py              # LangChain AgentExecutor tying all stages together
└── tests/
    └── test_penalty_scorer.py    # Offline unit tests
```

---

## Troubleshooting

**"Missing required environment variable 'GROQ_API_KEY'"**
You haven't created `.env` yet, or it still contains a placeholder value (anything starting with `your_`). Re-check Step 5.

**Pipeline fails to initialize / "GROQ HEALTH CHECK FAILED" in the terminal**
The configured `GROQ_MODEL` is either deprecated or returns a tool-call format `create_tool_calling_agent` can't parse. Check the specific message printed at startup, then fix `GROQ_MODEL` in `.env` and restart `flask_app.py`. `llama-3.3-70b-versatile` is the known-good default.

**`ModuleNotFoundError` for any package**
Make sure your conda environment is activated (`conda activate regintel`) and you ran `pip install -r requirements.txt` inside it, not in your system Python.

**PDF parsing returns no text**
The PDF is likely a scanned image rather than native text. This pipeline (by design, to stay free/local) does not include OCR; re-export or source a text-based PDF.

**Every obligation comes back as a gap**
Check whether `data/policies/` actually has any `.txt` files in it. With zero policies indexed, every obligation is a gap by definition — the agent will flag this as a caveat in its summary, but it's expected behaviour, not a bug.

**Groq rate limit errors**
The free tier has per-minute request limits. The extractor already retries with exponential backoff (`tenacity`); for very large circulars, consider splitting into smaller PDFs.

**Resetting the vector database**
Delete the `data/chroma_db/` folder and re-run an audit — it will be recreated automatically.

---

## Notes on design choices

- **Agentic, not a free-form loop.** A LangChain `AgentExecutor` decides at runtime whether to retry a thin PDF extraction, re-run obligation extraction on an empty result, or proceed — but it still calls the same four tools, in the same order, every time, with every call logged. This keeps the audit trail intact while letting the system handle edge cases a rigid script would choke on.
- **Local-first.** ChromaDB persists to disk; embeddings run on CPU via Sentence-Transformers. The only network call is to the Groq API for obligation extraction and agent reasoning.
- **Zero cost to operate**, beyond the free tiers documented above.