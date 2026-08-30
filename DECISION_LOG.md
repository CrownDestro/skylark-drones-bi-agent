# Decision Log — Skylark Drones BI Agent

**Author:** Dheeraj M  
**Scope:** Monday.com Business Intelligence Agent — key decisions, trade-offs, and assumptions

---

## Assumption: Use of free tier LLM like gemini and grok and not Ollama

**Cause:** Use free hosted APIs as Ollama requires a local GPU or CPU inference server. Gemini (free tier, Google AI Studio) offers zero-cost access suitable for BI responses. Groq (LLaMA 3.3 70B) provides a fast, generous free-tier fallback. Both require only an API key and work in any hosted environment.

---

## Assumption: Use LLM Is Used Only for Language and python for computation and Numbers

**Decision:** Use python as, Python handles all arithmetic. LLM handles only intent detection and prose generation.


The dataset is intentionally messy. Trusting an LLM to sum, filter, or aggregate monetary values risks hallucinated numbers being presented as business facts to an executive. All sums, percentages, ratios, and aggregations are performed by Python. The LLM receives a JSON analytics context and converts it into executive-level language only.

---

## -> Assumptions

The following core assumptions were strictly applied in the analytics logic:

1. **Probability weights:**
   - High = 80%
   - Medium = 50%
   - Low = 20%
   - Unknown = 30%
   *(These are analytical assumptions and are NOT values supplied by the source data. The Unknown = 30% assumption is used for deals with missing Closure Probability. This caveat is surfaced when showing weighted pipeline).*

2. **Currency:**
   - INR (₹)
   *(Currency is assumed to be INR and is not provided by the raw source numbers).*

3. **Quarter:**
   - Dynamically calculated using calendar quarters (from the runtime/current date).

---

## Closure Probability Transparency

The Closure Probability field in Monday contains qualitative values: **High**, **Medium**, **Low** (or empty). These are not numeric probabilities — they are CRM labels.

**Impact:** 258 of 344 deals (75%) have no closure probability — the 30% default applies to most of the pipeline. The weighted pipeline figure should be interpreted as an indicative estimate, and this assumption is visibly surfaced to the user.

---

## Data Quality Observations (Actual Data — Validated 30 Aug 2026)

| Board | Issue | Count | Impact |
|---|---|---|---|
| Deals | Missing deal value | 179/344 (52%) | Pipeline understated |
| Deals | Missing close date | 318/344 (92%) | Quarterly forecasting limited |
| Deals | Missing closure probability | 258/344 (75%) | Weighted pipeline uses 30% default |
| Work Orders | Missing collected amount | 98/176 (56%) | Collection rate may be understated |
| Work Orders | Missing WO status | 74/176 (42%) | Status breakdown is partial |

The system surfaces these as material caveats wherever they affect the requested answer.

---

## Assumption: Do Sector Normalisation

Raw sector values are mapped to canonical names:

| Raw | Canonical |
|---|---|
| MINING, mining sector | Mining |
| RENEWABLES, renewable | Renewables |
| POWERLINE, power line | Powerline |
| RAILWAYS, railway | Railways |
| DSP | DSP |
| energy | Renewables + Powerline (merged query) |
