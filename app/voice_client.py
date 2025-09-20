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

            # Send UID registration
            uid_message = {"UID": self.user_id}
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
        Send a user message and wait for LLM response.

        Args:
            prompt: User prompt to send

        Returns:
            LLM response string or None if failed
        """
        if not self.connected:
            print("❌ Not connected to voice manager")
            return None

        try:
            # Send user message
            user_message = {"USER": prompt}
            await self._send_message(user_message)
            print(f"📤 Sent: {prompt}")

            # Wait for LLM response
            response = await self._receive_message()
            if response and "LLM" in response:
                llm_response = response["LLM"]
                self.last_response = llm_response
                print(f"📥 Received: {llm_response}")
                return llm_response
            elif response and "ERROR" in response:
                print(f"❌ Error from voice manager: {response['ERROR']}")
                return None
            else:
                print(f"❌ Unexpected response format: {response}")
                return None

        except websockets.exceptions.ConnectionClosed:
            print("❌ Connection to voice manager was closed")
            self.connected = False
            return None
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return None

    async def disconnect(self):
        """Disconnect from the voice manager."""
        if self.websocket and self.websocket.close_code is None:
            await self.websocket.close()
            print("🔌 Disconnected from voice manager")

        self.connected = False
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
