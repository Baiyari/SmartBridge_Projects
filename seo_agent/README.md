# SEO Audit Agent - AI-Powered Technical SEO Crawler

An enterprise-grade, autonomous website SEO auditing tool built with **Python**, **Groq LLM** (`llama-3.3-70b-versatile`), and **Google Sheets reporting**.

> [!NOTE]
> We have designed and built a gorgeous, high-fidelity marketing landing page under `/marketing` referencing Semrush's website aesthetic. It includes custom scrolling reveals, dynamic concurrent pipeline particle flows, sweeping score dials, live filters, and multiple page themes.

---

## Technical Features

1. **Breadth-First-Search Crawler**: Asynchronously discovers all reachable internal URLs within target domains (`crawler.py`).
2. **Parallel Checkers Suite**: Analyzes metadata structures, keyword stuffed articles, broken redirect href anchors, and readability index marks concurrently per page.
3. **Groq LLM Reasoner**: Packages consolidated page errors and requests prioritized, markdown remedies from `llama-3.3-70b-versatile` in one payload context.
4. **Google Sheets Sync**: Interacts with spreadsheet APIs using Google Cloud service credentials, compiling run logs for visual trend metrics.

---

## Directory Structure

```
├── /marketing/           # Premium Semrush-styled marketing website components
│   ├── index.html        # High-impact semantic landing page layout
│   ├── style.css         # Customized mint layout design system & keyframe rules
│   └── app.js            # Simulated CLI streams, dynamic visualizers & filters
│
└── /seo_agent/           # Production-ready Python core codebase
    ├── /agent/           # Core execution orchestrator
    ├── /config/          # General configurations & credentials parsing
    ├── /modules/         # Async crawler & individual analysis checkers
    └── /utils/           # HTML parsers & Google Sheets API writers
```

---

## Getting Started

### 1. Python Audit Core Setup

Navigate to the core agent folder:
```bash
cd seo_agent
pip install -r requirements.txt
```

Create a `.env` configuration file inside `/seo_agent` and fill in your keys:
```env
GROQ_API_KEY=your_groq_api_key_here
GOOGLE_SHEETS_CREDENTIALS=path/to/credentials.json
```

Run an autonomous audit on any domain target:
```bash
python main.py --url https://example.com --sheet-id YOUR_SPREADSHEET_ID
```
*Note: `--sheet-id` is optional. If omitted, the audit runs and outputs a beautiful CLI table.*

---

## Marketing Website Preview

To view the newly built interactive marketing landing page, open `/marketing/index.html` directly in your browser or run a simple server:
```bash
# In the repository root
python -m http.server 8000
```
Then navigate to `http://localhost:8000/marketing/` to experience:
- **Cinematic Hero Terminal**: Real-time crawling typing simulations.
- **Expandable Feature Dashboards**: Solutions expand in-place showing detailed mini tables.
- **Live Pipeline Simulator**: Concurrent particles floating along path lines.
- **Score Trend & Radial Gauge**: Interactive visibility dials and dropdown filter lists.
- **Custom Page Themes**: Toggle mint, dark, and matrix CLI color palettes instantly in the footer.
