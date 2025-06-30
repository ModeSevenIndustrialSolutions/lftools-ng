# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Data models for lftools-ng project and server management."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class ServerType(Enum):
    """Types of servers in the Linux Foundation infrastructure."""

    JENKINS = "jenkins"
    GERRIT = "gerrit"
    NEXUS = "nexus"  # Sonatype Nexus Repository (artifact storage)
    NEXUS3 = "nexus3"  # Sonatype Nexus Repository 3.x (artifact storage)
    NEXUS_IQ = "nexus-iq"  # Sonatype Lifecycle (security/vulnerability scanning) - typically shared/multi-tenant
    SONAR = "sonar"
    ARTIFACTORY = "artifactory"
    GITLAB = "gitlab"
    GITHUB = "github"
    WIKI = "wiki"
    DOCS = "docs"
    JIRA = "jira"
    LOGS = "logs"


class ServerLocation(Enum):
    """Server hosting locations."""

    VEXXHOST = "vexxhost"
    AWS = "aws"
    GCE = "gce"  # Google Cloud Platform / Google Compute Engine
    KORG = "korg"
    SAAS = "saas"  # For hosted services like JIRA, Confluence, Artifactory
    OTHER = "other"


class WikiType(Enum):
    """Types of wiki systems."""

    MEDIAWIKI = "mediawiki"
    CONFLUENCE = "confluence"
    GITLAB_WIKI = "gitlab_wiki"
    GITHUB_WIKI = "github_wiki"
    OTHER = "other"


class IssueTrackingType(Enum):
    """Types of issue tracking systems."""

    JIRA = "jira"
    GITHUB_ISSUES = "github_issues"
    GITLAB_ISSUES = "gitlab_issues"
    OTHER = "other"


@dataclass
class Project:
    """Represents a Linux Foundation project."""

    name: str
    aliases: list[str] = field(default_factory=list)

    # Server associations (keeping only direct infrastructure)
    gerrit_url: Optional[str] = None
    github_mirror_org: Optional[str] = None
    jenkins_production: Optional[str] = None
    jenkins_sandbox: Optional[str] = None
    nexus_url: Optional[str] = None
    nexus3_url: Optional[str] = None
    sonar_url: Optional[str] = None
    logs_url: Optional[str] = None

    # Primary SCM information (for source code management)
    primary_scm_platform: Optional[str] = None  # "Gerrit", "GitHub", "GitLab", etc.
    primary_scm_url: Optional[str] = None  # Full URL to the primary SCM

    # Metadata
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)


@dataclass
class Server:
    """Represents a server in the Linux Foundation infrastructure."""

    name: str
    url: str
    server_type: ServerType

    # Network and hosting information
    vpn_address: Optional[str] = None
    location: ServerLocation = ServerLocation.OTHER

    # Additional properties based on server type
    github_mirror_org: Optional[str] = None  # For Gerrit servers
    is_production: bool = True  # For Jenkins servers (vs sandbox)

    # Metadata
    version: Optional[str] = None
    last_checked: Optional[datetime] = None
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)

    # Associated projects
    projects: list[str] = field(default_factory=list)

    def is_shared_infrastructure(self) -> bool:
        """Determine if this server is shared/multi-tenant infrastructure.

        Shared infrastructure servers typically:
        - Have no specific project associations (empty projects list)
        - Are specialized service types like security scanning
        - Have generic hostnames with location/function prefixes

        Returns:
            True if this appears to be shared infrastructure, False otherwise.
        """
        # Nexus IQ servers are typically shared security scanning infrastructure
        if self.server_type == ServerType.NEXUS_IQ:
            return True

        # Servers with no project associations may be shared infrastructure
        if not self.projects:
            # Check for shared service indicators in hostname
            hostname_lower = self.name.lower()
            shared_service_indicators = [
                'nexusiq', 'nexus-iq', 'sonarcloud', 'security', 'scan',
                'shared', 'common', 'platform', 'infrastructure'
            ]
            return any(indicator in hostname_lower for indicator in shared_service_indicators)

        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "url": self.url,
            "type": self.server_type.value,
            "vpn_address": self.vpn_address,
            "location": self.location.value,
            "github_mirror_org": self.github_mirror_org,
            "is_production": self.is_production,
            "version": self.version,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "projects": self.projects,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Server:
        """Create from dictionary."""
        # Handle datetime fields
        created = datetime.fromisoformat(data["created"]) if data.get("created") else datetime.now()
        updated = datetime.fromisoformat(data["updated"]) if data.get("updated") else datetime.now()
        last_checked = datetime.fromisoformat(data["last_checked"]) if data.get("last_checked") else None

        return cls(
            name=data["name"],
            url=data["url"],
            server_type=ServerType(data["type"]),
            vpn_address=data.get("vpn_address"),
            location=ServerLocation(data.get("location", "other")),
            github_mirror_org=data.get("github_mirror_org"),
            is_production=data.get("is_production", True),
            version=data.get("version"),
            last_checked=last_checked,
            created=created,
            updated=updated,
            projects=data.get("projects", []),
        )


