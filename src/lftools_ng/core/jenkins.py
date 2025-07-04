# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Core Jenkins client implementation for lftools-ng."""

import logging
import re
from typing import Any, Dict, List, Optional

import jenkins
from jenkins import Jenkins as PythonJenkins

logger = logging.getLogger(__name__)


class JenkinsAuthenticationError(Exception):
    """Raised when Jenkins authentication fails."""
    pass


class JenkinsConnectionError(Exception):
    """Raised when Jenkins connection fails for non-auth reasons."""
    pass


def _detect_auth_error(error_message: str) -> bool:
    """Detect if an error message indicates an authentication failure."""
    auth_indicators = [
        "401",
        "unauthorized",
        "authentication failed",
        "invalid credentials",
        "access denied",
        "forbidden",
        "login required"
    ]
    error_lower = error_message.lower()
    return any(indicator in error_lower for indicator in auth_indicators)


def _clean_error_message(error_message: str) -> str:
    """Clean up error messages to remove HTML content and make them more user-friendly."""
    # Remove HTML tags
    clean_msg = re.sub(r'<[^>]+>', '', error_message)
    # Remove excessive whitespace and newlines
    clean_msg = re.sub(r'\s+', ' ', clean_msg).strip()

    # Extract the main error information
    if "401" in clean_msg and "Unauthorized" in clean_msg:
        return "Jenkins server returned 401 Unauthorized - credentials are invalid or missing"
    elif "403" in clean_msg and "Forbidden" in clean_msg:
        return "Jenkins server returned 403 Forbidden - user lacks required permissions"
    elif "404" in clean_msg:
        return "Jenkins server endpoint not found (404) - check server URL"
    elif "Connection" in clean_msg and ("refused" in clean_msg or "timeout" in clean_msg):
        return "Cannot connect to Jenkins server - check server URL and network connectivity"

    # For other errors, truncate if too long but preserve key information
    if len(clean_msg) > 150:
        # Try to find the most important part
        if "Error" in clean_msg:
            # Extract error message up to first occurrence of technical details
            error_part = clean_msg.split("Error")[-1].split("HTTP")[0].split("URI:")[0].strip()
            if error_part and len(error_part) < 100:
                return f"Error{error_part}"
        clean_msg = clean_msg[:150] + "..."

    return clean_msg


