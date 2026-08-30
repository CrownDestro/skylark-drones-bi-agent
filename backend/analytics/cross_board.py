"""
Cross-board analytics: joins Deals and Work Orders on normalized sector
to provide unified pipeline vs execution comparison.
"""
from collections import defaultdict
from typing import Any, Dict, List

from backend.analytics.utils import fmt_inr, safe_sum
from backend.config import PROBABILITY_WEIGHTS


from backend.analytics.pipeline import _is_open

def cross_board_sector_analysis(
    deals: List[Dict],
    work_orders: List[Dict],
) -> Dict[str, Any]:
    """
    Compare pipeline (from Deals) vs execution/revenue (from Work Orders) by sector.

    Identifies:
    - High pipeline, low execution → conversion opportunity
    - Low pipeline, high execution → capacity risk
    - Balanced sectors
    """
    # Aggregate deals by sector
    deal_sectors: Dict[str, Dict] = defaultdict(lambda: {
        "pipeline": 0.0, "weighted_pipeline": 0.0, "deal_count": 0
    })
    for d in deals:
        if not _is_open(d):
            continue
        sec = d.get("sector") or "Unknown"
        v = d.get("deal_value") or 0
        prob = (d.get("closure_probability") or "").lower()
        weight = PROBABILITY_WEIGHTS.get(prob, PROBABILITY_WEIGHTS[""])
        deal_sectors[sec]["pipeline"] += v
        deal_sectors[sec]["weighted_pipeline"] += v * weight
        deal_sectors[sec]["deal_count"] += 1

    # Aggregate work orders by sector
    wo_sectors: Dict[str, Dict] = defaultdict(lambda: {
        "billed": 0.0, "collected": 0.0, "wo_count": 0, "contract": 0.0
    })
    for w in work_orders:
        sec = w.get("sector") or "Unknown"
        wo_sectors[sec]["billed"] += w.get("billed_value") or 0
        wo_sectors[sec]["collected"] += w.get("collected_amount") or 0
        wo_sectors[sec]["wo_count"] += 1
        wo_sectors[sec]["contract"] += w.get("amount_inr") or 0

    # Merge
    all_sectors = set(deal_sectors.keys()) | set(wo_sectors.keys())
    comparison = []
    for sec in sorted(all_sectors):
        d = deal_sectors.get(sec, {"pipeline": 0.0, "weighted_pipeline": 0.0, "deal_count": 0})
        w = wo_sectors.get(sec, {"billed": 0.0, "collected": 0.0, "wo_count": 0, "contract": 0.0})

        pipeline = d["pipeline"]
        billed = w["billed"]

        # Simple ratio for insight
        if pipeline > 0 and billed > 0:
            ratio = pipeline / billed
            if ratio > 3:
                insight = "High pipeline vs execution — strong sales opportunity, may need more delivery capacity"
            elif ratio < 0.5:
                insight = "Low pipeline vs execution — execution is outpacing new deals"
            else:
                insight = "Pipeline and execution appear balanced"
        elif pipeline > 0:
            insight = "Pipeline exists but no billed work orders in this sector yet"
        elif billed > 0:
            insight = "Active execution but limited new pipeline"
        else:
            insight = "No significant activity"

        comparison.append({
            "sector": sec,
            "pipeline": pipeline,
            "pipeline_fmt": fmt_inr(pipeline),
            "weighted_pipeline": d["weighted_pipeline"],
            "weighted_pipeline_fmt": fmt_inr(d["weighted_pipeline"]),
            "deal_count": d["deal_count"],
            "billed_value": billed,
            "billed_value_fmt": fmt_inr(billed),
            "collected": w["collected"],
            "collected_fmt": fmt_inr(w["collected"]),
            "wo_count": w["wo_count"],
            "insight": insight,
        })

    # Sort by pipeline desc
    comparison.sort(key=lambda x: x["pipeline"], reverse=True)

    return {
        "sectors": comparison,
        "total_sectors": len(comparison),
        "total_pipeline": sum(c["pipeline"] for c in comparison),
        "total_billed": sum(c["billed_value"] for c in comparison),
        "total_pipeline_fmt": fmt_inr(sum(c["pipeline"] for c in comparison)),
        "total_billed_fmt": fmt_inr(sum(c["billed_value"] for c in comparison)),
    }


def generate_leadership_update(
    deals: List[Dict],
    work_orders: List[Dict],
    deals_quality,
    wo_quality,
) -> Dict[str, Any]:
    """
    Generate a structured leadership update combining deals + work orders.
    """
    from backend.analytics.pipeline import calculate_pipeline
    from backend.analytics.revenue import calculate_revenue
    from backend.analytics.work_orders import analyze_work_orders

    pipeline_data = calculate_pipeline(deals, period="current_quarter")
    all_pipeline = calculate_pipeline(deals)
    revenue_data = calculate_revenue(work_orders)
    ops_data = analyze_work_orders(work_orders)
    cross_data = cross_board_sector_analysis(deals, work_orders)

    # Top sectors by pipeline
    top_sectors = sorted(
        cross_data["sectors"],
        key=lambda x: x["pipeline"],
        reverse=True,
    )[:3]

    # Risk flags
    risks = []
    if pipeline_data["missing_date_count"] > 0:
        risks.append(f"{pipeline_data['missing_date_count']} open deal(s) have no expected close date — forecasting confidence is reduced.")
    if pipeline_data["missing_value_count"] > 0:
        risks.append(f"{pipeline_data['missing_value_count']} open deal(s) have missing deal values.")
    if revenue_data["total_receivable"] and revenue_data["total_receivable"] > 0:
        risks.append(f"Outstanding receivables: {revenue_data['total_receivable_fmt']} — follow-up may be needed.")
    if revenue_data["missing_billed_count"] > 5:
        risks.append(f"{revenue_data['missing_billed_count']} work orders have no billed value on record.")

    # Collection rate insight
    collection_insight = None
    cr = revenue_data.get("collection_rate_pct")
    if cr is not None:
        if cr >= 80:
            collection_insight = f"Collection efficiency is strong at {cr:.0f}%."
        elif cr >= 60:
            collection_insight = f"Collection efficiency is moderate at {cr:.0f}% — receivables management may help."
        else:
            collection_insight = f"Collection efficiency is low at {cr:.0f}% — immediate receivables follow-up recommended."

    # Data quality caveats
    deal_caveats = deals_quality.to_caveats(threshold=3)
    wo_caveats = wo_quality.to_caveats(threshold=3)

    return {
        "pipeline": all_pipeline,          # All-time open pipeline (primary)
        "quarter_pipeline": pipeline_data,  # Current-quarter view (secondary context)
        "revenue": revenue_data,
        "operations": ops_data,
        "cross_board": cross_data,
        "top_sectors": top_sectors,
        "risks": risks,
        "collection_insight": collection_insight,
        "deal_caveats": deal_caveats,
        "wo_caveats": wo_caveats,
    }
