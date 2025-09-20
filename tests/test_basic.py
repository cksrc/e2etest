"""
Basic tests for MPT AI E2E Tester
"""

import pytest


def test_basic_math():
    """Test basic math operations."""
    assert 1 + 1 == 2
    assert 2 * 3 == 6


def test_string_operations():
    """Test basic string operations."""
    text = "hello world"
    assert text.upper() == "HELLO WORLD"
    assert "world" in text


def test_list_operations():
    """Test basic list operations."""
    items = [1, 2, 3]
    items.append(4)
    assert len(items) == 4
    assert 4 in items


class TestBasicClass:
    """Basic test class example."""
    
    def test_class_method(self):
        """Test method in class."""
        assert True
    
    def test_another_method(self):
        """Another test method."""
        result = "test"
        assert isinstance(result, str)
