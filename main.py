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
            print(f"Found USER_ID in .env file: {env_user_id}")

            # Ask user if they want to use the default USER_ID
            try:
                use_default = await asyncio.to_thread(
                    input, f"Use default USER_ID '{env_user_id}'? (y/N): "
                )
                use_default = use_default.strip().lower()

                if use_default in ["y", "yes"]:
                    print(f"Using USER_ID from .env file: {env_user_id}")
                    return env_user_id
                else:
                    print("Proceeding with manual USER_ID input")

            except (EOFError, KeyboardInterrupt):
                print("\nProceeding with manual USER_ID input")
        else:
            print("Invalid USER_ID in .env file, falling back to manual input")
    else:
        print("No USER_ID found in .env file")

    # Fall back to manual input
    print("\nPlease enter your User ID:")
    print("This will be used to identify your session with the voice manager")
    print("You can also set USER_ID in your .env file to skip this step")

    while True:
        try:
            user_id = await asyncio.to_thread(input, "User ID: ")
            user_id = user_id.strip()

            if not user_id:
                print("❌ User ID cannot be empty. Please try again.")
                continue

            if validate_user_id(user_id):
                print(f"User ID set to: {user_id}")
                return user_id

        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled")
            return None
        except Exception as e:
            print(f"Error getting user ID: {e}")
            return None


