#!/usr/bin/env python3
"""
Mock Voice Manager Server for MPT AI E2E Tester

This mock server simulates the voice manager by:
1. Establishing websocket connections
2. Expecting initial UID message
3. Listening for USER messages
4. Responding with LLM messages
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime
from typing import Dict, Any, Optional


class MockVoiceManager:
    """Mock voice manager server that handles websocket connections."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8070):
        """
        Initialize the mock voice manager.

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.clients = {}  # Store connected clients by UID
        self.message_count = 0

        # Setup logging
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

    async def handle_client(self, websocket):
        """
        Handle a client websocket connection.

        Args:
            websocket: WebSocket connection
        """
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.logger.info(f"New connection from {client_address}")

        uid = None
        try:
            # Wait for initial UID message
            uid = await self._wait_for_uid(websocket)
            if not uid:
                return

            # Store client
            self.clients[uid] = {
                "websocket": websocket,
                "address": client_address,
                "connected_at": datetime.now(),
                "message_count": 0,
            }

            self.logger.info(f"Client {uid} registered from {client_address}")

            # Handle messages from this client
            await self._handle_messages(websocket, uid)

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Client {uid or client_address} disconnected")
        except Exception as e:
            self.logger.error(f"Error handling client {uid or client_address}: {e}")
        finally:
            # Clean up client
            if uid and uid in self.clients:
                del self.clients[uid]
                self.logger.info(f"Client {uid} removed from registry")

    async def _wait_for_uid(self, websocket) -> Optional[str]:
        """
        Wait for the initial UID message from client.

        Args:
            websocket: WebSocket connection

        Returns:
            UID string if received, None if invalid
        """
        try:
            # Wait for first message with timeout
            message = await asyncio.wait_for(websocket.recv(), timeout=30.0)

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await self._send_error(websocket, "Invalid JSON format")
                return None

            if "UID" not in data:
                await self._send_error(websocket, "First message must contain UID")
                return None

            uid = data["UID"]
            if not uid or not isinstance(uid, str):
                await self._send_error(websocket, "UID must be a non-empty string")
                return None

            # Real server doesn't send UID confirmation, so we don't either
            self.logger.info(f"UID {uid} registered (no confirmation sent)")

            return uid

        except asyncio.TimeoutError:
            await self._send_error(websocket, "Timeout waiting for UID")
            return None
        except Exception as e:
            self.logger.error(f"Error waiting for UID: {e}")
            return None

    async def _handle_messages(self, websocket, uid: str):
        """
        Handle messages from a registered client.

        Args:
            websocket: WebSocket connection
            uid: Client UID
        """
        async for message in websocket:
            try:
                self.message_count += 1
                self.clients[uid]["message_count"] += 1

                self.logger.info(f"Received message from {uid}: {message}")

                # Parse message
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON format")
                    continue

                # Handle messages with new format: {"command": "USER", "message": "content"}
                if "command" in data and "message" in data:
                    if data["command"] == "USER":
                        await self._handle_user_message(websocket, uid, data["message"])
                    else:
                        await self._send_error(
                            websocket,
                            f"Unknown command: {data['command']}. Expected 'USER'.",
                        )
                else:
                    await self._send_error(
                        websocket,
                        "Invalid message format. Expected: {'command': 'USER', 'message': 'content'}",
                    )

            except Exception as e:
                self.logger.error(f"Error processing message from {uid}: {e}")
                await self._send_error(websocket, f"Error processing message: {str(e)}")

    async def _handle_user_message(self, websocket, uid: str, user_prompt: str):
        """
        Handle a USER message and generate synchronous LLM response.

        Args:
            websocket: WebSocket connection
            uid: Client UID
            user_prompt: User's prompt/message
        """
        self.logger.info(f"Processing USER message from {uid}: '{user_prompt}'")

        # Generate mock LLM response based on the prompt
        llm_response = self._generate_mock_response(user_prompt)

        # Send immediate synchronous LLM response: {"command": "LLM", "message": "response"}
        response = {"command": "LLM", "message": llm_response}
        await self._send_message(websocket, response)

        self.logger.info(f"Sent synchronous LLM response to {uid}: '{llm_response}'")

    def _generate_mock_response(self, user_prompt: str) -> str:
        """
        Generate a mock LLM response based on user prompt.

        Args:
            user_prompt: User's input prompt

        Returns:
            Mock LLM response string
        """
        prompt_lower = user_prompt.lower()

        # Simple response patterns for testing
        if "hello" in prompt_lower or "hi" in prompt_lower:
            return "Hello! How can I assist you today?"

        elif "weather" in prompt_lower:
            return "I'm a mock voice manager, so I can't check real weather. But let's pretend it's sunny!"

        elif "test" in prompt_lower:
            return "This is a test response from the mock voice manager. Everything is working correctly!"

        elif "time" in prompt_lower:
            current_time = datetime.now().strftime("%H:%M:%S")
            return f"The current time is {current_time}."

        elif "help" in prompt_lower:
            return "I'm a mock voice manager for testing. I can respond to various prompts like hello, weather, test, and time."

        elif "goodbye" in prompt_lower or "bye" in prompt_lower:
            return "Goodbye! Thanks for testing the mock voice manager."

        else:
            return f"I received your message: '{user_prompt}'. This is a mock response from the voice manager."

    async def _send_message(self, websocket, data: Dict[str, Any]):
        """
        Send a JSON message to the client.

        Args:
            websocket: WebSocket connection
            data: Data to send as JSON
        """
        message = json.dumps(data)
        await websocket.send(message)

    async def _send_error(self, websocket, error_message: str):
        """
        Send an error message to the client.

        Args:
            websocket: WebSocket connection
            error_message: Error message to send
        """
        error_data = {"ERROR": error_message}
        await self._send_message(websocket, error_data)

    def print_status(self):
        """Print current server status."""
        print(f"\n{'='*50}")
        print("Mock Voice Manager Status")
        print(f"{'='*50}")
        print(f"Listening on: {self.host}:{self.port}")
        print(f"Connected clients: {len(self.clients)}")
        print(f"Total messages processed: {self.message_count}")

        if self.clients:
            print("\nActive clients:")
            for uid, client_info in self.clients.items():
                print(
                    f"  - {uid}: {client_info['address']} ({client_info['message_count']} messages)"
                )

        print(f"{'='*50}\n")

    async def start_server(self):
        """Start the websocket server."""
        self.logger.info(f"Starting Mock Voice Manager on {self.host}:{self.port}")

        # Start websocket server
        server = await websockets.serve(self.handle_client, self.host, self.port)

        print(f"🤖 Mock Voice Manager Server Started (Synchronous Mode)")
        print(f"📡 Listening on ws://{self.host}:{self.port}")
        print(f"📋 Expected message format:")
        print(f'   1. First message: {{"UID": "user_id_here"}}')
        print(
            '   2. User messages: {"command": "USER", "message": "user prompt goes here"}'
        )
        print(
            '   3. Server responds synchronously: {"command": "LLM", "message": "Response from LLM"}'
        )
        print(f"\n🔄 Server is running... Press Ctrl+C to stop")

        try:
            # Keep server running
            await server.wait_closed()
        except KeyboardInterrupt:
            self.logger.info("Server shutdown requested")
            server.close()
            await server.wait_closed()
            print("\n🛑 Mock Voice Manager Server stopped")


async def main():
    """Main function to run the mock voice manager server."""
    # Create and start the mock voice manager
    voice_manager = MockVoiceManager()

    # Print status every 30 seconds
    async def status_printer():
        while True:
            await asyncio.sleep(30)
            voice_manager.print_status()

    # Run server and status printer concurrently
    await asyncio.gather(voice_manager.start_server(), status_printer())


if __name__ == "__main__":
    asyncio.run(main())
