#!/usr/bin/env python3
"""
MPT AI E2E Tester - Simple Command Line Interface
"""

import sys
import asyncio
from pathlib import Path
import yaml
from app.voice_client import VoiceManagerClient


async def get_user_id():
    """Prompt user for their USER_ID."""
    print("\n📝 Please enter your User ID:")
    print("💡 This will be used to identify your session with the voice manager")

    while True:
        try:
            user_id = await asyncio.to_thread(input, "User ID: ")
            user_id = user_id.strip()

            if not user_id:
                print("❌ User ID cannot be empty. Please try again.")
                continue

            # Basic validation - no spaces, reasonable length
            if " " in user_id:
                print("❌ User ID cannot contain spaces. Please try again.")
                continue

            if len(user_id) > 50:
                print("❌ User ID too long (max 50 characters). Please try again.")
                continue

            print(f"✅ User ID set to: {user_id}")
            return user_id

        except (EOFError, KeyboardInterrupt):
            print("\n❌ Operation cancelled")
            return None
        except Exception as e:
            print(f"❌ Error getting user ID: {e}")
            return None


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
        print(f"   User ID: {connection_info['user_id']} (provided by user)")
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
    print("📝 Press Enter after each response to continue to the next line")
    print("💡 Type 'quit' or 'exit' at any prompt to stop")
    print("=" * 60)

    i = 0  # Initialize counter
    for i, line in enumerate(scenario_lines, 1):
        if not client.connected:
            print("❌ Connection lost to voice manager")
            break

        try:
            print(f"\n📤 Line {i}/{len(scenario_lines)}: {line}")
            print("🔄 Sending to voice manager...")

            # Send the line to voice manager
            response = await client.send_user_message(line)

            if response:
                # Handle both string and dict responses
                if isinstance(response, dict):
                    llm_response = response.get("LLM", "No response received")
                else:
                    llm_response = str(response)
                print(f"🤖 LLM Response: {llm_response}")
            else:
                print("❌ No response received from voice manager")

            # Wait for user confirmation to continue (except for last line)
            if i < len(scenario_lines):
                print(
                    "\n⏸️  Paused. Press Enter to send next line, or type 'quit' to stop..."
                )
                user_input = await asyncio.to_thread(input, "Continue? ")
                user_input = user_input.strip().lower()

                if user_input in ["quit", "exit", "q", "stop"]:
                    print("🛑 Scenario execution stopped by user")
                    break

        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Scenario execution interrupted")
            break
        except Exception as e:
            print(f"❌ Error processing line {i}: {e}")

            # Ask user if they want to continue
            try:
                continue_choice = await asyncio.to_thread(
                    input, "Continue with next line? (y/N): "
                )
                if continue_choice.strip().lower() not in ["y", "yes"]:
                    break
            except (EOFError, KeyboardInterrupt):
                break

    print("\n✅ Scenario execution completed!")
    print(
        f"📊 Processed {min(i, len(scenario_lines))} out of {len(scenario_lines)} lines"
    )


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
