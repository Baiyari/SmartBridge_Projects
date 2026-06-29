"""
Google Sheets dashboard writer — upgraded with native charts & Issues Summary tab.

Sheet structure:
  1. "Dashboard"      — KPI panel + per-URL rows with score trend (5 runs)
  2. "Audit Log"      — append-only raw per-page data every run
  3. "Run History"    — one summary row per audit run
  4. "Issues Summary" — top issues ranked by frequency across all pages  ← NEW
  5. Embedded Charts  — Score Distribution (bar) + Avg Score Trend (line) ← NEW
"""

import re
import random
import string
from datetime import datetime, timezone
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials

from config.settings import settings
from utils.page_data import PageResult

# ── Auth ──────────────────────────────────────────────────────────────────────

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        settings.sheets_credentials_path, scopes=_SCOPES
    )
    return gspread.authorize(creds)


# ── Sheet names ───────────────────────────────────────────────────────────────

_DASHBOARD      = "Dashboard"
_AUDIT_LOG      = "Audit Log"
_RUN_HISTORY    = "Run History"
_ISSUES_SUMMARY = "Issues Summary"

# ── Headers ───────────────────────────────────────────────────────────────────

_LOG_HEADER = [
    "Run ID", "Timestamp (UTC)", "URL", "HTTP Status", "SEO Score",
    "Page Title", "Meta Issues", "Meta Detail",
    "Keyword Issues", "Top Keywords (density)",
    "Flesch Score", "Readability Grade", "Gunning Fog",
    "Broken Links", "AI Suggestions",
]

_HISTORY_HEADER = [
    "Run ID", "Timestamp (UTC)", "Target Domain",
    "Pages Audited", "Avg SEO Score", "Critical Pages (<50)",
    "Total Meta Issues", "Total Broken Links", "Status",
]

_DASH_HEADER = [
    "URL", "Page Title",
    "Latest Score", "Trend",
    "Run 1", "Run 2", "Run 3", "Run 4", "Run 5",
    "Meta Issues", "Broken Links", "Readability",
    "Top Fix", "Last Audited",
]

_ISSUES_HEADER = [
    "Issue Type", "Affected Pages", "% of Audited Pages",
    "Severity", "Recommended Action",
]

# ── Colour palette — clean, light, professional (production dashboard style) ──

def _rgb(r, g, b):
    return {"red": r / 255, "green": g / 255, "blue": b / 255}


# Core neutrals
_WHITE       = _rgb(255, 255, 255)
_PAGE_BG     = _rgb(255, 255, 255)   # main canvas — white
_PANEL_BG    = _rgb(247, 248, 250)   # very light gray panel
_ALT_BG      = _rgb(250, 250, 252)   # zebra stripe (almost white)
_NORM_BG     = _rgb(255, 255, 255)   # zebra stripe (white)
_CARD_BG     = _rgb(255, 255, 255)   # KPI card background
_BORDER_C    = _rgb(225, 228, 235)   # light gray border

# Text
_TEXT_MAIN   = _rgb(30, 41, 59)      # slate-800 — primary text
_TEXT_MUTED  = _rgb(100, 116, 139)   # slate-500 — secondary text
_HEADER_BG   = _rgb(241, 245, 249)   # slate-100 — table header background
_HEADER_FG   = _rgb(51, 65, 85)      # slate-700 — table header text

# Status colors — soft pastel backgrounds, strong readable text
_GREEN_BG    = _rgb(220, 252, 231)   # green-100
_GREEN_FG    = _rgb(22, 101, 52)     # green-800
_YELLOW_BG   = _rgb(254, 249, 195)   # yellow-100
_YELLOW_FG   = _rgb(133, 100, 4)     # yellow-800
_RED_BG      = _rgb(254, 226, 226)   # red-100
_RED_FG      = _rgb(153, 27, 27)     # red-800
_BLUE_BG     = _rgb(219, 234, 254)   # blue-100
_BLUE_FG     = _rgb(30, 64, 175)     # blue-800
_ORANGE_BG   = _rgb(255, 237, 213)   # orange-100
_ORANGE_FG   = _rgb(154, 52, 18)     # orange-800
_PURPLE_BG   = _rgb(237, 233, 254)   # purple-100
_PURPLE_FG   = _rgb(91, 33, 182)     # purple-800

# Accent
_ACCENT      = _rgb(37, 99, 235)     # blue-600 — primary accent


def _score_colors(score: int):
    if score >= 75:
        return _GREEN_BG, _GREEN_FG
    if score >= 50:
        return _YELLOW_BG, _YELLOW_FG
    return _RED_BG, _RED_FG


def _severity_colors(severity: str):
    s = severity.upper()
    if s == "CRITICAL": return _RED_BG,    _RED_FG
    if s == "HIGH":     return _ORANGE_BG, _ORANGE_FG
    if s == "MEDIUM":   return _YELLOW_BG, _YELLOW_FG
    return _rgb(241, 245, 249), _TEXT_MUTED


# ── batchUpdate helpers ───────────────────────────────────────────────────────

def _range_fmt(sid, r1, c1, r2, c2, fmt):
    return {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "cell": {"userEnteredFormat": fmt},
        "fields": "userEnteredFormat",
    }}


def _cell_fmt(sid, row, col, fmt):
    return _range_fmt(sid, row, col, row + 1, col + 1, fmt)


def _freeze(sid, rows=1, cols=0):
    return {"updateSheetProperties": {
        "properties": {"sheetId": sid,
                       "gridProperties": {"frozenRowCount": rows, "frozenColumnCount": cols}},
        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
    }}


def _col_w(sid, col, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS",
                  "startIndex": col, "endIndex": col + 1},
        "properties": {"pixelSize": px},
        "fields": "pixelSize",
    }}


def _row_h(sid, row, px):
    return {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS",
                  "startIndex": row, "endIndex": row + 1},
        "properties": {"pixelSize": px},
        "fields": "pixelSize",
    }}


