# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""GitHub organization discovery for Linux Foundation projects."""

import logging
import re
from typing import Any, Dict, List, Optional, Set
from types import TracebackType
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Constants to avoid duplication
HTML_PARSER = 'html.parser'
GITHUB_COM_PATTERN = r'github\.com'
GITHUB_ORG_PATTERN = r'github\.com/([^/\s]+)'


class GitHubDiscovery:
    """Discovers GitHub organizations for Linux Foundation projects."""

    def __init__(self) -> None:
        """Initialize the GitHub discovery service."""
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "lftools-ng/1.0 (Linux Foundation Project Discovery)"
            }
        )

        # Cache for discovered organizations to avoid repeated API calls
        self._verified_orgs: Set[str] = set()
        self._non_existent_orgs: Set[str] = set()

    def discover_github_organization(self, project_data: Dict[str, Any]) -> Optional[str]:
        """Discover GitHub organization for a project using multiple methods.

        Args:
            project_data: Project dictionary containing name, aliases, gerrit_url, etc.

        Returns:
            GitHub organization name if found, None otherwise
        """
        project_name = project_data.get("name", "")
        logger.info(f"Discovering GitHub organization for project: {project_name}")

        # Method 1: Check if already exists and verify
        existing_org = self._check_existing_github_org(project_data)
        if existing_org:
            return existing_org

        # Method 2: Check Gerrit for GitHub mirror configuration
        gerrit_org = self._discover_from_gerrit(project_data.get("gerrit_url"))
        if gerrit_org:
            return gerrit_org

        # Method 3: Try direct name matching
        direct_org = self._discover_from_direct_matching(project_data)
        if direct_org:
            return direct_org

        # Method 4: Search project homepage/documentation
        homepage_org = self._discover_from_project_homepage(project_data)
        if homepage_org:
            return homepage_org

        # Method 5: Search Wikipedia
        wikipedia_org = self._discover_from_wikipedia(project_data)
        if wikipedia_org:
            return wikipedia_org

        logger.info(f"No GitHub organization found for project: {project_name}")
        return None

    def _check_existing_github_org(self, project_data: Dict[str, Any]) -> Optional[str]:
        """Check and verify existing GitHub organization in project data."""
        existing_github_org = project_data.get("github_mirror_org")
        if existing_github_org and self._verify_github_org_exists(existing_github_org):
            logger.info(f"Existing GitHub org verified: {existing_github_org}")
            return str(existing_github_org)
        elif existing_github_org:
            logger.warning(f"Existing GitHub org {existing_github_org} not found, searching for alternatives")
        return None

    def _discover_from_direct_matching(self, project_data: Dict[str, Any]) -> Optional[str]:
        """Try direct matching of project name and aliases."""
        project_name = project_data.get("name", "")
        project_aliases = project_data.get("aliases", [])

        candidates = [project_name.lower()]
        candidates.extend([alias.lower() for alias in project_aliases if alias])

        # Try direct candidates first
        for candidate in candidates:
            clean_candidate = self._clean_organization_name(candidate)
            if clean_candidate and self._verify_github_org_exists(clean_candidate):
                logger.info(f"Found GitHub org via direct match: {clean_candidate}")
                return clean_candidate

        # Try name variations
        for candidate in candidates:
            variations = self._generate_name_variations(candidate)
            for variation in variations:
                if self._verify_github_org_exists(variation):
                    logger.info(f"Found GitHub org via variation: {variation}")
                    return variation

        return None

    def _discover_from_gerrit(self, gerrit_url: Optional[str]) -> Optional[str]:
        """Discover GitHub organization from Gerrit mirror configuration."""
        if not gerrit_url:
            return None

        try:
            # Try Gerrit API endpoints
            api_org = self._check_gerrit_api(gerrit_url)
            if api_org:
                return api_org

            # Fallback: scrape Gerrit web interface
            web_org = self._check_gerrit_web(gerrit_url)
            if web_org:
                return web_org

        except Exception as e:
            logger.debug(f"Error discovering from Gerrit {gerrit_url}: {e}")

        return None

    def _check_gerrit_api(self, gerrit_url: str) -> Optional[str]:
        """Check Gerrit API for GitHub mirrors."""
        parsed_url = urlparse(gerrit_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        api_endpoints = [
            f"{base_url}/projects/",
            f"{base_url}/a/projects/",
            f"{base_url}/r/projects/"
        ]

        for api_url in api_endpoints:
            try:
                response = self.client.get(api_url, timeout=10)
                if response.status_code == 200:
                    content = response.text
                    if content.startswith(")]}'"):  # Gerrit's XSSI protection
                        content = content[5:]

                    # Look for GitHub URLs in the response
                    github_matches = re.findall(GITHUB_ORG_PATTERN, content)
                    if github_matches:
                        # Find most common organization
                        org_counts: Dict[str, int] = {}
                        for org in github_matches:
                            org_counts[org] = org_counts.get(org, 0) + 1

                        if org_counts:
                            most_common_org = max(org_counts.keys(), key=lambda x: org_counts[x])
                            if self._verify_github_org_exists(most_common_org):
                                logger.info(f"Found GitHub org from Gerrit API: {most_common_org}")
                                return most_common_org
                    break

            except Exception as e:
                logger.debug(f"Failed to query Gerrit API {api_url}: {e}")

        return None

    def _check_gerrit_web(self, gerrit_url: str) -> Optional[str]:
        """Check Gerrit web interface for GitHub links."""
        try:
            response = self.client.get(gerrit_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, HTML_PARSER)

                # Look for GitHub links in the page
                github_links = soup.find_all('a', href=re.compile(GITHUB_COM_PATTERN))
                for link in github_links:
                    if isinstance(link, Tag) and hasattr(link, 'get'):
                        href = str(link.get('href', ''))
                        match = re.search(GITHUB_ORG_PATTERN, href)
                        if match:
                            org = match.group(1)
                            if self._verify_github_org_exists(org):
                                logger.info(f"Found GitHub org from Gerrit web: {org}")
                                return org

        except Exception as e:
            logger.debug(f"Failed to scrape Gerrit web interface: {e}")

        return None

    def _discover_from_project_homepage(self, project_data: Dict[str, Any]) -> Optional[str]:
        """Discover GitHub organization from project homepage or documentation."""
        urls_to_check = self._get_project_urls(project_data)

        for url in urls_to_check:
            org = self._extract_github_org_from_url(url)
            if org:
                return org

        return None

    def _get_project_urls(self, project_data: Dict[str, Any]) -> List[str]:
        """Get list of URLs to check for GitHub links."""
        url_fields = ['docs_url', 'wiki_url', 'homepage_url', 'website_url']
        urls: List[str] = []

        # Add known URLs first
        for field in url_fields:
            url = project_data.get(field)
            if url:
                urls.append(url)

        # Add likely URLs based on project name and aliases
        project_name = project_data.get("name", "")
        if project_name:
            urls.extend(self._generate_likely_urls(project_name))

        for alias in project_data.get("aliases", []):
            if alias:
                urls.extend(self._generate_likely_urls(alias))

        return urls

    def _generate_likely_urls(self, name: str) -> List[str]:
        """Generate likely homepage URLs for a project name."""
        name_lower = name.lower().replace(" ", "")
        return [
            f"https://{name_lower}.org",
            f"https://www.{name_lower}.org",
            f"https://{name_lower}.io",
            f"https://www.{name_lower}.io"
        ]

    def _extract_github_org_from_url(self, url: str) -> Optional[str]:
        """Extract GitHub organization from a URL by checking its content."""
        try:
            response = self.client.get(url, timeout=10, follow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, HTML_PARSER)

                # Look for GitHub links
                github_links = soup.find_all('a', href=re.compile(GITHUB_COM_PATTERN))
                for link in github_links:
                    if isinstance(link, Tag) and hasattr(link, 'get'):
                        href = str(link.get('href', ''))
                        match = re.search(GITHUB_ORG_PATTERN, href)
                        if match:
                            org = match.group(1)
                            # Filter out non-organization pages
                            if org not in ['login', 'join', 'pricing', 'features'] and self._verify_github_org_exists(org):
                                logger.info(f"Found GitHub org from homepage {url}: {org}")
                                return org

        except Exception as e:
            logger.debug(f"Failed to check URL {url}: {e}")

        return None

    def _discover_from_wikipedia(self, project_data: Dict[str, Any]) -> Optional[str]:
        """Discover GitHub organization from Wikipedia."""
        project_name = project_data.get("name", "")
        aliases = project_data.get("aliases", [])

        search_terms = [project_name] + aliases

        for term in search_terms:
            if not term:
                continue

            org = self._search_wikipedia_for_github(term)
            if org:
                return org

        return None

    def _search_wikipedia_for_github(self, term: str) -> Optional[str]:
        """Search Wikipedia for GitHub references for a given term."""
        try:
            # Search Wikipedia API
            search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{term.replace(' ', '_')}"
            response = self.client.get(search_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                extract = data.get('extract', '')

                # Look for GitHub mentions in the extract
                github_matches = re.findall(GITHUB_ORG_PATTERN, extract)
                for org in github_matches:
                    if self._verify_github_org_exists(org):
                        logger.info(f"Found GitHub org from Wikipedia: {org}")
                        return str(org)

            # Also try the full Wikipedia page
            return self._search_wikipedia_page(term)

        except Exception as e:
            logger.debug(f"Failed to search Wikipedia for {term}: {e}")

        return None

    def _search_wikipedia_page(self, term: str) -> Optional[str]:
        """Search full Wikipedia page for GitHub links."""
        try:
            page_url = f"https://en.wikipedia.org/wiki/{term.replace(' ', '_')}"
            response = self.client.get(page_url, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, HTML_PARSER)
                github_links = soup.find_all('a', href=re.compile(GITHUB_COM_PATTERN))

                for link in github_links:
                    if isinstance(link, Tag) and hasattr(link, 'get'):
                        href = str(link.get('href', ''))
                        match = re.search(GITHUB_ORG_PATTERN, href)
                        if match:
                            org = match.group(1)
                            if self._verify_github_org_exists(org):
                                logger.info(f"Found GitHub org from Wikipedia page: {org}")
                                return org

        except Exception as e:
            logger.debug(f"Failed to search Wikipedia page for {term}: {e}")

        return None

    def _generate_name_variations(self, name: str) -> List[str]:
        """Generate common variations of a project name for GitHub org search."""
        variations: List[str] = []
        clean_name = self._clean_organization_name(name)

        if not clean_name:
            return variations

        variations.append(clean_name)

        # Add variations with common prefixes/suffixes
        variations.extend([
            f"{clean_name}-project",
            f"{clean_name}project",
            f"project-{clean_name}",
            f"{clean_name}-foundation",
            f"{clean_name}foundation",
            f"{clean_name}-org",
            f"{clean_name}org"
        ])

        # Add variations with different separators
        if '-' in clean_name:
            variations.append(clean_name.replace('-', ''))
            variations.append(clean_name.replace('-', '_'))

        if '_' in clean_name:
            variations.append(clean_name.replace('_', ''))
            variations.append(clean_name.replace('_', '-'))

        # Remove duplicates and return
        return list(dict.fromkeys(variations))

    def _clean_organization_name(self, name: str) -> str:
        """Clean a name to be suitable as a GitHub organization name."""
        if not name:
            return ""

        # Convert to lowercase
        clean = name.lower()

        # Remove common words that don't belong in org names
        clean = re.sub(r'\b(the|project|foundation|consortium|alliance|group|community|initiative)\b', '', clean)

        # Replace spaces and special characters with hyphens
        clean = re.sub(r'[^\w\-]', '-', clean)

        # Remove multiple consecutive hyphens
        clean = re.sub(r'-+', '-', clean)

        # Remove leading/trailing hyphens
        clean = clean.strip('-')

        return clean

    def _verify_github_org_exists(self, org_name: str) -> bool:
        """Verify that a GitHub organization exists."""
        if not org_name:
            return False

        # Check cache first
        if org_name in self._verified_orgs:
            return True
        if org_name in self._non_existent_orgs:
            return False

        try:
            # Check if organization exists by trying to access its page
            url = f"https://github.com/{org_name}"
            response = self.client.head(url, timeout=10)

            if response.status_code == 200:
                self._verified_orgs.add(org_name)
                logger.debug(f"Verified GitHub org exists: {org_name}")
                return True
            else:
                self._non_existent_orgs.add(org_name)
                logger.debug(f"GitHub org does not exist: {org_name}")
                return False

        except Exception as e:
            logger.debug(f"Failed to verify GitHub org {org_name}: {e}")
            # Don't cache on error, might be temporary
            return False

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "GitHubDiscovery":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Context manager exit."""
        self.close()
