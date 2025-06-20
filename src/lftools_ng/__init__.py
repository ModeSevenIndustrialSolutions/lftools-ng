# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""lftools-ng: Next-generation Linux Foundation Release Engineering Tools."""

__version__ = "0.1.0"
__author__ = "LF Release Engineering"
__email__ = "releng@linuxfoundation.org"

from lftools_ng.core.jenkins import JenkinsClient

__all__ = ["JenkinsClient"]
