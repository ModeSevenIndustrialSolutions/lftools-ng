# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Multi-platform credential providers with local authentication support.

This module implements providers for various credential storage platforms,
leveraging existing local authentication where possible.
"""

import json
import logging
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from .credential_manager import (
    Credential,
    CredentialFilter,
    CredentialProvider,
    CredentialScope,
    CredentialType,
)

logger = logging.getLogger(__name__)


@dataclass
class PlatformConfig:
    """Configuration for a platform provider."""
    name: str
    auto_detect: bool = True
    auth_method: str = "auto"  # auto, cli, env, interactive
    required_tools: List[str] = field(default_factory=list)
    config_path: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)


class LocalAuthManager:
    """Manages local authentication detection and setup."""

    @staticmethod
    def check_command_exists(command: str) -> bool:
        """Check if a command exists in PATH."""
        try:
            subprocess.run([command, "--version"],
                         capture_output=True,
                         check=False,
                         timeout=5)
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    @staticmethod
    def get_git_config(key: str) -> Optional[str]:
        """Get git configuration value."""
        try:
            result = subprocess.run(
                ["git", "config", "--global", key],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    @staticmethod
    def check_github_cli_auth() -> bool:
        """Check if GitHub CLI is authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            return False

    @staticmethod
    def check_gitlab_cli_auth() -> bool:
        """Check if GitLab CLI is authenticated."""
        try:
            result = subprocess.run(
                ["glab", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            return False

    @staticmethod
    def check_onepassword_cli_auth() -> bool:
        """Check if 1Password CLI is authenticated."""
        try:
            result = subprocess.run(
                ["op", "account", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            return False

    @staticmethod
    def check_pass_setup() -> bool:
        """Check if UNIX pass is set up and accessible."""
        try:
            # Check if pass command exists
            if not LocalAuthManager.check_command_exists("pass"):
                return False

            # Check if password store exists
            store_path = os.path.expanduser("~/.password-store")
            if not os.path.exists(store_path):
                return False

            # Try to list passwords (this will fail if GPG is not set up)
            result = subprocess.run(
                ["pass", "ls"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            return False


class GitHubCredentialProvider(CredentialProvider):
    """GitHub credential provider using GitHub CLI."""

    def __init__(self, organization: Optional[str] = None, token: Optional[str] = None):
        """Initialize GitHub provider.

        Args:
            organization: GitHub organization name (for org secrets)
            token: GitHub personal access token (if not using CLI auth)
        """
        self.organization = organization
        self.token = token
        self._authenticated = False
        self._setup_auth()

    def _setup_auth(self):
        """Set up GitHub authentication."""
        if LocalAuthManager.check_github_cli_auth():
            logger.info("Using existing GitHub CLI authentication")
            self._authenticated = True
        elif self.token:
            logger.info("Using provided GitHub token")
            os.environ['GITHUB_TOKEN'] = self.token
            self._authenticated = True
        else:
            logger.warning("GitHub authentication not available. Use 'gh auth login' or provide token.")

    def get_name(self) -> str:
        """Get the provider name."""
        return "github"

    def supports_read(self) -> bool:
        """Whether this provider supports reading credentials."""
        return False  # GitHub secrets are write-only

    def supports_write(self) -> bool:
        """Whether this provider supports writing credentials."""
        return self._authenticated

    def list_credentials(self, credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
        """List all credentials from GitHub (not supported)."""
        logger.warning("GitHub does not support reading secret values")
        return []

    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get a specific credential by ID (not supported)."""
        return None

    def credential_exists(self, credential_id: str) -> bool:
        """Check if a credential exists in GitHub."""
        if not self._authenticated:
            return False

        try:
            # Try to get secret info (without value)
            if self.organization:
                cmd = ["gh", "secret", "list", "--org", self.organization]
            else:
                cmd = ["gh", "secret", "list"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return credential_id in result.stdout
        except subprocess.TimeoutExpired:
            return False

    def create_credential(self, credential: Credential) -> bool:
        """Create a new credential in GitHub."""
        if not self._authenticated:
            logger.error("GitHub authentication required")
            return False

        try:
            # Determine the secret value based on credential type
            secret_value = self._extract_secret_value(credential)
            if not secret_value:
                logger.error(f"Could not extract secret value from credential {credential.id}")
                return False

            # Create the secret
            if self.organization:
                cmd = ["gh", "secret", "set", credential.id, "--org", self.organization]
            else:
                cmd = ["gh", "secret", "set", credential.id]

            # Pass secret value via stdin
            result = subprocess.run(
                cmd,
                input=secret_value,
                text=True,
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Successfully created GitHub secret: {credential.id}")
                return True
            else:
                logger.error(f"Failed to create GitHub secret: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Timeout creating GitHub secret")
            return False

    def update_credential(self, credential: Credential) -> bool:
        """Update an existing credential in GitHub."""
        # GitHub doesn't distinguish between create and update
        return self.create_credential(credential)

    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential from GitHub."""
        if not self._authenticated:
            logger.error("GitHub authentication required")
            return False

        try:
            if self.organization:
                cmd = ["gh", "secret", "delete", credential_id, "--org", self.organization]
            else:
                cmd = ["gh", "secret", "delete", credential_id]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            return False

    def _extract_secret_value(self, credential: Credential) -> Optional[str]:
        """Extract the appropriate secret value from a credential."""
        if credential.type == CredentialType.USERNAME_PASSWORD:
            return credential.password
        elif credential.type == CredentialType.SECRET_TEXT:
            return credential.secret
        elif credential.type == CredentialType.SSH_PRIVATE_KEY:
            return credential.private_key
        elif credential.type == CredentialType.API_TOKEN:
            return credential.secret or credential.password
        else:
            return credential.secret or credential.password


class GitLabCredentialProvider(CredentialProvider):
    """GitLab credential provider using GitLab CLI."""

    def __init__(self, group: Optional[str] = None, token: Optional[str] = None):
        """Initialize GitLab provider.

        Args:
            group: GitLab group name (for group variables)
            token: GitLab personal access token (if not using CLI auth)
        """
        self.group = group
        self.token = token
        self._authenticated = False
        self._setup_auth()

    def _setup_auth(self):
        """Set up GitLab authentication."""
        if LocalAuthManager.check_gitlab_cli_auth():
            logger.info("Using existing GitLab CLI authentication")
            self._authenticated = True
        elif self.token:
            logger.info("Using provided GitLab token")
            os.environ['GITLAB_TOKEN'] = self.token
            self._authenticated = True
        else:
            logger.warning("GitLab authentication not available. Use 'glab auth login' or provide token.")

    def get_name(self) -> str:
        """Get the provider name."""
        return "gitlab"

    def supports_read(self) -> bool:
        """Whether this provider supports reading credentials."""
        return False  # GitLab variables values are typically protected

    def supports_write(self) -> bool:
        """Whether this provider supports writing credentials."""
        return self._authenticated

    def list_credentials(self, credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
        """List all credentials from GitLab."""
        # Implementation would use GitLab API to list variables
        return []

    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get a specific credential by ID."""
        return None

    def credential_exists(self, credential_id: str) -> bool:
        """Check if a credential exists in GitLab."""
        # Implementation would check GitLab variables
        return False

    def create_credential(self, credential: Credential) -> bool:
        """Create a new credential in GitLab."""
        # Implementation would use GitLab API to create variables
        return False

    def update_credential(self, credential: Credential) -> bool:
        """Update an existing credential in GitLab."""
        return self.create_credential(credential)

    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential from GitLab."""
        return False


class OnePasswordCredentialProvider(CredentialProvider):
    """1Password credential provider using 1Password CLI."""

    def __init__(self, vault: str = "Private", account: Optional[str] = None):
        """Initialize 1Password provider.

        Args:
            vault: 1Password vault name
            account: 1Password account (if multiple accounts)
        """
        self.vault = vault
        self.account = account
        self._authenticated = False
        self._setup_auth()

    def _setup_auth(self):
        """Set up 1Password authentication."""
        if LocalAuthManager.check_onepassword_cli_auth():
            logger.info("Using existing 1Password CLI authentication")
            self._authenticated = True
        else:
            logger.warning("1Password authentication not available. Use 'op signin' or 'op account add'.")

    def get_name(self) -> str:
        """Get the provider name."""
        return "1password"

    def supports_read(self) -> bool:
        """Whether this provider supports reading credentials."""
        return self._authenticated

    def supports_write(self) -> bool:
        """Whether this provider supports writing credentials."""
        return self._authenticated

    def list_credentials(self, credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
        """List all credentials from 1Password."""
        if not self._authenticated:
            return []

        try:
            cmd = ["op", "item", "list", "--vault", self.vault, "--format", "json"]
            if self.account:
                cmd.extend(["--account", self.account])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Failed to list 1Password items: {result.stderr}")
                return []

            items = json.loads(result.stdout)
            credentials = []

            for item in items:
                credential = self._convert_op_item_to_credential(item)
                if credential and (not credential_filter or credential_filter.matches(credential)):
                    credentials.append(credential)

            return credentials

        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.error(f"Error listing 1Password credentials: {e}")
            return []

    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get a specific credential by ID from 1Password."""
        if not self._authenticated:
            return None

        try:
            cmd = ["op", "item", "get", credential_id, "--vault", self.vault, "--format", "json"]
            if self.account:
                cmd.extend(["--account", self.account])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return None

            item = json.loads(result.stdout)
            return self._convert_op_item_to_credential(item, include_secrets=True)

        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

    def credential_exists(self, credential_id: str) -> bool:
        """Check if a credential exists in 1Password."""
        return self.get_credential(credential_id) is not None

    def create_credential(self, credential: Credential) -> bool:
        """Create a new credential in 1Password."""
        if not self._authenticated:
            return False

        try:
            # Create 1Password item template
            item_template = self._create_op_item_template(credential)

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(item_template, f)
                template_file = f.name

            try:
                cmd = ["op", "item", "create", "--template", template_file, "--vault", self.vault]
                if self.account:
                    cmd.extend(["--account", self.account])

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                success = result.returncode == 0

                if success:
                    logger.info(f"Successfully created 1Password item: {credential.id}")
                else:
                    logger.error(f"Failed to create 1Password item: {result.stderr}")

                return success

            finally:
                os.unlink(template_file)

        except Exception as e:
            logger.error(f"Error creating 1Password credential: {e}")
            return False

    def update_credential(self, credential: Credential) -> bool:
        """Update an existing credential in 1Password."""
        # 1Password CLI typically requires recreating items for updates
        if self.credential_exists(credential.id):
            # Delete and recreate
            if self.delete_credential(credential.id):
                return self.create_credential(credential)
        return False

    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential from 1Password."""
        if not self._authenticated:
            return False

        try:
            cmd = ["op", "item", "delete", credential_id, "--vault", self.vault]
            if self.account:
                cmd.extend(["--account", self.account])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            return False

    def _convert_op_item_to_credential(self, item: Dict[str, Any], include_secrets: bool = False) -> Optional[Credential]:
        """Convert 1Password item to unified credential."""
        try:
            credential = Credential(
                id=item.get('id', item.get('title', '')),
                name=item.get('title', ''),
                type=self._map_op_category_to_type(item.get('category', 'SECURE_NOTE')),
                scope=CredentialScope.GLOBAL,
                description=item.get('notes', ''),
                source_platform="1password",
                metadata={
                    '1password_category': item.get('category'),
                    '1password_vault': self.vault,
                }
            )

            if include_secrets and 'fields' in item:
                # Extract field values
                for field in item['fields']:
                    field_name = field.get('label', '').lower()
                    field_value = field.get('value', '')

                    if field_name in ['username', 'user']:
                        credential.username = field_value
                    elif field_name in ['password', 'pass']:
                        credential.password = field_value
                    elif field_name in ['private key', 'key']:
                        credential.private_key = field_value
                    elif field_name in ['secret', 'token']:
                        credential.secret = field_value

            return credential

        except Exception as e:
            logger.error(f"Error converting 1Password item: {e}")
            return None

    def _map_op_category_to_type(self, op_category: str) -> CredentialType:
        """Map 1Password category to credential type."""
        category_map = {
            'LOGIN': CredentialType.USERNAME_PASSWORD,
            'SECURE_NOTE': CredentialType.SECRET_TEXT,
            'SSH_KEY': CredentialType.SSH_PRIVATE_KEY,
            'API_CREDENTIAL': CredentialType.API_TOKEN,
            'CERTIFICATE': CredentialType.CERTIFICATE,
        }
        return category_map.get(op_category, CredentialType.UNKNOWN)

    def _create_op_item_template(self, credential: Credential) -> Dict[str, Any]:
        """Create 1Password item template from credential."""
        fields: List[Dict[str, Any]] = []
        template = {
            'title': credential.name,
            'category': self._map_type_to_op_category(credential.type),
            'vault': {'name': self.vault},
            'notes': credential.description,
            'fields': fields
        }

        # Add fields based on credential type
        if credential.username:
            fields.append({
                'label': 'username',
                'type': 'STRING',
                'value': credential.username
            })

        if credential.password:
            fields.append({
                'label': 'password',
                'type': 'CONCEALED',
                'value': credential.password
            })

        if credential.secret:
            fields.append({
                'label': 'secret',
                'type': 'CONCEALED',
                'value': credential.secret
            })

        if credential.private_key:
            fields.append({
                'label': 'private key',
                'type': 'STRING',
                'value': credential.private_key
            })

        return template

    def _map_type_to_op_category(self, cred_type: CredentialType) -> str:
        """Map credential type to 1Password category."""
        type_map = {
            CredentialType.USERNAME_PASSWORD: 'LOGIN',
            CredentialType.SECRET_TEXT: 'SECURE_NOTE',
            CredentialType.SSH_PRIVATE_KEY: 'SSH_KEY',
            CredentialType.API_TOKEN: 'API_CREDENTIAL',
            CredentialType.CERTIFICATE: 'CERTIFICATE',
        }
        return type_map.get(cred_type, 'SECURE_NOTE')


class UnixPassCredentialProvider(CredentialProvider):
    """UNIX pass credential provider."""

    def __init__(self, store_path: Optional[str] = None):
        """Initialize UNIX pass provider.

        Args:
            store_path: Path to password store (defaults to ~/.password-store)
        """
        self.store_path = store_path or os.path.expanduser("~/.password-store")
        self._authenticated = LocalAuthManager.check_pass_setup()

    def get_name(self) -> str:
        """Get the provider name."""
        return "pass"

    def supports_read(self) -> bool:
        """Whether this provider supports reading credentials."""
        return self._authenticated

    def supports_write(self) -> bool:
        """Whether this provider supports writing credentials."""
        return self._authenticated

    def list_credentials(self, credential_filter: Optional[CredentialFilter] = None) -> List[Credential]:
        """List all credentials from UNIX pass."""
        if not self._authenticated:
            return []

        try:
            result = subprocess.run(
                ["pass", "ls"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return []

            credentials = []
            for line in result.stdout.split('\n'):
                if line.strip() and not line.startswith('├') and not line.startswith('└'):
                    # Extract credential name from tree output
                    name = line.strip().replace('├── ', '').replace('└── ', '').replace('│   ', '')
                    if name and not name.startswith('Password Store'):
                        credential = Credential(
                            id=name,
                            name=name,
                            type=CredentialType.SECRET_TEXT,
                            scope=CredentialScope.GLOBAL,
                            source_platform="pass",
                            metadata={'pass_path': name}
                        )

                        if not credential_filter or credential_filter.matches(credential):
                            credentials.append(credential)

            return credentials

        except subprocess.TimeoutExpired:
            return []

    def get_credential(self, credential_id: str) -> Optional[Credential]:
        """Get a specific credential by ID from UNIX pass."""
        if not self._authenticated:
            return None

        try:
            result = subprocess.run(
                ["pass", "show", credential_id],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                return None

            # First line is typically the password, rest might be metadata
            lines = result.stdout.strip().split('\n')
            password = lines[0] if lines else ""

            metadata = {}
            username = None

            # Parse additional metadata from subsequent lines
            for line in lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()

                    if key in ['user', 'username']:
                        username = value
                    else:
                        metadata[key] = value

            return Credential(
                id=credential_id,
                name=credential_id,
                type=CredentialType.SECRET_TEXT,
                scope=CredentialScope.GLOBAL,
                username=username,
                secret=password,
                source_platform="pass",
                metadata=metadata
            )

        except subprocess.TimeoutExpired:
            return None

    def credential_exists(self, credential_id: str) -> bool:
        """Check if a credential exists in UNIX pass."""
        return self.get_credential(credential_id) is not None

    def create_credential(self, credential: Credential) -> bool:
        """Create a new credential in UNIX pass."""
        if not self._authenticated:
            return False

        try:
            # Prepare the credential content
            content_lines = []

            # Add the main secret (password/secret)
            main_secret = credential.password or credential.secret or ""
            content_lines.append(main_secret)

            # Add metadata
            if credential.username:
                content_lines.append(f"username: {credential.username}")
            if credential.description:
                content_lines.append(f"description: {credential.description}")

            content = '\n'.join(content_lines)

            # Create the password entry
            result = subprocess.run(
                ["pass", "insert", "--multiline", credential.id],
                input=content,
                text=True,
                capture_output=True,
                timeout=30
            )

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            return False

    def update_credential(self, credential: Credential) -> bool:
        """Update an existing credential in UNIX pass."""
        # pass doesn't have native update, so delete and recreate
        if self.credential_exists(credential.id):
            if self.delete_credential(credential.id):
                return self.create_credential(credential)
        return False

    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential from UNIX pass."""
        if not self._authenticated:
            return False

        try:
            result = subprocess.run(
                ["pass", "rm", "--force", credential_id],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            return False


def detect_available_providers() -> Dict[str, bool]:
    """Detect which credential providers are available locally."""
    providers = {
        'github': LocalAuthManager.check_github_cli_auth() or 'GITHUB_TOKEN' in os.environ,
        'gitlab': LocalAuthManager.check_gitlab_cli_auth() or 'GITLAB_TOKEN' in os.environ,
        '1password': LocalAuthManager.check_onepassword_cli_auth(),
        'pass': LocalAuthManager.check_pass_setup(),
    }

    return providers


def get_provider_suggestions() -> Dict[str, str]:
    """Get suggestions for setting up providers that aren't available."""
    suggestions = {}

    if not LocalAuthManager.check_github_cli_auth() and 'GITHUB_TOKEN' not in os.environ:
        suggestions['github'] = "Install GitHub CLI and run 'gh auth login', or set GITHUB_TOKEN environment variable"

    if not LocalAuthManager.check_gitlab_cli_auth() and 'GITLAB_TOKEN' not in os.environ:
        suggestions['gitlab'] = "Install GitLab CLI and run 'glab auth login', or set GITLAB_TOKEN environment variable"

    if not LocalAuthManager.check_onepassword_cli_auth():
        suggestions['1password'] = "Install 1Password CLI and run 'op signin' or 'op account add'"

    if not LocalAuthManager.check_pass_setup():
        suggestions['pass'] = "Install pass and set up GPG keys, or ensure ~/.password-store exists and is accessible"

    return suggestions
