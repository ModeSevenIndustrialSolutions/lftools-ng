# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""SSH configuration file parser for lftools-ng connectivity testing."""

import logging
import os
import pathlib
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SSHConfigParser:
    """Parse and query SSH configuration files."""

    def __init__(self, config_path: Optional[pathlib.Path] = None) -> None:
        """Initialize SSH config parser.

        Args:
            config_path: Path to SSH config file (default: ~/.ssh/config)
        """
        self.config_path = config_path or pathlib.Path.home() / ".ssh" / "config"
        self._config_data: List[Dict[str, Any]] = []
        self._parsed = False

    def _parse_config(self) -> None:
        """Parse the SSH configuration file."""
        if self._parsed:
            return

        if not self.config_path.exists():
            logger.debug(f"SSH config file not found: {self.config_path}")
            self._parsed = True
            return

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()

            current_host = None
            current_config: Dict[str, Any] = {}

            for line in content.split('\n'):
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                # Check for Host directive
                if line.lower().startswith('host '):
                    # Save previous host config if exists
                    if current_host and current_config:
                        self._config_data.append({
                            'host_patterns': current_host,
                            'config': current_config.copy()
                        })

                    # Start new host config
                    current_host = line[5:].strip()  # Remove "Host "
                    current_config = {}
                    continue

                # Parse config directive
                if current_host and ' ' in line:
                    key, value = line.split(' ', 1)
                    key = key.lower()
                    current_config[key] = value.strip()

            # Save last host config
            if current_host and current_config:
                self._config_data.append({
                    'host_patterns': current_host,
                    'config': current_config.copy()
                })

            self._parsed = True
            logger.debug(f"Parsed SSH config with {len(self._config_data)} host entries")

        except Exception as e:
            logger.debug(f"Error parsing SSH config {self.config_path}: {e}")
            self._parsed = True

    def get_config_for_host(self, hostname: str) -> Dict[str, str]:
        """Get SSH configuration for a specific host.

        Args:
            hostname: Hostname or IP address to match

        Returns:
            Dictionary of SSH configuration options
        """
        self._parse_config()

        merged_config: Dict[str, str] = {}

        for entry in self._config_data:
            host_patterns = entry['host_patterns']
            config = entry['config']

            # Check if hostname matches any of the patterns
            if self._hostname_matches_patterns(hostname, host_patterns):
                # Merge config (first match takes precedence for each key)
                for key, value in config.items():
                    if key not in merged_config:
                        merged_config[key] = value

        return merged_config

    def _hostname_matches_patterns(self, hostname: str, patterns: str) -> bool:
        """Check if hostname matches SSH host patterns.

        SSH config processes patterns as a group where negated patterns (starting with !)
        exclude matches from positive patterns in the same group.

        Args:
            hostname: Hostname to check
            patterns: Space-separated list of patterns

        Returns:
            True if hostname matches any positive pattern and no negative patterns
        """
        pattern_list = patterns.split()

        # Separate positive and negative patterns
        positive_patterns: List[str] = []
        negative_patterns: List[str] = []

        for pattern in pattern_list:
            if pattern.startswith('!'):
                negative_patterns.append(pattern[1:])  # Remove the !
            else:
                positive_patterns.append(pattern)

        # Check if hostname matches any positive pattern
        positive_match = False
        for pattern in positive_patterns:
            if self._match_pattern(hostname, pattern):
                positive_match = True
                break

        if not positive_match:
            return False

        # Check if hostname matches any negative pattern (exclusion)
        for pattern in negative_patterns:
            if self._match_pattern(hostname, pattern):
                return False  # Excluded by negative pattern

        return True

    def _match_pattern(self, hostname: str, pattern: str) -> bool:
        """Check if hostname matches a single SSH pattern.

        SSH patterns support:
        - * for any characters
        - ? for single character
        - Exact matches

        Args:
            hostname: Hostname to check
            pattern: SSH pattern (without negation prefix)

        Returns:
            True if hostname matches pattern
        """
        # Convert SSH pattern to regex
        regex_pattern = pattern
        regex_pattern = regex_pattern.replace('.', r'\.')
        regex_pattern = regex_pattern.replace('*', '.*')
        regex_pattern = regex_pattern.replace('?', '.')
        regex_pattern = f'^{regex_pattern}$'

        try:
            return bool(re.match(regex_pattern, hostname))
        except re.error:
            # If regex is invalid, fall back to exact match
            return hostname == pattern

    def get_username_for_host(self, hostname: str) -> Optional[str]:
        """Get the configured username for a host.

        Args:
            hostname: Hostname or IP address

        Returns:
            Username if configured, None otherwise
        """
        config = self.get_config_for_host(hostname)
        return config.get('user')

    def get_preferred_usernames(self, hostname: str) -> List[str]:
        """Get list of preferred usernames for a host, in priority order.

        Args:
            hostname: Hostname or IP address

        Returns:
            List of usernames to try, in order of preference
        """
        usernames: List[str] = []

        # 1. SSH config file username (highest priority)
        ssh_username = self.get_username_for_host(hostname)
        if ssh_username:
            usernames.append(ssh_username)

        # 2. Current system user
        current_user = os.getenv('USER') or os.getenv('USERNAME')
        if current_user and current_user not in usernames:
            usernames.append(current_user)

        # 3. Common infrastructure usernames
        common_usernames = ['ubuntu', 'jenkins', 'centos', 'admin', 'ec2-user', 'root']
        for username in common_usernames:
            if username not in usernames:
                usernames.append(username)

        return usernames

    def get_host_config_summary(self, hostname: str) -> Dict[str, Any]:
        """Get a summary of SSH configuration for a host.

        Args:
            hostname: Hostname or IP address

        Returns:
            Dictionary with configuration summary
        """
        config = self.get_config_for_host(hostname)
        usernames = self.get_preferred_usernames(hostname)

        return {
            'hostname': hostname,
            'username': config.get('user'),
            'port': config.get('port', '22'),
            'preferred_usernames': usernames,
            'identity_files': [f for f in config.get('identityfile', '').split() if f],
            'proxy_command': config.get('proxycommand'),
            'config_found': bool(config)
        }
