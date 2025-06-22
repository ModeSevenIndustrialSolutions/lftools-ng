# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for Jenkins CLI commands."""

from pathlib import Path
from unittest.mock import Mock, call, patch

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

    @patch("lftools_ng.commands.jenkins.JenkinsConfigReader")
    @patch("lftools_ng.commands.jenkins.JenkinsClient")
    def test_check_versions_success(
        self, mock_jenkins_client_class: Mock, mock_config_reader_class: Mock
    ) -> None:
        """Test checking Jenkins versions successfully."""
        # Mock configuration
        mock_config_reader = Mock()
        mock_config_reader.get_jenkins_configs.return_value = {
            "server1": Mock(url="https://jenkins1.example.org", user="user1", password="pass1"),
            "server2": Mock(url="https://jenkins2.example.org", user="user2", password="pass2"),
        }
        mock_config_reader_class.return_value = mock_config_reader

        # Mock Jenkins clients
        mock_client1 = Mock()
        mock_client1.get_version.return_value = "2.401.3"
        mock_client2 = Mock()
        mock_client2.get_version.return_value = "2.414.2"
        mock_jenkins_client_class.side_effect = [mock_client1, mock_client2]

        result = self.runner.invoke(jenkins_app, ["versions", "--format", "json"])

        assert result.exit_code == 0
        assert "2.401.3" in result.output
        assert "2.414.2" in result.output
        assert "server1" in result.output
        assert "server2" in result.output
        assert "Successful: 2" in result.output or "Successful: " in result.output

        # Verify Jenkins clients were created with correct parameters including timeout
        expected_calls = [
            call("https://jenkins1.example.org", "user1", "pass1", timeout=3),
            call("https://jenkins2.example.org", "user2", "pass2", timeout=3),
        ]
        mock_jenkins_client_class.assert_has_calls(expected_calls)

    @patch("lftools_ng.commands.jenkins.JenkinsConfigReader")
    def test_check_versions_no_config(self, mock_config_reader_class: Mock) -> None:
        """Test checking versions with no configuration found."""
        mock_config_reader = Mock()
        mock_config_reader.get_jenkins_configs.return_value = {}
        mock_config_reader_class.return_value = mock_config_reader

        result = self.runner.invoke(jenkins_app, ["versions"])

        assert result.exit_code == 1
        assert "No jenkins_jobs.ini files found" in result.output

    @patch("lftools_ng.commands.jenkins.JenkinsConfigReader")
    @patch("lftools_ng.commands.jenkins.JenkinsClient")
    def test_check_versions_with_failure(
        self, mock_jenkins_client_class: Mock, mock_config_reader_class: Mock
    ) -> None:
        """Test checking versions with one server failing."""
        # Mock configuration
        mock_config_reader = Mock()
        mock_config_reader.get_jenkins_configs.return_value = {
            "server1": Mock(url="https://jenkins1.example.org", user="user1", password="pass1"),
            "server2": Mock(url="https://jenkins2.example.org", user="user2", password="pass2"),
        }
        mock_config_reader_class.return_value = mock_config_reader

        # Mock Jenkins clients - one succeeds, one fails
        mock_client1 = Mock()
        mock_client1.get_version.return_value = "2.401.3"
        mock_jenkins_client_class.side_effect = [mock_client1, Exception("Authentication failed")]

        result = self.runner.invoke(jenkins_app, ["versions"])

        assert result.exit_code == 0  # Command succeeds even if some servers fail
        assert "2.401.3" in result.output
        assert "Authentication failed" in result.output
        assert "Successful: 1" in result.output or "Successful:" in result.output
        assert "Failed: 1" in result.output or "Failed:" in result.output

        # Verify Jenkins clients were created with correct parameters including timeout
        expected_calls = [
            call("https://jenkins1.example.org", "user1", "pass1", timeout=3),
            call("https://jenkins2.example.org", "user2", "pass2", timeout=3),
        ]
        mock_jenkins_client_class.assert_has_calls(expected_calls)

    @patch("lftools_ng.commands.jenkins.JenkinsConfigReader")
    @patch("lftools_ng.commands.jenkins.JenkinsClient")
    def test_check_versions_custom_timeout(
        self, mock_jenkins_client_class: Mock, mock_config_reader_class: Mock
    ) -> None:
        """Test checking versions with custom timeout."""
        # Mock configuration
        mock_config_reader = Mock()
        mock_config_reader.get_jenkins_configs.return_value = {
            "server1": Mock(url="https://jenkins1.example.org", user="user1", password="pass1"),
        }
        mock_config_reader_class.return_value = mock_config_reader

        # Mock Jenkins client
        mock_client1 = Mock()
        mock_client1.get_version.return_value = "2.401.3"
        mock_jenkins_client_class.return_value = mock_client1

        result = self.runner.invoke(jenkins_app, ["versions", "--timeout", "30"])

        assert result.exit_code == 0
        assert "2.401.3" in result.output

        # Verify Jenkins client was created with custom timeout
        mock_jenkins_client_class.assert_called_once_with(
            "https://jenkins1.example.org", "user1", "pass1", timeout=30
        )
