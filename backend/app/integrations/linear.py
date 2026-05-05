from __future__ import annotations

import asyncio
import re
import uuid
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
        team_id: str | None = None,
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

        if team_id is not None:
            filter_["team"] = {"id": {"eq": team_id}}

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

    async def list_teams(self) -> list[dict]:
        """Fetch all Linear teams in the workspace. Returns list of {id, name, key, description}."""
        gql = """
        query {
            teams {
                nodes { id name key description }
            }
        }
        """
        data = await self._execute(gql, {})
        return data["teams"]["nodes"]

    async def resolve_update_input(self, issue_id: str, raw: dict) -> dict:
        """Translate a proposal's after dict into a valid IssueUpdateInput for Linear.

        The LLM stores human-readable values (e.g. state="In Progress", assignee="James Liu").
        Linear's API requires IDs (stateId, assigneeId). This method resolves them.
        """
        _PASSTHROUGH = {"title", "description", "priority", "stateId", "assigneeId",
                        "teamId", "labelIds", "dueDate", "estimate", "parentId"}
        out: dict = {k: v for k, v in raw.items() if k in _PASSTHROUGH}

        if "stateId" in out and not _is_uuid(out["stateId"]):
            out.pop("stateId")
        if "assigneeId" in out and not _is_uuid(out["assigneeId"]):
            out.pop("assigneeId")

        needs_state = "state" in raw or ("stateId" in raw and "stateId" not in out)
        needs_assignee = "assignee" in raw or ("assigneeId" in raw and "assigneeId" not in out)

        issue: dict | None = None
        if needs_state:
            issue = await self.get_issue(issue_id)

        if needs_state:
            state_val = raw.get("state", raw.get("stateId"))
            state_name = state_val if isinstance(state_val, str) else (state_val.get("name") if isinstance(state_val, dict) else None)
            if state_name and issue:
                states = await self._get_workflow_states(issue["team"]["id"])
                match = next((s for s in states if s["name"].lower() == state_name.lower()), None)
                if match:
                    out["stateId"] = match["id"]

        if needs_assignee:
            assignee_val = raw.get("assignee", raw.get("assigneeId"))
            assignee_name = assignee_val if isinstance(assignee_val, str) else (assignee_val.get("name") if isinstance(assignee_val, dict) else None)
            if assignee_name:
                users = await self._search_users(assignee_name)
                if users:
                    out["assigneeId"] = users[0]["id"]

        return out

    async def _get_workflow_states(self, team_id: str) -> list[dict]:
        gql = """
        query TeamStates($id: String!) {
            team(id: $id) {
                states {
                    nodes { id name }
                }
            }
        }
        """
        data = await self._execute(gql, {"id": team_id})
        return data["team"]["states"]["nodes"]

    async def _search_users(self, name: str) -> list[dict]:
        gql = """
        query Users($name: String!) {
            users(filter: { displayName: { containsIgnoreCase: $name } }) {
                nodes { id displayName }
            }
        }
        """
        data = await self._execute(gql, {"name": name})
        return data["users"]["nodes"]

    async def update_issue(self, issue_id: str, fields: dict) -> dict:
        """Update an existing Linear issue. `fields` is a valid IssueUpdateInput dict."""
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


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
