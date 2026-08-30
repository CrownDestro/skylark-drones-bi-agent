"""
Data normalizer: cleans dates, sectors, statuses, monetary values, and text fields.
Preserves original raw values under __raw_ prefix for auditability.
"""
import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Sector normalization map ───────────────────────────────────────────────
SECTOR_ALIASES: Dict[str, str] = {
    "energy": "Energy",
    "energy sector": "Energy",
    "energysector": "Energy",
    "power": "Energy",
    "oil & gas": "Energy",
    "oil and gas": "Energy",

    "infrastructure": "Infrastructure",
    "infra": "Infrastructure",
    "infrastructure sector": "Infrastructure",

    "agriculture": "Agriculture",
    "agri": "Agriculture",
    "agri sector": "Agriculture",
    "farming": "Agriculture",

    "mining": "Mining",
    "mines": "Mining",
    "mining sector": "Mining",

    "construction": "Construction",
    "real estate": "Construction",
    "realestate": "Construction",

    "telecom": "Telecom",
    "telecommunications": "Telecom",

    "government": "Government",
    "govt": "Government",
    "gov": "Government",
    "public sector": "Government",

    "defence": "Defence",
    "defense": "Defence",

    "forestry": "Forestry",
    "forest": "Forestry",

    "utilities": "Utilities",
    "utility": "Utilities",

    "survey": "Survey",
    "surveying": "Survey",

    "smart cities": "Smart Cities",
    "smartcities": "Smart Cities",
    "smart city": "Smart Cities",

    "logistics": "Logistics",
    "transport": "Logistics",

    "industrial": "Industrial",
}

# ─── Status normalization ────────────────────────────────────────────────────
STATUS_ALIASES: Dict[str, str] = {
    "won": "Won",
    "closed won": "Won",
    "closed_won": "Won",
    "loss": "Lost",
    "lost": "Lost",
    "closed lost": "Lost",
    "closed_lost": "Lost",
    "in progress": "In Progress",
    "inprogress": "In Progress",
    "active": "Active",
    "open": "Open",
    "new": "New",
    "qualified": "Qualified",
    "proposal sent": "Proposal Sent",
    "proposal": "Proposal Sent",
    "negotiation": "Negotiation",
    "negotiating": "Negotiation",
    "pending": "Pending",
    "on hold": "On Hold",
    "onhold": "On Hold",
    "cancelled": "Cancelled",
    "canceled": "Cancelled",
    "completed": "Completed",
    "done": "Completed",
}

# ─── Probability normalization ────────────────────────────────────────────────
PROBABILITY_ALIASES: Dict[str, str] = {
    "high": "High",
    "hi": "High",
    "h": "High",
    "medium": "Medium",
    "med": "Medium",
    "m": "Medium",
    "low": "Low",
    "lo": "Low",
    "l": "Low",
}


