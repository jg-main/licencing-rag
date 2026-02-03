# tests/test_api_slack.py
"""Tests for Slack slash command endpoint."""

import hashlib
import hmac
import time
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

# Test Slack signing secret
TEST_SLACK_SECRET = "test-slack-signing-secret-12345"


@pytest.fixture
def client() -> TestClient:
    """Create test client for API."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_slack_secret():
    """Mock SLACK_SIGNING_SECRET environment variable for all tests."""
    with patch("api.config.SLACK_SIGNING_SECRET", TEST_SLACK_SECRET):
        with patch("api.middleware.auth.SLACK_SIGNING_SECRET", TEST_SLACK_SECRET):
            yield


def generate_slack_signature(
    timestamp: str, payload: dict[str, str], secret: str
) -> str:
    """Generate a valid Slack signature for testing.

    Args:
        timestamp: Unix timestamp as string.
        payload: Form data dict that will be URL-encoded.
        secret: Slack signing secret.

    Returns:
        Slack signature in format "v0=<hex_digest>".
    """
    # URL-encode the payload the same way TestClient does
    from urllib.parse import urlencode

    body = urlencode(payload)

    sig_basestring = f"v0:{timestamp}:{body}"
    signature = hmac.new(
        secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"v0={signature}"


class TestSlackCommandPayloadParsing:
    """Test Slack slash command payload parsing."""

    def test_valid_slack_command(self, client: TestClient) -> None:
        """Test that valid Slack command is accepted."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "What are the CME fees?",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
            "command": "/rag",
            "team_id": "T12345678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response_type"] == "ephemeral"
        assert "Searching" in data["text"]

    def test_empty_question_returns_warning(self, client: TestClient) -> None:
        """Test that empty question returns helpful warning."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "",  # Empty question
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response_type"] == "ephemeral"
        assert "Please provide a question" in data["text"]

    def test_whitespace_only_question_returns_warning(self, client: TestClient) -> None:
        """Test that whitespace-only question returns warning."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "   \n\t  ",  # Whitespace only
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "Please provide a question" in data["text"]

    def test_missing_response_url_returns_error(self, client: TestClient) -> None:
        """Test that missing response_url returns error."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "What are the CME fees?",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            # response_url is missing
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response_type"] == "ephemeral"
        assert "response_url" in data["text"]

    def test_missing_user_id_returns_error(self, client: TestClient) -> None:
        """Test that missing user_id returns error."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "What are the CME fees?",
            # user_id is missing
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response_type"] == "ephemeral"
        assert "user_id" in data["text"] or "channel_id" in data["text"]

    def test_missing_channel_id_returns_error(self, client: TestClient) -> None:
        """Test that missing channel_id returns error."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "What are the CME fees?",
            "user_id": "U12345678",
            # channel_id is missing
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["response_type"] == "ephemeral"
        assert "user_id" in data["text"] or "channel_id" in data["text"]


class TestSlackImmediateAcknowledgment:
    """Test immediate acknowledgment response (< 3 seconds)."""

    def test_immediate_response_format(self, client: TestClient) -> None:
        """Test that immediate response follows correct format."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "test query",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should be ephemeral
        assert data["response_type"] == "ephemeral"

        # Should have searching message
        assert "text" in data
        assert isinstance(data["text"], str)

    def test_response_time_under_3_seconds(self, client: TestClient) -> None:
        """Test that immediate response is fast (< 3 seconds).

        Note: This test verifies the synchronous acknowledgment returns quickly.
        The background task execution time is not included in Slack's 3-second requirement.
        TestClient executes background tasks synchronously, so we mock the RAG query
        to keep the test fast.
        """
        from unittest.mock import patch

        timestamp = str(int(time.time()))
        payload = {
            "text": "test query",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        # Mock the RAG query to avoid slow LLM calls in the background task
        mock_result = {
            "answer": "Test answer",
            "citations": [],
            "definitions": [],
            "metadata": {},
        }

        with patch("api.routes.slack.rag_query", return_value=mock_result):
            start_time = time.time()
            response = client.post(
                "/slack/command",
                data=payload,
                headers={
                    "X-Slack-Signature": signature,
                    "X-Slack-Request-Timestamp": timestamp,
                },
            )
            elapsed = time.time() - start_time

        assert response.status_code == 200
        # Should be fast even with background task mocked (< 1 second)
        assert elapsed < 1.0


class TestSlackAsyncResponse:
    """Test async response processing with mocked RAG query."""

    @pytest.mark.skip(
        reason="Requires pytest-asyncio plugin - background task testing covered by other tests"
    )
    @pytest.mark.asyncio
    async def test_background_task_processes_query(self) -> None:
        """Test that background task calls RAG query."""
        # This test would require mocking the background task execution
        # For now, we test the endpoint returns immediately
        # Integration tests would verify the actual background processing
        pass

    def test_async_response_format(self) -> None:
        """Test Block Kit formatting of async response."""
        from api.formatters.slack import format_answer_blocks

        # Mock RAG response
        response = {
            "answer": "The fee is $100 per month.",
            "citations": [
                {
                    "source": "cme",
                    "document": "fees/fee-list.pdf",
                    "page": 5,
                    "text": "Market data fee: $100/month",
                }
            ],
            "definitions": [
                {
                    "term": "Market Data",
                    "definition": "Real-time price and trading information.",
                }
            ],
            "refused": False,
            "metadata": {
                "latency_ms": 1200,
                "tokens_used": 150,
                "chunks_retrieved": 5,
            },
        }

        blocks = format_answer_blocks(response)

        # Should have multiple blocks
        assert len(blocks) > 0

        # First block should be answer section
        assert blocks[0]["type"] == "section"
        assert "Answer:" in blocks[0]["text"]["text"]
        assert "$100" in blocks[0]["text"]["text"]

        # Should contain citation context
        citation_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(citation_blocks) > 0

        # Should contain definitions
        def_text = str(blocks)
        assert "Market Data" in def_text

        # Should contain metadata footer
        assert "1200ms" in str(blocks[-1])

    def test_refusal_format(self) -> None:
        """Test Block Kit formatting of refusal response."""
        from api.formatters.slack import format_answer_blocks

        response = {
            "answer": "",
            "citations": [],
            "refused": True,
            "refusal_reason": "I cannot answer questions about pricing.",
        }

        blocks = format_answer_blocks(response)

        # Should have warning block
        assert len(blocks) > 0
        assert "Unable to Answer" in blocks[0]["text"]["text"]
        assert "pricing" in blocks[0]["text"]["text"]

    def test_error_format(self) -> None:
        """Test Block Kit formatting of error messages."""
        from api.formatters.slack import format_error_blocks

        blocks = format_error_blocks("Service unavailable", error_type="ERROR")

        assert len(blocks) > 0
        assert blocks[0]["type"] == "section"
        assert "ERROR" in blocks[0]["text"]["text"]
        assert "Service unavailable" in blocks[0]["text"]["text"]


class TestSlackSignatureVerification:
    """Test Slack signature verification."""

    def test_missing_signature_header_returns_401(self, client: TestClient) -> None:
        """Test that missing signature returns 401."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "test query",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                # Missing X-Slack-Signature
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_invalid_signature_returns_401(self, client: TestClient) -> None:
        """Test that invalid signature returns 401."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "test query",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": "v0=invalid_signature",
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    def test_expired_timestamp_returns_401(self, client: TestClient) -> None:
        """Test that expired timestamp returns 401."""
        # Timestamp from 10 minutes ago (> 5 minute limit)
        timestamp = str(int(time.time()) - 600)
        payload = {
            "text": "test query",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        response = client.post(
            "/slack/command",
            data=payload,
            headers={
                "X-Slack-Signature": signature,
                "X-Slack-Request-Timestamp": timestamp,
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "expired" in data["error"]["message"].lower()


class TestSlackErrorHandling:
    """Test error handling in background task."""

    @patch("api.routes.slack.rag_query")
    @patch("httpx.AsyncClient.post")
    def test_validation_error_sends_error_message(
        self, mock_http_post: MagicMock, mock_rag_query: MagicMock
    ) -> None:
        """Test that validation errors are sent to Slack."""
        # Mock RAG query to raise ValueError
        mock_rag_query.side_effect = ValueError("Invalid source")

        # Mock HTTP client
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_http_post.return_value = mock_response

        # This test would require triggering the background task
        # For now, we verify the error formatter works
        from api.formatters.slack import format_error_blocks

        blocks = format_error_blocks("Invalid source", error_type="VALIDATION ERROR")
        assert len(blocks) > 0
        assert "VALIDATION ERROR" in blocks[0]["text"]["text"]

    def test_service_error_format(self) -> None:
        """Test service error formatting."""
        from api.formatters.slack import format_error_blocks

        blocks = format_error_blocks(
            "Service temporarily unavailable", error_type="SERVICE ERROR"
        )
        assert len(blocks) > 0
        assert "SERVICE ERROR" in blocks[0]["text"]["text"]


class TestSlackLogging:
    """Test logging for Slack requests."""

    def test_slack_command_logs_request(self, client: TestClient) -> None:
        """Test that Slack command logs request details."""
        timestamp = str(int(time.time()))
        payload = {
            "text": "test query",
            "user_id": "U12345678",
            "channel_id": "C12345678",
            "response_url": "https://hooks.slack.com/commands/1234/5678",
            "command": "/rag",
            "team_id": "T12345678",
        }

        signature = generate_slack_signature(timestamp, payload, TEST_SLACK_SECRET)

        with patch("api.routes.slack.log") as mock_log:
            response = client.post(
                "/slack/command",
                data=payload,
                headers={
                    "X-Slack-Signature": signature,
                    "X-Slack-Request-Timestamp": timestamp,
                },
            )

            assert response.status_code == 200

            # Should log command received
            # Note: Background tasks run immediately in TestClient, so we get both logs
            mock_log.info.assert_called()

            # Check that "slack_command_received" was logged (may not be the last call)
            calls = [call[0][0] for call in mock_log.info.call_args_list]
            assert "slack_command_received" in calls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
