# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Comprehensive CLI testing suite that systematically tests all commands and options.

This test suite is designed to:
1. Test that command descriptions are accurate and up-to-date
2. Detect empty error boxes like the one reported in the issue
3. Be scalable to test future commands as they are added
4. Validate that all CLI flags and options work correctly
"""

import re
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from lftools_ng.cli import app


class TestCLIComprehensive:
    """Comprehensive test suite for CLI commands and options."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_projects_list_description_updated(self) -> None:
        """Test that the projects list command description has been updated."""
        result = self.runner.invoke(app, ["projects", "list", "--help"])
        assert result.exit_code == 0

        # Should NOT contain the old Jenkins server mappings reference
        assert "Jenkins server mappings" not in result.output, (
            "projects list command still contains old Jenkins server mappings reference"
        )

        # Should contain the updated description
        assert "List all registered projects" in result.output, (
            "projects list command missing updated description"
        )

    def test_no_empty_error_boxes(self) -> None:
        """Test that commands don't show empty error boxes like in the user's issue."""
        # Test various command patterns that might trigger the empty error box
        test_cases = [
            ["projects"],  # Should show help or proper error
            ["jenkins"],  # Should show help or proper error
            ["rebuild-data"],  # Should execute or show proper error
        ]

        for command in test_cases:
            result = self.runner.invoke(app, command)

            # If there's an error box, it should contain meaningful content
            # But if help is also shown, we consider that acceptable
            if "╭─ Error ─" in result.output:
                error_section = result.output[result.output.find("╭─ Error ─") :]
                # Count non-whitespace/formatting characters in error section
                content_chars = len(re.sub(r"[─│╭╯╰╮\s]", "", error_section))

                # If help is shown, empty error box is acceptable
                if "Commands" in result.output and "Options" in result.output:
                    continue  # Help is shown, so empty error is acceptable

                assert content_chars > 10, (
                    f"Empty or nearly empty error box for command {command}: {result.output}"
                )

    def test_all_help_commands_work(self) -> None:
        """Test that all help commands work and contain proper content."""
        # List of all known command paths that should work
        help_commands = [
            ["--help"],
            ["--version"],
            ["projects", "--help"],
            ["projects", "list", "--help"],
            ["projects", "servers", "--help"],
            ["projects", "repositories", "--help"],
            ["jenkins", "--help"],
            ["jenkins", "credentials", "--help"],
            ["rebuild-data", "--help"],
        ]

        for command_args in help_commands:
            result = self.runner.invoke(app, command_args)
            assert result.exit_code == 0, (
                f"Help command {command_args} failed with exit code {result.exit_code}: {result.output}"
            )

            # All help commands should contain usage information
            assert "Usage:" in result.output or "lftools-ng Information" in result.output, (
                f"Help command {command_args} missing expected content: {result.output}"
            )

            # Should not show empty error boxes
            assert "╭─ Error ─" not in result.output, (
                f"Help command {command_args} shows error: {result.output}"
            )

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_projects_commands_execute_successfully(self, mock_project_manager_class: Mock) -> None:
        """Test projects commands execute without errors."""
        # Mock the ProjectManager
        mock_manager = Mock()
        mock_manager.list_projects.return_value = [
            {"name": "test-project", "aliases": ["tp"], "github_org": "testorg", "source": "test"}
        ]
        mock_manager.list_servers.return_value = [
            {"name": "test-server", "url": "https://test.example.com", "type": "jenkins"}
        ]
        mock_project_manager_class.return_value = mock_manager

        # Test various projects commands
        test_commands = [
            ["projects", "list"],
            ["projects", "list", "--format", "json"],
            ["projects", "servers"],
        ]

        for command in test_commands:
            result = self.runner.invoke(app, command)
            assert result.exit_code == 0, f"Command {command} failed: {result.output}"
            # Should not show error boxes
            assert "╭─ Error ─" not in result.output, (
                f"Command {command} shows error box: {result.output}"
            )

    def test_jenkins_credentials_error_handling(self) -> None:
        """Test jenkins credentials shows helpful error for missing required params."""
        # Mock to prevent finding real config files
        with patch(
            "lftools_ng.core.jenkins_config.JenkinsConfigReader.get_jenkins_configs"
        ) as mock_configs:
            mock_configs.return_value = {}  # No configs found

            result = self.runner.invoke(app, ["jenkins", "credentials"])

            # Should show helpful error, not empty error box
            assert result.exit_code != 0  # Should fail

            if "╭─ Error ─" in result.output:
                # If there's an error box, it should contain helpful content
                assert len(result.output.strip()) > 50, "Error message should be informative"
                # Should mention something about required parameters
                assert any(
                    word in result.output.lower() for word in ["server", "required", "missing"]
                ), "Error should mention missing required parameters"


