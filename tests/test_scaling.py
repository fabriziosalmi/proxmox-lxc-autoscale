"""Tests for scaling calculations and timezone-aware behavior."""

import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lxc_autoscale'))

from scaling_manager import (
    calculate_increment,
    calculate_decrement,
    is_off_peak,
)


class TestCalculateIncrement:
    def test_basic_increment(self):
        result = calculate_increment(current=90, upper_threshold=80,
                                     min_increment=1, max_increment=4)
        assert 1 <= result <= 4

    def test_min_increment_floor(self):
        result = calculate_increment(current=81, upper_threshold=80,
                                     min_increment=1, max_increment=4)
        assert result >= 1

    def test_max_increment_cap(self):
        result = calculate_increment(current=100, upper_threshold=20,
                                     min_increment=1, max_increment=2)
        assert result <= 2

    def test_proportional_scaling(self):
        small = calculate_increment(current=85, upper_threshold=80,
                                    min_increment=1, max_increment=10)
        large = calculate_increment(current=99, upper_threshold=80,
                                    min_increment=1, max_increment=10)
        assert large >= small


class TestCalculateDecrement:
    def test_basic_decrement(self):
        result = calculate_decrement(current=5, lower_threshold=20,
                                     current_allocated=8, min_decrement=1,
                                     min_allocated=1)
        assert result >= 1

    def test_cannot_go_below_min(self):
        result = calculate_decrement(current=5, lower_threshold=20,
                                     current_allocated=2, min_decrement=1,
                                     min_allocated=1)
        assert result <= 1  # can only remove 1 (2 -> 1)


class TestIsOffPeak:
    """Test timezone-aware off-peak detection."""

    @patch('scaling_manager._current_hour')
    def test_off_peak_night(self, mock_hour):
        """23:00 should be off-peak with default 22-6 window."""
        mock_hour.return_value = 23
        assert is_off_peak() is True

    @patch('scaling_manager._current_hour')
    def test_off_peak_early_morning(self, mock_hour):
        """03:00 should be off-peak with default 22-6 window."""
        mock_hour.return_value = 3
        assert is_off_peak() is True

    @patch('scaling_manager._current_hour')
    def test_peak_afternoon(self, mock_hour):
        """14:00 should NOT be off-peak with default 22-6 window."""
        mock_hour.return_value = 14
        assert is_off_peak() is False

    @patch('scaling_manager._current_hour')
    def test_peak_boundary(self, mock_hour):
        """06:00 should NOT be off-peak (end boundary exclusive)."""
        mock_hour.return_value = 6
        assert is_off_peak() is False

    @patch('scaling_manager._current_hour')
    def test_off_peak_start_boundary(self, mock_hour):
        """22:00 should be off-peak (start boundary inclusive)."""
        mock_hour.return_value = 22
        assert is_off_peak() is True