def validate_user_id(user_id: str) -> bool:
    """Validate user ID format."""
    if not user_id:
        print("User ID cannot be empty.")
        return False

    # Basic validation - no spaces, reasonable length
    if " " in user_id:
        print("User ID cannot contain spaces.")
        return False

    if len(user_id) > 50:
        print("User ID too long (max 50 characters).")
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
    print("\nStarting Interactive Mode")
    print("=" * 40)

    # Ask for USER_ID
    user_id = await get_user_id()
    if not user_id:
        print("User ID is required for interactive mode")
        return

    # Create voice manager client with the provided user ID
    client = VoiceManagerClient(user_id=user_id)

    try:
        # Attempt connection
        print("Connection details:")
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
            print("Successfully connected to voice manager!")

            # Select scenario
            selected_scenario = await select_scenario()
            if not selected_scenario:
                print("No scenario selected. Exiting interactive mode.")
                await client.disconnect()
                return

            print(
                f"\nStarting interactive session with scenario: {selected_scenario.name}"
            )
            print("You can now interact with the voice manager")
            print("Type 'quit' or 'exit' to end the session")
            print("=" * 40)

            # Interactive session with selected scenario
            await interactive_chat_session(client, selected_scenario)
        else:
            print("Failed to connect to voice manager")
            print("Make sure the voice manager is running:")
            print("   python mock_voice_manager.py")

    except Exception as e:
        print(f"Error in interactive mode: {e}")

    finally:
        # Only disconnect if still connected (user might have disconnected manually)
        if client.is_connected():
            await client.disconnect()
        print("Interactive mode ended")


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

    print(f"Loaded {len(scenario_lines)} lines from scenario")
    print("Interactive Mode: Each line will be sent one at a time")
    print("Controls:")
    print("   • Press Enter to send the current command")
    print("   • Type 'S' or 's' to skip the current command")
    print("   • Type 'R' or 'r' to retry current command, or 'R:5' to replay line 5")
    print("   • Type 'I' or 'i' to insert and send a custom command")
    print("   • Type 'G:N' or 'g:N' to go to line N and resume from there")
    print("   • Type 'quit' or 'exit' to stop")
    print("=" * 60)

    i = 0  # Initialize counter
    while i < len(scenario_lines):
        current_line = scenario_lines[i]
        line_number = i + 1

        if not client.is_connected():
            print("Connection lost to voice manager")
            print("The server may have closed the connection after sending audio data")

            # Ask user if they want to reconnect and continue
            try:
                reconnect_choice = await asyncio.to_thread(
                    input, "Try to reconnect and continue? (y/N): "
                )
                if reconnect_choice.strip().lower() in ["y", "yes"]:
                    if await client.reconnect():
                        print("Reconnected successfully! Continuing scenario...")
                        continue
                    else:
                        print("Reconnection failed. Stopping scenario.")
                        break
                else:
                    print("Scenario execution stopped.")
                    break
            except (EOFError, KeyboardInterrupt):
                print("\nScenario execution interrupted")
                break

        try:
            # Show the command that will be executed when Enter is pressed
            print(
                f"\nCommand to execute ({line_number}/{len(scenario_lines)}): {current_line}"
            )

            print(
                "\nControls: [Enter] Send | [S] Skip | [R] Retry | [R:N] Replay Line N | [I] Insert | [G:N] Go to Line N | [quit] Exit"
            )
            user_choice = await asyncio.to_thread(input, "Your choice: ")
            user_choice = user_choice.strip()

            # Handle user choices
            user_choice_lower = user_choice.lower()

            if user_choice_lower in ["quit", "exit", "q", "stop"]:
                print("Scenario execution stopped by user")
                break
            elif user_choice_lower in ["s", "skip"]:
                print(f"Skipped command: {current_line}")
                i += 1  # Move to next command
                continue
            elif user_choice_lower in ["r", "retry"]:
                print(f"Retrying command: {current_line}")
                # Don't increment i, will retry the same command
            elif user_choice_lower.startswith("r:"):
                # Handle replay specific line (e.g., "r:5" to replay line 5)
                try:
                    replay_line_str = user_choice_lower.split(":", 1)[1]
                    replay_line_num = int(replay_line_str)

                    if 1 <= replay_line_num <= len(scenario_lines):
                        replay_command = scenario_lines[replay_line_num - 1]
                        print(f"Replaying line {replay_line_num}: {replay_command}")

                        # Send the replay command
                        print("Sending to voice manager...")
                        llm_response = await client.send_user_message(replay_command)

                        if llm_response:
                            print(f"LLM Response: {llm_response}")
                        else:
                            print("No response received from voice manager")

                        # Don't increment i, stay on current command
                    else:
                        print(
                            f"Invalid line number: {replay_line_num}. Valid range: 1-{len(scenario_lines)}"
                        )

                except (ValueError, IndexError):
                    print("Invalid format. Use 'R:5' to replay line 5")
            elif user_choice_lower in ["i", "insert"]:
                # Handle manual command insertion
                try:
                    custom_command = await asyncio.to_thread(
                        input, "Enter custom command: "
                    )
                    custom_command = custom_command.strip()

                    if custom_command:
                        print(f"Sending custom command: {custom_command}")
                        print("Sending to voice manager...")

                        llm_response = await client.send_user_message(custom_command)

                        if llm_response:
                            print(f"LLM Response: {llm_response}")
                        else:
                            print("No response received from voice manager")
                    else:
                        print("Empty command, skipping")

                    # Don't increment i, stay on current command
                except (EOFError, KeyboardInterrupt):
                    print("\nCustom command input cancelled")
            elif user_choice_lower.startswith("g:"):
                # Handle go to specific line (e.g., "g:3" to go to line 3)
                try:
                    goto_line_str = user_choice_lower.split(":", 1)[1]
                    goto_line_num = int(goto_line_str)

                    if 1 <= goto_line_num <= len(scenario_lines):
                        print(
                            f"Going to line {goto_line_num}: {scenario_lines[goto_line_num - 1]}"
                        )
                        i = (
                            goto_line_num - 1
                        )  # Set to target line (will be current in next iteration)
                        continue  # Continue to next iteration with new line
                    else:
                        print(
                            f"Invalid line number: {goto_line_num}. Valid range: 1-{len(scenario_lines)}"
                        )

                except (ValueError, IndexError):
                    print("Invalid format. Use 'G:3' to go to line 3")
            else:
                # Default behavior (Enter pressed or any other input)
                print("Sending to voice manager...")

                # Send the line to voice manager and wait for synchronous response
                llm_response = await client.send_user_message(current_line)

                if llm_response:
                    print(f"LLM Response: {llm_response}")
                else:
                    print("No response received from voice manager")

                i += 1  # Move to next command after successful send

        except (EOFError, KeyboardInterrupt):
            print("\nScenario execution interrupted")
            break
        except Exception as e:
            print(f"Error processing line {line_number}: {e}")

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

    print("\nScenario execution completed!")
    print(f"Processed {min(i, len(scenario_lines))} out of {len(scenario_lines)} lines")

    # Ask user if they want to keep the connection open for manual testing
    if client.is_connected():
        print("\nConnection is still active!")
        print("You can now send manual commands or keep the connection open")
        try:
            keep_open = await asyncio.to_thread(
                input, "Keep connection open for manual testing? (y/N): "
            )
            if keep_open.strip().lower() in ["y", "yes"]:
                print("Connection kept open. You can send manual commands:")
                print("Type your message and press Enter, or 'quit' to disconnect")
                await manual_chat_session(client)
        except (EOFError, KeyboardInterrupt):
            print("\nProceeding to disconnect...")
    else:
        print("\nConnection was lost during scenario execution")


async def manual_chat_session(client: VoiceManagerClient):
    """Allow manual interaction with the voice manager after scenario completion."""
    print("\n" + "=" * 60)
    print("Manual Chat Mode")
    print("=" * 60)
    print("You can now send messages directly to the voice manager")
    print("Type your message and press Enter")
    print("Type 'quit', 'exit', or 'disconnect' to close the connection")
    print("=" * 60)

    while client.is_connected():
        try:
            user_input = await asyncio.to_thread(input, "\nYour message: ")
            user_input = user_input.strip()

            if not user_input:
                print("Please enter a message")
                continue

            if user_input.lower() in ["quit", "exit", "disconnect", "q"]:
                print("Disconnecting from voice manager...")
                break

            print(f"Sending: {user_input}")
            response = await client.send_user_message(user_input)

            if response:
                print(f"Response: {response}")
            else:
                print("No response received or connection lost")
                break

        except (EOFError, KeyboardInterrupt):
            print("\nManual chat session interrupted")
            break
        except Exception as e:
            print(f"Error in manual chat: {e}")
            break

    print("Manual chat session ended")


