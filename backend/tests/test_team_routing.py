import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_list_teams_returns_list():
    from app.integrations.linear import LinearClient

    fake_response = {
        "teams": {
            "nodes": [
                {"id": "team-1", "name": "Frontend", "key": "FE", "description": ""},
                {"id": "team-2", "name": "Backend", "key": "BE", "description": "API team"},
            ]
        }
    }

    client = LinearClient("fake-key")
    with patch.object(client, "_execute", new=AsyncMock(return_value=fake_response)):
        teams = await client.list_teams()

    assert len(teams) == 2
    assert teams[0]["id"] == "team-1"
    assert teams[0]["name"] == "Frontend"
    assert teams[0]["key"] == "FE"


@pytest.mark.asyncio
async def test_search_issues_passes_team_filter():
    from app.integrations.linear import LinearClient

    captured: dict = {}

    async def fake_execute(gql: str, variables: dict) -> dict:
        captured["variables"] = variables
        return {"issues": {"nodes": [], "pageInfo": {"hasNextPage": False}}}

    client = LinearClient("fake-key")
    with patch.object(client, "_execute", new=AsyncMock(side_effect=fake_execute)):
        await client.search_issues("auth bug", team_id="team-1")

    assert captured["variables"]["filter"]["team"]["id"]["eq"] == "team-1"


@pytest.mark.asyncio
async def test_search_issues_no_team_filter_when_none():
    from app.integrations.linear import LinearClient

    captured: dict = {}

    async def fake_execute(gql: str, variables: dict) -> dict:
        captured["variables"] = variables
        return {"issues": {"nodes": [], "pageInfo": {"hasNextPage": False}}}

    client = LinearClient("fake-key")
    with patch.object(client, "_execute", new=AsyncMock(side_effect=fake_execute)):
        await client.search_issues("auth bug")

    assert "team" not in captured["variables"]["filter"]


def test_match_team_exact_name():
    from app.api.runs import _match_team_by_title
    teams = [
        {"linear_team_id": "t1", "name": "Frontend", "key": "FE"},
        {"linear_team_id": "t2", "name": "Backend", "key": "BE"},
    ]
    assert _match_team_by_title("Frontend Sprint Planning", teams) == "t1"


def test_match_team_key():
    from app.api.runs import _match_team_by_title
    teams = [{"linear_team_id": "t1", "name": "Frontend", "key": "FE"}]
    assert _match_team_by_title("FE weekly standup", teams) == "t1"


def test_match_team_case_insensitive():
    from app.api.runs import _match_team_by_title
    teams = [{"linear_team_id": "t1", "name": "Design", "key": "DES"}]
    assert _match_team_by_title("design review", teams) == "t1"


def test_match_team_no_match_returns_none():
    from app.api.runs import _match_team_by_title
    teams = [{"linear_team_id": "t1", "name": "Frontend", "key": "FE"}]
    assert _match_team_by_title("Q3 Planning", teams) is None
