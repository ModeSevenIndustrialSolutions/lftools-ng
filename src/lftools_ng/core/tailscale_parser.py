# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tailscale VPN parser for server discovery."""

from __future__ import annotations

import json
import logging
import platform
import re
import subprocess
from typing import Any, Dict, List, Optional

from lftools_ng.core.models import Server, ServerLocation, ServerType

logger = logging.getLogger(__name__)


class TailscaleParser:
    """Parser for Tailscale VPN server information."""

    def __init__(self) -> None:
        """Initialize the Tailscale parser."""
        self.tailscale_command = self._get_tailscale_command()

    def _get_tailscale_command(self) -> str:
        """Get the appropriate Tailscale command for the current platform.

        Returns:
            Path to Tailscale command.
        """
        system = platform.system().lower()

        if system == "darwin":  # macOS
            return "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
        elif system == "linux":
            # Try common locations
            possible_paths = [
                "/usr/bin/tailscale",
                "/usr/local/bin/tailscale",
                "/opt/tailscale/bin/tailscale"
            ]

            for path in possible_paths:
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        return path
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    continue

            # Default to system PATH
            return "tailscale"
        else:
            # For other platforms, assume it's in PATH
            return "tailscale"

    def get_tailscale_status(self) -> Dict[str, Any]:
        """Get Tailscale status information.

        Returns:
            Dictionary containing Tailscale status information.

        Raises:
            subprocess.SubprocessError: If Tailscale command fails.
        """
        try:
            result = subprocess.run(
                [self.tailscale_command, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(f"Tailscale status command failed: {result.stderr}")
                return {}

            status_data = json.loads(result.stdout)
            if not isinstance(status_data, dict):
                logger.warning("Tailscale status command returned non-dict data")
                return {}
            return status_data

        except subprocess.TimeoutExpired:
            logger.warning("Tailscale status command timed out")
            return {}
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Tailscale status JSON: {e}")
            return {}
        except FileNotFoundError:
            logger.warning("Tailscale command not found")
            return {}

    def get_tailscale_status_text(self) -> str:
        """Get Tailscale status information in text format.

        Returns:
            String containing Tailscale status output.
        """
        try:
            result = subprocess.run(
                [self.tailscale_command, "status"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.warning(f"Tailscale status command failed: {result.stderr}")
                return ""

            return result.stdout

        except subprocess.TimeoutExpired:
            logger.warning("Tailscale status command timed out")
            return ""
        except FileNotFoundError:
            logger.warning("Tailscale command not found")
            return ""

    def parse_vpn_servers(self, status_data: Optional[Dict[str, Any]] = None) -> List[Server]:
        """Parse VPN servers from Tailscale status.

        Args:
            status_data: Optional pre-fetched status data. If None, will fetch from Tailscale.

        Returns:
            List of Server objects representing VPN-accessible servers.
        """
        if status_data is None:
            status_data = self.get_tailscale_status()

        if not status_data:
            return []

        servers = []
        peers = status_data.get("Peer", {})

        for _, peer_info in peers.items():
            server = self._parse_peer_to_server(peer_info)
            if server:
                servers.append(server)

        return servers

    def _parse_peer_to_server(self, peer_info: Dict[str, Any]) -> Optional[Server]:
        """Parse a Tailscale peer into a Server object.

        Args:
            peer_info: Peer information dictionary.

        Returns:
            Server object or None if not a relevant server.
        """
        hostname = peer_info.get("HostName", "")
        if not hostname:
            return None

        # Skip non-server hosts (e.g., personal devices)
        if not self._is_infrastructure_server(hostname):
            return None

        # Extract server type from hostname
        server_type = self._determine_server_type_from_hostname(hostname)
        if not server_type:
            return None

        # Get VPN IP address
        tailscale_ips = peer_info.get("TailscaleIPs", [])
        vpn_address = tailscale_ips[0] if tailscale_ips else None

        # Determine location from hostname
        location = self._determine_location_from_hostname(hostname)

        # Construct server URL (this is a best guess)
        server_url = self._construct_server_url(hostname, server_type)

        # Determine project association from hostname
        project_names = self._extract_project_from_hostname(hostname)

        # For Jenkins servers, determine if production or sandbox
        is_production = True
        if server_type == ServerType.JENKINS:
            is_production = self._determine_jenkins_production_status(hostname)

        return Server(
            name=hostname,
            url=server_url,
            server_type=server_type,
            vpn_address=vpn_address,
            location=location,
            projects=project_names,
            is_production=is_production
        )

    def _is_infrastructure_server(self, hostname: str) -> bool:
        """Determine if a hostname represents infrastructure server.

        Args:
            hostname: Server hostname.

        Returns:
            True if this appears to be an infrastructure server.
        """
        hostname_lower = hostname.lower()

        # Known infrastructure patterns
        infrastructure_patterns = [
            "jenkins",
            "gerrit",
            "nexus",
            "sonar",
            "build",
            "ci",
            "git",
            "repo",
            "artifact"
        ]

        # Known Linux Foundation domains/patterns
        lf_patterns = [
            ".linuxfoundation.org",
            ".opendaylight.org",
            ".onap.org",
            ".akraino.org",
            ".edgexfoundry.org",
            ".fd.io",
            ".o-ran-sc.org",
            ".anuket.io",
            ".opnfv.org"
        ]

        # Check for infrastructure patterns
        for pattern in infrastructure_patterns:
            if pattern in hostname_lower:
                return True

        # Check for Linux Foundation domains
        for pattern in lf_patterns:
            if pattern in hostname_lower:
                return True

        return False

    def _determine_server_type_from_hostname(self, hostname: str) -> Optional[ServerType]:
        """Determine server type from hostname.

        Args:
            hostname: Server hostname.

        Returns:
            ServerType enum value or None.
        """
        hostname_lower = hostname.lower()

        if "jenkins" in hostname_lower:
            return ServerType.JENKINS
        elif "gerrit" in hostname_lower:
            return ServerType.GERRIT
        elif "nexusiq" in hostname_lower or "nexus-iq" in hostname_lower:
            return ServerType.NEXUS_IQ
        elif "nexus3" in hostname_lower:
            return ServerType.NEXUS3
        elif "nexus" in hostname_lower:
            # Determine if this is Nexus 2 or 3 based on instance number
            return self._determine_nexus_version_from_hostname(hostname_lower)
        elif "sonar" in hostname_lower:
            return ServerType.SONAR
        elif "artifactory" in hostname_lower:
            return ServerType.ARTIFACTORY
        elif "gitlab" in hostname_lower:
            return ServerType.GITLAB
        elif "logs" in hostname_lower:
            return ServerType.LOGS
        else:
            # Default to treating unknown infrastructure as Jenkins
            return ServerType.JENKINS

    def _determine_location_from_hostname(self, hostname: str) -> ServerLocation:
        """Determine server hosting location from hostname.

        Args:
            hostname: Server hostname.

        Returns:
            ServerLocation enum value.
        """
        hostname_lower = hostname.lower()

        if "vexxhost" in hostname_lower or "vex" in hostname_lower:
            return ServerLocation.VEXXHOST
        elif "aws" in hostname_lower or "amazonaws" in hostname_lower:
            return ServerLocation.AWS
        elif "gce" in hostname_lower or "gcp" in hostname_lower or "googlecloud" in hostname_lower:
            return ServerLocation.GCE
        elif "korg" in hostname_lower or "kernel.org" in hostname_lower:
            return ServerLocation.KORG
        else:
            return ServerLocation.OTHER

    def _construct_server_url(self, hostname: str, server_type: ServerType) -> str:
        """Construct likely server URL from hostname and type.

        Args:
            hostname: Server hostname.
            server_type: Type of server.

        Returns:
            Constructed URL or empty string for internal-only servers.
        """
        # If hostname already contains a domain, it might be a public server
        if "." in hostname:
            # Check if this looks like a public domain
            hostname_lower = hostname.lower()
            public_domains = [
                ".org", ".com", ".net", ".io", ".dev"
            ]

            # If it has a public domain, construct URL
            if any(domain in hostname_lower for domain in public_domains):
                return f"https://{hostname}/"

        # For internal hostnames (like vex-yul-rot-jenkins-2), don't construct public URLs
        # These are VPN-only internal servers and should not have public URLs

        # Only construct public URLs for certain patterns that are known to be public
        hostname_lower = hostname.lower()

        # Known public service patterns - these actually have public endpoints
        public_service_patterns = [
            "jenkins.onap.org",
            "jenkins.akraino.org",
            "jenkins.opendaylight.org",
            "jenkins.edgexfoundry.org",
            "jenkins.opencord.org",
            "jenkins.o-ran-sc.org",
            "jenkins.fd.io",
            "gerrit.onap.org",
            "gerrit.akraino.org",
            "gerrit.opendaylight.org",
            "gerrit.edgexfoundry.org",
            "gerrit.opencord.org",
            "gerrit.o-ran-sc.org",
            "gerrit.fd.io",
            "nexus.onap.org",
            "nexus.akraino.org",
            "nexus.opendaylight.org",
            "nexus.edgexfoundry.org",
            "nexus.o-ran-sc.org"
        ]

        # Check if this matches a known public service
        for pattern in public_service_patterns:
            if pattern in hostname_lower:
                return f"https://{pattern}/"

        # For all other internal servers, return empty URL
        # This prevents internal VPN hostnames from getting fake public URLs
        # Note: server_type is kept for potential future use in URL construction logic
        return ""

    def parse_status_text_to_servers(self, status_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse Tailscale status text output to extract server information.

        Args:
            status_text: Optional status text. If None, will fetch from Tailscale.

        Returns:
            List of server dictionaries with name and vpn_address.
        """
        if status_text is None:
            status_text = self.get_tailscale_status_text()

        if not status_text:
            return []

        servers = []
        lines = status_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse lines like: "100.127.96.13   matts-macbook-air    mwatkins@    macOS   -"
            parts = line.split()
            if len(parts) < 2:
                continue

            ip_address = parts[0]
            hostname = parts[1]

            # Skip if this doesn't look like an IP address
            if not self._is_valid_ip(ip_address):
                continue

            # Skip if hostname doesn't look like infrastructure
            if not self._is_infrastructure_server(hostname):
                continue

            servers.append({
                "name": hostname,
                "vpn_address": ip_address,
                "status": " ".join(parts[2:]) if len(parts) > 2 else "online"
            })

        logger.info(f"Parsed {len(servers)} infrastructure servers from Tailscale status text")
        return servers

    def _is_valid_ip(self, ip_string: str) -> bool:
        """Check if a string is a valid IP address.

        Args:
            ip_string: String to check

        Returns:
            True if valid IP address
        """
        try:
            import ipaddress
            ipaddress.ip_address(ip_string)
            return True
        except ValueError:
            return False

    def get_available_servers(self) -> List[Dict[str, Any]]:
        """Get list of available servers in dictionary format.

        Returns:
            List of server dictionaries.
        """
        # Try JSON format first
        try:
            servers = self.parse_vpn_servers()
            if servers:
                return [server.to_dict() for server in servers]
        except Exception as e:
            logger.debug(f"JSON parsing failed, trying text format: {e}")

        # Fall back to text format parsing
        try:
            return self.parse_status_text_to_servers()
        except Exception as e:
            logger.warning(f"Both JSON and text parsing failed: {e}")
            return []

    def _extract_project_from_hostname(self, hostname: str) -> List[str]:
        """Extract project name(s) from hostname using fuzzy matching.

        Args:
            hostname: Server hostname.

        Returns:
            List of project names that match the hostname.
        """
        from lftools_ng.core.project_matcher import get_project_matcher

        hostname_lower = hostname.lower()
        project_names = []

        # Extract potential project indicators from hostname
        # Split on both dots and dashes/underscores to get all parts
        hostname_base = hostname_lower.split('.')[0]  # Get the part before domain
        hostname_parts = hostname_base.replace('-', ' ').replace('_', ' ').split()

        matcher = get_project_matcher()

        # Infrastructure terms that should be skipped when alone
        skip_terms = {
            'jenkins', 'gerrit', 'nexus', 'nexus3', 'nexus2', 'sonar', 'build', 'prod', 'production', 'sandbox',
            'vex', 'aws', 'gce', 'yul', 'sjc', 'us', 'west', 'east', 'north', 'south',
            'server', 'host', 'gitolite', 'cregit', 'social', 'jira', 'wfx', 'rhel9', 'ap', 'southeast',
            '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
        }

        # Try to match multi-word combinations first (more specific)
        for i in range(len(hostname_parts)):
            for j in range(i + 2, min(i + 4, len(hostname_parts) + 1)):  # Try 2-3 word combinations
                combined = ' '.join(hostname_parts[i:j])
                if all(part not in skip_terms for part in hostname_parts[i:j]):  # Only if no part is a skip term
                    primary_name = matcher.get_primary_name(combined)
                    if primary_name:
                        project_names.append(primary_name)

        # Try individual parts (but include some multi-part project names)
        for i, part in enumerate(hostname_parts):
            # Skip pure infrastructure terms and location codes
            if part in skip_terms:
                continue

            # Special handling for common compound project names
            if part == 'jenkinsci' or (part == 'jenkins' and i + 1 < len(hostname_parts) and hostname_parts[i + 1] == 'ci'):
                primary_name = matcher.get_primary_name('jenkins ci')
                if primary_name:
                    project_names.append(primary_name)
                continue

            # Try exact project matching
            primary_name = matcher.get_primary_name(part)
            if primary_name:
                project_names.append(primary_name)

        # If no matches found, try less strict matching on original hostname
        if not project_names:
            # Try the whole hostname base as one term
            primary_name = matcher.get_primary_name(hostname_base)
            if primary_name:
                project_names.append(primary_name)

        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name in project_names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)

        return unique_names

    def _determine_nexus_version_from_hostname(self, hostname: str) -> ServerType:
        """Determine Nexus version from hostname based on instance numbers.

        Logic:
        - If only one nexus instance exists for a project, assume Nexus 3 (modern)
        - If multiple instances exist, lower numbers are Nexus 2, higher are Nexus 3

        Args:
            hostname: Server hostname (lowercased).

        Returns:
            ServerType.NEXUS (for Nexus 2) or ServerType.NEXUS3 (for Nexus 3).
        """
        # Extract instance number from hostname
        # Look for patterns like nexus-1, nexus-2, nexus1, nexus2, etc.
        number_match = re.search(r'nexus-?(\d+)', hostname)

        if number_match:
            instance_number = int(number_match.group(1))
            # Lower instance numbers (1, 2) are typically Nexus 2
            # Higher instance numbers (3, 4+) are typically Nexus 3
            if instance_number <= 2:
                return ServerType.NEXUS  # Nexus 2
            else:
                return ServerType.NEXUS3  # Nexus 3
        else:
            # No number found, assume modern Nexus 3
            return ServerType.NEXUS3

    def _determine_jenkins_production_status(self, hostname: str) -> bool:
        """Determine if a Jenkins server is production or sandbox.

        Logic:
        - Explicit 'prod' or 'production' in name -> production
        - Explicit 'sandbox' in name -> sandbox
        - Lower instance numbers (1, 2) -> production
        - Higher instance numbers (3+) -> sandbox
        - Default: production

        Args:
            hostname: Server hostname.

        Returns:
            True if production, False if sandbox.
        """
        hostname_lower = hostname.lower()

        # Explicit indicators
        if any(x in hostname_lower for x in ['prod', 'production']):
            return True
        if 'sandbox' in hostname_lower:
            return False

        # Extract instance number
        number_match = re.search(r'jenkins-?(\d+)', hostname_lower)

        if number_match:
            instance_number = int(number_match.group(1))
            # Lower numbers are typically production
            return instance_number <= 2

        # Default to production
        return True

    def _extract_location_info(self, hostname: str) -> Dict[str, Optional[str]]:
        """Extract hosting provider and region information from hostname.

        Args:
            hostname: Server hostname.

        Returns:
            Dictionary with 'provider' and 'region' keys.
        """
        hostname_lower = hostname.lower()
        provider = None
        region = None

        # Extract provider from hostname prefixes
        if hostname_lower.startswith('vex-'):
            provider = 'VEXXHOST'
            # Extract region (e.g., yul from vex-yul-*)
            parts = hostname_lower.split('-')
            if len(parts) >= 2:
                region = parts[1].upper()
        elif hostname_lower.startswith('aws-'):
            provider = 'AWS'
            # Extract region (e.g., us-west-2 from aws-us-west-2-*)
            parts = hostname_lower.split('-')
            if len(parts) >= 4:
                region = f"{parts[1]}-{parts[2]}-{parts[3]}".upper()
        elif hostname_lower.startswith('gce-'):
            provider = 'GCE'
            # GCE regions might follow different patterns
            parts = hostname_lower.split('-')
            if len(parts) >= 2:
                region = parts[1].upper()
        elif hostname_lower.startswith('pac-'):
            provider = 'PACKET'  # Now Equinix Metal
            parts = hostname_lower.split('-')
            if len(parts) >= 2:
                region = parts[1].upper()
        elif hostname_lower.startswith('lin-'):
            provider = 'LINODE'
            parts = hostname_lower.split('-')
            if len(parts) >= 2:
                region = parts[1].upper()
        elif hostname_lower.startswith('ser-'):
            provider = 'SERVARICA'
            parts = hostname_lower.split('-')
            if len(parts) >= 2:
                region = parts[1].upper()
        elif 'korg' in hostname_lower or 'kernel.org' in hostname_lower:
            provider = 'KERNEL.ORG'

        return {'provider': provider, 'region': region}
