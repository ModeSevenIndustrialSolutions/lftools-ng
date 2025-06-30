# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for server database initialization functionality."""

import pathlib
import tempfile
from unittest.mock import patch

import pytest

from lftools_ng.core.projects import ProjectManager


class TestServerInitialization:
    """Test server database initialization functionality."""

    def test_server_initialization_prompts_when_missing(self):
        """Test that server initialization prompts when database is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = pathlib.Path(tmpdir)
            manager = ProjectManager(config_dir)

            # Servers file should not exist initially
            assert not manager.servers_file.exists()

            # Mock the prompt to return True (user wants to initialize)
            with patch.object(manager, '_prompt_for_server_initialization', return_value=True), \
                 patch.object(manager, '_create_initial_servers_database', return_value=True):

                result = manager._ensure_servers_database_exists()
                assert result is True

    def test_server_initialization_declines_when_user_says_no(self):
        """Test that server initialization returns False when user declines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = pathlib.Path(tmpdir)
            manager = ProjectManager(config_dir)

            # Servers file should not exist initially
            assert not manager.servers_file.exists()

            # Mock the prompt to return False (user declines initialization)
            with patch.object(manager, '_prompt_for_server_initialization', return_value=False):
                result = manager._ensure_servers_database_exists()
                assert result is False

    def test_server_initialization_skips_when_file_exists(self):
        """Test that server initialization is skipped when file already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = pathlib.Path(tmpdir)
            manager = ProjectManager(config_dir)

            # Create a dummy servers file
            manager.servers_file.parent.mkdir(parents=True, exist_ok=True)
            manager.servers_file.write_text("servers: []")

            # Should return True without prompting
            result = manager._ensure_servers_database_exists()
            assert result is True

    def test_create_initial_servers_database(self):
        """Test that initial servers database is created correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = pathlib.Path(tmpdir)
            manager = ProjectManager(config_dir)

            # Create initial database
            with patch('builtins.print'):  # Suppress console output during test
                result = manager._create_initial_servers_database()

            assert result is True
            assert manager.servers_file.exists()

            # Verify content
            content = manager.servers_file.read_text()
            assert "servers:" in content
            assert "example-jenkins" in content
            assert "example-gerrit" in content

    def test_list_servers_triggers_initialization(self):
        """Test that list_servers triggers initialization when needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = pathlib.Path(tmpdir)
            manager = ProjectManager(config_dir)

            # Mock the initialization to return True
            with patch.object(manager, '_ensure_servers_database_exists', return_value=True), \
                 patch.object(manager, 'servers_file') as mock_file:

                # Mock file exists to return True after initialization
                mock_file.exists.return_value = True
                mock_file.open.return_value.__enter__.return_value.read.return_value = "servers: []"

                with patch('yaml.safe_load', return_value={"servers": []}):
                    servers = manager.list_servers()
                    assert isinstance(servers, list)

    def test_list_servers_returns_empty_when_declined(self):
        """Test that list_servers returns empty list when user declines initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = pathlib.Path(tmpdir)
            manager = ProjectManager(config_dir)

            # Mock the initialization to return False (user declined)
            with patch.object(manager, '_ensure_servers_database_exists', return_value=False):
                servers = manager.list_servers()
                assert servers == []
