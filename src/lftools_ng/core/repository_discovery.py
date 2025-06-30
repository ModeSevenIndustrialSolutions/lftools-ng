# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Repository discovery for Linux Foundation projects."""

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx
import yaml

from lftools_ng.core.github_discovery import GitHubDiscovery
from lftools_ng.core.gerrit_ssh import GerritSSHClient

logger = logging.getLogger(__name__)


class RepositoryNameMapper:
    """Handles bidirectional mapping between Gerrit and GitHub repository names."""

    @staticmethod
    def gerrit_to_github_name(gerrit_path: str) -> str:
        """Convert Gerrit repository path to GitHub repository name.

        Gerrit supports nested projects with folder hierarchy (e.g., 'project/subproject/repo').
        GitHub flattens these into simple names under the org (e.g., 'repo' or 'project-subproject-repo').

        Args:
            gerrit_path: Gerrit repository path (e.g., 'project/subproject/repo')

        Returns:
            GitHub repository name
        """
        if not gerrit_path:
            return ""

        # Handle nested paths by taking the last component or flattening
        if '/' in gerrit_path:
            # For nested paths, we typically take the last component
            # unless it's a generic name like 'repo' or 'src'
            parts = gerrit_path.split('/')
            last_part = parts[-1].lower()

            # If last part is too generic, flatten the path
            if last_part in ['repo', 'src', 'code', 'project', 'main']:
                # Flatten: 'project/subproject/repo' -> 'project-subproject-repo'
                return '-'.join(parts)
            else:
                # Use last component: 'project/subproject/specific-name' -> 'specific-name'
                return parts[-1]
        else:
            return gerrit_path

    @staticmethod
    def github_to_gerrit_candidates(github_name: str, project_gerrit_repos: List[str]) -> List[str]:
        """Find possible Gerrit paths that could map to a GitHub repository name.

        Args:
            github_name: GitHub repository name
            project_gerrit_repos: List of all Gerrit repository paths for the project

        Returns:
            List of possible Gerrit paths (ordered by likelihood)
        """
        candidates = []
        github_lower = github_name.lower()

        # Direct matches
        for gerrit_path in project_gerrit_repos:
            if gerrit_path.lower() == github_lower:
                candidates.append(gerrit_path)

        # Last component matches
        for gerrit_path in project_gerrit_repos:
            if '/' in gerrit_path:
                last_component = gerrit_path.split('/')[-1].lower()
                if last_component == github_lower:
                    candidates.append(gerrit_path)

        # Flattened name matches (convert dashes back to slashes)
        if '-' in github_name:
            potential_path = github_name.replace('-', '/')
            for gerrit_path in project_gerrit_repos:
                if gerrit_path.lower() == potential_path.lower():
                    candidates.append(gerrit_path)

        return candidates

    @staticmethod
    def normalize_repository_name(name: str) -> str:
        """Normalize repository name for consistent comparison.

        Args:
            name: Repository name

        Returns:
            Normalized name
        """
        if not name:
            return ""
        return name.lower().strip()


