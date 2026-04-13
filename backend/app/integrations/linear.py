from __future__ import annotations

from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

LINEAR_API_URL = "https://api.linear.app/graphql"

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), keep_trailing_newline=True)


class LinearClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search_issues(
        self,
        query: str,
        first: int = 20,
        after: str | None = None,
    ) -> dict:
        """Search Linear issues by keyword. Returns {"issues": [...], "pageInfo": {...}}."""
        variables: dict = {
            "filter": {"searchableContent": {"containsIgnoreCase": query}},
            "first": first,
        }
        if after is not None:
            variables["after"] = after

        gql = _jinja_env.get_template("linear_search_issues.j2").render()
        data = await self._execute(gql, variables)
        issues_data = data["issues"]
        return {
            "issues": issues_data["nodes"],
            "pageInfo": issues_data["pageInfo"],
        }

    async def get_issue(self, issue_id: str) -> dict:
        """Fetch a single Linear issue by ID."""
        gql = _jinja_env.get_template("linear_get_issue.j2").render()
        data = await self._execute(gql, {"id": issue_id})
        return data["issue"]

    async def _execute(self, query: str, variables: dict) -> dict:
        headers = {
            "Authorization": self._api_key,  # Linear: no "Bearer" prefix
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.post(
                LINEAR_API_URL,
                json={"query": query, "variables": variables},
                headers=headers,
            )
            response.raise_for_status()
            # TODO Phase C: exponential backoff on 429
            payload = response.json()
            if "errors" in payload:
                raise RuntimeError(f"Linear GraphQL error: {payload['errors']}")
            return payload["data"]
