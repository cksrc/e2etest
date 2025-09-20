#!/usr/bin/env python3
"""
MPT AI E2E Tester - Simple Command Line Interface
"""

import sys
import asyncio
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv
from app.voice_client import VoiceManagerClient


async def get_user_id():
    """Get USER_ID from .env file or prompt user for input."""
    # Load environment variables from .env file
    load_dotenv()

    # Try to get USER_ID from environment variables
    env_user_id = os.getenv("USER_ID")

    if env_user_id:
        env_user_id = env_user_id.strip()
        if env_user_id and validate_user_id(env_user_id):
            print(f"📋 Using USER_ID from .env file: {env_user_id}")
            return env_user_id
        else:
            print("⚠️  Invalid USER_ID in .env file, falling back to manual input")
    else:
        print("📝 No USER_ID found in .env file")

    # Fall back to manual input
    print("\n📝 Please enter your User ID:")
    print("💡 This will be used to identify your session with the voice manager")
    print("💡 You can also set USER_ID in your .env file to skip this step")

    while True:
        try:
            user_id = await asyncio.to_thread(input, "User ID: ")
            user_id = user_id.strip()

            if not user_id:
                print("❌ User ID cannot be empty. Please try again.")
                continue

            if validate_user_id(user_id):
                print(f"✅ User ID set to: {user_id}")
                return user_id

        except (EOFError, KeyboardInterrupt):
            print("\n❌ Operation cancelled")
            return None
        except Exception as e:
            print(f"❌ Error getting user ID: {e}")
            return None


def validate_user_id(user_id: str) -> bool:
    """Validate user ID format."""
    if not user_id:
        print("❌ User ID cannot be empty.")
        return False

    # Basic validation - no spaces, reasonable length
    if " " in user_id:
        print("❌ User ID cannot contain spaces.")
        return False

    if len(user_id) > 50:
        print("❌ User ID too long (max 50 characters).")
        return False

    return True


def get_available_scenarios():
    """Get list of available scenario files from the scenarios folder."""
    scenarios_dir = Path("scenarios")

    if not scenarios_dir.exists():
        return []

    # Find all .yaml and .yml files in scenarios directory
    scenario_files = []
    for pattern in ["*.yaml", "*.yml"]:
        scenario_files.extend(scenarios_dir.glob(pattern))

    # Sort by name for consistent ordering
    scenario_files.sort(key=lambda x: x.name)

    return scenario_files


async def select_scenario():
    """Let user select a scenario from available options."""
    print("\n📋 Available Scenarios")
    print("=" * 40)

    scenarios = get_available_scenarios()

    if not scenarios:
        print("❌ No scenario files found in the 'scenarios' folder")
        print("💡 Please add .yaml or .yml scenario files to the scenarios directory")
        return None

    # Display scenarios with numbers
    for i, scenario_file in enumerate(scenarios, 1):
        print(f"{i}. {scenario_file.name}")

    print(f"\n📝 Please select a scenario (1-{len(scenarios)}):")

    while True:
        try:
            choice = await asyncio.to_thread(input, "Scenario number: ")
            choice = choice.strip()

            if not choice:
                print("❌ Please enter a number")
                continue

            try:
                scenario_num = int(choice)
            except ValueError:
                print("❌ Please enter a valid number")
                continue

            if scenario_num < 1 or scenario_num > len(scenarios):
                print(f"❌ Please enter a number between 1 and {len(scenarios)}")
                continue

            selected_scenario = scenarios[scenario_num - 1]
            print(f"✅ Selected scenario: {selected_scenario.name}")
            return selected_scenario

        except (EOFError, KeyboardInterrupt):
            print("\n❌ Operation cancelled")
            return None
        except Exception as e:
            print(f"❌ Error selecting scenario: {e}")
            return None


async def run_interactive_mode():
    """Run the interactive mode with voice manager connection."""
    print("\n🎯 Starting Interactive Mode")
    print("=" * 40)

    # Ask for USER_ID
    user_id = await get_user_id()
    if not user_id:
        print("❌ User ID is required for interactive mode")
        return

    # Create voice manager client with the provided user ID
    client = VoiceManagerClient(user_id=user_id)

    try:
        # Attempt connection
        print("📋 Connection details:")
        connection_info = client.get_connection_info()
        print(f"   Host: {connection_info['host']}")
        print(f"   Port: {connection_info['port']}")
        # Check if USER_ID came from .env file
        env_user_id = os.getenv("USER_ID")
        source = (
            "from .env file"
            if env_user_id and env_user_id.strip() == connection_info["user_id"]
            else "provided by user"
        )
        print(f"   User ID: {connection_info['user_id']} ({source})")
        print()

        if await client.connect():
            print("🎉 Successfully connected to voice manager!")

            # Select scenario
            selected_scenario = await select_scenario()
            if not selected_scenario:
                print("❌ No scenario selected. Exiting interactive mode.")
                await client.disconnect()
                return

            print(
                f"\n🚀 Starting interactive session with scenario: {selected_scenario.name}"
            )
            print("💬 You can now interact with the voice manager")
            print("📝 Type 'quit' or 'exit' to end the session")
            print("=" * 40)

            # Interactive session with selected scenario
            await interactive_chat_session(client, selected_scenario)
        else:
            print("❌ Failed to connect to voice manager")
            print("💡 Make sure the voice manager is running:")
            print("   python mock_voice_manager.py")

    except Exception as e:
        print(f"❌ Error in interactive mode: {e}")

    finally:
        # Only disconnect if still connected (user might have disconnected manually)
        if client.is_connected():
            await client.disconnect()
        print("👋 Interactive mode ended")