class RepositoryDiscovery:
    """Discovers repositories from multiple SCM platforms."""

    def __init__(self):
        """Initialize repository discovery."""
        self.client = httpx.Client(
            timeout=60.0,
            headers={
                "User-Agent": "lftools-ng/1.0 (Linux Foundation Repository Discovery)"
            }
        )
        self.github_discovery = GitHubDiscovery()
        self.mapper = RepositoryNameMapper()
        self.gerrit_ssh_client = GerritSSHClient()  # Use SSH for Gerrit operations

    def discover_project_repositories(self, project_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discover repositories for a project from its primary SCM only.

        This method only discovers repositories from the primary SCM platform to avoid duplication.
        GitHub mirror information is added as metadata without creating duplicate repository entries.

        Args:
            project_data: Project dictionary containing SCM information

        Returns:
            List of repository dictionaries
        """
        project_name = project_data.get("name", "")
        logger.debug(f"Discovering repositories for project: {project_name}")

        repositories: List[Dict[str, Any]] = []

        # Get primary SCM platform and URL - check multiple field names for compatibility
        primary_scm = (
            project_data.get("primary_scm", "") or
            project_data.get("primary_scm_platform", "") or
            project_data.get("scm_platform", "")
        ).lower()

        # Get the primary SCM URL
        if primary_scm == "gerrit":
            primary_scm_url = project_data.get("gerrit_url", "") or project_data.get("primary_scm_url", "")
        elif primary_scm == "github":
            primary_scm_url = project_data.get("github_url", "") or project_data.get("primary_scm_url", "")
        else:
            primary_scm_url = project_data.get("primary_scm_url", "")

        # Skip projects without proper SCM configuration
        if not primary_scm or not primary_scm_url:
            logger.debug(f"Skipping {project_name}: no primary SCM configured (scm='{primary_scm}', url='{primary_scm_url}')")
            return repositories

        # Discover from primary SCM only
        if primary_scm == "gerrit":
            gerrit_repos = self._discover_gerrit_repositories(primary_scm_url, project_data)
            repositories.extend(gerrit_repos)
            logger.info(f"Discovered {len(gerrit_repos)} repositories from Gerrit for {project_name}")
        elif primary_scm == "github":
            github_repos = self._discover_github_repositories(primary_scm_url)
            repositories.extend(github_repos)
            logger.info(f"Discovered {len(github_repos)} repositories from GitHub for {project_name}")
        else:
            logger.warning(f"Unsupported primary SCM for {project_name}: {primary_scm}")
            return repositories

        # Add GitHub mirror metadata if available (but don't duplicate repositories)
        github_mirror_org = project_data.get("github_mirror_org")
        if github_mirror_org and primary_scm == "gerrit":
            self._add_github_mirror_metadata(repositories, github_mirror_org)

        # Add project metadata to all repositories
        for repo in repositories:
            repo["project"] = project_name

        logger.info(f"Total repositories discovered for {project_name}: {len(repositories)}")
        return repositories

    def _discover_gerrit_repositories(self, gerrit_url: str, project_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discover repositories from a Gerrit instance using SSH.

        Args:
            gerrit_url: Gerrit instance URL
            project_data: Project configuration

        Returns:
            List of repository dictionaries
        """
        repositories: List[Dict[str, Any]] = []
        project_name = project_data.get("name", "")

        try:
            logger.info(f"Discovering Gerrit repositories via SSH for {project_name}")

            # Use SSH client to get project list
            projects = self.gerrit_ssh_client.list_projects(gerrit_url)

            if not projects:
                logger.warning(f"No projects found for {gerrit_url} via SSH")
                return repositories

            # Convert to repository format
            for project in projects:
                project_path = project.get("name", "")
                if not project_path:
                    continue

                repo = {
                    "gerrit_path": project_path,
                    "gerrit_url": f"{gerrit_url}/gitweb?p={project_path}.git;a=summary",
                    "clone_url": f"{gerrit_url}/{project_path}",
                    "scm_platform": "gerrit",
                    "archived": project.get("state", "").upper() == "READ_ONLY",
                    "description": project.get("description", ""),
                    "github_name": self.mapper.gerrit_to_github_name(project_path),
                }
                repositories.append(repo)

            logger.info(f"Discovered {len(repositories)} Gerrit repositories for {project_name}")

        except Exception as e:
            logger.error(f"Failed to discover Gerrit repositories from {gerrit_url} via SSH: {e}")

        return repositories

    def _discover_github_repositories(self, github_url: str) -> List[Dict[str, Any]]:
        """Discover repositories from a GitHub organization.

        Args:
            github_url: GitHub organization or repository URL
            project_data: Optional project data for context

        Returns:
            List of repository dictionaries
        """
        repositories: List[Dict[str, Any]] = []

        try:
            # Extract organization from URL
            org_name = self._extract_github_org_from_url(github_url)
            if not org_name:
                return repositories

            # Use GitHub API to list repositories
            api_url = f"https://api.github.com/orgs/{org_name}/repos"

            # Handle pagination
            page = 1
            while page <= 10:  # Limit to prevent infinite loops
                params = {"page": page, "per_page": 100}
                response = self.client.get(api_url, params=params)

                if response.status_code != 200:
                    logger.warning(f"GitHub API returned {response.status_code} for {api_url}")
                    break

                repos_data = response.json()
                if not repos_data:
                    break

                for repo_info in repos_data:
                    repo = {
                        "github_name": repo_info["name"],
                        "github_url": repo_info["html_url"],
                        "clone_url": repo_info["clone_url"],
                        "ssh_url": repo_info["ssh_url"],
                        "scm_platform": "github",
                        "archived": repo_info.get("archived", False),
                        "description": repo_info.get("description", ""),
                        "stars": repo_info.get("stargazers_count", 0),
                        "forks": repo_info.get("forks_count", 0),
                        "language": repo_info.get("language", ""),
                        "updated_at": repo_info.get("updated_at", ""),
                    }
                    repositories.append(repo)

                page += 1

        except Exception as e:
            logger.error(f"Failed to discover GitHub repositories: {e}")

        return repositories

    def _add_github_mirror_metadata(self, repositories: List[Dict[str, Any]], github_org: str) -> None:
        """Add GitHub mirror metadata to repositories without creating duplicates.

        Args:
            repositories: List of repositories to enhance (modified in-place)
            github_org: GitHub organization name
        """
        try:
            # Get all GitHub repositories for the organization
            github_repos = self._discover_github_repositories(f"https://github.com/{github_org}")

            # Create lookup by GitHub name
            github_lookup = {repo["github_name"]: repo for repo in github_repos}

            # Add GitHub mirror metadata to existing repositories
            for repo in repositories:
                if "gerrit_path" in repo:
                    github_name = repo.get("github_name", "")
                    if github_name in github_lookup:
                        github_repo = github_lookup[github_name]
                        repo.update({
                            "github_mirror_url": github_repo["github_url"],
                            "github_clone_url": github_repo["clone_url"],
                            "github_ssh_url": github_repo["ssh_url"],
                            "github_stars": github_repo["stars"],
                            "github_forks": github_repo["forks"],
                            "github_language": github_repo["language"],
                            "github_updated_at": github_repo["updated_at"],
                        })

        except Exception as e:
            logger.warning(f"Failed to add GitHub mirror metadata: {e}")

    def _enhance_with_github_mirrors(self, repositories: List[Dict[str, Any]],
                                   github_org: str) -> None:
        """Enhance repository data with GitHub mirror information.

        Args:
            repositories: List of repositories to enhance (modified in-place)
            github_org: GitHub organization name
        """
        try:
            # Get all GitHub repositories for the organization
            github_repos = self._discover_github_repositories(f"https://github.com/{github_org}")

            # Create lookup by GitHub name
            github_lookup = {repo["github_name"]: repo for repo in github_repos}

            # Enhance existing repositories with GitHub mirror data
            for repo in repositories:
                if "gerrit_path" in repo:
                    github_name = repo.get("github_name", "")
                    if github_name in github_lookup:
                        github_repo = github_lookup[github_name]
                        repo.update({
                            "github_url": github_repo["github_url"],
                            "github_clone_url": github_repo["clone_url"],
                            "github_ssh_url": github_repo["ssh_url"],
                            "github_stars": github_repo["stars"],
                            "github_forks": github_repo["forks"],
                            "github_language": github_repo["language"],
                            "github_updated_at": github_repo["updated_at"],
                        })

            # Add GitHub-only repositories (not mirrored from Gerrit)
            gerrit_paths = {repo.get("gerrit_path", "") for repo in repositories}
            for github_repo in github_repos:
                # Check if this GitHub repo corresponds to any Gerrit repo
                github_name = github_repo["github_name"]
                candidates = self.mapper.github_to_gerrit_candidates(github_name, list(gerrit_paths))

                if not candidates:
                    # This is a GitHub-only repository
                    github_repo["is_github_only"] = True
                    repositories.append(github_repo)

        except Exception as e:
            logger.warning(f"Failed to enhance with GitHub mirrors: {e}")

    def _extract_github_org_from_url(self, url: str) -> Optional[str]:
        """Extract GitHub organization name from URL.

        Args:
            url: GitHub URL

        Returns:
            Organization name or None
        """
        try:
            parsed = urlparse(url)
            if parsed.netloc == "github.com":
                path_parts = parsed.path.strip('/').split('/')
                if path_parts and path_parts[0]:
                    return path_parts[0]
        except Exception:
            pass
        return None

    def close(self) -> None:
        """Close HTTP client and cleanup resources."""
        self.client.close()
        self.github_discovery.close()

    def __enter__(self) -> "RepositoryDiscovery":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> None:
        """Context manager exit."""
        self.close()
