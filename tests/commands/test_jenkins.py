# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for Jenkins CLI commands."""

from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from lftools_ng.commands.jenkins import jenkins_app


class TestJenkinsCommands:
    """Test cases for Jenkins CLI commands."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_get_credentials_success(self, mock_jenkins_client_class: Mock) -> None:
        """Test getting credentials successfully."""
        mock_client = Mock()
        mock_client.get_credentials.return_value = [
            {
                "id": "test-cred",
                "description": "Test Credential",
                "type": "username_password",
                "username": "testuser",
                "password": "testpass",
            }
        ]
        mock_jenkins_client_class.return_value = mock_client

        result = self.runner.invoke(
            jenkins_app,
            [
                "credentials",
                "--server",
                "https://jenkins.example.org",
                "--user",
                "testuser",
                "--password",
                "testpass",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        # Check that we got JSON output with credentials
        assert "test-cred" in result.output
        assert '"type":"username_password"' in result.output
        # Should have JSON structure indicators
        assert result.output.startswith("[")
        assert "credentials matching filters" in result.output

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_get_credentials_connection_error(self, mock_jenkins_client_class: Mock) -> None:
        """Test getting credentials with connection error."""
        mock_jenkins_client_class.side_effect = Exception("Connection failed")

        result = self.runner.invoke(
            jenkins_app,
            [
                "credentials",
                "--server",
                "https://jenkins.example.org",
                "--user",
                "testuser",
                "--password",
                "testpass",
            ],
        )

        assert result.exit_code == 1
        assert "Connection failed" in result.output

    @patch("lftools_ng.commands.jenkins.JenkinsClient")
    def test_run_groovy_script_success(
        self, mock_jenkins_client_class: Mock, tmp_path: Path
    ) -> None:
        """Test running groovy script successfully."""
        mock_client = Mock()
        mock_client.run_groovy_script.return_value = "Script executed successfully"
        mock_jenkins_client_class.return_value = mock_client

        # Create a temporary script file
        script_file = tmp_path / "test.groovy"
        script_file.write_text("println 'Hello World'")

        result = self.runner.invoke(
            jenkins_app,
            [
                "groovy",
                str(script_file),
                "--server",
                "https://jenkins.example.org",
                "--user",
                "testuser",
                "--password",
                "testpass",
            ],
        )

        assert result.exit_code == 0
        assert "Script executed successfully" in result.output
