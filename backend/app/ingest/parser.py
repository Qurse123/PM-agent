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
    idx = 0

    def _add(speaker: str, body: str) -> None:
        nonlocal idx
        body = body.strip()
        if not body:
            return
        segments.append(
            {
                "run_id": run_id,
                "segment_id": f"paste-{run_id}-{idx:04d}",
                "start_ms": None,
                "end_ms": None,
                "speaker_ref": speaker.strip() or "Unknown",
                "text": body,
            }
        )
        idx += 1

    lines = [line.strip() for line in text.strip().splitlines()]

    # Detect format: "Speaker: text" (inline) vs blank-line-separated blocks
    inline = any(": " in line for line in lines if line)

    if inline:
        for line in lines:
            if not line:
                continue
            if ": " in line:
                speaker, _, body = line.partition(": ")
                _add(speaker, body)
            else:
                # continuation line — append to last segment
                if segments:
                    segments[-1]["text"] += " " + line
    else:
        # Block format: blank lines separate speaker/text pairs
        raw_blocks = [b.strip() for b in text.strip().split("\n\n") if b.strip()]
        for block in raw_blocks:
            blines = [ln.strip() for ln in block.splitlines() if ln.strip()]
            if len(blines) < 2:
                continue
            _add(blines[0], " ".join(blines[1:]))

    return segments
