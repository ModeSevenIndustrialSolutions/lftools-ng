# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Integration tests for test configuration data."""

import pathlib

import yaml

from lftools_ng.core.projects import ProjectManager


class TestConfigIntegration:
    """Integration tests for test configuration files."""

    def test_test_config_projects_loads(self, test_config_dir: pathlib.Path) -> None:
        """Test that test_config/projects.yaml loads properly."""
        projects_file = test_config_dir / "projects.yaml"
        assert projects_file.exists()

        with open(projects_file) as f:
            data = yaml.safe_load(f)

        assert "projects" in data
        assert len(data["projects"]) > 0

        # Verify we have the expected test projects
        project_names = {p["name"] for p in data["projects"]}
        expected_names = {"TestProject1", "TestProject2", "TestProject3", "ArchivedProject"}
        assert expected_names.issubset(project_names)

    def test_test_config_repositories_loads(self, test_config_dir: pathlib.Path) -> None:
        """Test that test_config/repositories.yaml loads properly."""
        repos_file = test_config_dir / "repositories.yaml"
        assert repos_file.exists()

        with open(repos_file) as f:
            data = yaml.safe_load(f)

        assert "repositories" in data
        assert len(data["repositories"]) > 0

        # Verify we have repositories for our test projects
        projects = {r["project"] for r in data["repositories"]}
        expected_projects = {"TestProject1", "TestProject2", "TestProject3", "ArchivedProject"}
        assert expected_projects.issubset(projects)

    def test_test_config_servers_loads(self, test_config_dir: pathlib.Path) -> None:
        """Test that test_config/servers.yaml loads properly."""
        servers_file = test_config_dir / "servers.yaml"
        assert servers_file.exists()

        with open(servers_file) as f:
            data = yaml.safe_load(f)

        assert "servers" in data
        assert len(data["servers"]) > 0

        # Verify we have servers for our test projects
        has_test_projects = False
        for server in data["servers"]:
            projects = server.get("projects", [])
            if any(
                p in ["TestProject1", "TestProject2", "TestProject3", "ArchivedProject"]
                for p in projects
            ):
                has_test_projects = True
                break

        assert has_test_projects, "No servers found with test projects"

    def test_project_manager_with_test_data(
        self, project_manager_with_test_data: ProjectManager
    ) -> None:
        """Test that ProjectManager works with test data."""
        # Test loading projects
        projects = project_manager_with_test_data.list_projects()
        assert len(projects) >= 4  # At least our 4 test projects

        project_names = {p["name"] for p in projects}
        expected_names = {"TestProject1", "TestProject2", "TestProject3", "ArchivedProject"}
        assert expected_names.issubset(project_names)

        # Test loading repositories
        repositories_data = project_manager_with_test_data.list_repositories()
        assert repositories_data["total"] > 0
        assert repositories_data["active"] > 0
        assert repositories_data["archived"] > 0

        # Test loading servers (this should now work with our dummy data)
        servers = project_manager_with_test_data.list_servers()
        assert len(servers) > 0

        # Verify server structure
        for server in servers:
            assert "name" in server
            assert "type" in server
            assert "projects" in server
