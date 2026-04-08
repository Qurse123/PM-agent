import uuid
from typing import Any


def parse_transcript(text: str, run_id: uuid.UUID) -> list[dict[str, Any]]:
    """
    Parse pasted Meet transcript into segment dicts.

    Expected format (blocks separated by blank lines):
        Speaker Name
        Transcript text here.

        Another Speaker
        More text.

    Returns list of dicts matching TranscriptSegment fields (excluding id).
    segment_id format: f"paste-{run_id}-{i:04d}"
    start_ms and end_ms are None for paste runs.
    """
    segments: list[dict[str, Any]] = []

    # Split into blocks on one or more blank lines
    raw_blocks = [b.strip() for b in text.strip().split("\n\n") if b.strip()]

    # Further split on runs of multiple blank lines by re-joining then splitting
    # (the list comprehension above already handles consecutive blank lines via strip + filter)

    idx = 0
    for block in raw_blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]

        if not lines:
            continue

        if len(lines) == 1:
            # Only a speaker line with no text — skip per spec
            continue

        speaker = lines[0]
        body = " ".join(lines[1:])

        if not body:
            # No usable text — skip
            continue

        segments.append(
            {
                "run_id": run_id,
                "segment_id": f"paste-{run_id}-{idx:04d}",
                "start_ms": None,
                "end_ms": None,
                "speaker_ref": speaker if speaker else "Unknown",
                "text": body,
            }
        )
        idx += 1

    return segments
