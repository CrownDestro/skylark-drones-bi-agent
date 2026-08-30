"""
Pipeline analytics: calculates total pipeline, weighted pipeline,
deal counts, stage breakdown, and sector breakdown.

Key assumption (documented in DECISION_LOG.md):
  High = 0.80, Medium = 0.50, Low = 0.20, Unknown = 0.30
"""
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.config import PROBABILITY_WEIGHTS
from backend.analytics.utils import current_quarter, fmt_inr, safe_sum


# Stages considered "open" (not won/lost)
OPEN_STAGES = {
    "Open", "New", "Qualified", "Proposal Sent",
    "Negotiation", "Pending", "In Progress", "Active",
}
CLOSED_WON_STATUSES = {"Won"}
CLOSED_LOST_STATUSES = {"Lost", "Cancelled"}


def _prob_weight(deal: Dict) -> float:
    prob = (deal.get("closure_probability") or "").lower().strip()
    return PROBABILITY_WEIGHTS.get(prob, PROBABILITY_WEIGHTS[""])


def _is_open(deal: Dict) -> bool:
    status = deal.get("deal_status") or ""
    stage = deal.get("deal_stage") or ""
    if status in CLOSED_WON_STATUSES or status in CLOSED_LOST_STATUSES:
        return False
    if stage in CLOSED_WON_STATUSES or stage in CLOSED_LOST_STATUSES:
        return False
    return True


def _in_period(deal: Dict, start: datetime, end: datetime) -> bool:
    """Check if close_date or tentative_close_date falls in period."""
    for field in ("close_date", "tentative_close_date"):
        d = deal.get(field)
        if d and start <= d <= end:
            return True
    return False


def calculate_pipeline(
    deals: List[Dict],
    sector: Optional[str] = None,
    period: Optional[str] = None,  # "current_quarter", "current_year", or None (all time)
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate pipeline metrics.

    Returns:
        total_pipeline, weighted_pipeline, deal_count, open_deal_count,
        won_value, lost_value, stage_breakdown, sector_breakdown,
        top_deals, missing_value_count, missing_date_count
    """
    # Filter by sector
    if sector:
        sector_lower = sector.lower()
        filtered = [d for d in deals if (d.get("sector") or "").lower() == sector_lower]
    else:
        filtered = list(deals)

    # Filter by period
    if period == "current_quarter":
        q_start, q_end = current_quarter()
        period_filtered = [d for d in filtered if _in_period(d, q_start, q_end)]
        # If very few deals have dates in quarter, include open deals without dates too
        open_without_date = [d for d in filtered if _is_open(d) and not _in_period(d, q_start, q_end)
                             and d.get("close_date") is None and d.get("tentative_close_date") is None]
        period_filtered.extend(open_without_date)
        filtered = period_filtered
    elif period == "current_year":
        year = datetime.now().year
        y_start = datetime(year, 1, 1)
        y_end = datetime(year, 12, 31, 23, 59, 59)
        filtered = [d for d in filtered if _in_period(d, y_start, y_end)] or filtered

    # Status filter
    if status_filter:
        s = status_filter.lower()
        if s == "open":
            filtered = [d for d in filtered if _is_open(d)]
        elif s == "won":
            filtered = [d for d in filtered if (d.get("deal_status") or "").lower() == "won"]
        elif s == "lost":
            filtered = [d for d in filtered if (d.get("deal_status") or "").lower() == "lost"]

    # Core calculations
    open_deals = [d for d in filtered if _is_open(d)]
    won_deals = [d for d in filtered if (d.get("deal_status") or "").lower() == "won"]
    lost_deals = [d for d in filtered if (d.get("deal_status") or "").lower() == "lost"]

    total_pipeline = safe_sum(d.get("deal_value") for d in open_deals)
    weighted_pipeline = sum(
        (d.get("deal_value") or 0) * _prob_weight(d) for d in open_deals
    )
    won_value = safe_sum(d.get("deal_value") for d in won_deals)
    lost_value = safe_sum(d.get("deal_value") for d in lost_deals)

    missing_value_count = sum(1 for d in open_deals if d.get("deal_value") is None)
    missing_date_count = sum(
        1 for d in open_deals
        if d.get("close_date") is None and d.get("tentative_close_date") is None
    )

    missing_prob_deals = [d for d in open_deals if not str(d.get("closure_probability") or "").strip()]
    missing_probability_count = len(missing_prob_deals)
    missing_prob_weighted_value = sum((d.get("deal_value") or 0) * PROBABILITY_WEIGHTS.get("", 0.3) for d in missing_prob_deals)

    # Stage breakdown
    stage_breakdown: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "value": 0.0})
    for d in filtered:
        stage = d.get("deal_stage") or d.get("deal_status") or "Unknown"
        stage_breakdown[stage]["count"] += 1
        stage_breakdown[stage]["value"] += d.get("deal_value") or 0

    # Sector breakdown (for all-sector queries)
    sector_breakdown: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "value": 0.0, "weighted": 0.0})
    for d in open_deals:
        sec = d.get("sector") or "Unknown"
        sector_breakdown[sec]["count"] += 1
        v = d.get("deal_value") or 0
        sector_breakdown[sec]["value"] += v
        sector_breakdown[sec]["weighted"] += v * _prob_weight(d)

    # Top deals by value
    top_deals = sorted(
        [d for d in open_deals if d.get("deal_value") is not None],
        key=lambda x: x["deal_value"],
        reverse=True,
    )[:5]

    return {
        "total_records": len(filtered),
        "open_deal_count": len(open_deals),
        "won_deal_count": len(won_deals),
        "lost_deal_count": len(lost_deals),
        "total_pipeline": total_pipeline,
        "total_pipeline_fmt": fmt_inr(total_pipeline),
        "weighted_pipeline": weighted_pipeline,
        "weighted_pipeline_fmt": fmt_inr(weighted_pipeline),
        "won_value": won_value,
        "won_value_fmt": fmt_inr(won_value),
        "lost_value": lost_value,
        "stage_breakdown": dict(stage_breakdown),
        "sector_breakdown": {k: dict(v) for k, v in sector_breakdown.items()},
        "top_deals": [
            {"name": d["name"], "value": d["deal_value"], "value_fmt": fmt_inr(d["deal_value"]),
             "stage": d.get("deal_stage"), "sector": d.get("sector")}
            for d in top_deals
        ],
        "missing_value_count": missing_value_count,
        "missing_date_count": missing_date_count,
        "missing_probability_count": missing_probability_count,
        "missing_probability_weighted_value": missing_prob_weighted_value,
        "missing_probability_weighted_value_fmt": fmt_inr(missing_prob_weighted_value),
        "sector_filter": sector,
        "period_filter": period,
        "quarter_info": (lambda q: f"Q{(q.month-1)//3+1} {q.year}")(current_quarter()[0]) if period == "current_quarter" else None,
    }
