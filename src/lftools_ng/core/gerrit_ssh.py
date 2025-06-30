# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Gerrit SSH client for lftools-ng repository discovery."""

import json
import logging
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from lftools_ng.core.ssh_config_parser import SSHConfigParser

logger = logging.getLogger(__name__)


class GerritSSHClient:
    """SSH client for Gerrit operations."""

    def __init__(self, timeout: int = 30):
        """Initialize Gerrit SSH client.

        Args:
            timeout: SSH connection timeout in seconds
        """
        self.timeout = timeout
        self.ssh_config = SSHConfigParser()

    def list_projects(self, gerrit_url: str) -> List[Dict[str, Any]]:
        """List all projects from a Gerrit instance via SSH.

        Args:
            gerrit_url: Gerrit URL (e.g., https://gerrit.onap.org)

        Returns:
            List of project dictionaries
        """
        hostname, port = self._parse_gerrit_url(gerrit_url)
        if not hostname:
            logger.error(f"Could not parse Gerrit URL: {gerrit_url}")
            return []

        # Get SSH username for this host
        username = self._get_ssh_username(hostname)
        if not username:
            logger.error(f"No SSH username configured for {hostname}")
            return []

        logger.info(f"Connecting to Gerrit via SSH: {username}@{hostname}:{port}")

        try:
            # Execute gerrit ls-projects command
            projects_output = self._execute_gerrit_command(
                hostname, port, username, "gerrit ls-projects --format json --all"
            )

            if not projects_output:
                logger.warning(f"No output from gerrit ls-projects on {hostname}")
                return []

            # Parse JSON output - Gerrit returns a single JSON object with all projects
            projects = []
            try:
                # The output is a single JSON object where keys are project names
                all_projects = json.loads(projects_output)

                for project_name, project_data in all_projects.items():
                    if project_name:
                        projects.append({
                            'name': project_name,
                            'description': project_data.get('description', ''),
                            'state': project_data.get('state', 'ACTIVE'),
                            'web_links': project_data.get('web_links', [])
                        })

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse projects JSON from {hostname}: {e}")
                # Try line-by-line parsing as fallback
                for line in projects_output.strip().split('\n'):
                    if line.strip():
                        try:
                            project_data = json.loads(line)
                            project_name = project_data.get('id', '')
                            if project_name:
                                projects.append({
                                    'name': project_name,
                                    'description': project_data.get('description', ''),
                                    'state': project_data.get('state', 'ACTIVE'),
                                    'web_links': project_data.get('web_links', [])
                                })
                        except json.JSONDecodeError:
                            continue

            logger.info(f"Retrieved {len(projects)} projects from {hostname}")
            return projects

        except Exception as e:
            logger.error(f"Failed to list projects from {hostname}: {e}")
            return []

    def get_project_info(self, gerrit_url: str, project_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific project.

        Args:
            gerrit_url: Gerrit URL
            project_name: Name of the project

        Returns:
            Project information dictionary or None
        """
        hostname, port = self._parse_gerrit_url(gerrit_url)
        if not hostname:
            return None

        username = self._get_ssh_username(hostname)
        if not username:
            return None

        try:
            # Get project details
            cmd = f"gerrit ls-projects --format json --project {project_name}"
            output = self._execute_gerrit_command(hostname, port, username, cmd)

            if output:
                for line in output.strip().split('\\n'):
                    if line.strip():
                        try:
                            project_info = json.loads(line)
                            # Ensure we return a proper dict
                            if isinstance(project_info, dict):
                                return project_info
                        except json.JSONDecodeError:
                            continue

            return None

        except Exception as e:
            logger.error(f"Failed to get project info for {project_name}: {e}")
            return None

    def test_connection(self, gerrit_url: str) -> Tuple[bool, str]:
        """Test SSH connection to Gerrit.

        Args:
            gerrit_url: Gerrit URL to test

        Returns:
            Tuple of (success, message)
        """
        hostname, port = self._parse_gerrit_url(gerrit_url)
        if not hostname:
            return False, f"Could not parse URL: {gerrit_url}"

        username = self._get_ssh_username(hostname)
        if not username:
            return False, f"No SSH username configured for {hostname}"

        try:
            # Test with a simple gerrit version command
            output = self._execute_gerrit_command(
                hostname, port, username, "gerrit version", timeout=10
            )

            if output and "gerrit version" in output.lower():
                return True, f"Connected successfully to {hostname}"
            else:
                return False, f"Gerrit service not responding on {hostname}"

        except Exception as e:
            return False, f"Connection failed: {e}"

    def _parse_gerrit_url(self, gerrit_url: str) -> Tuple[Optional[str], int]:
        """Parse Gerrit URL to extract hostname and SSH port.

        Args:
            gerrit_url: Gerrit URL (HTTP/HTTPS)

        Returns:
            Tuple of (hostname, ssh_port)
        """
        try:
            parsed = urlparse(gerrit_url)
            hostname = parsed.netloc

            # Check if custom port is specified in URL
            if ':' in hostname:
                hostname_part, port_part = hostname.split(':', 1)
                try:
                    custom_port = int(port_part)
                    # Use custom port if it's not the standard HTTP/HTTPS ports
                    if custom_port not in [80, 443]:
                        return hostname_part, custom_port
                    else:
                        hostname = hostname_part
                except ValueError:
                    # If port parsing fails, use just the hostname
                    hostname = hostname_part

            # Default Gerrit SSH port
            ssh_port = 29418

            return hostname, ssh_port

        except Exception as e:
            logger.error(f"Failed to parse Gerrit URL {gerrit_url}: {e}")
            return None, 29418

    def _get_ssh_username(self, hostname: str) -> Optional[str]:
        """Get SSH username for Gerrit host.

        Args:
            hostname: Gerrit hostname

        Returns:
            SSH username or None
        """
        # First try SSH config
        ssh_username = self.ssh_config.get_username_for_host(hostname)
        if ssh_username:
            return ssh_username

        # Try common Gerrit usernames
        import os
        current_user = os.getenv('USER') or os.getenv('USERNAME')
        if current_user:
            return current_user

        # Default fallback (not ideal, but better than failing)
        logger.warning(f"No SSH username found for {hostname}, this may cause authentication issues")
        return None

    def _execute_gerrit_command(self, hostname: str, port: int, username: str,
                               command: str, timeout: Optional[int] = None) -> str:
        """Execute a Gerrit SSH command.

        Args:
            hostname: Gerrit hostname
            port: SSH port (usually 29418)
            username: SSH username
            command: Gerrit command to execute
            timeout: Command timeout (uses instance timeout if None)

        Returns:
            Command output

        Raises:
            Exception: If command fails
        """
        cmd_timeout = timeout or self.timeout

        # Build SSH command that respects local SSH configuration
        ssh_cmd = [
            "ssh",
            "-o", f"ConnectTimeout={cmd_timeout}",
            "-o", "BatchMode=yes",  # Use SSH agent/keys, no password prompts
            "-o", "StrictHostKeyChecking=no",  # Skip host key verification
            "-o", "UserKnownHostsFile=/dev/null",  # Don't save host keys
            "-o", "LogLevel=ERROR",  # Reduce SSH noise
            "-p", str(port),
            f"{username}@{hostname}",
            command
        ]

        logger.debug(f"Executing SSH command: {' '.join(ssh_cmd[:-1])} '<command>'")

        try:
            result = subprocess.run(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=cmd_timeout + 5,  # Add buffer
                check=False,
                text=True
            )

            if result.returncode == 0:
                return result.stdout
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                logger.error(f"Gerrit SSH command failed (exit {result.returncode}): {error_msg}")
                raise Exception(f"SSH command failed: {error_msg}")

        except subprocess.TimeoutExpired:
            raise Exception(f"SSH command timed out after {cmd_timeout} seconds")
        except Exception as e:
            logger.error(f"Failed to execute SSH command on {hostname}: {e}")
            raise

    def get_ssh_info_for_host(self, hostname: str) -> Dict[str, Any]:
        """Get SSH configuration info for a Gerrit host.

        Args:
            hostname: Gerrit hostname

        Returns:
            Dictionary with SSH configuration details
        """
        return self.ssh_config.get_host_config_summary(hostname)


class GerritRepositoryMapper:
    """Maps Gerrit repository paths to GitHub mirror names."""

    @staticmethod
    def gerrit_to_github_name(gerrit_path: str) -> str:
        """Convert Gerrit repository path to likely GitHub repository name.

        Gerrit supports nested projects with folder hierarchy (e.g., 'project/subproject/repo').
        GitHub flattens these into simple names under the org.

        Args:
            gerrit_path: Gerrit repository path

        Returns:
            Likely GitHub repository name
        """
        if not gerrit_path:
            return ""

        # Handle nested paths
        if '/' in gerrit_path:
            parts = gerrit_path.split('/')
            last_part = parts[-1].lower()

            # If last part is too generic, flatten the path
            generic_names = ['repo', 'src', 'code', 'project', 'main', 'core']
            if last_part in generic_names:
                # Flatten: 'project/subproject/repo' -> 'project-subproject-repo'
                return '-'.join(parts)
            else:
                # Use last component: 'project/subproject/specific-name' -> 'specific-name'
                return parts[-1]
        else:
            return gerrit_path

    @staticmethod
    def github_to_gerrit_candidates(github_name: str, gerrit_projects: List[str]) -> List[str]:
        """Find possible Gerrit paths that could map to a GitHub repository name.

        Args:
            github_name: GitHub repository name
            gerrit_projects: List of all Gerrit project paths

        Returns:
            List of possible Gerrit paths (ordered by likelihood)
        """
        candidates = []
        github_lower = github_name.lower()

        # Direct matches
        for gerrit_path in gerrit_projects:
            if gerrit_path.lower() == github_lower:
                candidates.append(gerrit_path)

        # Last component matches
        for gerrit_path in gerrit_projects:
            if '/' in gerrit_path:
                last_component = gerrit_path.split('/')[-1].lower()
                if last_component == github_lower:
                    candidates.append(gerrit_path)

        # Flattened name matches (convert dashes back to slashes)
        if '-' in github_name:
            potential_path = github_name.replace('-', '/')
            for gerrit_path in gerrit_projects:
                if gerrit_path.lower() == potential_path.lower():
                    candidates.append(gerrit_path)

        return candidates
