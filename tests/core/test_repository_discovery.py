# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for repository discovery functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from lftools_ng.core.repository_discovery import RepositoryDiscovery, RepositoryNameMapper


class TestRepositoryNameMapper:
    """Test cases for RepositoryNameMapper."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = RepositoryNameMapper()

    def test_gerrit_to_github_name_simple(self):
        """Test simple Gerrit to GitHub name conversion."""
        result = self.mapper.gerrit_to_github_name("simple-project")
        assert result == "simple-project"

    def test_gerrit_to_github_name_nested_specific(self):
        """Test nested path with specific name."""
        result = self.mapper.gerrit_to_github_name("project/subproject/specific-name")
        assert result == "specific-name"

    def test_gerrit_to_github_name_nested_generic(self):
        """Test nested path with generic name - should flatten."""
        result = self.mapper.gerrit_to_github_name("project/subproject/repo")
        assert result == "project-subproject-repo"

    def test_gerrit_to_github_name_empty(self):
        """Test empty input."""
        result = self.mapper.gerrit_to_github_name("")
        assert result == ""

    def test_github_to_gerrit_candidates_direct_match(self):
        """Test direct GitHub to Gerrit name matching."""
        gerrit_repos = ["simple-project", "other-project"]
        candidates = self.mapper.github_to_gerrit_candidates("simple-project", gerrit_repos)
        assert "simple-project" in candidates

    def test_github_to_gerrit_candidates_last_component(self):
        """Test matching last component of nested paths."""
        gerrit_repos = ["project/subproject/specific-name", "other/repo"]
        candidates = self.mapper.github_to_gerrit_candidates("specific-name", gerrit_repos)
        assert "project/subproject/specific-name" in candidates

    def test_github_to_gerrit_candidates_flattened(self):
        """Test matching flattened names."""
        gerrit_repos = ["project/subproject/repo", "simple-repo"]
        candidates = self.mapper.github_to_gerrit_candidates("project-subproject-repo", gerrit_repos)
        assert "project/subproject/repo" in candidates

    def test_normalize_repository_name(self):
        """Test repository name normalization."""
        result = self.mapper.normalize_repository_name("Project-Name_123")
        assert result == "project-name_123"


class TestRepositoryDiscovery:
    """Test cases for RepositoryDiscovery."""

    def setup_method(self):
        """Set up test fixtures."""
        self.discovery = RepositoryDiscovery()

    @patch('lftools_ng.core.repository_discovery.GerritSSHClient')
    @patch('lftools_ng.core.repository_discovery.GitHubDiscovery')
    def test_init(self, mock_github_discovery, mock_gerrit_ssh):
        """Test RepositoryDiscovery initialization."""
        discovery = RepositoryDiscovery()
        assert hasattr(discovery, 'gerrit_ssh_client')
        assert hasattr(discovery, 'github_discovery')
        assert hasattr(discovery, 'mapper')

    @patch('lftools_ng.core.repository_discovery.RepositoryDiscovery._discover_gerrit_repositories')
    @patch('lftools_ng.core.repository_discovery.RepositoryDiscovery._discover_github_repositories')
    def test_discover_repositories_gerrit_primary(self, mock_github, mock_gerrit):
        """Test repository discovery with Gerrit as primary SCM."""
        mock_gerrit.return_value = [
            {
                "gerrit_path": "test-repo",
                "scm_platform": "gerrit",
                "github_name": "test-repo"
            }
        ]
        mock_github.return_value = []

        project_data = {
            "name": "test-project",
            "primary_scm": "gerrit",
            "gerrit_url": "https://gerrit.example.org"
        }

        repositories = self.discovery.discover_repositories("test-project", project_data)

        assert len(repositories) == 1
        assert repositories[0]["gerrit_path"] == "test-repo"
        assert repositories[0]["project"] == "test-project"
        mock_gerrit.assert_called_once()

    @patch('lftools_ng.core.repository_discovery.RepositoryDiscovery._discover_github_repositories')
    def test_discover_repositories_github_primary(self, mock_github):
        """Test repository discovery with GitHub as primary SCM."""
        mock_github.return_value = [
            {
                "github_name": "test-repo",
                "scm_platform": "github"
            }
        ]

        project_data = {
            "name": "test-project",
            "primary_scm": "github",
            "github_url": "https://github.com/test-org"
        }

        repositories = self.discovery.discover_repositories("test-project", project_data)

        assert len(repositories) == 1
        assert repositories[0]["github_name"] == "test-repo"
        assert repositories[0]["project"] == "test-project"
        mock_github.assert_called_once()

    @patch('lftools_ng.core.repository_discovery.GerritSSHClient')
    def test_discover_gerrit_repositories(self, mock_gerrit_ssh_class):
        """Test Gerrit repository discovery via SSH."""
        # Mock the Gerrit SSH client
        mock_client = Mock()
        mock_client.list_projects.return_value = [
            {
                "name": "test-project/repo1",
                "description": "Test repository 1",
                "state": "ACTIVE"
            },
            {
                "name": "test-project/repo2",
                "description": "Test repository 2",
                "state": "READ_ONLY"
            }
        ]
        mock_gerrit_ssh_class.return_value = mock_client

        discovery = RepositoryDiscovery()
        discovery.gerrit_ssh_client = mock_client

        project_data = {"name": "test-project"}
        repositories = discovery._discover_gerrit_repositories("https://gerrit.example.org", project_data)

        assert len(repositories) == 2
        assert repositories[0]["gerrit_path"] == "test-project/repo1"
        assert repositories[0]["scm_platform"] == "gerrit"
        assert repositories[0]["archived"] is False
        assert repositories[1]["archived"] is True  # READ_ONLY state

    @patch('lftools_ng.core.repository_discovery.GitHubDiscovery')
    def test_discover_github_repositories(self, mock_github_class):
        """Test GitHub repository discovery."""
        # Mock the GitHub discovery
        mock_discovery = Mock()
        mock_discovery.discover_repositories.return_value = [
            {
                "name": "repo1",
                "description": "Test repository 1",
                "archived": False,
                "private": False,
                "language": "Python"
            }
        ]
        mock_github_class.return_value = mock_discovery

        discovery = RepositoryDiscovery()
        discovery.github_discovery = mock_discovery

        project_data = {"name": "test-project"}
        repositories = discovery._discover_github_repositories("https://github.com/test-org", project_data)

        assert len(repositories) == 1
        assert repositories[0]["github_name"] == "repo1"
        assert repositories[0]["scm_platform"] == "github"

    @patch('lftools_ng.core.repository_discovery.GitHubDiscovery')
    def test_enhance_with_github_mirrors(self, mock_github_class):
        """Test enhancement of repositories with GitHub mirror information."""
        # Mock GitHub discovery
        mock_discovery = Mock()
        mock_discovery.discover_repositories.return_value = [
            {
                "name": "repo1",
                "description": "Mirror of repo1",
                "archived": False
            }
        ]
        mock_github_class.return_value = mock_discovery

        discovery = RepositoryDiscovery()
        discovery.github_discovery = mock_discovery

        # Create test repositories
        repositories = [
            {
                "gerrit_path": "project/repo1",
                "github_name": "repo1",
                "scm_platform": "gerrit"
            }
        ]

        discovery._enhance_with_github_mirrors(repositories, "test-org")

        # Verify enhancement
        assert repositories[0]["github_mirror_name"] == "repo1"
        assert repositories[0]["github_mirror_url"] == "https://github.com/test-org/repo1"

    def test_discover_repositories_missing_scm_url(self):
        """Test repository discovery with missing SCM URL."""
        project_data = {
            "name": "test-project",
            "primary_scm": "gerrit"
            # Missing gerrit_url
        }

        repositories = self.discovery.discover_repositories("test-project", project_data)
        assert repositories == []

    def test_discover_repositories_unsupported_scm(self):
        """Test repository discovery with unsupported SCM."""
        project_data = {
            "name": "test-project",
            "primary_scm": "svn",  # Unsupported
            "svn_url": "https://svn.example.org"
        }

        repositories = self.discovery.discover_repositories("test-project", project_data)
        assert repositories == []
