"""
Core BI Agent: routes user intent to analytics tools and generates responses.

Flow:
  user message
    → intent detection (LLM or pattern matching)
    → analytics tools (deterministic Python)
    → context building
    → LLM response generation
    → executive answer (+ caveats)
"""
import re
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.agent.llm import get_router
from backend.agent.prompts import SYSTEM_PROMPT, build_context
from backend.data.normalizer import normalize_deals, normalize_work_orders
from backend.data.quality import check_deals_quality, check_work_orders_quality

logger = logging.getLogger(__name__)

# ─── Intent patterns ─────────────────────────────────────────────────────────
# Lightweight pattern matching to reduce LLM calls for intent detection

INTENT_PATTERNS = [
    # Data provenance / transparency (check early — specific)
    (r"(what|which)\s+(data|source|board|record)|you\s+use|data.*used|how.*know", "data_provenance"),
    # Pipeline reliability / forecast quality
    (r"reliab|forecast\s+reliab|accura|confiden|trustworth|missing\s+data", "forecast_reliability"),
    # Leadership / executive summary
    (r"leadership\s+update|executive\s+summary|board\s+update|status\s+update|prepare\s+(a\s+)?update", "leadership_update"),
    # Ambiguous business health — must check BEFORE generic patterns
    (r"how.*(business\s+doing|company\s+doing|we\s+doing)", "ambiguous_business"),
    # Revenue / billing
    (r"revenue|billed|billing|invoice", "revenue_analysis"),
    # Collections / receivables
    (r"collect(ed|ion)|received|outstanding|receivabl", "revenue_analysis"),
    # Sector ranking — must be before cross_board_analysis and pipeline
    (r"which\s+sector|sector.*strongest|sector.*best|sector.*rank|strongest\s+sector|best\s+sector", "sector_analysis"),
    # Cross-board: requires both pipeline and execution concepts
    (r"(pipeline.*execut|execut.*pipeline|strong.*pipeline.*weak|weak.*execut|compar.*sector|sector.*compar|vs\b|versus\b)", "cross_board_analysis"),
    # Sector-specific pipeline queries
    (r"(energy|renewables?|powerline|mining|railways?|dsp|tender|sector)\s+(pipeline|deals?|performance|looking)", "pipeline_analysis"),
    # Pipeline general
    (r"pipeline|deals?\s+pipeline|sales\s+pipeline|funnel", "pipeline_analysis"),
    # Work orders / operations
    (r"work\s+order|operations?|execution|project\s+status", "work_order_analysis"),
    # Deals specific (biggest, won, etc.)
    (r"(top|biggest|largest|best)\s+deal|open\s+deal|active\s+deal|won|closed", "deals_analysis"),
    # Sector generic
    (r"sector|industry|segment", "sector_analysis"),
]


SECTOR_PATTERNS = {
    "mining": "Mining",
    "powerline": "Powerline",
    "power line": "Powerline",
    "renewables": "Renewables",
    "renewable": "Renewables",
    "energy": "Energy",
    "solar": "Renewables",
    "railways": "Railways",
    "railway": "Railways",
    "rail": "Railways",
    "dsp": "DSP",
    "tender": "Tender",
    "construction": "Construction",
    "aviation": "Aviation",
    "manufacturing": "Manufacturing",
    "security": "Security And Surveillance",
    "surveillance": "Security And Surveillance",
}


PERIOD_PATTERNS = {
    "this quarter": "current_quarter",
    "current quarter": "current_quarter",
    "q1": "Q1",
    "q2": "Q2",
    "q3": "Q3",
    "q4": "Q4",
    "this year": "current_year",
    "current year": "current_year",
    "fy": "current_year",
}


def detect_intent(message: str) -> str:
    """Detect user intent from message using pattern matching."""
    msg_lower = message.lower()
    for pattern, intent in INTENT_PATTERNS:
        if re.search(pattern, msg_lower):
            return intent
    return "general_query"


