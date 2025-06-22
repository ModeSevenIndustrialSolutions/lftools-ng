# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Comprehensive integration tests for universal filtering system.

This test suite ensures that ALL CLI commands support the universal filtering
system. When adding new CLI commands, you MUST add tests here to verify
filtering functionality.

The universal filtering system is a CORE FEATURE of lftools-ng and must be
supported by every command that returns tabular data.
"""

import json
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from src.lftools_ng.cli import app


class TestUniversalFilteringIntegration:
    """Integration tests for universal filtering across all CLI commands.

    IMPORTANT: When adding new CLI commands that return data, you MUST add
    corresponding tests in this class to ensure filtering works correctly.
    """

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_projects_list_filtering_integration(self):
        """Test filtering integration with projects list command.

        This tests the complete integration from CLI arguments through
        to filtered output in all supported formats.
        """
        # Test include filtering with JSON output
        result = self.runner.invoke(
            app, ["projects", "list", "--include", "source=GitHub", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Should only contain GitHub projects
        for item in data:
            assert item.get("source") == "GitHub"

        # Test exclude filtering with table output
        result = self.runner.invoke(
            app, ["projects", "list", "--exclude", "name~=test", "--format", "table"]
        )
        assert result.exit_code == 0
        # Table output should not contain 'test' in names
        assert "test" not in result.stdout.lower()

        # Test field filtering
        result = self.runner.invoke(
            app, ["projects", "list", "--fields", "name,source", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        if data:  # If there's data
            for item in data:
                # Should only have name and source fields
                assert set(item.keys()) <= {"name", "source"}

    def test_projects_servers_filtering_integration(self):
        """Test filtering integration with projects servers command."""
        # Test type filtering
        result = self.runner.invoke(
            app, ["projects", "servers", "--include", "type=jenkins", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for item in data:
            assert item.get("type") == "jenkins"

        # Test combined include/exclude filters
        result = self.runner.invoke(
            app,
            [
                "projects",
                "servers",
                "--include",
                "type=jenkins",
                "--exclude",
                "name~=sandbox",
                "--fields",
                "name,type,url",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for item in data:
            assert item.get("type") == "jenkins"
            assert "sandbox" not in item.get("name", "").lower()
            assert set(item.keys()) <= {"name", "type", "url"}

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_jenkins_credentials_filtering_integration(self, mock_jenkins_client: Mock) -> None:
        """Test filtering integration with Jenkins credentials command."""
        # Mock Jenkins client response
        mock_credentials = [
            {
                "id": "ssh-key-1",
                "type": "ssh_private_key",
                "username": "deploy",
                "description": "Deploy key",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake key 1\n-----END RSA PRIVATE KEY-----",
            },
            {
                "id": "ssh-key-2",
                "type": "ssh_private_key",
                "username": "admin",
                "description": "Admin key",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake key 2\n-----END RSA PRIVATE KEY-----",
            },
            {
                "id": "password-1",
                "type": "username_password",
                "username": "user",
                "description": "User password",
                "password": "secret123",
            },
            {
                "id": "test-key",
                "type": "ssh_private_key",
                "username": "test",
                "description": "Test key",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest key\n-----END RSA PRIVATE KEY-----",
            },
        ]

        mock_client_instance = Mock()
        mock_client_instance.get_credentials.return_value = mock_credentials
        mock_jenkins_client.return_value = mock_client_instance

        # Test type filtering
        result = self.runner.invoke(
            app,
            [
                "jenkins",
                "credentials",
                "--server",
                "https://jenkins.example.com",
                "--user",
                "admin",
                "--password",
                "token",
                "--type",
                "ssh_private_key",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        # Parse only the JSON part (before the summary)
        json_output = result.output.split("\n\nFound")[0]
        data = json.loads(json_output)
        for item in data:
            assert item.get("type") == "ssh_private_key"

        # Test exclude filtering
        result = self.runner.invoke(
            app,
            [
                "jenkins",
                "credentials",
                "--server",
                "https://jenkins.example.com",
                "--user",
                "admin",
                "--password",
                "token",
                "--exclude",
                "id~=test",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        json_output = result.output.split("\n\nFound")[0]
        data = json.loads(json_output)
        for item in data:
            assert "test" not in item.get("id", "").lower()

        # Test field filtering
        result = self.runner.invoke(
            app,
            [
                "jenkins",
                "credentials",
                "--server",
                "https://jenkins.example.com",
                "--user",
                "admin",
                "--password",
                "token",
                "--fields",
                "id,type",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        json_output = result.output.split("\n\nFound")[0]
        data = json.loads(json_output)
        for item in data:
            assert set(item.keys()) <= {"id", "type"}

    def test_filtering_with_all_output_formats(self):
        """Test that filtering works with all supported output formats."""
        formats = ["table", "json", "json-pretty", "yaml"]

        for format_type in formats:
            result = self.runner.invoke(
                app, ["projects", "list", "--include", "source=GitHub", "--format", format_type]
            )
            assert result.exit_code == 0, f"Failed for format: {format_type}"
            assert result.stdout, f"No output for format: {format_type}"

    def test_complex_filtering_scenarios(self):
        """Test complex filtering scenarios that users might employ."""
        # Multiple include filters (AND logic)
        result = self.runner.invoke(
            app,
            [
                "projects",
                "servers",
                "--include",
                "type=jenkins",
                "--include",
                "name~=foundation",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for item in data:
            assert item.get("type") == "jenkins"
            assert "foundation" in item.get("name", "").lower()

        # Combined include and exclude filters
        result = self.runner.invoke(
            app,
            [
                "projects",
                "servers",
                "--include",
                "type=jenkins",
                "--exclude",
                "name~=sandbox",
                "--exclude",
                "name~=test",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for item in data:
            assert item.get("type") == "jenkins"
            name = item.get("name", "").lower()
            assert "sandbox" not in name
            assert "test" not in name

    def test_error_handling_for_invalid_filters(self):
        """Test error handling for invalid filter expressions."""
        # Invalid filter syntax
        result = self.runner.invoke(
            app, ["projects", "list", "--include", "invalid_syntax_no_operator", "--format", "json"]
        )
        assert result.exit_code != 0
        assert "Invalid filter" in result.stdout

        # Invalid field names (should not crash, just return empty results)
        result = self.runner.invoke(
            app, ["projects", "list", "--include", "nonexistent_field=value", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 0  # Should return no results

    def test_nested_field_filtering(self):
        """Test filtering on nested fields using dot notation."""
        # This test assumes future enhancements might include nested data
        result = self.runner.invoke(app, ["projects", "list", "--format", "json"])
        assert result.exit_code == 0
        # Test passes if command runs without error
        # Future nested field tests can be added here

    def test_empty_and_not_empty_filters(self):
        """Test empty and not-empty field filtering."""
        # Test excluding empty fields
        result = self.runner.invoke(
            app, ["projects", "list", "--exclude", "github_mirror_org:empty", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        for item in data:
            github_org = item.get("github_mirror_org", "")
            assert github_org is not None and github_org != ""

    def test_filtering_performance_with_large_datasets(self):
        """Test that filtering performs reasonably with larger datasets."""
        # This is more of a smoke test - ensures filtering doesn't crash
        # with realistic data volumes
        result = self.runner.invoke(app, ["projects", "list", "--format", "json"])
        assert result.exit_code == 0

        # Apply various filters to ensure they complete in reasonable time
        filters = ["--include", "name~=linux", "--exclude", "name~=test", "--fields", "name,source"]

        result = self.runner.invoke(app, ["projects", "list", *filters, "--format", "json"])
        assert result.exit_code == 0


class TestFilteringSystemRequirements:
    """Tests to ensure new commands meet filtering requirements.

    CRITICAL: This test class enforces that new CLI commands include
    filtering support. When adding new commands, add corresponding
    requirement tests here.
    """

    def test_all_data_commands_have_filtering_options(self):
        """Ensure all commands that return data support filtering options.

        This test verifies that filtering options are available in command help.
        When adding new data-returning commands, they MUST pass this test.
        """
        runner = CliRunner()

        # Test projects commands
        commands_to_test = [
            ["projects", "list", "--help"],
            ["projects", "servers", "--help"],
            ["jenkins", "credentials", "--help"],
        ]

        required_options = ["--include", "--exclude", "--fields", "--exclude-fields"]

        for cmd in commands_to_test:
            result = runner.invoke(app, cmd)
            assert result.exit_code == 0, f"Help failed for command: {' '.join(cmd)}"

            for option in required_options:
                assert option in result.output, (
                    f"Command {' '.join(cmd[:-1])} missing required filtering option: {option}\n"
                    f"ALL data-returning commands MUST support universal filtering!\n"
                    f"See docs/filtering.md for implementation requirements."
                )

    def test_filtering_documentation_requirements(self):
        """Test that filtering is properly documented in command help."""
        runner = CliRunner()

        # Check that commands have filtering examples in their help
        result = runner.invoke(app, ["projects", "list", "--help"])
        assert result.exit_code == 0
        assert "Filter examples:" in result.output
        assert "filtering capabilities" in result.output.lower()

    def test_json_output_requirement(self):
        """Test that all data commands support JSON output for programmatic use."""
        runner = CliRunner()

        commands_to_test = [["projects", "list"], ["projects", "servers"]]

        for cmd in commands_to_test:
            result = runner.invoke(app, [*cmd, "--format", "json"])
            assert result.exit_code == 0, f"JSON output failed for: {' '.join(cmd)}"

            # Should be valid JSON
            try:
                json.loads(result.stdout)
            except json.JSONDecodeError:
                pytest.fail(f"Command {' '.join(cmd)} does not produce valid JSON output")


# Template for future command tests
class TestNewCommandFilteringTemplate:
    """TEMPLATE: Copy this class when adding new CLI commands.

    When adding a new CLI command that returns data, copy this template
    and implement the required tests. This ensures consistency and
    maintains the quality of the filtering system.

    Steps to add filtering support to a new command:
    1. Add filtering parameters to your command function using the pattern
       from existing commands (projects.py, jenkins.py)
    2. Use format_and_output() from core.output module
    3. Copy this template class and implement the tests
    4. Add your command to TestFilteringSystemRequirements tests
    5. Update README.md with examples of your command's filtering
    """

    @pytest.mark.skip(reason="Template class - implement for actual commands")
    def test_new_command_basic_filtering(self):
        """Test basic include/exclude filtering for new command."""
        runner = CliRunner()

        # Test include filtering
        result = runner.invoke(
            app, ["your-command", "subcommand", "--include", "field=value", "--format", "json"]
        )
        assert result.exit_code == 0
        # Add assertions specific to your command

    @pytest.mark.skip(reason="Template class - implement for actual commands")
    def test_new_command_field_filtering(self):
        """Test field selection for new command."""
        runner = CliRunner()

        result = runner.invoke(
            app, ["your-command", "subcommand", "--fields", "field1,field2", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        if data:
            for item in data:
                assert set(item.keys()) <= {"field1", "field2"}

    @pytest.mark.skip(reason="Template class - implement for actual commands")
    def test_new_command_all_formats(self):
        """Test that new command supports all output formats."""
        runner = CliRunner()

        formats = ["table", "json", "json-pretty", "yaml"]
        for format_type in formats:
            result = runner.invoke(app, ["your-command", "subcommand", "--format", format_type])
            assert result.exit_code == 0, f"Failed for format: {format_type}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
