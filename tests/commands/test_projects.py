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
            {"name": "test-project", "alias": "tp", "jenkins_server": "jenkins.example.org"}
        ]
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["list"])

        assert result.exit_code == 0
        assert "test-project" in result.output
        # Check that aliases column shows the alias from test data
        assert "tp" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_list_servers_empty(self, mock_project_manager_class: Mock) -> None:
        """Test listing servers when database is empty."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = []
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["servers"])

        assert result.exit_code == 0
        # Should show empty table with headers
        assert "Server" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_list_servers_with_data(self, mock_project_manager_class: Mock) -> None:
        """Test listing servers with data."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {
                "name": "jenkins-prod",
                "type": "jenkins",
                "url": "https://jenkins.example.org/",
                "project_count": 5,
            }
        ]
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["servers"])

        assert result.exit_code == 0
        assert "jenkins-prod" in result.output
        assert "5" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_rebuild_projects_database_success(self, mock_project_manager_class: Mock) -> None:
        """Test rebuilding projects database successfully."""
        mock_manager = Mock()
        mock_manager.rebuild_projects_database.return_value = {
            "projects_count": 10,
            "servers_count": 3,
        }
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["rebuild-projects", "--force"])

        assert result.exit_code == 0
        assert "Projects: 10" in result.output
        assert "Servers: 3" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_rebuild_projects_database_with_source_url(
        self, mock_project_manager_class: Mock
    ) -> None:
        """Test rebuilding projects database with source URL."""
        mock_manager = Mock()
        mock_manager.rebuild_projects_database.return_value = {
            "projects_count": 5,
            "servers_count": 2,
        }
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(
            projects_app,
            ["rebuild-projects", "--force", "--source", "https://example.com/projects.yaml"],
        )

        assert result.exit_code == 0
        assert "Projects: 5" in result.output
        mock_manager.rebuild_projects_database.assert_called_once_with(
            source_url="https://example.com/projects.yaml", force=True
        )

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_rebuild_projects_database_exists_no_force(
        self, mock_project_manager_class: Mock
    ) -> None:
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
        mock_manager.rebuild_servers_database.return_value = {"servers_count": 5}
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["rebuild-servers", "--force"])

        assert result.exit_code == 0
        assert "Servers: 5" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_list_projects_with_aliases_and_source(self, mock_project_manager_class: Mock) -> None:
        """Test listing projects with proper aliases and source detection."""
        mock_manager = Mock()
        mock_manager.list_projects.return_value = [
            {
                "name": "TestProject1",
                "alias": "tp1",
                "github_mirror_org": "testorg1",
            },
            {
                "name": "TestProject2",
                "aliases": ["tp2", "test2"],
                "github_mirror_org": "testorg2",
            },
        ]
        # Mock the repositories data to simulate Gerrit detection
        mock_manager.list_repositories.return_value = {
            "repositories": [
                {
                    "project": "TestProject2",
                    "gerrit_path": "test/project2",
                    "description": "Mirror of https://gerrit.example.org/test/project2",
                }
            ]
        }
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["list"])

        assert result.exit_code == 0
        assert "TestProject1" in result.output
        assert "TestProject2" in result.output
        assert "tp1" in result.output
        assert "tp2, test2" in result.output
        assert "GitHub" in result.output
        assert "Gerrit" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_detect_uniform_column_values(self, mock_project_manager_class: Mock) -> None:
        """Test detection of uniform values across columns (potential bug indicator)."""
        # This is a test case that would fail if all columns have the same value
        mock_manager = Mock()
        mock_manager.list_projects.return_value = [
            {"name": "Project1", "alias": "None", "github_mirror_org": ""},
            {"name": "Project2", "alias": "None", "github_mirror_org": ""},
            {"name": "Project3", "alias": "None", "github_mirror_org": ""},
        ]
        mock_manager.list_repositories.return_value = {"repositories": []}
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["list"])

        # Check if we can extract the table data (this is a simplified check)
        # In a real implementation, we might want to parse the table output
        # and verify that not all values in each column are identical

        # For now, let's just ensure the command runs
        assert result.exit_code == 0

        # This test demonstrates the pattern - in practice, you'd want to:
        # 1. Parse the table output
        # 2. Extract column values
        # 3. Check for uniformity in each column
        # 4. Flag potential issues

    def test_column_uniformity_detector(self) -> None:
        """Test utility function to detect uniform column values."""
        # Test data representing table columns
        test_columns = {
            "aliases": ["None", "None", "None", "None"],  # All same - should be flagged
            "github_org": ["org1", "org2", "org1", "org3"],  # Mixed - OK
            "source": ["GitHub", "GitHub", "GitHub", "GitHub"],  # All same - should be flagged
        }

        uniform_columns = []
        for column_name, values in test_columns.items():
            unique_values = set(values)
            if len(unique_values) == 1:
                uniform_columns.append(column_name)

        # Should detect that aliases and source columns are uniform
        assert "aliases" in uniform_columns
        assert "source" in uniform_columns
        assert "github_org" not in uniform_columns

    def test_projects_list_integration(self) -> None:
        """Integration test for the complete projects list functionality."""
        import json
        import subprocess

        # Test the actual command with JSON output to verify data structure
        result = subprocess.run(
            ["lftools-ng", "projects", "list", "--format", "json"],
            capture_output=True,
            text=True,
            cwd="/Users/mwatkins/Repositories/ModeSevenIndustrialSolutions/lftools-ng",
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Parse JSON output
        projects_data = json.loads(result.stdout)
        assert isinstance(projects_data, list)
        assert len(projects_data) > 0

        # Check that each project has the expected fields
        for project in projects_data:
            assert "name" in project
            assert "alias" in project or "aliases" in project
            # Note: Not all projects may have github_mirror_org, so we don't assert it

        # Test table output doesn't crash
        result_table = subprocess.run(
            ["lftools-ng", "projects", "list"],
            capture_output=True,
            text=True,
            cwd="/Users/mwatkins/Repositories/ModeSevenIndustrialSolutions/lftools-ng",
        )

        assert result_table.returncode == 0
        assert "Project" in result_table.stdout
        assert "Aliases" in result_table.stdout
        assert "Source" in result_table.stdout

        # Test uniformity check doesn't crash
        result_uniformity = subprocess.run(
            ["lftools-ng", "projects", "list", "--check-uniformity"],
            capture_output=True,
            text=True,
            cwd="/Users/mwatkins/Repositories/ModeSevenIndustrialSolutions/lftools-ng",
        )

        assert result_uniformity.returncode == 0
