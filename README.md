# Skylark Drones — Monday.com Business Intelligence Agent

A conversational AI agent that answers founder-level business questions using live data from Monday.com. Built for the Skylark Drones technical assignment.

---

## Overview

The agent dynamically queries two Monday.com boards (Deals + Work Orders) via the GraphQL API, normalizes messy real-world data, performs deterministic Python analytics, and uses a free LLM (Gemini/Groq) to generate executive-level responses.

**Architecture principle:** The LLM never directly touches Monday.com. Python owns all data retrieval and calculation; the LLM only converts structured results into natural language.

---

## Architecture

```
Browser (HTML/CSS/JS)
       ↓ HTTPS
FastAPI Backend (Python)
       ├──→ Monday GraphQL API (read-only)
       │        ↓
       │    Deals + Work Orders
       │        ↓
       │    Normalizer (dates, sectors, statuses, currency)
       │        ↓
       │    Deterministic Analytics
       │        pipeline.py  → pipeline, weighted pipeline, sector breakdown
       │        revenue.py   → billed, collected, receivables, collection rate
       │        work_orders.py → status, execution, operations
       │        cross_board.py → pipeline vs execution, leadership update
       │
       └──→ LLM Provider
                ↓
            Gemini (primary) → Groq (fallback) → Deterministic (always available)
                ↓
            Executive-language response from structured analytics context
```

---

## Features

### Supported Queries (all validated against live Monday data)

| # | Query Type | Example |
|---|---|---|
| 1 | Total pipeline | "What is our total pipeline?" |
| 2 | Sector pipeline | "How is the energy sector pipeline looking?" |
| 3 | Quarter pipeline | "How is our energy pipeline this quarter?" |
| 4 | Biggest deals | "What are our biggest open deals?" |
| 5 | Billing | "How much have we billed?" |
| 6 | Collections | "How much have we collected?" |
| 7 | Receivables | "How much is outstanding?" |
| 8 | Work orders | "How are our work orders performing?" |
| 9 | Sector comparison | "Which sector has the strongest pipeline?" |
| 10 | Cross-board analysis | "Which sectors have strong pipeline but weak execution?" |
| 11 | Leadership update | "Prepare a leadership update for this quarter." |
| 12 | Ambiguous → clarification | "How is the business doing?" |
| 13 | Forecast reliability | "How reliable is our pipeline forecast?" |
| 14 | Data transparency | "What data did you use to answer this?" |

### Validated Analytics (30 Aug 2026, live data)

| Metric | Value |
|---|---|
| Total open pipeline | ₹221.05 Cr (179 deals) |
| Weighted pipeline* | ₹72.29 Cr |
| Won value | ₹9.50 Cr |
| Contract (WO) | ₹21.16 Cr |
| Billed value | ₹12.67 Cr |
| Collected | ₹9.04 Cr |
| Receivables | ₹3.63 Cr |
| Collection rate | 71.4% |
| Top pipeline sector | Powerline (₹80.59 Cr) |

*Weighted pipeline uses assumed probabilities: High 80%, Medium 50%, Low 20%, Unknown 30% — not from source data.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML/CSS/JavaScript (single-file, no build step) |
| Backend | Python 3.13 + FastAPI + uvicorn |
| Business Analytics | Deterministic Python (no LLM math) |
| Monday Integration | Monday.com GraphQL API v2 (read-only) |
| LLM Primary | Google Gemini 1.5 Flash (free tier) |
| LLM Fallback | Groq LLaMA 3.3 70B (free tier) |
| Final Fallback | Structured deterministic response (always available) |

---

## Monday.com Setup

Two boards were created by importing the provided Excel files:

| Board | ID | Records |
|---|---|---|
| Deals | `5030966894` | 344 usable records |
| Work Orders | `5030966898` | 176 usable records |

The Excel files are **not used at runtime**. All data is fetched live from Monday.com.

---

## Data Quality

The dataset contains intentional messiness. Key quality metrics:

| Field | Missing | Impact |
|---|---|---|
| Deal value | 52% (179/344) | Pipeline total is understated |
| Close date | 92% (318/344) | Quarter filtering has limited precision |
| Closure probability | 75% (258/344) | Weighted pipeline uses 30% default for most deals |
| Collected amount (WO) | 56% (98/176) | Collection rate may be understated |
| WO status | 42% (74/176) | Status breakdown is partial |

The agent surfaces material caveats when they affect the answer.

---

## Sector Normalisation

Raw sector values are mapped to canonical names:

| Raw | Canonical |
|---|---|
| MINING, mining sector | Mining |
| RENEWABLES, renewable | Renewables |
| POWERLINE, power line | Powerline |
| RAILWAYS, railway | Railways |
| DSP | DSP |
| energy | Renewables + Powerline (merged query) |

---

## LLM Provider Architecture

```
backend/agent/llm.py           ← provider router
backend/agent/providers/
    gemini.py                  ← Gemini 1.5 Flash
    groq.py                    ← Groq LLaMA 3.3 70B
```

The router tries Gemini first. On any failure (API error, quota, timeout), it tries Groq. If both fail, a deterministic Python response is returned. No single provider is required for the system to function.

---

## Environment Variables

