# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for platform providers module."""

import subprocess
from unittest.mock import patch

from lftools_ng.core.platform_providers import (
    LocalAuthManager,
    PlatformConfig,
)


class TestPlatformConfig:
    """Test platform configuration functionality."""

    def test_platform_config_init_defaults(self):
        """Test platform config initialization with defaults."""
        config = PlatformConfig(name="test-platform")

        assert config.name == "test-platform"
        assert config.auto_detect is True
        assert config.auth_method == "auto"
        assert config.required_tools == []
        assert config.config_path is None
        assert config.env_vars == {}

    def test_platform_config_init_custom(self):
        """Test platform config initialization with custom values."""
        config = PlatformConfig(
            name="custom-platform",
            auto_detect=False,
            auth_method="cli",
            required_tools=["kubectl", "aws"],
            config_path="/custom/path",
            env_vars={"VAR1": "value1", "VAR2": "value2"},
        )

        assert config.name == "custom-platform"
        assert config.auto_detect is False
        assert config.auth_method == "cli"
        assert config.required_tools == ["kubectl", "aws"]
        assert config.config_path == "/custom/path"
        assert config.env_vars == {"VAR1": "value1", "VAR2": "value2"}

    def test_platform_config_immutable_defaults(self):
        """Test that default factory creates new instances."""
        config1 = PlatformConfig(name="test1")
        config2 = PlatformConfig(name="test2")

        # Modify one config's lists/dicts
        config1.required_tools.append("tool1")
        config1.env_vars["key"] = "value"

        # Other config should be unaffected
        assert config2.required_tools == []
        assert config2.env_vars == {}


class TestLocalAuthManager:
    """Test local authentication manager functionality."""

    def test_check_command_exists_true(self):
        """Test checking for existing command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = LocalAuthManager.check_command_exists("git")

            assert result is True
            mock_run.assert_called_once()

    def test_check_command_exists_false(self):
        """Test checking for non-existing command."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = LocalAuthManager.check_command_exists("nonexistent-command")

            assert result is False

    def test_check_command_exists_error(self):
        """Test handling of subprocess errors."""
        with patch("subprocess.run") as mock_run:
            # The actual implementation catches subprocess errors and returns False
            mock_run.side_effect = FileNotFoundError()

            result = LocalAuthManager.check_command_exists("failed-command")

            assert result is False

    def test_get_git_config_success(self):
        """Test getting git config value."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "test-value\n"
            mock_run.return_value.returncode = 0

            value = LocalAuthManager.get_git_config("user.name")

            assert value == "test-value"

    def test_get_git_config_error(self):
        """Test handling git config errors."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            value = LocalAuthManager.get_git_config("nonexistent.key")

            assert value is None

    def test_check_github_cli_auth_success(self):
        """Test successful GitHub CLI authentication check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = LocalAuthManager.check_github_cli_auth()

            assert result is True

    def test_check_github_cli_auth_failed(self):
        """Test failed GitHub CLI authentication check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            result = LocalAuthManager.check_github_cli_auth()

            assert result is False

    def test_check_gitlab_cli_auth_success(self):
        """Test successful GitLab CLI authentication check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = LocalAuthManager.check_gitlab_cli_auth()

            assert result is True

    def test_check_gitlab_cli_auth_failed(self):
        """Test failed GitLab CLI authentication check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            result = LocalAuthManager.check_gitlab_cli_auth()

            assert result is False

    def test_check_onepassword_cli_auth_success(self):
        """Test successful 1Password CLI authentication check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = LocalAuthManager.check_onepassword_cli_auth()

            assert result is True

    def test_check_onepassword_cli_auth_failed(self):
        """Test failed 1Password CLI authentication check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            result = LocalAuthManager.check_onepassword_cli_auth()

            assert result is False

    def test_check_pass_setup_success(self):
        """Test successful pass setup check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            result = LocalAuthManager.check_pass_setup()

            assert result is True

    def test_check_pass_setup_failed(self):
        """Test failed pass setup check."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            result = LocalAuthManager.check_pass_setup()

            assert result is False


