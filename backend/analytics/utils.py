"""
Analytics helpers shared across modules.
"""
from datetime import datetime
from typing import Optional, Tuple


def current_quarter() -> Tuple[datetime, datetime]:
    """Return (start, end) datetimes for the current calendar quarter."""
    now = datetime.now()
    q = (now.month - 1) // 3  # 0-indexed quarter
    q_start_month = q * 3 + 1
    q_end_month = q_start_month + 2
    q_start = datetime(now.year, q_start_month, 1)
    if q_end_month == 12:
        q_end = datetime(now.year, 12, 31, 23, 59, 59)
    else:
        next_q_start = datetime(now.year, q_end_month + 1, 1)
        from datetime import timedelta
        q_end = next_q_start - timedelta(seconds=1)
    return q_start, q_end


def fmt_inr(amount: Optional[float]) -> str:
    """Format a number as INR with Cr/L shorthand."""
    if amount is None:
        return "N/A"
    if abs(amount) >= 1e7:
        return f"₹{amount/1e7:.2f} Cr"
    if abs(amount) >= 1e5:
        return f"₹{amount/1e5:.2f} L"
    return f"₹{amount:,.0f}"


def safe_sum(values) -> float:
    """Sum non-None values."""
    return sum(v for v in values if v is not None)
