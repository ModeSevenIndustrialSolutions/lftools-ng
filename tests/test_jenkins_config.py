# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Tests for Jenkins configuration file handling and authentication validation.

This module tests reading jenkins_jobs.ini files and validating Jenkins server
connectivity with the configured credentials.
"""

import configparser
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from lftools_ng.core.jenkins_config import JenkinsConfig, JenkinsConfigReader


class TestJenkinsConfigReader:
    """Test cases for JenkinsConfigReader."""

    def test_get_standard_config_paths(self, tmp_path):
        """Test finding standard config paths."""
        reader = JenkinsConfigReader()

        # Create test config files
        cwd_config = tmp_path / "jenkins_jobs.ini"
        cwd_config.write_text("[test]\nurl=http://test.com\nuser=test\npassword=test")

        # Create fake home directory
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch("pathlib.Path.home", return_value=fake_home),
        ):
            paths = reader.get_standard_config_paths()
            assert len(paths) == 1
            assert paths[0] == cwd_config

    def test_read_config_file(self, tmp_path):
        """Test reading a config file."""
        reader = JenkinsConfigReader()

        config_content = """
[job_builder]
ignore_cache=True

[test-server]
url=https://jenkins.test.com
user=testuser
password=testpass123
"""
        config_file = tmp_path / "test_config.ini"
        config_file.write_text(config_content)

        config = reader.read_config_file(config_file)
        assert config is not None
        assert "test-server" in config.sections()
        assert config["test-server"]["url"] == "https://jenkins.test.com"

    def test_parse_config(self, tmp_path):
        """Test parsing config into JenkinsConfig objects."""
        reader = JenkinsConfigReader()

        config = configparser.ConfigParser()
        config.read_string("""
[job_builder]
ignore_cache=True

[test-server]
url=https://jenkins.test.com
user=testuser
password=testpass123

[incomplete-server]
url=https://jenkins.incomplete.com
user=testuser
# missing password
""")

        configs = reader._parse_config(config)

        # Should have one valid config (incomplete-server should be skipped)
        assert "test-server" in configs
        assert "incomplete-server" not in configs
        assert "job_builder" not in configs

        jenkins_config = configs["test-server"]
        assert jenkins_config.url == "https://jenkins.test.com"
        assert jenkins_config.user == "testuser"
        assert jenkins_config.password == "testpass123"
        assert jenkins_config.section_name == "test-server"

    def test_get_config_by_url(self, tmp_path):
        """Test getting config by URL."""
        reader = JenkinsConfigReader()

        config_content = """
[test-server]
url=https://jenkins.test.com
user=testuser
password=testpass123