def _merge(sid, r1, c1, r2, c2):
    return {"mergeCells": {
        "range": {"sheetId": sid, "startRowIndex": r1, "endRowIndex": r2,
                  "startColumnIndex": c1, "endColumnIndex": c2},
        "mergeType": "MERGE_ALL",
    }}


def _border(color=None):
    c = color or _BORDER_C
    side = {"style": "SOLID", "color": c}
    return {"top": side, "bottom": side, "left": side, "right": side}


def _header_fmt():
    return {
        "backgroundColor": _HEADER_BG,
        "textFormat": {"bold": True, "foregroundColor": _HEADER_FG, "fontSize": 10, "fontFamily": "Arial"},
        "verticalAlignment": "MIDDLE",
        "horizontalAlignment": "CENTER",
        "padding": {"top": 8, "bottom": 8, "left": 8, "right": 8},
        "borders": _border(_BORDER_C),
    }


def _score_fmt(bg, fg):
    return {
        "backgroundColor": bg,
        "textFormat": {"bold": True, "foregroundColor": fg, "fontSize": 11, "fontFamily": "Arial"},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    }


# ── Sheet helpers ─────────────────────────────────────────────────────────────

def _get_or_create(spreadsheet, title, rows=5000, cols=20):
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def _sid(ws):
    return ws._properties["sheetId"]


# ── Issues Summary tab ────────────────────────────────────────────────────────

_ISSUE_DEFINITIONS = [
    ("missing_title",        "Missing <title> Tag",            "CRITICAL", "Add a unique <title> to every page (30–65 chars)"),
    ("title_too_short",      "Title Too Short (<30 chars)",    "HIGH",     "Expand title to include primary keyword (30–65 chars)"),
    ("title_too_long",       "Title Too Long (>65 chars)",     "HIGH",     "Trim title to under 65 characters"),
    ("missing_meta_desc",    "Missing Meta Description",       "CRITICAL", "Write a 150–160 char meta description per page"),
    ("duplicate_meta_desc",  "Duplicate Meta Description",     "HIGH",     "Make each page's meta description unique"),
    ("missing_canonical",    "Missing Canonical Tag",          "HIGH",     "Add <link rel='canonical' href='...'> to every page"),
    ("malformed_canonical",  "Malformed Canonical Tag",        "MEDIUM",   "Ensure canonical href is an absolute URL"),
    ("missing_og_title",     "Missing og:title",               "MEDIUM",   "Add Open Graph title for social sharing"),
    ("missing_og_desc",      "Missing og:description",         "MEDIUM",   "Add Open Graph description for social sharing"),
    ("missing_og_image",     "Missing og:image",               "MEDIUM",   "Add a 1200×630px og:image for link previews"),
]


def _write_issues_summary(ws, spreadsheet, results):
    sid = _sid(ws)
    ws.clear()
    total = len(results)

    # Title row
    ws.update(range_name="A1", values=[["🔎  Issues Summary — Ranked by Frequency"]], value_input_option="RAW")
    ws.update(range_name="A2", values=[[f"Based on audit of {total} page(s). Issues sorted by most affected pages."]], value_input_option="RAW")
    # Spacer row 3
    # Header row 4
    ws.update(range_name="A4", values=[_ISSUES_HEADER], value_input_option="RAW")

    # Count each issue type across all results
    rows = []
    for attr, label, severity, action in _ISSUE_DEFINITIONS:
        count = sum(1 for r in results if getattr(r.meta, attr, False))
        if count == 0:
            continue
        pct = f"{round(count / total * 100)}%" if total else "0%"
        rows.append([label, count, pct, severity, action])

    # Also add keyword/readability/broken-link aggregate issues
    overstuffed_pages = sum(1 for r in results if r.keywords.overstuffed)
    underopt_pages    = sum(1 for r in results if r.keywords.underoptimised)
    low_read_pages    = sum(1 for r in results if r.readability.below_target)
    broken_pages      = sum(1 for r in results if r.broken_links)

    for count, label, severity, action in [
        (overstuffed_pages, "Keyword Overstuffing (>4% density)", "HIGH",   "Reduce keyword frequency; aim for 1–2% natural density"),
        (underopt_pages,    "Thin / Keyword-Poor Content",        "HIGH",   "Add more relevant content (min 300 words recommended)"),
        (low_read_pages,    "Low Readability (Flesch <50)",       "MEDIUM", "Simplify sentences; target 8th-grade reading level"),
        (broken_pages,      "Pages with Broken Links",           "HIGH",   "Fix or remove all broken internal/external links"),
    ]:
        if count > 0:
            pct = f"{round(count / total * 100)}%" if total else "0%"
            rows.append([label, count, pct, severity, action])

    # Sort by affected page count descending
    rows.sort(key=lambda x: -x[1])

    if rows:
        ws.update(range_name="A5", values=rows, value_input_option="RAW")

    # ── Formatting ────────────────────────────────────────────────────────────
    NCOLS = 5
    reqs = []

    # Title
    reqs.append(_merge(sid, 0, 0, 1, NCOLS))
    reqs.append(_range_fmt(sid, 0, 0, 1, NCOLS, {
        "backgroundColor": _ACCENT,
        "textFormat": {"bold": True, "foregroundColor": _WHITE, "fontSize": 14, "fontFamily": "Arial"},
        "verticalAlignment": "MIDDLE",
        "padding": {"top": 10, "bottom": 10, "left": 12},
    }))
    reqs.append(_row_h(sid, 0, 48))

    # Subtitle
    reqs.append(_merge(sid, 1, 0, 2, NCOLS))
    reqs.append(_range_fmt(sid, 1, 0, 2, NCOLS, {
        "backgroundColor": _PANEL_BG,
        "textFormat": {"foregroundColor": _TEXT_MUTED, "fontSize": 10, "italic": True, "fontFamily": "Arial"},
        "verticalAlignment": "MIDDLE",
        "padding": {"left": 12},
    }))
    reqs.append(_row_h(sid, 1, 26))

    # Spacer
    reqs.append(_range_fmt(sid, 2, 0, 3, NCOLS, {"backgroundColor": _WHITE}))
    reqs.append(_row_h(sid, 2, 8))

    # Header row (row index 3)
    reqs.append(_range_fmt(sid, 3, 0, 4, NCOLS, _header_fmt()))
    reqs.append(_row_h(sid, 3, 34))

    # Data rows
    for i, row in enumerate(rows):
        ri = 4 + i
        severity = row[3] if len(row) > 3 else "LOW"
        sev_bg, sev_fg = _severity_colors(severity)
        row_bg = _ALT_BG if i % 2 == 0 else _NORM_BG

        reqs.append(_range_fmt(sid, ri, 0, ri + 1, NCOLS, {
            "backgroundColor": row_bg,
            "textFormat": {"foregroundColor": _TEXT_MAIN, "fontSize": 10, "fontFamily": "Arial"},
            "verticalAlignment": "MIDDLE",
            "padding": {"left": 8, "right": 8},
            "borders": {"bottom": {"style": "SOLID", "color": _BORDER_C}},
        }))
        reqs.append(_row_h(sid, ri, 30))
        # Affected pages col (col 1) — colour by count
        reqs.append(_cell_fmt(sid, ri, 1, {
            "backgroundColor": row_bg,
            "textFormat": {"bold": True, "foregroundColor": _ACCENT, "fontSize": 11, "fontFamily": "Arial"},
            "horizontalAlignment": "CENTER",
        }))
        # Severity column (col 3)
        reqs.append(_cell_fmt(sid, ri, 3, {
            "backgroundColor": sev_bg,
            "textFormat": {"bold": True, "foregroundColor": sev_fg, "fontSize": 10, "fontFamily": "Arial"},
            "horizontalAlignment": "CENTER",
        }))

    # Column widths
    reqs += [
        _col_w(sid, 0, 260),  # Issue Type
        _col_w(sid, 1, 120),  # Affected Pages
        _col_w(sid, 2, 110),  # % of Pages
        _col_w(sid, 3, 100),  # Severity
        _col_w(sid, 4, 340),  # Recommended Action
    ]
    reqs.append(_freeze(sid, rows=4, cols=0))

    spreadsheet.batch_update({"requests": reqs})