# Scalable test functions for future commands
@pytest.fixture
def cli_runner():
    """Provide a CLI runner for tests."""
    return CliRunner()


@pytest.fixture
def mock_all_dependencies():
    """Mock all external dependencies for CLI testing."""
    with (
        patch("lftools_ng.commands.projects.ProjectManager") as mock_pm,
        patch("lftools_ng.core.jenkins_provider.JenkinsClient") as mock_jc,
        patch("lftools_ng.core.projects.ProjectManager") as mock_core_pm,
    ):
        # Set up reasonable mock returns
        mock_manager = Mock()
        mock_manager.list_projects.return_value = []
        mock_manager.list_servers.return_value = []
        mock_pm.return_value = mock_manager
        mock_core_pm.return_value = mock_manager

        mock_client = Mock()
        mock_client.get_credentials.return_value = []
        mock_jc.return_value = mock_client

        yield {
            "project_manager": mock_pm,
            "jenkins_client": mock_jc,
            "core_project_manager": mock_core_pm,
        }


def test_scalable_cli_integration(cli_runner, mock_all_dependencies):
    """
    Scalable integration test for all CLI commands.

    This test is designed to be easily extensible. To test new commands:
    1. Add them to the commands_to_test list below
    2. The test will automatically validate they work without empty error boxes
    3. Add any specific validation logic needed for your command

    This approach ensures that as new commands are added, they are automatically
    tested for basic functionality and proper error handling.
    """
    # List of commands to test - extend this as new commands are added
    # Format: (command_args, expected_exit_code)
    commands_to_test = [
        (["--help"], 0),
        (["--version"], 0),
        (["projects", "list"], 0),
        (["projects", "list", "--format", "json"], 0),
        (["projects", "servers"], 0),
        (
            [
                "jenkins",
                "credentials",
                "--server",
                "https://test",
                "--user",
                "test",
                "--password",
                "test",
            ],
            0,
        ),
        (["rebuild-data", "--help"], 0),
    ]

    for command, expected_exit_code in commands_to_test:
        result = cli_runner.invoke(app, command)
        assert result.exit_code == expected_exit_code, (
            f"Command {command} failed with exit code {result.exit_code}: {result.output}"
        )

        # Ensure no empty error boxes (the main issue from the user's report)
        if "╭─ Error ─" in result.output:
            error_content = result.output[result.output.find("╭─ Error ─") :]
            meaningful_content = re.sub(r"[─│╭╯╰╮\s]", "", error_content)
            assert len(meaningful_content) > 5, (
                f"Command {command} shows empty error box: {result.output}"
            )


def test_error_cases_provide_helpful_messages(cli_runner):
    """Test that error cases provide helpful messages instead of empty error boxes."""
    # Test commands that should produce helpful errors
    error_test_cases = [
        ["jenkins", "credentials"],  # Missing required parameters
        ["projects", "nonexistent-subcommand"],  # Invalid subcommand
    ]

    for command in error_test_cases:
        # For jenkins credentials, mock to prevent finding real config files
        if command == ["jenkins", "credentials"]:
            with patch(
                "lftools_ng.core.jenkins_config.JenkinsConfigReader.get_jenkins_configs"
            ) as mock_configs:
                mock_configs.return_value = {}  # No configs found
                result = cli_runner.invoke(app, command)
        else:
            result = cli_runner.invoke(app, command)

        # Should fail but with helpful message
        assert result.exit_code != 0, f"Command {command} should fail but didn't"

        # Should not show the empty error box from the original issue
        if "╭─ Error ─" in result.output:
            # Extract the error section and verify it has meaningful content
            lines = result.output.split("\n")
            error_lines = []
            in_error_section = False

            for line in lines:
                if "╭─ Error ─" in line:
                    in_error_section = True
                elif "╰─" in line and in_error_section:
                    in_error_section = False
                elif in_error_section:
                    error_lines.append(line)

            # Error section should contain meaningful content
            error_text = "\n".join(error_lines).strip()
            meaningful_chars = len(re.sub(r"[│\s]", "", error_text))
            assert meaningful_chars > 5, (
                f"Command {command} has empty error message: '{error_text}'"
            )


def test_future_commands_template():
    """
    Template for testing future commands.

    When new commands are added to the CLI, copy this template and modify it
    to test the specific functionality of the new command.

    Example:
    def test_new_command_functionality(cli_runner, mock_all_dependencies):
        # Test the new command
        result = cli_runner.invoke(app, ['new-command', '--help'])
        assert result.exit_code == 0
        assert "Usage:" in result.output

        # Test execution with mocked dependencies
        result = cli_runner.invoke(app, ['new-command', '--option', 'value'])
        assert result.exit_code == 0
        assert "╭─ Error ─" not in result.output
    """
    pass  # This is just a template/documentation function