def load_scenario_lines(scenario_file: Path):
    """Load scenario file and extract lines to send."""
    try:
        with open(scenario_file, "r", encoding="utf-8") as f:
            content = f.read().strip()

        # Try to parse as YAML first
        try:
            yaml_data = yaml.safe_load(content)
            if isinstance(yaml_data, dict) and "lines" in yaml_data:
                return yaml_data["lines"]
            elif isinstance(yaml_data, list):
                return yaml_data
        except yaml.YAMLError:
            pass

        # If not YAML or no 'lines' key, treat as plain text (one line per line)
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        return lines

    except Exception as e:
        print(f"❌ Error loading scenario file: {e}")
        return []


async def interactive_chat_session(client: VoiceManagerClient, scenario_file: Path):
    """Run an interactive chat session with the voice manager using the selected scenario."""
    print(f"📄 Loading scenario: {scenario_file.name}")

    # Load scenario lines
    scenario_lines = load_scenario_lines(scenario_file)

    if not scenario_lines:
        print("❌ No lines found in scenario file or failed to load")
        return

    print(f"✅ Loaded {len(scenario_lines)} lines from scenario")
    print("🎯 Interactive Mode: Each line will be sent one at a time")
    print("📝 Controls:")
    print("   • Press Enter to send the current command")
    print("   • Type 'S' or 's' to skip the current command")
    print("   • Type 'R' or 'r' to retry current command, or 'R:5' to replay line 5")
    print("   • Type 'I' or 'i' to insert and send a custom command")
    print("   • Type 'quit' or 'exit' to stop")
    print("=" * 60)

    i = 0  # Initialize counter
    while i < len(scenario_lines):
        current_line = scenario_lines[i]
        line_number = i + 1

        if not client.is_connected():
            print("❌ Connection lost to voice manager")
            print(
                "💡 The server may have closed the connection after sending audio data"
            )

            # Ask user if they want to reconnect and continue
            try:
                reconnect_choice = await asyncio.to_thread(
                    input, "🔄 Try to reconnect and continue? (y/N): "
                )
                if reconnect_choice.strip().lower() in ["y", "yes"]:
                    if await client.reconnect():
                        print("✅ Reconnected successfully! Continuing scenario...")
                        continue
                    else:
                        print("❌ Reconnection failed. Stopping scenario.")
                        break
                else:
                    print("🛑 Scenario execution stopped.")
                    break
            except (EOFError, KeyboardInterrupt):
                print("\n🛑 Scenario execution interrupted")
                break

        try:
            # Show current command and next command preview
            print(
                f"\n📤 Current Command ({line_number}/{len(scenario_lines)}): {current_line}"
            )

            # Show next command preview if available
            if i + 1 < len(scenario_lines):
                next_line = scenario_lines[i + 1]
                print(
                    f"👀 Next Command ({line_number + 1}/{len(scenario_lines)}): {next_line}"
                )
            else:
                print("👀 Next Command: [End of scenario]")

            print(
                "\n🎮 Controls: [Enter] Send | [S] Skip | [R] Retry | [R:N] Replay Line N | [I] Insert | [quit] Exit"
            )
            user_choice = await asyncio.to_thread(input, "Your choice: ")
            user_choice = user_choice.strip()

            # Handle user choices
            user_choice_lower = user_choice.lower()

            if user_choice_lower in ["quit", "exit", "q", "stop"]:
                print("🛑 Scenario execution stopped by user")
                break
            elif user_choice_lower in ["s", "skip"]:
                print(f"⏭️  Skipped command: {current_line}")
                i += 1  # Move to next command
                continue
            elif user_choice_lower in ["r", "retry"]:
                print(f"🔄 Retrying command: {current_line}")
                # Don't increment i, will retry the same command
            elif user_choice_lower.startswith("r:"):
                # Handle replay specific line (e.g., "r:5" to replay line 5)
                try:
                    replay_line_str = user_choice_lower.split(":", 1)[1]
                    replay_line_num = int(replay_line_str)

                    if 1 <= replay_line_num <= len(scenario_lines):
                        replay_command = scenario_lines[replay_line_num - 1]
                        print(f"🔄 Replaying line {replay_line_num}: {replay_command}")

                        # Send the replay command
                        print("🔄 Sending to voice manager...")
                        llm_response = await client.send_user_message(replay_command)

                        if llm_response:
                            print(f"🤖 LLM Response: {llm_response}")
                        else:
                            print("❌ No response received from voice manager")

                        # Don't increment i, stay on current command
                    else:
                        print(
                            f"❌ Invalid line number: {replay_line_num}. Valid range: 1-{len(scenario_lines)}"
                        )

                except (ValueError, IndexError):
                    print("❌ Invalid format. Use 'R:5' to replay line 5")
            elif user_choice_lower in ["i", "insert"]:
                # Handle manual command insertion
                try:
                    custom_command = await asyncio.to_thread(
                        input, "💬 Enter custom command: "
                    )
                    custom_command = custom_command.strip()

                    if custom_command:
                        print(f"📝 Sending custom command: {custom_command}")
                        print("🔄 Sending to voice manager...")

                        llm_response = await client.send_user_message(custom_command)

                        if llm_response:
                            print(f"🤖 LLM Response: {llm_response}")
                        else:
                            print("❌ No response received from voice manager")
                    else:
                        print("❌ Empty command, skipping")

                    # Don't increment i, stay on current command
                except (EOFError, KeyboardInterrupt):
                    print("\n❌ Custom command input cancelled")
            else:
                # Default behavior (Enter pressed or any other input)
                print("🔄 Sending to voice manager...")

                # Send the line to voice manager and wait for synchronous response
                llm_response = await client.send_user_message(current_line)

                if llm_response:
                    print(f"🤖 LLM Response: {llm_response}")
                else:
                    print("❌ No response received from voice manager")

                i += 1  # Move to next command after successful send

        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Scenario execution interrupted")
            break
        except Exception as e:
            print(f"❌ Error processing line {line_number}: {e}")

            # Ask user if they want to continue, retry, or stop
            try:
                error_choice = await asyncio.to_thread(
                    input, "Error occurred. [Enter] Continue | [R] Retry | [Q] Quit: "
                )
                error_choice = error_choice.strip().lower()

                if error_choice in ["q", "quit", "exit"]:
                    break
                elif error_choice in ["r", "retry"]:
                    continue  # Retry the same command
                else:
                    i += 1  # Continue to next command

            except (EOFError, KeyboardInterrupt):
                break

    print("\n✅ Scenario execution completed!")
    print(
        f"📊 Processed {min(i, len(scenario_lines))} out of {len(scenario_lines)} lines"
    )

    # Ask user if they want to keep the connection open for manual testing
    if client.is_connected():
        print("\n🔌 Connection is still active!")
        print("💡 You can now send manual commands or keep the connection open")
        try:
            keep_open = await asyncio.to_thread(
                input, "Keep connection open for manual testing? (y/N): "
            )
            if keep_open.strip().lower() in ["y", "yes"]:
                print("🎯 Connection kept open. You can send manual commands:")
                print("📝 Type your message and press Enter, or 'quit' to disconnect")
                await manual_chat_session(client)
        except (EOFError, KeyboardInterrupt):
            print("\n🔌 Proceeding to disconnect...")
    else:
        print("\n🔌 Connection was lost during scenario execution")