# ── Charts ────────────────────────────────────────────────────────────────────

def _add_charts(spreadsheet, dash_ws, hist_ws, results):
    """
    Adds two embedded charts to the Dashboard sheet:
      Chart 1 (top-right): Donut chart — Score Distribution (Critical/Needs Fix/Healthy)
      Chart 2 (below KPIs): Bar chart  — Top 10 pages by SEO score
    Adds one chart to Run History:
      Chart 3: Line chart  — Average SEO Score over time
    """
    dash_sid = _sid(dash_ws)
    hist_sid = _sid(hist_ws)

    total   = len(results)
    healthy = sum(1 for r in results if r.score >= 75)
    fix     = sum(1 for r in results if 50 <= r.score < 75)
    critical= sum(1 for r in results if r.score < 50)

    requests = []

    # ── Remove existing charts on Dashboard & Run History so re-runs don't stack duplicates ──
    try:
        meta = spreadsheet.fetch_sheet_metadata()
        for sheet in meta.get("sheets", []):
            sid_ = sheet["properties"]["sheetId"]
            if sid_ in (dash_sid, hist_sid):
                for chart in sheet.get("charts", []):
                    requests.append({"deleteEmbeddedObject": {"objectId": chart["chartId"]}})
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not enumerate existing charts (non-fatal): {e}")

    # ── Chart 1: Score Distribution Donut (Dashboard, anchored top-right) ───
    requests.append({"addChart": {"chart": {
        "spec": {
            "title": "Score Distribution",
            "titleTextFormat": {"bold": True, "foregroundColor": _TEXT_MAIN, "fontSize": 12, "fontFamily": "Arial"},
            "backgroundColor": _WHITE,
            "pieChart": {
                "legendPosition": "BOTTOM_LEGEND",
                "pieHole": 0.45,
                "domain": {"sourceRange": {"sources": [{
                    "sheetId": dash_sid,
                    "startRowIndex": 4, "endRowIndex": 5,
                    "startColumnIndex": 2, "endColumnIndex": 8,
                }]}},
                "series": {"sourceRange": {"sources": [{
                    "sheetId": dash_sid,
                    "startRowIndex": 5, "endRowIndex": 6,
                    "startColumnIndex": 2, "endColumnIndex": 8,
                }]}},
            },
        },
        "position": {
            "overlayPosition": {
                "anchorCell": {
                    "sheetId": dash_sid,
                    "rowIndex": 0, "columnIndex": 9,
                },
                "offsetXPixels": 0,
                "offsetYPixels": 0,
                "widthPixels": 380,
                "heightPixels": 230,
            }
        },
    }}})

    # ── Chart 2: Horizontal Bar — Top pages by score (Dashboard) ────────────
    # Data rows start at index _SUMMARY_ROWS + 1 (row after table header)
    data_start_idx = _SUMMARY_ROWS + 1
    data_end_idx = data_start_idx + max(len(results), 1)
    requests.append({"addChart": {"chart": {
        "spec": {
            "title": "Page SEO Scores",
            "titleTextFormat": {"bold": True, "foregroundColor": _TEXT_MAIN, "fontSize": 12, "fontFamily": "Arial"},
            "backgroundColor": _WHITE,
            "basicChart": {
                "chartType": "BAR",
                "legendPosition": "NO_LEGEND",
                "axis": [
                    {"position": "BOTTOM_AXIS", "title": "SEO Score (0–100)",
                     "titleTextPosition": {"horizontalAlignment": "CENTER"},
                     "format": {"foregroundColor": _TEXT_MUTED},
                     "viewWindowOptions": {"viewWindowMin": 0, "viewWindowMax": 100}},
                    {"position": "LEFT_AXIS",
                     "format": {"foregroundColor": _TEXT_MUTED}},
                ],
                "domains": [{"domain": {"sourceRange": {"sources": [{
                    "sheetId": dash_sid,
                    "startRowIndex": data_start_idx, "endRowIndex": data_end_idx,
                    "startColumnIndex": 0, "endColumnIndex": 1,
                }]}}}],
                "series": [{"series": {"sourceRange": {"sources": [{
                    "sheetId": dash_sid,
                    "startRowIndex": data_start_idx, "endRowIndex": data_end_idx,
                    "startColumnIndex": 2, "endColumnIndex": 3,
                }]}}, "targetAxis": "BOTTOM_AXIS", "color": _GREEN_FG}],
            },
        },
        "position": {
            "overlayPosition": {
                "anchorCell": {
                    "sheetId": dash_sid,
                    "rowIndex": 12, "columnIndex": 9,
                },
                "widthPixels": 380,
                "heightPixels": 280,
            }
        },
    }}})

    # ── Chart 3: Line — Avg Score over runs (Run History sheet) ─────────────
    hist_vals = hist_ws.get_all_values()
    # Data rows only (exclude header row at index 0); need at least 1 data row.
    n_data_rows = max(len(hist_vals) - 1, 1)
    end_row = 1 + n_data_rows  # exclusive end index, skipping header

    requests.append({"addChart": {"chart": {
        "spec": {
            "title": "Average SEO Score — Run History",
            "titleTextFormat": {"bold": True, "foregroundColor": _TEXT_MAIN, "fontSize": 12, "fontFamily": "Arial"},
            "backgroundColor": _WHITE,
            "basicChart": {
                "chartType": "LINE",
                "legendPosition": "BOTTOM_LEGEND",
                "axis": [
                    {"position": "BOTTOM_AXIS", "title": "Run",
                     "format": {"foregroundColor": _TEXT_MUTED}},
                    {"position": "LEFT_AXIS",   "title": "Avg Score",
                     "format": {"foregroundColor": _TEXT_MUTED},
                     "viewWindowOptions": {"viewWindowMin": 0, "viewWindowMax": 100}},
                ],
                "domains": [{"domain": {"sourceRange": {"sources": [{
                    "sheetId": hist_sid,
                    "startRowIndex": 1, "endRowIndex": end_row,
                    "startColumnIndex": 0, "endColumnIndex": 1,
                }]}}}],
                "series": [{"series": {"sourceRange": {"sources": [{
                    "sheetId": hist_sid,
                    "startRowIndex": 1, "endRowIndex": end_row,
                    "startColumnIndex": 4, "endColumnIndex": 5,
                }]}}, "targetAxis": "LEFT_AXIS", "color": _BLUE_FG}],
                "interpolateNulls": True,
                "lineSmoothing": True,
                "headerCount": 0,
            },
        },
        "position": {
            "overlayPosition": {
                "anchorCell": {
                    "sheetId": hist_sid,
                    "rowIndex": 1, "columnIndex": 10,
                },
                "widthPixels": 480,
                "heightPixels": 280,
            }
        },
    }}})

    delete_reqs = [r for r in requests if "deleteEmbeddedObject" in r]
    add_reqs    = [r for r in requests if "addChart" in r]

    try:
        if delete_reqs:
            spreadsheet.batch_update({"requests": delete_reqs})
        spreadsheet.batch_update({"requests": add_reqs})
    except Exception as e:
        # Charts are non-critical — log and continue
        import logging
        logging.getLogger(__name__).warning(f"Chart creation failed (non-fatal): {e}")


