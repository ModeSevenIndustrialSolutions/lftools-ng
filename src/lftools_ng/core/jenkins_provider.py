# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Jenkins credential provider implementation.

This module implements the CredentialProvider interface for Jenkins,
providing unified access to all Jenkins credential types.
"""

import logging
from typing import Any, Dict, List, Optional

from .credential_manager import (
    Credential,
    CredentialFilter,
    CredentialProvider,
    CredentialScope,
    CredentialType,
)
from .credential_classifier import CredentialClassifier
from .jenkins import JenkinsClient, JenkinsAuthenticationError, JenkinsConnectionError

logger = logging.getLogger(__name__)


class JenkinsCredentialProvider(CredentialProvider):
    """Jenkins implementation of CredentialProvider."""

    def __init__(self,
                 server: str,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 timeout: int = 60,
                 enable_classification: bool = True):
        """Initialize Jenkins credential provider.

        Args:
            server: Jenkins server URL
            username: Jenkins username
            password: Jenkins password/token
            timeout: Connection timeout in seconds
            enable_classification: Whether to enable credential classification
        """
        self.client = JenkinsClient(server, username, password, timeout)
        self.server = server
        self.classifier = CredentialClassifier() if enable_classification else None

    def get_name(self) -> str:
        """Get the provider name."""
        return "jenkins"

    def supports_read(self) -> bool:
        """Whether this provider supports reading credentials."""
        return True

    def supports_write(self) -> bool:
        """Whether this provider supports writing credentials."""
        return False  # Jenkins credential creation via API is complex

    def list_credentials(self, credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
        """List all credentials from Jenkins."""
        try:
            # Get all credentials in one call (unified approach)
            jenkins_creds = self.client.get_credentials()

            # Convert to unified format
            credentials: List[Credential] = []
            for cred_data in jenkins_creds:
                credential = self._convert_jenkins_credential(cred_data)
                if credential:
                    credentials.append(credential)

            # Apply filter if provided
            if credential_filter:
                credentials = [cred for cred in credentials if credential_filter.matches(cred)]

            logger.info(f"Retrieved {len(credentials)} credentials from Jenkins")
            return credentials

        except (JenkinsAuthenticationError, JenkinsConnectionError):
            # Re-raise authentication and connection errors without modification
            raise
        except Exception as e:
            logger.error(f"Failed to list Jenkins credentials: {e}")
            return []

    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get a specific credential by ID from Jenkins."""
        credentials = self.list_credentials()
        for credential in credentials:
            if credential.id == credential_id:
                return credential
        return None

    def credential_exists(self, credential_id: str) -> bool:
        """Check if a credential exists in Jenkins."""
        return self.get_credential(credential_id) is not None

    def _convert_jenkins_credential(self, cred_data: Dict[str, Any]) -> Optional[Credential]:
        """Convert Jenkins credential data to unified Credential object."""
        try:
            credential = self._create_base_credential(cred_data)
            if not credential:
                return None

            self._set_credential_fields(credential, cred_data)
            self._add_basic_tags(credential)
            self._classify_credential(credential, cred_data)

            return credential

        except Exception as e:
            logger.error(f"Failed to convert Jenkins credential {cred_data.get('id', 'unknown')}: {e}")
            return None

    def _create_base_credential(self, cred_data: Dict[str, Any]) -> Optional[Credential]:
        """Create base credential object with core fields."""
        # Map Jenkins types to unified types
        type_mapping = {
            "username_password": CredentialType.USERNAME_PASSWORD,
            "ssh_private_key": CredentialType.SSH_PRIVATE_KEY,
            "secret_text": CredentialType.SECRET_TEXT,
            "secret_file": CredentialType.SECRET_FILE,
        }

        jenkins_type = cred_data.get("type", "unknown")
        unified_type = type_mapping.get(jenkins_type, CredentialType.UNKNOWN)

        # Create unified credential
        credential = Credential(
            id=cred_data.get("id", ""),
            name=cred_data.get("id", ""),  # Jenkins uses ID as name
            type=unified_type,
            scope=CredentialScope.GLOBAL,  # Jenkins credentials are typically global
            description=cred_data.get("description", ""),
            source_platform="jenkins",
            source_id=cred_data.get("id", ""),
            metadata={
                "jenkins_type": jenkins_type,
                "jenkins_server": self.server,
            }
        )

        return credential

    def _set_credential_fields(self, credential: Credential, cred_data: Dict[str, Any]) -> None:
        """Set type-specific credential fields."""
        if credential.type == CredentialType.USERNAME_PASSWORD:
            credential.username = cred_data.get("username")
            credential.password = cred_data.get("password")

        elif credential.type == CredentialType.SSH_PRIVATE_KEY:
            credential.username = cred_data.get("username")
            credential.private_key = cred_data.get("private_key")
            credential.passphrase = cred_data.get("passphrase")

        elif credential.type == CredentialType.SECRET_TEXT:
            credential.secret = cred_data.get("secret")

        elif credential.type == CredentialType.SECRET_FILE:
            credential.filename = cred_data.get("filename")
            # Note: File content is not available through Jenkins API

    def _add_basic_tags(self, credential: Credential) -> None:
        """Add basic tags based on credential characteristics."""
        tags: set[str] = set()

        # Add tags based on credential content
        if credential.username:
            tags.add("has-username")
        if credential.password:
            tags.add("has-password")
        if credential.private_key:
            tags.add("ssh-key")
        if credential.passphrase:
            tags.add("has-passphrase")
        if credential.secret:
            tags.add("secret")

        # Tag based on common naming patterns
        cred_id_lower = credential.id.lower()
        if "nexus" in cred_id_lower:
            tags.add("nexus")
        if "deploy" in cred_id_lower:
            tags.add("deploy")
        if "ssh" in cred_id_lower:
            tags.add("ssh")
        if "test" in cred_id_lower:
            tags.add("test")
        if "prod" in cred_id_lower or "production" in cred_id_lower:
            tags.add("production")

        credential.tags = tags

    def _classify_credential(self, credential: Credential, cred_data: Dict[str, Any]) -> None:
        """Classify credential into subtypes if classifier is enabled."""
        if not self.classifier:
            return

        classification = self.classifier.classify_credential(cred_data)

        # Ensure metadata dict exists
        if credential.metadata is None:
            credential.metadata = {}

        # Add classification metadata
        credential.metadata.update({
            "detected_type": classification.detected_type,
            "subtype": classification.subtype,
            "strength": classification.strength.value if classification.strength else None,
            "key_size": classification.key_size,
            "algorithm": classification.algorithm,
            "format": classification.format,
            "has_passphrase": classification.has_passphrase,
            "expires": classification.expires,
            "issuer": classification.issuer,
            "subject": classification.subject,
            "fingerprint": classification.fingerprint,
        })

        # Add validation errors and security warnings if present
        if classification.validation_errors:
            credential.metadata["validation_errors"] = classification.validation_errors
        if classification.security_warnings:
            credential.metadata["security_warnings"] = classification.security_warnings
        # Add any additional metadata from classification
        if classification.metadata:
            credential.metadata.update(classification.metadata)

        # Add tags based on classification
        tags = credential.tags or set()
        if classification.subtype:
            tags.add(f"subtype:{classification.subtype}")
        if classification.strength and classification.strength.value != "unknown":
            tags.add(f"strength:{classification.strength.value}")
        if classification.algorithm:
            tags.add(f"algorithm:{classification.algorithm}")
        if classification.validation_errors:
            tags.add("has-errors")
        if classification.security_warnings:
            tags.add("has-warnings")

        # Update tags after classification
        credential.tags = tags


# Legacy convenience functions for backward compatibility
def get_jenkins_credentials(server: str,
                          username: Optional[str] = None,
                          password: Optional[str] = None,
                          credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
    """Get Jenkins credentials using the unified provider (legacy function)."""
    provider = JenkinsCredentialProvider(server, username, password)
    return provider.list_credentials(credential_filter)


def get_jenkins_secrets(server: str,
                       username: Optional[str] = None,
                       password: Optional[str] = None) -> List[Credential]:
    """Get only Jenkins secrets (legacy function)."""
    credential_filter = CredentialFilter(types={CredentialType.SECRET_TEXT})
    return get_jenkins_credentials(server, username, password, credential_filter)


def get_jenkins_ssh_keys(server: str,
                        username: Optional[str] = None,
                        password: Optional[str] = None) -> List[Credential]:
    """Get only Jenkins SSH keys (legacy function)."""
    credential_filter = CredentialFilter(types={CredentialType.SSH_PRIVATE_KEY})
    return get_jenkins_credentials(server, username, password, credential_filter)
