"""
Integration tests for the complete voice client and mock server flow
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.voice_client import VoiceManagerClient


class TestVoiceClientIntegration:
    """Integration tests for VoiceManagerClient with mocked websocket."""

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock websocket for testing."""
        mock_ws = AsyncMock()
        mock_ws.close_code = None
        return mock_ws

    @pytest.fixture
    def client(self):
        """Create a VoiceManagerClient for testing."""
        return VoiceManagerClient(host="localhost", port=8070, user_id="test_user")

    async def test_successful_connection_flow(self, client, mock_websocket):
        """Test successful connection and UID registration."""
        # Mock websockets.connect to return the mock websocket directly
        with patch(
            "websockets.connect", new_callable=AsyncMock, return_value=mock_websocket
        ):
            result = await client.connect()

            assert result is True
            assert client.connected is True
            assert client.websocket == mock_websocket

            # Verify UID registration message was sent
            mock_websocket.send.assert_called_once()
            sent_message = mock_websocket.send.call_args[0][0]
            parsed_message = json.loads(sent_message)

            assert parsed_message == {"command": "UID", "message": "test_user"}

    async def test_send_user_message_success(self, client, mock_websocket):
        """Test successful user message sending and response."""
        # Setup mock response - need to handle the timeout for additional data
        mock_response = {"command": "LLM", "message": "I'll help you with that!"}
        mock_websocket.recv.side_effect = [
            json.dumps(mock_response),  # First call: LLM response
            asyncio.TimeoutError(),  # Second call: timeout for additional data (mock server behavior)
        ]

        with patch(
            "websockets.connect", new_callable=AsyncMock, return_value=mock_websocket
        ):
            # Connect first
            await client.connect()
            mock_websocket.send.reset_mock()  # Reset to ignore UID message
            mock_websocket.recv.side_effect = [
                json.dumps(mock_response),  # Reset side_effect for the actual test
                asyncio.TimeoutError(),
            ]

            # Send user message
            result = await client.send_user_message("Go to Abu Dhabi")

            assert result == "I'll help you with that!"
            assert client.last_response == mock_response

            # Verify message was sent in correct format
            mock_websocket.send.assert_called_once()
            sent_message = mock_websocket.send.call_args[0][0]
            parsed_message = json.loads(sent_message)

            expected_message = {"command": "USER", "message": "Go to Abu Dhabi"}
            assert parsed_message == expected_message

    async def test_send_user_message_invalid_response(self, client, mock_websocket):
        """Test handling of invalid response format."""
        # Setup invalid mock response
        mock_response = {"invalid": "format"}
        mock_websocket.recv.side_effect = [
            json.dumps(mock_response),  # Invalid response
            asyncio.TimeoutError(),  # Timeout for additional data
        ]

        with patch(
            "websockets.connect", new_callable=AsyncMock, return_value=mock_websocket
        ):
            await client.connect()
            mock_websocket.send.reset_mock()
            mock_websocket.recv.side_effect = [
                json.dumps(mock_response),
                asyncio.TimeoutError(),
            ]

            result = await client.send_user_message("Test message")

            assert result is None

    async def test_send_user_message_not_connected(self, client):
        """Test sending message when not connected."""
        result = await client.send_user_message("Test message")
        assert result is None

    async def test_disconnect_flow(self, client, mock_websocket):
        """Test proper disconnection."""
        with patch(
            "websockets.connect", new_callable=AsyncMock, return_value=mock_websocket
        ):
            await client.connect()
            assert client.connected is True

            await client.disconnect()

            assert client.connected is False
            assert client.websocket is None
            mock_websocket.close.assert_called_once()

    async def test_connection_refused(self, client):
        """Test handling of connection refused error."""
        with patch("websockets.connect", side_effect=ConnectionRefusedError()):
            result = await client.connect()

            assert result is False
            assert client.connected is False

    async def test_websocket_connection_closed_during_send(
        self, client, mock_websocket
    ):
        """Test handling of connection closed during message send."""
        import websockets.exceptions

        mock_websocket.send.side_effect = websockets.exceptions.ConnectionClosed(
            None, None
        )

        with patch(
            "websockets.connect", new_callable=AsyncMock, return_value=mock_websocket
        ):
            await client.connect()

            result = await client.send_user_message("Test message")

            assert result is None
            assert client.connected is False

    async def test_send_user_message_with_audio_data(self, client, mock_websocket):
        """Test handling of real server response with audio header and audio bytes."""
        # Setup mock responses in sequence
        llm_response = {"command": "LLM", "message": "Location set: Cyprus."}
        audio_header = {
            "client_id": "2d4665c7-f020-4e68-a444-5a36c473bbfa",
            "audio_id": "b9372316-ff61-4be1-bb81-8df97758fe18",
            "slice": 1,
            "total": 1,
            "message": "Location set Cyprus",
            "table": None,
            "list": None,
            "long": None,
            "duration": 1.5146666666666666,
        }
        audio_bytes = b"fake_audio_data" * 1000  # Simulate 71KB of audio data

        # Mock recv to return responses in sequence
        mock_websocket.recv.side_effect = [
            json.dumps(llm_response),  # First: LLM response
            json.dumps(audio_header),  # Second: Audio header
            audio_bytes,  # Third: Audio bytes
        ]

        with patch(
            "websockets.connect", new_callable=AsyncMock, return_value=mock_websocket
        ):
            # Connect first
            await client.connect()
            mock_websocket.send.reset_mock()  # Reset to ignore UID message

            # Send user message
            result = await client.send_user_message("Go To cyprus")

            # Should return the LLM response and handle audio data gracefully
            assert result == "Location set: Cyprus."
            assert client.last_response == llm_response

            # Verify message was sent in correct format
            mock_websocket.send.assert_called_once()
            sent_message = mock_websocket.send.call_args[0][0]
            parsed_message = json.loads(sent_message)

            expected_message = {"command": "USER", "message": "Go To cyprus"}
            assert parsed_message == expected_message

    async def test_send_user_message_mock_server_no_audio(self, client, mock_websocket):
        """Test handling of mock server response (no audio data)."""
        # Setup mock response (only LLM response, no audio)
        mock_response = {"command": "LLM", "message": "I'll help you with that!"}

        # Mock recv to return only LLM response, then timeout for additional data
        mock_websocket.recv.side_effect = [
            json.dumps(mock_response),  # First: LLM response
            asyncio.TimeoutError(),  # No additional data (mock server behavior)
        ]

        with patch(
            "websockets.connect", new_callable=AsyncMock, return_value=mock_websocket
        ):
            # Connect first
            await client.connect()
            mock_websocket.send.reset_mock()  # Reset to ignore UID message

            # Send user message
            result = await client.send_user_message("Test message")

            # Should return the LLM response and handle timeout gracefully
            assert result == "I'll help you with that!"
            assert client.last_response == mock_response