# ── Audit Log ─────────────────────────────────────────────────────────────────

def _init_log(spreadsheet, ws):
    existing = ws.get_all_values()
    if not existing or existing[0] != _LOG_HEADER:
        ws.insert_row(_LOG_HEADER, index=1, value_input_option="RAW")
    sid = _sid(ws)
    spreadsheet.batch_update({"requests": [
        _range_fmt(sid, 0, 0, 1, len(_LOG_HEADER), _header_fmt()),
        _freeze(sid, rows=1),
        _col_w(sid, 0, 95),  _col_w(sid, 1, 165), _col_w(sid, 2, 285),
        _col_w(sid, 3, 80),  _col_w(sid, 4, 85),  _col_w(sid, 5, 200),
        _col_w(sid, 6, 80),  _col_w(sid, 7, 210), _col_w(sid, 8, 145),
        _col_w(sid, 9, 200), _col_w(sid, 10, 90), _col_w(sid, 11, 115),
        _col_w(sid, 12, 90), _col_w(sid, 13, 90), _col_w(sid, 14, 450),
    ]})


def _write_log(ws, spreadsheet, run_id, ts, results):
    sid = _sid(ws)
    rows = []
    for r in sorted(results, key=lambda x: x.score):
        top_kw = ", ".join(f"{w} ({d:.1%})" for w, d in r.keywords.top_keywords[:5])
        # Format suggestions as numbered list instead of pipe-separated
        sugg = "\n".join(f"{i+1}. {s}" for i, s in enumerate(r.suggestions[:4]))
        rows.append([
            run_id, ts, r.url, r.status_code, r.score,
            r.title, r.meta.count(), r.meta.to_str(),
            r.keywords.to_str(), top_kw,
            round(r.readability.flesch_score, 1),
            r.readability.grade_label or "n/a",
            round(r.readability.gunning_fog, 1),
            len(r.broken_links), sugg,
        ])
    ws.append_rows(rows, value_input_option="RAW")

    all_vals = ws.get_all_values()
    start = len(all_vals) - len(rows)
    reqs = []
    for i, r in enumerate(sorted(results, key=lambda x: x.score)):
        bg, fg = _score_colors(r.score)
        row_bg = _ALT_BG if i % 2 == 0 else _NORM_BG
        reqs.append(_range_fmt(sid, start + i, 0, start + i + 1, len(_LOG_HEADER), {
            "backgroundColor": row_bg,
            "textFormat": {"foregroundColor": _TEXT_MAIN, "fontSize": 10, "fontFamily": "Arial"},
            "verticalAlignment": "TOP",
            "padding": {"left": 6, "right": 6},
            "borders": {"bottom": {"style": "SOLID", "color": _BORDER_C}},
        }))
        reqs.append(_cell_fmt(sid, start + i, 4, _score_fmt(bg, fg)))
        # Wrap suggestions column
        reqs.append(_cell_fmt(sid, start + i, 14, {
            "backgroundColor": row_bg,
            "textFormat": {"foregroundColor": _rgb(51, 65, 85), "fontSize": 9, "fontFamily": "Arial"},
            "wrapStrategy": "WRAP",
            "verticalAlignment": "TOP",
        }))
        # Auto-grow row height so wrapped suggestions don't overflow into adjacent cells
        n_lines = len(r.suggestions[:4]) or 1
        reqs.append(_row_h(sid, start + i, max(60, 20 * n_lines + 10)))
    spreadsheet.batch_update({"requests": reqs})


