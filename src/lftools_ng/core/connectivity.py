# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Server connectivity testing utilities for lftools-ng."""

import logging
import socket
import subprocess
from typing import Any, Dict, Optional, Tuple

import httpx

from lftools_ng.core.ssh_config_parser import SSHConfigParser

logger = logging.getLogger(__name__)

# Result constants for consistent formatting
RESULT_SUCCESS = "[green]✓[/green]"
RESULT_FAILURE = "[red]✗[/red]"
RESULT_TIMEOUT = "[yellow]⏱[/yellow]"
RESULT_WARNING = "[yellow]⚠[/yellow]"
RESULT_CLOUDFLARE_CDN = "[yellow]☁[/yellow]"
RESULT_NA = "[dim]N/A[/dim]"


class ConnectivityTester:
    """Test connectivity to servers using various methods."""

    def __init__(self, timeout: int = 3) -> None:
        """Initialize connectivity tester.

        Args:
            timeout: Timeout in seconds for all tests
        """
        self.timeout = timeout
        self._last_ssh_details: Dict[str, Any] = {}
        self._ssh_config = SSHConfigParser()

    def test_url(self, url: str) -> str:
        """Test HTTP/HTTPS URL accessibility.

        Args:
            url: URL to test

        Returns:
            Color-coded result string
        """
        if not url:
            return RESULT_NA

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.head(url, follow_redirects=True)
                if response.status_code < 400:
                    return RESULT_SUCCESS
                elif response.status_code == 403:
                    # Check if this is a Cloudflare CDN blocking bot-like requests
                    if self._is_cloudflare_cdn_blocking(url):
                        return RESULT_CLOUDFLARE_CDN
                    else:
                        return f"[red]✗ ({response.status_code})[/red]"
                else:
                    return f"[red]✗ ({response.status_code})[/red]"
        except httpx.TimeoutException:
            return RESULT_TIMEOUT
        except (httpx.RequestError, httpx.HTTPStatusError):
            return RESULT_FAILURE
        except Exception as e:
            logger.debug(f"Unexpected error testing URL {url}: {e}")
            return RESULT_FAILURE

    def test_ssh_port(self, host: str, port: int = 22) -> str:
        """Test SSH port connectivity using socket.

        Args:
            host: Hostname or IP address
            port: Port number (default: 22)

        Returns:
            Color-coded result string
        """
        if not host:
            return RESULT_NA

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return RESULT_SUCCESS
            else:
                return RESULT_FAILURE
        except socket.timeout:
            return RESULT_TIMEOUT
        except Exception as e:
            logger.debug(f"Unexpected error testing SSH port {host}:{port}: {e}")
            return RESULT_FAILURE

    def test_ssh_shell(self, host: str, port: int = 22, username: Optional[str] = None, verbose: bool = False) -> str:
        """Test SSH shell access using local SSH configuration and authentication methods.

        This test uses the local system's SSH configuration, including:
        - SSH agent authentication
        - SSH keys from ~/.ssh/
        - Hardware tokens (YubiKey, etc.)
        - Secure enclave keys (Secretive, etc.)
        - SSH config file settings

        Args:
            host: Hostname or IP address
            port: Port number (default: 22)
            username: Username for SSH connection (if None, tries common usernames)
            verbose: If True, store detailed results for later retrieval

        Returns:
            Color-coded result string
        """
        if not host:
            return RESULT_NA

        # Store detailed results if verbose mode is requested
        self._last_ssh_details = {
            "host": host,
            "port": port,
            "attempted_usernames": [],
            "successful_username": None,
            "errors": [],
            "auth_methods_tried": [],
            "ssh_config_used": False
        }

        # Get preferred usernames from SSH config and system
        if username:
            usernames_to_try = [username]
        else:
            usernames_to_try = self._ssh_config.get_preferred_usernames(host)

        if verbose:
            ssh_config_summary = self._ssh_config.get_host_config_summary(host)
            self._last_ssh_details["ssh_config_used"] = ssh_config_summary["config_found"]
            self._last_ssh_details["ssh_config_summary"] = ssh_config_summary

        for test_username in usernames_to_try:
            if verbose:
                self._last_ssh_details["attempted_usernames"].append(test_username)

            result, details = self._test_ssh_with_username(host, port, test_username, verbose)

            if verbose and details:
                if "error" in details:
                    self._last_ssh_details["errors"].append(f"{test_username}: {details['error']}")
                if "auth_methods" in details:
                    self._last_ssh_details["auth_methods_tried"].extend(details["auth_methods"])

            if result == RESULT_SUCCESS:
                if verbose:
                    self._last_ssh_details["successful_username"] = test_username
                return result
            elif result != RESULT_FAILURE:
                # If we get warning (auth issue), return immediately
                # Only continue trying usernames if we get complete failure
                return result

        # If all usernames failed, return failure
        return RESULT_FAILURE

    def _test_ssh_with_username(self, host: str, port: int, username: str, verbose: bool = False) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Test SSH connection with a specific username.

        Args:
            host: Hostname or IP address
            port: Port number
            username: Username to test
            verbose: Whether to collect detailed information

        Returns:
            Tuple of (color-coded result string, optional details dict)
        """
        details: Optional[Dict[str, Any]] = None
        if verbose:
            details = {
                "username": username,
                "auth_methods": [],
                "error": None
            }

        try:
            # Build SSH command that respects local configuration
            cmd = [
                "ssh",
                "-o", f"ConnectTimeout={self.timeout}",
                "-o", "BatchMode=yes",  # Don't prompt for passwords, but allow other auth
                "-o", "StrictHostKeyChecking=no",  # Skip host key verification for testing
                "-o", "UserKnownHostsFile=/dev/null",  # Don't save host keys
                "-o", "LogLevel=ERROR",  # Reduce noise in logs
                "-p", str(port),
                f"{username}@{host}",
                self._get_test_command()
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout + 2,  # Add buffer for subprocess overhead
                check=False,
                text=True
            )

            # Analyze the result
            ssh_result = self._analyze_ssh_result(result, host, username)

            if verbose and details:
                details["error"] = result.stderr.strip() if result.stderr else None
                if result.stderr:
                    # Try to extract authentication methods from stderr
                    if "publickey" in result.stderr:
                        details["auth_methods"].append("publickey")
                    if "password" in result.stderr:
                        details["auth_methods"].append("password")
                    if "keyboard-interactive" in result.stderr:
                        details["auth_methods"].append("keyboard-interactive")

            return ssh_result, details

        except subprocess.TimeoutExpired:
            if verbose and details:
                details["error"] = "Connection timeout"
            return RESULT_TIMEOUT, details
        except Exception as e:
            logger.debug(f"Unexpected error testing SSH shell {username}@{host}: {e}")
            if verbose and details:
                details["error"] = str(e)
            return RESULT_FAILURE, details

    def _get_test_command(self) -> str:
        """Get a safe test command that should be available on most Unix systems.

        Returns:
            Command string to execute on remote system
        """
        # Use a more robust compound command that tries multiple safe options
        # This maximizes chances of success across different systems (Linux, BSD, etc.)
        return "command -v echo >/dev/null 2>&1 && echo 'SSH_OK' || printf 'SSH_OK\\n' || /bin/echo 'SSH_OK' || test -f /bin/sh && echo 'SSH_OK'"

    def _analyze_ssh_result(self, result: subprocess.CompletedProcess[str], host: str, username: str) -> str:
        """Analyze SSH command result and return appropriate status.

        Args:
            result: Completed subprocess result
            host: Host that was tested
            username: Username that was tested

        Returns:
            Color-coded result string
        """
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""

        # Success: Command executed and returned expected output
        if result.returncode == 0 and "SSH_OK" in stdout:
            logger.debug(f"SSH shell test successful for {username}@{host}")
            return RESULT_SUCCESS

        # Connection refused or network unreachable
        if result.returncode == 255:
            if "Connection refused" in stderr or "No route to host" in stderr:
                logger.debug(f"SSH connection failed for {username}@{host}: {stderr}")
                return RESULT_FAILURE
            elif "Connection timed out" in stderr:
                return RESULT_TIMEOUT

        # Authentication-related issues (SSH is working but auth failed)
        auth_indicators = [
            "Permission denied",
            "Authentication failed",
            "publickey",
            "password",
            "keyboard-interactive"
        ]

        if any(indicator in stderr.lower() for indicator in auth_indicators):
            logger.debug(f"SSH authentication failed for {username}@{host}, but SSH service is responding")
            return RESULT_WARNING

        # Other SSH protocol errors (server reachable but SSH issues)
        ssh_errors = [
            "Protocol mismatch",
            "Remote protocol version",
            "SSH_DISCONNECT",
            "Bad protocol version"
        ]

        if any(error in stderr for error in ssh_errors):
            logger.debug(f"SSH protocol error for {username}@{host}: {stderr}")
            return RESULT_WARNING

        # Unexpected success (command ran but didn't output expected result)
        if result.returncode == 0:
            logger.debug(f"SSH command succeeded for {username}@{host} but unexpected output: {stdout}")
            return RESULT_SUCCESS

        # Default to failure for other cases
        logger.debug(f"SSH test failed for {username}@{host}: returncode={result.returncode}, stderr={stderr}")
        return RESULT_FAILURE

    def get_last_ssh_details(self) -> Dict[str, Any]:
        """Get detailed information about the last SSH test.

        Returns:
            Dictionary with SSH test details
        """
        return self._last_ssh_details.copy()

    def test_all(self, server: Dict[str, Any], username: Optional[str] = None, verbose: bool = False) -> Dict[str, str]:
        """Test all connectivity types for a server.

        Args:
            server: Server dictionary with url, vpn_address, etc.
            username: Username for SSH connection
            verbose: Whether to collect detailed information

        Returns:
            Dictionary with test results
        """
        results: Dict[str, str] = {}

        # Test URL
        url = server.get("url", "")
        results["url"] = self.test_url(url)

        # Test SSH port
        vpn_address = server.get("vpn_address", "")
        results["ssh_port"] = self.test_ssh_port(vpn_address)

        # Test SSH shell
        results["ssh_shell"] = self.test_ssh_shell(vpn_address, username=username, verbose=verbose)

        return results

    def _is_cloudflare_cdn_blocking(self, url: str) -> bool:
        """Check if a 403 error is caused by Cloudflare CDN blocking bot-like requests.

        Args:
            url: The URL that returned a 403 error

        Returns:
            True if the URL is behind Cloudflare CDN, False otherwise
        """
        try:
            from urllib.parse import urlparse
            import socket

            # Extract hostname from URL
            parsed_url = urlparse(url)
            hostname = parsed_url.netloc

            if not hostname:
                return False

            # Perform DNS lookup to get IP address
            try:
                ip_address = socket.gethostbyname(hostname)
            except socket.gaierror:
                logger.debug(f"Could not resolve hostname {hostname}")
                return False

            # Check if the IP address belongs to Cloudflare's IP ranges
            return self._is_cloudflare_ip(ip_address)

        except Exception as e:
            logger.debug(f"Error checking Cloudflare CDN for {url}: {e}")
            return False

    def _is_cloudflare_ip(self, ip_address: str) -> bool:
        """Check if an IP address belongs to Cloudflare's known IP ranges.

        Args:
            ip_address: The IP address to check

        Returns:
            True if the IP belongs to Cloudflare, False otherwise
        """
        try:
            import ipaddress

            # Cloudflare's known IP ranges (IPv4)
            # These are the main Cloudflare IP ranges as of 2025
            cloudflare_ranges = [
                "173.245.48.0/20",
                "103.21.244.0/22",
                "103.22.200.0/22",
                "103.31.4.0/22",
                "141.101.64.0/18",
                "108.162.192.0/18",
                "190.93.240.0/20",
                "188.114.96.0/20",
                "197.234.240.0/22",
                "198.41.128.0/17",
                "162.158.0.0/15",
                "104.16.0.0/13",
                "104.24.0.0/14",
                "172.64.0.0/13",
                "131.0.72.0/22"
            ]

            ip = ipaddress.ip_address(ip_address)

            for range_str in cloudflare_ranges:
                network = ipaddress.ip_network(range_str)
                if ip in network:
                    logger.debug(f"IP {ip_address} matches Cloudflare range {range_str}")
                    return True

            return False

        except Exception as e:
            logger.debug(f"Error checking if IP {ip_address} is Cloudflare: {e}")
            return False
