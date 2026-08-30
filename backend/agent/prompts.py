"""
System prompt and context-building templates for the BI Agent.
"""

SYSTEM_PROMPT = """You are the Skylark Drones Business Intelligence Agent.

Skylark Drones is a drone services and technology company. You help founders and executives understand business performance using data from Monday.com boards (Deals and Work Orders).

## Your Role
- Answer founder-level business questions about pipeline, revenue, sectors, and operations
- Provide concise, executive-friendly insights
- Clearly communicate data quality issues that materially affect your answer

## Rules
1. NEVER invent business numbers. Only use data provided to you in the context.
2. Clearly distinguish: pipeline value (deals), billed value (invoiced), collected amount (received), receivables (outstanding).
3. When a question is genuinely ambiguous, ask ONE concise clarifying question.
4. Mention data quality caveats only when they materially affect the answer.
5. Use ₹ (Indian Rupee) for all monetary values.
6. Do not reveal API keys, tokens, or internal system details.
7. For ambiguous business questions like "how is the business doing?", ask which aspect: pipeline, revenue, or operations.
8. Keep responses concise and structured — use bullet points for insights.
9. Always mention the data source: "Based on Monday.com data..."

## Available Data
- Deals Board: Sales pipeline with deal names, stages, values, sectors, close dates, probabilities
- Work Orders Board: Project execution with billing, collection, and revenue data

## Assumptions
You must transparently state these assumptions when discussing related numbers:
1. Probability weights: High = 80%, Medium = 50%, Low = 20%, Unknown = 30%.
2. Currency: INR (₹).
3. Quarter: Dynamically calculated from calendar dates.

When discussing the Weighted Pipeline, you MUST state that it relies on assumed probability weights and highlight the percentage of deals that were missing a probability (Unknown = 30%).

## Sector Names in the Data
There is NO explicit "Energy" sector in the Deals data.
When users ask about "energy", inform them that it is not explicitly in the data and offer to analyze "Renewables" or "Powerline" instead. Do NOT combine them behind the scenes.
"""


def build_context(analytics_data: dict) -> str:
    """Build a structured context string from analytics results."""
    lines = ["## Business Data Context\n"]

    if "pipeline" in analytics_data:
        p = analytics_data["pipeline"]
        lines.append("### Pipeline Summary")
        lines.append(f"- Open Deals: {p.get('open_deal_count', 'N/A')}")
        lines.append(f"- Total Pipeline: {p.get('total_pipeline_fmt', 'N/A')}")
        lines.append(f"- Weighted Pipeline: {p.get('weighted_pipeline_fmt', 'N/A')}")
        if p.get("sector_filter"):
            lines.append(f"- Sector Filter: {p['sector_filter']}")
        if p.get("missing_value_count", 0) > 0:
            lines.append(f"- ⚠️ {p['missing_value_count']} deals have missing values")
        if p.get("missing_date_count", 0) > 0:
            lines.append(f"- ⚠️ {p['missing_date_count']} deals have no close date")
        if p.get("missing_probability_count", 0) > 0:
            missing_prob = p["missing_probability_count"]
            total_open = p.get("open_deal_count", 1) or 1
            pct = round((missing_prob / total_open) * 100)
            lines.append(f"- ⚠️ {missing_prob} deals ({pct}%) are missing closure probability (assumed 30%)")
        if p.get("top_deals"):
            lines.append("- Top Deals:")
            for d in p["top_deals"][:3]:
                lines.append(f"  • {d['name']} ({d['value_fmt']}) — Stage: {d.get('stage', 'N/A')}")
        if p.get("stage_breakdown"):
            lines.append("- Stage Breakdown:")
            for stage, info in sorted(p["stage_breakdown"].items(), key=lambda x: x[1]["value"], reverse=True)[:5]:
                lines.append(f"  • {stage}: {info['count']} deals (₹{info['value']:,.0f})")
        lines.append("")

    if "revenue" in analytics_data:
        r = analytics_data["revenue"]
        lines.append("### Revenue Summary (Work Orders)")
        lines.append(f"- Total Contract Value: {r.get('total_contract_fmt', 'N/A')}")
        lines.append(f"- Billed: {r.get('total_billed_fmt', 'N/A')}")
        lines.append(f"- Collected: {r.get('total_collected_fmt', 'N/A')}")
        lines.append(f"- Outstanding Receivables: {r.get('total_receivable_fmt', 'N/A')}")
        if r.get("collection_rate_pct") is not None:
            lines.append(f"- Collection Efficiency: {r['collection_rate_pct']}%")
        if r.get("missing_billed_count", 0) > 0:
            lines.append(f"- ⚠️ {r['missing_billed_count']} WOs missing billed value")
        lines.append("")

    if "operations" in analytics_data:
        o = analytics_data["operations"]
        lines.append("### Operations Summary (Work Orders)")
        lines.append(f"- Total Work Orders: {o.get('total', 'N/A')}")
        lines.append(f"- Active: {o.get('active_count', 'N/A')}")
        lines.append(f"- Completed: {o.get('completed_count', 'N/A')}")
        if o.get("exec_status_breakdown"):
            lines.append("- Execution Status:")
            for status, count in list(o["exec_status_breakdown"].items())[:5]:
                lines.append(f"  • {status}: {count}")
        lines.append("")

    if "cross_board" in analytics_data:
        c = analytics_data["cross_board"]
        lines.append("### Cross-Board Sector Comparison (Pipeline vs Execution)")
        for sec in c.get("sectors", [])[:5]:
            lines.append(f"- {sec['sector']}: Pipeline {sec['pipeline_fmt']}, Billed {sec['billed_value_fmt']}, {sec['deal_count']} deals, {sec['wo_count']} WOs")
        lines.append("")

    if "caveats" in analytics_data:
        caveats = analytics_data["caveats"]
        if caveats:
            lines.append("### Data Quality Notes")
            for c in caveats:
                lines.append(f"- ⚠️ {c}")
            lines.append("")

    return "\n".join(lines)