# ── Run History ───────────────────────────────────────────────────────────────

def _init_history(spreadsheet, ws):
    existing = ws.get_all_values()
    if not existing or existing[0] != _HISTORY_HEADER:
        ws.insert_row(_HISTORY_HEADER, index=1, value_input_option="RAW")
    sid = _sid(ws)
    spreadsheet.batch_update({"requests": [
        _range_fmt(sid, 0, 0, 1, len(_HISTORY_HEADER), _header_fmt()),
        _freeze(sid, rows=1),
        _col_w(sid, 0, 110), _col_w(sid, 1, 165), _col_w(sid, 2, 260),
        _col_w(sid, 3, 105), _col_w(sid, 4, 115), _col_w(sid, 5, 125),
        _col_w(sid, 6, 135), _col_w(sid, 7, 135), _col_w(sid, 8, 110),
    ]})


def _write_history(ws, spreadsheet, run_id, ts, domain, results):
    sid = _sid(ws)
    avg      = round(sum(r.score for r in results) / len(results), 1) if results else 0
    critical = sum(1 for r in results if r.score < 50)
    t_meta   = sum(r.meta.count() for r in results)
    t_broken = sum(len(r.broken_links) for r in results)
    ws.append_row([run_id, ts, domain, len(results), avg,
                   critical, t_meta, t_broken, "✓ Complete"],
                  value_input_option="RAW")

    all_vals = ws.get_all_values()
    new_i = len(all_vals) - 1
    bg, fg = _score_colors(int(avg))
    spreadsheet.batch_update({"requests": [
        _range_fmt(sid, new_i, 0, new_i + 1, len(_HISTORY_HEADER), {
            "backgroundColor": _ALT_BG if new_i % 2 == 0 else _NORM_BG,
            "textFormat": {"foregroundColor": _TEXT_MAIN, "fontSize": 10, "fontFamily": "Arial"},
            "verticalAlignment": "MIDDLE",
            "padding": {"left": 6},
            "borders": {"bottom": {"style": "SOLID", "color": _BORDER_C}},
        }),
        _row_h(sid, new_i, 32),
        _cell_fmt(sid, new_i, 4, _score_fmt(bg, fg)),
        _cell_fmt(sid, new_i, 8, {
            "backgroundColor": _GREEN_BG,
            "textFormat": {"bold": True, "foregroundColor": _GREEN_FG, "fontFamily": "Arial"},
            "horizontalAlignment": "CENTER",
        }),
    ]})


# ── Dashboard ─────────────────────────────────────────────────────────────────

_SUMMARY_ROWS   = 11
_DATA_START_ROW = _SUMMARY_ROWS + 1


def _trend_label(scores):
    valid = [s for s in scores if s != ""]
    if len(valid) < 2:
        return "—"
    delta = valid[-1] - valid[0]
    color = "22c55e" if delta > 0 else ("ef4444" if delta < 0 else "60a5fa")
    vals = ",".join(str(s) for s in valid)
    return f'=SPARKLINE({{{vals}}},{{"charttype","line";"color","#{color}";"linewidth",2}})'


def _init_dashboard(spreadsheet, ws):
    sid = _sid(ws)
    spreadsheet.batch_update({"requests": [
        _freeze(sid, rows=_SUMMARY_ROWS + 1, cols=0),
        _col_w(sid, 0, 285), _col_w(sid, 1, 185),
        _col_w(sid, 2, 105), _col_w(sid, 3, 130),   # Trend — wider for sparkline
        _col_w(sid, 4, 65),  _col_w(sid, 5, 65),
        _col_w(sid, 6, 65),  _col_w(sid, 7, 65),
        _col_w(sid, 8, 65),
        _col_w(sid, 9, 120), _col_w(sid, 10, 115),
        _col_w(sid, 11, 120), _col_w(sid, 12, 280),  # Top Fix
        _col_w(sid, 13, 155),                         # Last Audited
    ]})


