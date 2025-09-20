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
            print(f"📤 Registering user ID: {self.user_id}")

            # Real server doesn't send confirmation for UID registration
            # Just assume success if we got this far without error
            print("✅ User ID registered (no confirmation expected)")
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

            # Wait for the first response (LLM response)
            llm_response = await self._receive_llm_response()
            if llm_response:
                print(f"📥 Received: {llm_response}")

                # After LLM response, the real server may send additional data
                # (audio header + audio bytes) that we need to consume and ignore
                # Only try this if we're still connected
                if self.connected:
                    await self._consume_additional_server_data()

                return llm_response
            else:
                print("❌ No LLM response received from voice manager")
                return None

        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection to voice manager was closed")
            self.connected = False
            return None
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return None

    async def _receive_llm_response(self) -> Optional[str]:
        """
        Receive and parse the LLM response message from the voice manager.

        Returns:
            LLM response string if successful, None if failed
        """
        response = await self._receive_message()
        if response and response.get("command") == "LLM" and "message" in response:
            llm_response = response["message"]
            self.last_response = response
            return llm_response
        elif response:
            print(f"❌ Unexpected response format: {response}")
            return None
        else:
            return None

    async def _consume_additional_server_data(self):
        """
        Consume additional data that the real server sends after LLM response.
        This includes audio header (JSON) and audio bytes (binary data).

        The mock server doesn't send this additional data, so we handle both cases.
        """
        if not self.connected:
            print("📝 Not connected - skipping additional data consumption")
            return

        try:
            # Try to receive audio header message (JSON format)
            # Set a short timeout since mock server won't send this
            header_message = await asyncio.wait_for(
                self._receive_message_or_bytes(), timeout=1.0
            )

            if not self.connected:
                print("📝 Connection lost during audio header reception")
                return

            if header_message:
                if isinstance(header_message, dict):
                    # This is the audio header JSON message
                    print(
                        f"🎵 Received audio header (ignoring): client_id={header_message.get('client_id', 'unknown')}"
                    )

                    # Try to receive audio bytes only if still connected
                    if self.connected:
                        try:
                            audio_data = await asyncio.wait_for(
                                self._receive_message_or_bytes(), timeout=2.0
                            )

                            if audio_data and isinstance(audio_data, bytes):
                                print(
                                    f"🎵 Received audio data: {len(audio_data)} bytes (ignoring)"
                                )
                            elif audio_data:
                                print(
                                    f"❓ Unexpected data type after header: {type(audio_data)}"
                                )
                        except asyncio.TimeoutError:
                            print("📝 No audio data received (timeout)")
                        except websockets.exceptions.ConnectionClosed:
                            print("📝 Connection closed while receiving audio data")
                            self.connected = False

                elif isinstance(header_message, bytes):
                    # Sometimes the header and audio might come as one binary message
                    print(
                        f"🎵 Received binary data: {len(header_message)} bytes (ignoring)"
                    )

        except asyncio.TimeoutError:
            # This is expected for mock server - no additional data sent
            print("📝 No additional server data (mock server mode)")
        except websockets.exceptions.ConnectionClosed:
            print("📝 Connection closed while consuming additional data")
            self.connected = False
        except Exception as e:
            print(f"⚠️ Error consuming additional server data: {e}")
            # Don't mark as disconnected for other errors - might be recoverable

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
            return json.loads(message)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON received: {e}")
            return None
        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection closed while receiving message")
            self.connected = False
            return None

    async def _receive_message_or_bytes(self) -> Optional[Any]:
        """
        Receive a message that could be either JSON or binary data.

        Returns:
            Dict if JSON message, bytes if binary data, None if error
        """
        if not self.websocket:
            return None

        try:
            message = await self.websocket.recv()

            # Try to parse as JSON first
            if isinstance(message, str):
                try:
                    return json.loads(message)
                except json.JSONDecodeError:
                    # If it's a string but not valid JSON, return as is
                    return message
            elif isinstance(message, bytes):
                # Try to decode as JSON string first
                try:
                    decoded = message.decode("utf-8")
                    return json.loads(decoded)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # If it's not JSON, return as binary data
                    return message
            else:
                return message

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