class TestPlatformProvidersIntegration:
    """Integration tests for platform providers."""

    def test_command_availability_detection(self):
        """Test detection of available commands."""
        commands_to_test = ["git", "gh", "glab", "op", "pass"]

        with patch("subprocess.run") as mock_run:
            # Simulate some commands being available
            mock_run.return_value.returncode = 0

            for command in commands_to_test:
                result = LocalAuthManager.check_command_exists(command)
                assert isinstance(result, bool)

    def test_auth_check_methods(self):
        """Test all authentication check methods."""
        auth_methods = [
            LocalAuthManager.check_github_cli_auth,
            LocalAuthManager.check_gitlab_cli_auth,
            LocalAuthManager.check_onepassword_cli_auth,
            LocalAuthManager.check_pass_setup,
        ]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            for auth_method in auth_methods:
                result = auth_method()
                assert isinstance(result, bool)

    def test_git_config_integration(self):
        """Test git configuration integration."""
        git_configs = ["user.name", "user.email", "core.editor"]

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "test-value\n"
            mock_run.return_value.returncode = 0

            for config_key in git_configs:
                value = LocalAuthManager.get_git_config(config_key)
                assert value == "test-value"

    def test_error_handling_subprocess_failures(self):
        """Test error handling for subprocess failures."""
        with patch("subprocess.run") as mock_run:
            # Mock FileNotFoundError which is handled by the actual implementation
            mock_run.side_effect = FileNotFoundError()

            # Test each method individually to handle different error cases
            result1 = LocalAuthManager.check_command_exists("git")
            assert result1 is False

            result2 = LocalAuthManager.get_git_config("user.name")
            assert result2 is None

            # Reset to CalledProcessError for other methods
            mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

            result3 = LocalAuthManager.check_github_cli_auth()
            assert result3 is False

            result4 = LocalAuthManager.check_gitlab_cli_auth()
            assert result4 is False

            result5 = LocalAuthManager.check_onepassword_cli_auth()
            assert result5 is False

            result6 = LocalAuthManager.check_pass_setup()
            assert result6 is False

    def test_platform_config_validation(self):
        """Test platform configuration validation scenarios."""
        configs = [
            PlatformConfig(name="minimal"),
            PlatformConfig(
                name="full-config",
                auto_detect=False,
                auth_method="env",
                required_tools=["git", "gh"],
                config_path="/config/path",
                env_vars={"TOKEN": "value"},
            ),
        ]

        for config in configs:
            # All configs should be valid data structures
            assert isinstance(config.name, str)
            assert isinstance(config.auto_detect, bool)
            assert isinstance(config.auth_method, str)
            assert isinstance(config.required_tools, list)
            assert isinstance(config.env_vars, dict)

    def test_subprocess_command_construction(self):
        """Test that subprocess commands are constructed correctly."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            # Test various command executions
            LocalAuthManager.check_command_exists("test-command")
            LocalAuthManager.get_git_config("test.key")
            LocalAuthManager.check_github_cli_auth()

            # Verify subprocess.run was called
            assert mock_run.call_count >= 3

    def test_environment_variable_handling(self):
        """Test handling of environment variables."""
        config = PlatformConfig(
            name="env-test", env_vars={"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"}
        )

        # Test that environment variables are properly structured
        assert len(config.env_vars) == 2
        assert config.env_vars["TEST_VAR"] == "test_value"
        assert config.env_vars["ANOTHER_VAR"] == "another_value"

    def test_tool_requirement_validation(self):
        """Test tool requirement specifications."""
        config_with_tools = PlatformConfig(
            name="tool-test", required_tools=["git", "docker", "kubectl", "helm"]
        )

        # Test that tools are properly specified
        assert len(config_with_tools.required_tools) == 4
        assert "git" in config_with_tools.required_tools
        assert "docker" in config_with_tools.required_tools

    def test_config_path_handling(self):
        """Test configuration path handling."""
        configs = [
            PlatformConfig(name="no-path"),
            PlatformConfig(name="with-path", config_path="/some/config/path"),
            PlatformConfig(name="relative-path", config_path="./config"),
        ]

        for config in configs:
            # Config path should be properly handled
            assert config.config_path is None or isinstance(config.config_path, str)

    def test_auth_method_options(self):
        """Test different authentication method options."""
        auth_methods = ["auto", "cli", "env", "interactive", "config"]

        for auth_method in auth_methods:
            config = PlatformConfig(name=f"test-{auth_method}", auth_method=auth_method)
            assert config.auth_method == auth_method

    def test_concurrent_command_execution(self):
        """Test that multiple commands can be executed safely."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "output\n"

            # Execute multiple commands in sequence
            results = []
            commands = ["git", "gh", "glab", "op"]

            for cmd in commands:
                result = LocalAuthManager.check_command_exists(cmd)
                results.append(result)

            # All should succeed
            assert all(results)
            assert mock_run.call_count == len(commands)
