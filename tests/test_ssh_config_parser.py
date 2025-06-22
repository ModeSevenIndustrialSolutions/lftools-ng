# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for SSH configuration parser."""

import os
import pathlib
import tempfile
from unittest.mock import patch

from lftools_ng.core.ssh_config_parser import SSHConfigParser


class TestSSHConfigParser:
    """Test SSH configuration file parsing."""

    def test_parse_empty_config(self):
        """Test parsing when no config file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "config"
            parser = SSHConfigParser(config_path)

            config = parser.get_config_for_host("example.com")
            assert config == {}

            usernames = parser.get_preferred_usernames("example.com")
            # Should include current user and common usernames
            assert len(usernames) > 0

    def test_parse_basic_config(self):
        """Test parsing basic SSH config."""
        config_content = """
# Comment line
Host example.com
    User testuser
    Port 2222
    IdentityFile ~/.ssh/test_key

Host *.internal
    User admin
    Port 22
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "config"
            with open(config_path, "w") as f:
                f.write(config_content)

            parser = SSHConfigParser(config_path)

            # Test exact match
            config = parser.get_config_for_host("example.com")
            assert config["user"] == "testuser"
            assert config["port"] == "2222"
            assert config["identityfile"] == "~/.ssh/test_key"

            # Test wildcard match
            config = parser.get_config_for_host("server.internal")
            assert config["user"] == "admin"
            assert config["port"] == "22"

    def test_hostname_pattern_matching(self):
        """Test SSH hostname pattern matching."""
        config_content = """
Host example.com example.org
    User multihost

Host 192.168.*
    User iprange

Host !exclude.test *.test
    User negation

Host *.test
    User wildcard
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "config"
            with open(config_path, "w") as f:
                f.write(config_content)

            parser = SSHConfigParser(config_path)

            # Test multiple hosts
            config = parser.get_config_for_host("example.com")
            assert config["user"] == "multihost"
            config = parser.get_config_for_host("example.org")
            assert config["user"] == "multihost"

            # Test IP ranges
            config = parser.get_config_for_host("192.168.1.1")
            assert config["user"] == "iprange"

            # Test negation (comes before wildcard in config)
            config = parser.get_config_for_host("exclude.test")
            assert config.get("user") != "negation"  # Should be excluded, fallback to wildcard
            assert config.get("user") == "wildcard"  # Matches the later *.test pattern

            config = parser.get_config_for_host("other.test")
            assert config["user"] == "negation"  # Matches the first negation pattern

            # Test fallback wildcard
            config = parser.get_config_for_host("server.test")
            assert config["user"] == "negation"  # First match wins

    def test_get_preferred_usernames(self):
        """Test username preference ordering."""
        config_content = """
Host configured.com
    User sshuser
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "config"
            with open(config_path, "w") as f:
                f.write(config_content)

            parser = SSHConfigParser(config_path)

            # Mock current user
            with patch.dict(os.environ, {"USER": "currentuser"}):
                # Host with SSH config
                usernames = parser.get_preferred_usernames("configured.com")
                assert usernames[0] == "sshuser"  # SSH config first
                assert "currentuser" in usernames  # Current user second
                assert "ubuntu" in usernames  # Common usernames included

                # Host without SSH config
                usernames = parser.get_preferred_usernames("unconfigured.com")
                assert usernames[0] == "currentuser"  # Current user first
                assert "ubuntu" in usernames  # Common usernames included

    def test_get_host_config_summary(self):
        """Test getting host configuration summary."""
        config_content = """
Host test.com
    User testuser
    Port 2222
    IdentityFile ~/.ssh/test_key
    ProxyCommand ssh gateway -W %h:%p
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "config"
            with open(config_path, "w") as f:
                f.write(config_content)

            parser = SSHConfigParser(config_path)

            summary = parser.get_host_config_summary("test.com")
            assert summary["hostname"] == "test.com"
            assert summary["username"] == "testuser"
            assert summary["port"] == "2222"
            assert summary["config_found"] is True
            assert summary["proxy_command"] == "ssh gateway -W %h:%p"
            assert len(summary["preferred_usernames"]) > 0
            assert summary["preferred_usernames"][0] == "testuser"

    def test_case_insensitive_directives(self):
        """Test that SSH config directives are case insensitive."""
        config_content = """
Host example.com
    USER testuser
    PORT 2222
    IdentityFile ~/.ssh/test_key
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = pathlib.Path(tmpdir) / "config"
            with open(config_path, "w") as f:
                f.write(config_content)

            parser = SSHConfigParser(config_path)

            config = parser.get_config_for_host("example.com")
            assert config["user"] == "testuser"  # Keys should be lowercase
            assert config["port"] == "2222"
