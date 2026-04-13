"""
Tests for Phase A ingest pipeline:
  1. parser.parse_transcript  (sync)
  2. meet.fetch_transcript_entries  (async, mocked httpx)
  3. Grounding contract: duplicate (run_id, segment_id) raises IntegrityError  (async, SQLite)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ingest.parser import parse_transcript

# ---------------------------------------------------------------------------
# 1. Parser tests (sync)
# ---------------------------------------------------------------------------


def _make_run_id() -> uuid.UUID:
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


def test_parse_basic_two_speakers():
    run_id = _make_run_id()
    text_input = "Alice\nHello everyone.\n\nBob\nThanks for joining."
    segments = parse_transcript(text_input, run_id)

    assert len(segments) == 2

    assert segments[0]["speaker_ref"] == "Alice"
    assert segments[0]["text"] == "Hello everyone."
    assert segments[0]["run_id"] == run_id
    assert segments[0]["start_ms"] is None
    assert segments[0]["end_ms"] is None

    assert segments[1]["speaker_ref"] == "Bob"
    assert segments[1]["text"] == "Thanks for joining."


def test_parse_segment_ids_are_stable():
    run_id = _make_run_id()
    text_input = "Alice\nFirst line.\n\nBob\nSecond line."

    result_a = parse_transcript(text_input, run_id)
    result_b = parse_transcript(text_input, run_id)

    assert [s["segment_id"] for s in result_a] == [s["segment_id"] for s in result_b]
    assert result_a[0]["segment_id"] == f"paste-{run_id}-0000"
    assert result_a[1]["segment_id"] == f"paste-{run_id}-0001"


def test_parse_skips_solo_speaker_block():
    run_id = _make_run_id()
    # Block 0: solo speaker (no body) — should be skipped
    # Block 1: valid
    text_input = "Alice\n\nBob\nHello there."
    segments = parse_transcript(text_input, run_id)

    assert len(segments) == 1
    assert segments[0]["speaker_ref"] == "Bob"
    assert segments[0]["text"] == "Hello there."


def test_parse_multiple_blank_lines_between_blocks():
    run_id = _make_run_id()
    # Three blank lines between blocks
    text_input = "Alice\nFirst block.\n\n\n\nBob\nSecond block."
    segments = parse_transcript(text_input, run_id)

    assert len(segments) == 2
    assert segments[0]["speaker_ref"] == "Alice"
    assert segments[1]["speaker_ref"] == "Bob"


def test_parse_empty_transcript():
    run_id = _make_run_id()
    segments = parse_transcript("", run_id)
    assert segments == []


def test_parse_strips_whitespace():
    run_id = _make_run_id()
    text_input = "  Alice  \n  Hello with spaces.  \n\n  Bob  \n  Trailing spaces.  "
    segments = parse_transcript(text_input, run_id)

    assert len(segments) == 2
    assert segments[0]["speaker_ref"] == "Alice"
    assert segments[0]["text"] == "Hello with spaces."
    assert segments[1]["speaker_ref"] == "Bob"
    assert segments[1]["text"] == "Trailing spaces."


def test_parse_segment_id_index_skips_invalid():
    run_id = _make_run_id()
    # Block 0: solo speaker → skipped, does not consume an index
    # Block 1: valid → gets index 0000 (not 0001)
    text_input = "OnlySpeaker\n\nRealSpeaker\nReal text here."
    segments = parse_transcript(text_input, run_id)

    assert len(segments) == 1
    assert segments[0]["segment_id"] == f"paste-{run_id}-0000"


# ---------------------------------------------------------------------------
# 2. Meet client tests (async, mocked httpx)
# ---------------------------------------------------------------------------


def _make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Build a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status = MagicMock()
    return resp


def _build_mock_client(responses: list) -> MagicMock:
    """
    Build a mock httpx.AsyncClient whose `get` returns `responses` in order.
    Supports use as an async context manager.
    """
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)

    # Support `async with httpx.AsyncClient(...) as client:`
    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=mock_client)
    async_cm.__aexit__ = AsyncMock(return_value=False)
    return async_cm


@pytest.mark.asyncio
async def test_fetch_maps_entry_fields():
    from app.ingest.meet import fetch_transcript_entries

    conf_id = "confRecords/abc123"
    access_token = "tok"

    transcripts_resp = _make_response(
        {
            "transcripts": [{"name": f"conferenceRecords/{conf_id}/transcripts/t1"}],
        }
    )
    entries_resp = _make_response(
        {
            "transcriptEntries": [
                {
                    "name": "conferenceRecords/abc/transcripts/t1/entries/entry001",
                    "startTime": "2024-01-01T10:00:00Z",
                    "endTime": "2024-01-01T10:00:05Z",
                    "participantSession": {
                        "signedinUser": {"displayName": "Alice"}
                    },
                    "text": "Hello world.",
                }
            ],
        }
    )

    mock_cm = _build_mock_client([transcripts_resp, entries_resp])

    with patch("httpx.AsyncClient", return_value=mock_cm):
        segments = await fetch_transcript_entries(conf_id, access_token)

    assert len(segments) == 1
    seg = segments[0]
    assert seg["segment_id"] == "entry001"
    assert seg["speaker_ref"] == "Alice"
    assert seg["text"] == "Hello world."
    # 2024-01-01T10:00:00Z → epoch ms
    expected_start = int(
        datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
    )
    expected_end = int(
        datetime(2024, 1, 1, 10, 0, 5, tzinfo=timezone.utc).timestamp() * 1000
    )
    assert seg["start_ms"] == expected_start
    assert seg["end_ms"] == expected_end


@pytest.mark.asyncio
async def test_fetch_fallback_segment_id():
    """Entry missing 'name' field → segment_id falls back to 'meet-0000'."""
    from app.ingest.meet import fetch_transcript_entries

    conf_id = "confRecords/abc123"

    transcripts_resp = _make_response(
        {
            "transcripts": [{"name": "conferenceRecords/abc/transcripts/t1"}],
        }
    )
    entries_resp = _make_response(
        {
            "transcriptEntries": [
                {
                    # No "name" field
                    "text": "No name entry.",
                }
            ],
        }
    )

    mock_cm = _build_mock_client([transcripts_resp, entries_resp])

    with patch("httpx.AsyncClient", return_value=mock_cm):
        segments = await fetch_transcript_entries(conf_id, "tok")

    assert len(segments) == 1
    assert segments[0]["segment_id"] == "meet-0000"


@pytest.mark.asyncio
async def test_fetch_missing_timestamps_returns_none():
    from app.ingest.meet import fetch_transcript_entries

    transcripts_resp = _make_response(
        {"transcripts": [{"name": "conferenceRecords/abc/transcripts/t1"}]}
    )
    entries_resp = _make_response(
        {
            "transcriptEntries": [
                {
                    "name": "conferenceRecords/abc/transcripts/t1/entries/e1",
                    # No startTime / endTime
                    "text": "No timestamps.",
                }
            ]
        }
    )

    mock_cm = _build_mock_client([transcripts_resp, entries_resp])

    with patch("httpx.AsyncClient", return_value=mock_cm):
        segments = await fetch_transcript_entries("cr/abc", "tok")

    assert segments[0]["start_ms"] is None
    assert segments[0]["end_ms"] is None


@pytest.mark.asyncio
async def test_fetch_missing_speaker_returns_none():
    from app.ingest.meet import fetch_transcript_entries

    transcripts_resp = _make_response(
        {"transcripts": [{"name": "conferenceRecords/abc/transcripts/t1"}]}
    )
    entries_resp = _make_response(
        {
            "transcriptEntries": [
                {
                    "name": "conferenceRecords/abc/transcripts/t1/entries/e1",
                    # No participantSession
                    "text": "Anonymous speech.",
                }
            ]
        }
    )

    mock_cm = _build_mock_client([transcripts_resp, entries_resp])

    with patch("httpx.AsyncClient", return_value=mock_cm):
        segments = await fetch_transcript_entries("cr/abc", "tok")

    assert segments[0]["speaker_ref"] is None


@pytest.mark.asyncio
async def test_fetch_raises_on_non_2xx():
    import httpx

    from app.ingest.meet import fetch_transcript_entries

    error_resp = _make_response({}, status_code=403)
    mock_cm = _build_mock_client([error_resp])

    with patch("httpx.AsyncClient", return_value=mock_cm):
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_transcript_entries("cr/abc", "tok")


@pytest.mark.asyncio
async def test_fetch_paginates_transcripts():
    from app.ingest.meet import fetch_transcript_entries

    # Page 1: one transcript + nextPageToken
    transcripts_page1 = _make_response(
        {
            "transcripts": [{"name": "conferenceRecords/abc/transcripts/t1"}],
            "nextPageToken": "token-page2",
        }
    )
    # Page 2: second transcript, no token
    transcripts_page2 = _make_response(
        {
            "transcripts": [{"name": "conferenceRecords/abc/transcripts/t2"}],
        }
    )
    # Entries for t1
    entries_t1 = _make_response(
        {
            "transcriptEntries": [
                {
                    "name": "conferenceRecords/abc/transcripts/t1/entries/e1",
                    "text": "From t1.",
                }
            ]
        }
    )
    # Entries for t2
    entries_t2 = _make_response(
        {
            "transcriptEntries": [
                {
                    "name": "conferenceRecords/abc/transcripts/t2/entries/e2",
                    "text": "From t2.",
                }
            ]
        }
    )

    mock_cm = _build_mock_client([transcripts_page1, transcripts_page2, entries_t1, entries_t2])

    with patch("httpx.AsyncClient", return_value=mock_cm):
        segments = await fetch_transcript_entries("cr/abc", "tok")

    assert len(segments) == 2
    texts = {s["text"] for s in segments}
    assert "From t1." in texts
    assert "From t2." in texts


@pytest.mark.asyncio
async def test_fetch_paginates_entries():
    from app.ingest.meet import fetch_transcript_entries

    transcripts_resp = _make_response(
        {"transcripts": [{"name": "conferenceRecords/abc/transcripts/t1"}]}
    )
    # Entries page 1
    entries_page1 = _make_response(
        {
            "transcriptEntries": [
                {
                    "name": "conferenceRecords/abc/transcripts/t1/entries/e1",
                    "text": "Entry one.",
                }
            ],
            "nextPageToken": "entries-page2",
        }
    )
    # Entries page 2
    entries_page2 = _make_response(
        {
            "transcriptEntries": [
                {
                    "name": "conferenceRecords/abc/transcripts/t1/entries/e2",
                    "text": "Entry two.",
                }
            ]
        }
    )

    mock_cm = _build_mock_client([transcripts_resp, entries_page1, entries_page2])

    with patch("httpx.AsyncClient", return_value=mock_cm):
        segments = await fetch_transcript_entries("cr/abc", "tok")

    assert len(segments) == 2
    texts = {s["text"] for s in segments}
    assert "Entry one." in texts
    assert "Entry two." in texts


# ---------------------------------------------------------------------------
# 3. Grounding contract test (async, SQLite in-memory via aiosqlite)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_segment_id_raises_integrity_error():
    """
    Inserting two TranscriptSegments with the same (run_id, segment_id)
    must raise IntegrityError — enforcing the citation grounding contract.
    """
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID

    # We need to re-map Postgres-specific UUID columns to generic types for SQLite.
    # Build a fresh metadata that uses String for UUID columns.
    from sqlalchemy import (
        Column,
        DateTime,
        ForeignKey,
        Integer,
        MetaData,
        String,
        Table,
        Text,
        UniqueConstraint,
    )
    from sqlalchemy.ext.asyncio import create_async_engine

    metadata = MetaData()

    runs_table = Table(
        "runs",
        metadata,
        Column("id", String, primary_key=True),
        Column("conference_record_id", String, nullable=False),
        Column("status", String, nullable=False, default="ingesting"),
        Column("created_at", String, nullable=False),
    )

    segments_table = Table(
        "transcript_segments",
        metadata,
        Column("id", String, primary_key=True),
        Column("run_id", String, ForeignKey("runs.id"), nullable=False),
        Column("segment_id", String, nullable=False),
        Column("start_ms", Integer, nullable=True),
        Column("end_ms", Integer, nullable=True),
        Column("speaker_ref", String, nullable=True),
        Column("text", Text, nullable=False),
        UniqueConstraint("run_id", "segment_id", name="uq_run_segment"),
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    run_id = str(uuid.uuid4())
    seg_id = str(uuid.uuid4())

    async with engine.connect() as conn:
        # Insert Run
        await conn.execute(
            runs_table.insert().values(
                id=run_id,
                conference_record_id="conf-xyz",
                status="ingesting",
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        await conn.commit()

        # Insert first segment — should succeed
        await conn.execute(
            segments_table.insert().values(
                id=str(uuid.uuid4()),
                run_id=run_id,
                segment_id="paste-abc-0000",
                start_ms=None,
                end_ms=None,
                speaker_ref="Alice",
                text="First segment.",
            )
        )
        await conn.commit()

        # Insert duplicate (same run_id + segment_id) — must raise IntegrityError
        with pytest.raises(IntegrityError):
            await conn.execute(
                segments_table.insert().values(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    segment_id="paste-abc-0000",  # duplicate!
                    start_ms=None,
                    end_ms=None,
                    speaker_ref="Bob",
                    text="Duplicate segment.",
                )
            )
            await conn.commit()

    await engine.dispose()
