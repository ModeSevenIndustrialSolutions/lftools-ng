# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Integration tests for SSH-based repository discovery."""

import json
from unittest.mock import Mock, patch

from lftools_ng.core.gerrit_ssh import GerritSSHClient
from lftools_ng.core.repository_discovery import RepositoryDiscovery


class TestSSHRepositoryDiscoveryIntegration:
    """Integration tests for SSH-based repository discovery system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.discovery = RepositoryDiscovery()

    @patch("subprocess.run")
    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_end_to_end_gerrit_discovery(self, mock_ssh_config, mock_subprocess):
        """Test end-to-end Gerrit repository discovery via SSH."""
        # Mock SSH config
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        # Mock SSH response with realistic ONAP-style repositories
        mock_projects = [
            {"name": "aai/aai-common", "description": "AAI Common library", "state": "ACTIVE"},
            {"name": "aai/babel", "description": "AAI Babel microservice", "state": "ACTIVE"},
            {
                "name": "integration/testsuite",
                "description": "Integration test suite",
                "state": "READ_ONLY",
            },
        ]

        from subprocess import CompletedProcess

        mock_subprocess.return_value = CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(mock_projects), stderr=""
        )

        # Test project data similar to real ONAP configuration
        project_data = {
            "name": "ONAP",
            "primary_scm": "gerrit",
            "gerrit_url": "https://gerrit.onap.org",
            "github_mirror_org": "onap",
        }

        # Perform discovery
        repositories = self.discovery.discover_repositories("ONAP", project_data)

        # Verify results
        assert len(repositories) == 3

        # Check first repository
        aai_common = repositories[0]
        assert aai_common["gerrit_path"] == "aai/aai-common"
        assert aai_common["scm_platform"] == "gerrit"
        assert aai_common["github_name"] == "aai-common"  # Last component
        assert aai_common["archived"] is False
        assert aai_common["project"] == "ONAP"

        # Check archived repository
        integration_repo = repositories[2]
        assert integration_repo["gerrit_path"] == "integration/testsuite"
        assert integration_repo["archived"] is True  # READ_ONLY state

    @patch("subprocess.run")
    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    @patch("lftools_ng.core.github_discovery.GitHubDiscovery")
    def test_gerrit_with_github_mirrors(self, mock_github_class, mock_ssh_config, mock_subprocess):
        """Test Gerrit discovery enhanced with GitHub mirror information."""
        # Mock SSH config
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        # Mock Gerrit SSH response
        mock_gerrit_projects = [
            {
                "name": "project/awesome-tool",
                "description": "An awesome development tool",
                "state": "ACTIVE",
            }
        ]

        from subprocess import CompletedProcess

        mock_subprocess.return_value = CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(mock_gerrit_projects), stderr=""
        )

        # Mock GitHub discovery
        mock_github_discovery = Mock()
        mock_github_discovery.discover_repositories.return_value = [
            {
                "name": "awesome-tool",
                "description": "Mirror: An awesome development tool",
                "archived": False,
                "private": False,
            }
        ]
        mock_github_class.return_value = mock_github_discovery

        # Test project data with GitHub mirrors
        project_data = {
            "name": "TestProject",
            "primary_scm": "gerrit",
            "gerrit_url": "https://gerrit.example.org",
            "github_mirror_org": "test-project",
        }

        # Perform discovery
        repositories = self.discovery.discover_repositories("TestProject", project_data)

        # Verify results
        assert len(repositories) == 1
        repo = repositories[0]

        # Check Gerrit information
        assert repo["gerrit_path"] == "project/awesome-tool"
        assert repo["scm_platform"] == "gerrit"
        assert repo["github_name"] == "awesome-tool"

        # Check GitHub mirror information
        assert repo["github_mirror_name"] == "awesome-tool"
        assert repo["github_mirror_url"] == "https://github.com/test-project/awesome-tool"

    @patch("subprocess.run")
    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_ssh_connection_failure_handling(self, mock_ssh_config, mock_subprocess):
        """Test graceful handling of SSH connection failures."""
        # Mock SSH config
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "testuser"
        mock_ssh_config.return_value = mock_parser

        # Mock SSH failure
        from subprocess import CompletedProcess

        mock_subprocess.return_value = CompletedProcess(
            args=[],
            returncode=255,  # SSH connection failure
            stdout="",
            stderr="ssh: connect to host gerrit.example.org port 29418: Connection refused",
        )

        project_data = {
            "name": "TestProject",
            "primary_scm": "gerrit",
            "gerrit_url": "https://gerrit.example.org",
        }

        # Perform discovery - should handle failure gracefully
        repositories = self.discovery.discover_repositories("TestProject", project_data)

        # Should return empty list, not crash
        assert repositories == []

    def test_repository_name_mapping_edge_cases(self):
        """Test edge cases in repository name mapping."""
        mapper = self.discovery.mapper

        # Test deeply nested paths
        result = mapper.gerrit_to_github_name("org/project/subproject/component/repo")
        assert result == "org-project-subproject-component-repo"

        # Test paths with special characters
        result = mapper.gerrit_to_github_name("project/sub-project_v2/tool.git")
        assert result == "tool.git"

        # Test empty and None inputs
        assert mapper.gerrit_to_github_name("") == ""
        assert mapper.gerrit_to_github_name(None) == ""

        # Test normalization
        normalized = mapper.normalize_repository_name("Project-Name_123")
        assert normalized == "project-name_123"

    @patch("lftools_ng.core.gerrit_ssh.SSHConfigParser")
    def test_ssh_username_resolution(self, mock_ssh_config):
        """Test SSH username resolution from SSH config."""
        # Mock SSH config with username mapping
        mock_parser = Mock()
        mock_parser.get_username_for_host.return_value = "mygerrituser"
        mock_ssh_config.return_value = mock_parser

        client = GerritSSHClient()
        username = client._get_ssh_username("gerrit.onap.org")

        assert username == "mygerrituser"
        mock_parser.get_username_for_host.assert_called_once_with("gerrit.onap.org")

    def test_project_data_validation(self):
        """Test validation of project data configurations."""
        # Test missing primary_scm
        project_data = {"name": "TestProject", "gerrit_url": "https://gerrit.example.org"}
        repositories = self.discovery.discover_repositories("TestProject", project_data)
        assert repositories == []

        # Test missing SCM URL
        project_data = {
            "name": "TestProject",
            "primary_scm": "gerrit",
            # Missing gerrit_url
        }
        repositories = self.discovery.discover_repositories("TestProject", project_data)
        assert repositories == []

        # Test unsupported SCM
        project_data = {
            "name": "TestProject",
            "primary_scm": "svn",
            "svn_url": "https://svn.example.org",
        }
        repositories = self.discovery.discover_repositories("TestProject", project_data)
        assert repositories == []


class TestRealWorldScenarios:
    """Test scenarios based on real Linux Foundation projects."""

    def setup_method(self):
        """Set up test fixtures."""
        self.discovery = RepositoryDiscovery()

    def test_onap_style_repository_structure(self):
        """Test with ONAP-style nested repository structure."""
        mapper = self.discovery.mapper

        # Typical ONAP repositories
        onap_repos = [
            "aai/aai-common",
            "aai/babel",
            "aai/champ",
            "integration/testsuite",
            "integration/devtoolkit",
            "policy/engine",
            "policy/api",
            "sdc/sdc-workflow-designer",
        ]

        # Test mapping for each
        expected_mappings = {
            "aai/aai-common": "aai-common",
            "aai/babel": "babel",
            "integration/testsuite": "testsuite",
            "policy/engine": "engine",
            "sdc/sdc-workflow-designer": "sdc-workflow-designer",
        }

        for gerrit_path, expected_github in expected_mappings.items():
            # Ensure this path is in our test data
            assert gerrit_path in onap_repos, f"Test repository {gerrit_path} not in onap_repos"
            result = mapper.gerrit_to_github_name(gerrit_path)
            assert result == expected_github, (
                f"Failed for {gerrit_path}: got {result}, expected {expected_github}"
            )

    def test_oran_style_repository_structure(self):
        """Test with O-RAN-SC style repository structure."""
        mapper = self.discovery.mapper

        # Typical O-RAN-SC repositories
        oran_repos = [
            "pti/rtp",
            "ric-plt/e2mgr",
            "ric-plt/rtmgr",
            "sim/o1-interface",
            "nonrtric/plt/rappmanager",
        ]

        expected_mappings = {
            "pti/rtp": "rtp",
            "ric-plt/e2mgr": "e2mgr",
            "sim/o1-interface": "o1-interface",
            "nonrtric/plt/rappmanager": "rappmanager",
        }

        for gerrit_path, expected_github in expected_mappings.items():
            # Ensure this path is in our test data
            assert gerrit_path in oran_repos, f"Test repository {gerrit_path} not in oran_repos"
            result = mapper.gerrit_to_github_name(gerrit_path)
            assert result == expected_github, (
                f"Failed for {gerrit_path}: got {result}, expected {expected_github}"
            )

    def test_reverse_mapping_fuzzy_matching(self):
        """Test reverse mapping with fuzzy matching capabilities."""
        mapper = self.discovery.mapper

        # Simulate a real project's repositories
        project_gerrit_repos = [
            "aai/aai-common",
            "aai/babel",
            "integration/testsuite",
            "integration/devtoolkit",
            "policy/engine",
            "policy/api",
        ]

        # Test finding candidates for various GitHub names
        test_cases = [
            ("babel", ["aai/babel"]),
            ("testsuite", ["integration/testsuite"]),
            ("engine", ["policy/engine"]),
            ("api", ["policy/api"]),
            ("aai-common", ["aai/aai-common"]),
        ]

        for github_name, expected_candidates in test_cases:
            candidates = mapper.github_to_gerrit_candidates(github_name, project_gerrit_repos)
            for expected in expected_candidates:
                assert expected in candidates, (
                    f"Expected {expected} in candidates for {github_name}, got {candidates}"
                )
