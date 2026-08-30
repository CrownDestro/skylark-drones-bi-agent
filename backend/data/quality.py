"""
Data quality checker: tracks missing/invalid fields and produces
human-readable caveats for the LLM response layer.
"""
from typing import Any, Dict, List, Optional, Tuple


class QualityReport:
    """Accumulates data quality issues for a dataset."""

    def __init__(self, dataset_name: str):
        self.dataset_name = dataset_name
        self.issues: List[Dict] = []
        self.total_records: int = 0
        self.records_with_issues: int = 0

    def record(self, field: str, count: int, description: str):
        if count > 0:
            self.issues.append({"field": field, "count": count, "description": description})

    def to_caveats(self, threshold: int = 1) -> List[str]:
        """Return only material caveats (count >= threshold)."""
        caveats = []
        for issue in self.issues:
            if issue["count"] >= threshold:
                caveats.append(issue["description"])
        return caveats

    def to_dict(self) -> Dict:
        return {
            "dataset": self.dataset_name,
            "total_records": self.total_records,
            "issues": self.issues,
        }


def check_deals_quality(deals: List[Dict]) -> QualityReport:
    """Run quality checks on normalized deals list."""
    report = QualityReport("Deals")
    report.total_records = len(deals)

    missing_value = sum(1 for d in deals if d.get("deal_value") is None)
    missing_close = sum(1 for d in deals if d.get("close_date") is None)
    missing_sector = sum(1 for d in deals if not d.get("sector"))
    missing_stage = sum(1 for d in deals if not d.get("deal_stage"))
    missing_prob = sum(1 for d in deals if not d.get("closure_probability"))
    missing_status = sum(1 for d in deals if not d.get("deal_status"))

    report.record("deal_value", missing_value,
                  f"{missing_value} deal(s) have missing deal values — pipeline total may be understated.")
    report.record("close_date", missing_close,
                  f"{missing_close} deal(s) have missing close dates — quarterly forecasting is affected.")
    report.record("sector", missing_sector,
                  f"{missing_sector} deal(s) have no sector assigned — sector analysis may be incomplete.")
    report.record("deal_stage", missing_stage,
                  f"{missing_stage} deal(s) have no stage information.")
    report.record("closure_probability", missing_prob,
                  f"{missing_prob} deal(s) have no closure probability — weighted pipeline uses default weight 0.30.")
    report.record("deal_status", missing_status,
                  f"{missing_status} deal(s) have no status — some filtering may exclude them.")

    # Count records with at least one issue
    report.records_with_issues = sum(
        1 for d in deals
        if any([
            d.get("deal_value") is None,
            d.get("close_date") is None,
            not d.get("sector"),
        ])
    )
    return report


def check_work_orders_quality(wos: List[Dict]) -> QualityReport:
    """Run quality checks on normalized work orders list."""
    report = QualityReport("Work Orders")
    report.total_records = len(wos)

    missing_amount = sum(1 for w in wos if w.get("amount_inr") is None)
    missing_billed = sum(1 for w in wos if w.get("billed_value") is None)
    missing_collected = sum(1 for w in wos if w.get("collected_amount") is None)
    missing_sector = sum(1 for w in wos if not w.get("sector"))
    missing_status = sum(1 for w in wos if not w.get("wo_status"))
    missing_start = sum(1 for w in wos if w.get("probable_start_date") is None)

    report.record("amount_inr", missing_amount,
                  f"{missing_amount} work order(s) have missing PO/contract amount.")
    report.record("billed_value", missing_billed,
                  f"{missing_billed} work order(s) have missing billed value — revenue may be understated.")
    report.record("collected_amount", missing_collected,
                  f"{missing_collected} work order(s) have missing collected amount — cash flow data is incomplete.")
    report.record("sector", missing_sector,
                  f"{missing_sector} work order(s) have no sector — sector performance may be incomplete.")
    report.record("wo_status", missing_status,
                  f"{missing_status} work order(s) have no status.")
    report.record("probable_start_date", missing_start,
                  f"{missing_start} work order(s) have no probable start date.")

    report.records_with_issues = sum(
        1 for w in wos
        if any([
            w.get("billed_value") is None,
            w.get("collected_amount") is None,
            not w.get("sector"),
        ])
    )
    return report
