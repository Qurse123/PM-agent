from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import anthropic
from anthropic.types import MessageParam, ToolParam
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.linear import LinearClient
from app.models.db import FeedbackEvent, Proposal, ProposalCitation, TranscriptSegment, WorkspaceContext

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), keep_trailing_newline=True)

MAX_ITERATIONS = 10

_TOOLS: list[ToolParam] = json.loads(_jinja_env.get_template("linear_tools.j2").render())


def _build_system_prompt(
    transcript_lines: list[str],
    valid_segment_ids: set[str],
    prior_feedback: str,
    workspace: WorkspaceContext | None = None,
) -> str:
    return _jinja_env.get_template("orchestrator_system.j2").render(
        transcript_text="\n".join(transcript_lines),
        segment_ids_list=", ".join(sorted(valid_segment_ids)),
        prior_feedback=prior_feedback,
        workspace=workspace,
    )


async def _handle_create_proposal(
    input_: dict[str, Any],
    db: AsyncSession,
    run_id: uuid.UUID,
    valid_segment_ids: set[str],
    proposal_ids: list[uuid.UUID],
) -> dict[str, Any]:
    """Validate citations and write proposal + citations to DB."""
    citations = input_.get("citations")

    if not citations:
        raise ValueError("Proposal must have at least one citation")

    for c in citations:
        for sid in c.get("segment_ids"):
            if sid not in valid_segment_ids:
                raise ValueError(f"segment_id '{sid}' not found in transcript")
        if not c.get("quote").strip():
            raise ValueError("Citation must have a non-empty quote")
        if not c.get("rationale").strip():
            raise ValueError("Citation must have a non-empty rationale")

    operation = input_["operation"]
    before = input_.get("before")
    if operation == "update" and before is None:
        raise ValueError("'before' must be provided for update operations")

    proposal = Proposal(
        run_id=run_id,
        target=input_["target"],
        operation=operation,
        before=before,
        after=input_["after"],
        status="pending",
    )
    db.add(proposal)
    await db.flush()

    for c in citations:
        db.add(
            ProposalCitation(
                proposal_id=proposal.id,
                segment_ids=c["segment_ids"],
                quote=c["quote"],
                rationale=c["rationale"],
            )
        )
    await db.commit()
    proposal_ids.append(proposal.id)
    return {"proposal_id": str(proposal.id), "status": "created"}


async def _dispatch_tool(
    name: str,
    input_: dict[str, Any],
    linear: LinearClient,
    db: AsyncSession,
    run_id: uuid.UUID,
    valid_segment_ids: set[str],
    proposal_ids: list[uuid.UUID],
) -> dict[str, Any]:
    """Dispatch a tool call and return a result dict. Errors are returned as dicts (not raised)."""
    try:
        if name == "search_linear_issues":
            return await linear.search_issues(
                query=input_["query"],
                first=input_.get("first", 20),
                after=input_.get("after"),
            )
        elif name == "get_linear_issue":
            return await linear.get_issue(input_["issue_id"])
        elif name == "create_proposal":
            return await _handle_create_proposal(input_, db, run_id, valid_segment_ids, proposal_ids)
        else:
            return {"error": f"Unknown tool: {name}"}
    except Exception as exc:
        return {"error": str(exc)}


async def run_orchestrator(run_id: uuid.UUID, db: AsyncSession) -> list[uuid.UUID]:
    """
    Run the LLM agent loop for a given run.
    Returns list of proposal IDs created.
    """
    # Load transcript segments
    result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.run_id == run_id)
        .order_by(TranscriptSegment.start_ms.asc().nulls_last(), TranscriptSegment.id.asc())
    )
    segments = list(result.scalars().all())

    if not segments:
        raise ValueError(
            f"No transcript segments for run {run_id}; add transcript data before running the orchestrator."
        )

    valid_segment_ids: set[str] = {s.segment_id for s in segments}
    transcript_lines = [
        f"[{s.segment_id}] {s.speaker_ref or 'Unknown'}: {s.text}"
        for s in segments
    ]

    # Retrieve recent feedback events to inject into system prompt
    feedback_result = await db.execute(
        select(FeedbackEvent).order_by(FeedbackEvent.created_at.desc()).limit(20)
    )
    feedback_events = list(feedback_result.scalars().all())
    if feedback_events:
        lines = ["Past feedback from this workspace (most recent first):"]
        for fe in feedback_events:
            line = f"- [{fe.category}] {fe.reason}"
            if fe.disputed_segment_ids:
                line += f" (disputed segments: {', '.join(fe.disputed_segment_ids)})"
            lines.append(line)
        prior_feedback: str = "\n".join(lines)
    else:
        prior_feedback = ""

    ctx_result = await db.execute(select(WorkspaceContext).limit(1))
    workspace = ctx_result.scalar_one_or_none()

    system_prompt = _build_system_prompt(transcript_lines, valid_segment_ids, prior_feedback, workspace)

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    linear = LinearClient(settings.linear_api_key)

    messages: list[MessageParam] = [{"role": "user", "content": "Begin."}]
    proposal_ids: list[uuid.UUID] = []

    for _iteration in range(MAX_ITERATIONS):
        response = await client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=system_prompt,
            tools=_TOOLS,
            messages=messages,
        )

        # Append assistant message
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        # Process ALL tool_use blocks, collect ALL results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await _dispatch_tool(
                    name=block.name,
                    input_=block.input,
                    linear=linear,
                    db=db,
                    run_id=run_id,
                    valid_segment_ids=valid_segment_ids,
                    proposal_ids=proposal_ids,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return proposal_ids
