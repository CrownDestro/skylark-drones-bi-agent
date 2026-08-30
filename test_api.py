"""Test all 14 required queries via the live API."""
import sys, httpx
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000"

r = httpx.get(f"{BASE}/health", timeout=5)
print("Health:", r.json())
print()

queries = [
    ("What is our total pipeline?", "pipeline_analysis"),
    ("How is the energy sector pipeline looking?", "pipeline_analysis"),
    ("How is our energy pipeline this quarter?", "pipeline_analysis"),
    ("What are our biggest open deals?", "deals_analysis"),
    ("How much have we billed?", "revenue_analysis"),
    ("How much have we collected?", "revenue_analysis"),
    ("How much is outstanding?", "revenue_analysis"),
    ("How are our work orders performing?", "work_order_analysis"),
    ("Which sector has the strongest pipeline?", "sector_analysis"),
    ("Which sectors have strong pipeline but weak execution?", "cross_board_analysis"),
    ("Prepare a leadership update for this quarter.", "leadership_update"),
    ("How is the business doing?", "ambiguous_business"),
    ("How reliable is our pipeline forecast?", "forecast_reliability"),
    ("What data did you use to answer this?", "data_provenance"),
]

passed = 0
failed = 0
for i, (msg, expected) in enumerate(queries, 1):
    label = msg[:55] + "..." if len(msg) > 55 else msg
    print(f"--- Q{i}: {label}")
    try:
        r = httpx.post(
            f"{BASE}/chat",
            json={"message": msg, "history": []},
            timeout=90,
        )
        if r.status_code == 200:
            d = r.json()
            got = d.get("intent", "?")
            ok = "OK" if got == expected else "WARN"
            srcs = ", ".join(d.get("sources", []))
            resp = (d.get("response") or "")[:120].strip().replace("\n", " ")
            print(f"  [{ok}] Intent: {got} (expected: {expected})")
            print(f"  Sources: {srcs or 'none'}")
            print(f"  Preview: {resp}")
            if ok == "OK":
                passed += 1
            else:
                failed += 1
        else:
            print(f"  [FAIL] HTTP {r.status_code}: {r.text[:100]}")
            failed += 1
    except Exception as e:
        print(f"  [ERROR] {e}")
        failed += 1
    print()

print(f"Results: {passed} passed / {failed} intent mismatches / {len(queries)} total")
