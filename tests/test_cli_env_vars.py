# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Tests for CLI environment variable support.

This module tests that all CLI commands properly define environment variables
and don't show incorrect '(env var: 'None')' messages.
"""

from typer.testing import CliRunner

from lftools_ng.cli import app
from lftools_ng.commands.jenkins import jenkins_app


class TestCLIEnvironmentVariables:
    """Test environment variable support in CLI commands."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_jenkins_credentials_help_shows_env_vars(self):
        """Test that jenkins credentials command help shows proper environment variables."""
        result = self.runner.invoke(jenkins_app, ["credentials", "--help"])

        # Should not contain 'env var: 'None''
        assert "(env var: 'None')" not in result.output

        # Should contain proper environment variable references
        assert "JENKINS_URL" in result.output
        assert "JENKINS_USER" in result.output
        assert "JENKINS_PASSWORD" in result.output

    def test_jenkins_analyze_help_shows_env_vars(self):
        """Test that jenkins analyze command help shows proper environment variables."""
        result = self.runner.invoke(jenkins_app, ["analyze", "--help"])

        # Should not contain 'env var: 'None''
        assert "(env var: 'None')" not in result.output

        # Should contain proper environment variable references
        assert "JENKINS_URL" in result.output
        assert "JENKINS_USER" in result.output
        assert "JENKINS_PASSWORD" in result.output

    def test_jenkins_migrate_help_shows_env_vars(self):
        """Test that jenkins migrate command help shows proper environment variables."""
        result = self.runner.invoke(jenkins_app, ["migrate", "--help"])

        # Should not contain 'env var: 'None''
        assert "(env var: 'None')" not in result.output

        # Should contain proper environment variable references
        assert "JENKINS_URL" in result.output
        assert "JENKINS_USER" in result.output
        assert "JENKINS_PASSWORD" in result.output

    def test_jenkins_groovy_help_shows_env_vars(self):
        """Test that jenkins groovy command help shows proper environment variables."""
        result = self.runner.invoke(jenkins_app, ["groovy", "--help"])

        # Should not contain 'env var: 'None''
        assert "(env var: 'None')" not in result.output

        # Should contain proper environment variable references
        assert "JENKINS_URL" in result.output
        assert "JENKINS_USER" in result.output
        assert "JENKINS_PASSWORD" in result.output

    def test_all_jenkins_commands_have_env_vars(self):
        """Test that all jenkins commands define environment variables."""
        # Get help for main jenkins command to see subcommands
        result = self.runner.invoke(jenkins_app, ["--help"])
        assert result.exit_code == 0

        # Extract command names from help output
        # The output uses rich tables, so we need to look for the command lines differently
        lines = result.output.split("\n")
        commands = []
        in_commands_section = False

        for line in lines:
            if "╭─ Commands" in line or "Commands:" in line:
                in_commands_section = True
                continue
            elif in_commands_section and line.strip():
                if "╰─" in line:
                    # End of commands section
                    break
                elif "│" in line and line.strip().startswith("│"):
                    # This is a command line in the rich table
                    # Extract command name (first word after │)
                    content = line.split("│")[1] if "│" in line else ""
                    parts = content.strip().split()
                    if parts:
                        commands.append(parts[0])

        assert len(commands) > 0, f"No commands found in help output. Full output:\n{result.output}"

        # Test each command's help output
        for command in commands:
            if command in ["credentials", "analyze", "migrate", "groovy"]:
                # These commands require Jenkins connection so should have env vars
                result = self.runner.invoke(jenkins_app, [command, "--help"])
                assert result.exit_code == 0, f"Help for '{command}' command failed"
                assert "(env var: 'None')" not in result.output, (
                    f"Command '{command}' shows incorrect env var info"
                )

    def test_main_app_help_no_incorrect_env_vars(self):
        """Test that main app help doesn't show incorrect environment variables."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "(env var: 'None')" not in result.output

    def test_projects_command_help_no_incorrect_env_vars(self):
        """Test that projects command help doesn't show incorrect environment variables."""
        result = self.runner.invoke(app, ["projects", "--help"])
        assert result.exit_code == 0
        assert "(env var: 'None')" not in result.output

    def test_rebuild_command_help_no_incorrect_env_vars(self):
        """Test that rebuild command help doesn't show incorrect environment variables."""
        result = self.runner.invoke(app, ["rebuild-data", "--help"])
        assert result.exit_code == 0
        assert "(env var: 'None')" not in result.output


class TestJenkinsConfigFileSupport:
    """Test Jenkins configuration file support in CLI commands."""

    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()

    def test_credentials_command_shows_config_file_option(self):
        """Test that credentials command shows config file option in help."""
        result = self.runner.invoke(jenkins_app, ["credentials", "--help"])
        assert result.exit_code == 0
        assert "--config-file" in result.output
        assert "jenkins_jobs.ini" in result.output

    def test_analyze_command_shows_config_file_option(self):
        """Test that analyze command shows config file option in help."""
        result = self.runner.invoke(jenkins_app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--config-file" in result.output
        assert "jenkins_jobs.ini" in result.output

    def test_migrate_command_shows_config_file_option(self):
        """Test that migrate command shows config file option in help."""
        result = self.runner.invoke(jenkins_app, ["migrate", "--help"])
        assert result.exit_code == 0
        assert "--config-file" in result.output
        assert "jenkins_jobs.ini" in result.output

    def test_groovy_command_shows_config_file_option(self):
        """Test that groovy command shows config file option in help."""
        result = self.runner.invoke(jenkins_app, ["groovy", "--help"])
        assert result.exit_code == 0
        assert "--config-file" in result.output
        assert "jenkins_jobs.ini" in result.output

    def test_commands_show_config_file_as_preferred_option(self):
        """Test that commands show config file as preferred authentication method."""
        commands_to_test = ["credentials", "analyze", "migrate", "groovy"]

        for command in commands_to_test:
            result = self.runner.invoke(jenkins_app, [command, "--help"])
            assert result.exit_code == 0

            # Config file option should appear before other auth options in help
            help_text = result.output
            config_file_pos = help_text.find("--config-file")

            # Different commands use different server option names
            if command == "migrate":
                server_pos = help_text.find("--source-server")
                user_pos = help_text.find("--source-user")
                password_pos = help_text.find("--source-password")
            else:
                server_pos = help_text.find("--server")
                user_pos = help_text.find("--user")
                password_pos = help_text.find("--password")

            # Config file should be mentioned (may not always be first due to alphabetical ordering)
            assert config_file_pos != -1, f"--config-file option not found in {command} help"
            assert server_pos != -1, f"Server option not found in {command} help"
            assert user_pos != -1, f"User option not found in {command} help"
            assert password_pos != -1, f"--password option not found in {command} help"