async def manual_chat_session(client: VoiceManagerClient):
    """Allow manual interaction with the voice manager after scenario completion."""
    print("\n" + "=" * 60)
    print("🎯 Manual Chat Mode")
    print("=" * 60)
    print("💬 You can now send messages directly to the voice manager")
    print("📝 Type your message and press Enter")
    print("🛑 Type 'quit', 'exit', or 'disconnect' to close the connection")
    print("=" * 60)

    while client.is_connected():
        try:
            user_input = await asyncio.to_thread(input, "\n💬 Your message: ")
            user_input = user_input.strip()

            if not user_input:
                print("❌ Please enter a message")
                continue

            if user_input.lower() in ["quit", "exit", "disconnect", "q"]:
                print("🛑 Disconnecting from voice manager...")
                break

            print(f"📤 Sending: {user_input}")
            response = await client.send_user_message(user_input)

            if response:
                print(f"🤖 Response: {response}")
            else:
                print("❌ No response received or connection lost")
                break

        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Manual chat session interrupted")
            break
        except Exception as e:
            print(f"❌ Error in manual chat: {e}")
            break

    print("👋 Manual chat session ended")


def main():
    """Main entry point for the MPT AI E2E Tester CLI."""
    print("=" * 60)
    print("🤖 MPT AI E2E Tester")
    print("=" * 60)
    print("This tool tests the MPT AI platform with automated scenarios.")
    print()

    print("Please select the mode of operation:")
    print()
    print("1. Interactive Mode")
    print("   - Run scenarios step-by-step")
    print("   - Wait for user confirmation between steps")
    print("   - Observe the Browser UI")
    print()
    print("2. Headless Mode")
    print("   - Run scenarios automatically")
    print("   - No user interaction required")
    print("   - Generate test reports")
    print()

    while True:
        try:
            choice = input(
                "Enter your choice (1 for Interactive, 2 for Headless): "
            ).strip()
            if choice == "1":
                print("✓ Interactive mode selected")
                asyncio.run(run_interactive_mode())
                break
            elif choice == "2":
                print("✓ Headless mode selected")
                break
            else:
                print("Invalid choice. Please enter 1 or 2.")
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            sys.exit(1)

    print("\nCLI completed successfully!")


if __name__ == "__main__":
    main()
