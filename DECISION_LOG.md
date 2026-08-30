# Decision Log — Skylark Drones BI Agent

**Author:** Technical Candidate  
**Date:** 30 August 2026  
**Scope:** Monday.com Business Intelligence Agent — key decisions, trade-offs, and assumptions

---

## 1. Why Monday GraphQL API (not MCP)

The assignment asks for Monday.com integration. The Monday.com Model Context Protocol (MCP) server is a newer tool, but it routes the LLM directly to Monday, which would violate the requirement that numerical calculations be deterministic and controlled. Instead, the backend exclusively owns the Monday integration via the GraphQL v2 API. The LLM sees only structured analytical results, never raw Monday data.

**Decision:** Monday GraphQL API → Python analytics → LLM explanation.

---

## 2. Why Free Hosted LLM (not Ollama)

Ollama requires a local GPU or CPU inference server. A hosted prototype evaluated by a third party cannot depend on a local machine. Gemini 1.5 Flash (free tier, Google AI Studio) offers zero-cost access suitable for BI responses. Groq (LLaMA 3.3 70B) provides a fast, generous free-tier fallback. Both require only an API key and work in any hosted environment.

**Provider chain:** Gemini → Groq → Deterministic structured fallback  
**Decision:** Free hosted APIs; LLM provider abstracted behind `backend/agent/llm.py`.

---

## 3. Why LLM Is Used Only for Language, Not Numbers

The dataset is intentionally messy. Trusting an LLM to sum, filter, or aggregate monetary values risks hallucinated numbers being presented as business facts to an executive. All sums, percentages, ratios, and aggregations are performed by Python. The LLM receives a JSON analytics context and converts it into executive-level language only.

**Decision:** Python handles all arithmetic. LLM handles only intent detection and prose generation.

---

## 4. Closure Probability Assumption

The Closure Probability field in Monday contains qualitative values: **High**, **Medium**, **Low** (or empty). These are not numeric probabilities — they are CRM labels.

For weighted pipeline, the following mapping was applied:

| Label | Weight Applied |
|---|---|
| High | 80% |
| Medium | 50% |
| Low | 20% |
| Unknown / Missing | 30% (conservative) |

**This is an analytical assumption, not source data.** It is stated in all responses where weighted pipeline is shown.

**Impact:** 258 of 344 deals (75%) have no closure probability — the 30% default applies to most of the pipeline. The weighted pipeline figure should be interpreted as an indicative estimate.

---

## 5. Calendar Quarter Assumption

"Current quarter" is calculated dynamically from the runtime date using calendar quarters:

- Q1: Jan–Mar · Q2: Apr–Jun · Q3: Jul–Sep · Q4: Oct–Dec

As of 30 August 2026, this resolves to **Q3 2026 (1 Jul – 30 Sep 2026)**.

**Caveat:** 92% of open deals have no close date. Quarterly pipeline filtering has limited applicability; the system includes all undated open deals in the quarterly view and flags this limitation.

---

## 6. Currency Assumption (INR)

All monetary values in Monday.com are assumed to be **Indian Rupees (INR)**. The source data was masked; no currency symbol appears in the raw Monday fields. INR is assumed from business context. Figures are displayed as Cr (crore) and L (lakh).

**The following are treated as distinct and never conflated:**
- Deal Value (pipeline potential)
- Contract Amount / Amount (Excl. GST)
- Billed Value (invoiced amount)
- Collected Amount (received cash)
- Amount Receivable (outstanding)

---

## 7. Data Quality Observations (Actual Data — Validated 30 Aug 2026)

| Board | Issue | Count | Impact |
|---|---|---|---|
| Deals | Missing deal value | 179/344 (52%) | Pipeline understated |
| Deals | Missing close date | 318/344 (92%) | Quarterly forecasting limited |
| Deals | Missing closure probability | 258/344 (75%) | Weighted pipeline uses 30% default |
| Work Orders | Missing collected amount | 98/176 (56%) | Collection rate may be understated |
| Work Orders | Missing WO status | 74/176 (42%) | Status breakdown is partial |

The system surfaces these as material caveats wherever they affect the requested answer.

---

## 8. Leadership Update Interpretation

The assignment described a "leadership update" without a fixed schema. This was interpreted as an executive summary combining: sales pipeline snapshot, operational/WO performance, billing and collections, key risks, and cross-sector insights. The format follows a standard board-ready structure (Sales / Execution / Financial / Risks / Opportunities).

---

## 9. What Would Be Improved with More Time

1. **Persistent caching (Redis)** — eliminate the 20–30s Monday fetch on first request
2. **Scheduled data refresh** — cache warmed at startup, not on first user query
3. **Historical trend analysis** — QoQ pipeline comparison once data accumulates
4. **Richer cross-board matching** — sector name normalization between boards is approximate
5. **Authenticated frontend** — currently open to anyone with the URL
6. **Conversation memory** — short-term session memory improves follow-up queries
7. **Chart rendering** — bar charts for sector breakdown would improve executive experience
8. **Deal-level search** — "find me all Mining deals above ₹5 Cr" requires item-level filtering

---

*All values shown in responses are retrieved live from Monday.com. Excel files were used only to populate Monday.com and are not accessed at runtime.*