class JenkinsClient:
    """Jenkins client for lftools-ng operations."""

    def __init__(
        self,
        server: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 60,
    ) -> None:
        """Initialize Jenkins client.

        Args:
            server: Jenkins server URL
            username: Jenkins username
            password: Jenkins password or API token
            timeout: Request timeout in seconds
        """
        self.server = server
        self.username = username
        self.password = password
        self.timeout = timeout

        # Initialize Jenkins connection
        self.client: PythonJenkins = jenkins.Jenkins(
            server, username=username, password=password, timeout=timeout
        )

        # Verify connection
        try:
            self.client.get_version()
            logger.info(f"Connected to Jenkins server: {server}")
        except Exception as e:
            error_msg = str(e)
            if _detect_auth_error(error_msg):
                clean_msg = _clean_error_message(error_msg)
                raise JenkinsAuthenticationError(f"Authentication failed for {server}: {clean_msg}")
            else:
                clean_msg = _clean_error_message(error_msg)
                raise JenkinsConnectionError(f"Failed to connect to Jenkins server {server}: {clean_msg}")

    def run_groovy_script(self, script: str) -> str:
        """Run a Groovy script on the Jenkins server.

        Args:
            script: Groovy script content to execute

        Returns:
            Script execution result

        Raises:
            Exception: If script execution fails
        """
        try:
            result = self.client.run_script(script)
            logger.debug("Groovy script executed successfully")
            return str(result)
        except Exception as e:
            error_msg = str(e)
            if _detect_auth_error(error_msg):
                clean_msg = _clean_error_message(error_msg)
                raise JenkinsAuthenticationError(f"Authentication failed: {clean_msg}")
            else:
                clean_msg = _clean_error_message(error_msg)
                raise JenkinsConnectionError(f"Failed to execute Groovy script: {clean_msg}")

    def get_credentials(self) -> List[Dict[str, Any]]:
        """Extract all credentials from Jenkins server.

        Returns:
            List of credential dictionaries
        """
        groovy_script = '''
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.common.*
import com.cloudbees.plugins.credentials.domains.*
import com.cloudbees.plugins.credentials.impl.*
import com.cloudbees.jenkins.plugins.sshcredentials.impl.*
import org.jenkinsci.plugins.plaincredentials.impl.*
import hudson.util.Secret
import groovy.json.JsonBuilder

def credentials = []

def creds = com.cloudbees.plugins.credentials.CredentialsProvider.lookupCredentials(
    com.cloudbees.plugins.credentials.common.StandardCredentials.class,
    Jenkins.instance,
    null,
    null
)

for (c in creds) {
    def credMap = [:]
    credMap.id = c.id
    credMap.description = c.description ?: ""

    if (c instanceof UsernamePasswordCredentialsImpl) {
        credMap.type = "username_password"
        credMap.username = c.username
        credMap.password = c.password?.getPlainText()
    } else if (c instanceof BasicSSHUserPrivateKey) {
        credMap.type = "ssh_private_key"
        credMap.username = c.username
        credMap.passphrase = c.passphrase?.getPlainText()
        credMap.private_key = c.privateKey
    } else if (c instanceof StringCredentialsImpl) {
        credMap.type = "secret_text"
        credMap.secret = c.secret?.getPlainText()
    } else if (c instanceof FileCredentialsImpl) {
        credMap.type = "secret_file"
        credMap.filename = c.fileName
    } else {
        credMap.type = c.class.simpleName
    }

    credentials.add(credMap)
}

def json = new JsonBuilder(credentials)
println json.toString()
'''

        try:
            result = self.run_groovy_script(groovy_script)
            import json
            parsed_result: list[dict[str, Any]] = json.loads(result)
            return parsed_result
        except (JenkinsAuthenticationError, JenkinsConnectionError):
            # Re-raise our custom exceptions without modification
            raise
        except Exception as e:
            logger.error(f"Failed to get credentials: {e}")
            # Return fallback result for backward compatibility
            return []

    def get_secrets(self) -> List[Dict[str, Any]]:
        """Extract all secrets from Jenkins server.

        Returns:
            List of secret dictionaries
        """
        groovy_script = '''
import com.cloudbees.plugins.credentials.*
import org.jenkinsci.plugins.plaincredentials.impl.*
import groovy.json.JsonBuilder

def secrets = []

def creds = com.cloudbees.plugins.credentials.CredentialsProvider.lookupCredentials(
    com.cloudbees.plugins.credentials.common.StandardCredentials.class,
    Jenkins.instance,
    null,
    null
)

for (c in creds) {
    if (c instanceof StringCredentialsImpl) {
        def secretMap = [:]
        secretMap.id = c.id
        secretMap.description = c.description ?: ""
        secretMap.type = "secret_text"
        secretMap.secret = c.secret?.getPlainText()
        secrets.add(secretMap)
    }
}

def json = new JsonBuilder(secrets)
println json.toString()
'''

        try:
            result = self.run_groovy_script(groovy_script)
            import json
            parsed_result: list[dict[str, Any]] = json.loads(result)
            return parsed_result
        except Exception as e:
            logger.error(f"Failed to get secrets: {e}")
            return []

    def get_ssh_private_keys(self) -> List[Dict[str, Any]]:
        """Extract all SSH private keys from Jenkins server.

        Returns:
            List of SSH private key dictionaries
        """
        groovy_script = '''
import com.cloudbees.plugins.credentials.*
import com.cloudbees.jenkins.plugins.sshcredentials.impl.*
import groovy.json.JsonBuilder

def keys = []

def creds = com.cloudbees.plugins.credentials.CredentialsProvider.lookupCredentials(
    com.cloudbees.plugins.credentials.Credentials.class,
    Jenkins.instance,
    null,
    null
)

for (c in creds) {
    if (c instanceof BasicSSHUserPrivateKey) {
        def keyMap = [:]
        keyMap.id = c.id
        keyMap.description = c.description ?: ""
        keyMap.type = "ssh_private_key"
        keyMap.username = c.username
        keyMap.passphrase = c.passphrase?.getPlainText()
        keyMap.private_key = c.privateKey
        keys.add(keyMap)
    }
}

def json = new JsonBuilder(keys)
println json.toString()
'''

        try:
            result = self.run_groovy_script(groovy_script)
            import json
            parsed_result: list[dict[str, Any]] = json.loads(result)
            return parsed_result
        except Exception as e:
            logger.error(f"Failed to get SSH private keys: {e}")
            return []

    def get_version(self) -> str:
        """Get Jenkins server version.

        Returns:
            Jenkins version string
        """
        try:
            version = self.client.get_version()
            return str(version)
        except Exception as e:
            error_msg = str(e)
            if _detect_auth_error(error_msg):
                clean_msg = _clean_error_message(error_msg)
                raise JenkinsAuthenticationError(f"Authentication failed: {clean_msg}")
            else:
                clean_msg = _clean_error_message(error_msg)
                raise JenkinsConnectionError(f"Failed to get Jenkins version: {clean_msg}")

    def get_info(self) -> Dict[str, Any]:
        """Get Jenkins server information.

        Returns:
            Server information dictionary
        """
        try:
            info = self.client.get_info()
            return dict(info)
        except Exception as e:
            logger.error(f"Failed to get Jenkins info: {e}")
            raise
