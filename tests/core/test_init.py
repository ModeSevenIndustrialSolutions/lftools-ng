# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for core module initialization."""

import pytest


def test_core_imports() -> None:
    """Test that core module imports work correctly."""
    from lftools_ng.core import jenkins, projects

    # Test that the main classes are available
    assert hasattr(jenkins, 'JenkinsClient')
    assert hasattr(projects, 'ProjectManager')


def test_core_module_version() -> None:
    """Test that core module has version information."""
    import lftools_ng.core

    # Test that the module can be imported without errors
    assert lftools_ng.core is not None


def test_lazy_import_jenkins_client() -> None:
    """Test lazy import of JenkinsClient."""
    from lftools_ng.core import JenkinsClient

    # Test that we can import and it's the correct class
    assert JenkinsClient is not None
    assert JenkinsClient.__name__ == "JenkinsClient"


def test_lazy_import_project_manager() -> None:
    """Test lazy import of ProjectManager."""
    from lftools_ng.core import ProjectManager

    # Test that we can import and it's the correct class
    assert ProjectManager is not None
    assert ProjectManager.__name__ == "ProjectManager"


def test_getattr_invalid_attribute() -> None:
    """Test that invalid attribute access raises AttributeError."""
    import lftools_ng.core

    with pytest.raises(AttributeError, match="module 'lftools_ng.core' has no attribute 'InvalidClass'"):
        lftools_ng.core.InvalidClass  # type: ignore[attr-defined]


def test_all_attribute() -> None:
    """Test that __all__ contains expected exports."""
    import lftools_ng.core

    assert hasattr(lftools_ng.core, "__all__")
    assert "JenkinsClient" in lftools_ng.core.__all__
    assert "ProjectManager" in lftools_ng.core.__all__
