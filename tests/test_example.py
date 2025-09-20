"""
Example tests to demonstrate pytest functionality
"""

import pytest


def test_example_pass():
    """Example test that passes."""
    assert True


def test_example_with_data():
    """Example test with some data."""
    data = {"name": "test", "value": 42}
    assert data["name"] == "test"
    assert data["value"] == 42


@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4), 
    (3, 6),
])
def test_double_function(input, expected):
    """Example parametrized test."""
    def double(x):
        return x * 2
    
    assert double(input) == expected


def test_with_fixture(tmp_path):
    """Example test using pytest fixture."""
    # tmp_path is a built-in pytest fixture
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")
    
    assert test_file.read_text() == "hello"
