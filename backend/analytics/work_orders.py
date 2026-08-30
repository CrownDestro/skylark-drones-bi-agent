"""
Work Order operational analytics.
"""
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional

from backend.analytics.utils import fmt_inr, safe_sum


def analyze_work_orders(
    work_orders: List[Dict],
    sector: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Operational analysis of work orders:
    - Status distribution
    - Execution vs billing vs collection status
    - Active / completed / delayed counts
    - Financial summary
    """
    filtered = list(work_orders)

    if sector:
        sector_lower = sector.lower()
        filtered = [w for w in filtered if (w.get("sector") or "").lower() == sector_lower]

    total = len(filtered)

    # Execution status breakdown
    exec_status_counts = Counter(
        w.get("execution_status") or "Unknown" for w in filtered
    )
    wo_status_counts = Counter(
        w.get("wo_status") or "Unknown" for w in filtered
    )
    billing_status_counts = Counter(
        w.get("billing_status") or "Unknown" for w in filtered
    )
    collection_status_counts = Counter(
        w.get("collection_status") or "Unknown" for w in filtered
    )

    # Active / completed
    active_statuses = {"Active", "In Progress", "Open", "New"}
    completed_statuses = {"Completed", "Done", "Won"}
    active_count = sum(1 for w in filtered if (w.get("wo_status") or w.get("execution_status") or "") in active_statuses)
    completed_count = sum(1 for w in filtered if (w.get("wo_status") or w.get("execution_status") or "") in completed_statuses)

    # Nature of work breakdown
    nature_counts = Counter(w.get("nature_of_work") or "Unknown" for w in filtered)
    type_counts = Counter(w.get("type_of_work") or "Unknown" for w in filtered)

    # Financial summary
    total_contract = safe_sum(w.get("amount_inr") for w in filtered)
    total_billed = safe_sum(w.get("billed_value") for w in filtered)
    total_collected = safe_sum(w.get("collected_amount") for w in filtered)
    total_receivable = safe_sum(w.get("amount_receivable") for w in filtered)

    # Missing key fields
    missing_amount = sum(1 for w in filtered if w.get("amount_inr") is None)
    missing_billed = sum(1 for w in filtered if w.get("billed_value") is None)

    return {
        "total": total,
        "active_count": active_count,
        "completed_count": completed_count,
        "exec_status_breakdown": dict(exec_status_counts.most_common()),
        "wo_status_breakdown": dict(wo_status_counts.most_common()),
        "billing_status_breakdown": dict(billing_status_counts.most_common()),
        "collection_status_breakdown": dict(collection_status_counts.most_common()),
        "nature_of_work_breakdown": dict(nature_counts.most_common(10)),
        "type_of_work_breakdown": dict(type_counts.most_common(10)),
        "total_contract": total_contract,
        "total_contract_fmt": fmt_inr(total_contract),
        "total_billed": total_billed,
        "total_billed_fmt": fmt_inr(total_billed),
        "total_collected": total_collected,
        "total_collected_fmt": fmt_inr(total_collected),
        "total_receivable": total_receivable,
        "total_receivable_fmt": fmt_inr(total_receivable),
        "missing_amount_count": missing_amount,
        "missing_billed_count": missing_billed,
        "sector_filter": sector,
    }
