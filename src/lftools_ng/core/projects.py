# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Project management core functionality for lftools-ng."""

import logging
import pathlib
import shutil
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import yaml

# Import GitHub discovery
from lftools_ng.core.github_discovery import GitHubDiscovery

logger = logging.getLogger(__name__)

# URL constants to avoid duplication
FDIO_JENKINS_URL = "https://jenkins.fd.io"
LF_JENKINS_URL = "https://jenkins.linuxfoundation.org"
LF_NEXUS_IQ_URL = "https://nexus-iq.wl.linuxfoundation.org"
YOCTO_AUTOBUILDER_URL = "https://autobuilder.yoctoproject.org"

# Server/project name constants
FDIO_KEY = "fd.io"
FDIO_ALT_KEY = "fdio"


class ProjectManager:
    """Manages projects and Jenkins server mappings."""

    def __init__(self, config_dir: pathlib.Path, auto_init: bool = True) -> None:
        """Initialize project manager.

        Args:
            config_dir: Directory path for configuration files
            auto_init: Whether to auto-initialize config from resources
        """
        self.config_dir = config_dir
        self.projects_file = config_dir / "projects.yaml"
        self.servers_file = config_dir / "servers.yaml"
        self.repositories_file = config_dir / "repositories.yaml"  # New repositories file

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Auto-initialize configuration from resources if needed
        if auto_init:
            self._auto_initialize_config()

    def _auto_initialize_config(self) -> None:
        """Auto-initialize configuration from resources directory if config files don't exist."""
        try:
            # Find the resources directory relative to this file
            current_file = pathlib.Path(__file__)
            # Navigate up from src/lftools_ng/core/projects.py to project root
            project_root = current_file.parent.parent.parent.parent
            resources_dir = project_root / "resources"

            if not resources_dir.exists():
                logger.warning(f"Resources directory not found: {resources_dir}")
                return

            files_to_copy = [
                ("projects.yaml", self.projects_file),
                ("servers.yaml", self.servers_file),
                ("repositories.yaml", self.repositories_file)
            ]

            copied_files = []
            for resource_file, config_file in files_to_copy:
                resource_path = resources_dir / resource_file
                if resource_path.exists() and not config_file.exists():
                    shutil.copy2(resource_path, config_file)
                    copied_files.append(resource_file)
                    logger.info(f"Initialized {config_file} from resources")

            if copied_files:
                logger.info(f"Auto-initialized configuration with Linux Foundation data: {', '.join(copied_files)}")

        except Exception as e:
            logger.warning(f"Failed to auto-initialize configuration: {e}")

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all registered projects.

        Returns:
            List of project dictionaries
        """
        if not self.projects_file.exists():
            logger.warning(f"Projects file not found: {self.projects_file}")
            return []

        try:
            with open(self.projects_file) as f:
                data = yaml.safe_load(f)
                if data is None:
                    return []
                projects = data.get("projects", [])
                if not isinstance(projects, list):
                    return []
                # Filter out any None entries that might have been parsed from YAML
                return [p for p in projects if p is not None]
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")
            return []

    def list_servers(self) -> List[Dict[str, Any]]:
        """List all registered Jenkins servers.

        Returns:
            List of server dictionaries
        """
        from lftools_ng.utils.server_utils import load_servers_data

        data = load_servers_data()
        if data is None:
            return []

        # Handle both dictionary and list formats
        if isinstance(data, dict):
            servers = data.get("servers", [])
        elif isinstance(data, list):
            servers = data
        else:
            return []

        if not isinstance(servers, list):
            return []

        try:
            # Load projects for mapping
            projects = self.list_projects()

            # Enhance servers with comprehensive data integration
            self._integrate_server_data_sources(servers, projects)

            # Map projects to servers and calculate project counts
            self._map_projects_to_servers_in_place(servers, projects)

            # Enhance servers with missing URLs
            self._enhance_servers_with_inferred_urls(servers)

            return servers
        except Exception as e:
            logger.error(f"Failed to process servers: {e}")
            return []

    def list_repositories(self, project: Optional[str] = None, include_archived: bool = False) -> Dict[str, Any]:
        """List repositories for projects.

        Args:
            project: Optional project name to filter by
            include_archived: Whether to include archived repositories

        Returns:
            Dictionary with repositories list and metadata
        """
        if not self.repositories_file.exists():
            logger.warning(f"Repositories file not found: {self.repositories_file}")
            return {"repositories": [], "total": 0, "active": 0, "archived": 0}

        try:
            with open(self.repositories_file) as f:
                data = yaml.safe_load(f)
                if data is None:
                    return {"repositories": [], "total": 0, "active": 0, "archived": 0}

                repositories = data.get("repositories", [])
                if not isinstance(repositories, list):
                    return {"repositories": [], "total": 0, "active": 0, "archived": 0}

                # Filter by project if specified
                if project:
                    repositories = [repo for repo in repositories if repo.get("project", "").lower() == project.lower()]

                # Filter archived if not requested
                if not include_archived:
                    repositories = [repo for repo in repositories if not repo.get("archived", False)]

                # Calculate statistics
                total = len(data.get("repositories", []))
                active = len([repo for repo in data.get("repositories", []) if not repo.get("archived", False)])
                archived = total - active

                return {
                    "repositories": repositories,
                    "total": total,
                    "active": active,
                    "archived": archived
                }
        except Exception as e:
            logger.error(f"Failed to load repositories: {e}")
            return {"repositories": [], "total": 0, "active": 0, "archived": 0}

    def get_repository_info(self, project: str, repository: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific repository.

        Args:
            project: Project name
            repository: Repository name (either Gerrit path or GitHub name)

        Returns:
            Repository information if found, None otherwise
        """
        repositories_data = self.list_repositories(include_archived=True)

        for repo in repositories_data["repositories"]:
            if repo.get("project", "").lower() != project.lower():
                continue

            # Match either by Gerrit path or GitHub name
            if (repo.get("gerrit_path") == repository or
                repo.get("github_name") == repository):
                return dict(repo)

        return None



    def rebuild_projects_database(
        self,
        source_url: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, int]:
        """Rebuild projects database from source.

        Args:
            source_url: URL to fetch project configuration from
            force: Force rebuild even if database exists

        Returns:
            Dictionary with rebuild statistics
        """
        if self.projects_file.exists() and not force:
            raise ValueError(
                "Projects database already exists. Use --force to rebuild."
            )

        # Default source URLs for LF projects
        if not source_url:
            # Try to find local resources file relative to the package
            # Go up from src/lftools_ng/core/projects.py to the project root
            package_root = pathlib.Path(__file__).parent.parent.parent.parent
            local_projects_file = package_root / "resources" / "projects.yaml"
            if local_projects_file.exists():
                source_url = f"file://{local_projects_file}"
            else:
                raise FileNotFoundError(
                    f"Projects resource file not found at {local_projects_file}. "
                    "Please ensure the resources directory is present, or specify a source URL."
                )

        try:
            # Fetch project configuration
            logger.info(f"Fetching project configuration from: {source_url}")
            content = self._fetch_config_file(source_url)

            # Parse configuration (always use YAML for our purposes)
            config_data = yaml.safe_load(content)

            # Extract projects
            projects = self._extract_projects_from_config(config_data)

            # Enhance projects with GitHub discovery
            self._enhance_projects_with_github_discovery(projects)

            servers = self._extract_servers_from_projects(projects)

            # Save to files
            self._save_projects(projects)
            self._save_servers(servers)

            logger.info(f"Rebuilt projects database with {len(projects)} projects")
            return {
                "projects_count": len(projects),
                "servers_count": len(servers)
            }

        except Exception as e:
            logger.error(f"Failed to rebuild projects database: {e}")
            raise

    def rebuild_servers_database(
        self,
        source_url: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, int]:
        """Rebuild servers database from source.

        Args:
            source_url: URL to fetch server configuration from
            force: Force rebuild even if database exists

        Returns:
            Dictionary with rebuild statistics
        """
        if self.servers_file.exists() and not force:
            raise ValueError(
                "Servers database already exists. Use --force to rebuild."
            )

        # Default source URLs for LF servers
        if not source_url:
            # Try to find local resources file relative to the package
            # Go up from src/lftools_ng/core/projects.py to the project root
            package_root = pathlib.Path(__file__).parent.parent.parent.parent
            local_servers_file = package_root / "resources" / "servers.yaml"
            if local_servers_file.exists():
                source_url = f"file://{local_servers_file}"
            else:
                raise FileNotFoundError(
                    f"Servers resource file not found at {local_servers_file}. "
                    "Please ensure the resources directory is present, or specify a source URL."
                )

        try:
            # Fetch server configuration
            logger.info(f"Fetching server configuration from: {source_url}")
            content = self._fetch_config_file(source_url)

            # Parse configuration (always use YAML for our purposes)
            config_data = yaml.safe_load(content)

            # Extract servers
            servers = self._extract_servers_from_config(config_data)
            projects = self.list_projects()

            # Map projects to servers
            try:
                projects_mapped = self._map_projects_to_servers(projects, servers)
            except AttributeError as e:
                logger.error(f"Error in _map_projects_to_servers: {e}")
                logger.error(f"Projects type: {type(projects)}, length: {len(projects) if projects else 'N/A'}")
                logger.error(f"Servers type: {type(servers)}, length: {len(servers) if servers else 'N/A'}")
                if projects:
                    logger.error(f"First few projects: {projects[:3]}")
                if servers:
                    logger.error(f"First few servers: {servers[:3]}")
                raise

            # Reconcile VPN addresses with live Tailscale data
            logger.info("Reconciling VPN addresses with Tailscale data...")
            try:
                self._enhance_servers_with_tailscale_data(servers)
                logger.info("VPN address reconciliation completed")
            except Exception as e:
                logger.warning(f"VPN reconciliation failed, continuing without it: {e}")

            # Save to file
            self._save_servers(servers)

            logger.info(f"Rebuilt servers database with {len(servers)} servers")

            return {
                "servers_count": len(servers),
                "projects_mapped": projects_mapped
            }

        except Exception as e:
            logger.error(f"Failed to rebuild servers database: {e}")
            raise

    def _fetch_config_file(self, source_url: str) -> str:
        """
        Fetch configuration file from local file system or remote URL.

        Args:
            source_url: URL or file path to fetch from

        Returns:
            Content of the file as string
        """
        if source_url.startswith('file://'):
            # Handle local file paths
            file_path = source_url[7:]  # Remove 'file://' prefix
            if not os.path.isabs(file_path):
                # Make relative paths relative to the package root
                package_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                file_path = os.path.join(package_root, file_path)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except IOError as e:
                raise Exception(f"Failed to read local file {file_path}: {e}")
        else:
            # Handle remote URLs
            try:
                with httpx.Client(timeout=30) as client:
                    response = client.get(source_url)
                    response.raise_for_status()
                    return str(response.text)
            except httpx.HTTPStatusError as e:
                raise Exception(f"Failed to fetch from {source_url}: {e}")
            except httpx.RequestError as e:
                raise Exception(f"Network error fetching from {source_url}: {e}")

    def _extract_projects_from_config(self, config_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract projects from configuration data."""
        projects = []

        # Extract projects from the rich configuration data
        if "projects" in config_data:
            for project_config in config_data["projects"]:
                # Preserve all the rich data from the resources file
                project = {
                    "name": project_config.get("name", "unknown"),
                    "primary_name": project_config.get("primary_name", project_config.get("name", "unknown")),
                    "aliases": project_config.get("aliases", []),
                    "previous_names": project_config.get("previous_names", []),
                    "gerrit_url": project_config.get("gerrit_url"),
                    "github_mirror_org": project_config.get("github_mirror_org"),
                    "jenkins_production": project_config.get("jenkins_production"),
                    "jenkins_sandbox": project_config.get("jenkins_sandbox"),
                    "nexus_url": project_config.get("nexus_url"),
                    "nexus3_url": project_config.get("nexus3_url"),
                    "wiki_url": project_config.get("wiki_url"),
                    "wiki_type": project_config.get("wiki_type"),
                    "docs_url": project_config.get("docs_url"),
                    "issue_tracking_url": project_config.get("issue_tracking_url"),
                    "issue_tracking_type": project_config.get("issue_tracking_type"),
                    "sonar_url": project_config.get("sonar_url"),
                    "logs_url": project_config.get("logs_url"),
                    "status": "active",
                    "created": self._current_timestamp()
                }

                # For backward compatibility, also set 'alias' field from first alias if available
                if project["aliases"]:
                    project["alias"] = project["aliases"][0]
                else:
                    project["alias"] = project["name"]

                projects.append(project)

        return projects

    def _extract_servers_from_config(self, config_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract servers from configuration data."""
        servers = []

        # This is a placeholder implementation
        if "servers" in config_data:
            for server_config in config_data["servers"]:
                # Skip None entries
                if server_config is None:
                    logger.warning("Skipping None server entry in configuration")
                    continue

                server_name = server_config.get("name", "unknown")
                server_url = server_config.get("url", "")
                server_type = server_config.get("type", "jenkins")  # Default to jenkins
                vpn_address = server_config.get("vpn_address", "")
                location = server_config.get("location", "")
                projects = server_config.get("projects", [])  # Extract projects list

                # If no URL provided, try to infer it
                if not server_url:
                    inferred_url = self._infer_url_from_server_name(server_name, server_type)
                    if inferred_url and self._test_url_accessibility(inferred_url):
                        server_url = inferred_url
                        logger.info(f"Successfully inferred URL for {server_name}: {inferred_url}")
                    elif inferred_url:
                        logger.info(f"Inferred URL {inferred_url} for {server_name} is not accessible")

                server = {
                    "name": server_name,
                    "url": server_url,
                    "type": server_type,
                    "vpn_address": vpn_address,
                    "location": location,
                    "projects": projects,
                    "project_count": len(projects),
                    "status": "active",
                    "created": self._current_timestamp()
                }
                servers.append(server)

        return servers

    def _integrate_server_data_sources(self, servers: List[Dict[str, Any]], _projects: List[Dict[str, Any]]) -> None:
        """Integrate data from multiple sources to fix edge cases and improve consistency.

        Args:
            servers: List of server dictionaries to enhance
            _projects: List of project dictionaries for context (unused but kept for future use)
        """
        # Enhance servers with live Tailscale VPN addresses
        self._enhance_servers_with_tailscale_data(servers)

        for server in servers:
            self._fix_opnfv_anuket_linking(server)
            self._handle_secondary_jenkins_instances(server, servers)
            self._fix_lf_infrastructure_urls(server)
            self._enhance_server_url_if_missing(server)
            self._link_servers_to_projects_by_patterns(server)

    def _enhance_server_url_if_missing(self, server: Dict[str, Any]) -> None:
        """Enhance server with URL if missing, using project-based inference.

        This bypasses accessibility testing for well-documented project infrastructure.
        """
        server_name = server.get("name", "")
        server_url = server.get("url", "")
        server_type = server.get("type", "jenkins")

        # If server has no URL, try to infer one
        if not server_url and server_name:
            # First try project-based resolution (more reliable for known projects)
            project_name = self._resolve_project_from_hostname(server_name.lower())
            if project_name:
                candidate_urls = self._get_project_infrastructure_urls(project_name, server_type)
                if candidate_urls:
                    base_url = candidate_urls[0]

                    # Handle sandbox instances with /sandbox path
                    if 'sandbox' in server_name.lower():
                        inferred_url = f"{base_url}/sandbox"
                    # Handle jenkins-2 secondary instances - typically sandbox instances
                    elif 'jenkins-2' in server_name.lower() or server_name.lower().endswith('-2'):
                        inferred_url = f"{base_url}/sandbox"
                    else:
                        inferred_url = base_url

                    # For well-documented project infrastructure, set URL directly
                    server["url"] = inferred_url
                    logger.info(f"Applied project-based URL for {server_name}: {inferred_url}")
                    return

            # Fallback to legacy pattern matching with accessibility testing
            fallback_url: Optional[str] = self._infer_url_from_server_name(server_name, server_type)
            if fallback_url is not None and self._test_url_accessibility(fallback_url):
                server["url"] = fallback_url
                logger.info(f"Successfully inferred and tested URL for {server_name}: {fallback_url}")
            elif fallback_url is not None:
                logger.debug(f"Inferred URL {fallback_url} for {server_name} is not accessible")

    def _fix_opnfv_anuket_linking(self, server: Dict[str, Any]) -> None:
        """Fix OPNFV/Anuket server linking issue."""
        server_name = server.get("name", "").lower()
        if any(pattern in server_name for pattern in ["opnfv", "anuket"]):
            if not server.get("projects"):
                server["projects"] = []
            # Link to Anuket project (formerly OPNFV)
            if "Anuket" not in server["projects"]:
                server["projects"].append("Anuket")

    def _handle_secondary_jenkins_instances(self, server: Dict[str, Any], servers: List[Dict[str, Any]]) -> None:
        """Handle jenkins-2 instances (usually sandbox/secondary)."""
        server_name = server.get("name", "").lower()
        if "jenkins-2" in server_name or server_name.endswith("-2"):
            # These should typically be linked to the same project as jenkins-1
            primary_server_name = server_name.replace("jenkins-2", "jenkins-1").replace("-2", "-1")
            primary_server = self._find_server_by_name_pattern(servers, primary_server_name)
            if primary_server and primary_server.get("projects"):
                if not server.get("projects"):
                    server["projects"] = []
                # Copy project associations from primary server
                for project in primary_server["projects"]:
                    if project not in server["projects"]:
                        server["projects"].append(project)

    def _fix_lf_infrastructure_urls(self, server: Dict[str, Any]) -> None:
        """Fix Linux Foundation IT infrastructure URLs."""
        server_name = server.get("name", "").lower()
        if "lfit" in server_name or "linuxfoundation" in server_name:
            # These servers should have standard URLs
            if not server.get("url"):
                if "jenkins" in server_name:
                    base_url = "https://jenkins.linuxfoundation.org"
                    if "sandbox" in server_name:
                        server["url"] = f"{base_url}/sandbox"
                    else:
                        server["url"] = base_url
                elif "gerrit" in server_name:
                    server["url"] = "https://gerrit.linuxfoundation.org"

    def _build_project_name_mapping(self, projects: List[Dict[str, Any]]) -> Dict[str, str]:
        """Build a mapping of project identifiers to canonical names.

        Args:
            projects: List of project dictionaries

        Returns:
            Dictionary mapping various project identifiers to canonical names
        """
        mapping = {}

        for project in projects:
            primary_name = project.get("primary_name") or project.get("name", "")
            aliases = project.get("aliases") or []
            previous_names = project.get("previous_names") or []

            # Normalize aliases and previous names
            aliases = [a.strip().lower() for a in aliases]
            previous_names = [pn.strip().lower() for pn in previous_names]

            # Map primary name and all aliases to the canonical name
            for identifier in [primary_name.lower()] + aliases + previous_names:
                if identifier:
                    mapping[identifier] = primary_name

        return mapping

    def _find_server_by_name_pattern(self, servers: List[Dict[str, Any]], pattern: str) -> Optional[Dict[str, Any]]:
        """Find a server by name pattern.

        Args:
            servers: List of server dictionaries
            pattern: Pattern to match against server names

        Returns:
            Matching server dictionary or None
        """
        pattern_lower = pattern.lower()
        for server in servers:
            server_name = server.get("name", "").lower()
            if pattern_lower in server_name or server_name in pattern_lower:
                return server
        return None

    def _link_servers_to_projects_by_patterns(self, server: Dict[str, Any]) -> None:
        """Link servers to projects based on hostname patterns.

        Args:
            server: Server dictionary to enhance
        """
        server_name = server.get("name", "").lower()

        # Define hostname patterns that indicate project association
        project_patterns = {
            "opnfv": "Anuket",
            "anuket": "Anuket",
            "onap": "ONAP",
            "akraino": "Akraino",
            "opendaylight": "OpenDaylight",
            "odl": "OpenDaylight",
            "o-ran-sc": "O-RAN-SC",
            "oran": "O-RAN-SC",
            "opencord": "CORD",
            "edgex": "EdgeX Foundry",
            "edgexfoundry": "EdgeX Foundry",
            "fd.io": "FD.io",
            "fdio": "FD.io",
            "agl": "Automotive Grade Linux",
            "automotivelinux": "Automotive Grade Linux",
            "yocto": "Yocto Project",
            "cip": "Civil Infrastructure Platform",
        }

        for pattern, project_name in project_patterns.items():
            if pattern in server_name:
                if not server.get("projects"):
                    server["projects"] = []
                if project_name not in server["projects"]:
                    server["projects"].append(project_name)
                break  # Only match the first pattern to avoid duplicates

    def _map_projects_to_servers_in_place(
        self,
        servers: List[Dict[str, Any]],
        projects: List[Dict[str, Any]]
    ) -> None:
        """Map projects to servers and update server data in place.

        Args:
            servers: List of server dictionaries to update
            projects: List of project dictionaries containing server URLs
        """
        # Create server lookup mapping
        server_lookup = self._build_server_lookup(servers)

        # Map each project to servers
        for project in projects:
            self._map_single_project_to_servers(project, server_lookup)

        # Update project counts
        for server in servers:
            server["project_count"] = len(server.get("projects", []))

    def _build_server_lookup(self, servers: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Build lookup mapping from server names/URLs to server objects."""
        from urllib.parse import urlparse

        server_lookup = {}
        for server in servers:
            server_name = server.get("name", "")
            server_url = server.get("url", "")

            # Initialize projects list and count if not already set
            if "projects" not in server:
                server["projects"] = []
            if "project_count" not in server:
                server["project_count"] = 0

            # Add to lookup by name
            if server_name:
                server_lookup[server_name] = server
                server_lookup[server_name.lower()] = server

            # Add to lookup by URL (both full URL and domain)
            if server_url:
                server_lookup[server_url] = server
                parsed = urlparse(server_url)
                if parsed.netloc:
                    server_lookup[parsed.netloc] = server
                    server_lookup[parsed.netloc.lower()] = server

        return server_lookup

    def _map_single_project_to_servers(self, project: Dict[str, Any], server_lookup: Dict[str, Dict[str, Any]]) -> None:
        """Map a single project to its servers."""

        project_name = project.get("name", "unknown")

        # Define server URL fields to check
        server_url_fields = [
            "jenkins_production",
            "jenkins_sandbox",
            "gerrit_url",
            "nexus_url",
            "nexus3_url",
            "sonar_url",
            "logs_url"
        ]

        # Check each server URL field in the project
        for field in server_url_fields:
            url = project.get(field)
            if url:
                server = self._find_server_by_url(url, server_lookup)
                if server and project_name not in server["projects"]:
                    server["projects"].append(project_name)

    def _find_server_by_url(self, url: str, server_lookup: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find server by URL in the lookup mapping."""
        from urllib.parse import urlparse

        # First try exact URL match
        if url in server_lookup:
            return server_lookup[url]

        # Try domain name match
        parsed = urlparse(url)
        if parsed.netloc:
            netloc_variations = [
                parsed.netloc,
                parsed.netloc.lower(),
            ]
            for netloc in netloc_variations:
                if netloc in server_lookup:
                    return server_lookup[netloc]

        return None

    def _enhance_servers_with_inferred_urls(self, servers: List[Dict[str, Any]]) -> None:
        """Enhance servers with inferred URLs where missing.

        Args:
            servers: List of server dictionaries to enhance
        """
        for server in servers:
            if not server.get("url"):
                self._infer_and_set_server_url(server)

    def _infer_and_set_server_url(self, server: Dict[str, Any]) -> None:
        """Infer and set URL for a single server."""
        server_name = server.get("name", "")
        server_type = server.get("type", "jenkins")

        # Try to infer URL from server name
        inferred_url = self._infer_url_from_server_name(server_name, server_type)
        if inferred_url:
            # Test if the inferred URL is accessible
            if self._test_url_accessibility(inferred_url):
                server["url"] = inferred_url
                logger.info(f"Inferred accessible URL for {server_name}: {inferred_url}")
            else:
                logger.debug(f"Inferred URL {inferred_url} for {server_name} is not accessible")

        # Special handling for Nexus IQ servers
        if server_type == "nexus-iq" and not server.get("url"):
            self._handle_nexus_iq_url_inference(server, server_name)

    def _handle_nexus_iq_url_inference(self, server: Dict[str, Any], server_name: str) -> None:
        """Handle Nexus IQ URL inference."""
        nexus_iq_url = self._infer_nexus_iq_url(server_name)
        if nexus_iq_url:
            # For internal AWS servers, don't test accessibility
            # as they are only accessible from within the VPN
            if server_name.startswith("aws-"):
                server["url"] = nexus_iq_url
                logger.info(f"Inferred internal Nexus IQ URL for {server_name}: {nexus_iq_url}")
            elif self._test_url_accessibility(nexus_iq_url):
                server["url"] = nexus_iq_url
                logger.info(f"Inferred accessible Nexus IQ URL for {server_name}: {nexus_iq_url}")

    def _infer_nexus_iq_url(self, server_name: str) -> Optional[str]:
        """Infer Nexus IQ URL from server name.

        Args:
            server_name: Server hostname

        Returns:
            Inferred URL or None
        """
        # Nexus IQ servers typically use standard ports and paths
        # Common patterns:
        # 1. https://hostname:8070 (default Nexus IQ port)
        # 2. https://hostname/nexusiq
        # 3. https://hostname (if running on standard HTTPS port)

        if not server_name:
            return None

        # Special handling for Linux Foundation shared Nexus IQ infrastructure
        if server_name == "aws-us-west-2-wl-nexusiq-1":
            # This is the shared LF Nexus IQ server - use public URL
            return LF_NEXUS_IQ_URL

        # For AWS internal servers, we typically can't access them directly
        # but we can document the expected internal URL pattern
        if server_name.startswith("aws-"):
            # AWS internal servers typically use hostname:8070 for Nexus IQ
            return f"https://{server_name}:8070"

        # For public-facing servers, try standard HTTPS
        return f"https://{server_name}"

    def _extract_servers_from_projects(self, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique servers from project configurations using URL analysis."""
        servers = []
        seen_servers: Dict[str, Dict[str, Any]] = {}

        for project in projects:
            # Skip None entries
            if project is None:
                logger.warning("Skipping None project entry")
                continue

            project_name = project.get('name', 'unknown')

            # Extract different types of servers from URL fields
            server_url_mappings = [
                (project.get('gerrit_url'), 'gerrit'),
                (project.get('nexus_url'), 'nexus'),
                (project.get('nexus3_url'), 'nexus3'),
                (project.get('sonar_url'), 'sonar'),
                (project.get('logs_url'), 'logs'),
            ]

            for url, server_type in server_url_mappings:
                if not url:
                    continue

                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    if not parsed.netloc:
                        continue

                    # Create a unique key for the server based on hostname and type
                    server_key = f"{parsed.netloc}-{server_type}"

                    if server_key not in seen_servers:
                        # Create base URL
                        base_url = f"{parsed.scheme}://{parsed.netloc}"

                        # Generate server name from hostname
                        hostname_parts = parsed.netloc.split('.')
                        if len(hostname_parts) >= 2:
                            server_name = f"{hostname_parts[0]}-{server_type}"
                        else:
                            server_name = f"{parsed.netloc}-{server_type}"

                        server = {
                            "name": server_name,
                            "url": base_url,
                            "hostname": parsed.netloc,
                            "type": server_type,
                            "status": "discovered",
                            "projects": [project_name],
                            "created": self._current_timestamp()
                        }
                        seen_servers[server_key] = server
                        servers.append(server)
                    else:
                        # Add project to existing server
                        if project_name not in seen_servers[server_key]["projects"]:
                            seen_servers[server_key]["projects"].append(project_name)

                except Exception as e:
                    logger.warning(f"Failed to parse URL {url} for project {project_name}: {e}")
                    continue

        # Update project counts
        for server in servers:
            server["project_count"] = len(server["projects"])

        return servers

    def _map_projects_to_servers(
        self,
        projects: List[Dict[str, Any]],
        servers: List[Dict[str, Any]]
    ) -> int:
        """Map projects to servers and return count of mapped projects."""
        # Since servers are already extracted with their project lists,
        # we just need to count unique projects across all servers
        mapped_projects = set()

        for server in servers:
            if server is not None and "projects" in server:
                for project_name in server["projects"]:
                    mapped_projects.add(project_name)

        return len(mapped_projects)

    def _save_projects(self, projects: List[Dict[str, Any]]) -> None:
        """Save projects to file."""
        data = {
            "projects": projects,
            "metadata": {
                "updated": self._current_timestamp(),
                "count": len(projects)
            }
        }

        self._save_yaml_with_header(data, self.projects_file)

    def _save_servers(self, servers: List[Dict[str, Any]]) -> None:
        """Save servers to file."""
        data = {
            "servers": servers,
            "metadata": {
                "updated": self._current_timestamp(),
                "count": len(servers)
            }
        }

        self._save_yaml_with_header(data, self.servers_file)

    def _current_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.now().isoformat()

    def _save_yaml_with_header(self, data: Dict[str, Any], file_path: pathlib.Path) -> None:
        """Save YAML data with proper SPDX header and document start marker."""
        header = """# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

---
"""
        with open(file_path, "w") as f:
            f.write(header)
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def _test_url_accessibility(self, url: str) -> bool:
        """Test if a URL is accessible and returns a valid response.

        Args:
            url: URL to test.

        Returns:
            True if URL is accessible (even if authentication is required).
        """
        if not url:
            return False

        try:
            # Test the URL with a short timeout and simple request
            response = httpx.head(url, timeout=5, follow_redirects=True)

            # Consider 2xx, 3xx, 401, 403, and 405 responses as successful
            # 401/403 mean the server exists but requires auth or denies access - still valid URLs
            # Some services return 405 for HEAD requests but are still valid
            if (response.status_code in range(200, 400) or
                response.status_code in [401, 403, 405]):
                logger.debug(f"URL {url} is accessible (status: {response.status_code})")
                return True
            else:
                logger.debug(f"URL {url} returned status: {response.status_code}")
                return False

        except Exception as e:
            logger.debug(f"URL {url} accessibility test failed: {e}")
            return False

    def _infer_url_from_server_name(self, server_name: str, server_type: str) -> Optional[str]:
        """Infer URL from server name for servers without explicit URLs.

        Args:
            server_name: Name of the server (e.g., 'vex-yul-agl-jenkins-1')
            server_type: Type of server ('jenkins', 'gerrit', 'nexus', etc.)

        Returns:
            Inferred URL or None if unable to infer
        """
        if not server_name or not server_type:
            return None

        server_name_lower = server_name.lower()

        # First, try to resolve the project from hostname using fuzzy mapping
        project_name = self._resolve_project_from_hostname(server_name_lower)
        if project_name:
            candidate_urls = self._get_project_infrastructure_urls(project_name, server_type)
            if candidate_urls:
                base_url = candidate_urls[0]

                # Handle sandbox instances with /sandbox path
                if 'sandbox' in server_name_lower:
                    return f"{base_url}/sandbox"

                # Handle jenkins-2 secondary instances - typically sandbox instances
                if 'jenkins-2' in server_name_lower or server_name_lower.endswith('-2'):
                    return f"{base_url}/sandbox"

                # Return the base URL for primary instances
                return base_url

        # Fallback to legacy pattern matching if project resolution fails
        url_patterns = self._get_url_patterns_for_server_type(server_type)
        inferred_url = self._match_server_name_to_patterns(server_name_lower, url_patterns)
        if inferred_url:
            return inferred_url

        # Additional pattern matching for complex server names
        return self._handle_complex_server_patterns(server_name_lower, server_type)

    def _get_url_patterns_for_server_type(self, server_type: str) -> Dict[str, List[str]]:
        """Get URL patterns based on server type."""
        url_patterns = {
            # Jenkins servers - only include confirmed working patterns
            'jenkins': {
                'agl': ['https://build.automotivelinux.org'],  # AGL uses build.automotivelinux.org
                'automotivelinux': ['https://build.automotivelinux.org'],
                'akraino': ['https://jenkins.akraino.org'],
                'onap': ['https://jenkins.onap.org'],
                'opencord': ['https://jenkins.opencord.org'],
                'edgexfoundry': ['https://jenkins.edgexfoundry.org'],
                'o-ran-sc': ['https://jenkins.o-ran-sc.org'],
                'opendaylight': ['https://jenkins.opendaylight.org'],
                'opnfv': ['https://build.opnfv.org'],  # OPNFV uses build.opnfv.org pattern
                FDIO_KEY: [FDIO_JENKINS_URL],
                FDIO_ALT_KEY: [FDIO_JENKINS_URL],
                'lfit': [LF_JENKINS_URL],
                'linuxfoundation': [LF_JENKINS_URL],
                'yocto': [YOCTO_AUTOBUILDER_URL, 'https://jenkins.yoctoproject.org'],
                'yoctoproject': [YOCTO_AUTOBUILDER_URL, 'https://jenkins.yoctoproject.org'],
            },
            # Gerrit servers
            'gerrit': {
                'agl': ['https://gerrit.automotivelinux.org'],
                'automotivelinux': ['https://gerrit.automotivelinux.org'],
                'opnfv': ['https://gerrit.opnfv.org'],
                'akraino': ['https://gerrit.akraino.org'],
                'onap': ['https://gerrit.onap.org'],
                'opencord': ['https://gerrit.opencord.org'],
                'edgexfoundry': ['https://gerrit.edgexfoundry.org'],
                'o-ran-sc': ['https://gerrit.o-ran-sc.org'],
                'opendaylight': ['https://git.opendaylight.org', 'https://gerrit.opendaylight.org'],
                FDIO_KEY: ['https://gerrit.fd.io'],
                FDIO_ALT_KEY: ['https://gerrit.fd.io'],
                'lfit': ['https://gerrit.linuxfoundation.org'],
                'linuxfoundation': ['https://gerrit.linuxfoundation.org'],
            },
            # Nexus servers
            'nexus': {
                'akraino': ['https://nexus.akraino.org'],
                'onap': ['https://nexus.onap.org'],
                'opencord': ['https://nexus.opencord.org'],
                'edgexfoundry': ['https://nexus.edgexfoundry.org'],
                'o-ran-sc': ['https://nexus.o-ran-sc.org'],
                'opendaylight': ['https://nexus.opendaylight.org'],
                FDIO_KEY: ['https://nexus.fd.io'],
                FDIO_ALT_KEY: ['https://nexus.fd.io'],
            }
        }

        return url_patterns.get(server_type, {})

    def _match_server_name_to_patterns(self, server_name: str, patterns: Dict[str, List[str]]) -> Optional[str]:
        """Match server name to URL patterns."""
        for project_key, candidate_urls in patterns.items():
            if project_key in server_name:
                base_url = candidate_urls[0]

                # Handle sandbox instances with /sandbox path
                if 'sandbox' in server_name:
                    return f"{base_url}/sandbox"

                # Handle jenkins-2 secondary instances - typically sandbox instances
                if 'jenkins-2' in server_name or server_name.endswith('-2'):
                    # For most projects, -2 instances are sandbox instances
                    return f"{base_url}/sandbox"

                # Return the base URL for primary instances
                return base_url

        return None

    def _handle_complex_server_patterns(self, server_name: str, server_type: str) -> Optional[str]:
        """Handle additional pattern matching for complex server names."""
        if server_type == 'jenkins':
            # Handle Linux Foundation IT infrastructure
            if 'lfit' in server_name or 'linuxfoundation' in server_name:
                base_url = LF_JENKINS_URL
                if 'sandbox' in server_name:
                    return f"{base_url}/sandbox"
                return base_url

            # Handle Yocto Project infrastructure
            if 'yocto' in server_name:
                return YOCTO_AUTOBUILDER_URL

            # Handle CIP (Civil Infrastructure Platform)
            if 'cip' in server_name:
                return 'https://jenkins.cip-project.org'

        return None

    def enhance_existing_servers(self) -> Dict[str, int]:
        """Enhance existing servers with inferred URLs for servers missing URLs.

        Returns:
            Dictionary with enhancement statistics
        """
        servers = self.list_servers()
        enhanced_count = 0

        for server in servers:
            server_name = server.get("name", "")
            server_url = server.get("url", "")
            server_type = server.get("type", "jenkins")  # Default to jenkins if not specified

            # If server has no URL, try to infer one
            if not server_url and server_name:
                inferred_url = self._infer_url_from_server_name(server_name, server_type)
                if inferred_url and self._test_url_accessibility(inferred_url):
                    server["url"] = inferred_url
                    enhanced_count += 1
                    logger.info(f"Successfully inferred URL for {server_name}: {inferred_url}")
                elif inferred_url:
                    logger.info(f"Inferred URL {inferred_url} for {server_name} is not accessible")

        # Save enhanced servers back to file
        if enhanced_count > 0:
            self._save_servers(servers)
            logger.info(f"Enhanced {enhanced_count} servers with inferred URLs")

        return {
            "servers_total": len(servers),
            "servers_enhanced": enhanced_count
        }

    def _resolve_project_from_hostname(self, server_name: str) -> Optional[str]:
        """Resolve the actual project name from a server hostname using pattern mapping.

        Args:
            server_name: Server hostname

        Returns:
            Resolved project name or None
        """
        server_name = server_name.lower()

        # Define hostname patterns that indicate project association
        project_patterns = {
            "opnfv": "Anuket",
            "anuket": "Anuket",
            "onap": "ONAP",
            "akraino": "Akraino",
            "opendaylight": "OpenDaylight",
            "odl": "OpenDaylight",
            "o-ran-sc": "O-RAN-SC",
            "oran": "O-RAN-SC",
            "opencord": "CORD",
            "edgex": "EdgeX Foundry",
            "edgexfoundry": "EdgeX Foundry",
            "agl": "AGL",
            "automotivelinux": "AGL",
            "fd.io": "FD.io",
            "fdio": "FD.io",
            "lfit": "LF RelEng",
            "linuxfoundation": "LF RelEng",
            "yocto": "Yocto Project",
            "yoctoproject": "Yocto Project"
        }

        for pattern, project in project_patterns.items():
            if pattern in server_name:
                return project

        return None

    def _get_project_infrastructure_urls(self, project_name: str, server_type: str) -> List[str]:
        """Get the current infrastructure URLs for a project.

        Args:
            project_name: Name of the project
            server_type: Type of server (jenkins, gerrit, nexus, etc.)

        Returns:
            List of candidate URLs for the project's infrastructure
        """
        # Map project names to their current infrastructure URLs
        project_infrastructure = {
            "Anuket": {
                "jenkins": ["https://build.opnfv.org"],  # Still uses opnfv.org domain
                "gerrit": ["https://gerrit.opnfv.org"]
            },
            "ONAP": {
                "jenkins": ["https://jenkins.onap.org"],
                "gerrit": ["https://gerrit.onap.org"],
                "nexus": ["https://nexus.onap.org"]
            },
            "Akraino": {
                "jenkins": ["https://jenkins.akraino.org"],
                "gerrit": ["https://gerrit.akraino.org"],
                "nexus": ["https://nexus.akraino.org"]
            },
            "OpenDaylight": {
                "jenkins": ["https://jenkins.opendaylight.org"],
                "gerrit": ["https://git.opendaylight.org", "https://gerrit.opendaylight.org"],
                "nexus": ["https://nexus.opendaylight.org"]
            },
            "O-RAN-SC": {
                "jenkins": ["https://jenkins.o-ran-sc.org"],
                "gerrit": ["https://gerrit.o-ran-sc.org"],
                "nexus": ["https://nexus.o-ran-sc.org"]
            },
            "CORD": {
                "jenkins": ["https://jenkins.opencord.org"],
                "gerrit": ["https://gerrit.opencord.org"]
            },
            "EdgeX Foundry": {
                "jenkins": ["https://jenkins.edgexfoundry.org"],
                "gerrit": ["https://gerrit.edgexfoundry.org"],
                "nexus": ["https://nexus.edgexfoundry.org"]
            },
            "AGL": {
                "jenkins": ["https://build.automotivelinux.org"],
                "gerrit": ["https://gerrit.automotivelinux.org"]
            },
            "FD.io": {
                "jenkins": [FDIO_JENKINS_URL],
                "gerrit": ["https://gerrit.fd.io"]
            },
            "LF RelEng": {
                "jenkins": [LF_JENKINS_URL],
                "gerrit": ["https://gerrit.linuxfoundation.org"]
            },
            "Yocto Project": {
                "jenkins": [YOCTO_AUTOBUILDER_URL, "https://jenkins.yoctoproject.org"]
            }
        }

        if project_name in project_infrastructure:
            project_urls = project_infrastructure[project_name]
            return project_urls.get(server_type, [])

        return []

    def _enhance_projects_with_github_discovery(self, projects: List[Dict[str, Any]]) -> None:
        """Enhance projects with GitHub organization discovery and repository enumeration.

        Args:
            projects: List of project dictionaries to enhance
        """
        from lftools_ng.core.github_discovery import GitHubDiscovery

        logger.info("Enhancing projects with GitHub discovery...")
        discovered_count = 0
        repositories = []

        with GitHubDiscovery() as github_discovery:
            for project in projects:
                proj_name = project.get("name", "")
                existing_org = project.get("github_mirror_org")

                if existing_org:
                    logger.info(f"Project {proj_name} already has GitHub org: {existing_org}")
                else:
                    # Discover GitHub organization
                    logger.info(f"Discovering GitHub org for: {proj_name}")
                    discovered_org = github_discovery.discover_github_organization(project)

                    if discovered_org:
                        project["github_mirror_org"] = discovered_org
                        discovered_count += 1
                        logger.info(f"Found GitHub org for {proj_name}: {discovered_org}")

                # Discover repositories for this project
                project_repos = self._discover_project_repositories(project, github_discovery)
                repositories.extend(project_repos)

        # Save discovered repositories
        if repositories:
            self._save_repositories(repositories)
            logger.info(f"Saved {len(repositories)} repositories for {len(projects)} projects")

        logger.info(f"GitHub discovery enhanced {discovered_count} projects with new organizations")

    def _discover_project_repositories(self, project: Dict[str, Any], github_discovery: Any) -> List[Dict[str, Any]]:
        """Discover repositories for a specific project.

        Args:
            project: Project data dictionary
            github_discovery: GitHub discovery instance

        Returns:
            List of repository dictionaries
        """
        repositories = []
        proj_name = project.get("name", "")
        github_org = project.get("github_mirror_org")

        # Discover repositories from GitHub if we have an organization
        if github_org:
            github_repos = self._discover_github_repositories(github_org, proj_name, github_discovery)
            repositories.extend(github_repos)

        # Add Gerrit repositories if we have Gerrit URL
        gerrit_url = project.get("gerrit_url")
        if gerrit_url:
            gerrit_repos = self._discover_gerrit_repositories(gerrit_url, proj_name)
            repositories.extend(gerrit_repos)

        return repositories

    def _discover_github_repositories(self, github_org: str, project_name: str, github_discovery: Any) -> List[Dict[str, Any]]:
        """Discover repositories from GitHub organization.

        Args:
            github_org: GitHub organization name
            project_name: Project name
            github_discovery: GitHub discovery instance

        Returns:
            List of repository dictionaries
        """
        repositories = []

        try:
            # Get repositories from GitHub API
            response = github_discovery.client.get(f"https://api.github.com/orgs/{github_org}/repos")
            if response.status_code == 200:
                github_repos = response.json()

                for repo in github_repos:
                    repo_data = {
                        "project": project_name,
                        "github_name": repo.get("name", ""),
                        "description": repo.get("description", ""),
                        "archived": repo.get("archived", False),
                        "gerrit_path": self._map_github_to_gerrit_path(repo.get("name", "")),
                        "created": datetime.now().isoformat(),
                        "updated": datetime.now().isoformat(),
                    }
                    repositories.append(repo_data)

        except Exception as e:
            logger.warning(f"Failed to discover GitHub repositories for {github_org}: {e}")

        return repositories

    def _discover_gerrit_repositories(self, gerrit_url: str, project_name: str) -> List[Dict[str, Any]]:
        """Discover repositories from Gerrit.

        Args:
            gerrit_url: Gerrit server URL
            project_name: Project name

        Returns:
            List of repository dictionaries
        """
        repositories: List[Dict[str, Any]] = []

        try:
            # This would need actual Gerrit API implementation
            # For now, we'll create placeholder entries based on common patterns
            logger.info(f"Gerrit repository discovery for {gerrit_url} (project: {project_name}) not yet implemented")

        except Exception as e:
            logger.warning(f"Failed to discover Gerrit repositories for {gerrit_url}: {e}")

        return repositories

    def _map_github_to_gerrit_path(self, github_name: str) -> Optional[str]:
        """Map GitHub repository name to likely Gerrit path.

        Args:
            github_name: GitHub repository name

        Returns:
            Likely Gerrit path or None if no mapping can be determined
        """
        # Replace hyphens with slashes for common patterns
        # e.g., "it-dep-l2" -> "it/dep/l2"
        if "-" in github_name:
            # Simple heuristic: replace hyphens with slashes
            return github_name.replace("-", "/")

        return None

    def _save_repositories(self, repositories: List[Dict[str, Any]]) -> None:
        """Save repositories to the repositories file.

        Args:
            repositories: List of repository dictionaries
        """
        try:
            repositories_data = {"repositories": repositories}
            self._save_yaml_with_header(repositories_data, self.repositories_file)
            logger.info(f"Saved {len(repositories)} repositories to {self.repositories_file}")

        except Exception as e:
            logger.error(f"Failed to save repositories: {e}")

    def _enhance_servers_with_tailscale_data(self, servers: List[Dict[str, Any]]) -> None:
        """Enhance servers with live Tailscale VPN address data.

        This method comprehensively reconciles server VPN addresses with live Tailscale data.
        It eliminates placeholder 100.64.X.Y addresses and only populates VPN addresses
        from actual Tailscale connectivity.

        Args:
            servers: List of server dictionaries to enhance with VPN addresses
        """
        try:
            from lftools_ng.core.tailscale_parser import TailscaleParser

            parser = TailscaleParser()

            # Get live Tailscale status
            logger.info("Fetching live Tailscale status for VPN address reconciliation...")
            tailscale_status = parser.get_tailscale_status()

            if not tailscale_status:
                logger.warning("No Tailscale data available - clearing placeholder VPN addresses")
                self._clear_placeholder_vpn_addresses(servers)
                return

            # Parse Tailscale peers to get available servers
            tailscale_servers = parser.parse_vpn_servers(tailscale_status)

            if not tailscale_servers:
                logger.warning("No Tailscale servers found - clearing placeholder VPN addresses")
                self._clear_placeholder_vpn_addresses(servers)
                return

            logger.info(f"Found {len(tailscale_servers)} servers in Tailscale network")

            # Create comprehensive mapping from Tailscale data
            vpn_mapping = self._create_comprehensive_vpn_mapping(tailscale_servers)

            # Perform gap analysis and update servers
            self._reconcile_server_vpn_addresses(servers, vpn_mapping, tailscale_servers)

        except ImportError:
            logger.warning("Tailscale parser not available - clearing placeholder VPN addresses")
            self._clear_placeholder_vpn_addresses(servers)
        except Exception as e:
            logger.warning(f"Failed to enhance servers with Tailscale data: {e}")
            logger.warning("Clearing placeholder VPN addresses due to error")
            self._clear_placeholder_vpn_addresses(servers)

    def _clear_placeholder_vpn_addresses(self, servers: List[Dict[str, Any]]) -> None:
        """Clear placeholder 100.64.X.Y VPN addresses from servers.

        Args:
            servers: List of server dictionaries to clean up
        """
        cleared_count = 0
        for server in servers:
            vpn_address = server.get("vpn_address")
            if vpn_address and str(vpn_address).startswith("100.64."):
                logger.info(f"Clearing placeholder VPN address for {server.get('name', 'unknown')}: {vpn_address}")
                server["vpn_address"] = None
                cleared_count += 1

        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} placeholder VPN addresses")

    def _create_comprehensive_vpn_mapping(self, tailscale_servers: List[Any]) -> Dict[str, str]:
        """Create comprehensive mapping from public server names to VPN addresses.

        Args:
            tailscale_servers: List of Server objects from Tailscale

        Returns:
            Dict mapping public server names to VPN addresses
        """
        vpn_mapping: Dict[str, str] = {}

        for ts_server in tailscale_servers:
            hostname = ts_server.name if hasattr(ts_server, 'name') else str(ts_server.get("name", ""))
            vpn_addr = ts_server.vpn_address if hasattr(ts_server, 'vpn_address') else ts_server.get("vpn_address", "")

            if not hostname or not vpn_addr:
                continue

            logger.debug(f"Processing Tailscale server: {hostname} -> {vpn_addr}")

            # Map direct hostname
            vpn_mapping[hostname] = vpn_addr

            # Map public domain equivalents using comprehensive patterns
            public_mappings = self._map_tailscale_hostname_to_public_domains(hostname)
            for public_name in public_mappings:
                vpn_mapping[public_name] = vpn_addr
                logger.debug(f"Mapped {hostname} -> {public_name} -> {vpn_addr}")

        logger.info(f"Created VPN mapping for {len(vpn_mapping)} server name variants")
        return vpn_mapping

    def _map_tailscale_hostname_to_public_domains(self, hostname: str) -> List[str]:
        """Map Tailscale internal hostname to all possible public domain names.

        Args:
            hostname: Internal Tailscale hostname (e.g., "vex-yul-ecomp-jenkins-1")

        Returns:
            List of public domain names this could map to
        """
        hostname_lower = hostname.lower()
        mappings: List[str] = []

        # Create specific mappings based on actual Tailscale output patterns
        # These are derived from the actual tss output provided by the user
        specific_mappings = {
            # ONAP/ECOMP mappings from actual Tailscale output
            "vex-yul-ecomp-jenkins-1": ["jenkins.onap.org"],
            "vex-yul-ecomp-jenkins-2": ["jenkins.onap.org/sandbox"],
            "aws-us-west-2-onap-gerrit-1": ["gerrit.onap.org"],
            "vex-yul-onap-nexus-4": ["nexus3.onap.org"],

            # OpenDaylight mappings
            "vex-yul-odl-jenkins-1": ["jenkins.opendaylight.org"],
            "vex-yul-odl-jenkins-2": ["jenkins.opendaylight.org/sandbox"],
            "aws-eu-west-3-odl-gerrit-1": ["git.opendaylight.org"],
            "aws-us-west-2-odl-gerrit-1": ["git.opendaylight.org"],
            "vex-yul-odl-nexus-1": ["nexus3.opendaylight.org"],
            "vex-yul-odl-nexus-2": ["nexus3.opendaylight.org"],

            # O-RAN-SC mappings
            "vex-sjc-oran-jenkins-prod-1": ["jenkins.o-ran-sc.org"],
            "vex-sjc-oran-jenkins-sandbox-1": ["jenkins.o-ran-sc.org/sandbox"],
            "aws-us-west-2-oran-gerrit-1": ["gerrit.o-ran-sc.org"],
            "vex-sjc-oran-nexus3-1": ["nexus3.o-ran-sc.org"],
            "vex-sjc-oran-nexus2-1": ["nexus3.o-ran-sc.org"],

            # Akraino mappings
            "vex-yul-akraino-jenkins-prod-1": ["jenkins.akraino.org"],
            "vex-yul-akraino-jenkins-sandbox-1": ["jenkins.akraino.org/sandbox"],
            "aws-us-west-2-akraino-gerrit-1": ["gerrit.akraino.org"],
            "vex-yul-akraino-nexus3-1": ["nexus3.akraino.org"],
            "vex-yul-akraino-nexus2-1": ["nexus3.akraino.org"],

            # EdgeX Foundry mappings
            "vex-yul-edgex-jenkins-1": ["jenkins.edgexfoundry.org"],
            "vex-yul-edgex-jenkins-2": ["jenkins.edgexfoundry.org/sandbox"],
            "vex-yul-edgex-nexus-2-1": ["nexus3.edgexfoundry.org"],
            "vex-yul-edgex-nexus-2": ["nexus3.edgexfoundry.org"],

            # FD.io mappings
            "aws-us-west-2-fdio-gerrit-1": ["gerrit.fd.io"],

            # OPNFV mappings
            "aws-us-west-2-opnfv-gerrit-1": ["gerrit.opnfv.org"],
            "gce-opnfv-jenkins-2": ["build.opnfv.org", "build.opnfv.org/sandbox"],
            "vex-yul-opnfv-jenkins-sandbox-1": ["build.opnfv.org/sandbox"],

            # CORD mappings
            "aws-us-west-2-cord-jenkins-1": ["jenkins.opencord.org"],

            # AGL mappings
            "vex-yul-agl-jenkins-1": ["build.automotivelinux.org"],
            "aws-us-west-2-agl-gerrit-1": ["gerrit.automotivelinux.org"],
            "aws-us-west-2-agl-gerrit-2-1": ["gerrit.automotivelinux.org"],

            # Linux Foundation IT mappings
            "aws-us-west-2-lfit-jenkins-1": ["jenkins.linuxfoundation.org"],
            "aws-us-west-2-lfit-jenkins-sandbox-1": ["jenkins.linuxfoundation.org/sandbox"],
            "aws-us-west-2-lfit-gerrit-1": ["gerrit.linuxfoundation.org"],
        }

        # Check for exact match first
        if hostname_lower in specific_mappings:
            mappings.extend(specific_mappings[hostname_lower])
            return mappings

        # Fallback to pattern-based matching for new or unrecognized servers
        pattern_mappings = [
            # ONAP/ECOMP patterns
            {
                "patterns": ["ecomp-jenkins-1", "onap-jenkins-1", "ecomp-jenkins-prod", "onap-jenkins-prod"],
                "domains": ["jenkins.onap.org"]
            },
            {
                "patterns": ["ecomp-jenkins-2", "onap-jenkins-2", "ecomp-jenkins-sandbox", "onap-jenkins-sandbox"],
                "domains": ["jenkins.onap.org/sandbox"]
            },
            {
                "patterns": ["ecomp-gerrit", "onap-gerrit"],
                "domains": ["gerrit.onap.org"]
            },
            {
                "patterns": ["ecomp-nexus", "onap-nexus"],
                "domains": ["nexus3.onap.org"]
            },

            # OpenDaylight patterns
            {
                "patterns": ["odl-jenkins-1", "odl-jenkins-prod"],
                "domains": ["jenkins.opendaylight.org"]
            },
            {
                "patterns": ["odl-jenkins-2", "odl-jenkins-sandbox"],
                "domains": ["jenkins.opendaylight.org/sandbox"]
            },
            {
                "patterns": ["odl-gerrit"],
                "domains": ["git.opendaylight.org"]
            },
            {
                "patterns": ["odl-nexus"],
                "domains": ["nexus3.opendaylight.org"]
            },

            # O-RAN-SC patterns
            {
                "patterns": ["oran-jenkins-prod", "oran-jenkins-1"],
                "domains": ["jenkins.o-ran-sc.org"]
            },
            {
                "patterns": ["oran-jenkins-sandbox", "oran-jenkins-2"],
                "domains": ["jenkins.o-ran-sc.org/sandbox"]
            },
            {
                "patterns": ["oran-gerrit"],
                "domains": ["gerrit.o-ran-sc.org"]
            },
            {
                "patterns": ["oran-nexus"],
                "domains": ["nexus3.o-ran-sc.org"]
            },

            # Akraino patterns
            {
                "patterns": ["akraino-jenkins-prod", "akraino-jenkins-1"],
                "domains": ["jenkins.akraino.org"]
            },
            {
                "patterns": ["akraino-jenkins-sandbox", "akraino-jenkins-2"],
                "domains": ["jenkins.akraino.org/sandbox"]
            },
            {
                "patterns": ["akraino-gerrit"],
                "domains": ["gerrit.akraino.org"]
            },
            {
                "patterns": ["akraino-nexus"],
                "domains": ["nexus3.akraino.org"]
            },

            # EdgeX patterns
            {
                "patterns": ["edgex-jenkins-1", "edgex-jenkins-prod"],
                "domains": ["jenkins.edgexfoundry.org"]
            },
            {
                "patterns": ["edgex-jenkins-2", "edgex-jenkins-sandbox"],
                "domains": ["jenkins.edgexfoundry.org/sandbox"]
            },
            {
                "patterns": ["edgex-nexus"],
                "domains": ["nexus3.edgexfoundry.org"]
            },

            # FD.io patterns
            {
                "patterns": ["fdio-gerrit"],
                "domains": ["gerrit.fd.io"]
            },
            {
                "patterns": ["fdio-jenkins"],
                "domains": ["jenkins.fd.io", "jenkins.fd.io/sandbox"]
            },
            {
                "patterns": ["fdio-nexus"],
                "domains": ["nexus.fd.io"]
            },

            # OPNFV patterns
            {
                "patterns": ["opnfv-jenkins", "opnfv-build"],
                "domains": ["build.opnfv.org", "build.opnfv.org/sandbox"]
            },
            {
                "patterns": ["opnfv-gerrit"],
                "domains": ["gerrit.opnfv.org"]
            },
            {
                "patterns": ["opnfv-nexus"],
                "domains": ["nexus3.opnfv.org"]
            },

            # CORD patterns
            {
                "patterns": ["cord-jenkins"],
                "domains": ["jenkins.opencord.org", "jenkins.opencord.org/sandbox"]
            },
            {
                "patterns": ["cord-gerrit"],
                "domains": ["gerrit.opencord.org"]
            },
            {
                "patterns": ["cord-nexus"],
                "domains": ["nexus3.opencord.org"]
            },

            # AGL patterns
            {
                "patterns": ["agl-jenkins", "agl-build"],
                "domains": ["build.automotivelinux.org", "build.automotivelinux.org/sandbox"]
            },
            {
                "patterns": ["agl-gerrit"],
                "domains": ["gerrit.automotivelinux.org"]
            },
            {
                "patterns": ["agl-nexus"],
                "domains": ["nexus3.automotivelinux.org"]
            },

            # Linux Foundation IT patterns
            {
                "patterns": ["lfit-jenkins", "linuxfoundation-jenkins"],
                "domains": ["jenkins.linuxfoundation.org", "jenkins.linuxfoundation.org/sandbox"]
            },
            {
                "patterns": ["lfit-gerrit", "linuxfoundation-gerrit"],
                "domains": ["gerrit.linuxfoundation.org"]
            },
            {
                "patterns": ["lfit-nexus", "linuxfoundation-nexus"],
                "domains": ["nexus3.linuxfoundation.org"]
            },
        ]

        # Apply pattern-based mapping rules
        for rule in pattern_mappings:
            for pattern in rule["patterns"]:
                if pattern in hostname_lower:
                    mappings.extend(rule["domains"])
                    break

        # Remove duplicates while preserving order
        return list(dict.fromkeys(mappings))

    def _reconcile_server_vpn_addresses(self, servers: List[Dict[str, Any]], vpn_mapping: Dict[str, str], tailscale_servers: List[Any]) -> None:
        """Reconcile server VPN addresses with Tailscale data and perform gap analysis.

        Args:
            servers: List of server dictionaries to update
            vpn_mapping: Mapping from server names to VPN addresses
            tailscale_servers: List of Tailscale server objects for gap analysis
        """
        updated_count = 0
        cleared_count = 0
        gap_servers: List[str] = []

        # Update servers with actual Tailscale VPN addresses
        for server in servers:
            server_name = server.get("name", "")
            current_vpn = server.get("vpn_address")

            if server_name in vpn_mapping:
                new_vpn = vpn_mapping[server_name]
                if current_vpn != new_vpn:
                    logger.info(f"Updated VPN address for {server_name}: {current_vpn} -> {new_vpn}")
                    server["vpn_address"] = new_vpn
                    updated_count += 1
            else:
                # Server not found in Tailscale - clear placeholder VPN addresses
                if current_vpn and (str(current_vpn).startswith("100.64.") or not str(current_vpn).startswith("100.")):
                    logger.info(f"Clearing VPN address for {server_name} (not in Tailscale): {current_vpn}")
                    server["vpn_address"] = None
                    cleared_count += 1
                    gap_servers.append(server_name)

        # Perform gap analysis - identify Tailscale servers not in our database
        tailscale_hostnames = {ts.name if hasattr(ts, 'name') else str(ts.get("name", "")) for ts in tailscale_servers}
        mapped_hostnames = set(vpn_mapping.keys())

        # Find Tailscale servers that don't map to any server in our database
        unmapped_tailscale = tailscale_hostnames - {k for k in vpn_mapping.keys() if k in tailscale_hostnames}

        # Log reconciliation results
        logger.info(f"VPN address reconciliation complete:")
        logger.info(f"  - Updated {updated_count} servers with live Tailscale VPN addresses")
        logger.info(f"  - Cleared {cleared_count} placeholder/invalid VPN addresses")
        logger.info(f"  - {len(gap_servers)} servers not found in Tailscale network")
        logger.info(f"  - {len(unmapped_tailscale)} Tailscale servers not mapped to database entries")

        if gap_servers:
            logger.warning(f"Servers missing from Tailscale network: {', '.join(gap_servers[:10])}")
            if len(gap_servers) > 10:
                logger.warning(f"... and {len(gap_servers) - 10} more")

        if unmapped_tailscale:
            logger.info(f"Unmapped Tailscale servers: {', '.join(list(unmapped_tailscale)[:10])}")
            if len(unmapped_tailscale) > 10:
                logger.info(f"... and {len(unmapped_tailscale) - 10} more")

    # Keep the original _map_internal_hostname_to_public method for backward compatibility
    # but mark it as deprecated in favor of the new comprehensive mapping
    def _map_internal_hostname_to_public(self, internal_hostname: str) -> Optional[str]:
        """Map internal Tailscale hostname to public domain name.

        Args:
            internal_hostname: Internal hostname like "vex-yul-onap-gerrit-1"

        Returns:
            Public domain name like "gerrit.onap.org" or None if no mapping found
        """
        hostname_lower = internal_hostname.lower()

        # Define mapping patterns from internal names to public domains
        mapping_patterns = [
            # ONAP mappings (including ECOMP legacy names) - more specific patterns first
            (r".*onap.*gerrit.*", "gerrit.onap.org"),
            (r".*onap.*nexus.*", "nexus3.onap.org"),
            (r".*onap.*jenkins.*(sandbox|2).*", "jenkins.onap.org/sandbox"),
            (r".*onap.*jenkins.*(prod|1).*", "jenkins.onap.org"),
            # ECOMP legacy mappings to ONAP - more specific patterns first
            (r".*ecomp.*gerrit.*", "gerrit.onap.org"),
            (r".*ecomp.*nexus.*", "nexus3.onap.org"),
            (r".*ecomp.*jenkins.*(sandbox|2).*", "jenkins.onap.org/sandbox"),
            (r".*ecomp.*jenkins.*(prod|1).*", "jenkins.onap.org"),

            # OpenDaylight mappings - more specific patterns first
            (r".*odl.*gerrit.*", "git.opendaylight.org"),
            (r".*odl.*nexus.*", "nexus3.opendaylight.org"),
            (r".*odl.*jenkins.*(sandbox|2).*", "jenkins.opendaylight.org/sandbox"),
            (r".*odl.*jenkins.*(prod|1).*", "jenkins.opendaylight.org"),

            # O-RAN-SC mappings (more specific patterns first)
            (r".*oran.*gerrit.*", "gerrit.o-ran-sc.org"),
            (r".*oran.*nexus.*", "nexus3.o-ran-sc.org"),
            (r".*oran.*jenkins.*(sandbox|2).*", "jenkins.o-ran-sc.org/sandbox"),
            (r".*oran.*jenkins.*(prod|1).*", "jenkins.o-ran-sc.org"),

            # Akraino mappings - more specific patterns first
            (r".*akraino.*gerrit.*", "gerrit.akraino.org"),
            (r".*akraino.*nexus.*", "nexus3.akraino.org"),
            (r".*akraino.*jenkins.*(sandbox|2).*", "jenkins.akraino.org/sandbox"),
            (r".*akraino.*jenkins.*(prod|1).*", "jenkins.akraino.org"),

            # FD.io mappings - more specific patterns first
            (r".*fdio.*gerrit.*", "gerrit.fd.io"),
            (r".*fdio.*nexus.*", "nexus.fd.io"),
            (r".*fdio.*jenkins.*(sandbox|2).*", "jenkins.fd.io/sandbox"),
            (r".*fdio.*jenkins.*(prod|1).*", "jenkins.fd.io"),

            # OPNFV mappings - more specific patterns first
            (r".*opnfv.*gerrit.*", "gerrit.opnfv.org"),
            (r".*opnfv.*nexus.*", "nexus3.opnfv.org"),
            (r".*opnfv.*jenkins.*(sandbox|2).*", "build.opnfv.org/sandbox"),
            (r".*opnfv.*jenkins.*(prod|1).*", "build.opnfv.org"),

            # EdgeX mappings - more specific patterns first
            (r".*edgex.*gerrit.*", "gerrit.edgexfoundry.org"),
            (r".*edgex.*nexus.*", "nexus3.edgexfoundry.org"),
            (r".*edgex.*jenkins.*(sandbox|2).*", "jenkins.edgexfoundry.org/sandbox"),
            (r".*edgex.*jenkins.*(prod|1).*", "jenkins.edgexfoundry.org"),

            # AGL mappings
            (r".*agl.*gerrit.*", "gerrit.automotivelinux.org"),
            (r".*agl.*nexus.*", "nexus3.automotivelinux.org"),
            (r".*agl.*jenkins.*", "build.automotivelinux.org"),

            # Additional project mappings based on your Tailscale output
            (r".*cord.*jenkins.*", "jenkins.opencord.org"),
            (r".*cord.*gerrit.*", "gerrit.opencord.org"),

            # Linux Foundation Jenkins
            (r".*lfit.*jenkins.*", "jenkins.linuxfoundation.org"),
            (r".*lfit.*gerrit.*", "gerrit.linuxfoundation.org"),
        ]

        import re
        for pattern, public_name in mapping_patterns:
            if re.match(pattern, hostname_lower):
                return public_name

        return None