def extract_sector(message: str) -> Optional[str]:
    """Extract sector from user message."""
    msg_lower = message.lower()
    for key, sector in SECTOR_PATTERNS.items():
        if key in msg_lower:
            if isinstance(sector, list):
                return sector[0]  # return primary
            return sector
    return None


def extract_period(message: str) -> Optional[str]:
    """Extract time period from user message."""
    msg_lower = message.lower()
    for pattern, period in PERIOD_PATTERNS.items():
        if pattern in msg_lower:
            return period
    return None


def _deterministic_response(intent: str, analytics_data: Dict, sector: Optional[str] = None) -> str:
    """
    Generate a structured response without LLM when all providers fail.
    Returns markdown-formatted text.
    """
    lines = ["📊 **Skylark Drones Business Intelligence**\n"]

    if intent == "leadership_update":
        lu = analytics_data.get("leadership_update", {})
        p = lu.get("pipeline", {})
        r = lu.get("revenue", {})
        o = lu.get("operations", {})
        top_sectors = lu.get("top_sectors", [])

        lines.append(f"## Leadership Update — {datetime.now().strftime('%B %Y')}\n")
        lines.append("### 💼 Sales Pipeline")
        lines.append(f"- Open Deals: **{p.get('open_deal_count', 'N/A')}**")
        lines.append(f"- Total Pipeline: **{p.get('total_pipeline_fmt', 'N/A')}**")
        lines.append(f"- Weighted Pipeline: **{p.get('weighted_pipeline_fmt', 'N/A')}**")
        
        missing_prob = p.get('missing_probability_count', 0)
        total_open = p.get('open_deal_count', 1) or 1
        if missing_prob > 0:
            pct = round((missing_prob / total_open) * 100)
            lines.append(f"  *Assumes 30% probability for {missing_prob} deals ({pct}%) missing this value.*")
            
        lines.append(f"- Deals Won: **{p.get('won_value_fmt', 'N/A')}**\n")

        lines.append("### 💰 Revenue & Collections (Work Orders)")
        lines.append(f"- Total Billed: **{r.get('total_billed_fmt', 'N/A')}**")
        lines.append(f"- Collected: **{r.get('total_collected_fmt', 'N/A')}**")
        lines.append(f"- Receivables: **{r.get('total_receivable_fmt', 'N/A')}**")
        if r.get("collection_rate_pct") is not None:
            lines.append(f"- Collection Rate: **{r['collection_rate_pct']}%**\n")

        lines.append("### ⚙️ Operations")
        lines.append(f"- Total Work Orders: **{o.get('total', 'N/A')}**")
        lines.append(f"- Active: {o.get('active_count', 'N/A')}")
        lines.append(f"- Completed: {o.get('completed_count', 'N/A')}\n")

        if top_sectors:
            lines.append("### 🏆 Top Sectors by Pipeline")
            for s in top_sectors[:3]:
                lines.append(f"- **{s['sector']}**: Pipeline {s['pipeline_fmt']}, Billed {s['billed_value_fmt']}")
            lines.append("")

        risks = lu.get("risks", [])
        if risks:
            lines.append("### ⚠️ Key Risks")
            for r_item in risks:
                lines.append(f"- {r_item}")
            lines.append("")

        caveats = lu.get("deal_caveats", []) + lu.get("wo_caveats", [])
        if caveats:
            lines.append("### 📋 Data Quality Notes")
            for c in caveats[:3]:
                lines.append(f"- {c}")

    elif intent in ("pipeline_analysis", "deals_analysis"):
        p = analytics_data.get("pipeline", {})
        lines.append("### 📈 Pipeline Analysis")
        if sector:
            lines.append(f"**Sector: {sector}**\n")
        lines.append(f"- Open Deals: **{p.get('open_deal_count', 'N/A')}**")
        lines.append(f"- Total Pipeline: **{p.get('total_pipeline_fmt', 'N/A')}**")
        lines.append(f"- Weighted Pipeline: **{p.get('weighted_pipeline_fmt', 'N/A')}**")
        
        missing_prob = p.get('missing_probability_count', 0)
        total_open = p.get('open_deal_count', 1) or 1
        if missing_prob > 0:
            pct = round((missing_prob / total_open) * 100)
            lines.append(f"  *Assumes 30% probability for {missing_prob} deals ({pct}%) missing this value.*")

        lines.append(f"- Deals Won: **{p.get('won_value_fmt', 'N/A')}**\n")

        if p.get("top_deals"):
            lines.append("**Top Deals:**")
            for d in p["top_deals"][:3]:
                lines.append(f"- {d['name']}: **{d['value_fmt']}** — {d.get('stage', 'N/A')}")
            lines.append("")

        if p.get("stage_breakdown"):
            lines.append("**By Stage:**")
            for stage, info in sorted(p["stage_breakdown"].items(), key=lambda x: x[1]["value"], reverse=True)[:5]:
                lines.append(f"- {stage}: {info['count']} deals")
            lines.append("")

        caveats = []
        if p.get("missing_value_count", 0) > 0:
            caveats.append(f"{p['missing_value_count']} deals have missing values — total may be understated.")
        if p.get("missing_date_count", 0) > 0:
            caveats.append(f"{p['missing_date_count']} deals have no expected close date.")
        if caveats:
            lines.append("**⚠️ Data Notes:**")
            for c in caveats:
                lines.append(f"- {c}")

    elif intent == "revenue_analysis":
        r = analytics_data.get("revenue", {})
        lines.append("### 💰 Revenue Analysis")
        if sector:
            lines.append(f"**Sector: {sector}**\n")
        lines.append(f"- Contract Value: **{r.get('total_contract_fmt', 'N/A')}**")
        lines.append(f"- Billed: **{r.get('total_billed_fmt', 'N/A')}**")
        lines.append(f"- Collected: **{r.get('total_collected_fmt', 'N/A')}**")
        lines.append(f"- Receivables: **{r.get('total_receivable_fmt', 'N/A')}**")
        if r.get("collection_rate_pct") is not None:
            lines.append(f"- Collection Efficiency: **{r['collection_rate_pct']}%**")

    elif intent == "work_order_analysis":
        o = analytics_data.get("operations", {})
        lines.append("### ⚙️ Work Order Analysis")
        lines.append(f"- Total: **{o.get('total', 'N/A')}**")
        lines.append(f"- Active: **{o.get('active_count', 'N/A')}**")
        lines.append(f"- Completed: **{o.get('completed_count', 'N/A')}**")
        lines.append(f"- Contract: **{o.get('total_contract_fmt', 'N/A')}**")
        lines.append(f"- Billed: **{o.get('total_billed_fmt', 'N/A')}**")
        lines.append(f"- Collected: **{o.get('total_collected_fmt', 'N/A')}**")

    elif intent == "sector_analysis":
        c = analytics_data.get("cross_board", {})
        lines.append("### 🏭 Sector Performance")
        for sec in c.get("sectors", [])[:6]:
            lines.append(f"\n**{sec['sector']}**")
            lines.append(f"  Pipeline: {sec['pipeline_fmt']} ({sec['deal_count']} deals)")
            lines.append(f"  Billed: {sec['billed_value_fmt']} ({sec['wo_count']} WOs)")

    elif intent == "cross_board_analysis":
        c = analytics_data.get("cross_board", {})
        lines.append("### 🔄 Pipeline vs Execution by Sector")
        for sec in c.get("sectors", [])[:5]:
            lines.append(f"\n**{sec['sector']}**")
            lines.append(f"  Pipeline: {sec['pipeline_fmt']} | Billed: {sec['billed_value_fmt']}")
            lines.append(f"  Insight: *{sec['insight']}*")

    elif intent == "data_provenance":
        p = analytics_data.get("pipeline", {})
        r = analytics_data.get("revenue", {})
        lines.append("### 📁 Data Sources Used")
        lines.append("\n**Deals Board (Monday.com)**")
        lines.append(f"- Records: {p.get('total_records', 'N/A')} deals")
        lines.append(f"- Open deals included: {p.get('open_deal_count', 'N/A')}")
        lines.append("- Fields: Deal Name, Owner, Client, Status, Stage, Closure Probability, Deal Value, Sector, Close Dates")
        lines.append("\n**Work Orders Board (Monday.com)**")
        lines.append(f"- Records: {r.get('total_work_orders', 'N/A')} work orders")
        lines.append("- Fields: Customer, Sector, Execution Status, Amount (excl GST), Billed Value, Collected Amount, Receivables")
        lines.append("\n**Analytical Assumptions**")
        lines.append("- Closure probability: High=80%, Medium=50%, Low=20%, Unknown=30%")
        lines.append("- Currency: INR (as provided in Monday.com data)")
        lines.append("- Quarter: Dynamically calculated from current date")
        lines.append("- Data is fetched live from Monday.com GraphQL API (read-only)")
        lines.append("- Excel source files are NOT used at runtime")
        if p.get("missing_value_count", 0) > 0:
            lines.append(f"\n**Data Quality**")
            lines.append(f"- {p['missing_value_count']} deals missing deal value")
            lines.append(f"- {p.get('missing_date_count', 0)} deals missing close date")

    elif intent == "forecast_reliability":
        p = analytics_data.get("pipeline", {})
        mv = p.get("missing_value_count", 0)
        md = p.get("missing_date_count", 0)
        total_open = p.get("open_deal_count", 1) or 1
        value_pct = round((1 - mv / total_open) * 100) if total_open else 0
        date_pct = round((1 - md / total_open) * 100) if total_open else 0

        lines.append("### 🔍 Pipeline Forecast Reliability")
        lines.append(f"\n**Total Open Deals: {p.get('open_deal_count', 'N/A')}**\n")
        lines.append(f"- Deal value populated: **{total_open - mv}/{total_open}** ({value_pct}%)")
        lines.append(f"- Close date available: **{total_open - md}/{total_open}** ({date_pct}%)\n")

        if value_pct < 60:
            lines.append("⚠️ **Low confidence** — over 40% of open deals lack a monetary value. The total pipeline figure is significantly understated.")
        elif value_pct < 80:
            lines.append("⚠️ **Moderate confidence** — some deal values missing. Pipeline total may be understated by 20-40%.")
        else:
            lines.append("✅ **Reasonable confidence** — most open deals have a monetary value populated.")

        if date_pct < 20:
            lines.append("⚠️ **Quarter forecasting is unreliable** — over 80% of deals have no close date. Current-quarter pipeline filter cannot be applied meaningfully.")
        elif date_pct < 50:
            lines.append("⚠️ **Quarter forecasting is limited** — fewer than half of deals have a close date.")

        lines.append("\n**Probability weights used (not from Monday data):**")
        lines.append("High=80%, Medium=50%, Low=20%, Unknown/missing=30%")
        lines.append(f"- Deals with probability set: {total_open - p.get('missing_value_count', 0)}")
        lines.append(f"\n_Weighted pipeline: {p.get('weighted_pipeline_fmt', 'N/A')}_")
        lines.append("_This represents a probabilistic estimate, not a committed forecast._")

    elif intent == "ambiguous_business":
        lines.append("I can analyze different aspects of the business. Which would you like?")
        lines.append("\n1. **Sales Pipeline** — deal counts, values, stages, and sectors")
        lines.append("2. **Revenue & Collections** — billed amounts, collected amounts, receivables")
        lines.append("3. **Work Order Operations** — active projects, execution status")
        lines.append("4. **Leadership Update** — comprehensive executive summary")
        lines.append("\nJust ask about any of these, or say 'give me a leadership update' for a full overview.")
        return "\n".join(lines)
    else:
        lines.append("I can help with:")
        lines.append("- **Pipeline analysis** — 'How's our pipeline?'")
        lines.append("- **Revenue** — 'How much have we billed/collected?'")
        lines.append("- **Work orders** — 'How are operations performing?'")
        lines.append("- **Sector analysis** — 'Which sector has the best pipeline?'")
        lines.append("- **Cross-board** — 'Compare pipeline vs execution by sector'")
        lines.append("- **Leadership update** — 'Give me a leadership update'")

    lines.append(f"\n_Based on Monday.com data as of {datetime.now().strftime('%d %b %Y')}_")
    return "\n".join(lines)



