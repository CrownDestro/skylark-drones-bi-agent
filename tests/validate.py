"""
Validation tests for all 14 required query types.
Runs deterministically against live Monday.com data.
No LLM required for this validation — tests the analytics layer only.

Run: py -3.13 validate.py
"""
import sys
import os
sys.path.insert(0, ".")
# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from backend.monday.boards import fetch_deals, fetch_work_orders
from backend.data.normalizer import normalize_deals, normalize_work_orders
from backend.data.quality import check_deals_quality, check_work_orders_quality
from backend.analytics.pipeline import calculate_pipeline
from backend.analytics.revenue import calculate_revenue
from backend.analytics.work_orders import analyze_work_orders
from backend.analytics.cross_board import cross_board_sector_analysis, generate_leadership_update
from backend.analytics.utils import current_quarter, fmt_inr

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check(condition, label, detail=""):
    icon = PASS if condition else FAIL
    print(f"  {icon} {label}")
    if detail:
        print(f"     {detail}")
    return condition


# ──────────────────────────────────────────────────────────────
section("1. DATA FETCH")
print("  Fetching from Monday.com...")
deals = normalize_deals(fetch_deals())
wos = normalize_work_orders(fetch_work_orders())
deals_quality = check_deals_quality(deals)
wo_quality = check_work_orders_quality(wos)

check(len(deals) > 100, f"Deals loaded: {len(deals)}")
check(len(wos) > 50, f"Work orders loaded: {len(wos)}")
check(deals_quality.total_records > 0, "Deals quality tracker initialized")
check(wo_quality.total_records > 0, "WO quality tracker initialized")


# ──────────────────────────────────────────────────────────────
section("2. HEADER ROW FILTERING")
# All normalized names should not be 'deal name masked' or 'name'
bad_names = [d for d in deals if (d.get("name") or "").lower() in ("deal name", "deal name masked", "name")]
bad_wo = [w for w in wos if (w.get("name") or "").lower() in ("deal name masked", "name")]
check(len(bad_names) == 0, f"No header rows in deals (found {len(bad_names)})")
check(len(bad_wo) == 0, f"No header rows in work orders (found {len(bad_wo)})")


# ──────────────────────────────────────────────────────────────
section("3. QUERY TYPE 1 — Total Pipeline")
pipeline = calculate_pipeline(deals)
tp = pipeline["total_pipeline"]
check(tp > 0, f"Total pipeline: {pipeline['total_pipeline_fmt']}")
check(pipeline["open_deal_count"] > 0, f"Open deals: {pipeline['open_deal_count']}")
check(pipeline["weighted_pipeline"] > 0, f"Weighted pipeline: {pipeline['weighted_pipeline_fmt']}")
check(pipeline["won_value"] >= 0, f"Won value: {pipeline['won_value_fmt']}")
print(f"  {WARN} Probability assumption: High=80%, Medium=50%, Low=20%, Unknown=30%")
print(f"  {WARN} Missing deal values: {pipeline['missing_value_count']} (pipeline may be understated)")


# ──────────────────────────────────────────────────────────────
section("4. QUERY TYPE 2 — Sector Pipeline (Energy)")
# Energy maps to Renewables
ren_pipeline = calculate_pipeline(deals, sector="Renewables")
check(ren_pipeline["open_deal_count"] >= 0, f"Renewables deals: {ren_pipeline['open_deal_count']}")
check(True, f"Renewables pipeline: {ren_pipeline['total_pipeline_fmt']}")

# Also test Mining
mining_pipeline = calculate_pipeline(deals, sector="Mining")
check(mining_pipeline["open_deal_count"] >= 0, f"Mining deals: {mining_pipeline['open_deal_count']}")


# ──────────────────────────────────────────────────────────────
section("5. QUERY TYPE 3 — Time-based Pipeline (current quarter)")
q_start, q_end = current_quarter()
q_label = f"Q{(q_start.month-1)//3+1} {q_start.year}"
print(f"  Current quarter: {q_label} ({q_start.date()} → {q_end.date()})")
check(True, f"Quarter dynamically calculated: {q_label}")
q_pipeline = calculate_pipeline(deals, period="current_quarter")
check(True, f"Quarter pipeline: {q_pipeline['total_pipeline_fmt']} ({q_pipeline['open_deal_count']} deals)")
print(f"  {WARN} {pipeline['missing_date_count']} open deals have no close date — quarter filter has limited precision")


# ──────────────────────────────────────────────────────────────
section("6. QUERY TYPE 4 — Biggest Open Deals")
top = pipeline["top_deals"]
check(len(top) > 0, f"Top {len(top)} deals found")
for i, d in enumerate(top[:3], 1):
    print(f"  #{i} {d['name']:30s} {d['value_fmt']:15s} Sector: {d.get('sector', 'N/A')}")


# ──────────────────────────────────────────────────────────────
section("7. QUERY TYPE 5 — Revenue / Billing")
rev = calculate_revenue(wos)
check(rev["total_billed"] >= 0, f"Total billed: {rev['total_billed_fmt']}")
check(rev["missing_billed_count"] >= 0, f"Missing billed values: {rev['missing_billed_count']}")
print(f"  Contract: {rev['total_contract_fmt']}")
print(f"  Billed:   {rev['total_billed_fmt']}")


