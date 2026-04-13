import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

MEET_BASE = "https://meet.googleapis.com/v2"


def _parse_time_to_ms(value: str | None) -> int | None:
    """
    Parse an RFC3339 / ISO8601 datetime string to epoch milliseconds.
    Returns None if value is missing or cannot be parsed.
    """
    if not value: 
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.astimezone(timezone.utc).timestamp() * 1000)
    except (ValueError, AttributeError):
        return None


async def fetch_transcript_entries(
    conference_record_id: str,
    access_token: str,
) -> list[dict[str, Any]]:
    """
    Fetch all transcript entries for a conference record.

    Returns segment dicts matching TranscriptSegment fields (excluding id, run_id):
        segment_id, start_ms, end_ms, speaker_ref, text

    segment_id: last component of entry resource name, or f"meet-{index:04d}" fallback.
    start_ms / end_ms: parsed from RFC3339 startTime/endTime fields (or None).
    speaker_ref: entry["participantSession"]["signedinUser"]["displayName"] (or None).

    Raises httpx.HTTPStatusError on any non-2xx response.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    segments: list[dict[str, Any]] = [] ## initalized as an empty list
    global_index = 0 ## no. of transcipt enteries we save

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        ##list transcripts for the conference record (with pagination)
        transcripts_url = (
            f"{MEET_BASE}/conferenceRecords/{conference_record_id}/transcripts"
        )
        transcripts: list[dict[str, Any]] = []
        page_token: str | None = None
        while True: ## run loop forever until something in the loop breaks
            params: dict[str, str] = {} ## empty dict 
            if page_token: 
                params["pageToken"] = page_token
            response = await client.get(transcripts_url, headers=headers, params=params)
            response.raise_for_status() ## raise a status error if anything happens
            data = response.json() ## make reponse a json format called data 
            transcripts.extend(data["transcripts"])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        ##lists the no of spoken chunks in a single transcipt
        for transcript in transcripts:
            transcript_name = transcript["name"]
            entries_url = f"{MEET_BASE}/{transcript_name}/entries"
            entries: list[dict[str, Any]] = []
            entries_page_token: str | None = None
            while True:
                entries_params: dict[str, str] = {}
                if entries_page_token:
                    entries_params["pageToken"] = entries_page_token
                entries_response = await client.get(entries_url, headers=headers, params=entries_params)
                entries_response.raise_for_status()
                entries_data = entries_response.json()
                entries.extend(entries_data["transcriptEntries"])
                entries_page_token = entries_data.get("nextPageToken")
                if not entries_page_token:
                    break

            for entry in entries:
                # Derive segment_id from the last component of the resource name,
                # falling back to a stable positional id if the field is missing.
                raw_name: str | None = entry.get("name")
                segment_id = raw_name.split("/")[-1] if raw_name else f"meet-{global_index:04d}"

                # Parse timestamps
                start_ms = _parse_time_to_ms(entry.get("startTime"))
                end_ms = _parse_time_to_ms(entry.get("endTime"))

                # Speaker ref from nested participant session
                speaker_ref: str | None = None
                participant_session = entry.get("participantSession")
                if participant_session is not None:
                    signed_in_user = participant_session.get("signedinUser")
                    if signed_in_user is not None:
                        speaker_ref = signed_in_user.get("displayName")

                text: str = entry["text"]

                segments.append(
                    {
                        "segment_id": segment_id,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "speaker_ref": speaker_ref,
                        "text": text,
                    }
                )
                global_index += 1

    return segments