def _write_summary_panel(ws, spreadsheet, ts, results):
    """
    Redesigned dashboard layout:

    ROW 0  ── Full-width dark header bar with title + timestamp
    ROW 1  ── Thin accent divider line (indigo)
    ROW 2  ── Spacer
    ROW 3  ── KPI SECTION LABEL
    ROW 4  ── KPI LABELS  (7 cards across cols 0-12)
    ROW 5  ── KPI VALUES  (large bold numbers, color-coded cards)
    ROW 6  ── KPI SUBLABELS (% breakdowns, tiny text under numbers)
    ROW 7  ── Spacer
    ROW 8  ── HEALTH BAR label row
    ROW 9  ── HEALTH BAR (segmented progress bar, 3-color)
    ROW 10 ── Spacer
    ROW 11 ── TABLE HEADER
    """
    sid = _sid(ws)
    total     = len(results)
    healthy   = sum(1 for r in results if r.score >= 75)
    needs_fix = sum(1 for r in results if 50 <= r.score < 75)
    critical  = sum(1 for r in results if r.score < 50)
    avg_score = round(sum(r.score for r in results) / total, 1) if total else 0
    t_meta    = sum(r.meta.count() for r in results)
    t_broken  = sum(len(r.broken_links) for r in results)
    t_kw      = sum(len(r.keywords.overstuffed) + (1 if r.keywords.underoptimised else 0) for r in results)

    NCOLS = 14
    pct_h = f"{round(healthy   / total * 100)}%" if total else "0%"
    pct_f = f"{round(needs_fix / total * 100)}%" if total else "0%"
    pct_c = f"{round(critical  / total * 100)}%" if total else "0%"

    # ── Clean light palette for the dashboard ────────────────────────────────
    _TITLE_BG   = _WHITE                  # white header bar
    _CARD_ALT   = _rgb(248, 250, 252)     # very light slate — alt card bg
    _LABEL_FG   = _TEXT_MUTED             # slate-500
    _DIVIDER    = _BORDER_C               # light border

    # ── Write cell values ────────────────────────────────────────────────────
    ws.update("A1", [["  SEO Audit Intelligence Dashboard"]], value_input_option="RAW")
    ws.update("A2", [[""]], value_input_option="RAW")   # accent bar (colored via fmt)
    ws.update("A3", [[""]], value_input_option="RAW")   # spacer
    ws.update("A4", [["  KEY PERFORMANCE INDICATORS"]], value_input_option="RAW")

    # KPI labels row
    kpi_labels = [
        "PAGES AUDITED", "", "HEALTHY", "", "NEEDS FIX", "",
        "CRITICAL", "", "AVG SCORE", "", "META ISSUES", "", "KW FLAGS", "BROKEN LINKS"
    ]
    ws.update("A5:N5", [kpi_labels], value_input_option="RAW")

    # KPI values row
    kpi_values = [
        total, "", healthy, "", needs_fix, "",
        critical, "", avg_score, "", t_meta, "", t_kw, t_broken
    ]
    ws.update("A6:N6", [kpi_values], value_input_option="RAW")

    # KPI sublabels row (context under the numbers)
    kpi_sub = [
        "total crawled", "", pct_h + " of total", "", pct_f + " of total", "",
        pct_c + " of total", "", "out of 100", "", "across all pages", "", "density flags", "dead links"
    ]
    ws.update("A7:N7", [kpi_sub], value_input_option="RAW")

    ws.update("A8", [[""]], value_input_option="RAW")   # spacer
    ws.update("A9", [["  SITE HEALTH BREAKDOWN"]], value_input_option="RAW")
    ws.update("A10:N10", [[""] * NCOLS], value_input_option="RAW")  # progress bar
    ws.update("A11", [[""]], value_input_option="RAW")  # spacer

    # ── Format requests ──────────────────────────────────────────────────────
    reqs = []

    # ROW 0: Title bar — full width, white, large bold, with accent border below
    reqs += [
        _merge(sid, 0, 0, 1, NCOLS),
        _range_fmt(sid, 0, 0, 1, NCOLS, {
            "backgroundColor": _TITLE_BG,
            "textFormat": {
                "bold": True,
                "foregroundColor": _TEXT_MAIN,
                "fontSize": 18,
                "fontFamily": "Arial",
            },
            "verticalAlignment": "MIDDLE",
            "padding": {"top": 0, "bottom": 0, "left": 16},
        }),
        _row_h(sid, 0, 58),
    ]

    # ROW 1: Thin accent divider line
    reqs += [
        _merge(sid, 1, 0, 2, NCOLS),
        _range_fmt(sid, 1, 0, 2, NCOLS, {"backgroundColor": _ACCENT}),
        _row_h(sid, 1, 4),
    ]

    # ROW 2: Spacer
    reqs += [
        _range_fmt(sid, 2, 0, 3, NCOLS, {"backgroundColor": _WHITE}),
        _row_h(sid, 2, 10),
    ]

    # ROW 3: "KEY PERFORMANCE INDICATORS" section label
    reqs += [
        _merge(sid, 3, 0, 4, NCOLS),
        _range_fmt(sid, 3, 0, 4, NCOLS, {
            "backgroundColor": _WHITE,
            "textFormat": {
                "bold": True,
                "foregroundColor": _ACCENT,
                "fontSize": 9,
                "fontFamily": "Arial",
            },
            "verticalAlignment": "MIDDLE",
            "padding": {"left": 14},
        }),
        _row_h(sid, 3, 22),
    ]

    # ROW 4: KPI label cards
    # ROW 5: KPI value cards
    # ROW 6: KPI sublabel cards
    kpi_card_configs = [
        # (col_start, col_end, label_fg, value_bg, value_fg)
        (0,  2,  _BLUE_FG,   _BLUE_BG,   _BLUE_FG),     # Pages — blue
        (2,  4,  _GREEN_FG,  _GREEN_BG,  _GREEN_FG),    # Healthy — green
        (4,  6,  _YELLOW_FG, _YELLOW_BG, _YELLOW_FG),   # Needs Fix — yellow
        (6,  8,  _RED_FG,    _RED_BG,    _RED_FG),      # Critical — red
        (8,  10, _PURPLE_FG, _PURPLE_BG, _PURPLE_FG),   # Avg Score — purple
        (10, 12, _ORANGE_FG, _ORANGE_BG, _ORANGE_FG),   # Meta — orange
        (12, 13, _rgb(15, 118, 110), _rgb(204, 251, 241), _rgb(15, 118, 110)),   # KW — teal
        (13, 14, _PURPLE_FG, _PURPLE_BG, _PURPLE_FG),   # Broken — violet
    ]

    for c1, c2, lbl_fg, val_bg, val_fg in kpi_card_configs:
        # Label row (row 4)
        reqs += [
            _merge(sid, 4, c1, 5, c2),
            _range_fmt(sid, 4, c1, 5, c2, {
                "backgroundColor": _CARD_BG,
                "textFormat": {"bold": True, "foregroundColor": lbl_fg, "fontSize": 7, "fontFamily": "Arial"},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "BOTTOM",
                "padding": {"bottom": 4},
                "borders": {"top": {"style": "SOLID", "color": _DIVIDER},
                            "left": {"style": "SOLID", "color": _DIVIDER},
                            "right": {"style": "SOLID", "color": _DIVIDER}},
            }),
        ]
        # Value row (row 5)
        reqs += [
            _merge(sid, 5, c1, 6, c2),
            _range_fmt(sid, 5, c1, 6, c2, {
                "backgroundColor": val_bg,
                "textFormat": {"bold": True, "foregroundColor": val_fg, "fontSize": 26, "fontFamily": "Arial"},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "borders": {"left": {"style": "SOLID", "color": _DIVIDER},
                            "right": {"style": "SOLID", "color": _DIVIDER}},
            }),
        ]
        # Sublabel row (row 6)
        reqs += [
            _merge(sid, 6, c1, 7, c2),
            _range_fmt(sid, 6, c1, 7, c2, {
                "backgroundColor": _CARD_BG,
                "textFormat": {"foregroundColor": _LABEL_FG, "fontSize": 7, "italic": True, "fontFamily": "Arial"},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "TOP",
                "padding": {"top": 4},
                "borders": {"bottom": {"style": "SOLID", "color": _DIVIDER},
                            "left": {"style": "SOLID", "color": _DIVIDER},
                            "right": {"style": "SOLID", "color": _DIVIDER}},
            }),
        ]

    reqs += [_row_h(sid, 4, 22), _row_h(sid, 5, 52), _row_h(sid, 6, 20)]

    # ROW 7: Spacer
    reqs += [
        _range_fmt(sid, 7, 0, 8, NCOLS, {"backgroundColor": _WHITE}),
        _row_h(sid, 7, 12),
    ]

    # ROW 8: Health bar section label
    reqs += [
        _merge(sid, 8, 0, 9, NCOLS),
        _range_fmt(sid, 8, 0, 9, NCOLS, {
            "backgroundColor": _WHITE,
            "textFormat": {"bold": True, "foregroundColor": _ACCENT, "fontSize": 9, "fontFamily": "Arial"},
            "verticalAlignment": "MIDDLE",
            "padding": {"left": 14},
        }),
        _row_h(sid, 8, 22),
    ]

    # ROW 9: Segmented health progress bar
    h_cols = round((healthy   / total) * NCOLS) if total else 0
    f_cols = round((needs_fix / total) * NCOLS) if total else 0
    c_cols = NCOLS - h_cols - f_cols

    col = 0
    for count, bg, fg, label in [
        (h_cols, _GREEN_BG,  _GREEN_FG,  f"✅ {pct_h} Healthy"),
        (f_cols, _YELLOW_BG, _YELLOW_FG, f"⚠ {pct_f} Needs Fix"),
        (c_cols, _RED_BG,    _RED_FG,    f"🔴 {pct_c} Critical"),
    ]:
        if count > 0:
            reqs.append(_merge(sid, 9, col, 10, col + count))
            reqs.append(_range_fmt(sid, 9, col, 10, col + count, {
                "backgroundColor": bg,
                "textFormat": {"bold": True, "foregroundColor": fg, "fontSize": 8, "fontFamily": "Arial"},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
            }))
            # Write label into first cell of segment
            col += count
    reqs.append(_row_h(sid, 9, 24))

    # Write progress bar labels
    pb_row = [""] * NCOLS
    if h_cols > 0: pb_row[0]      = f"✅ {pct_h} Healthy"
    if f_cols > 0: pb_row[h_cols] = f"⚠ {pct_f} Needs Fix"
    if c_cols > 0: pb_row[h_cols + f_cols] = f"🔴 {pct_c} Critical"
    ws.update("A10:N10", [pb_row], value_input_option="RAW")

    # ROW 10: Spacer before table
    reqs += [
        _range_fmt(sid, 10, 0, 11, NCOLS, {"backgroundColor": _WHITE}),
        _row_h(sid, 10, 10),
    ]

    # ROW 11: Table column headers (styled)
    reqs += [
        _range_fmt(sid, 11, 0, 12, len(_DASH_HEADER), {
            "backgroundColor": _HEADER_BG,
            "textFormat": {
                "bold": True,
                "foregroundColor": _HEADER_FG,
                "fontSize": 9,
                "fontFamily": "Arial",
            },
            "verticalAlignment": "MIDDLE",
            "horizontalAlignment": "CENTER",
            "padding": {"top": 8, "bottom": 8, "left": 8, "right": 8},
            "borders": {
                "bottom": {"style": "SOLID", "color": _ACCENT},
                "top": {"style": "SOLID", "color": _DIVIDER},
            },
        }),
        _row_h(sid, 11, 34),
    ]

    spreadsheet.batch_update({"requests": reqs})


