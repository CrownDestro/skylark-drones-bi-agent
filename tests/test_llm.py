"""Test Gemini LLM integration on the live server."""
import sys, httpx
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000"

print("=== LLM Integration Test ===\n")
r = httpx.get(f"{BASE}/health", timeout=5)
print("Health:", r.json())
print()

# Test a query that benefits most from LLM natural language
queries = [
    "What is our total pipeline?",
    "Which sectors have strong pipeline but weak execution?",
    "Prepare a leadership update for this quarter.",
]

for msg in queries:
    print(f"Q: {msg}")
    try:
        r = httpx.post(f"{BASE}/chat", json={"message": msg, "history": []}, timeout=120)
        if r.status_code == 200:
            d = r.json()
            resp = (d.get("response") or "")
            # Check if response looks like Gemini (longer, more natural) vs deterministic (starts with emoji header)
            is_deterministic = resp.startswith("📊 **Skylark Drones")
            llm_label = "DETERMINISTIC FALLBACK" if is_deterministic else "LLM RESPONSE"
            print(f"  [{llm_label}]")
            print(f"  Intent: {d.get('intent')}")
            print(f"  Sources: {', '.join(d.get('sources', []))}")
            print(f"  Response preview ({len(resp)} chars):")
            print(f"  {resp[:250].strip().replace(chr(10), ' ')}")
        else:
            print(f"  HTTP {r.status_code}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()
