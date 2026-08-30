"""
Diagnostic script: verifies Monday.com board schemas and sample data.
Token is read from .env / environment — never hardcoded here.
"""
import os
import sys
sys.path.insert(0, ".")

# Load .env
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.environ.get("MONDAY_API_TOKEN", "")
if not TOKEN:
    print("ERROR: MONDAY_API_TOKEN not set in .env or environment")
    sys.exit(1)

import httpx

DEALS = os.environ.get("DEALS_BOARD_ID", "5030966894")
WOS = os.environ.get("WORK_ORDERS_BOARD_ID", "5030966898")

headers = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2023-10",
}


def q(gql, variables=None):
    payload = {"query": gql}
    if variables:
        payload["variables"] = variables
    r = httpx.post("https://api.monday.com/v2", headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("data", {})


GQL_COLS = """
query ($b: ID!) {
    boards(ids: [$b]) {
        name
        columns { id title type }
    }
}
"""

GQL_ITEMS = """
query ($b: ID!) {
    boards(ids: [$b]) {
        items_page(limit: 3) {
            items {
                id name
                column_values {
                    id text value
                    column { title type }
                }
            }
        }
    }
}
"""


def print_columns(board_id, label):
    print(f"\n=== {label} COLUMNS ===")
    data = q(GQL_COLS, {"b": board_id})
    board = data.get("boards", [{}])[0]
    print("Board:", board.get("name"))
    for col in board.get("columns", []):
        print(f"  {col['id']:35s} | {col['title']:50s} | {col['type']}")


def print_sample(board_id, label):
    print(f"\n=== {label} SAMPLE ITEMS ===")
    data = q(GQL_ITEMS, {"b": board_id})
    items = data.get("boards", [{}])[0].get("items_page", {}).get("items", [])
    for item in items:
        print(f"\nItem: {item['name']} (id={item['id']})")
        for cv in item.get("column_values", []):
            if cv.get("text"):
                print(f"  [{cv['column']['title']}] = {cv['text'][:80]}")


print_columns(DEALS, "DEALS")
print_sample(DEALS, "DEALS")
print_columns(WOS, "WORK ORDERS")
print_sample(WOS, "WORK ORDERS")
print("\nDone!")
