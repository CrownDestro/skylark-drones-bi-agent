import asyncio
from backend.agent.agent import BIAgent

async def get_sectors():
    agent = BIAgent()
    deals, wos = agent._load_data()
    
    deal_sectors = set(d.get("sector") for d in deals if d.get("sector"))
    wo_sectors = set(w.get("sector") for w in wos if w.get("sector"))
    
    print("Deals Sectors:", deal_sectors)
    print("Work Orders Sectors:", wo_sectors)
    
if __name__ == "__main__":
    asyncio.run(get_sectors())
