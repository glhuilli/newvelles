"""Tests for newvelles.config module."""

import os
import tempfile
from unittest.mock import patch

import pytest

from newvelles.config import config, debug


class TestConfig:
    """Test config module functionality."""

    def test_config_returns_configparser(self):
        """Test that config() returns a ConfigParser object."""
        cfg = config()
        assert hasattr(cfg, "get")
        assert hasattr(cfg, "sections")

    def test_config_has_required_sections(self):
        """Test that config has required sections."""
        cfg = config()
        sections = cfg.sections()
        assert "PARAMS" in sections
        assert "DAEMON" in sections

    def test_config_has_required_params(self):
        """Test that config has required parameters."""
        cfg = config()
        assert cfg.has_option("PARAMS", "debug")
        assert cfg.has_option("PARAMS", "limit")
        assert cfg.has_option("PARAMS", "cluster_limit")

    def test_config_has_required_daemon_params(self):
        """Test that config has required daemon parameters."""
        cfg = config()
        assert cfg.has_option("DAEMON", "wait_time")
        assert cfg.has_option("DAEMON", "debug")

    def test_debug_returns_boolean(self):
        """Test that debug() returns a boolean."""
        result = debug()
        assert isinstance(result, bool)

    def test_debug_with_true_value(self):
        """Test debug() with True value in config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                """[PARAMS]
debug = True
limit = 100
cluster_limit = 1

[DAEMON]
wait_time = 60
debug = True
"""
            )
            temp_config_path = f.name

        try:
            with patch("newvelles.config.path.join") as mock_join:
                mock_join.return_value = temp_config_path
                result = debug()
                assert result is True
        finally:
            os.unlink(temp_config_path)

    def test_debug_with_false_value(self):
        """Test debug() with False value in config."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(
                """[PARAMS]
debug = False
limit = 100
cluster_limit = 1

[DAEMON]
wait_time = 60
debug = False
"""
            )
            temp_config_path = f.name

        try:
            with patch("newvelles.config.path.join") as mock_join:
                mock_join.return_value = temp_config_path
                result = debug()
                assert result is False
        finally:
            os.unlink(temp_config_path)

    def test_config_values_types(self):
        """Test that config values have expected types."""
        cfg = config()

        # Test that we can get string values
        debug_val = cfg.get("PARAMS", "debug")
        assert isinstance(debug_val, str)

        limit_val = cfg.get("PARAMS", "limit")
        assert isinstance(limit_val, str)

        cluster_limit_val = cfg.get("PARAMS", "cluster_limit")
        assert isinstance(cluster_limit_val, str)

        wait_time_val = cfg.get("DAEMON", "wait_time")
        assert isinstance(wait_time_val, str)