```env
# Required
MONDAY_API_TOKEN=your_monday_api_token

# Board IDs (defaults shown — only override if using different boards)
DEALS_BOARD_ID=5030966894
WORK_ORDERS_BOARD_ID=5030966898

# LLM (at least one recommended; system works without via deterministic fallback)
GEMINI_API_KEY=          # https://aistudio.google.com/apikey (free)
GROQ_API_KEY=            # https://console.groq.com/keys (free)

# CORS
FRONTEND_URL=https://your-frontend.netlify.app
```

---

## Local Setup

```bash
# Clone/unzip and enter directory
cd skylar_drones

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start backend
py -3.13 -m uvicorn backend.main:app --reload --port 8000

# Open frontend
# Open frontend/index.html in browser
# (or use a local server: python -m http.server 3000 --directory frontend)
```

---

## API Endpoints

### `GET /health`
Returns service status. Never exposes secrets.
```json
{"status": "ok", "monday_configured": true, "timestamp": "..."}
```

### `POST /chat`
Main conversational endpoint.

**Request:**
```json
{
  "message": "How is our energy pipeline this quarter?",
  "history": []
}
```

**Response:**
```json
{
  "response": "### Energy Sector Pipeline...",
  "intent": "pipeline_analysis",
  "sector": "Renewables",
  "period": "current_quarter",
  "sources": ["Deals Board"],
  "filters": {"sector": "Renewables", "period": "current_quarter"},
  "data_quality": {"deals": {...}, "work_orders": {...}},
  "analytics_used": ["pipeline"],
  "timestamp": "..."
}
```

### `GET /`
API info. No secrets exposed.

---

## Deployment

### Backend — Render.com (free tier)

1. Push code to GitHub (ensure `.env` is in `.gitignore`)
2. Create account at [render.com](https://render.com)
3. New → Web Service → connect repo
4. Build: `pip install -r requirements.txt`
5. Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables in Render dashboard (never commit secrets)
7. The `render.yaml` in the project root can automate this

### Frontend — Netlify / GitHub Pages

1. Edit `frontend/index.html` line: `const API = '...'` → your Render URL
2. Deploy the `frontend/` folder to Netlify (drag-and-drop works)

---

## Analytical Assumptions

All assumptions are documented in `DECISION_LOG.md`.

| Assumption | Value | Documented |
|---|---|---|
| Closure probability: High | 80% | README + DECISION_LOG |
| Closure probability: Medium | 50% | README + DECISION_LOG |
| Closure probability: Low | 20% | README + DECISION_LOG |
| Unknown probability | 30% (conservative) | README + DECISION_LOG |
| Currency | INR (assumed) | README + DECISION_LOG |
| Quarter | Calendar quarter, dynamically calculated | README + DECISION_LOG |

---

## Project Structure

```
skylar_drones/
├── data/                        # Source Excel files (not used at runtime)
├── frontend/
│   └── index.html               # Single-page conversational UI
├── backend/
│   ├── main.py                  # FastAPI application
│   ├── config.py                # Environment variable loading
│   ├── monday/
│   │   ├── client.py            # GraphQL client (pagination, error handling)
│   │   └── boards.py            # Board data fetching
│   ├── data/
│   │   ├── normalizer.py        # Data cleaning and normalisation
│   │   └── quality.py           # Data quality tracking
│   ├── analytics/
│   │   ├── pipeline.py          # Pipeline metrics
│   │   ├── revenue.py           # Revenue / billing / collections
│   │   ├── work_orders.py       # Operations analytics
│   │   ├── cross_board.py       # Cross-board + leadership update
│   │   └── utils.py             # fmt_inr, current_quarter, safe_sum
│   └── agent/
│       ├── agent.py             # Main BI agent (intent → analytics → LLM)
│       ├── llm.py               # Provider router (Gemini → Groq → fallback)
│       ├── prompts.py           # System prompt + context builder
│       └── providers/
│           ├── gemini.py        # Google Gemini provider
│           └── groq.py          # Groq provider
├── validate.py                  # Full validation (all 14 query types)
├── test_api.py                  # Live API tests
├── render.yaml                  # Render.com deployment config
├── requirements.txt
├── .env.example
├── .gitignore                   # .env excluded
├── DECISION_LOG.md
└── README.md
```

---

## Security

- `MONDAY_API_TOKEN`, `GEMINI_API_KEY`, `GROQ_API_KEY` are loaded from environment variables only
- `.env` is excluded from version control via `.gitignore`
- `.env.example` contains variable names only — no values
- No secrets are exposed in API responses or logs
- Monday integration is read-only (no create/update/delete operations)

---

## Known Limitations

1. **Cold start latency** — first query after a Render free-tier sleep takes 30–60s (Monday API fetch)
2. **Quarterly forecasting** — 92% of deals lack a close date; Q3 filter has limited precision
3. **LLM rate limits** — free tiers have monthly/daily limits; deterministic fallback handles overload
4. **Currency not confirmed** — INR assumed from business context, not validated in source data
5. **Sector matching** — cross-board sector join is on normalised text; unrecognised sectors go to "Unknown"
6. **No conversation memory** — history within a session only; cleared on page refresh
