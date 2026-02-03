# api/routes/slack.py
"""Slack slash command endpoint for the License Intelligence API.

Implements the /slack/command endpoint for Slack app integration with:
- Immediate acknowledgment (< 3 seconds requirement)
- Background task for async query processing
- Block Kit formatted responses
- Error handling and logging
"""

import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import Depends
from fastapi import Request

from api.dependencies import authenticate_slack
from api.formatters.slack import format_answer_blocks
from api.formatters.slack import format_error_blocks
from app.logging import get_logger
from app.query import query as rag_query

log = get_logger(__name__)

# Apply Slack signature verification to all routes in this router
router = APIRouter(
    prefix="/slack",
    tags=["Slack"],
    dependencies=[Depends(authenticate_slack)],
)


async def process_slack_query(
    question: str,
    user_id: str,
    channel_id: str,
    response_url: str,
    request_id: str,
) -> None:
    """Process Slack query in background and send response.

    This function runs asynchronously after the immediate acknowledgment
    is sent to Slack. It performs the RAG query and sends the formatted
    response to the response_url.

    Args:
        question: The user's question from Slack.
        user_id: Slack user ID for audit logging.
        channel_id: Slack channel ID for audit logging.
        response_url: Slack response_url for sending async response.
        request_id: Request ID for tracing.
    """
    start_time = time.time()
    query_id = str(uuid.uuid4())

    log.info(
        "slack_query_started",
        query_id=query_id,
        request_id=request_id,
        user_id=user_id,
        channel_id=channel_id,
        question_length=len(question),
    )

    try:
        # Execute RAG query
        # Use all sources by default for Slack queries
        result = rag_query(
            question=question,
            sources=None,  # All sources
            search_mode="hybrid",
            top_k=10,
            enable_reranking=True,
            enable_confidence_gate=True,
            include_definitions=True,  # Include definitions for Slack
        )

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Add metadata to result
        if "metadata" not in result:
            result["metadata"] = {}
        result["metadata"]["latency_ms"] = latency_ms
        result["metadata"]["query_id"] = query_id

        # Format response as Block Kit blocks
        blocks = format_answer_blocks(result)

        # Send response to Slack
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                response_url,
                json={
                    "response_type": "ephemeral",  # Only visible to requesting user
                    "blocks": blocks,
                },
            )
            response.raise_for_status()

        log.info(
            "slack_query_completed",
            query_id=query_id,
            request_id=request_id,
            user_id=user_id,
            latency_ms=latency_ms,
            refused=result.get("refused", False),
            chunks_retrieved=result.get("chunks_retrieved", 0),
        )

    except ValueError as e:
        # Validation errors (empty question, invalid sources, etc.)
        log.error(
            "slack_query_validation_error",
            query_id=query_id,
            request_id=request_id,
            user_id=user_id,
            error=str(e),
        )

        blocks = format_error_blocks(
            f"Sorry, I couldn't process that question: {e}",
            error_type="VALIDATION ERROR",
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    response_url,
                    json={
                        "response_type": "ephemeral",
                        "blocks": blocks,
                    },
                )
        except Exception as send_error:
            log.error(
                "slack_error_response_failed",
                query_id=query_id,
                request_id=request_id,
                error=str(send_error),
            )

    except RuntimeError as e:
        # Service errors (index not found, OpenAI failures, etc.)
        log.error(
            "slack_query_service_error",
            query_id=query_id,
            request_id=request_id,
            user_id=user_id,
            error=str(e),
        )

        blocks = format_error_blocks(
            "Sorry, the service is temporarily unavailable. Please try again later.",
            error_type="SERVICE ERROR",
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    response_url,
                    json={
                        "response_type": "ephemeral",
                        "blocks": blocks,
                    },
                )
        except Exception as send_error:
            log.error(
                "slack_error_response_failed",
                query_id=query_id,
                request_id=request_id,
                error=str(send_error),
            )

    except Exception as e:
        # Unexpected errors
        log.error(
            "slack_query_unexpected_error",
            query_id=query_id,
            request_id=request_id,
            user_id=user_id,
            error_type=type(e).__name__,
            error=str(e),
        )

        blocks = format_error_blocks(
            "Sorry, an unexpected error occurred. Please try again.",
            error_type="INTERNAL ERROR",
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    response_url,
                    json={
                        "response_type": "ephemeral",
                        "blocks": blocks,
                    },
                )
        except Exception as send_error:
            log.error(
                "slack_error_response_failed",
                query_id=query_id,
                request_id=request_id,
                error=str(send_error),
            )


@router.post("/command")
async def slack_command(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Handle Slack slash command requests.

    Immediately acknowledges the request (< 3 seconds) and processes
    the query in a background task. The final response is sent to
    the response_url asynchronously.

    Requires Slack signature verification (no API key needed).

    **Response Behavior**:
    - All responses are ephemeral (visible only to the user who invoked the command)
    - Both immediate acknowledgment and async responses use response_type: "ephemeral"
    - To enable in_channel responses, modify response_type in return values and
      process_slack_query function

    **Validation**:
    - Validates question is not empty/whitespace
    - Validates response_url is present (required for async response)
    - Validates user_id and channel_id are present (required for audit logging)

    Args:
        request: FastAPI request object (for request_id and form data).
        background_tasks: FastAPI background tasks.

    Returns:
        Immediate acknowledgment response (ephemeral message).

    Raises:
        UnauthorizedError: If Slack signature verification fails (handled by dependency).
    """
    # Get form data from request.state (cached by authenticate_slack dependency)
    # We can't use Form() parameters because the request body was already consumed
    # during Slack signature verification
    form_data = request.state.slack_form

    # Extract form fields
    text = str(form_data.get("text", ""))
    response_url = str(form_data.get("response_url", ""))
    user_id = str(form_data.get("user_id", ""))
    channel_id = str(form_data.get("channel_id", ""))
    command = str(form_data.get("command", ""))
    team_id = str(form_data.get("team_id", ""))

    # Get request ID for tracing
    request_id = getattr(request.state, "request_id", None)

    # Validate question is not empty
    question = text.strip()
    if not question:
        return {
            "response_type": "ephemeral",
            "text": ":warning: Please provide a question. Example: `/rag What are the CME fees?`",
        }

    # Validate required fields for async response
    # response_url is required to send the async response back to Slack
    if not response_url:
        return {
            "response_type": "ephemeral",
            "text": ":x: Missing response_url. This slash command cannot process async responses.",
        }

    # user_id and channel_id are required for audit logging and context
    if not user_id or not channel_id:
        return {
            "response_type": "ephemeral",
            "text": ":x: Missing user_id or channel_id. Cannot process request.",
        }

    log.info(
        "slack_command_received",
        request_id=request_id,
        command=command,
        user_id=user_id,
        channel_id=channel_id,
        team_id=team_id,
        question_length=len(question),
    )

    # Queue background task for async processing
    background_tasks.add_task(
        process_slack_query,
        question=question,
        user_id=user_id,
        channel_id=channel_id,
        response_url=response_url,
        request_id=request_id or "unknown",
    )

    # Return immediate acknowledgment
    return {
        "response_type": "ephemeral",
        "text": ":mag: Searching license agreements...",
    }
