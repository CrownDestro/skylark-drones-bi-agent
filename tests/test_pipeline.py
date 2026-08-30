"""Test the full data pipeline end-to-end."""
import sys
sys.path.insert(0, '.')
from backend.monday.boards import fetch_deals, fetch_work_orders
from backend.data.normalizer import normalize_deals, normalize_work_orders
from backend.data.quality import check_deals_quality, check_work_orders_quality

print('Fetching deals...')
raw_deals = fetch_deals()
deals = normalize_deals(raw_deals)
print(f'Got {len(deals)} deals')

print('Fetching work orders...')
raw_wos = fetch_work_orders()
wos = normalize_work_orders(raw_wos)
print(f'Got {len(wos)} work orders')

# Quality
dq = check_deals_quality(deals)
wq = check_work_orders_quality(wos)

print()
print('=== DEALS QUALITY ===')
print('Total:', dq.total_records)
for issue in dq.issues:
    print(f'  {issue["field"]}: {issue["count"]}')
    print(f'    {issue["description"]}')

print()
print('=== SAMPLE DEAL (normalized) ===')
for d in deals[:2]:
    print({k:v for k,v in d.items() if k != '__raw'})

print()
print('=== WORK ORDERS QUALITY ===')
print('Total:', wq.total_records)
for issue in wq.issues:
    print(f'  {issue["field"]}: {issue["count"]}')

print()
print('=== PIPELINE TEST ===')
from backend.analytics.pipeline import calculate_pipeline
result = calculate_pipeline(deals)
print('Open deals:', result['open_deal_count'])
print('Total pipeline:', result['total_pipeline_fmt'])
print('Weighted:', result['weighted_pipeline_fmt'])
print('Won:', result['won_value_fmt'])
print('Missing values:', result['missing_value_count'])
print('Missing dates:', result['missing_date_count'])

print()
print('=== SECTOR BREAKDOWN ===')
for sector, info in sorted(result['sector_breakdown'].items(), key=lambda x: x[1]['value'], reverse=True):
    print(f'  {sector}: {info["count"]} deals, value: {info["value"]:,.0f}')

print()
print('=== REVENUE TEST ===')
from backend.analytics.revenue import calculate_revenue
rev = calculate_revenue(wos)
print('Total contract:', rev['total_contract_fmt'])
print('Total billed:', rev['total_billed_fmt'])
print('Total collected:', rev['total_collected_fmt'])
print('Receivables:', rev['total_receivable_fmt'])
print('Collection rate:', rev['collection_rate_pct'])

print()
print('All tests passed!')
