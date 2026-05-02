from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.linear import LINEAR_API_URL, LinearClient


def _mock_response(data: dict, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = data
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp
        )
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


def _patch_client(mock_resp):
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_client, mock_ctx


@pytest.mark.asyncio
async def test_search_issues_sends_correct_query():
    """search_issues posts to LINEAR_API_URL with the search keyword in variables."""
    mock_resp = _mock_response(
        {
            "data": {
                "issues": {
                    "nodes": [],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        await client.search_issues("fix login")

    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs[0][0] == LINEAR_API_URL
    body = call_kwargs[1]["json"]
    variables = body["variables"]
    assert (
        variables["filter"]["searchableContent"]["contains"] == "fix login"
    )


@pytest.mark.asyncio
async def test_search_issues_returns_parsed_result():
    """search_issues returns a dict with 'issues' list and 'pageInfo'."""
    nodes = [{"id": "abc", "title": "T"}]
    page_info = {"hasNextPage": False, "endCursor": None}
    mock_resp = _mock_response(
        {"data": {"issues": {"nodes": nodes, "pageInfo": page_info}}}
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        result = await client.search_issues("some query")

    assert "issues" in result
    assert "pageInfo" in result
    assert result["issues"] == nodes
    assert result["pageInfo"] == page_info


@pytest.mark.asyncio
async def test_search_issues_with_cursor():
    """search_issues includes 'after' cursor in POST body variables when provided."""
    mock_resp = _mock_response(
        {
            "data": {
                "issues": {
                    "nodes": [],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                }
            }
        }
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        await client.search_issues("query", after="cursor-abc")

    call_kwargs = mock_client.post.call_args
    body = call_kwargs[1]["json"]
    assert body["variables"]["after"] == "cursor-abc"


@pytest.mark.asyncio
async def test_get_issue_sends_correct_id():
    """get_issue posts with the correct issue ID in variables."""
    mock_resp = _mock_response(
        {
            "data": {
                "issue": {
                    "id": "issue-123",
                    "title": "Some issue",
                    "identifier": "ENG-1",
                    "description": "desc",
                    "state": {"name": "In Progress"},
                    "assignee": {"displayName": "Alice"},
                    "team": {"name": "Engineering"},
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-02T00:00:00Z",
                    "comments": {"nodes": []},
                }
            }
        }
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        await client.get_issue("issue-123")

    call_kwargs = mock_client.post.call_args
    body = call_kwargs[1]["json"]
    assert body["variables"]["id"] == "issue-123"


@pytest.mark.asyncio
async def test_get_issue_returns_dict():
    """get_issue returns a dict with 'id' and 'title' keys."""
    issue = {
        "id": "issue-456",
        "title": "Bug in login",
        "identifier": "ENG-2",
        "description": "Login broken",
        "state": {"name": "Todo"},
        "assignee": None,
        "team": {"name": "Backend"},
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
        "comments": {"nodes": []},
    }
    mock_resp = _mock_response({"data": {"issue": issue}})
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        result = await client.get_issue("issue-456")

    assert "id" in result
    assert "title" in result
    assert result["id"] == "issue-456"
    assert result["title"] == "Bug in login"


@pytest.mark.asyncio
async def test_graphql_error_raises_runtime_error():
    """A GraphQL error in the response body (HTTP 200) raises RuntimeError."""
    mock_resp = _mock_response(
        {"errors": [{"message": "Not found"}]}
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        with pytest.raises(RuntimeError, match="Linear GraphQL error"):
            await client.get_issue("bad-id")


@pytest.mark.asyncio
async def test_http_error_raises():
    """An HTTP 401 response raises httpx.HTTPStatusError."""
    mock_resp = _mock_response({}, status_code=401)
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="bad-key")
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_issue("issue-123")


@pytest.mark.asyncio
async def test_null_assignee_handled():
    """A node with assignee=None is returned without raising."""
    nodes = [{"id": "xyz", "title": "No assignee issue", "assignee": None}]
    page_info = {"hasNextPage": False, "endCursor": None}
    mock_resp = _mock_response(
        {"data": {"issues": {"nodes": nodes, "pageInfo": page_info}}}
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        result = await client.search_issues("no assignee")

    assert result["issues"][0]["assignee"] is None


@pytest.mark.asyncio
async def test_create_issue_sends_correct_variables():
    """create_issue posts the correct mutation variables to Linear."""
    mock_resp = _mock_response(
        {"data": {"issueCreate": {"success": True, "issue": {"id": "new-1", "title": "New issue", "url": "https://linear.app/new-1"}}}}
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        result = await client.create_issue(title="New issue", description="Details", team_id="team-xyz")

    assert result["id"] == "new-1"
    call_kwargs = mock_client.post.call_args
    body = call_kwargs[1]["json"]
    assert body["variables"]["title"] == "New issue"
    assert body["variables"]["description"] == "Details"
    assert body["variables"]["teamId"] == "team-xyz"


@pytest.mark.asyncio
async def test_update_issue_sends_correct_variables():
    """update_issue posts the correct mutation variables to Linear."""
    mock_resp = _mock_response(
        {"data": {"issueUpdate": {"success": True, "issue": {"id": "li-123", "title": "Updated", "url": "https://linear.app/li-123"}}}}
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        result = await client.update_issue("li-123", {"title": "Updated"})

    assert result["id"] == "li-123"
    call_kwargs = mock_client.post.call_args
    body = call_kwargs[1]["json"]
    assert body["variables"]["id"] == "li-123"
    assert body["variables"]["input"] == {"title": "Updated"}


@pytest.mark.asyncio
async def test_create_issue_failure_raises():
    """create_issue raises RuntimeError when Linear returns success=False."""
    mock_resp = _mock_response(
        {"data": {"issueCreate": {"success": False, "issue": None}}}
    )
    mock_client, mock_ctx = _patch_client(mock_resp)

    with patch("httpx.AsyncClient", return_value=mock_ctx):
        client = LinearClient(api_key="test-key")
        with pytest.raises(RuntimeError, match="Linear issueCreate failed"):
            await client.create_issue(title="Bad", description="", team_id="team-xyz")


@pytest.mark.asyncio
async def test_retries_on_429():
    """_execute retries up to 3 times on 429 then succeeds on 4th attempt."""
    ok_resp = _mock_response({"data": {"issue": {"id": "li-1", "title": "T", "url": "u"}}})

    rate_resp = MagicMock()
    rate_resp.status_code = 429
    rate_resp.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=[rate_resp, rate_resp, rate_resp, ok_resp])
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("httpx.AsyncClient", return_value=mock_ctx),
        patch("app.integrations.linear.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        client = LinearClient(api_key="test-key")
        result = await client.get_issue("li-1")

    assert result["id"] == "li-1"
    assert mock_sleep.call_count == 3
    assert mock_client.post.call_count == 4