def _update_dashboard(ws, spreadsheet, ts, results):
    sid = _sid(ws)
    _write_summary_panel(ws, spreadsheet, ts, results)

    # Write header at row index _SUMMARY_ROWS
    ws.update(f"A{_SUMMARY_ROWS + 1}", [_DASH_HEADER], value_input_option="RAW")

    all_vals   = ws.get_all_values()
    existing   = all_vals[_SUMMARY_ROWS + 1:] if len(all_vals) > _SUMMARY_ROWS + 1 else []
    url_to_idx = {row[0]: i for i, row in enumerate(existing) if row and row[0]}
    result_map = {r.url: r for r in results}
    MAX_RUNS   = 5

    updated  = [row[:] for row in existing]
    new_rows = []

    for url, r in result_map.items():
        # Build top fix string — clean LLM suggestion
        top_fix = ""
        if r.suggestions:
            raw = r.suggestions[0]
            m = re.match(r"^\[(CRITICAL|HIGH|MEDIUM|LOW)\]\s*(.+)$", raw, re.IGNORECASE)
            top_fix = f"[{m.group(1).upper()}] {m.group(2)}" if m else raw

        if url in url_to_idx:
            idx = url_to_idx[url]
            row = updated[idx]
            while len(row) < len(_DASH_HEADER):
                row.append("")
            run_scores = []
            for ci in range(4, 9):
                try:
                    v = row[ci]
                    if v != "":
                        run_scores.append(int(v))
                except (ValueError, TypeError, IndexError):
                    pass
            run_scores.append(r.score)
            if len(run_scores) > MAX_RUNS:
                run_scores = run_scores[-MAX_RUNS:]
            padded = [""] * MAX_RUNS
            for i, s in enumerate(run_scores):
                padded[i] = s
            updated[idx] = [
                url, r.title, r.score, _trend_label(run_scores),
                *padded, r.meta.count(), len(r.broken_links),
                r.readability.grade_label or "n/a", top_fix, ts,
            ]
        else:
            padded = [r.score] + [""] * (MAX_RUNS - 1)
            new_rows.append([
                url, r.title, r.score, _trend_label([r.score]),
                *padded, r.meta.count(), len(r.broken_links),
                r.readability.grade_label or "n/a", top_fix, ts,
            ])

    data_start = f"A{_SUMMARY_ROWS + 2}"
    if updated:
        ws.update(data_start, updated, value_input_option="USER_ENTERED")
    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    # Re-apply row formatting
    all_vals = ws.get_all_values()
    reqs = []
    for row_i, row in enumerate(all_vals[_SUMMARY_ROWS + 1:], start=_SUMMARY_ROWS + 1):
        if not row or not row[0]:
            continue
        row_bg = _ALT_BG if row_i % 2 == 0 else _NORM_BG
        reqs.append(_range_fmt(sid, row_i, 0, row_i + 1, len(_DASH_HEADER), {
            "backgroundColor": row_bg,
            "textFormat": {"foregroundColor": _TEXT_MAIN, "fontSize": 10, "fontFamily": "Arial"},
            "verticalAlignment": "MIDDLE",
            "padding": {"left": 6, "right": 6},
            "borders": {"bottom": {"style": "SOLID", "color": _BORDER_C}},
        }))
        reqs.append(_row_h(sid, row_i, 38))
        # Latest score (col 2)
        try:
            score = int(row[2]) if len(row) > 2 and row[2] != "" else 0
            bg, fg = _score_colors(score)
            reqs.append(_cell_fmt(sid, row_i, 2, _score_fmt(bg, fg)))
        except (ValueError, TypeError):
            pass
        # Individual run scores (cols 4–8)
        for ci in range(4, 9):
            if ci < len(row) and row[ci] != "":
                try:
                    s = int(row[ci])
                    bg, fg = _score_colors(s)
                    reqs.append(_cell_fmt(sid, row_i, ci, {
                        "backgroundColor": bg,
                        "textFormat": {"bold": True, "foregroundColor": fg, "fontSize": 9, "fontFamily": "Arial"},
                        "horizontalAlignment": "CENTER",
                    }))
                except (ValueError, TypeError):
                    pass
        # Trend cell (col 3) — sparkline lives here, just style the bg
        reqs.append(_cell_fmt(sid, row_i, 3, {
            "backgroundColor": _WHITE,
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
        }))
        # Top Fix cell (col 12) — muted text, wrapped
        reqs.append(_cell_fmt(sid, row_i, 12, {
            "backgroundColor": row_bg,
            "textFormat": {"foregroundColor": _TEXT_MUTED, "fontSize": 9, "italic": True, "fontFamily": "Arial"},
            "wrapStrategy": "WRAP",
            "verticalAlignment": "MIDDLE",
        }))

    if reqs:
        spreadsheet.batch_update({"requests": reqs})


