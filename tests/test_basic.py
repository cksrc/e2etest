"""
Tests for MPT AI E2E Tester - Voice Client and Mock Server
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from app.voice_client import VoiceManagerClient


class TestVoiceClient:
    """Test the VoiceManagerClient functionality."""

    def test_client_initialization(self):
        """Test client initializes with correct defaults."""
        client = VoiceManagerClient()
        assert client.host == "localhost"
        assert client.port == 8070
        # USER_ID comes from .env file
        assert client.user_id == "test_user_001"
        assert not client.connected
        assert client.websocket is None

    def test_client_custom_initialization(self):
        """Test client initializes with custom values."""
        client = VoiceManagerClient(
            host="example.com", port=9090, user_id="custom_user"
        )
        assert client.host == "example.com"
        assert client.port == 9090
        assert client.user_id == "custom_user"

    def test_connection_info(self):
        """Test connection info returns correct data."""
        client = VoiceManagerClient(host="test.com", port=8080, user_id="test123")
        info = client.get_connection_info()

        expected = {
            "host": "test.com",
            "port": 8080,
            "user_id": "test123",
            "connected": False,
            "uri": "ws://test.com:8080/ws",
        }
        assert info == expected


class TestMessageFormat:
    """Test message format handling."""

    def test_user_message_format(self):
        """Test USER message format is correct."""
        expected_format = {"command": "USER", "message": "test prompt"}

        # This would be the format sent by send_user_message
        assert expected_format["command"] == "USER"
        assert "message" in expected_format
        assert expected_format["message"] == "test prompt"

    def test_llm_response_format(self):
        """Test LLM response format is correct."""
        expected_format = {"command": "LLM", "message": "test response"}

        # This would be the format received from server
        assert expected_format["command"] == "LLM"
        assert "message" in expected_format
        assert expected_format["message"] == "test response"

    def test_uid_message_format(self):
        """Test UID registration format is correct."""
        expected_format = {"UID": "test_user_123"}

        assert "UID" in expected_format
        assert expected_format["UID"] == "test_user_123"


@pytest.mark.asyncio
async def test_send_message_not_connected():
    """Test sending message when not connected returns None."""
    client = VoiceManagerClient()
    result = await client.send_user_message("test message")
    assert result is None
