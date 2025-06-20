# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Parser for Linux Foundation infrastructure inventory."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from lftools_ng.core.models import (
    IssueTrackingType,
    Project,
    Server,
    ServerLocation,
    ServerType,
    WikiType,
)
from lftools_ng.core.project_matcher import get_project_matcher

logger = logging.getLogger(__name__)

INVENTORY_URL = "https://docs.releng.linuxfoundation.org/en/latest/infra/inventory.html"


class InventoryParser:
    """Parser for Linux Foundation infrastructure inventory."""

    def __init__(self) -> None:
        """Initialize the inventory parser."""
        self.client = httpx.Client(timeout=30.0)

    def fetch_inventory_data(self, url: str = INVENTORY_URL) -> str:
        """Fetch the inventory HTML page.

        Args:
            url: URL to fetch inventory from.

        Returns:
            HTML content of the inventory page.

        Raises:
            httpx.RequestError: If request fails.
        """
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def parse_inventory_table(self, html_content: str) -> List[Dict[str, Any]]:
        """Parse the inventory table from HTML content.

        Args:
            html_content: HTML content containing the inventory table.

        Returns:
            List of project dictionaries parsed from the table.
        """
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find the table - it's the main table in the document
        tables = soup.find_all('table')
        if not tables:
            logger.warning("No tables found in inventory page")
            return []

        # The inventory table should be the first/main table
        table = tables[0]
        rows = table.find_all('tr')

        if len(rows) < 2:
            logger.warning("Inventory table has no data rows")
            return []

        # Parse header to understand column structure
        header_row = rows[0]
        headers = [th.get_text().strip() for th in header_row.find_all(['th', 'td'])]

        projects = []

        for row in rows[1:]:  # Skip header row
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                continue

            # First cell should contain the project name
            project_name = cells[0].get_text().strip()
            if not project_name or project_name in ['Project', '']:
                continue

            project_data = self._parse_project_row(project_name, cells)
            if project_data:
                projects.append(project_data)

        return projects

    def _parse_project_row(self, project_name: str, cells: List[Any]) -> Optional[Dict[str, Any]]:
        """Parse a single project row from the table.

        Args:
            project_name: Name of the project.
            cells: Table cells for this row.

        Returns:
            Project dictionary or None if parsing fails.
        """
        try:
            project_data = {
                "name": project_name,
                "primary_name": project_name,
                "aliases": [],
                "previous_names": [],
            }

            # Use project matcher for enhanced alias detection
            matcher = get_project_matcher()
            project_info = matcher.get_project_info(project_name)

            if project_info:
                project_data["primary_name"] = project_info["primary_name"]
                project_data["aliases"] = project_info["aliases"]
                project_data["previous_names"] = project_info.get("previous_names", [])

            # Parse URLs from each cell (skip first cell which is project name)
            for i, cell in enumerate(cells[1:], 1):
                cell_text = cell.get_text().strip()
                if not cell_text or cell_text == "N/A":
                    continue

                # Extract URLs from the cell
                urls = self._extract_urls_from_cell(cell)

                # Classify URLs based on column position and content
                for url in urls:
                    self._classify_and_assign_url(project_data, url)

            return project_data

        except Exception as e:
            logger.warning(f"Failed to parse project row for {project_name}: {e}")
            return None

    def _extract_urls_from_cell(self, cell: Any) -> List[str]:
        """Extract URLs from a table cell.

        Args:
            cell: BeautifulSoup cell element.

        Returns:
            List of URLs found in the cell.
        """
        urls = []

        # Extract from href attributes
        for link in cell.find_all('a', href=True):
            urls.append(link['href'])

        # Extract from text content (space or newline separated)
        cell_text = cell.get_text()
        url_pattern = r'https?://[^\s]+'
        text_urls = re.findall(url_pattern, cell_text)
        urls.extend(text_urls)

        return urls

    def _classify_and_assign_url(self, project_data: Dict[str, Any], url: str) -> None:
        """Classify a URL and assign it to the appropriate project field.

        Args:
            project_data: Project dictionary to update.
            url: URL to classify and assign.
        """
        url_lower = url.lower()
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()

        # Gerrit servers
        if 'gerrit' in domain or 'gerrit' in url_lower:
            project_data['gerrit_url'] = url

        # GitHub organizations
        elif 'github.com' in domain:
            project_data['github_mirror_org'] = self._extract_github_org(url)

        # Jenkins servers
        elif 'jenkins' in domain:
            if 'sandbox' in url_lower:
                project_data['jenkins_sandbox'] = url
            else:
                project_data['jenkins_production'] = url

        # Nexus repositories
        elif 'nexus3' in domain or 'nexus3' in url_lower:
            project_data['nexus3_url'] = url
        elif 'nexus' in domain:
            project_data['nexus_url'] = url

        # Wiki systems
        elif 'wiki' in domain or 'wiki' in url_lower:
            project_data['wiki_url'] = url
            project_data['wiki_type'] = self._determine_wiki_type(url)

        # Documentation
        elif 'docs' in domain or 'docs' in url_lower or 'readthedocs' in domain:
            project_data['docs_url'] = url

        # Issue tracking
        elif 'jira' in domain:
            project_data['issue_tracking_url'] = url
            project_data['issue_tracking_type'] = IssueTrackingType.JIRA.value

        # SonarQube/SonarCloud
        elif 'sonar' in domain:
            project_data['sonar_url'] = url

        # Logs
        elif 'logs' in domain or 'logs' in url_lower:
            project_data['logs_url'] = url

    def _extract_github_org(self, github_url: str) -> str:
        """Extract GitHub organization from URL.

        Args:
            github_url: GitHub URL.

        Returns:
            GitHub organization name.
        """
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip('/').split('/')
        if path_parts:
            return path_parts[0]
        return ""

    def _determine_wiki_type(self, wiki_url: str) -> str:
        """Determine the type of wiki system from URL.

        Args:
            wiki_url: Wiki URL.

        Returns:
            Wiki type string.
        """
        url_lower = wiki_url.lower()

        if 'github.com' in url_lower and 'wiki' in url_lower:
            return WikiType.GITHUB_WIKI.value
        elif 'gitlab' in url_lower and 'wiki' in url_lower:
            return WikiType.GITLAB_WIKI.value
        elif 'atlassian' in url_lower or 'confluence' in url_lower:
            return WikiType.CONFLUENCE.value
        else:
            return WikiType.MEDIAWIKI.value

    def parse_projects_from_inventory(self, url: str = INVENTORY_URL) -> List[Project]:
        """Parse projects from the Linux Foundation inventory.

        Args:
            url: URL of the inventory page.

        Returns:
            List of Project objects.
        """
        html_content = self.fetch_inventory_data(url)
        project_dicts = self.parse_inventory_table(html_content)

        projects = []
        for project_dict in project_dicts:
            try:
                project = Project(
                    name=project_dict.get("name", ""),
                    aliases=project_dict.get("aliases", []),
                    gerrit_url=project_dict.get("gerrit_url"),
                    github_mirror_org=project_dict.get("github_mirror_org"),
                    jenkins_production=project_dict.get("jenkins_production"),
                    jenkins_sandbox=project_dict.get("jenkins_sandbox"),
                    nexus_url=project_dict.get("nexus_url"),
                    nexus3_url=project_dict.get("nexus3_url"),
                    sonar_url=project_dict.get("sonar_url"),
                    logs_url=project_dict.get("logs_url"),
                )
                projects.append(project)
            except Exception as e:
                logger.warning(f"Failed to create Project object for {project_dict.get('name', 'unknown')}: {e}")

        return projects

    def extract_servers_from_projects(self, projects: List[Project]) -> List[Server]:
        """Extract unique servers from project configurations.

        Args:
            projects: List of Project objects.

        Returns:
            List of Server objects.
        """
        servers = []
        seen_servers: Dict[str, Server] = {}

        for project in projects:
            # Extract different types of servers
            server_mappings = [
                (project.gerrit_url, ServerType.GERRIT, project.github_mirror_org),
                (project.jenkins_production, ServerType.JENKINS, None, True),
                (project.jenkins_sandbox, ServerType.JENKINS, None, False),
                (project.nexus_url, ServerType.NEXUS, None),
                (project.nexus3_url, ServerType.NEXUS3, None),
                (project.sonar_url, ServerType.SONAR, None),
            ]

            for mapping in server_mappings:
                url = mapping[0]
                server_type = mapping[1]
                extra_info = mapping[2] if len(mapping) > 2 else None
                is_production = mapping[3] if len(mapping) > 3 else True

                if not url:
                    continue

                parsed_url = urlparse(url)
                server_name = parsed_url.netloc

                if server_name in seen_servers:
                    # Add project to existing server
                    seen_servers[server_name].projects.append(project.name)
                else:
                    # Create new server
                    server = Server(
                        name=server_name,
                        url=url,
                        server_type=server_type,
                        github_mirror_org=extra_info if server_type == ServerType.GERRIT else None,
                        is_production=is_production,
                        location=self._determine_server_location(server_name),
                        projects=[project.name],
                    )
                    seen_servers[server_name] = server
                    servers.append(server)

        return servers

    def _determine_server_location(self, server_name: str) -> ServerLocation:
        """Determine server location based on hostname.

        Args:
            server_name: Server hostname.

        Returns:
            ServerLocation enum value.
        """
        name_lower = server_name.lower()

        # SAAS/Hosted services
        if any(saas in name_lower for saas in [
            'atlassian.net', 'jira.com', 'confluence.com', 'github.com',
            'gitlab.com', 'readthedocs.org', 'artifactory.com', 'sonarcloud.io'
        ]):
            return ServerLocation.SAAS

        # Infrastructure providers
        if 'vexxhost' in name_lower:
            return ServerLocation.VEXXHOST
        elif 'aws' in name_lower or 'amazonaws' in name_lower:
            return ServerLocation.AWS
        elif 'korg' in name_lower or 'kernel.org' in name_lower:
            return ServerLocation.KORG
        else:
            return ServerLocation.OTHER

    def _test_url_accessibility(self, url: str) -> bool:
        """Test if a URL is accessible and returns a valid response.

        Args:
            url: URL to test.

        Returns:
            True if URL is accessible.
        """
        if not url:
            return False

        try:
            import requests

            # Test the URL with a short timeout and simple request
            response = requests.head(url, timeout=5, allow_redirects=True)

            # Consider 2xx and 3xx responses as successful
            # Some services return 405 for HEAD requests but are still valid
            if response.status_code in range(200, 400) or response.status_code == 405:
                logger.debug(f"URL {url} is accessible (status: {response.status_code})")
                return True
            else:
                logger.debug(f"URL {url} returned status: {response.status_code}")
                return False

        except ImportError:
            # If requests is not available, assume URL is accessible
            logger.warning("requests library not available, cannot test URL accessibility")
            return True
        except Exception as e:
            logger.debug(f"URL {url} accessibility test failed: {e}")
            return False

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
