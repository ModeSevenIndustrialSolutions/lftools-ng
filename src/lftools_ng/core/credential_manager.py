# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Unified credential management system for lftools-ng.

This module provides a unified abstraction layer for managing credentials
across different platforms (Jenkins, GitHub, 1Password, etc.).
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CredentialType(Enum):
    """Supported credential types."""
    USERNAME_PASSWORD = "username_password"
    SSH_PRIVATE_KEY = "ssh_private_key"
    SECRET_TEXT = "secret_text"
    SECRET_FILE = "secret_file"
    API_TOKEN = "api_token"
    CERTIFICATE = "certificate"
    UNKNOWN = "unknown"


class CredentialScope(Enum):
    """Credential scope levels."""
    GLOBAL = "global"
    REPOSITORY = "repository"
    ORGANIZATION = "organization"
    PROJECT = "project"


@dataclass
class Credential:
    """Unified credential representation."""
    id: str
    name: str
    type: CredentialType
    scope: CredentialScope
    description: str = ""
    tags: Optional[Set[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    # Credential-specific fields
    username: Optional[str] = None
    password: Optional[str] = None
    secret: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None
    filename: Optional[str] = None
    file_content: Optional[bytes] = None

    # Platform-specific identifiers
    source_platform: Optional[str] = None
    source_id: Optional[str] = None
    target_platform: Optional[str] = None
    target_id: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = set()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CredentialFilter:
    """Filter criteria for credential operations."""
    types: Optional[Set[CredentialType]] = None
    name_patterns: Optional[List[str]] = None  # Supports wildcards and regex
    id_patterns: Optional[List[str]] = None
    tags: Optional[Set[str]] = None
    scopes: Optional[Set[CredentialScope]] = None
    has_username: Optional[bool] = None
    has_password: Optional[bool] = None
    has_passphrase: Optional[bool] = None
    exclude_empty: bool = True

    def matches(self, credential: Credential) -> bool:
        """Check if a credential matches this filter."""
        import re
        import fnmatch

        # Type filter
        if self.types and credential.type not in self.types:
            return False

        # Scope filter
        if self.scopes and credential.scope not in self.scopes:
            return False

        # Name pattern filter
        if self.name_patterns:
            name_match = False
            for pattern in self.name_patterns:
                # Try fnmatch first (supports wildcards like *, ?)
                if fnmatch.fnmatch(credential.name, pattern):
                    name_match = True
                    break
                # If fnmatch fails, try regex (but handle regex errors gracefully)
                try:
                    if re.search(pattern, credential.name):
                        name_match = True
                        break
                except re.error:
                    # If regex is invalid, fall back to simple substring match
                    if pattern in credential.name:
                        name_match = True
                        break
            if not name_match:
                return False

        # ID pattern filter
        if self.id_patterns:
            id_match = False
            for pattern in self.id_patterns:
                # Try fnmatch first (supports wildcards like *, ?)
                if fnmatch.fnmatch(credential.id, pattern):
                    id_match = True
                    break
                # If fnmatch fails, try regex (but handle regex errors gracefully)
                try:
                    if re.search(pattern, credential.id):
                        id_match = True
                        break
                except re.error:
                    # If regex is invalid, fall back to simple substring match
                    if pattern in credential.id:
                        id_match = True
                        break
            if not id_match:
                return False

        # Tag filter
        if self.tags and credential.tags and not self.tags.intersection(credential.tags):
            return False

        # Field presence filters
        if self.has_username is not None:
            if self.has_username and not credential.username:
                return False
            if not self.has_username and credential.username:
                return False

        if self.has_password is not None:
            if self.has_password and not credential.password:
                return False
            if not self.has_password and credential.password:
                return False

        if self.has_passphrase is not None:
            if self.has_passphrase and not credential.passphrase:
                return False
            if not self.has_passphrase and credential.passphrase:
                return False

        # Empty credential filter
        if self.exclude_empty and self._is_empty_credential(credential):
            return False

        return True

    def _is_empty_credential(self, credential: Credential) -> bool:
        """Check if credential has no actual secret data."""
        # A credential is considered empty if it has none of the actual secret fields
        # populated. Username alone is not considered secret data.
        return not any([
            credential.password,
            credential.secret,
            credential.private_key,
            credential.file_content
        ])


@dataclass
class MigrationOptions:
    """Options for credential migration operations."""
    overwrite_existing: bool = False
    dry_run: bool = False
    backup_existing: bool = True
    validate_before_migration: bool = True
    preserve_metadata: bool = True
    tag_migrated: bool = True
    migration_tag: str = "migrated-from-jenkins"


@dataclass
class MigrationResult:
    """Result of a credential migration operation."""
    success: bool
    credential: Credential
    source_platform: str
    target_platform: str
    action: str  # "created", "updated", "skipped", "failed"
    message: str = ""
    error: Optional[str] = None


class CredentialProvider(ABC):
    """Abstract base class for credential providers."""

    @abstractmethod
    def get_name(self) -> str:
        """Get the provider name."""
        pass

    @abstractmethod
    def list_credentials(self, credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
        """List all credentials from this provider."""
        pass

    @abstractmethod
    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get a specific credential by ID."""
        pass

    @abstractmethod
    def supports_read(self) -> bool:
        """Whether this provider supports reading credentials."""
        pass

    @abstractmethod
    def supports_write(self) -> bool:
        """Whether this provider supports writing credentials."""
        pass

    @abstractmethod
    def credential_exists(self, credential_id: str) -> bool:
        """Check if a credential exists."""
        pass

    def create_credential(self, credential: Credential) -> bool:
        """Create a new credential."""
        raise NotImplementedError(f"{self.get_name()} does not support credential creation")

    def update_credential(self, credential: Credential) -> bool:
        """Update an existing credential."""
        raise NotImplementedError(f"{self.get_name()} does not support credential updates")

    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential."""
        raise NotImplementedError(f"{self.get_name()} does not support credential deletion")


class CredentialManager:
    """Unified credential management system."""

    def __init__(self):
        self.providers: Dict[str, CredentialProvider] = {}

    def register_provider(self, provider: CredentialProvider) -> None:
        """Register a credential provider."""
        self.providers[provider.get_name()] = provider
        logger.info(f"Registered credential provider: {provider.get_name()}")

    def get_provider(self, name: str) -> Optional[CredentialProvider]:
        """Get a registered provider by name."""
        return self.providers.get(name)

    def list_providers(self) -> List[str]:
        """List all registered provider names."""
        return list(self.providers.keys())

    def list_credentials(self,
                        provider_name: str,
                        credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
        """List credentials from a specific provider."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' not found")

        if not provider.supports_read():
            raise ValueError(f"Provider '{provider_name}' does not support reading credentials")

        return provider.list_credentials(credential_filter)

    def migrate_credentials(self,
                           source_provider: str,
                           target_provider: str,
                           credential_filter: Optional[CredentialFilter] = None,
                           options: Optional[MigrationOptions] = None) -> List[MigrationResult]:
        """Migrate credentials from one provider to another."""
        if options is None:
            options = MigrationOptions()

        source = self.get_provider(source_provider)
        target = self.get_provider(target_provider)

        if not source:
            raise ValueError(f"Source provider '{source_provider}' not found")
        if not target:
            raise ValueError(f"Target provider '{target_provider}' not found")

        if not source.supports_read():
            raise ValueError(f"Source provider '{source_provider}' does not support reading")
        if not target.supports_write():
            raise ValueError(f"Target provider '{target_provider}' does not support writing")

        # Get credentials from source
        credentials = source.list_credentials(credential_filter)
        results = []

        for credential in credentials:
            result = self._migrate_single_credential(credential, target, options)
            results.append(result)

            if not options.dry_run:
                logger.info(f"Migration result: {result.action} - {credential.id}")

        return results

    def _migrate_single_credential(self,
                                  credential: Credential,
                                  target: CredentialProvider,
                                  options: MigrationOptions) -> MigrationResult:
        """Migrate a single credential to target provider."""
        try:
            # Check if credential already exists in target
            exists = target.credential_exists(credential.id)

            if exists and not options.overwrite_existing:
                return MigrationResult(
                    success=True,
                    credential=credential,
                    source_platform=credential.source_platform or "unknown",
                    target_platform=target.get_name(),
                    action="skipped",
                    message="Credential already exists and overwrite_existing=False"
                )

            # Prepare credential for migration
            migrated_credential = self._prepare_credential_for_migration(credential, target.get_name(), options)

            if options.dry_run:
                action = "would_update" if exists else "would_create"
                return MigrationResult(
                    success=True,
                    credential=migrated_credential,
                    source_platform=credential.source_platform or "unknown",
                    target_platform=target.get_name(),
                    action=action,
                    message="Dry run - no changes made"
                )

            # Perform the migration
            if exists:
                success = target.update_credential(migrated_credential)
                action = "updated" if success else "failed"
            else:
                success = target.create_credential(migrated_credential)
                action = "created" if success else "failed"

            return MigrationResult(
                success=success,
                credential=migrated_credential,
                source_platform=credential.source_platform or "unknown",
                target_platform=target.get_name(),
                action=action,
                message="Migration completed successfully" if success else "Migration failed"
            )

        except Exception as e:
            logger.error(f"Error migrating credential {credential.id}: {e}")
            return MigrationResult(
                success=False,
                credential=credential,
                source_platform=credential.source_platform or "unknown",
                target_platform=target.get_name(),
                action="failed",
                error=str(e)
            )

    def _prepare_credential_for_migration(self,
                                        credential: Credential,
                                        target_platform: str,
                                        options: MigrationOptions) -> Credential:
        """Prepare a credential for migration to target platform."""
        # Create a copy of the credential
        import copy
        migrated = copy.deepcopy(credential)

        # Update platform information
        migrated.target_platform = target_platform

        # Add migration tag if requested
        if options.tag_migrated and migrated.tags is not None:
            migrated.tags.add(options.migration_tag)

        # Preserve or update metadata
        if options.preserve_metadata and migrated.metadata is not None:
            migrated.metadata["migration_source"] = credential.source_platform
            migrated.metadata["migration_date"] = str(datetime.now().isoformat())
            # Add migration origin for 1Password origin/source field (STRING type)
            if credential.source_platform == "jenkins":
                migrated.metadata["migration_origin"] = "Migrated from Jenkins"

        return migrated
