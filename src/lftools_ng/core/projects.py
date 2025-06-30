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
FDIO_SERVER_URL = "https://jenkins.fd.io"
LF_SERVER_URL = "https://jenkins.linuxfoundation.org"
LF_NEXUS_IQ_URL = "https://nexus-iq.wl.linuxfoundation.org"
YOCTO_AUTOBUILDER_URL = "https://autobuilder.yoctoproject.org"

# Server/project name constants
FDIO_KEY = "fd.io"
FDIO_ALT_KEY = "fdio"


class ProjectManager:
    """Manages projects and server mappings."""

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
        """Auto-initialize configuration from resources directory if config files don't exist.

        Note: Only projects.yaml and repositories.yaml are auto-initialized.
        servers.yaml is intentionally NOT auto-initialized as it contains sensitive
        VPN addresses and must be built locally via Tailscale integration.
        """
        try:
            # Find the resources directory relative to this file
            current_file = pathlib.Path(__file__)
            # Navigate up from src/lftools_ng/core/projects.py to project root
            project_root = current_file.parent.parent.parent.parent
            resources_dir = project_root / "resources"

            if not resources_dir.exists():
                logger.warning(f"Resources directory not found: {resources_dir}")
                return

            # Only copy safe files that don't contain sensitive information
            files_to_copy = [
                ("projects.yaml", self.projects_file),
                ("repositories.yaml", self.repositories_file)
                # NOTE: servers.yaml is intentionally excluded - it must be built locally
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
                logger.info("Note: servers.yaml must be built locally via 'lftools-ng projects rebuild-servers'")

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
        """List all registered servers.

        Returns:
            List of server dictionaries
        """
        # Check if servers database exists, prompt for initialization if needed
        if not self._ensure_servers_database_exists():
            # User declined to initialize, return empty list
            return []

        try:
            # Load projects first (needed for server building/mapping)
            projects = self.list_projects()

            servers = []

            # Try to load existing servers from YAML file
            if self.servers_file.exists():
                with open(self.servers_file) as f:
                    data = yaml.safe_load(f)
                    if data is not None:
                        # Handle both dictionary and list formats
                        if isinstance(data, dict):
                            servers = data.get("servers", [])
                        elif isinstance(data, list):
                            servers = data

                        if not isinstance(servers, list):
                            servers = []

            # If no servers found in YAML, build them from projects
            if not servers:
                logger.info("No servers found in servers.yaml, building servers from projects...")
                servers = self._build_servers_from_projects(projects)
            else:
                # Enhance existing servers with comprehensive data integration
                self._integrate_server_data_sources(servers, projects)

                # Map projects to servers and calculate project counts
                self._map_projects_to_servers_in_place(servers, projects)

                # Enhance servers with missing URLs
                self._enhance_servers_with_inferred_urls(servers)

            return servers
        except Exception as e:
            logger.error(f"Failed to load servers: {e}")
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
        """Rebuild projects database from source with enhancements.

        This method now:
        1. Uses the base projects.yaml as a foundation
        2. Adds fall-through projects from PROJECT_ALIASES
        3. Ensures all projects have accurate Primary SCM platform and URL information
        4. Merges aliases from multiple sources for comprehensive matching

        Args:
            source_url: URL to fetch project configuration from (optional)
            force: Force rebuild even if database exists

        Returns:
            Dictionary with rebuild statistics
        """
        if self.projects_file.exists() and not force:
            raise ValueError(
                "Projects database already exists. Use --force to rebuild."
            )

        try:
            # Generate enhanced projects database
            logger.info("Generating enhanced projects database with fall-through projects and SCM mapping...")
            enhanced_data = self._generate_enhanced_projects_database()

            # If a source URL is provided, try to merge it with our enhanced data
            if source_url:
                logger.info(f"Merging with external source: {source_url}")
                # For now, we prioritize our enhanced data and just log the external source
                # Future enhancement could merge the two sources intelligently
                logger.warning("External source URLs are currently logged but not merged. Enhanced local data takes precedence.")

            # Save the enhanced database
            self._save_yaml_with_header(enhanced_data, self.projects_file)

            projects_count = len(enhanced_data.get("projects", []))
            logger.info(f"Successfully built enhanced projects database with {projects_count} projects")

            return {
                "projects_count": projects_count,
                "servers_count": 0  # Will be built separately by servers rebuild
            }

        except Exception as e:
            logger.error(f"Failed to rebuild projects database: {e}")
            raise

    def rebuild_servers_database(
        self,
        source_url: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, int]:
        """Rebuild servers database from live data sources.

        This method builds the servers database from multiple sources:
        1. Projects data (for basic server enumeration)
        2. Tailscale VPN network (for VPN addresses and infrastructure discovery)
        3. Linux Foundation inventory (for validation)

        Note: This method requires VPN access to build the complete database.
        VPN addresses and internal server information are only available to
        users with active Tailscale VPN connectivity.

        Args:
            source_url: Optional URL to fetch server configuration from (deprecated)
            force: Force rebuild even if database exists

        Returns:
            Dictionary with rebuild statistics
        """
        if self.servers_file.exists() and not force:
            raise ValueError(
                "Servers database already exists. Use --force to rebuild."
            )

        # Build servers database from live data sources
        logger.info("Building servers database from live Linux Foundation infrastructure data...")
        logger.info("Note: This requires active Tailscale VPN connection for complete server enumeration")

        try:
            # Build from live projects data
            projects = self.list_projects()
            servers = self._build_servers_from_projects(projects)

            # Enhance with Tailscale VPN data
            self._enhance_servers_with_tailscale_data(servers)

            # Apply additional server intelligence
            self._apply_server_naming_conventions(servers)

            # Save the rebuilt database
            servers_data = {"servers": servers}
            self._save_yaml_with_header(servers_data, self.servers_file)

            logger.info(f"Successfully built servers database with {len(servers)} servers")

            return {
                "servers_count": len(servers)
            }

        except Exception as e:
            logger.error(f"Failed to build servers database: {e}")
            raise

    def _build_servers_from_projects(self, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build servers list from projects data.

        Args:
            projects: List of project dictionaries

        Returns:
            List of server dictionaries
        """
        servers = []

        # Extract unique servers from projects
        server_map = {}

        for project in projects:
            # Extract server URLs from various project fields
            # Support both legacy and new field names for servers
            server_urls = []

            # Check for Jenkins servers
            if project.get("jenkins_production"):
                server_urls.append((project["jenkins_production"], "jenkins", True))
            if project.get("jenkins_sandbox"):
                server_urls.append((project["jenkins_sandbox"], "jenkins", False))

            # Legacy support for projects that may have this field
            if project.get("jenkins_server"):
                server_urls.append((f"https://{project['jenkins_server']}", "jenkins", True))

            # Future support for other server types
            if project.get("gerrit_url"):
                server_urls.append((project["gerrit_url"], "gerrit", True))
            if project.get("nexus_url"):
                server_urls.append((project["nexus_url"], "nexus", True))
            if project.get("nexus3_url"):
                server_urls.append((project["nexus3_url"], "nexus", True))

            for server_url, server_type, is_production in server_urls:
                if not server_url:
                    continue

                # Extract server name from URL
                from urllib.parse import urlparse
                parsed = urlparse(server_url)
                server_name = parsed.netloc.replace(":", "_")  # Handle port numbers

                # Determine location and properties based on server URL patterns
                location = "unknown"
                github_mirror_org = None

                # Map known servers to locations and properties
                if "onap" in server_url:
                    location = "vexxhost"
                    if "sandbox" not in server_url:
                        github_mirror_org = "onap"
                elif "opendaylight" in server_url:
                    location = "rackspace"
                    github_mirror_org = "opendaylight"
                elif "fd.io" in server_url:
                    location = "rackspace"
                    github_mirror_org = "FDio"
                elif "lfnetworking" in server_url:
                    location = "aws"

                if server_name not in server_map:
                    server_map[server_name] = {
                        "name": server_name,
                        "url": server_url,
                        "type": server_type,
                        "vpn_address": "",  # Will be filled by Tailscale integration
                        "location": location,
                        "github_mirror_org": github_mirror_org,
                        "is_production": is_production,
                        "version": "unknown",
                        "projects": []
                    }

                # Add project to server
                project_name = project.get("name", "unknown")
                if project_name not in server_map[server_name]["projects"]:
                    server_map[server_name]["projects"].append(project_name)

        servers = list(server_map.values())
        logger.info(f"Built {len(servers)} servers from {len(projects)} projects")

        return servers

    def _ensure_servers_database_exists(self) -> bool:
        """Ensure servers database exists, prompt to build if missing.

        The servers database contains sensitive VPN addresses and network topology
        information that cannot be bundled with the package. It must be built locally
        using live data from Tailscale VPN network.

        Returns:
            True if database exists or was created, False if user declined
        """
        if self.servers_file.exists():
            return True

        # Inform user about VPN requirement
        logger.warning("Servers database not found!")
        logger.info("The servers database contains VPN addresses and internal network topology")
        logger.info("that must be built locally from your Tailscale VPN connection.")
        logger.info("This ensures sensitive infrastructure data is not bundled with the package.")

        # Prompt user to build database
        try:
            import typer
            message = (
                "Build servers database from live Tailscale VPN data? "
                "(requires active VPN connection)"
            )
            if typer.confirm(message):
                logger.info("Building servers database from Tailscale VPN network...")
                self.rebuild_servers_database(force=True)
                return True
            else:
                logger.warning("User declined to build servers database")
                logger.info("Server-related commands will have limited functionality")
                return False
        except ImportError:
            # If typer not available, try to build automatically
            logger.info("Servers database not found. Building from Tailscale VPN network...")
            logger.info("Note: This requires an active Tailscale VPN connection")
            try:
                self.rebuild_servers_database(force=True)
                return True
            except Exception as e:
                logger.error(f"Auto-build failed: {e}")
                logger.error("Please ensure Tailscale VPN is connected and try again")
                return False
        except Exception as e:
            logger.error(f"Failed to build servers database: {e}")
            return False

    def _save_yaml_with_header(self, data: Dict[str, Any], file_path: pathlib.Path) -> None:
        """Save data as YAML with a header comment.

        Args:
            data: Data to save
            file_path: Path to save to
        """
        header = f"""# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: {datetime.now().year} The Linux Foundation
#
# This file was automatically generated by lftools-ng on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# DO NOT EDIT MANUALLY - Use 'lftools-ng projects rebuild-servers --force' to regenerate

"""

        with open(file_path, 'w') as f:
            f.write(header)
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Saved {file_path}")

    def _integrate_server_data_sources(self, servers: List[Dict[str, Any]], projects: List[Dict[str, Any]]) -> None:
        """Integrate data from various sources into server records.

        This method enhances server records with data from:
        1. Tailscale VPN network (for VPN addresses and infrastructure discovery)
        2. Cross-references with projects data to validate mappings
        3. Applies naming conventions and server type logic

        Args:
            servers: List of server dictionaries to enhance
            projects: List of project dictionaries for reference
        """
        try:
            from lftools_ng.core.tailscale_parser import TailscaleParser

            # Initialize Tailscale parser
            tailscale_parser = TailscaleParser()

            # Get VPN server data
            vpn_servers = tailscale_parser.get_available_servers()

            if not vpn_servers:
                logger.warning("No Tailscale VPN servers found. VPN addresses will remain empty.")
                return

            logger.info(f"Found {len(vpn_servers)} servers in Tailscale VPN network")

            # Create a mapping of server names to VPN data (address and location)
            vpn_mapping = {}
            for vpn_server in vpn_servers:
                vpn_name = vpn_server.get("name", "")
                vpn_address = vpn_server.get("vpn_address", "")
                if vpn_name and vpn_address:
                    vpn_mapping[vpn_name] = {
                        "vpn_address": vpn_address,
                        "location": vpn_server.get("status", "").split()[-1] if vpn_server.get("status") else "unknown"
                    }

            # Enhance existing servers with VPN data
            enhanced_count = 0
            for server in servers:
                server_name = server.get("name", "")

                # Try direct name match first
                if server_name in vpn_mapping:
                    vpn_data = vpn_mapping[server_name]
                    server["vpn_address"] = vpn_data["vpn_address"]
                    enhanced_count += 1
                    continue

                # Try fuzzy matching for servers that might have different naming
                # Extract base server name from URL if needed
                server_url = server.get("url", "")
                if server_url:
                    from urllib.parse import urlparse
                    parsed = urlparse(server_url)
                    url_hostname = parsed.netloc

                    # Check if URL hostname matches any VPN server
                    for vpn_name, vpn_data in vpn_mapping.items():
                        if self._fuzzy_match_server_names(url_hostname, vpn_name):
                            server["vpn_address"] = vpn_data["vpn_address"]
                            enhanced_count += 1
                            break

            logger.info(f"Enhanced {enhanced_count} servers with VPN addresses from Tailscale")

        except ImportError:
            logger.warning("Tailscale integration not available")
        except Exception as e:
            logger.warning(f"Failed to integrate Tailscale data: {e}")

    def _fuzzy_match_server_names(self, url_hostname: str, vpn_hostname: str) -> bool:
        """Perform fuzzy matching between URL hostname and VPN hostname.

        Args:
            url_hostname: Hostname from server URL
            vpn_hostname: Hostname from Tailscale VPN

        Returns:
            True if hostnames likely refer to the same server
        """
        # Simple fuzzy matching logic
        # Remove common prefixes/suffixes and compare
        url_clean = url_hostname.lower().replace("jenkins.", "").replace("gerrit.", "").replace("nexus.", "")
        vpn_clean = vpn_hostname.lower()

        # Check if the project name appears in both
        url_parts = url_clean.split(".")
        vpn_parts = vpn_clean.split("-")

        # Look for common project indicators
        common_projects = ["onap", "opendaylight", "odl", "fdio", "fd.io", "akraino", "edgex", "oran", "o-ran-sc"]

        url_project = None
        vpn_project = None

        for project in common_projects:
            if project in url_clean:
                url_project = project
            for part in vpn_parts:
                if project in part:
                    vpn_project = project

        return url_project == vpn_project and url_project is not None

    def _map_projects_to_servers_in_place(self, servers: List[Dict[str, Any]], projects: List[Dict[str, Any]]) -> None:
        """Map projects to servers and update server project counts in-place.

        Args:
            servers: List of server dictionaries to update
            projects: List of project dictionaries
        """
        # Create mapping of server URLs to projects
        server_projects = {}

        for project in projects:
            # Extract server URLs from various project fields (same logic as _build_servers_from_projects)
            server_urls = []

            # Check for Jenkins servers
            if project.get("jenkins_production"):
                server_urls.append(project["jenkins_production"])
            if project.get("jenkins_sandbox"):
                server_urls.append(project["jenkins_sandbox"])

            # Legacy support
            if project.get("jenkins_server"):
                server_urls.append(f"https://{project['jenkins_server']}")

            # Future support for other server types
            if project.get("gerrit_url"):
                server_urls.append(project["gerrit_url"])
            if project.get("nexus_url"):
                server_urls.append(project["nexus_url"])
            if project.get("nexus3_url"):
                server_urls.append(project["nexus3_url"])

            for server_url in server_urls:
                if not server_url:
                    continue

                # Extract server name from URL
                from urllib.parse import urlparse
                parsed = urlparse(server_url)
                server_name = parsed.netloc.replace(":", "_")  # Handle port numbers

                if server_name not in server_projects:
                    server_projects[server_name] = []
                project_name = project.get("name", "unknown")
                if project_name not in server_projects[server_name]:
                    server_projects[server_name].append(project_name)

        # Update servers with project information, preserving existing assignments
        for server in servers:
            server_name = server.get("name", "")
            if server_name in server_projects:
                # Update with projects found in projects.yaml
                server["projects"] = server_projects[server_name]
                server["project_count"] = len(server_projects[server_name])
            else:
                # Preserve existing project assignments for VPN-discovered servers
                existing_projects = server.get("projects", [])
                if not existing_projects:
                    # Only set to empty if there were no existing projects
                    server["projects"] = []
                    server["project_count"] = 0
                else:
                    # Keep existing projects and update count
                    server["project_count"] = len(existing_projects)

    def _enhance_servers_with_inferred_urls(self, servers: List[Dict[str, Any]]) -> None:
        """Enhance servers with inferred URLs if missing.

        Args:
            servers: List of server dictionaries to enhance
        """
        for server in servers:
            if not server.get("url") and server.get("name"):
                # Infer HTTPS URL from server name
                server_name = server["name"]
                if not server_name.startswith(("http://", "https://")):
                    server["url"] = f"https://{server_name}"

    def _enhance_servers_with_tailscale_data(self, servers: List[Dict[str, Any]]) -> None:
        """Enhance server records with Tailscale VPN data.

        This method attempts to connect to the Tailscale VPN network to discover
        infrastructure servers and populate VPN addresses. It requires an active
        Tailscale connection.

        Args:
            servers: List of server dictionaries to enhance
        """
        try:
            from lftools_ng.core.tailscale_parser import TailscaleParser

            tailscale = TailscaleParser()

            # Test if Tailscale is available and logged in
            status_data = tailscale.get_tailscale_status()
            if not status_data:
                logger.warning("Tailscale not available or not logged in. VPN data will be incomplete.")
                return

            # Parse VPN servers from Tailscale
            vpn_servers = tailscale.parse_vpn_servers(status_data)

            if not vpn_servers:
                logger.warning("No infrastructure servers found in Tailscale VPN network")
                return

            logger.info(f"Found {len(vpn_servers)} infrastructure servers in Tailscale VPN")

            # Create lookup maps
            vpn_by_hostname = {server.name: server for server in vpn_servers}

            # Enhance existing servers with VPN data
            for server_dict in servers:
                server_name = server_dict.get("name", "")
                server_url = server_dict.get("url", "")

                # Try direct hostname match
                if server_name in vpn_by_hostname:
                    vpn_server = vpn_by_hostname[server_name]
                    server_dict["vpn_address"] = vpn_server.vpn_address
                    # Transfer location and hosting information if unknown
                    if server_dict.get("location") == "unknown":
                        server_dict["location"] = vpn_server.location.value
                    continue

                # Try URL-based matching
                if server_url:
                    from urllib.parse import urlparse
                    parsed = urlparse(server_url)
                    url_hostname = parsed.netloc

                    # Look for matches in VPN hostnames
                    for vpn_hostname, vpn_server in vpn_by_hostname.items():
                        if self._match_server_hostnames(url_hostname, vpn_hostname):
                            server_dict["vpn_address"] = vpn_server.vpn_address
                            # Transfer location and hosting information if unknown
                            if server_dict.get("location") == "unknown":
                                server_dict["location"] = vpn_server.location.value
                            break

            # Add any VPN-only servers that weren't found in projects
            existing_names = {s.get("name", "") for s in servers}
            for vpn_server in vpn_servers:
                if vpn_server.name not in existing_names:
                    # Add new server discovered via VPN
                    new_server = {
                        "name": vpn_server.name,
                        "url": vpn_server.url or "",
                        "type": vpn_server.server_type.value,
                        "vpn_address": vpn_server.vpn_address,
                        "location": vpn_server.location.value,
                        "is_production": vpn_server.is_production,
                        "projects": vpn_server.projects,
                        "version": "unknown"
                    }
                    servers.append(new_server)

            logger.info(f"Enhanced servers with Tailscale VPN data. Total servers: {len(servers)}")

        except ImportError:
            logger.warning("Tailscale parser not available")
        except Exception as e:
            logger.error(f"Failed to enhance servers with Tailscale data: {e}")

    def _match_server_hostnames(self, url_hostname: str, vpn_hostname: str) -> bool:
        """Match URL hostname to VPN hostname using project-based logic.

        Args:
            url_hostname: Hostname from server URL (e.g., jenkins.onap.org)
            vpn_hostname: Hostname from VPN (e.g., vex-yul-onap-jenkins-1)

        Returns:
            True if hostnames likely refer to the same logical server
        """
        # Extract project name from both hostnames
        url_project = self._extract_project_from_url_hostname(url_hostname)
        vpn_project = self._extract_project_from_vpn_hostname(vpn_hostname)

        if not url_project or not vpn_project:
            return False

        # Check if both refer to the same project
        return url_project.lower() == vpn_project.lower()

    def _extract_project_from_url_hostname(self, hostname: str) -> Optional[str]:
        """Extract project name from public URL hostname.

        Args:
            hostname: Public hostname (e.g., jenkins.onap.org)

        Returns:
            Project name or None
        """
        hostname_lower = hostname.lower()

        # Known project domains
        project_domains = {
            "onap.org": "onap",
            "opendaylight.org": "opendaylight",
            "o-ran-sc.org": "o-ran-sc",
            "fd.io": "fdio",
            "akraino.org": "akraino",
            "edgexfoundry.org": "edgex",
            "automotivelinux.org": "agl",
            "opnfv.org": "opnfv"
        }

        for domain, project in project_domains.items():
            if domain in hostname_lower:
                return project

        return None

    def _extract_project_from_vpn_hostname(self, hostname: str) -> Optional[str]:
        """Extract project name from VPN hostname.

        Args:
            hostname: VPN hostname (e.g., vex-yul-onap-jenkins-1)

        Returns:
            Project name or None
        """
        hostname_lower = hostname.lower()

        # Known project patterns in VPN hostnames
        project_patterns = [
            "onap", "opendaylight", "odl", "o-ran-sc", "oran",
            "fdio", "fd-io", "akraino", "edgex", "agl", "opnfv"
        ]

        parts = hostname_lower.split("-")
        for part in parts:
            if part in project_patterns:
                # Normalize some project names
                if part in ["odl"]:
                    return "opendaylight"
                elif part in ["oran", "o-ran-sc"]:
                    return "o-ran-sc"
                elif part in ["fd-io"]:
                    return "fdio"
                else:
                    return part

        return None

    def _apply_server_naming_conventions(self, servers: List[Dict[str, Any]]) -> None:
        """Apply Linux Foundation server naming conventions and intelligence.

        This method applies the server enumeration logic described in the requirements:
        - Jenkins production vs sandbox determination
        - Nexus version mapping (2 vs 3)
        - Server type classification

        Args:
            servers: List of server dictionaries to enhance
        """
        for server in servers:
            server_name = server.get("name", "")
            server_type = server.get("type", "")

            # Apply Jenkins production/sandbox logic
            if server_type == "jenkins":
                server["is_production"] = self._determine_jenkins_production_status_from_name(server_name)

            # Apply Nexus version logic
            elif server_type in ["nexus", "nexus3"]:
                server["type"] = self._determine_nexus_version_from_name(server_name)

            # Enhance with additional metadata
            self._add_server_metadata(server)

    def _determine_jenkins_production_status_from_name(self, server_name: str) -> bool:
        """Determine if Jenkins server is production or sandbox based on name.

        Uses the logic described in requirements:
        - Explicit prod/production/sandbox indicators
        - Number hierarchy (lower = production, higher = sandbox)

        Args:
            server_name: Server name/hostname

        Returns:
            True if production, False if sandbox
        """
        name_lower = server_name.lower()

        # Explicit indicators
        if any(indicator in name_lower for indicator in ["prod", "production"]):
            return True
        if "sandbox" in name_lower:
            return False

        # Number-based hierarchy
        import re
        number_match = re.search(r'jenkins-?(\d+)', name_lower)
        if number_match:
            instance_num = int(number_match.group(1))
            return instance_num <= 2  # 1,2 = production, 3+ = sandbox

        # Default to production
        return True

    def _determine_nexus_version_from_name(self, server_name: str) -> str:
        """Determine Nexus version (2 or 3) based on server name and instance number.

        Uses the logic described in requirements:
        - Single instance = assume Nexus 3 (modern)
        - Multiple instances = lower number is Nexus 2, higher is Nexus 3

        Args:
            server_name: Server name/hostname

        Returns:
            "nexus" for Nexus 2, "nexus3" for Nexus 3
        """
        name_lower = server_name.lower()

        # If explicitly named nexus3, return that
        if "nexus3" in name_lower:
            return "nexus3"

        # Extract instance number
        import re
        number_match = re.search(r'nexus-?(\d+)', name_lower)

        if number_match:
            instance_num = int(number_match.group(1))
            # Lower numbers (1,2) typically Nexus 2, higher (3,4+) typically Nexus 3
            if instance_num <= 2:
                return "nexus"  # Nexus 2
            else:
                return "nexus3"  # Nexus 3
        else:
            # Single instance, assume modern Nexus 3
            return "nexus3"

    def _add_server_metadata(self, server: Dict[str, Any]) -> None:
        """Add additional metadata to server record.

        Args:
            server: Server dictionary to enhance
        """
        server_name = server.get("name", "")

        # Add hosting provider information
        if server_name.startswith("vex-"):
            server["hosting_provider"] = "VEXXHOST"
        elif server_name.startswith("aws-"):
            server["hosting_provider"] = "AWS"
        elif server_name.startswith("gce-"):
            server["hosting_provider"] = "GCE"
        elif "korg" in server_name.lower():
            server["hosting_provider"] = "KERNEL.ORG"
        else:
            server["hosting_provider"] = "unknown"

        # Set default values if missing
        if "version" not in server:
            server["version"] = "unknown"
        if "projects" not in server:
            server["projects"] = []
        if "vpn_address" not in server:
            server["vpn_address"] = ""

    def _generate_enhanced_projects_database(self) -> Dict[str, Any]:
        """Generate an enhanced projects database that includes fall-through projects.

        This method:
        1. Takes the base projects from resources/projects.yaml
        2. Adds fall-through projects from PROJECT_ALIASES that aren't already included
        3. Ensures all projects have proper SCM platform and URL information
        4. Updates aliases to include all known variations

        Returns:
            Enhanced projects data structure ready to be saved
        """
        from lftools_ng.core.models import PROJECT_ALIASES

        # Start with base projects from resources
        package_root = pathlib.Path(__file__).parent.parent.parent.parent
        local_projects_file = package_root / "resources" / "projects.yaml"

        base_projects = []
        if local_projects_file.exists():
            try:
                with open(local_projects_file) as f:
                    data = yaml.safe_load(f)
                    base_projects = data.get("projects", [])
            except Exception as e:
                logger.warning(f"Failed to load base projects: {e}")

        # Create a set of existing project names (case-insensitive)
        existing_projects = set()
        for project in base_projects:
            name = project.get("name", "").lower()
            existing_projects.add(name)
            # Also add aliases to avoid duplicates
            for alias in project.get("aliases", []):
                existing_projects.add(alias.lower())

        # Process existing projects to enhance them with SCM info from PROJECT_ALIASES
        enhanced_projects = []
        for project in base_projects:
            enhanced_project = dict(project)  # Copy existing project data

            # Try to enhance with PROJECT_ALIASES data
            project_name = project.get("name", "").lower()
            project_enhanced = False

            for alias_key, alias_data in PROJECT_ALIASES.items():
                # Check if this project matches any pattern in PROJECT_ALIASES
                if (project_name == alias_data.get("primary_name", "").lower() or
                    project_name in [alias.lower() for alias in alias_data.get("aliases", [])] or
                    any(project_name == pattern.lower() for pattern in alias_data.get("name_patterns", []))):

                    # Enhance with SCM information if not already present
                    if not enhanced_project.get("primary_scm_platform"):
                        enhanced_project["primary_scm_platform"] = alias_data.get("primary_scm_platform", "Unknown")
                    if not enhanced_project.get("primary_scm_url"):
                        enhanced_project["primary_scm_url"] = alias_data.get("primary_scm_url", "")

                    # Enhance aliases - merge existing with PROJECT_ALIASES
                    existing_aliases = set(enhanced_project.get("aliases", []))
                    alias_aliases = set(alias_data.get("aliases", []))
                    merged_aliases = list(existing_aliases.union(alias_aliases))
                    enhanced_project["aliases"] = merged_aliases

                    project_enhanced = True
                    break

            # If we couldn't enhance from PROJECT_ALIASES, try to infer SCM from existing data
            if not project_enhanced:
                if not enhanced_project.get("primary_scm_platform"):
                    if enhanced_project.get("gerrit_url"):
                        enhanced_project["primary_scm_platform"] = "Gerrit"
                        enhanced_project["primary_scm_url"] = enhanced_project["gerrit_url"]
                    elif enhanced_project.get("github_mirror_org"):
                        # For GitHub, we need to be careful - it might be a mirror
                        # If there's also a gerrit_url, then Gerrit is primary
                        if enhanced_project.get("gerrit_url"):
                            enhanced_project["primary_scm_platform"] = "Gerrit"
                            enhanced_project["primary_scm_url"] = enhanced_project["gerrit_url"]
                        else:
                            enhanced_project["primary_scm_platform"] = "GitHub"
                            enhanced_project["primary_scm_url"] = f"https://github.com/{enhanced_project['github_mirror_org']}"
                    else:
                        enhanced_project["primary_scm_platform"] = "Unknown"
                        enhanced_project["primary_scm_url"] = ""

            enhanced_projects.append(enhanced_project)

        # Now add fall-through projects that aren't already in the list
        for alias_key, alias_data in PROJECT_ALIASES.items():
            primary_name = alias_data.get("primary_name", "")
            if not primary_name:
                continue

            # Check if this project is already included
            primary_name_lower = primary_name.lower()
            if primary_name_lower in existing_projects:
                continue

            # Check aliases too
            aliases = alias_data.get("aliases", [])
            if any(alias.lower() in existing_projects for alias in aliases):
                continue

            # This is a new fall-through project - add it
            fall_through_project = {
                "name": primary_name,
                "aliases": aliases,
                "primary_name": primary_name,
                "domain": alias_data.get("domain", ""),
                "primary_scm_platform": alias_data.get("primary_scm_platform", "Unknown"),
                "primary_scm_url": alias_data.get("primary_scm_url", "")
            }

            enhanced_projects.append(fall_through_project)
            existing_projects.add(primary_name_lower)
            logger.info(f"Added fall-through project: {primary_name}")

        return {
            "projects": enhanced_projects,
            "# SPDX-License-Identifier": "Apache-2.0",
            "# SPDX-FileCopyrightText": "2025 The Linux Foundation",
            "#": "",
            "# Enhanced projects database for lftools-ng": "",
            "# Includes main LF projects plus fall-through projects with accurate SCM mapping": "",
            f"# Last updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
