"""
Tests for scenario loading and CLI functionality
"""

import pytest
import yaml
from pathlib import Path
from main import load_scenario_lines, get_available_scenarios


class TestScenarioLoading:
    """Test scenario file loading functionality."""

    def test_load_yaml_scenario_with_lines(self, tmp_path):
        """Test loading YAML scenario with 'lines' key."""
        scenario_content = {
            "lines": ["Go to Abu Dhabi", "Check the weather", "Book a hotel"]
        }

        scenario_file = tmp_path / "test_scenario.yaml"
        scenario_file.write_text(yaml.dump(scenario_content))

        lines = load_scenario_lines(scenario_file)
        assert lines == ["Go to Abu Dhabi", "Check the weather", "Book a hotel"]

    def test_load_yaml_scenario_as_list(self, tmp_path):
        """Test loading YAML scenario as direct list."""
        scenario_content = ["Navigate to Dubai", "Find restaurants", "Make reservation"]

        scenario_file = tmp_path / "test_scenario.yaml"
        scenario_file.write_text(yaml.dump(scenario_content))

        lines = load_scenario_lines(scenario_file)
        assert lines == ["Navigate to Dubai", "Find restaurants", "Make reservation"]

    def test_load_plain_text_scenario(self, tmp_path):
        """Test loading plain text scenario."""
        scenario_content = """Open browser
Navigate to website
Click login button
Enter credentials"""

        scenario_file = tmp_path / "test_scenario.txt"
        scenario_file.write_text(scenario_content)

        lines = load_scenario_lines(scenario_file)
        expected = [
            "Open browser",
            "Navigate to website",
            "Click login button",
            "Enter credentials",
        ]
        assert lines == expected

    def test_load_empty_scenario(self, tmp_path):
        """Test loading empty scenario file."""
        scenario_file = tmp_path / "empty_scenario.yaml"
        scenario_file.write_text("")

        lines = load_scenario_lines(scenario_file)
        assert lines == []

    def test_load_nonexistent_scenario(self):
        """Test loading non-existent scenario file."""
        nonexistent_file = Path("nonexistent_scenario.yaml")
        lines = load_scenario_lines(nonexistent_file)
        assert lines == []


class TestScenarioDiscovery:
    """Test scenario file discovery functionality."""

    def test_get_available_scenarios_yaml_files(self, tmp_path, monkeypatch):
        """Test finding YAML scenario files."""
        # Create test scenario files
        (tmp_path / "scenario1.yaml").write_text("lines: ['test1']")
        (tmp_path / "scenario2.yml").write_text("lines: ['test2']")
        (tmp_path / "not_scenario.txt").write_text("not a scenario")

        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create scenarios directory
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()
        (scenarios_dir / "test1.yaml").write_text("lines: ['test1']")
        (scenarios_dir / "test2.yml").write_text("lines: ['test2']")

        scenarios = get_available_scenarios()
        scenario_names = [s.name for s in scenarios]

        assert "test1.yaml" in scenario_names
        assert "test2.yml" in scenario_names
        assert len(scenarios) == 2

    def test_get_available_scenarios_no_directory(self, tmp_path, monkeypatch):
        """Test when scenarios directory doesn't exist."""
        monkeypatch.chdir(tmp_path)
        scenarios = get_available_scenarios()
        assert scenarios == []

    def test_get_available_scenarios_empty_directory(self, tmp_path, monkeypatch):
        """Test when scenarios directory is empty."""
        monkeypatch.chdir(tmp_path)
        scenarios_dir = tmp_path / "scenarios"
        scenarios_dir.mkdir()

        scenarios = get_available_scenarios()
        assert scenarios == []


@pytest.mark.parametrize(
    "message_format,expected_command,expected_message",
    [
        ({"command": "USER", "message": "test"}, "USER", "test"),
        ({"command": "LLM", "message": "response"}, "LLM", "response"),
    ],
)
def test_message_format_validation(message_format, expected_command, expected_message):
    """Test message format validation."""
    assert message_format["command"] == expected_command
    assert message_format["message"] == expected_message
