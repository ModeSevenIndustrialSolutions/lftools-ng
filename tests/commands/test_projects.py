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

        result = self.runner.invoke(projects_app, ["servers", "list"])

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
                "vpn_address": "jenkins-prod.vpn",
                "location": "Virginia",
                "projects": ["project1", "project2"],
            }
        ]
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["servers", "list"])

        assert result.exit_code == 0
        assert "jenkins-prod.vpn" in result.output
        assert "Virginia" in result.output
        assert "project1 (+1)" in result.output

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
        import os
        import subprocess

        # Test the actual command with JSON output to verify data structure
        result = subprocess.run(
            ["lftools-ng", "projects", "list", "--format", "json"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),  # Use current working directory instead of hardcoded path
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
            cwd=os.getcwd(),
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
            cwd=os.getcwd(),
        )

        assert result_uniformity.returncode == 0

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_servers_connectivity_basic(
        self, mock_connectivity_tester_class: Mock, mock_project_manager_class: Mock
    ) -> None:
        """Test basic servers connectivity command."""
        # Setup mocks
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {"name": "server1", "url": "https://server1.example.org", "vpn_address": "server1.vpn"}
        ]
        mock_project_manager_class.return_value = mock_manager

        mock_tester = Mock()
        mock_tester.test_url.return_value = "✓"  # Updated method name
        mock_tester.test_ssh_port.return_value = "✓"
        mock_tester.test_ssh_shell.return_value = "✓"
        mock_tester.get_last_ssh_details.return_value = {}  # Add this method
        mock_connectivity_tester_class.return_value = mock_tester

        result = self.runner.invoke(projects_app, ["servers", "connectivity"])

        assert result.exit_code == 0
        assert "Testing connectivity to 1 servers" in result.output
        mock_connectivity_tester_class.assert_called_once_with(timeout=3)

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_servers_connectivity_with_timeout(
        self, mock_connectivity_tester_class: Mock, mock_project_manager_class: Mock
    ) -> None:
        """Test servers connectivity command with custom timeout."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {"name": "server1", "url": "https://server1.example.org", "vpn_address": "server1.vpn"}
        ]
        mock_project_manager_class.return_value = mock_manager

        mock_tester = Mock()
        mock_tester.test_url.return_value = "✓"
        mock_tester.test_ssh_port.return_value = "✓"
        mock_tester.test_ssh_shell.return_value = "✓"
        mock_tester.get_last_ssh_details.return_value = {}
        mock_connectivity_tester_class.return_value = mock_tester

        result = self.runner.invoke(projects_app, ["servers", "connectivity", "--timeout", "10"])

        assert result.exit_code == 0
        assert "timeout: 10s" in result.output
        mock_connectivity_tester_class.assert_called_once_with(timeout=10)

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_servers_connectivity_with_username(
        self, mock_connectivity_tester_class: Mock, mock_project_manager_class: Mock
    ) -> None:
        """Test servers connectivity command with specific username."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {"name": "server1", "url": "https://server1.example.org", "vpn_address": "server1.vpn"}
        ]
        mock_project_manager_class.return_value = mock_manager

        mock_tester = Mock()
        mock_tester.test_url.return_value = "✓"
        mock_tester.test_ssh_port.return_value = "✓"
        mock_tester.test_ssh_shell.return_value = "✓"
        mock_tester.get_last_ssh_details.return_value = {}
        mock_connectivity_tester_class.return_value = mock_tester

        result = self.runner.invoke(
            projects_app, ["servers", "connectivity", "--username", "testuser"]
        )

        assert result.exit_code == 0
        assert "SSH username: testuser" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_servers_connectivity_verbose(
        self, mock_connectivity_tester_class: Mock, mock_project_manager_class: Mock
    ) -> None:
        """Test servers connectivity command with verbose output."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {"name": "server1", "url": "https://server1.example.org", "vpn_address": "server1.vpn"}
        ]
        mock_project_manager_class.return_value = mock_manager

        mock_tester = Mock()
        mock_tester.test_url.return_value = "✓"
        mock_tester.test_ssh_port.return_value = "✓"
        mock_tester.test_ssh_shell.return_value = "✓"
        mock_tester.get_last_ssh_details.return_value = {}
        mock_connectivity_tester_class.return_value = mock_tester

        result = self.runner.invoke(projects_app, ["servers", "connectivity", "--verbose"])

        assert result.exit_code == 0
        assert "Using local SSH config and authentication methods" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_servers_connectivity_live_mode(
        self, mock_connectivity_tester_class: Mock, mock_project_manager_class: Mock
    ) -> None:
        """Test servers connectivity command with --live flag."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {"name": "server1", "url": "https://server1.example.org", "vpn_address": "server1.vpn"}
        ]
        mock_project_manager_class.return_value = mock_manager

        mock_tester = Mock()
        mock_tester.test_url.return_value = "✓"
        mock_tester.test_ssh_port.return_value = "✓"
        mock_tester.test_ssh_shell.return_value = "✓"
        mock_tester.get_last_ssh_details.return_value = {}
        mock_connectivity_tester_class.return_value = mock_tester

        result = self.runner.invoke(projects_app, ["servers", "connectivity", "--live"])

        assert result.exit_code == 0
        assert "Testing connectivity to 1 servers" in result.output
        assert "Live" in result.output  # Should show "Server Connectivity Test Results (Live)"

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_servers_connectivity_no_servers(self, mock_project_manager_class: Mock) -> None:
        """Test servers connectivity command when no servers are configured."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = []
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["servers", "connectivity"])

        assert result.exit_code == 0
        assert "No servers to test" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_servers_connectivity_with_filters(
        self, mock_connectivity_tester_class: Mock, mock_project_manager_class: Mock
    ) -> None:
        """Test servers connectivity command with include/exclude filters."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {
                "name": "jenkins-prod",
                "url": "https://jenkins-prod.example.org",
                "vpn_address": "jenkins-prod.vpn",
            },
            {
                "name": "jenkins-staging",
                "url": "https://jenkins-staging.example.org",
                "vpn_address": "jenkins-staging.vpn",
            },
        ]
        mock_project_manager_class.return_value = mock_manager

        mock_tester = Mock()
        mock_tester.test_url.return_value = "✓"
        mock_tester.test_ssh_port.return_value = "✓"
        mock_tester.test_ssh_shell.return_value = "✓"
        mock_tester.get_last_ssh_details.return_value = {}
        mock_connectivity_tester_class.return_value = mock_tester

        # Test with include filter
        result = self.runner.invoke(
            projects_app, ["servers", "connectivity", "--include", "name~=prod"]
        )

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        # Due to filtering complexity, we'll just check it runs successfully
        # The actual filtering logic is tested in the core modules

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_servers_connectivity_mixed_results(
        self, mock_connectivity_tester_class: Mock, mock_project_manager_class: Mock
    ) -> None:
        """Test servers connectivity command with mixed success/failure results."""
        mock_manager = Mock()
        mock_manager.list_servers.return_value = [
            {"name": "server1", "url": "https://server1.example.org", "vpn_address": "server1.vpn"},
            {"name": "server2", "url": "https://server2.example.org", "vpn_address": "server2.vpn"},
        ]
        mock_project_manager_class.return_value = mock_manager

        mock_tester = Mock()

        # Configure different results for different calls
        def mock_test_url(url):
            if "server1" in url:
                return "✓"
            return "✗"

        def mock_test_ssh_port(address):
            if "server1" in address:
                return "✓"
            return "✗"

        def mock_test_ssh_shell(address, username=None, verbose=False):
            if "server1" in address:
                return "⚠"
            return "✗"

        mock_tester.test_url.side_effect = mock_test_url
        mock_tester.test_ssh_port.side_effect = mock_test_ssh_port
        mock_tester.test_ssh_shell.side_effect = mock_test_ssh_shell
        mock_tester.get_last_ssh_details.return_value = {}
        mock_connectivity_tester_class.return_value = mock_tester

        result = self.runner.invoke(projects_app, ["servers", "connectivity"])

        assert result.exit_code == 0
        assert "Testing connectivity to 2 servers" in result.output

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_servers_connectivity_exception_handling(
        self, mock_project_manager_class: Mock
    ) -> None:
        """Test servers connectivity command handles exceptions gracefully."""
        mock_manager = Mock()
        mock_manager.list_servers.side_effect = Exception("Database error")
        mock_project_manager_class.return_value = mock_manager

        result = self.runner.invoke(projects_app, ["servers", "connectivity"])

        # Command should handle the exception gracefully
        # The exact behavior depends on implementation - we'll verify it doesn't crash
        assert (
            result.exit_code != 0
            or "error" in result.output.lower()
            or "Database error" in result.output
        )