# ── Public entry point ────────────────────────────────────────────────────────

def write_results(sheet_id: str, results: list[PageResult]) -> None:
    """
    Write a full audit run to four Google Sheets worksheets:
      - Dashboard      : KPI panel + per-URL score table with 5-run trend
      - Audit Log      : append-only raw per-page data
      - Run History    : one summary row per run
      - Issues Summary : top issues ranked by frequency       ← new
    Plus embedded charts on Dashboard and Run History.        ← new
    """
    gc          = _client()
    spreadsheet = gc.open_by_key(sheet_id)

    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-") + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=4)
    )
    domain = urlparse(results[0].url).netloc if results else "unknown"

    # Audit Log
    log_ws = _get_or_create(spreadsheet, _AUDIT_LOG)
    _init_log(spreadsheet, log_ws)
    _write_log(log_ws, spreadsheet, run_id, ts, results)

    # Run History
    hist_ws = _get_or_create(spreadsheet, _RUN_HISTORY)
    _init_history(spreadsheet, hist_ws)
    _write_history(hist_ws, spreadsheet, run_id, ts, domain, results)

    # Dashboard
    dash_ws = _get_or_create(spreadsheet, _DASHBOARD)
    _init_dashboard(spreadsheet, dash_ws)
    _update_dashboard(dash_ws, spreadsheet, ts, results)

    # Issues Summary (new tab)
    issues_ws = _get_or_create(spreadsheet, _ISSUES_SUMMARY)
    _write_issues_summary(issues_ws, spreadsheet, results)

    # Charts (non-blocking — failure won't crash the audit)
    _add_charts(spreadsheet, dash_ws, hist_ws, results)