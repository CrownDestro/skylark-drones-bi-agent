"""
Monday.com GraphQL API client.
Read-only. Never mutates board data.
"""
import httpx
import logging
from typing import Any, Dict, Optional

from backend.config import MONDAY_API_TOKEN, MONDAY_API_URL

logger = logging.getLogger(__name__)


class MondayClient:
    """Thin wrapper around the Monday.com GraphQL API."""

    def __init__(self, token: str = MONDAY_API_TOKEN):
        if not token:
            raise ValueError("MONDAY_API_TOKEN is not set.")
        self._token = token
        self._headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "API-Version": "2023-10",
        }

    def query(self, gql: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a GraphQL query and return parsed JSON data."""
        payload: Dict[str, Any] = {"query": gql}
        if variables:
            payload["variables"] = variables

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    MONDAY_API_URL,
                    headers=self._headers,
                    json=payload,
                )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                logger.error("Monday GraphQL errors: %s", result["errors"])
                raise RuntimeError(f"Monday API errors: {result['errors']}")

            return result.get("data", {})

        except httpx.HTTPStatusError as e:
            logger.error("Monday HTTP error %s: %s", e.response.status_code, e.response.text)
            raise RuntimeError(f"Monday API HTTP error: {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error("Monday request error: %s", e)
            raise RuntimeError("Could not connect to Monday.com API.") from e

    def get_board_columns(self, board_id: str) -> list:
        """Return column definitions for a board."""
        gql = """
        query ($boardId: ID!) {
            boards(ids: [$boardId]) {
                columns {
                    id
                    title
                    type
                    settings_str
                }
            }
        }
        """
        data = self.query(gql, {"boardId": board_id})
        boards = data.get("boards", [])
        if not boards:
            return []
        return boards[0].get("columns", [])

    def get_all_items(self, board_id: str, limit: int = 500) -> list:
        """
        Fetch all items from a board using cursor-based pagination.
        Returns a flat list of item dicts with column_values unpacked.
        """
        items: list = []
        cursor: Optional[str] = None

        while True:
            if cursor:
                gql = """
                query ($boardId: ID!, $limit: Int!, $cursor: String!) {
                    boards(ids: [$boardId]) {
                        items_page(limit: $limit, cursor: $cursor) {
                            cursor
                            items {
                                id
                                name
                                column_values {
                                    id
                                    text
                                    value
                                    column {
                                        title
                                        type
                                    }
                                }
                            }
                        }
                    }
                }
                """
                variables = {"boardId": board_id, "limit": limit, "cursor": cursor}
            else:
                gql = """
                query ($boardId: ID!, $limit: Int!) {
                    boards(ids: [$boardId]) {
                        items_page(limit: $limit) {
                            cursor
                            items {
                                id
                                name
                                column_values {
                                    id
                                    text
                                    value
                                    column {
                                        title
                                        type
                                    }
                                }
                            }
                        }
                    }
                }
                """
                variables = {"boardId": board_id, "limit": limit}

            data = self.query(gql, variables)
            boards = data.get("boards", [])
            if not boards:
                break

            page = boards[0].get("items_page", {})
            page_items = page.get("items", [])
            items.extend(page_items)

            cursor = page.get("cursor")
            if not cursor or not page_items:
                break

        return items


# Module-level singleton (lazy)
_client: Optional[MondayClient] = None


def get_client() -> MondayClient:
    global _client
    if _client is None:
        _client = MondayClient()
    return _client
