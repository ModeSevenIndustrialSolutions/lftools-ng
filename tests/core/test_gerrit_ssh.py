# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for Gerrit SSH client functionality."""

import json
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import Mock, patch

from lftools_ng.core.gerrit_ssh import GerritSSHClient


class TestGerritSSHClient:
    """Test cases for GerritSSHClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = GerritSSHClient(timeout=30)

    def test_init(self):
        """Test client initialization."""
        assert self.client.timeout == 30
        assert hasattr(self.client, "ssh_config")

    def test_parse_gerrit_url(self):
        """Test Gerrit URL parsing."""
        # Test HTTPS URL
        hostname, port = self.client._parse_gerrit_url("https://gerrit.onap.org")
        assert hostname == "gerrit.onap.org"
        assert port == 29418

        # Test HTTP URL
        hostname, port = self.client._parse_gerrit_url("http://gerrit.example.org")
        assert hostname == "gerrit.example.org"
        assert port == 29418

        # Test with custom port
        hostname, port = self.client._parse_gerrit_url("https://gerrit.example.org:9999")
        assert hostname == "gerrit.example.org"
        assert port == 9999

        # Test invalid URL
        hostname, port = self.client._parse_gerrit_url("invalid-url")
        assert hostname is None
        assert port is None

    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_get_ssh_username(self, mock_ssh_config):
        """Test SSH username resolution."""
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        client = GerritSSHClient()
        username = client._get_ssh_username("gerrit.example.org")

        assert username == "testuser"
        mock_parser.get_username_for_host.assert_called_once_with("gerrit.example.org")

    @patch("subprocess.run")
    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_list_projects_success(self, mock_ssh_config, mock_subprocess):
        """Test successful project listing via SSH."""
        # Mock SSH config
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        # Mock successful SSH response
        mock_projects = [
            {"name": "project1", "description": "Test project 1"},
            {"name": "project2", "description": "Test project 2", "state": "READ_ONLY"},
        ]
        mock_subprocess.return_value = CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(mock_projects), stderr=""
        )

        client = GerritSSHClient()
        projects = client.list_projects("https://gerrit.example.org")

        assert len(projects) == 2
        assert projects[0]["name"] == "project1"
        assert projects[1]["name"] == "project2"
        assert projects[1]["state"] == "READ_ONLY"

    @patch("subprocess.run")
    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_list_projects_line_format(self, mock_ssh_config, mock_subprocess):
        """Test project listing with line-by-line JSON format."""
        # Mock SSH config
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        # Mock line-by-line JSON response
        mock_stdout = '{"name": "project1", "description": "Test project 1"}\n{"name": "project2", "description": "Test project 2"}\n'
        mock_subprocess.return_value = CompletedProcess(
            args=[], returncode=0, stdout=mock_stdout, stderr=""
        )

        client = GerritSSHClient()
        projects = client.list_projects("https://gerrit.example.org")

        assert len(projects) == 2
        assert projects[0]["name"] == "project1"
        assert projects[1]["name"] == "project2"

    @patch("subprocess.run")
    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_list_projects_ssh_failure(self, mock_ssh_config, mock_subprocess):
        """Test SSH command failure."""
        # Mock SSH config
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        # Mock SSH failure
        mock_subprocess.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Permission denied"
        )

        client = GerritSSHClient()
        projects = client.list_projects("https://gerrit.example.org")

        assert projects == []

    @patch("subprocess.run")
    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_list_projects_timeout(self, mock_ssh_config, mock_subprocess):
        """Test SSH command timeout."""
        # Mock SSH config
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        # Mock timeout
        mock_subprocess.side_effect = TimeoutExpired(["ssh"], 30)

        client = GerritSSHClient()
        projects = client.list_projects("https://gerrit.example.org")

        assert projects == []

    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_list_projects_no_username(self, mock_ssh_config):
        """Test project listing when no SSH username is configured."""
        # Mock SSH config with no username
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = None
        mock_ssh_config.return_value = mock_parser

        client = GerritSSHClient()
        projects = client.list_projects("https://gerrit.example.org")

        assert projects == []

    def test_list_projects_invalid_url(self):
        """Test project listing with invalid URL."""
        projects = self.client.list_projects("invalid-url")
        assert projects == []

    def test_gerrit_to_github_name_mapping(self):
        """Test bidirectional mapping functions."""
        # Test simple path
        result = self.client.gerrit_to_github_name("simple-project")
        assert result == "simple-project"

        # Test nested path - should take last component
        result = self.client.gerrit_to_github_name("project/subproject/specific-name")
        assert result == "specific-name"

        # Test generic last component - should flatten
        result = self.client.gerrit_to_github_name("project/subproject/repo")
        assert result == "project-subproject-repo"

        # Test empty path
        result = self.client.gerrit_to_github_name("")
        assert result == ""

    def test_github_to_gerrit_candidates(self):
        """Test GitHub to Gerrit candidate finding."""
        gerrit_repos = [
            "simple-project",
            "project/subproject/specific-name",
            "project/subproject/repo",
            "other/repo",
        ]

        # Test direct match
        candidates = self.client.github_to_gerrit_candidates("simple-project", gerrit_repos)
        assert "simple-project" in candidates

        # Test last component match
        candidates = self.client.github_to_gerrit_candidates("specific-name", gerrit_repos)
        assert "project/subproject/specific-name" in candidates

        # Test flattened name match
        candidates = self.client.github_to_gerrit_candidates(
            "project-subproject-repo", gerrit_repos
        )
        assert "project/subproject/repo" in candidates

    @patch("subprocess.run")
    def test_test_ssh_connectivity_success(self, mock_subprocess):
        """Test successful SSH connectivity test."""
        mock_subprocess.return_value = CompletedProcess(
            args=[], returncode=0, stdout="Welcome to Gerrit Code Review", stderr=""
        )

        result = self.client.test_ssh_connectivity("gerrit.example.org", "testuser")
        assert result is True

    @patch("subprocess.run")
    def test_test_ssh_connectivity_failure(self, mock_subprocess):
        """Test failed SSH connectivity test."""
        mock_subprocess.return_value = CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Connection refused"
        )

        result = self.client.test_ssh_connectivity("gerrit.example.org", "testuser")
        assert result is False

    @patch("subprocess.run")
    def test_test_ssh_connectivity_timeout(self, mock_subprocess):
        """Test SSH connectivity timeout."""
        mock_subprocess.side_effect = TimeoutExpired(["ssh"], 30)

        result = self.client.test_ssh_connectivity("gerrit.example.org", "testuser")
        assert result is False