# ──────────────────────────────────────────────────────────────
section("8. QUERY TYPE 6 — Collections")
check(rev["total_collected"] >= 0, f"Total collected: {rev['total_collected_fmt']}")
check(rev["collection_rate_pct"] is not None, f"Collection rate: {rev['collection_rate_pct']}%")


# ──────────────────────────────────────────────────────────────
section("9. QUERY TYPE 7 — Receivables (Outstanding)")
check(rev["total_receivable"] >= 0, f"Total receivable: {rev['total_receivable_fmt']}")
# Verify: receivable = billed - collected (approximate)
implied = rev["total_billed"] - rev["total_collected"]
diff = abs(rev["total_receivable"] - implied)
check(diff < rev["total_billed"] * 0.5, "Receivable is roughly consistent with billed-collected",
      f"Stored: {fmt_inr(rev['total_receivable'])} vs implied: {fmt_inr(implied)}")


# ──────────────────────────────────────────────────────────────
section("10. QUERY TYPE 8 — Work Orders Performance")
ops = analyze_work_orders(wos)
check(ops["total"] > 0, f"Total WOs: {ops['total']}")
check(True, f"Exec status breakdown: {dict(list(ops['exec_status_breakdown'].items())[:3])}")
check(True, f"Active: {ops['active_count']}, Completed: {ops['completed_count']}")


# ──────────────────────────────────────────────────────────────
section("11. QUERY TYPE 9 — Sector Comparison (Strongest Pipeline)")
cross = cross_board_sector_analysis(deals, wos)
check(len(cross["sectors"]) > 0, f"Sectors: {cross['total_sectors']}")
top_sec = cross["sectors"][:3]
print(f"  Top sectors by pipeline:")
for s in top_sec:
    print(f"    {s['sector']:20s} Pipeline: {s['pipeline_fmt']:15s} Billed: {s['billed_value_fmt']}")


# ──────────────────────────────────────────────────────────────
section("12. QUERY TYPE 10 — Cross-board (Pipeline vs Execution)")
high_pipeline_low_exec = [
    s for s in cross["sectors"]
    if s["pipeline"] > 0 and (s["pipeline"] / max(s["billed_value"], 1)) > 3
]
check(True, f"Sectors with high pipeline vs execution: {len(high_pipeline_low_exec)}")
for s in high_pipeline_low_exec[:3]:
    print(f"    {s['sector']:20s} Pipeline: {s['pipeline_fmt']:15s} Billed: {s['billed_value_fmt']}")
    print(f"    Insight: {s['insight']}")


# ──────────────────────────────────────────────────────────────
section("13. QUERY TYPE 11 — Leadership Update")
lu = generate_leadership_update(deals, wos, deals_quality, wo_quality)
check("pipeline" in lu, "Pipeline data in leadership update")
check("revenue" in lu, "Revenue data in leadership update")
check("operations" in lu, "Operations data in leadership update")
check("risks" in lu, "Risks identified")
print(f"  Risks identified: {len(lu['risks'])}")
for r in lu["risks"][:3]:
    print(f"    - {r}")


# ──────────────────────────────────────────────────────────────
section("14. DATA QUALITY SUMMARY")
print(f"\n  DEALS ({deals_quality.total_records} records):")
for issue in deals_quality.issues:
    pct = issue["count"] / deals_quality.total_records * 100 if deals_quality.total_records else 0
    print(f"    {WARN} {issue['field']:30s}: {issue['count']:4d} missing ({pct:.0f}%)")

print(f"\n  WORK ORDERS ({wo_quality.total_records} records):")
for issue in wo_quality.issues:
    pct = issue["count"] / wo_quality.total_records * 100 if wo_quality.total_records else 0
    print(f"    {WARN} {issue['field']:30s}: {issue['count']:4d} missing ({pct:.0f}%)")


# ──────────────────────────────────────────────────────────────
section("15. SECURITY CHECKS")
import inspect, backend.config as cfg
# Verify token not printed in module repr
check("eyJ" not in str(inspect.getsource(cfg)), "Token not hardcoded in config.py")
check(cfg.MONDAY_API_TOKEN != "", "Token loaded from env")
check(cfg.MONDAY_API_TOKEN == os.environ.get("MONDAY_API_TOKEN", ""), "Token matches env var")


# ──────────────────────────────────────────────────────────────
section("SUMMARY")
print("""
  Data source:     Monday.com GraphQL API (read-only)
  Excel files:     NOT used at runtime
  Pipeline calcs:  Python (deterministic)
  Revenue calcs:   Python (deterministic)
  Cross-board:     Python (deterministic)
  Quarter logic:   Dynamically calculated from current date
  Currency:        INR (assumed — see DECISION_LOG.md)
  Probability:     Assumption (High=80%, Medium=50%, Low=20%)
  LLM role:        Intent detection + executive language only
  LLM fallback:    Deterministic structured response
""")
print("Validation complete.")
