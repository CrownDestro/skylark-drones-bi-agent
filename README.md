# Skylark Drones — Monday.com Business Intelligence Agent

A conversational AI agent that answers founder-level business questions using live data from Monday.com. Built for the Skylark Drones technical assignment.

---

## Overview

The agent dynamically queries two Monday.com boards (Deals + Work Orders) via the GraphQL API, normalizes messy real-world data, performs deterministic Python analytics, and uses a free LLM (Gemini/Groq) to generate executive-level responses.

**Architecture principle:** The LLM never directly touches Monday.com. Python owns all data retrieval and calculation; the LLM only converts structured results into natural language.

---

## 🏗️ Architecture

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "background": "#0d1117",
    "primaryTextColor": "#111827",
    "secondaryTextColor": "#111827",
    "lineColor": "#64748b",
    "fontFamily": "Inter, Arial, sans-serif"
  }
}}%%

flowchart TB

    U["👤 Business User"]

    F["🖥️ Next.js<br/>Conversational UI"]

    B["⚡ FastAPI<br/>BI Agent API"]

    A["🤖 AI Agent"]

    M["🟣 Monday.com<br/>Deals + Work Orders"]

    X["📊 Analytics<br/>Pipeline • Billing • Forecast"]

    L["🧠 Gemini<br/>Primary LLM"]

    G["⚡ Groq<br/>Fallback LLM"]


    U --> F
    F <-->|HTTPS / SSE| B
    B --> A

    A --> M
    M --> X
    X --> A

    A --> L
    L -.->|Fallback| G


    classDef user fill:#ffffff,stroke:#64748b,stroke-width:2px,color:#111827
    classDef frontend fill:#eef2ff,stroke:#6366f1,stroke-width:2px,color:#111827
    classDef backend fill:#ecfeff,stroke:#0891b2,stroke-width:2px,color:#111827
    classDef data fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,color:#111827
    classDef ai fill:#fdf4ff,stroke:#c026d3,stroke-width:2px,color:#111827

    class U user
    class F frontend
    class B,A backend
    class M,X data
    class L,G ai

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next JS |
| Backend | Python 3.13 + FastAPI + uvicorn |
| Business Analytics | Python |
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

---

## Data Quality

The dataset contains intentional messiness. Key quality metrics:

| Field | Missing | Impact |
|---|---|---|
| Deal value | 52% (179/344) | Pipeline total is understated |
| Close date | 92% (318/344) | Quarter filtering has limited precision |
| Closure probability | 75% (258/344) | Weighted pipeline uses 30% default for most deals |
| Collected amount (WO) | 56% (98/176) | Collection rate may be understated |
| Work Order status | 42% (74/176) | Status breakdown is partial |

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
cd skylar_drones

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env

# Start backend
py -3.13 -m uvicorn backend.main:app --reload --port 8000

```

---

## API Endpoints

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
├── data/                        # problem statement & Source Excel files
├── frontend/
│   └──
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
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
├── DECISION_LOG.md
└── README.md
```

---

## Known Limitations

1. **Quarterly forecasting** — 92% of deals lack a close date; Q3 filter has limited precision
2. **LLM rate limits** — free tiers have monthly/daily limits; deterministic fallback handles overload
3. **Currency not confirmed** — INR assumed from business context, not validated in source data
4. **Sector matching** — cross-board sector join is on normalised text; unrecognised sectors go to "Unknown"
5. **No conversation memory** — history within a session only; cleared on page refresh