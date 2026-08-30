"""
Board-level data fetching: converts raw Monday items into
clean Python dicts ready for normalization.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from backend.monday.client import get_client
from backend.config import DEALS_BOARD_ID, WORK_ORDERS_BOARD_ID

logger = logging.getLogger(__name__)


def _item_to_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a Monday item (with column_values list) into a flat dict.
    Keys are column titles (lowercased, spaces→underscores).
    Always includes 'id' and 'name'.
    """
    row: Dict[str, Any] = {
        "id": item.get("id"),
        "name": item.get("name", ""),
    }
    for cv in item.get("column_values", []):
        col_title = cv.get("column", {}).get("title", cv.get("id", ""))
        col_type = cv.get("column", {}).get("type", "")
        key = col_title.strip().lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "").replace(".", "").replace("-", "_")

        # Prefer text representation; fall back to value JSON
        text_val = cv.get("text", None)
        raw_val = cv.get("value", None)

        if text_val is not None and text_val != "":
            row[key] = text_val
        elif raw_val is not None and raw_val != "null":
            # Try to parse JSON value for richer types
            try:
                parsed = json.loads(raw_val)
                if isinstance(parsed, dict):
                    # For date columns, extract the date string
                    if "date" in parsed:
                        row[key] = parsed["date"]
                    elif "text" in parsed:
                        row[key] = parsed["text"]
                    else:
                        row[key] = raw_val
                else:
                    row[key] = parsed
            except (json.JSONDecodeError, TypeError):
                row[key] = raw_val
        else:
            row[key] = None

        # Also store column type metadata for normalizer
        row[f"__type_{key}"] = col_type

    return row


def fetch_deals(limit: int = 500) -> List[Dict[str, Any]]:
    """Fetch all deals from the Deals board."""
    client = get_client()
    logger.info("Fetching deals from board %s", DEALS_BOARD_ID)
    raw_items = client.get_all_items(DEALS_BOARD_ID, limit=limit)
    logger.info("Fetched %d deals", len(raw_items))
    return [_item_to_dict(item) for item in raw_items]


def fetch_work_orders(limit: int = 500) -> List[Dict[str, Any]]:
    """Fetch all work orders from the Work Orders board."""
    client = get_client()
    logger.info("Fetching work orders from board %s", WORK_ORDERS_BOARD_ID)
    raw_items = client.get_all_items(WORK_ORDERS_BOARD_ID, limit=limit)
    logger.info("Fetched %d work orders", len(raw_items))
    return [_item_to_dict(item) for item in raw_items]


def get_board_schema(board_id: str) -> List[Dict[str, Any]]:
    """Return the column schema for a board."""
    client = get_client()
    return client.get_board_columns(board_id)
