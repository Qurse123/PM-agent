from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment, FileSystemLoader
from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
    ChatCompletionToolUnionParam,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.integrations.linear import LinearClient
from app.models.db import Proposal, ProposalCitation, TranscriptSegment, WorkspaceContext
from app.rag.retrieve import retrieve_similar_feedback

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(_PROMPTS_DIR), keep_trailing_newline=True)

MAX_ITERATIONS = 10

_TOOLS: list[dict] = json.loads(_jinja_env.get_template("linear_tools.j2").render())


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
        seg_ids = c.get("segment_ids") or []
        for sid in seg_ids:
            if sid not in valid_segment_ids:
                raise ValueError(f"segment_id '{sid}' not found in transcript")
        quote = (c.get("quote") or "").strip()
        rationale = (c.get("rationale") or "").strip()
        if not quote:
            raise ValueError("Citation must have a non-empty quote")
        if not rationale:
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

    transcript_summary = " ".join(transcript_lines)[:800]
    feedback_events = await retrieve_similar_feedback(transcript_summary, db, limit=10)
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

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    linear = LinearClient(settings.linear_api_key)

    messages: list[ChatCompletionMessageParam] = cast(
        list[ChatCompletionMessageParam],
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Begin."},
        ],
    )
    proposal_ids: list[uuid.UUID] = []

    for _iteration in range(MAX_ITERATIONS):
        response = await client.chat.completions.create(
            model="gpt-4o",
            tools=cast(list[ChatCompletionToolUnionParam], _TOOLS),
            messages=messages,
        )

        choice = response.choices[0]
        msg = choice.message

        # Append assistant message (only function tool calls are supported here)
        assistant_tool_calls: list[dict[str, Any]] | None = None
        if msg.tool_calls:
            assistant_tool_calls = []
            for tc in msg.tool_calls:
                if getattr(tc, "type", None) != "function":
                    continue
                ftc = cast(ChatCompletionMessageFunctionToolCall, tc)
                assistant_tool_calls.append(
                    {
                        "id": ftc.id,
                        "type": "function",
                        "function": {"name": ftc.function.name, "arguments": ftc.function.arguments},
                    }
                )
            if not assistant_tool_calls:
                assistant_tool_calls = None

        messages.append(
            cast(
                ChatCompletionMessageParam,
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": assistant_tool_calls,
                },
            )
        )

        if choice.finish_reason == "stop":
            break

        for tc in msg.tool_calls or []:
            if getattr(tc, "type", None) != "function":
                continue
            ftc = cast(ChatCompletionMessageFunctionToolCall, tc)
            result = await _dispatch_tool(
                name=ftc.function.name,
                input_=json.loads(ftc.function.arguments),
                linear=linear,
                db=db,
                run_id=run_id,
                valid_segment_ids=valid_segment_ids,
                proposal_ids=proposal_ids,
            )
            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    {
                        "role": "tool",
                        "tool_call_id": ftc.id,
                        "content": json.dumps(result),
                    },
                )
            )

    return proposal_ids
