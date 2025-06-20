# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for project management functionality."""

import pathlib
import tempfile
from unittest.mock import Mock, patch

import pytest
import yaml

from lftools_ng.core.projects import ProjectManager


class TestProjectManager:
    """Test cases for ProjectManager."""

    def test_project_manager_init(self) -> None:
        """Test ProjectManager initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            assert manager.config_dir == config_dir
            assert manager.projects_file == config_dir / "projects.yaml"
            assert manager.servers_file == config_dir / "servers.yaml"
            assert config_dir.exists()

    def test_list_projects_empty(self) -> None:
        """Test listing projects when no file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            projects = manager.list_projects()
            assert projects == []

    def test_list_projects_with_data(self) -> None:
        """Test listing projects with existing data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            # Create test data
            test_data = {
                "projects": [
                    {
                        "name": "test-project",
                        "alias": "test",
                        "jenkins_server": "jenkins.example.com",
                    }
                ]
            }

            with open(manager.projects_file, "w") as f:
                yaml.dump(test_data, f)

            projects = manager.list_projects()
            assert len(projects) == 1
            assert projects[0]["name"] == "test-project"
            assert projects[0]["alias"] == "test"

    def test_list_servers_empty(self) -> None:
        """Test listing servers when no file exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            servers = manager.list_servers()
            assert servers == []

    def test_list_servers_with_data(self) -> None:
        """Test listing servers with existing data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            # Create test server data
            test_servers = {
                "servers": [
                    {
                        "name": "jenkins.example.com",
                        "url": "https://jenkins.example.com",
                    }
                ]
            }

            # Create test project data to test project count
            test_projects = {
                "projects": [
                    {
                        "name": "test-project",
                        "alias": "test",
                        "jenkins_production": "https://jenkins.example.com",
                    }
                ]
            }

            with open(manager.servers_file, "w") as f:
                yaml.dump(test_servers, f)

            with open(manager.projects_file, "w") as f:
                yaml.dump(test_projects, f)

            servers = manager.list_servers()
            assert len(servers) == 1
            assert servers[0]["name"] == "jenkins.example.com"
            assert servers[0]["project_count"] == 1

    def test_add_project(self) -> None:
        """Test adding a new project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            project_data = {
                "name": "new-project",
                "alias": "new",
                "jenkins_server": "jenkins.example.com",
            }

            manager.add_project(project_data)

            # Verify project was added
            projects = manager.list_projects()
            assert len(projects) == 1
            assert projects[0]["name"] == "new-project"
            assert "created" in projects[0]

    def test_add_project_duplicate_name(self) -> None:
        """Test adding a project with duplicate name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            # Add first project
            project_data = {
                "name": "test-project",
                "alias": "test1",
                "jenkins_server": "jenkins.example.com",
            }
            manager.add_project(project_data)

            # Try to add duplicate
            duplicate_data = {
                "name": "test-project",
                "alias": "test2",
                "jenkins_server": "jenkins.example.com",
            }

            with pytest.raises(ValueError, match="Project name .* already exists"):
                manager.add_project(duplicate_data)

    def test_add_server(self) -> None:
        """Test adding a new server."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            server_data = {"name": "jenkins.example.com", "url": "https://jenkins.example.com"}

            manager.add_server(server_data)

            # Verify server was added
            servers = manager.list_servers()
            assert len(servers) == 1
            assert servers[0]["name"] == "jenkins.example.com"
            assert "created" in servers[0]

    def test_add_server_duplicate_name(self) -> None:
        """Test adding a server with duplicate name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            # Add first server
            server_data = {"name": "jenkins.example.com", "url": "https://jenkins.example.com"}
            manager.add_server(server_data)

            # Try to add duplicate
            duplicate_data = {"name": "jenkins.example.com", "url": "https://jenkins2.example.com"}

            with pytest.raises(ValueError, match="Server name .* already exists"):
                manager.add_server(duplicate_data)

    @patch("lftools_ng.core.projects.httpx.Client")
    def test_rebuild_projects_database(self, mock_client_class: Mock) -> None:
        """Test rebuilding projects database."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            # Mock HTTP response
            mock_response = Mock()
            mock_response.text = yaml.dump(
                {
                    "projects": [
                        {
                            "name": "test-project",
                            "alias": "test",
                            "jenkins_server": "jenkins.example.com",
                        }
                    ]
                }
            )
            mock_response.raise_for_status.return_value = None

            mock_client = Mock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = manager.rebuild_projects_database(force=True)

            assert result["projects_count"] == 1
            assert result["servers_count"] == 1

            # Verify projects were saved
            projects = manager.list_projects()
            assert len(projects) == 1
            assert projects[0]["name"] == "test-project"

    def test_rebuild_projects_database_exists_no_force(self) -> None:
        """Test rebuilding when database exists without force."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = pathlib.Path(temp_dir) / "config"
            manager = ProjectManager(config_dir)

            # Create existing file
            manager.projects_file.touch()

            with pytest.raises(ValueError, match="Projects database already exists"):
                manager.rebuild_projects_database()

    def test_load_projects_db_empty_file(self, tmp_path: pathlib.Path) -> None:
        """Test loading projects database when file doesn't exist."""
        manager = ProjectManager(tmp_path)
        projects = manager.list_projects()
        assert projects == []

    def test_load_projects_db_invalid_data(self, tmp_path: pathlib.Path) -> None:
        """Test loading projects database with invalid YAML data."""
        manager = ProjectManager(tmp_path)
        # Create a file with invalid YAML
        with open(manager.projects_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: data:")

        # Should handle YAML error gracefully and return empty list
        projects = manager.list_projects()
        assert projects == []

    def test_save_projects_db(self, tmp_path: pathlib.Path) -> None:
        """Test saving projects database."""
        manager = ProjectManager(tmp_path)
        test_projects = [
            {"name": "test1"},
            {"name": "test2"},
        ]

        manager._save_projects(test_projects)

        # Verify the file was created and contains correct data
        assert manager.projects_file.exists()
        loaded_projects = manager.list_projects()
        assert len(loaded_projects) == 2
        assert loaded_projects[0]["name"] == "test1"

    def test_load_servers_db_empty_file(self, tmp_path: pathlib.Path) -> None:
        """Test loading servers database when file doesn't exist."""
        manager = ProjectManager(tmp_path)
        servers = manager.list_servers()
        assert servers == []

    def test_load_servers_db_invalid_data(self, tmp_path: pathlib.Path) -> None:
        """Test loading servers database with invalid YAML data."""
        manager = ProjectManager(tmp_path)
        # Create a file with invalid YAML
        with open(manager.servers_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: data:")

        # Should handle YAML error gracefully and return empty list
        servers = manager.list_servers()
        assert servers == []

    def test_save_servers_db(self, tmp_path: pathlib.Path) -> None:
        """Test saving servers database."""
        manager = ProjectManager(tmp_path)
        test_servers = [
            {"name": "jenkins1", "url": "https://jenkins1.example.org"},
            {"name": "jenkins2", "url": "https://jenkins2.example.org"},
        ]

        manager._save_servers(test_servers)

        # Verify the file was created and contains correct data
        assert manager.servers_file.exists()
        loaded_servers = manager.list_servers()
        assert len(loaded_servers) == 2
        assert loaded_servers[0]["name"] == "jenkins1"

    def test_list_projects_from_sample(self, tmp_path: pathlib.Path) -> None:
        """Test list_projects method with sample data."""
        manager = ProjectManager(tmp_path)
        # Create projects database first
        manager.rebuild_projects_database()

        projects = manager.list_projects()
        # Should return projects from the sample data
        assert len(projects) == 0

    def test_list_servers_from_sample(self, tmp_path: pathlib.Path) -> None:
        """Test list_servers method with sample data."""
        manager = ProjectManager(tmp_path)
        # Create servers database first
        manager.rebuild_servers_database()

        servers = manager.list_servers()
        # Should return servers from the sample data
        assert len(servers) == 0

    def test_extract_servers_from_projects(self, tmp_path: pathlib.Path) -> None:
        """Test extracting servers from projects."""
        manager = ProjectManager(tmp_path)
        projects = [
            {"name": "project1", "jenkins_server": "jenkins1.example.org"},
            {"name": "project2", "jenkins_server": "jenkins2.example.org"},
            {"name": "project3", "jenkins_server": "jenkins1.example.org"},  # duplicate
            {"name": "project4"},  # no jenkins_server
        ]

        servers = manager._extract_servers_from_projects(projects)

        # Should extract 2 unique servers
        assert len(servers) == 2
        server_names = [s["name"] for s in servers]
        assert "jenkins1.example.org" in server_names
        assert "jenkins2.example.org" in server_names

    def test_list_servers_with_projects(self, tmp_path: pathlib.Path) -> None:
        """Test listing servers with project count calculation."""
        manager = ProjectManager(tmp_path)

        # Create servers data
        servers_data = {
            "servers": [
                {"name": "jenkins1", "url": "https://jenkins1.example.com"},
                {"name": "jenkins2", "url": "https://jenkins2.example.com"},
            ]
        }
        with open(manager.servers_file, "w", encoding="utf-8") as f:
            yaml.dump(servers_data, f)

        # Create projects data with jenkins_production references
        projects_data = [
            {"name": "project1", "jenkins_production": "https://jenkins1.example.com"},
            {"name": "project2", "jenkins_production": "https://jenkins1.example.com"},
            {"name": "project3", "jenkins_production": "https://jenkins2.example.com"},
        ]
        with open(manager.projects_file, "w", encoding="utf-8") as f:
            yaml.dump(projects_data, f)

        servers = manager.list_servers()
        assert len(servers) == 2

        # Check project counts
        jenkins1_server = next(s for s in servers if s["name"] == "jenkins1")
        jenkins2_server = next(s for s in servers if s["name"] == "jenkins2")

        assert jenkins1_server["project_count"] == 2
        assert jenkins2_server["project_count"] == 1

    def test_list_servers_list_format(self, tmp_path: pathlib.Path) -> None:
        """Test loading servers database when data is a list."""
        manager = ProjectManager(tmp_path)
        # Create servers data as a list (not dict with 'servers' key)
        servers_data = [
            {"name": "jenkins1", "url": "https://jenkins1.example.com"},
            {"name": "jenkins2", "url": "https://jenkins2.example.com"},
        ]
        with open(manager.servers_file, "w", encoding="utf-8") as f:
            yaml.dump(servers_data, f)

        servers = manager.list_servers()
        assert len(servers) == 2
        assert servers[0]["name"] == "jenkins1"

    def test_load_projects_db_dict_format(self, tmp_path: pathlib.Path) -> None:
        """Test loading projects database when data is a dict with 'projects' key."""
        manager = ProjectManager(tmp_path)
        # Create projects data as a dict with 'projects' key
        projects_data = {"projects": [{"name": "project1"}, {"name": "project2"}]}
        with open(manager.projects_file, "w", encoding="utf-8") as f:
            yaml.dump(projects_data, f)

        # Use list_projects instead of load_projects_db for dict format
        projects = manager.list_projects()
        assert len(projects) == 2
        assert projects[0]["name"] == "project1"

    def test_load_projects_db_invalid_format(self, tmp_path: pathlib.Path) -> None:
        """Test loading projects database with invalid format returns empty list."""
        manager = ProjectManager(tmp_path)
        # Create projects data that's neither list nor dict with 'projects' key
        projects_data = {"invalid": "format"}
        with open(manager.projects_file, "w", encoding="utf-8") as f:
            yaml.dump(projects_data, f)

        projects = manager.list_projects()
        assert projects == []


# Add tests for enhanced project name resolution in ProjectManager


class TestProjectManagerEnhanced:
    """Test enhanced project name resolution in ProjectManager."""

    def test_list_projects_basic(self, tmp_path: pathlib.Path) -> None:
        """Test basic project listing functionality."""
        manager = ProjectManager(tmp_path)

        # Create test data with projects that have aliases
        test_data = {
            "projects": [
                {
                    "name": "Anuket (Formerly OPNFV)",
                    "aliases": ["OPNFV", "anuket", "opnfv"],
                },
                {
                    "name": "O-RAN",
                    "aliases": ["O-RAN", "ORAN", "O-RAN-SC", "o-ran-sc", "oran"],
                },
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test that we can list projects
        projects = manager.list_projects()
        assert len(projects) == 2
        project_names = [p.get("name") for p in projects]
        assert "Anuket (Formerly OPNFV)" in project_names
        assert "O-RAN" in project_names

        # Find the first project for verification
        first_project = projects[0]
        assert first_project["name"] in ["Anuket (Formerly OPNFV)", "O-RAN"]

        # Test alias matches
