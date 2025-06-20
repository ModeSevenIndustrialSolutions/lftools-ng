# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for Jenkins client functionality."""

from unittest.mock import Mock, patch

import pytest

from lftools_ng.core.jenkins import JenkinsClient


class TestJenkinsClient:
    """Test cases for JenkinsClient."""

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_jenkins_client_init(self, mock_jenkins_class: Mock) -> None:
        """Test JenkinsClient initialization."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.return_value = "2.401.3"
        mock_jenkins_class.return_value = mock_jenkins

        client = JenkinsClient(
            server="https://jenkins.example.com", username="testuser", password="testpass"
        )

        assert client.server == "https://jenkins.example.com"
        assert client.username == "testuser"
        assert client.password == "testpass"

        mock_jenkins_class.assert_called_once_with(
            "https://jenkins.example.com", username="testuser", password="testpass", timeout=60
        )
        mock_jenkins.get_version.assert_called_once()

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_jenkins_client_init_connection_error(self, mock_jenkins_class: Mock) -> None:
        """Test JenkinsClient initialization with connection error."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.side_effect = Exception("Connection failed")
        mock_jenkins_class.return_value = mock_jenkins

        with pytest.raises(Exception, match="Connection failed"):
            JenkinsClient(
                server="https://jenkins.example.com", username="testuser", password="testpass"
            )

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_run_groovy_script(self, mock_jenkins_class: Mock) -> None:
        """Test running a Groovy script."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.return_value = "2.401.3"
        mock_jenkins.run_script.return_value = "Script output"
        mock_jenkins_class.return_value = mock_jenkins

        client = JenkinsClient(
            server="https://jenkins.example.com", username="testuser", password="testpass"
        )

        result = client.run_groovy_script("println 'Hello World'")

        assert result == "Script output"
        mock_jenkins.run_script.assert_called_once_with("println 'Hello World'")

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_get_credentials(self, mock_jenkins_class: Mock) -> None:
        """Test getting credentials."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.return_value = "2.401.3"
        mock_jenkins.run_script.return_value = "[]"  # Empty JSON array
        mock_jenkins_class.return_value = mock_jenkins

        client = JenkinsClient(
            server="https://jenkins.example.com", username="testuser", password="testpass"
        )

        credentials = client.get_credentials()

        assert credentials == []
        mock_jenkins.run_script.assert_called_once()
        # Verify that the Groovy script contains credential-related imports
        script_call = mock_jenkins.run_script.call_args[0][0]
        assert "com.cloudbees.plugins.credentials" in script_call
        assert "StandardCredentials" in script_call

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_get_secrets(self, mock_jenkins_class: Mock) -> None:
        """Test getting secrets."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.return_value = "2.401.3"
        mock_jenkins.run_script.return_value = "[]"
        mock_jenkins_class.return_value = mock_jenkins

        client = JenkinsClient(
            server="https://jenkins.example.com", username="testuser", password="testpass"
        )

        secrets = client.get_secrets()

        assert secrets == []
        mock_jenkins.run_script.assert_called_once()

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_get_ssh_private_keys(self, mock_jenkins_class: Mock) -> None:
        """Test getting SSH private keys."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.return_value = "2.401.3"
        mock_jenkins.run_script.return_value = "[]"
        mock_jenkins_class.return_value = mock_jenkins

        client = JenkinsClient(
            server="https://jenkins.example.com", username="testuser", password="testpass"
        )

        keys = client.get_ssh_private_keys()

        assert keys == []
        mock_jenkins.run_script.assert_called_once()

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_get_version(self, mock_jenkins_class: Mock) -> None:
        """Test getting Jenkins version."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.return_value = "2.401.3"
        mock_jenkins_class.return_value = mock_jenkins

        client = JenkinsClient(
            server="https://jenkins.example.com", username="testuser", password="testpass"
        )

        version = client.get_version()
        assert version == "2.401.3"

    @patch("lftools_ng.core.jenkins.jenkins.Jenkins")
    def test_get_info(self, mock_jenkins_class: Mock) -> None:
        """Test getting Jenkins info."""
        mock_jenkins = Mock()
        mock_jenkins.get_version.return_value = "2.401.3"
        mock_jenkins.get_info.return_value = {"version": "2.401.3", "nodeDescription": "Test"}
        mock_jenkins_class.return_value = mock_jenkins

        client = JenkinsClient(
            server="https://jenkins.example.com", username="testuser", password="testpass"
        )

        info = client.get_info()
        assert info["version"] == "2.401.3"
        assert info["nodeDescription"] == "Test"
