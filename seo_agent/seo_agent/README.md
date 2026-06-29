# Website SEO Auditing Agent

AI-powered SEO analysis using **Ollama (Mistral)** + **Google Sheets** reporting.

> **Note:** The LLM backend is Ollama running locally (not Groq). Make sure Ollama is installed and the `mistral` model is pulled before running.

---

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running locally
- Google Cloud Service Account credentials (for Sheets reporting)

---

## Setup

### 1. Install Python dependencies

```bash
cd seo_agent
pip install -r requirements.txt
```

### 2. Start Ollama and pull the model

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the Mistral model
ollama pull mistral

# Start the Ollama server (keep this running in the background)
ollama serve
```

### 3. Configure environment variables

Edit the `.env` file inside `/seo_agent` and fill in your values:

```env
GOOGLE_SHEETS_CREDENTIALS=credentials.json
GOOGLE_SHEET_ID=your_google_sheet_id_here
```

> No API key is needed for the LLM — Ollama runs fully locally.

### 4. Set up Google Sheets (optional)

To enable Sheets reporting:
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a Service Account and download the JSON credentials
3. Save the file as `credentials.json` inside the `seo_agent/` folder
4. Share your target Google Sheet with the service account email address

---

## Run

### CLI audit (no Sheets)

```bash
python main.py --url https://example.com
```

### CLI audit with Google Sheets reporting

```bash
python main.py --url https://example.com --sheet-id YOUR_SHEET_ID
```

`--sheet-id` is optional. Without it, the audit runs and prints a summary table to the terminal only.

### Run as a Flask API server

```bash
python api.py
# Server starts at http://localhost:5000
```

Then POST to the `/audit` endpoint:

```bash
curl -X POST http://localhost:5000/audit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

---

## What It Checks

| Module | What It Does |
|---|---|
| `meta_checker.py` | Title tags, meta descriptions, canonical, Open Graph |
| `keyword_analyser.py` | Keyword density — flags overstuffed and under-optimised pages |
| `readability.py` | Flesch score and Gunning Fog index |
| `link_detector.py` | Broken internal and external links |
| `llm_suggestions.py` | Prioritised fixes via local Mistral model |
| `sheets_writer.py` | Writes results to Google Sheets dashboard |

---

## Troubleshooting

**LLM suggestions show "Could not generate" fallback**
→ Ollama is not running. Start it with `ollama serve` and ensure `mistral` is pulled.

**Google Sheets write fails**
→ Check that `credentials.json` exists in the `seo_agent/` folder and the sheet is shared with the service account email.

**No pages found during crawl**
→ Ensure the target URL includes the scheme: `https://example.com`, not `example.com`.
