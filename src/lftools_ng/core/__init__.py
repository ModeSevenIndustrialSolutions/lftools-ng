# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Core modules for lftools-ng."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lftools_ng.core.jenkins import JenkinsClient
    from lftools_ng.core.projects import ProjectManager

__all__ = ["JenkinsClient", "ProjectManager"]


def __getattr__(name: str) -> Any:
    """Lazy import for core modules."""
    if name == "JenkinsClient":
        from lftools_ng.core.jenkins import JenkinsClient
        return JenkinsClient
    elif name == "ProjectManager":
        from lftools_ng.core.projects import ProjectManager
        return ProjectManager
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
