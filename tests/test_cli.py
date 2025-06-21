# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for lftools-ng CLI interface."""

import logging
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from lftools_ng.cli import app


class TestCLI:
    """Test cases for main CLI."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_cli_help(self) -> None:
        """Test CLI help command."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Linux Foundation Release Engineering Tools" in result.output

    def test_cli_version(self) -> None:
        """Test CLI version command."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
        assert "lftools-ng Information" in result.output
        assert "Linux Foundation Release Engineering Tools" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_projects_subcommand(self, mock_project_manager_class: Mock) -> None:
        """Test projects subcommand integration."""
        mock_manager = Mock()
        mock_manager.list_projects.return_value = []
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(app, ["projects", "list"])
        assert result.exit_code == 0
        assert "Project" in result.output
        assert "Aliases" in result.output

    @patch("lftools_ng.commands.jenkins.JenkinsClient")
    def test_jenkins_subcommand(self, mock_jenkins_client_class: Mock) -> None:
        """Test jenkins subcommand integration."""
        mock_client = Mock()
        mock_client.get_credentials.return_value = []
        mock_jenkins_client_class.return_value = mock_client

        result = self.runner.invoke(
            app,
            [
                "jenkins",
                "credentials",
                "--server",
                "https://jenkins.example.org",
                "--user",
                "testuser",
                "--password",
                "testpass",
            ],
        )
        assert result.exit_code == 0

    def test_cli_version_flag(self) -> None:
        """Test that --version flag displays version and exits."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "lftools-ng Information" in result.stdout
        assert "0.1.0" in result.stdout

    def test_cli_verbose_flag(self) -> None:
        """Test that --verbose flag sets logging level."""
        with patch("logging.basicConfig") as mock_basicConfig:
            result = self.runner.invoke(app, ["--verbose", "--version"])
            assert result.exit_code == 0
            mock_basicConfig.assert_called_once_with(level=logging.DEBUG)

    def test_cli_no_subcommand_shows_help(self) -> None:
        """Test that running CLI without subcommand shows help."""
        result = self.runner.invoke(app, [])
        # Note: CLI exits with code 2 when no subcommand is provided, which is expected
        assert result.exit_code == 2
        assert "Usage:" in result.stdout
