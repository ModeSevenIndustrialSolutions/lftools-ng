# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Common test fixtures for lftools-ng."""

import pathlib
import shutil
import tempfile
from typing import Any, Dict, Generator

import pytest

from lftools_ng.core.projects import ProjectManager

# Test constants
TEST_DATE_CREATED = "2025-01-01T10:00:00Z"
TEST_DATE_UPDATED = "2025-01-15T10:00:00Z"


@pytest.fixture
def test_config_dir() -> pathlib.Path:
    """Get path to the test_config directory with dummy data."""
    repo_root = pathlib.Path(__file__).parent.parent
    return repo_root / "test_config"


@pytest.fixture
def temp_config_dir(test_config_dir: pathlib.Path) -> Generator[pathlib.Path, None, None]:
    """Create a temporary directory with dummy test config files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config = pathlib.Path(temp_dir) / "config"
        temp_config.mkdir(parents=True, exist_ok=True)

        # Copy test files to temp directory
        for file_name in ["projects.yaml", "repositories.yaml", "servers.yaml"]:
            source_file = test_config_dir / file_name
            target_file = temp_config / file_name
            if source_file.exists():
                shutil.copy2(source_file, target_file)

        yield temp_config


@pytest.fixture
def project_manager_with_test_data(temp_config_dir: pathlib.Path) -> ProjectManager:
    """Create a ProjectManager instance using test data."""
    return ProjectManager(temp_config_dir, auto_init=False)


@pytest.fixture
def sample_project_data() -> Dict[str, Any]:
    """Sample project data for testing."""
    return {
        "name": "TestProject1",
        "display_name": "Test Project One",
        "description": "A test project for unit testing",
        "primary_scm": "gerrit",
        "gerrit_host": "gerrit.testproject1.org",
        "gerrit_server": "https://gerrit.testproject1.org/",
        "github_mirror_org": "testproject1-mirror",
        "github_server": "https://github.com/testproject1-mirror/",
        "jenkins_server": "https://jenkins.testproject1.org/",
        "nexus_server": "https://nexus.testproject1.org/",
        "sonar_server": "https://sonar.testproject1.org/",
        "created": TEST_DATE_CREATED,
        "updated": TEST_DATE_UPDATED
    }


@pytest.fixture
def sample_server_data() -> Dict[str, Any]:
    """Sample server data for testing."""
    return {
        "name": "jenkins.testproject1.org",
        "url": "https://jenkins.testproject1.org/",
        "type": "jenkins",
        "vpn_address": "10.0.1.10",
        "location": "aws",
        "github_mirror_org": None,
        "is_production": True,
        "version": "2.401.3",
        "last_checked": TEST_DATE_UPDATED,
        "created": TEST_DATE_CREATED,
        "updated": TEST_DATE_UPDATED,
        "projects": ["TestProject1"]
    }


@pytest.fixture
def sample_repository_data() -> Dict[str, Any]:
    """Sample repository data for testing."""
    return {
        "project": "TestProject1",
        "gerrit_path": "testproject1/core",
        "github_name": "testproject1-core",
        "description": "Core module for TestProject1",
        "archived": False,
        "created": TEST_DATE_CREATED,
        "updated": TEST_DATE_UPDATED
    }
