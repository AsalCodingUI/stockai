"""E2E Tests for CLI Setup and Configuration (Story 1.1)."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from stockai import __version__
from stockai.cli.main import app
from stockai.config import get_settings

runner = CliRunner()


class TestCLISetup:
    """Test CLI setup and basic commands."""

    def test_cli_help(self):
        """AC1.1.5: stock --help displays help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "StockAI" in result.stdout
        assert "AI-Powered Indonesian Stock Analysis" in result.stdout

    def test_cli_version(self):
        """Test version flag displays version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_cli_config_command(self):
        """Test config command shows configuration."""
        result = runner.invoke(app, ["config"])
        assert result.exit_code == 0
        assert "Configuration" in result.stdout

    def test_cli_info_command_placeholder(self):
        """Test info command exists (placeholder)."""
        result = runner.invoke(app, ["info", "BBCA"])
        assert result.exit_code == 0
        assert "BBCA" in result.stdout

    @patch("stockai.cli.main.get_settings")
    @patch("stockai.agents.create_trading_orchestrator")
    def test_cli_analyze_command_placeholder(self, mock_create_orchestrator, mock_get_settings):
        """Test analyze command exists (placeholder)."""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.has_google_api = True
        mock_get_settings.return_value = mock_settings

        # Mock orchestrator
        mock_orchestrator = MagicMock()
        async def mock_analyze(*args, **kwargs):
            return {"answer": "Analysis result for BBCA"}
        mock_orchestrator.analyze = mock_analyze
        mock_create_orchestrator.return_value = mock_orchestrator

        result = runner.invoke(app, ["analyze", "BBCA"])
        assert result.exit_code == 0
        assert "BBCA" in result.stdout

    @patch("stockai.cli.main.YahooFinanceSource")
    def test_cli_predict_command_placeholder(self, mock_yahoo_class):
        """Test predict command exists (placeholder)."""
        import pandas as pd
        from datetime import datetime
        mock_yahoo = MagicMock()
        mock_yahoo.get_price_history.return_value = pd.DataFrame({
            "date": pd.date_range(end=datetime.now(), periods=100, freq='D'),
            "open": [100.0] * 100,
            "high": [100.0] * 100,
            "low": [100.0] * 100,
            "close": [100.0] * 100,
            "volume": [1000] * 100,
        })
        mock_yahoo_class.return_value = mock_yahoo

        result = runner.invoke(app, ["predict", "BBCA"])
        assert result.exit_code == 0
        assert "BBCA" in result.stdout

    def test_cli_history_command_placeholder(self):
        """Test history command exists (placeholder)."""
        result = runner.invoke(app, ["history", "BBCA"])
        assert result.exit_code == 0
        assert "BBCA" in result.stdout

    def test_cli_portfolio_list_placeholder(self):
        """Test portfolio list command exists."""
        result = runner.invoke(app, ["portfolio", "list"])
        assert result.exit_code == 0

    def test_cli_portfolio_add_placeholder(self):
        """Test portfolio add command exists."""
        result = runner.invoke(app, ["portfolio", "add", "BBCA", "100", "9500"])
        assert result.exit_code == 0
        assert "BBCA" in result.stdout

    def test_cli_watchlist_list_placeholder(self):
        """Test watchlist list command exists."""
        result = runner.invoke(app, ["watchlist", "list"])
        assert result.exit_code == 0

    def test_cli_watchlist_add_placeholder(self):
        """Test watchlist add command exists."""
        result = runner.invoke(app, ["watchlist", "add", "BBCA"])
        assert result.exit_code == 0


class TestConfiguration:
    """Test configuration system."""

    def test_settings_loads(self):
        """AC1.1.1: Project structure follows Python package best practices."""
        settings = get_settings()
        assert settings is not None

    def test_settings_has_model(self):
        """Test default model is configured."""
        settings = get_settings()
        # Model name may include "models/" prefix
        assert "gemini" in settings.model.lower()

    def test_settings_has_default_index(self):
        """Test default index is IDX30."""
        settings = get_settings()
        assert settings.default_index == "IDX30"

    def test_settings_cache_ttl(self):
        """Test cache TTL has default."""
        settings = get_settings()
        assert settings.cache_ttl > 0

    def test_settings_log_level(self):
        """Test log level is valid."""
        settings = get_settings()
        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]


class TestModuleImports:
    """Test that all modules can be imported."""

    def test_import_stockai(self):
        """Test main package imports."""
        import stockai
        assert stockai.__version__

    def test_import_config(self):
        """Test config module imports."""
        from stockai.config import Settings, get_settings, MODEL_MAP
        assert Settings
        assert get_settings
        assert MODEL_MAP

    def test_import_cli(self):
        """Test CLI module imports."""
        from stockai.cli.main import app
        assert app


class TestModuleExecution:
    """Test module can be executed."""

    def test_module_execution_help(self):
        """Test python -m stockai --help works."""
        project_root = Path(__file__).resolve().parent.parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "stockai", "--help"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        assert result.returncode == 0
        assert "StockAI" in result.stdout