def _clean_str(v: Any) -> Optional[str]:
    """Return a stripped, non-empty string or None."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def normalize_sector(raw: Any) -> Optional[str]:
    """Normalize sector/service string to canonical form."""
    s = _clean_str(raw)
    if not s:
        return None
    key = s.lower().strip()
    return SECTOR_ALIASES.get(key, s.title())  # title-case unknown sectors


def normalize_status(raw: Any) -> Optional[str]:
    """Normalize deal/WO status string."""
    s = _clean_str(raw)
    if not s:
        return None
    key = s.lower().strip()
    return STATUS_ALIASES.get(key, s.title())


def normalize_probability(raw: Any) -> Optional[str]:
    """Normalize closure probability to High/Medium/Low."""
    s = _clean_str(raw)
    if not s:
        return None
    key = s.lower().strip()
    return PROBABILITY_ALIASES.get(key, s.title())


def normalize_date(raw: Any) -> Optional[datetime]:
    """
    Try multiple date formats. Returns datetime or None.
    Invalid/empty dates recorded as None (tracked separately by quality module).
    """
    s = _clean_str(raw)
    if not s or s.lower() in ("none", "null", "n/a", "na", "-", "tbd"):
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d.%m.%Y",
        "%m-%d-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    # Fallback: try dateutil if available
    try:
        from dateutil import parser as du_parser  # type: ignore
        return du_parser.parse(s, dayfirst=True)
    except Exception:
        pass

    logger.debug("Could not parse date: %r", raw)
    return None


def normalize_number(raw: Any) -> Optional[float]:
    """
    Parse numeric/monetary values. Handles commas, currency symbols, etc.
    Returns None for truly missing values (not zero).
    """
    s = _clean_str(raw)
    if not s or s.lower() in ("none", "null", "n/a", "na", "-", ""):
        return None
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[₹$€£,\s]", "", s)
    # Handle lakh/crore text (e.g. "1.5L", "2Cr")
    cleaned = cleaned.replace("L", "e5").replace("Cr", "e7").replace("K", "e3")
    try:
        return float(cleaned)
    except ValueError:
        logger.debug("Could not parse number: %r", raw)
        return None


def normalize_deal(raw_deal: Dict) -> Dict:
    """
    Normalize a raw deal dict from Monday.
    Keys are generated from column titles by boards.py (lowercased, spaces→underscores).
    Actual Monday column titles for Deals board:
      name, owner_code, client_code, deal_status, close_date_a, closure_probability,
      masked_deal_value, tentative_close_date, deal_stage, product_deal, sector/service, created_date
    Returns a new dict with cleaned fields and __raw originals.
    """
    d = dict(raw_deal)

    def get(key_patterns, normalize_fn=None):
        for pat in key_patterns:
            v = d.get(pat)
            if v is not None:
                return normalize_fn(v) if normalize_fn else v
        return None

    # Skip header rows (Monday sometimes imports the header row as an item)
    name_val = _clean_str(d.get("name")) or ""
    if name_val.lower() in ("deal name", "deal name masked", "name"):
        return None  # Signal to filter out

    norm: Dict = {
        "id": d.get("id"),
        "name": name_val or "Unknown Deal",

        # Owner / client — exact Monday title keys
        "owner_code": _clean_str(get(["owner_code", "owner", "bd_code"])),
        "client_code": _clean_str(get(["client_code", "client"])),

        # Status / stage — exact Monday title keys
        "deal_status": normalize_status(get(["deal_status", "status"])),
        "deal_stage": normalize_status(get(["deal_stage", "stage"])),
        "closure_probability": normalize_probability(get(["closure_probability"])),

        # Monetary — exact Monday column: "masked_deal_value"
        "deal_value": normalize_number(get(["masked_deal_value", "deal_value", "value"])),

        # Sector — exact Monday column: "sector/service" → key becomes "sector_service"
        "sector": normalize_sector(get(["sector_service", "sector/service", "sector", "service"])),
        "product": _clean_str(get(["product_deal", "product"])),

        # Dates — exact Monday columns
        "close_date": normalize_date(get(["close_date_a", "close_date"])),
        "tentative_close_date": normalize_date(get(["tentative_close_date"])),
        "created_date": normalize_date(get(["created_date"])),

        "__raw": {k: v for k, v in d.items() if not k.startswith("__type_")},
    }

    return norm


def normalize_work_order(raw_wo: Dict) -> Dict:
    """
    Normalize a raw work order dict from Monday.
    Column keys are generated by boards.py from actual Monday column titles.
    Actual key patterns based on Monday board schema:
      customer_name_code, serial_#, nature_of_work, execution_status,
      amount_in_rupees_excl_of_gst_masked, billed_value_in_rupees_incl_of_gst_masked,
      collected_amount_in_rupees_incl_of_gst_masked, amount_receivable_masked,
      wo_status_billed, billing_status, invoice_status, collection_status, sector
    """
    d = dict(raw_wo)

    def get(key_patterns, normalize_fn=None):
        for pat in key_patterns:
            v = d.get(pat)
            if v is not None:
                return normalize_fn(v) if normalize_fn else v
        return None

    # Skip header rows
    name_val = _clean_str(d.get("name")) or ""
    if name_val.lower() in ("deal name masked", "deal name", "name"):
        return None  # Signal to filter out

    norm: Dict = {
        "id": d.get("id"),
        "name": name_val or "Unknown WO",

        # Customer/deal identifiers
        "customer_code": _clean_str(get([
            "customer_name_code", "customer_code", "client_code", "customer"
        ])),
        "serial_no": _clean_str(get([
            "serial_#", "serial_no", "serial"
        ])),

        # Work type information
        "nature_of_work": _clean_str(get([
            "nature_of_work", "nature", "work_type"
        ])),
        "type_of_work": _clean_str(get([
            "type_of_work", "work_category", "type"
        ])),

        # Status fields — exact Monday column keys
        "execution_status": normalize_status(get([
            "execution_status", "exec_status"
        ])),
        "wo_status": normalize_status(get([
            "wo_status_billed", "wo_status", "work_order_status", "status"
        ])),
        "billing_status": normalize_status(get([
            "billing_status", "bill_status"
        ])),
        "invoice_status": normalize_status(get([
            "invoice_status"
        ])),
        "collection_status": normalize_status(get([
            "collection_status"
        ])),

        # Sector — exact Monday column: "sector" (status type)
        "sector": normalize_sector(get(["sector", "sector_service"])),

        # Personnel
        "bd_personnel": _clean_str(get([
            "bd_kam_personnel_code", "bd_code", "personnel"
        ])),

        # Monetary — CRITICAL: keep distinct, never conflate
        # Use excl GST for contract amount (cleaner comparison)
        "amount_inr": normalize_number(get([
            "amount_in_rupees_excl_of_gst_masked",  # exact Monday key
            "amount_in_rupees_incl_of_gst_masked",
            "amount_in_rupees_excl_of_gst_masked_",
            "amount_inr", "amount", "po_value"
        ])),

        # Use incl GST for billed (as invoiced to client)
        "billed_value": normalize_number(get([
            "billed_value_in_rupees_incl_of_gst_masked",  # exact Monday key
            "billed_value_in_rupees_excl_of_gst_masked",
            "billed_value", "billed_amount"
        ])),

        # Collected (what was received)
        "collected_amount": normalize_number(get([
            "collected_amount_in_rupees_incl_of_gst_masked",  # exact Monday key
            "collected_amount", "collected", "collection_amount"
        ])),

        # Receivables
        "amount_receivable": normalize_number(get([
            "amount_receivable_masked",  # exact Monday key
            "amount_receivable", "receivable", "outstanding"
        ])),

        # Dates
        "date_of_po_loi": normalize_date(get(["date_of_po_loi", "po_date", "loi_date"])),
        "probable_start_date": normalize_date(get(["probable_start_date", "start_date"])),
        "probable_end_date": normalize_date(get(["probable_end_date", "end_date"])),
        "data_delivery_date": normalize_date(get(["data_delivery_date", "delivery_date"])),
        "collection_date": normalize_date(get(["collection_date"])),

        # Billing months (string, not date)
        "expected_billing_month": _clean_str(get(["expected_billing_month", "billing_month"])),
        "actual_billing_month": _clean_str(get(["actual_billing_month"])),
        "actual_collection_month": _clean_str(get(["actual_collection_month"])),

        "__raw": {k: v for k, v in d.items() if not k.startswith("__type_")},
    }
    return norm


def normalize_deals(raw_deals: List[Dict]) -> List[Dict]:
    results = []
    for d in raw_deals:
        normalized = normalize_deal(d)
        if normalized is not None:
            results.append(normalized)
    return results


def normalize_work_orders(raw_wos: List[Dict]) -> List[Dict]:
    results = []
    for w in raw_wos:
        normalized = normalize_work_order(w)
        if normalized is not None:
            results.append(normalized)
    return results

