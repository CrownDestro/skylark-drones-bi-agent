"""Targeted tests for the 3 previously-failing queries."""
import sys, httpx
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8001"

queries = [
    ("What is our total pipeline?", "pipeline_analysis"),
    ("Which sector has the strongest pipeline?", "sector_analysis"),
    ("Prepare a leadership update for this quarter.", "leadership_update"),
]

for i, (msg, expected) in enumerate(queries, 1):
    print(f"--- {msg}")
    try:
        r = httpx.post(f"{BASE}/chat", json={"message": msg, "history": []}, timeout=120)
        if r.status_code == 200:
            d = r.json()
            got = d.get("intent", "?")
            ok = "OK" if got == expected else "MISMATCH"
            print(f"  [{ok}] Intent: {got}")
            print(f"  Sources: {', '.join(d.get('sources', []))}")
            resp = (d.get("response") or "")[:300].strip().replace("\n", " ")
            print(f"  Response: {resp}")
        else:
            print(f"  [FAIL] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [ERROR] {e}")
    print()
