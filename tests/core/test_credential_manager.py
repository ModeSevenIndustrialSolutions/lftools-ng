# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Tests for unified credential management system.
"""

from unittest.mock import Mock, patch

import pytest

from lftools_ng.core.credential_manager import (
    Credential,
    CredentialFilter,
    CredentialManager,
    CredentialScope,
    CredentialType,
)
from lftools_ng.core.jenkins_provider import JenkinsCredentialProvider


class TestCredentialFilter:
    """Test cases for CredentialFilter."""

    def test_matches_type_filter(self):
        """Test type filtering."""
        credential = Credential(
            id="test-cred",
            name="Test Credential",
            type=CredentialType.USERNAME_PASSWORD,
            scope=CredentialScope.GLOBAL,
            username="testuser",
            password="testpass",  # Need this to not be considered empty
        )

        # Should match
        filter_match = CredentialFilter(types={CredentialType.USERNAME_PASSWORD})
        assert filter_match.matches(credential)

        # Should not match
        filter_no_match = CredentialFilter(types={CredentialType.SSH_PRIVATE_KEY})
        assert not filter_no_match.matches(credential)

    def test_matches_has_username_filter(self):
        """Test username presence filtering."""
        cred_with_username = Credential(
            id="test-cred-1",
            name="Test Credential 1",
            type=CredentialType.USERNAME_PASSWORD,
            scope=CredentialScope.GLOBAL,
            username="testuser",
            password="testpass",  # Need this to not be considered empty
        )

        cred_without_username = Credential(
            id="test-cred-2",
            name="Test Credential 2",
            type=CredentialType.SECRET_TEXT,
            scope=CredentialScope.GLOBAL,
            secret="testsecret",  # Need this to not be considered empty
        )

        # Filter for credentials with username
        filter_has_username = CredentialFilter(has_username=True)
        assert filter_has_username.matches(cred_with_username)
        assert not filter_has_username.matches(cred_without_username)

        # Filter for credentials without username
        filter_no_username = CredentialFilter(has_username=False)
        assert not filter_no_username.matches(cred_with_username)
        assert filter_no_username.matches(cred_without_username)

    def test_matches_tag_filter(self):
        """Test tag filtering."""
        credential = Credential(
            id="test-cred",
            name="Test Credential",
            type=CredentialType.USERNAME_PASSWORD,
            scope=CredentialScope.GLOBAL,
            username="testuser",
            password="testpass",  # Need this to not be considered empty
            tags={"nexus", "deploy"},
        )

        # Should match - has nexus tag
        filter_nexus = CredentialFilter(tags={"nexus"})
        assert filter_nexus.matches(credential)

        # Should match - has deploy tag
        filter_deploy = CredentialFilter(tags={"deploy"})
        assert filter_deploy.matches(credential)

        # Should not match - doesn't have test tag
        filter_test = CredentialFilter(tags={"test"})
        assert not filter_test.matches(credential)

    def test_matches_name_pattern_filter(self):
        """Test name pattern filtering."""
        credential = Credential(
            id="nexus-deploy-key",
            name="nexus-deploy-key",
            type=CredentialType.SSH_PRIVATE_KEY,
            scope=CredentialScope.GLOBAL,
            private_key="-----BEGIN RSA PRIVATE KEY-----\n...",  # Need this to not be considered empty
        )

        # Should match wildcard pattern
        filter_wildcard = CredentialFilter(name_patterns=["*nexus*"])
        assert filter_wildcard.matches(credential)

        # Should match exact pattern
        filter_exact = CredentialFilter(name_patterns=["nexus-deploy-key"])
        assert filter_exact.matches(credential)

        # Should not match
        filter_no_match = CredentialFilter(name_patterns=["*github*"])
        assert not filter_no_match.matches(credential)


class TestCredentialManager:
    """Test cases for CredentialManager."""

    def test_register_provider(self):
        """Test provider registration."""
        manager = CredentialManager()

        # Mock provider
        provider = Mock()
        provider.get_name.return_value = "test-provider"

        manager.register_provider(provider)

        assert "test-provider" in manager.list_providers()
        assert manager.get_provider("test-provider") == provider

    def test_list_credentials(self):
        """Test listing credentials from provider."""
        manager = CredentialManager()

        # Mock provider
        provider = Mock()
        provider.get_name.return_value = "test-provider"
        provider.supports_read.return_value = True
        provider.list_credentials.return_value = [
            Credential(
                id="test-1",
                name="Test 1",
                type=CredentialType.USERNAME_PASSWORD,
                scope=CredentialScope.GLOBAL,
            )
        ]

        manager.register_provider(provider)

        credentials = manager.list_credentials("test-provider")

        assert len(credentials) == 1
        assert credentials[0].id == "test-1"

    def test_list_credentials_not_found(self):
        """Test listing credentials from non-existent provider."""
        manager = CredentialManager()

        with pytest.raises(ValueError, match="Provider 'non-existent' not found"):
            manager.list_credentials("non-existent")

    def test_list_credentials_read_not_supported(self):
        """Test listing credentials from provider that doesn't support reading."""
        manager = CredentialManager()

        # Mock provider that doesn't support reading
        provider = Mock()
        provider.get_name.return_value = "write-only-provider"
        provider.supports_read.return_value = False

        manager.register_provider(provider)

        with pytest.raises(ValueError, match="does not support reading credentials"):
            manager.list_credentials("write-only-provider")