async def run_headless_mode():
    """Run headless mode - automated execution without user interaction."""
    print("Starting Headless Mode")
    print("=" * 60)

    # Load environment variables
    load_dotenv()

    # Check if USER_ID is available in .env file
    env_user_id = os.getenv("USER_ID")
    if not env_user_id or not env_user_id.strip():
        print("Error: USER_ID must be set in .env file for headless mode")
        print("Please add USER_ID=your_user_id to your .env file")
        return

    user_id = env_user_id.strip()
    if not validate_user_id(user_id):
        print(f"Error: Invalid USER_ID in .env file: '{user_id}'")
        print("USER_ID must contain only letters, numbers, underscores, and hyphens")
        return

    print(f"Using USER_ID from .env file: {user_id}")

    # Get available scenarios
    scenarios = get_available_scenarios()
    if not scenarios:
        print("No scenario files found in 'scenarios' directory")
        print("Please create .yaml or .yml files in the scenarios folder")
        return

    # Show available scenarios
    print("\nAvailable scenarios:")
    for i, scenario_file in enumerate(scenarios, 1):
        print(f"  {i}. {scenario_file.name}")

    # For headless mode, use the first scenario or allow selection
    print(f"\nUsing first available scenario: {scenarios[0].name}")
    selected_scenario = scenarios[0]

    # Create client and connect
    client = VoiceManagerClient(user_id=user_id)

    try:
        print("\nConnection details:")
        print(f"   Host: {client.host}")
        print(f"   Port: {client.port}")
        print(f"   User ID: {client.user_id}")

        if await client.connect():
            print("Successfully connected to voice manager!")
            await headless_execution(client, selected_scenario)
        else:
            print("Failed to connect to voice manager")
            print("Make sure the voice manager is running:")
            print("   python mock_voice_manager.py")

    except Exception as e:
        print(f"Error in headless mode: {e}")

    finally:
        if client.is_connected():
            await client.disconnect()
        print("Headless mode ended")


async def headless_execution(client: VoiceManagerClient, scenario_file: Path):
    """Execute scenario automatically without user interaction."""
    print(f"\nLoading scenario: {scenario_file.name}")

    try:
        with open(scenario_file, "r", encoding="utf-8") as f:
            scenario_data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading scenario file: {e}")
        return

    if not scenario_data or "commands" not in scenario_data:
        print("Invalid scenario file: missing 'commands' section")
        return

    scenario_lines = scenario_data["commands"]
    if not scenario_lines:
        print("No commands found in scenario")
        return

    print(f"Loaded {len(scenario_lines)} commands from scenario")
    print("Headless Mode: Commands will be executed automatically with 3-second delays")
    print("=" * 60)

    for i, command in enumerate(scenario_lines):
        line_number = i + 1

        if not client.is_connected():
            print("Connection lost to voice manager")
            print("Attempting to reconnect...")
            if await client.reconnect():
                print("Reconnected successfully! Continuing scenario...")
            else:
                print("Reconnection failed. Stopping scenario.")
                break

        try:
            print(
                f"\nExecuting command ({line_number}/{len(scenario_lines)}): {command}"
            )
            print("Sending to voice manager...")

            # Send the command to voice manager
            llm_response = await client.send_user_message(command)

            if llm_response:
                print(f"LLM Response: {llm_response}")
            else:
                print("No response received from voice manager")

            # Wait 3 seconds before next command (except for the last command)
            if i < len(scenario_lines) - 1:
                print("Waiting 3 seconds before next command...")
                await asyncio.sleep(3)

        except Exception as e:
            print(f"Error processing command {line_number}: {e}")
            print("Continuing with next command...")
            continue

    print(f"\nHeadless execution completed!")
    print(f"Processed {len(scenario_lines)} commands")


def main():
    """Main entry point for the MPT AI E2E Tester CLI."""
    print("=" * 60)
    print("MPT AI E2E Tester")
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
                print("Interactive mode selected")
                asyncio.run(run_interactive_mode())
                break
            elif choice == "2":
                print("Headless mode selected")
                asyncio.run(run_headless_mode())
                break
            else:
                print("Invalid choice. Please enter 1 or 2.")
        except (EOFError, KeyboardInterrupt):
            print("\nOperation cancelled.")
            sys.exit(1)

    print("\nCLI completed successfully!")


if __name__ == "__main__":
    main()