class BIAgent:
    """
    Skylark Drones BI Agent.
    Orchestrates intent detection, analytics, and LLM response generation.
    """

    def __init__(self):
        self._llm = get_router()
        self._deals_cache: Optional[List[Dict]] = None
        self._work_orders_cache: Optional[List[Dict]] = None
        self._deals_quality = None
        self._work_orders_quality = None
        self._cache_time: Optional[datetime] = None
        self.CACHE_SECONDS = 300  # 5-minute cache

    def _is_cache_valid(self) -> bool:
        if not self._cache_time:
            return False
        return (datetime.now() - self._cache_time).total_seconds() < self.CACHE_SECONDS

    def _load_data(self, needs_deals: bool = True, needs_wos: bool = True, progress_callback=None) -> Tuple[List[Dict], List[Dict]]:
        """Load and normalize data from Monday.com (with 5-min cache, parallel fetch if needed)."""
        if self._is_cache_valid() and self._deals_cache is not None and self._work_orders_cache is not None:
            if progress_callback:
                progress_callback({"stage": "fetching_cache", "status": "complete", "message": "Using cached board data"})
            return self._deals_cache, self._work_orders_cache

        from backend.monday.boards import fetch_deals, fetch_work_orders
        import concurrent.futures

        raw_deals = []
        raw_wos = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_deals = None
            future_wos = None

            if needs_deals:
                if progress_callback:
                    progress_callback({"stage": "fetching_deals", "status": "running"})
                future_deals = executor.submit(fetch_deals)
            if needs_wos:
                if progress_callback:
                    progress_callback({"stage": "fetching_work_orders", "status": "running"})
                future_wos = executor.submit(fetch_work_orders)

            if future_deals:
                raw_deals = future_deals.result()
                if progress_callback:
                    progress_callback({"stage": "fetching_deals", "status": "complete", "message": f"Retrieved {len(raw_deals)} Deals"})
            
            if future_wos:
                raw_wos = future_wos.result()
                if progress_callback:
                    progress_callback({"stage": "fetching_work_orders", "status": "complete", "message": f"Retrieved {len(raw_wos)} Work Orders"})

        if progress_callback:
            progress_callback({"stage": "normalizing", "status": "running"})

        if needs_deals:
            self._deals_cache = normalize_deals(raw_deals)
            self._deals_quality = check_deals_quality(self._deals_cache)
        
        if needs_wos:
            self._work_orders_cache = normalize_work_orders(raw_wos)
            self._work_orders_quality = check_work_orders_quality(self._work_orders_cache)
            
        self._cache_time = datetime.now()

        if progress_callback:
            progress_callback({"stage": "normalizing", "status": "complete", "message": "Data normalized and validated"})

        logger.info("Loaded %d deals and %d work orders", 
                    len(self._deals_cache) if self._deals_cache else 0, 
                    len(self._work_orders_cache) if self._work_orders_cache else 0)
        
        return self._deals_cache or [], self._work_orders_cache or []

    def chat(self, user_message: str, conversation_history: List[Dict] = None, progress_callback=None) -> Dict[str, Any]:
        """
        Main entry point. Returns a dict with:
          - response: str (formatted answer)
          - intent: str
          - sector: optional str
          - period: optional str
          - data_quality: dict
          - analytics_used: list[str]
          - sources: list[str]
        """
        try:
            # Detect intent and parameters
            intent = detect_intent(user_message)
            sector = extract_sector(user_message)
            period = extract_period(user_message)

            # Ambiguous business health → ask clarifying question, no data fetch needed
            if intent == "ambiguous_business":
                return {
                    "response": _deterministic_response("ambiguous_business", {}, sector),
                    "intent": intent,
                    "sector": sector,
                    "period": period,
                    "data_quality": {},
                    "analytics_used": [],
                    "sources": [],
                }

            if progress_callback:
                progress_callback({"stage": "understanding", "status": "complete", "message": f"Identified intent: {intent}"})

            needs_deals = intent in ("pipeline_analysis", "deals_analysis", "sector_analysis", "cross_board_analysis", "leadership_update", "data_provenance", "forecast_reliability", "general_query")
            needs_wos = intent in ("revenue_analysis", "work_order_analysis", "sector_analysis", "cross_board_analysis", "leadership_update", "data_provenance", "general_query")

            # Load data from Monday.com (with 5-min cache)
            deals, work_orders = self._load_data(needs_deals=needs_deals, needs_wos=needs_wos, progress_callback=progress_callback)

            if progress_callback:
                progress_callback({"stage": "analytics", "status": "running"})

            # ── Analytics dispatch ─────────────────────────────────────────────
            analytics_data: Dict = {}
            caveats = []

            if intent in ("pipeline_analysis", "deals_analysis"):
                if sector == "Energy":
                    return {
                        "response": (
                            "There is no explicit 'Energy' sector in the source Deals data. "
                            "The available related sectors are **Renewables** and **Powerline**. "
                            "Please ask about those specifically if you would like to see their pipelines."
                        ),
                        "intent": intent,
                        "sector": sector,
                        "period": period,
                        "data_quality": {},
                        "analytics_used": [],
                        "sources": ["Deals Board"],
                    }

                from backend.analytics.pipeline import calculate_pipeline
                analytics_data["pipeline"] = calculate_pipeline(deals, sector=sector, period=period)
                caveats += self._deals_quality.to_caveats(threshold=5)

            elif intent == "revenue_analysis":
                from backend.analytics.revenue import calculate_revenue
                analytics_data["revenue"] = calculate_revenue(work_orders, sector=sector)
                caveats += self._work_orders_quality.to_caveats(threshold=5)

            elif intent == "work_order_analysis":
                from backend.analytics.work_orders import analyze_work_orders
                analytics_data["operations"] = analyze_work_orders(work_orders, sector=sector)
                caveats += self._work_orders_quality.to_caveats(threshold=5)

            elif intent == "sector_analysis":
                from backend.analytics.cross_board import cross_board_sector_analysis
                analytics_data["cross_board"] = cross_board_sector_analysis(deals, work_orders)

            elif intent == "cross_board_analysis":
                from backend.analytics.cross_board import cross_board_sector_analysis
                from backend.analytics.pipeline import calculate_pipeline
                analytics_data["cross_board"] = cross_board_sector_analysis(deals, work_orders)
                analytics_data["pipeline"] = calculate_pipeline(deals)

            elif intent == "leadership_update":
                from backend.analytics.cross_board import generate_leadership_update
                lu = generate_leadership_update(
                    deals, work_orders,
                    self._deals_quality,
                    self._work_orders_quality,
                )
                analytics_data["leadership_update"] = lu
                analytics_data["pipeline"] = lu.get("pipeline", {})
                analytics_data["revenue"] = lu.get("revenue", {})
                analytics_data["operations"] = lu.get("operations", {})
                analytics_data["cross_board"] = lu.get("cross_board", {})

            elif intent == "data_provenance":
                # User wants to know what data was used — provide full transparency
                from backend.analytics.pipeline import calculate_pipeline
                from backend.analytics.revenue import calculate_revenue
                analytics_data["pipeline"] = calculate_pipeline(deals)
                analytics_data["revenue"] = calculate_revenue(work_orders)
                caveats += self._deals_quality.to_caveats(threshold=1)
                caveats += self._work_orders_quality.to_caveats(threshold=1)

            elif intent == "forecast_reliability":
                # User wants to know how reliable the pipeline forecast is
                from backend.analytics.pipeline import calculate_pipeline
                analytics_data["pipeline"] = calculate_pipeline(deals)
                caveats += self._deals_quality.to_caveats(threshold=1)

            else:
                # general_query: provide pipeline + revenue overview
                from backend.analytics.pipeline import calculate_pipeline
                from backend.analytics.revenue import calculate_revenue
                analytics_data["pipeline"] = calculate_pipeline(deals, sector=sector, period=period)
                analytics_data["revenue"] = calculate_revenue(work_orders)
                caveats += self._deals_quality.to_caveats(threshold=5)

            analytics_data["caveats"] = caveats

            # Build structured context for LLM
            context = build_context(analytics_data)

            if progress_callback:
                progress_callback({"stage": "analytics", "status": "complete", "message": "Calculated metrics"})
                progress_callback({"stage": "generating_response", "status": "running"})

            # ── LLM generation ────────────────────────────────────────────────
            llm_response = self._llm.generate(SYSTEM_PROMPT, user_message, context)

            # Sanitize: reject error-shaped strings that a provider may return as text
            # (e.g. Groq returning {"error": ...} JSON as a string)
            _is_error_response = (
                llm_response
                and (
                    llm_response.strip().startswith("{'error'")
                    or llm_response.strip().startswith('{"error"')
                    or llm_response.strip().startswith("LLM Error")
                    or "No endpoints found" in llm_response
                    or "is not found for API version" in llm_response
                )
            )

            if llm_response and not _is_error_response:
                response = llm_response
            else:
                if _is_error_response:
                    logger.warning("LLM returned error-shaped response, using deterministic fallback")
                else:
                    logger.info("All LLM providers failed — using deterministic fallback for intent: %s", intent)
                response = _deterministic_response(intent, analytics_data, sector)

            # ── Build sources list ─────────────────────────────────────────────
            sources = []
            used = set(analytics_data.keys())
            if any(k in used for k in ("pipeline", "deals_analysis", "cross_board", "leadership_update")):
                sources.append("Deals Board")
            if any(k in used for k in ("revenue", "operations", "work_order_analysis", "cross_board", "leadership_update")):
                sources.append("Work Orders Board")

            return {
                "response": response,
                "intent": intent,
                "sector": sector,
                "period": period,
                "data_quality": {
                    "deals": self._deals_quality.to_dict() if self._deals_quality else {},
                    "work_orders": self._work_orders_quality.to_dict() if self._work_orders_quality else {},
                },
                "analytics_used": [k for k in analytics_data if k != "caveats"],
                "sources": sources,
            }

        except RuntimeError as e:
            logger.error("Monday API error in chat: %s", e)
            return {
                "response": (
                    "I'm unable to retrieve data from Monday.com right now. "
                    "The API may be temporarily unavailable. Please try again in a moment."
                ),
                "intent": "error",
                "error": str(e),
                "data_quality": {},
                "analytics_used": [],
                "sources": [],
            }
        except Exception as e:
            logger.exception("Unexpected error in BIAgent.chat: %s", e)
            return {
                "response": "An unexpected error occurred. Please try again.",
                "intent": "error",
                "error": str(e),
                "data_quality": {},
                "analytics_used": [],
                "sources": [],
            }
