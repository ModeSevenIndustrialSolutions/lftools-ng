# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Jenkins configuration management for reading jenkins_jobs.ini files.

This module provides utilities for reading and parsing jenkins_jobs.ini files
from standard locations and custom paths.
"""

import configparser
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class JenkinsConfig:
    """Configuration for a Jenkins server."""
    url: str
    user: str
    password: str
    section_name: str


class JenkinsConfigReader:
    """Read and parse jenkins_jobs.ini configuration files."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_standard_config_paths(self) -> List[Path]:
        """Get standard paths where jenkins_jobs.ini files are typically located."""
        paths: List[Path] = []

        # Current working directory
        cwd_path = Path.cwd() / "jenkins_jobs.ini"
        if cwd_path.exists():
            paths.append(cwd_path)

        # User's .config directory
        config_path = Path.home() / ".config" / "jenkins_jobs" / "jenkins_jobs.ini"
        if config_path.exists():
            paths.append(config_path)

        return paths

    def read_config_file(self, config_path: Path) -> Optional[configparser.ConfigParser]:
        """Read and parse a jenkins_jobs.ini configuration file."""
        try:
            config = configparser.ConfigParser()
            config.read(config_path)
            self.logger.debug(f"Successfully read Jenkins config from {config_path}")
            return config
        except Exception as e:
            self.logger.error(f"Failed to read Jenkins config from {config_path}: {e}")
            return None

    def get_jenkins_configs(self, config_path: Optional[Path] = None) -> Dict[str, JenkinsConfig]:
        """
        Get all Jenkins configurations from config file.

        Args:
            config_path: Optional path to specific config file. If None, searches standard locations.

        Returns:
            Dictionary mapping section names to JenkinsConfig objects.
        """
        configs: Dict[str, JenkinsConfig] = {}

        if config_path:
            # Use specific config file
            if not config_path.exists():
                self.logger.error(f"Specified config file does not exist: {config_path}")
                return configs

            config = self.read_config_file(config_path)
            if config:
                configs.update(self._parse_config(config))
        else:
            # Search standard locations
            standard_paths = self.get_standard_config_paths()
            for path in standard_paths:
                config = self.read_config_file(path)
                if config:
                    configs.update(self._parse_config(config))
                    self.logger.info(f"Loaded Jenkins configurations from {path}")
                    break  # Use first found config file

        return configs

    def _parse_config(self, config: configparser.ConfigParser) -> Dict[str, JenkinsConfig]:
        """Parse ConfigParser object into JenkinsConfig objects."""
        configs: Dict[str, JenkinsConfig] = {}

        for section_name in config.sections():
            # Skip the job_builder section which contains general settings
            if section_name == "job_builder":
                continue

            section = config[section_name]

            # Validate required fields
            required_fields = ["url", "user", "password"]
            missing_fields = [field for field in required_fields if field not in section]

            if missing_fields:
                self.logger.warning(
                    f"Section '{section_name}' is missing required fields: {missing_fields}"
                )
                continue

            try:
                jenkins_config = JenkinsConfig(
                    url=section["url"],
                    user=section["user"],
                    password=section["password"],
                    section_name=section_name
                )
                configs[section_name] = jenkins_config
                self.logger.debug(f"Loaded Jenkins config for '{section_name}': {jenkins_config.url}")
            except Exception as e:
                self.logger.error(f"Failed to parse config for section '{section_name}': {e}")

        return configs

    def get_config_by_url(self, url: str, config_path: Optional[Path] = None) -> Optional[JenkinsConfig]:
        """
        Get Jenkins configuration by URL.

        Args:
            url: Jenkins server URL to match.
            config_path: Optional path to specific config file.

        Returns:
            JenkinsConfig object if found, None otherwise.
        """
        configs = self.get_jenkins_configs(config_path)

        # Normalize the input URL for comparison
        normalized_url = url.rstrip('/').lower()

        for config in configs.values():
            # Normalize config URL for comparison
            config_normalized = config.url.rstrip('/').lower()

            # Try exact match first
            if config_normalized == normalized_url:
                return config

            # Try matching base domain (for cases like jenkins.example.org vs jenkins.example.org/subpath)
            if normalized_url in config_normalized or config_normalized in normalized_url:
                # Make sure it's a reasonable match (not just random substring)
                if config_normalized.startswith(normalized_url) or normalized_url.startswith(config_normalized):
                    return config

        return None

    def list_available_servers(self, config_path: Optional[Path] = None) -> List[Tuple[str, str]]:
        """
        List available Jenkins servers from config.

        Args:
            config_path: Optional path to specific config file.

        Returns:
            List of tuples (section_name, url).
        """
        configs = self.get_jenkins_configs(config_path)
        return [(config.section_name, config.url) for config in configs.values()]


def get_jenkins_credentials(
    server_url: Optional[str] = None,
    config_path: Optional[Path] = None
) -> Optional[JenkinsConfig]:
    """
    Convenience function to get Jenkins credentials.

    Args:
        server_url: Optional Jenkins server URL to match.
        config_path: Optional path to specific config file.

    Returns:
        JenkinsConfig object if found, None otherwise.
    """
    reader = JenkinsConfigReader()

    if server_url:
        return reader.get_config_by_url(server_url, config_path)
    else:
        # Return first available config
        configs = reader.get_jenkins_configs(config_path)
        if configs:
            return next(iter(configs.values()))
        return None
