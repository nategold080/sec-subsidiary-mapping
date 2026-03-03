"""Tests for CLI module."""

import pytest
from click.testing import CliRunner

from src.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Employer Labor Compliance" in result.output

    def test_scrape_help(self, runner):
        result = runner.invoke(cli, ["scrape", "--help"])
        assert result.exit_code == 0
        assert "--whd" in result.output
        assert "--osha" in result.output
        assert "--nlrb" in result.output

    def test_pipeline_help(self, runner):
        result = runner.invoke(cli, ["pipeline", "--help"])
        assert result.exit_code == 0
        assert "--min-year" in result.output

    def test_stats_help(self, runner):
        result = runner.invoke(cli, ["stats", "--help"])
        assert result.exit_code == 0

    def test_export_help(self, runner):
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        assert "--output-dir" in result.output
