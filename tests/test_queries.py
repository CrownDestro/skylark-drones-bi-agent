import asyncio
import os
import sys

from backend.agent.agent import BIAgent

queries = [
    "What is our total pipeline?",
    "What are our biggest open deals?",
    "How much have we billed?",
    "How much have we collected?",
    "How much is outstanding?",
    "Which sector has the strongest pipeline?",
    "How are our work orders performing?",
    "Which sectors have strong pipeline but weak execution?",
    "Prepare a leadership update for this quarter.",
    "How is the business doing?",
    "How reliable is our current forecast?",
    "What data did you use to answer this?",
    "How is our Energy pipeline looking?",
    "What is our Renewables pipeline?",
    "What is our Powerline pipeline?",
]

async def test_all():
    agent = BIAgent()
    # Force initial load
    print("Loading data...")
    agent._load_data()
    print("Data loaded.")
    
    for i, q in enumerate(queries, 1):
        print(f"\n{'='*50}")
        print(f"Test {i}: {q}")
        print(f"{'='*50}")
        try:
            res = agent.chat(q, [])
            print(f"Intent: {res.get('intent')}")
            print(f"Sector: {res.get('sector')}")
            print(f"\nResponse:\n{res.get('response')}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_all())
