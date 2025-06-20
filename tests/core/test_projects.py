# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for project management functionality."""

import pathlib
import tempfile
from unittest.mock import MagicMock, Mock, patch

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
        projects = manager.load_projects_db()
        assert projects == []

    def test_load_projects_db_invalid_data(self, tmp_path: pathlib.Path) -> None:
        """Test loading projects database with invalid YAML data."""
        manager = ProjectManager(tmp_path)
        # Create a file with invalid YAML
        with open(manager.projects_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: data:")

        # Should handle YAML error gracefully and return empty list
        projects = manager.load_projects_db()
        assert projects == []

    def test_save_projects_db(self, tmp_path: pathlib.Path) -> None:
        """Test saving projects database."""
        manager = ProjectManager(tmp_path)
        test_projects = [
            {"name": "test1"},
            {"name": "test2"},
        ]

        manager.save_projects_db(test_projects)

        # Verify the file was created and contains correct data
        assert manager.projects_file.exists()
        loaded_projects = manager.load_projects_db()
        assert len(loaded_projects) == 2
        assert loaded_projects[0]["name"] == "test1"

    def test_load_servers_db_empty_file(self, tmp_path: pathlib.Path) -> None:
        """Test loading servers database when file doesn't exist."""
        manager = ProjectManager(tmp_path)
        servers = manager.load_servers_db()
        assert servers == []

    def test_load_servers_db_invalid_data(self, tmp_path: pathlib.Path) -> None:
        """Test loading servers database with invalid YAML data."""
        manager = ProjectManager(tmp_path)
        # Create a file with invalid YAML
        with open(manager.servers_file, "w", encoding="utf-8") as f:
            f.write("invalid: yaml: data:")

        # Should handle YAML error gracefully and return empty list
        servers = manager.load_servers_db()
        assert servers == []

    def test_save_servers_db(self, tmp_path: pathlib.Path) -> None:
        """Test saving servers database."""
        manager = ProjectManager(tmp_path)
        test_servers = [
            {"name": "jenkins1", "url": "https://jenkins1.example.org"},
            {"name": "jenkins2", "url": "https://jenkins2.example.org"},
        ]

        manager.save_servers_db(test_servers)

        # Verify the file was created and contains correct data
        assert manager.servers_file.exists()
        loaded_servers = manager.load_servers_db()
        assert len(loaded_servers) == 2
        assert loaded_servers[0]["name"] == "jenkins1"

    def test_enumerate_projects(self, tmp_path: pathlib.Path) -> None:
        """Test enumerate_projects method."""
        manager = ProjectManager(tmp_path)
        projects = manager.enumerate_projects()

        # Should return at least one example project
        assert len(projects) > 0
        assert "example-project" in [p.get("name") for p in projects]

    def test_enumerate_servers(self, tmp_path: pathlib.Path) -> None:
        """Test enumerate_servers method."""
        manager = ProjectManager(tmp_path)
        servers = manager.enumerate_servers()

        # Should return at least one example server
        assert len(servers) > 0
        assert "jenkins-prod" in [s.get("name") for s in servers]

    def test_rebuild_projects_db(self, tmp_path: pathlib.Path) -> None:
        """Test rebuild_projects_db method."""
        manager = ProjectManager(tmp_path)
        count = manager.rebuild_projects_db()

        # Should return a count of projects
        assert isinstance(count, int)
        assert count > 0

        # Should create the projects file
        assert manager.projects_file.exists()

    def test_rebuild_servers_db(self, tmp_path: pathlib.Path) -> None:
        """Test rebuild_servers_db method."""
        manager = ProjectManager(tmp_path)
        count = manager.rebuild_servers_db()

        # Should return a count of servers
        assert isinstance(count, int)
        assert count > 0

        # Should create the servers file
        assert manager.servers_file.exists()

    @patch("httpx.Client")
    def test_fetch_projects_from_default_source_success(
        self, mock_client_class: Mock, tmp_path: pathlib.Path
    ) -> None:
        """Test fetching projects from default source successfully."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = "projects:\n  - name: remote-project"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        manager = ProjectManager(tmp_path)
        projects = manager._fetch_projects_from_default_source()

        assert len(projects) == 1
        assert projects[0]["name"] == "remote-project"

    @patch("httpx.Client")
    def test_fetch_projects_from_url_success(self, mock_client_class: Mock, tmp_path: pathlib.Path) -> None:
        """Test fetching projects from URL successfully."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = "projects:\n  - name: url-project"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        manager = ProjectManager(tmp_path)
        projects = manager._fetch_projects_from_url("https://example.com/projects.yaml")

        assert len(projects) == 1
        assert projects[0]["name"] == "url-project"

    @patch("httpx.Client")
    def test_fetch_servers_from_url_success(self, mock_client_class: Mock, tmp_path: pathlib.Path) -> None:
        """Test fetching servers from URL successfully."""
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.text = "servers:\n  - name: url-server\n    url: https://jenkins.example.org"
        mock_response.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        manager = ProjectManager(tmp_path)
        servers = manager._fetch_servers_from_url("https://example.com/servers.yaml")

        assert len(servers) == 1
        assert servers[0]["name"] == "url-server"

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
                {"name": "jenkins2", "url": "https://jenkins2.example.com"}
            ]
        }
        with open(manager.servers_file, "w", encoding="utf-8") as f:
            yaml.dump(servers_data, f)

        # Create projects data with jenkins_production references
        projects_data = [
            {"name": "project1", "jenkins_production": "https://jenkins1.example.com"},
            {"name": "project2", "jenkins_production": "https://jenkins1.example.com"},
            {"name": "project3", "jenkins_production": "https://jenkins2.example.com"}
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
            {"name": "jenkins2", "url": "https://jenkins2.example.com"}
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
        projects_data = {
            "projects": [
                {"name": "project1"},
                {"name": "project2"}
            ]
        }
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

        projects = manager.load_projects_db()
        assert projects == []


# Add tests for enhanced project name resolution in ProjectManager

class TestProjectManagerEnhanced:
    """Test enhanced project name resolution in ProjectManager."""

    def test_find_project_by_name(self, tmp_path: pathlib.Path) -> None:
        """Test finding projects by name or alias."""
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
                }
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test exact name matches
        project = manager.find_project_by_name("Anuket (Formerly OPNFV)")
        assert project is not None
        assert project["name"] == "Anuket (Formerly OPNFV)"

        # Test alias matches
        project = manager.find_project_by_name("OPNFV")
        assert project is not None
        assert project["name"] == "Anuket (Formerly OPNFV)"

        project = manager.find_project_by_name("oran")
        assert project is not None
        assert project["name"] == "O-RAN"

        # Test case insensitive
        project = manager.find_project_by_name("opnfv")
        assert project is not None
        assert project["name"] == "Anuket (Formerly OPNFV)"

        # Test non-existent project
        project = manager.find_project_by_name("nonexistent")
        assert project is None

    def test_resolve_project_name(self, tmp_path: pathlib.Path) -> None:
        """Test resolving project names."""
        manager = ProjectManager(tmp_path)

        # Create test data
        test_data = {
            "projects": [
                {
                    "name": "Anuket (Formerly OPNFV)",
                    "aliases": ["OPNFV", "anuket", "opnfv"],
                }
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test resolving aliases to canonical name
        assert manager.resolve_project_name("OPNFV") == "Anuket (Formerly OPNFV)"
        assert manager.resolve_project_name("anuket") == "Anuket (Formerly OPNFV)"
        assert manager.resolve_project_name("Anuket (Formerly OPNFV)") == "Anuket (Formerly OPNFV)"

        # Test non-existent project
        assert manager.resolve_project_name("nonexistent") is None

    def test_get_project_aliases(self, tmp_path: pathlib.Path) -> None:
        """Test getting project aliases."""
        manager = ProjectManager(tmp_path)

        # Create test data
        test_data = {
            "projects": [
                {
                    "name": "O-RAN",
                    "aliases": ["O-RAN", "ORAN", "O-RAN-SC", "o-ran-sc", "oran"],
                }
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test getting aliases
        aliases = manager.get_project_aliases("O-RAN")
        assert "oran" in aliases
        assert "o-ran-sc" in aliases

        aliases = manager.get_project_aliases("oran")
        assert "O-RAN" in aliases
        assert "O-RAN-SC" in aliases

        # Test non-existent project
        aliases = manager.get_project_aliases("nonexistent")
        assert aliases == []

    def test_is_same_project(self, tmp_path: pathlib.Path) -> None:
        """Test checking if two names refer to the same project."""
        manager = ProjectManager(tmp_path)

        # Create test data
        test_data = {
            "projects": [
                {
                    "name": "Anuket (Formerly OPNFV)",
                    "aliases": ["OPNFV", "anuket", "opnfv"],
                },
                {
                    "name": "ONAP",
                    "aliases": ["ONAP", "onap", "ECOMP"],
                }
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test same project
        assert manager.is_same_project("Anuket (Formerly OPNFV)", "OPNFV")
        assert manager.is_same_project("OPNFV", "anuket")
        assert manager.is_same_project("ONAP", "ECOMP")

        # Test different projects
        assert not manager.is_same_project("OPNFV", "ONAP")
        assert not manager.is_same_project("anuket", "ECOMP")

        # Test with non-existent projects
        assert not manager.is_same_project("nonexistent", "OPNFV")
        assert not manager.is_same_project("", "OPNFV")

    def test_list_project_names_and_aliases(self, tmp_path: pathlib.Path) -> None:
        """Test getting all project names and aliases."""
        manager = ProjectManager(tmp_path)

        # Create test data
        test_data = {
            "projects": [
                {
                    "name": "Anuket (Formerly OPNFV)",
                    "aliases": ["OPNFV", "anuket"],
                },
                {
                    "name": "ONAP",
                    "aliases": ["onap", "ECOMP"],
                }
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test getting all names and aliases
        all_names = manager.list_project_names_and_aliases()

        assert "Anuket (Formerly OPNFV)" in all_names
        assert "OPNFV" in all_names
        assert "anuket" in all_names
        assert "ONAP" in all_names
        assert "onap" in all_names
        assert "ECOMP" in all_names

        # Should be sorted
        assert all_names == sorted(all_names)

        # Should not contain duplicates
        assert len(all_names) == len(set(all_names))
