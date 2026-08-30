"""Quick Gemini SDK connectivity test."""
import sys, os, warnings
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
load_dotenv()
key = os.environ.get("GEMINI_API_KEY", "")
print(f"Key prefix: {key[:15]}...")

from google import genai

client = genai.Client(api_key=key)

models_to_try = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-3.6-flash",
]

print("\nTesting models...")
for model in models_to_try:
    try:
        resp = client.models.generate_content(
            model=model,
            contents="Reply with: Hello from Skylark BI"
        )
        text = resp.text if hasattr(resp, "text") else str(resp)
        print(f"  OK  [{model}]: {text[:60].strip()}")
        break
    except Exception as e:
        err = str(e)[:100]
        print(f"  FAIL [{model}]: {err}")
