# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Test connectivity testing functionality."""

from unittest.mock import MagicMock, patch

from lftools_ng.core.connectivity import RESULT_FAILURE, RESULT_SUCCESS, ConnectivityTester


class TestConnectivityTester:
    """Test the ConnectivityTester class."""

    def test_init(self):
        """Test ConnectivityTester initialization."""
        tester = ConnectivityTester(timeout=5)
        assert tester.timeout == 5

    def test_init_default_timeout(self):
        """Test ConnectivityTester default timeout."""
        tester = ConnectivityTester()
        assert tester.timeout == 3

    @patch("lftools_ng.core.connectivity.httpx.Client")
    def test_url_success(self, mock_client):
        """Test successful URL test."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.return_value.__enter__.return_value.head.return_value = mock_response

        tester = ConnectivityTester()
        result = tester.test_url("https://example.com")
        assert result == RESULT_SUCCESS

    @patch("lftools_ng.core.connectivity.httpx.Client")
    def test_url_failure(self, mock_client):
        """Test failed URL test."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.return_value.__enter__.return_value.head.return_value = mock_response

        tester = ConnectivityTester()
        result = tester.test_url("https://example.com")
        assert "404" in result

    def test_url_empty(self):
        """Test URL test with empty URL."""
        tester = ConnectivityTester()
        result = tester.test_url("")
        assert "N/A" in result

    @patch("lftools_ng.core.connectivity.socket.socket")
    def test_ssh_port_success(self, mock_socket):
        """Test successful SSH port test."""
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        mock_socket.return_value = mock_sock

        tester = ConnectivityTester()
        result = tester.test_ssh_port("192.168.1.1")
        assert result == RESULT_SUCCESS

    @patch("lftools_ng.core.connectivity.socket.socket")
    def test_ssh_port_failure(self, mock_socket):
        """Test failed SSH port test."""
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1  # Connection failed
        mock_socket.return_value = mock_sock

        tester = ConnectivityTester()
        result = tester.test_ssh_port("192.168.1.1")
        assert result == RESULT_FAILURE

    def test_ssh_port_empty_host(self):
        """Test SSH port test with empty host."""
        tester = ConnectivityTester()
        result = tester.test_ssh_port("")
        assert "N/A" in result

    @patch("lftools_ng.core.connectivity.subprocess.run")
    def test_ssh_shell_success(self, mock_run):
        """Test successful SSH shell test."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        tester = ConnectivityTester()
        result = tester.test_ssh_shell("192.168.1.1")
        assert result == RESULT_SUCCESS

    @patch("lftools_ng.core.connectivity.subprocess.run")
    def test_ssh_shell_auth_failure(self, mock_run):
        """Test SSH shell test with authentication failure."""
        mock_result = MagicMock()
        mock_result.returncode = 255  # SSH exit code for auth failure
        mock_result.stdout = ""
        mock_result.stderr = "Permission denied (publickey)"  # Auth failure message
        mock_run.return_value = mock_result

        tester = ConnectivityTester()
        result = tester.test_ssh_shell("192.168.1.1")
        assert "⚠" in result  # Warning for auth failure

    @patch("lftools_ng.core.connectivity.subprocess.run")
    def test_ssh_shell_connection_failure(self, mock_run):
        """Test SSH shell test with connection failure."""
        mock_result = MagicMock()
        mock_result.returncode = 255  # SSH connection failed
        mock_result.stdout = ""
        mock_result.stderr = "Connection refused"  # Connection failure message
        mock_run.return_value = mock_result

        tester = ConnectivityTester()
        result = tester.test_ssh_shell("192.168.1.1")
        assert result == RESULT_FAILURE

    def test_ssh_shell_empty_host(self):
        """Test SSH shell test with empty host."""
        tester = ConnectivityTester()
        result = tester.test_ssh_shell("")
        assert "N/A" in result

    def test_test_all(self):
        """Test the test_all method."""
        tester = ConnectivityTester()
        server = {"url": "https://example.com", "vpn_address": "192.168.1.1"}

        with (
            patch.object(tester, "test_url", return_value=RESULT_SUCCESS),
            patch.object(tester, "test_ssh_port", return_value=RESULT_SUCCESS),
            patch.object(tester, "test_ssh_shell", return_value=RESULT_SUCCESS),
        ):
            results = tester.test_all(server)

            assert results["url"] == RESULT_SUCCESS
            assert results["ssh_port"] == RESULT_SUCCESS
            assert results["ssh_shell"] == RESULT_SUCCESS


class TestProjectsConnectivityCommand:
    """Test the projects connectivity CLI command."""

    @patch("lftools_ng.commands.projects.ProjectManager")
    @patch("lftools_ng.core.connectivity.ConnectivityTester")
    def test_connectivity_command_basic(self, mock_connectivity_tester, mock_project_manager):
        """Test basic connectivity command functionality."""
        from typer.testing import CliRunner

        from lftools_ng.commands.projects import projects_app

        # Mock server data
        mock_servers = [
            {"name": "test-server", "url": "https://test.example.com", "vpn_address": "192.168.1.1"}
        ]

        # Mock project manager
        mock_manager = MagicMock()
        mock_manager.list_servers.return_value = mock_servers
        mock_project_manager.return_value = mock_manager

        # Mock connectivity tester
        mock_tester = MagicMock()
        mock_tester.test_url.return_value = RESULT_SUCCESS
        mock_tester.test_ssh_port.return_value = RESULT_SUCCESS
        mock_tester.test_ssh_shell.return_value = RESULT_SUCCESS
        mock_tester.get_last_ssh_details.return_value = {}
        mock_connectivity_tester.return_value = mock_tester

        runner = CliRunner()
        result = runner.invoke(projects_app, ["servers", "connectivity", "--timeout", "1"])

        assert result.exit_code == 0
        assert "Testing connectivity to 1 servers" in result.stdout
        mock_connectivity_tester.assert_called_once_with(timeout=1)

    @patch("lftools_ng.commands.projects.ProjectManager")
    def test_connectivity_command_no_servers(self, mock_project_manager):
        """Test connectivity command with no servers."""
        from typer.testing import CliRunner

        from lftools_ng.commands.projects import projects_app

        # Mock project manager to return no servers
        mock_manager = MagicMock()
        mock_manager.list_servers.return_value = []
        mock_project_manager.return_value = mock_manager

        runner = CliRunner()
        result = runner.invoke(projects_app, ["servers", "connectivity"])

        assert result.exit_code == 0
        assert "No servers to test" in result.stdout