class TestMessageFormatIntegration:
    """Test message format handling in integration scenarios."""

    def test_uid_message_serialization(self):
        """Test UID message can be properly serialized."""
        uid_message = {"command": "UID", "message": "test_user_123"}
        serialized = json.dumps(uid_message)
        deserialized = json.loads(serialized)

        assert deserialized == uid_message

    def test_user_message_serialization(self):
        """Test USER message can be properly serialized."""
        user_message = {"command": "USER", "message": "Navigate to Dubai"}
        serialized = json.dumps(user_message)
        deserialized = json.loads(serialized)

        assert deserialized == user_message

    def test_llm_response_serialization(self):
        """Test LLM response can be properly serialized."""
        llm_response = {
            "command": "LLM",
            "message": "I'll help you navigate to Dubai. Let me find the best route for you.",
        }
        serialized = json.dumps(llm_response)
        deserialized = json.loads(serialized)

        assert deserialized == llm_response

    @pytest.mark.parametrize(
        "message,expected_valid",
        [
            ({"command": "USER", "message": "test"}, True),
            ({"command": "LLM", "message": "response"}, True),
            ({"command": "INVALID", "message": "test"}, False),
            ({"message": "test"}, False),  # Missing command
            ({"command": "USER"}, False),  # Missing message
            ({}, False),  # Empty message
        ],
    )
    def test_message_validation(self, message, expected_valid):
        """Test message format validation."""
        is_valid = (
            isinstance(message, dict)
            and "command" in message
            and "message" in message
            and message["command"] in ["USER", "LLM"]
            and isinstance(message["message"], str)
        )

        assert is_valid == expected_valid


class TestScenarioIntegration:
    """Test scenario execution integration."""

    def test_scenario_message_sequence(self):
        """Test that scenario lines can be converted to proper message format."""
        scenario_lines = ["Go to Abu Dhabi", "Check the weather", "Book a hotel"]

        # Convert to message format
        messages = []
        for line in scenario_lines:
            message = {"command": "USER", "message": line}
            messages.append(message)

        # Verify all messages are properly formatted
        for i, message in enumerate(messages):
            assert message["command"] == "USER"
            assert message["message"] == scenario_lines[i]

            # Verify serialization works
            serialized = json.dumps(message)
            deserialized = json.loads(serialized)
            assert deserialized == message
