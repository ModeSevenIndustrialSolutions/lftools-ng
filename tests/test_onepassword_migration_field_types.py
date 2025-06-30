#!/usr/bin/env python3
"""
Test for 1Password origin/source field creation with correct field type.
"""

import pytest
from unittest.mock import Mock, patch
from lftools_ng.core.credential_manager import Credential, CredentialType, CredentialScope
from lftools_ng.core.platform_providers import OnePasswordCredentialProvider


def test_onepassword_credential_with_migration_origin():
    """Test that 1Password credentials are created with origin/source field as STRING type."""

    # Create a credential with migration metadata
    credential = Credential(
        id="test-repo",
        name="test-repo",
        type=CredentialType.USERNAME_PASSWORD,
        scope=CredentialScope.GLOBAL,
        description="Test credential",
        username="deploy",
        password="secret123",
        source_platform="jenkins",
        target_platform="1password",
        metadata={
            "github_url": "https://github.com/test/repo",
            "project": "TestProject",
            "migration_source": "jenkins-cred-id",
            "migration_type": "repository_deployment",
            "migration_origin": "Migrated from Jenkins"  # This should create origin/source field as STRING
        }
    )

    # Create OnePassword provider
    op_provider = OnePasswordCredentialProvider("TestVault")

    # Generate the template
    template = op_provider._create_op_item_template(credential)

    # Verify the template structure
    assert template["title"] == "test-repo"
    assert template["category"] == "LOGIN"
    assert template["vault"]["name"] == "TestVault"

    # Check that all the required fields are present
    fields = template["fields"]
    field_labels = [f["label"] for f in fields]

    assert "username" in field_labels
    assert "password" in field_labels
    assert "notesPlain" not in field_labels  # Should NOT be present for migrated credentials
    assert "origin/source" in field_labels  # This is the key field we're testing
    assert "website" in field_labels

    # Verify field types are correct
    for field in fields:
        if field["label"] == "username":
            assert field["type"] == "STRING"
            assert field["value"] == "deploy"
        elif field["label"] == "password":
            assert field["type"] == "CONCEALED"
            assert field["value"] == "secret123"
        elif field["label"] == "origin/source":
            # This is the critical test - must be STRING, not CONCEALED
            assert field["type"] == "STRING"
            assert field["value"] == "Migrated from Jenkins"
        elif field["label"] == "website":
            assert field["type"] == "URL"
            assert field["value"] == "https://github.com/test/repo"


def test_onepassword_credential_without_migration_origin():
    """Test that credentials without migration_origin don't get the origin/source field."""

    # Create a credential without migration metadata
    credential = Credential(
        id="test-repo",
        name="test-repo",
        type=CredentialType.USERNAME_PASSWORD,
        scope=CredentialScope.GLOBAL,
        description="Test credential",
        username="deploy",
        password="secret123",
        source_platform="jenkins",
        target_platform="1password",
        metadata={
            "github_url": "https://github.com/test/repo",
            "project": "TestProject"
            # No migration_origin field
        }
    )

    # Create OnePassword provider
    op_provider = OnePasswordCredentialProvider("TestVault")

    # Generate the template
    template = op_provider._create_op_item_template(credential)

    # Check that origin/source field is NOT present
    fields = template["fields"]
    field_labels = [f["label"] for f in fields]

    assert "origin/source" not in field_labels


def test_onepassword_non_login_credential_with_migration_origin():
    """Test that non-LOGIN credentials also get the origin/source field correctly."""

    # Create a non-LOGIN credential (SECRET_TEXT)
    credential = Credential(
        id="test-secret",
        name="test-secret",
        type=CredentialType.SECRET_TEXT,
        scope=CredentialScope.GLOBAL,
        description="Test secret",
        secret="secret-value",
        source_platform="jenkins",
        target_platform="1password",
        metadata={
            "migration_origin": "Migrated from Jenkins"
        }
    )

    # Create OnePassword provider
    op_provider = OnePasswordCredentialProvider("TestVault")

    # Generate the template
    template = op_provider._create_op_item_template(credential)

    # Verify the template uses generic structure
    assert template["title"] == "test-secret"
    assert template["category"] == "SECURE_NOTE"  # Should map to SECURE_NOTE for SECRET_TEXT

    # Check that origin/source field is present with correct type
    fields = template["fields"]
    origin_field = None
    for field in fields:
        if field["label"] == "origin/source":
            origin_field = field
            break

    assert origin_field is not None
    assert origin_field["type"] == "STRING"  # Critical: Must be STRING, not CONCEALED
    assert origin_field["value"] == "Migrated from Jenkins"


def test_onepassword_non_migrated_credential_gets_notesplain():
    """Test that non-migrated credentials still get the notesPlain field."""

    # Create a non-migrated credential (no migration_origin)
    credential = Credential(
        id="regular-cred",
        name="regular-cred",
        type=CredentialType.USERNAME_PASSWORD,
        scope=CredentialScope.GLOBAL,
        description="This is a regular credential",
        username="user",
        password="pass",
        source_platform="jenkins",
        target_platform="1password",
        metadata={
            "some_other_field": "value"
            # No migration_origin field
        }
    )

    # Create OnePassword provider
    op_provider = OnePasswordCredentialProvider("TestVault")

    # Generate the template
    template = op_provider._create_op_item_template(credential)

    # Check that notesPlain field IS present
    fields = template["fields"]
    field_labels = [f["label"] for f in fields]

    assert "notesPlain" in field_labels  # Should be present for non-migrated
    assert "origin/source" not in field_labels  # Should NOT be present for non-migrated

    # Verify notesPlain field content
    notesplain_field = next((f for f in fields if f["label"] == "notesPlain"), None)
    assert notesplain_field is not None
    assert notesplain_field["type"] == "STRING"
    assert notesplain_field["value"] == "This is a regular credential"


if __name__ == "__main__":
    print("Testing 1Password origin/source field creation...")

    try:
        test_onepassword_credential_with_migration_origin()
        print("✓ test_onepassword_credential_with_migration_origin passed")
    except Exception as e:
        print(f"✗ test_onepassword_credential_with_migration_origin failed: {e}")

    try:
        test_onepassword_credential_without_migration_origin()
        print("✓ test_onepassword_credential_without_migration_origin passed")
    except Exception as e:
        print(f"✗ test_onepassword_credential_without_migration_origin failed: {e}")

    try:
        test_onepassword_non_login_credential_with_migration_origin()
        print("✓ test_onepassword_non_login_credential_with_migration_origin passed")
    except Exception as e:
        print(f"✗ test_onepassword_non_login_credential_with_migration_origin failed: {e}")

    try:
        test_onepassword_non_migrated_credential_gets_notesplain()
        print("✓ test_onepassword_non_migrated_credential_gets_notesplain passed")
    except Exception as e:
        print(f"✗ test_onepassword_non_migrated_credential_gets_notesplain failed: {e}")

    print("All tests completed!")