class TestJenkinsCredentialProvider:
    """Test cases for JenkinsCredentialProvider."""

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_list_credentials(self, mock_jenkins_client_class):
        """Test listing credentials from Jenkins."""
        # Mock Jenkins client
        mock_client = Mock()
        mock_client.get_credentials.return_value = [
            {
                "id": "nexus-deploy",
                "type": "username_password",
                "username": "deploy",
                "password": "secret123",
                "description": "Nexus deployment credential",
            },
            {
                "id": "ssh-key-1",
                "type": "ssh_private_key",
                "username": "git",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
                "passphrase": "key-passphrase",
                "description": "SSH key for Git operations",
            },
        ]
        mock_jenkins_client_class.return_value = mock_client

        # Test the provider
        provider = JenkinsCredentialProvider("https://jenkins.example.com", "user", "pass")

        credentials = provider.list_credentials()

        assert len(credentials) == 2

        # Check first credential
        cred1 = credentials[0]
        assert cred1.id == "nexus-deploy"
        assert cred1.type == CredentialType.USERNAME_PASSWORD
        assert cred1.username == "deploy"
        assert cred1.password == "secret123"
        assert "nexus" in cred1.tags
        assert "has-username" in cred1.tags
        assert "has-password" in cred1.tags

        # Check second credential
        cred2 = credentials[1]
        assert cred2.id == "ssh-key-1"
        assert cred2.type == CredentialType.SSH_PRIVATE_KEY
        assert cred2.username == "git"
        assert cred2.private_key == "-----BEGIN RSA PRIVATE KEY-----\n..."
        assert cred2.passphrase == "key-passphrase"
        assert "ssh-key" in cred2.tags
        assert "has-username" in cred2.tags
        assert "has-passphrase" in cred2.tags

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_list_credentials_with_filter(self, mock_jenkins_client_class):
        """Test listing credentials with filter."""
        # Mock Jenkins client
        mock_client = Mock()
        mock_client.get_credentials.return_value = [
            {
                "id": "nexus-deploy",
                "type": "username_password",
                "username": "deploy",
                "password": "secret123",
                "description": "Nexus deployment credential",
            },
            {
                "id": "test-secret",
                "type": "secret_text",
                "secret": "test-value",
                "description": "Test secret",
            },
        ]
        mock_jenkins_client_class.return_value = mock_client

        # Test the provider with filter
        provider = JenkinsCredentialProvider("https://jenkins.example.com", "user", "pass")

        # Filter for username/password credentials only
        credential_filter = CredentialFilter(types={CredentialType.USERNAME_PASSWORD})
        credentials = provider.list_credentials(credential_filter)

        assert len(credentials) == 1
        assert credentials[0].type == CredentialType.USERNAME_PASSWORD

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_get_credential(self, mock_jenkins_client_class):
        """Test getting specific credential."""
        # Mock Jenkins client
        mock_client = Mock()
        mock_client.get_credentials.return_value = [
            {
                "id": "nexus-deploy",
                "type": "username_password",
                "username": "deploy",
                "password": "secret123",
                "description": "Nexus deployment credential",
            },
        ]
        mock_jenkins_client_class.return_value = mock_client

        provider = JenkinsCredentialProvider("https://jenkins.example.com", "user", "pass")

        # Get existing credential
        credential = provider.get_credential("nexus-deploy")
        assert credential is not None
        assert credential.id == "nexus-deploy"

        # Get non-existent credential
        credential = provider.get_credential("non-existent")
        assert credential is None

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_credential_exists(self, mock_jenkins_client_class):
        """Test checking if credential exists."""
        # Mock Jenkins client
        mock_client = Mock()
        mock_client.get_credentials.return_value = [
            {
                "id": "nexus-deploy",
                "type": "username_password",
                "username": "deploy",
                "password": "secret123",
                "description": "Nexus deployment credential",
            },
        ]
        mock_jenkins_client_class.return_value = mock_client

        provider = JenkinsCredentialProvider("https://jenkins.example.com", "user", "pass")

        assert provider.credential_exists("nexus-deploy")
        assert not provider.credential_exists("non-existent")

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_provider_capabilities(self, mock_jenkins_client_class):
        """Test provider capabilities."""
        # Mock Jenkins client to avoid network calls
        mock_client = Mock()
        mock_jenkins_client_class.return_value = mock_client

        provider = JenkinsCredentialProvider("https://jenkins.example.com", "user", "pass")

        assert provider.get_name() == "jenkins"
        assert provider.supports_read() is True
        assert provider.supports_write() is False  # Jenkins write is complex

    @patch("lftools_ng.core.jenkins_provider.JenkinsClient")
    def test_unsupported_operations(self, mock_jenkins_client_class):
        """Test unsupported write operations."""
        # Mock Jenkins client to avoid network calls
        mock_client = Mock()
        mock_jenkins_client_class.return_value = mock_client

        provider = JenkinsCredentialProvider("https://jenkins.example.com", "user", "pass")

        credential = Credential(
            id="test",
            name="Test",
            type=CredentialType.USERNAME_PASSWORD,
            scope=CredentialScope.GLOBAL,
        )

        with pytest.raises(NotImplementedError):
            provider.create_credential(credential)

        with pytest.raises(NotImplementedError):
            provider.update_credential(credential)

        with pytest.raises(NotImplementedError):
            provider.delete_credential("test")