@dataclass
class Repository:
    """Represents a repository (Gerrit or GitHub) associated with a project."""

    project: str
    gerrit_path: Optional[str] = None  # e.g., "it/dep/l2" for Gerrit repositories
    github_name: Optional[str] = None  # e.g., "it-dep-l2" for GitHub mirror names
    description: Optional[str] = None
    archived: bool = False  # Whether the repository is archived/read-only

    # Metadata
    created: datetime = field(default_factory=datetime.now)
    updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "project": self.project,
            "gerrit_path": self.gerrit_path,
            "github_name": self.github_name,
            "description": self.description,
            "archived": self.archived,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Repository:
        """Create from dictionary."""
        created = datetime.fromisoformat(data["created"]) if data.get("created") else datetime.now()
        updated = datetime.fromisoformat(data["updated"]) if data.get("updated") else datetime.now()

        return cls(
            project=data["project"],
            gerrit_path=data.get("gerrit_path"),
            github_name=data.get("github_name"),
            description=data.get("description"),
            archived=data.get("archived", False),
            created=created,
            updated=updated,
        )


# Constants
FDIO_PROJECT_KEY = "fd.io"

# Known project aliases and mappings
PROJECT_ALIASES: Dict[str, Dict[str, Any]] = {
    "anuket": {
        "primary_name": "Anuket",
        "aliases": ["OPNFV", "anuket", "opnfv"],
        "previous_names": ["OPNFV"],
        "name_patterns": ["anuket", "opnfv", "anuket (formerly opnfv)"],
        "domain": "anuket.io",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://gerrit.opnfv.org"
    },
    "onap": {
        "primary_name": "ONAP",
        "aliases": ["ONAP", "onap", "ECOMP", "ecomp"],
        "previous_names": ["ECOMP"],
        "name_patterns": ["onap", "ecomp"],
        "domain": "onap.org",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://gerrit.onap.org",
        "github_mirror_org": "onap"
    },
    "opendaylight": {
        "primary_name": "OpenDaylight",
        "aliases": ["OpenDaylight", "ODL", "opendaylight", "odl"],
        "previous_names": [],
        "name_patterns": ["opendaylight", "odl"],
        "domain": "opendaylight.org",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://git.opendaylight.org/gerrit",
        "github_mirror_org": "opendaylight"
    },
    "o-ran-sc": {
        "primary_name": "O-RAN Software Community",
        "aliases": ["O-RAN", "ORAN", "O-RAN-SC", "o-ran-sc", "oran"],
        "previous_names": [],
        "name_patterns": ["o-ran", "oran", "o-ran-sc", "o-ran software community"],
        "domain": "o-ran-sc.org",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://gerrit.o-ran-sc.org",
        "github_mirror_org": "o-ran-sc"
    },
    # Additional known projects with aliases
    "agl": {
        "primary_name": "Automotive Grade Linux",
        "aliases": ["AGL", "agl"],
        "previous_names": [],
        "name_patterns": ["agl", "automotive grade linux"],
        "domain": "automotivelinux.org",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://gerrit.automotivelinux.org"
    },
    "akraino": {
        "primary_name": "Akraino Edge Stack",
        "aliases": ["Akraino", "akraino"],
        "previous_names": [],
        "name_patterns": ["akraino", "akraino edge stack"],
        "domain": "akraino.org",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://gerrit.akraino.org",
        "github_mirror_org": "akraino-edge-stack"
    },
    "edgex": {
        "primary_name": "EdgeX Foundry",
        "aliases": ["EdgeX", "edgex", "EdgeX Foundry"],
        "previous_names": [],
        "name_patterns": ["edgex", "edgex foundry"],
        "domain": "edgexfoundry.org",
        "primary_scm_platform": "GitHub",
        "primary_scm_url": "https://github.com/edgexfoundry",
        "github_mirror_org": "edgexfoundry"
    },
    FDIO_PROJECT_KEY: {
        "primary_name": "Fast Data Project",
        "aliases": ["FD.io", FDIO_PROJECT_KEY, "Fast Data"],
        "previous_names": [],
        "name_patterns": [FDIO_PROJECT_KEY, "fdio", "fast data"],
        "domain": "fd.io",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://gerrit.fd.io",
        "github_mirror_org": "FDio"
    },
    "opencord": {
        "primary_name": "OpenCORD",
        "aliases": ["OpenCORD", "opencord", "CORD", "cord"],
        "previous_names": [],
        "name_patterns": ["opencord", "cord", "central office re-architected as a datacenter"],
        "domain": "opencord.org",
        "primary_scm_platform": "Gerrit",
        "primary_scm_url": "https://gerrit.opencord.org",
        "github_mirror_org": "opencord"
    },
    "hyperledger": {
        "primary_name": "Hyperledger",
        "aliases": ["HyperLedger", "Hyperledger", "hyperledger"],
        "previous_names": [],
        "name_patterns": ["hyperledger", "hyper ledger"],
        "domain": "hyperledger.org",
        "primary_scm_platform": "GitHub",
        "primary_scm_url": "https://github.com/hyperledger"
    },
    "zowe": {
        "primary_name": "Zowe",
        "aliases": ["Zowe", "zowe"],
        "previous_names": [],
        "name_patterns": ["zowe"],
        "domain": "zowe.org",
        "primary_scm_platform": "GitHub",
        "primary_scm_url": "https://github.com/zowe"
    },
    # Fall-through projects not listed on platforms inventory but hosted by LF
    "jenkins-ci": {
        "primary_name": "Jenkins CI",
        "aliases": ["Jenkins", "jenkins", "jenkinsci", "jenkins-ci"],
        "previous_names": [],
        "name_patterns": ["jenkins", "jenkinsci", "jenkins ci"],
        "domain": "jenkins.io",
        "primary_scm_platform": "GitHub",
        "primary_scm_url": "https://github.com/jenkinsci"
    },
    "kernel-org": {
        "primary_name": "Kernel.org",
        "aliases": ["KORG", "korg", "kernel.org", "kernel", "linux-kernel"],
        "previous_names": [],
        "name_patterns": ["korg", "kernel", "kernel.org", "linux kernel"],
        "domain": "kernel.org",
        "primary_scm_platform": "Git",
        "primary_scm_url": "https://git.kernel.org"
    },
    "lfit": {
        "primary_name": "Linux Foundation IT",
        "aliases": ["LFIT", "lfit", "linuxfoundation", "linux-foundation"],
        "previous_names": [],
        "name_patterns": ["lfit", "linux foundation it"],
        "domain": "linuxfoundation.org",
        "primary_scm_platform": "GitHub",
        "primary_scm_url": "https://github.com/lfit"
    },
    "yocto": {
        "primary_name": "Yocto Project",
        "aliases": ["Yocto", "yocto"],
        "previous_names": [],
        "name_patterns": ["yocto", "yocto project"],
        "domain": "yoctoproject.org",
        "primary_scm_platform": "Git",
        "primary_scm_url": "https://git.yoctoproject.org"
    },
    "cip": {
        "primary_name": "Civil Infrastructure Platform",
        "aliases": ["CIP", "cip"],
        "previous_names": [],
        "name_patterns": ["cip", "civil infrastructure platform"],
        "domain": "cip-project.org",
        "primary_scm_platform": "GitLab",
        "primary_scm_url": "https://gitlab.com/cip-project"
    },
    "cti": {
        "primary_name": "Core Technologies Initiative",
        "aliases": ["CTI", "cti"],
        "previous_names": [],
        "name_patterns": ["cti", "core technologies initiative"],
        "domain": "coreinfrastructure.org",
        "primary_scm_platform": "GitHub",
        "primary_scm_url": "https://github.com/coreinfrastructure"
    },
    "rot": {
        "primary_name": "Radio over IP",
        "aliases": ["ROT", "rot", "radio-over-ip"],
        "previous_names": [],
        "name_patterns": ["rot", "radio over ip"],
        "domain": "radiooverip.org",
        "primary_scm_platform": "Unknown",
        "primary_scm_url": ""
    },
    "wl": {
        "primary_name": "Windriver Linux",
        "aliases": ["WL", "wl", "windriver", "wind-river"],
        "previous_names": [],
        "name_patterns": ["wl", "windriver", "wind river"],
        "domain": "windriver.com",
        "primary_scm_platform": "Unknown",
        "primary_scm_url": ""
    }
}
