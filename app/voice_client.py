"""
Voice Manager Client for MPT AI E2E Tester

Handles websocket communication with the voice manager.
"""

import asyncio
import json
import websockets
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv


class VoiceManagerClient:
    """Client for communicating with the voice manager via websockets."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user_id: Optional[str] = None,
    ):
        """
        Initialize the voice manager client.

        Args:
            host: Voice manager host (defaults to env var or localhost)
            port: Voice manager port (defaults to env var or 8070)
            user_id: User ID (defaults to env var or test_user)
        """
        # Load environment variables
        load_dotenv()

        self.host = host or os.getenv("VOICE_MANAGER_IP", "localhost")
        self.port = int(port or os.getenv("VOICE_MANAGER_PORT", "8070"))
        self.user_id = user_id or os.getenv("USER_ID", "test_user")

        self.websocket = None
        self.connected = False
        self.last_response = None
        self.message_callback = None
        self.listener_task = None
        self._prefetched_messages = []  # buffer for messages read during connect()

    async def connect(self) -> bool:
        """
        Connect to the voice manager and register user ID.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            uri = f"ws://{self.host}:{self.port}/ws"
            print(f"🔌 Connecting to voice manager at {uri}...")

            # Connect to websocket
            self.websocket = await websockets.connect(uri)
            print("✅ Connected to voice manager")

            # Send UID registration with new format: {"command": "UID", "message": "user_id"}
            uid_message = {"command": "UID", "message": self.user_id}
            await self._send_message(uid_message)
            print(f"📤 Registering user ID (new format): {self.user_id}")

            # Try to detect mock server error and fall back to legacy UID format
            try:
                incoming = await asyncio.wait_for(self.websocket.recv(), timeout=0.3)
                if isinstance(incoming, (bytes, bytearray)):
                    # Buffer binary too in case upper layers expect it
                    self._prefetched_messages.append(incoming)
                else:
                    try:
                        data = json.loads(incoming)
                        if isinstance(data, dict) and "ERROR" in data:
                            error_msg = str(data.get("ERROR"))
                            # Mock server expects legacy UID format: {"UID": "..."}
                            if (
                                "UID" in error_msg
                                or "First message must contain UID" in error_msg
                            ):
                                print(
                                    "ℹ️ Falling back to legacy UID registration format"
                                )
                                await self._send_legacy_uid()
                        else:
                            # Not an error: buffer for later consumption by send_user_message
                            self._prefetched_messages.append(incoming)
                    except Exception:
                        # Non-JSON: buffer as-is
                        self._prefetched_messages.append(incoming)
            except asyncio.TimeoutError:
                # No immediate error — proceed normally (real server case)
                pass
            except websockets.exceptions.ConnectionClosed:
                # Server closed after wrong UID format — try reconnect with legacy UID
                print(
                    "ℹ️ Server closed after UID registration, retrying with legacy format..."
                )
                if not await self._reconnect_with_legacy_uid(uri):
                    return False

            # If we got here, consider registration successful
            print("✅ User ID registered")
            self.connected = True
            return True

        except ConnectionRefusedError:
            print(
                f"❌ Connection refused. Is the voice manager running on {self.host}:{self.port}?"
            )
            return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    async def _send_legacy_uid(self) -> None:
        """Send legacy UID registration expected by the mock server: {"UID": "..."}."""
        legacy = {"UID": self.user_id}
        await self._send_message(legacy)
        print(f"📤 Registering user ID (legacy format): {self.user_id}")

    async def _reconnect_with_legacy_uid(self, uri: str) -> bool:
        """Reconnect and register using legacy UID format for mock server compatibility."""
        try:
            # Ensure previous socket is closed
            if self.websocket and self.websocket.close_code is None:
                try:
                    await self.websocket.close()
                except Exception:
                    pass
            self.websocket = await websockets.connect(uri)
            await self._send_legacy_uid()
            self.connected = True
            return True
        except Exception as e:
            print(f"❌ Legacy UID reconnect failed: {e}")
            self.connected = False
            return False

    async def send_user_message(self, prompt: str) -> Optional[str]:
        """
        Send a user message to the voice manager and wait for synchronous response.

        The real server sends multiple messages after a USER message:
        1. LLM response: {"command": "LLM", "message": "response"}
        2. Audio header: {"client_id": "...", "audio_id": "...", ...}
        3. Audio bytes (binary data)

        Args:
            prompt: User prompt to send

        Returns:
            LLM response string if successful, None if failed
        """
        if not self.connected:
            print("❌ Not connected to voice manager")
            return None

        try:
            # Send user message with new format: {"command": "USER", "message": "content"}
            user_message = {"command": "USER", "message": prompt}
            await self._send_message(user_message)
            print(f"📤 Sent: {prompt}")

            # The server might send responses in different orders:
            # 1. LLM response first, then audio data
            # 2. Audio data mixed with LLM response
            # We need to keep reading until we get the LLM response

            llm_response = None
            max_attempts = 5  # Prevent infinite loop
            attempts = 0

            while attempts < max_attempts and self.connected:
                attempts += 1
                response = await self._receive_command_message()

                if response is None:
                    continue

                if isinstance(response, dict):
                    command = response.get("command")
                    message = response.get("message", "")

                    if command in ["LLM", "SPEAK", "WRONG"]:
                        llm_response = message
                        self.last_response = response
                        print(f"📥 Received {command}: {llm_response}")
                        break
                    else:
                        print(f"🎵 Ignoring command: {command}")
                elif isinstance(response, bytes):
                    print(f"🎵 Received binary data: {len(response)} bytes (ignoring)")
                else:
                    print(f"❓ Received unexpected data type: {type(response)}")

            if llm_response:
                # Continue consuming any remaining audio data
                if self.connected:
                    await self._consume_additional_server_data()
                return llm_response
            else:
                print(
                    "❌ No valid response received from voice manager after multiple attempts"
                )
                return None

        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection to voice manager was closed")
            self.connected = False
            return None
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return None

    async def _consume_additional_server_data(self):
        """
        Consume any remaining data that the server might send after the command response.
        The new _receive_command_message() method automatically ignores non-command data,
        so we just need to keep reading until timeout.
        """
        if not self.connected:
            return

        try:
            # Keep consuming data for a short time to clear any remaining audio data
            # The _receive_command_message method will automatically ignore non-command data
            timeout_attempts = 3
            for _ in range(timeout_attempts):
                try:
                    await asyncio.wait_for(self._receive_command_message(), timeout=0.5)
                except asyncio.TimeoutError:
                    break  # No more data to consume

        except websockets.exceptions.ConnectionClosed:
            print("📝 Connection closed while consuming additional data")
            self.connected = False
        except Exception as e:
            print(f"⚠️ Error consuming additional server data: {e}")

    def is_connected(self) -> bool:
        """
        Check if the client is connected and the websocket is still open.

        Returns:
            True if connected and websocket is open, False otherwise
        """
        return (
            self.connected
            and self.websocket is not None
            and self.websocket.close_code is None
        )

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to the voice manager.

        Returns:
            True if reconnection successful, False otherwise
        """
        print("🔄 Attempting to reconnect to voice manager...")

        # Clean up existing connection
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass  # Ignore errors during cleanup

        self.websocket = None
        self.connected = False

        # Attempt new connection
        return await self.connect()

    async def _message_listener(self):
        """Background task to listen for asynchronous messages from the server."""
        try:
            while self.connected and self.websocket:
                try:
                    message = await self.websocket.recv()
                    data = json.loads(message)

                    # Handle LLM responses with new format: {"command": "LLM", "message": "response"}
                    if data.get("command") == "LLM" and "message" in data:
                        llm_response = data["message"]
                        print(f"📥 Received: {llm_response}")
                        self.last_response = data

                        # Call callback if set
                        if self.message_callback:
                            self.message_callback(data)
                    else:
                        print(f"❌ Unexpected message format: {data}")

                except websockets.exceptions.ConnectionClosed:
                    print("🔌 Connection closed by server")
                    self.connected = False
                    break
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON received: {e}")
                except Exception as e:
                    print(f"❌ Error in message listener: {e}")

        except Exception as e:
            print(f"❌ Message listener error: {e}")
        finally:
            self.connected = False

    def set_message_callback(self, callback):
        """Set a callback function to handle incoming messages."""
        self.message_callback = callback

    async def disconnect(self):
        """Disconnect from the voice manager."""
        self.connected = False

        # Close websocket
        if self.websocket and self.websocket.close_code is None:
            await self.websocket.close()
            print("🔌 Disconnected from voice manager")

        self.websocket = None

    async def _send_message(self, data: Dict[str, Any]):
        """Send a JSON message to the voice manager."""
        if not self.websocket:
            raise RuntimeError("Not connected to voice manager")

        message = json.dumps(data)
        await self.websocket.send(message)

    async def _receive_message(self) -> Optional[Dict[str, Any]]:
        """Receive and parse a JSON message from the voice manager."""
        if not self.websocket:
            return None

        try:
            message = await self.websocket.recv()

            # Handle binary data (audio bytes) that might come instead of JSON
            if isinstance(message, bytes):
                print(
                    f"🎵 Received binary data instead of JSON: {len(message)} bytes (ignoring)"
                )
                return None

            return json.loads(message)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON received: {e}")
            # The message might be binary data that we should ignore
            return None
        except UnicodeDecodeError as e:
            print(f"🎵 Received binary audio data: {e} (ignoring)")
            return None
        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection closed while receiving message")
            self.connected = False
            return None

    async def _receive_command_message(self) -> Optional[Dict[str, Any]]:
        """
        Receive and parse only valid command messages from the voice manager.
        Ignores anything that doesn't start with {"command".

        Returns:
            Dict if valid command message, None otherwise
        """
        if not self.websocket:
            return None

        try:
            if self._prefetched_messages:
                message = self._prefetched_messages.pop(0)
            else:
                message = await self.websocket.recv()

            # Handle binary data - ignore it
            if isinstance(message, bytes):
                print(f"🎵 Ignoring binary data: {len(message)} bytes")
                return None

            # Handle string messages
            if isinstance(message, str):
                # Only process messages that start with {"command"
                if not message.strip().startswith('{"command"'):
                    print(f"🎵 Ignoring non-command message: {message[:50]}...")
                    return None

                try:
                    parsed = json.loads(message)
                    # Double-check it's a valid command message
                    if isinstance(parsed, dict) and "command" in parsed:
                        return parsed
                    else:
                        print("🎵 Ignoring message without command field")
                        return None
                except json.JSONDecodeError:
                    print("🎵 Ignoring invalid JSON message")
                    return None

            # Ignore any other data types
            print(f"🎵 Ignoring unknown message type: {type(message)}")
            return None

        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection closed while receiving message")
            self.connected = False
            return None
        except Exception as e:
            print(f"❌ Error receiving message: {e}")
            return None

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        return {
            "host": self.host,
            "port": self.port,
            "user_id": self.user_id,
            "connected": self.connected,
            "uri": f"ws://{self.host}:{self.port}/ws",
        }


async def test_connection():
    """Test function to verify voice manager connection."""
    client = VoiceManagerClient()

    print("🧪 Testing voice manager connection...")
    print(f"📋 Connection info: {client.get_connection_info()}")

    try:
        # Connect
        if await client.connect():
            print("✅ Connection test passed")

            # Send a test message
            response = await client.send_user_message("Hello, this is a test message")
            if response:
                print("✅ Message test passed")
            else:
                print("❌ Message test failed")
        else:
            print("❌ Connection test failed")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")

    finally:
        await client.disconnect()


if __name__ == "__main__":
    # Run connection test
    asyncio.run(test_connection())
