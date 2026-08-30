"""
Revenue analytics using Work Orders data.
Clearly distinguishes: contract amount, billed value, collected amount, receivables.
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional

from backend.analytics.utils import fmt_inr, safe_sum


def calculate_revenue(
    work_orders: List[Dict],
    sector: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate revenue metrics from Work Orders.

    Key distinctions:
    - amount_inr: Contract/PO value (what was ordered)
    - billed_value: What has been invoiced
    - collected_amount: What has been received/paid
    - amount_receivable: Outstanding amount

    Never conflates these — each has different business meaning.
    """
    filtered = list(work_orders)

    # Sector filter
    if sector:
        sector_lower = sector.lower()
        filtered = [w for w in filtered if (w.get("sector") or "").lower() == sector_lower]

    # Status filter
    if status_filter:
        s = status_filter.lower()
        filtered = [w for w in filtered
                    if (w.get("wo_status") or "").lower() == s
                    or (w.get("execution_status") or "").lower() == s]

    total_contract = safe_sum(w.get("amount_inr") for w in filtered)
    total_billed = safe_sum(w.get("billed_value") for w in filtered)
    total_collected = safe_sum(w.get("collected_amount") for w in filtered)
    total_receivable = safe_sum(w.get("amount_receivable") for w in filtered)

    missing_billed = sum(1 for w in filtered if w.get("billed_value") is None)
    missing_collected = sum(1 for w in filtered if w.get("collected_amount") is None)
    missing_contract = sum(1 for w in filtered if w.get("amount_inr") is None)

    # Collection efficiency
    collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else None

    # Sector breakdown
    sector_breakdown: Dict[str, Dict] = defaultdict(lambda: {
        "count": 0, "contract": 0.0, "billed": 0.0, "collected": 0.0, "receivable": 0.0
    })
    for w in filtered:
        sec = w.get("sector") or "Unknown"
        sector_breakdown[sec]["count"] += 1
        sector_breakdown[sec]["contract"] += w.get("amount_inr") or 0
        sector_breakdown[sec]["billed"] += w.get("billed_value") or 0
        sector_breakdown[sec]["collected"] += w.get("collected_amount") or 0
        sector_breakdown[sec]["receivable"] += w.get("amount_receivable") or 0

    # Sort by billed value
    sorted_sectors = sorted(
        sector_breakdown.items(),
        key=lambda x: x[1]["billed"],
        reverse=True,
    )

    return {
        "total_work_orders": len(filtered),
        "total_contract": total_contract,
        "total_contract_fmt": fmt_inr(total_contract),
        "total_billed": total_billed,
        "total_billed_fmt": fmt_inr(total_billed),
        "total_collected": total_collected,
        "total_collected_fmt": fmt_inr(total_collected),
        "total_receivable": total_receivable,
        "total_receivable_fmt": fmt_inr(total_receivable),
        "collection_rate_pct": round(collection_rate, 1) if collection_rate is not None else None,
        "missing_billed_count": missing_billed,
        "missing_collected_count": missing_collected,
        "missing_contract_count": missing_contract,
        "sector_breakdown": {k: {**v,
                                  "billed_fmt": fmt_inr(v["billed"]),
                                  "collected_fmt": fmt_inr(v["collected"])}
                             for k, v in sorted_sectors},
        "sector_filter": sector,
    }
