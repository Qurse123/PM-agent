from __future__ import annotations

import asyncio
import re
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
        """Search Linear issues by keyword or identifier. Returns {"issues": [...], "pageInfo": {...}}."""
        identifier_match = re.fullmatch(r"[A-Z]+-(\d+)", query.strip())
        if identifier_match:
            # Search by number AND content so both paths work
            issue_number = int(identifier_match.group(1))
            filter_: dict = {
                "or": [
                    {"number": {"eq": issue_number}},
                    {"searchableContent": {"contains": query}},
                ]
            }
        else:
            filter_ = {"searchableContent": {"contains": query}}

        variables: dict = {"filter": filter_, "first": first}
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

    async def create_issue(self, title: str, description: str, team_id: str) -> dict:
        """Create a new Linear issue. Returns the created issue dict."""
        mutation = """
        mutation CreateIssue($title: String!, $description: String, $teamId: String!) {
            issueCreate(input: { title: $title, description: $description, teamId: $teamId }) {
                success
                issue { id title url }
            }
        }
        """
        result = await self._execute(mutation, {"title": title, "description": description, "teamId": team_id})
        if not result.get("issueCreate", {}).get("success"):
            raise RuntimeError(f"Linear issueCreate failed: {result}")
        return result["issueCreate"]["issue"]

    async def update_issue(self, issue_id: str, fields: dict) -> dict:
        """Update an existing Linear issue. `fields` is a partial IssueUpdateInput dict."""
        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue { id title url }
            }
        }
        """
        result = await self._execute(mutation, {"id": issue_id, "input": fields})
        if not result.get("issueUpdate", {}).get("success"):
            raise RuntimeError(f"Linear issueUpdate failed: {result}")
        return result["issueUpdate"]["issue"]

    async def _execute(self, query: str, variables: dict) -> dict:
        headers = {
            "Authorization": self._api_key,  # Linear: no "Bearer" prefix
            "Content-Type": "application/json",
        }
        delays = [1.0, 2.0, 4.0]
        last_response: httpx.Response | None = None
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            for attempt, delay in enumerate(delays + [None]):
                response = await client.post(
                    LINEAR_API_URL,
                    json={"query": query, "variables": variables},
                    headers=headers,
                )
                last_response = response
                if response.status_code == 429 and delay is not None:
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                payload = response.json() ## converts http response into a python object
                if "errors" in payload:
                    raise RuntimeError(f"Linear GraphQL error: {payload['errors']}")
                return payload["data"]
        if last_response is not None:
            last_response.raise_for_status()  # final raise after exhausted retries
        raise RuntimeError("Linear request failed before receiving a response")