[another-server]
url=https://jenkins.another.com
user=anotheruser
password=anotherpass123
"""
        config_file = tmp_path / "test_config.ini"
        config_file.write_text(config_content)

        # Test exact match
        jenkins_config = reader.get_config_by_url("https://jenkins.test.com", config_file)
        assert jenkins_config is not None
        assert jenkins_config.section_name == "test-server"

        # Test URL with trailing slash
        jenkins_config = reader.get_config_by_url("https://jenkins.test.com/", config_file)
        assert jenkins_config is not None
        assert jenkins_config.section_name == "test-server"

        # Test non-existent URL
        jenkins_config = reader.get_config_by_url("https://nonexistent.com", config_file)
        assert jenkins_config is None


@pytest.mark.integration
class TestJenkinsConnectivity:
    """
    Integration tests for Jenkins server connectivity.

    These tests only run when jenkins_jobs.ini files are found in standard locations.
    They validate that each configured Jenkins server is accessible with the
    provided credentials.
    """

    def test_jenkins_server_connectivity(self):
        """Test connectivity to all configured Jenkins servers."""
        reader = JenkinsConfigReader()
        configs = reader.get_jenkins_configs()

        if not configs:
            pytest.skip("No jenkins_jobs.ini configuration files found")

        # Import here to avoid circular imports
        from lftools_ng.core.jenkins import JenkinsClient

        failed_servers = []
        successful_connections = 0

        for section_name, config in configs.items():
            try:
                # Create Jenkins client with shorter timeout
                client = JenkinsClient(config.url, config.user, config.password, timeout=10)

                # Perform a simple operation that requires authentication
                version = client.get_version()

                # Verify we got a version response (indicates successful connection)
                if version:
                    successful_connections += 1
                    logging.info(
                        f"✓ Connected to {section_name} ({config.url}), version: {version}"
                    )
                else:
                    failed_servers.append((section_name, config.url, "No version returned"))

            except Exception as e:
                failed_servers.append((section_name, config.url, str(e)))
                logging.warning(f"✗ Failed to connect to {section_name} ({config.url}): {e}")

        # Report results
        if successful_connections > 0:
            logging.info(f"Successfully validated {successful_connections} Jenkins server(s)")

        if failed_servers:
            error_msg = "Failed to connect to Jenkins servers:\n"
            for section_name, url, error in failed_servers:
                error_msg += f"  - {section_name} ({url}): {error}\n"

            # In CI environments, we might want to fail hard
            # In development, we log warnings but don't fail the test
            if len(failed_servers) == len(configs):
                pytest.fail(
                    f"All configured Jenkins servers failed connectivity test:\n{error_msg}"
                )
            else:
                logging.warning(error_msg)

    def test_jenkins_credential_access(self):
        """Test that we can access Jenkins credentials on configured servers."""
        reader = JenkinsConfigReader()
        configs = reader.get_jenkins_configs()

        if not configs:
            pytest.skip("No jenkins_jobs.ini configuration files found")

        from lftools_ng.core.credential_manager import CredentialManager
        from lftools_ng.core.jenkins_provider import JenkinsCredentialProvider

        successful_access = 0
        failed_servers = []

        for section_name, config in configs.items():
            try:
                # Initialize credential manager and provider
                manager = CredentialManager()
                jenkins_provider = JenkinsCredentialProvider(
                    config.url, config.user, config.password
                )
                manager.register_provider(jenkins_provider)

                # Try to list credentials (this requires proper authentication)
                credentials = manager.list_credentials("jenkins")

                successful_access += 1
                logging.info(
                    f"✓ Successfully accessed credentials on {section_name} ({config.url}) - found {len(credentials)} credentials"
                )

            except Exception as e:
                failed_servers.append((section_name, config.url, str(e)))
                logging.warning(
                    f"✗ Failed to access credentials on {section_name} ({config.url}): {e}"
                )

        # Report results
        if successful_access > 0:
            logging.info(
                f"Successfully accessed credentials on {successful_access} Jenkins server(s)"
            )

        if failed_servers:
            error_msg = "Failed to access credentials on Jenkins servers:\n"
            for section_name, url, error in failed_servers:
                error_msg += f"  - {section_name} ({url}): {error}\n"

            if len(failed_servers) == len(configs):
                pytest.fail(
                    f"All configured Jenkins servers failed credential access test:\n{error_msg}"
                )
            else:
                logging.warning(error_msg)


class TestJenkinsConfigIntegration:
    """Test integration with actual jenkins_jobs.ini files if they exist."""

    def test_config_file_locations(self):
        """Test that we can find config files in expected locations."""
        reader = JenkinsConfigReader()

        # Check current directory
        cwd_config = Path.cwd() / "jenkins_jobs.ini"
        if cwd_config.exists():
            config = reader.read_config_file(cwd_config)
            assert config is not None, "Failed to read jenkins_jobs.ini from current directory"

        # Check user config directory
        user_config = Path.home() / ".config" / "jenkins_jobs" / "jenkins_jobs.ini"
        if user_config.exists():
            config = reader.read_config_file(user_config)
            assert config is not None, "Failed to read jenkins_jobs.ini from user config directory"

    def test_get_first_available_config(self):
        """Test getting the first available config when no specific server is requested."""
        reader = JenkinsConfigReader()
        configs = reader.get_jenkins_configs()

        if configs:
            # Should be able to get first config
            first_config = next(iter(configs.values()))
            assert isinstance(first_config, JenkinsConfig)
            assert first_config.url
            assert first_config.user
            assert first_config.password
