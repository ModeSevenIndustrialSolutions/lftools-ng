# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for project CLI commands."""

from unittest.mock import Mock, patch

from typer.testing import CliRunner

from lftools_ng.commands.projects import projects_app


class TestProjectCommands:
    """Test cases for project CLI commands."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_list_projects_empty(self, mock_project_manager_class: Mock) -> None:
        """Test listing projects when database is empty."""
        mock_manager = Mock()
        mock_manager.list_projects.return_value = []
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["list"])

        assert result.exit_code == 0
        # Should show empty table, not "No projects found"
        assert "Project" in result.output
        assert "Aliases" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_list_projects_with_data(self, mock_project_manager_class: Mock) -> None:
        """Test listing projects with data."""
        mock_manager = Mock()
        mock_manager.list_projects.return_value = [
            {
                "name": "test-project",
                "alias": "tp",
                "jenkins_server": "jenkins.example.org"
            }
        ]
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["list"])

        assert result.exit_code == 0
        assert "test-project" in result.output
        # Check that aliases column is shown (the test data doesn't include aliases, so it shows "None")
        assert "None" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_list_servers_empty(self, mock_project_manager_class: Mock) -> None:
        """Test listing servers when database is empty."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = []
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["servers"])

        assert result.exit_code == 0
        # Should show empty table, not "No servers found"
        assert "Registered Servers" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_list_servers_with_data(self, mock_project_manager_class: Mock) -> None:
        """Test listing servers with data."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {
                "name": "jenkins-prod",
                "type": "jenkins",
                "url": "https://jenkins.example.org/",
                "project_count": 5
            }
        ]
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["servers"])

        assert result.exit_code == 0
        assert "jenkins-prod" in result.output
        assert "5" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_add_project_success(self, mock_project_manager_class: Mock) -> None:
        """Test adding a project successfully."""
        mock_manager = Mock()
        mock_manager.add_project.return_value = True
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, [
            "add-project",
            "test-project",
            "--aliases", "tp",
            "--jenkins-prod", "https://jenkins.example.org"
        ])

        assert result.exit_code == 0
        assert "Successfully added project" in result.output
        mock_manager.add_project.assert_called_once()

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_add_project_duplicate(self, mock_project_manager_class: Mock) -> None:
        """Test adding a duplicate project."""
        mock_manager = Mock()
        mock_manager.add_project.side_effect = ValueError("Project name 'test-project' already exists")
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, [
            "add-project",
            "test-project",
            "--aliases", "tp",
            "--jenkins-prod", "https://jenkins.example.org"
        ])

        assert result.exit_code == 1
        assert "already exists" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_add_server_success(self, mock_project_manager_class: Mock) -> None:
        """Test adding a server successfully."""
        mock_manager = Mock()
        mock_manager.add_server.return_value = True
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, [
            "add-server",
            "jenkins-prod",
            "--url", "https://jenkins.example.org/"
        ])

        assert result.exit_code == 0
        assert "Successfully added server" in result.output
        mock_manager.add_server.assert_called_once()

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_add_server_duplicate(self, mock_project_manager_class: Mock) -> None:
        """Test adding a duplicate server."""
        mock_manager = Mock()
        mock_manager.add_server.side_effect = ValueError("Server name 'jenkins-prod' already exists")
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, [
            "add-server",
            "jenkins-prod",
            "--url", "https://jenkins.example.org/"
        ])

        assert result.exit_code == 1
        assert "already exists" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_rebuild_projects_database_success(self, mock_project_manager_class: Mock) -> None:
        """Test rebuilding projects database successfully."""
        mock_manager = Mock()
        mock_manager.rebuild_projects_database.return_value = {
            "projects_count": 10,
            "servers_count": 3
        }
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["rebuild-projects", "--force"])

        assert result.exit_code == 0
        assert "Projects loaded: 10" in result.output
        assert "Servers discovered: 3" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_rebuild_projects_database_with_source_url(self, mock_project_manager_class: Mock) -> None:
        """Test rebuilding projects database with source URL."""
        mock_manager = Mock()
        mock_manager.rebuild_projects_database.return_value = {
            "projects_count": 5,
            "servers_count": 2
        }
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, [
            "rebuild-projects",
            "--force",
            "--source", "https://example.com/projects.yaml"
        ])

        assert result.exit_code == 0
        assert "Projects loaded: 5" in result.output
        mock_manager.rebuild_projects_database.assert_called_once_with(
            source_url="https://example.com/projects.yaml",
            force=True
        )

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_rebuild_projects_database_exists_no_force(self, mock_project_manager_class: Mock) -> None:
        """Test rebuilding projects database when it exists without force."""
        mock_manager = Mock()
        mock_manager.rebuild_projects_database.side_effect = ValueError(
            "Projects database already exists. Use --force to overwrite."
        )
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["rebuild-projects"])

        assert result.exit_code == 1
        assert "already exists" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_rebuild_servers_database_success(self, mock_project_manager_class: Mock) -> None:
        """Test rebuilding servers database successfully."""
        mock_manager = Mock()
        mock_manager.rebuild_servers_database.return_value = {
            "servers_count": 5
        }
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["rebuild-servers", "--force"])

        assert result.exit_code == 0
        assert "Servers loaded: 5" in result.output
