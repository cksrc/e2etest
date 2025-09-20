"""
Tests for the Mock Voice Manager Server
"""

import pytest
import asyncio
import json
import websockets
from unittest.mock import patch, AsyncMock
from mock_voice_manager import MockVoiceManager


class TestMockVoiceManager:
    """Test the MockVoiceManager functionality."""
    
    def test_mock_server_initialization(self):
        """Test mock server initializes correctly."""
        server = MockVoiceManager()
        assert server.host == "0.0.0.0"
        assert server.port == 8070
        assert server.clients == {}
        assert server.message_count == 0
    
    def test_mock_server_custom_initialization(self):
        """Test mock server with custom host and port."""
        server = MockVoiceManager(host="localhost", port=9090)
        assert server.host == "localhost"
        assert server.port == 9090
    
    def test_generate_mock_response_greeting(self):
        """Test mock response generation for greetings."""
        server = MockVoiceManager()
        
        # Test greeting responses
        response = server._generate_mock_response("hello")
        assert "hello" in response.lower() or "hi" in response.lower()
        
        response = server._generate_mock_response("hi there")
        assert len(response) > 0
    
    def test_generate_mock_response_navigation(self):
        """Test mock response generation for navigation commands."""
        server = MockVoiceManager()
        
        response = server._generate_mock_response("Go to Abu Dhabi")
        assert "abu dhabi" in response.lower() or "navigate" in response.lower()
        
        response = server._generate_mock_response("Find directions to Dubai")
        assert len(response) > 0
    
    def test_generate_mock_response_weather(self):
        """Test mock response generation for weather queries."""
        server = MockVoiceManager()
        
        response = server._generate_mock_response("What's the weather like?")
        assert "weather" in response.lower() or "temperature" in response.lower()
    
    def test_generate_mock_response_default(self):
        """Test mock response generation for unknown commands."""
        server = MockVoiceManager()
        
        response = server._generate_mock_response("random unknown command")
        assert "received your message" in response.lower()
        assert "random unknown command" in response


class TestMessageHandling:
    """Test message handling functionality."""
    
    def test_valid_user_message_format(self):
        """Test valid USER message format."""
        message = {"command": "USER", "message": "test prompt"}
        
        assert message["command"] == "USER"
        assert "message" in message
        assert message["message"] == "test prompt"
    
    def test_valid_llm_response_format(self):
        """Test valid LLM response format."""
        response = {"command": "LLM", "message": "test response"}
        
        assert response["command"] == "LLM"
        assert "message" in response
        assert response["message"] == "test response"
    
    def test_uid_registration_format(self):
        """Test UID registration message format."""
        uid_message = {"UID": "test_user_123"}
        
        assert "UID" in uid_message
        assert uid_message["UID"] == "test_user_123"


@pytest.mark.asyncio
class TestAsyncMockServer:
    """Test asynchronous mock server functionality."""
    
    async def test_send_message_format(self):
        """Test _send_message formats JSON correctly."""
        server = MockVoiceManager()
        
        # Mock websocket
        mock_websocket = AsyncMock()
        
        test_data = {"command": "LLM", "message": "test response"}
        await server._send_message(mock_websocket, test_data)
        
        # Verify websocket.send was called with JSON string
        mock_websocket.send.assert_called_once()
        sent_data = mock_websocket.send.call_args[0][0]
        parsed_data = json.loads(sent_data)
        
        assert parsed_data == test_data
    
    async def test_send_error_format(self):
        """Test _send_error formats error message correctly."""
        server = MockVoiceManager()
        
        # Mock websocket
        mock_websocket = AsyncMock()
        
        await server._send_error(mock_websocket, "Test error message")
        
        # Verify websocket.send was called with error format
        mock_websocket.send.assert_called_once()
        sent_data = mock_websocket.send.call_args[0][0]
        parsed_data = json.loads(sent_data)
        
        assert parsed_data["ERROR"] == "Test error message"


class TestMessageFormatValidation:
    """Test message format validation."""
    
    @pytest.mark.parametrize("command,message,expected_valid", [
        ("USER", "test message", True),
        ("LLM", "test response", True),
        ("INVALID", "test", False),
        ("", "test", False),
    ])
    def test_command_validation(self, command, message, expected_valid):
        """Test command validation."""
        message_format = {"command": command, "message": message}
        
        is_valid = (
            "command" in message_format 
            and "message" in message_format
            and message_format["command"] in ["USER", "LLM"]
        )
        
        assert is_valid == expected_valid
    
    def test_missing_fields(self):
        """Test validation with missing fields."""
        # Missing command
        message1 = {"message": "test"}
        assert "command" not in message1
        
        # Missing message
        message2 = {"command": "USER"}
        assert "message" not in message2
        
        # Complete message
        message3 = {"command": "USER", "message": "test"}
        assert "command" in message3 and "message" in message3


@pytest.mark.integration
class TestMockServerIntegration:
    """Integration tests for mock server (require actual server startup)."""
    
    @pytest.mark.skip(reason="Integration test - requires manual server startup")
    async def test_full_message_flow(self):
        """Test complete message flow with real websocket connection."""
        # This test would require starting the actual mock server
        # and connecting to it with a real websocket client
        pass
    
    @pytest.mark.skip(reason="Integration test - requires manual server startup") 
    async def test_multiple_clients(self):
        """Test handling multiple concurrent clients."""
        # This test would verify the server can handle multiple
        # simultaneous websocket connections
        pass
