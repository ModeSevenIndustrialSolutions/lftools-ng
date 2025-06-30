# 1Password Migration Field Type Corrections

## Summary

Updated lftools-ng to ensure all future credential migrations from Jenkins to 1Password create the "origin/source" field with the correct field type (`STRING` instead of `CONCEALED`).

## Changes Made

### 1. OnePasswordCredentialProvider Updates

**File:** `src/lftools_ng/core/platform_providers.py`

- Updated `_create_op_item_template()` method to check for `migration_origin` metadata
- When `migration_origin` is present, creates an "origin/source" field with type `STRING`
- Applies to both LOGIN items and generic items (SECURE_NOTE, etc.)

**Before:**
```python
# Only created notesPlain field for description
if credential.description:
    fields.append({
        'label': 'notesPlain',
        'type': 'STRING',
        'value': credential.description
    })
```

**After:**
```python
# Creates both notesPlain and origin/source fields
if credential.description:
    fields.append({
        'label': 'notesPlain',
        'type': 'STRING',
        'value': credential.description
    })

# Add origin/source field for migrated credentials (using STRING type, not CONCEALED)
if credential.metadata and 'migration_origin' in credential.metadata:
    fields.append({
        'label': 'origin/source',
        'type': 'STRING',
        'value': credential.metadata['migration_origin']
    })
```

### 2. Repository Migration Updates

**Files:**
- `src/lftools_ng/commands/repository_migrate.py`
- `src/lftools_ng/commands/oran_migrate.py`

- Added `migration_origin` metadata to all credentials created during repository migrations

**Before:**
```python
metadata={
    "github_url": mapping.github_url,
    "project": mapping.project,
    "migration_source": mapping.jenkins_credential_id,
    "migration_type": "repository_deployment"
}
```

**After:**
```python
metadata={
    "github_url": mapping.github_url,
    "project": mapping.project,
    "migration_source": mapping.jenkins_credential_id,
    "migration_type": "repository_deployment",
    "migration_origin": "Migrated from Jenkins"  # This will create the origin/source field as STRING type
}
```

### 3. General Jenkins Migration Updates

**File:** `src/lftools_ng/commands/jenkins.py`

- Updated the `migrate_credentials()` command to add migration metadata for all credentials

**Added:**
```python
# Add migration metadata for origin/source field (STRING type for 1Password)
if cred.metadata is None:
    cred.metadata = {}
cred.metadata["migration_origin"] = "Migrated from Jenkins"
```

### 4. Credential Manager Updates

**File:** `src/lftools_ng/core/credential_manager.py`

- Updated `_prepare_credential_for_migration()` method to automatically add migration_origin for Jenkins credentials

**Added:**
```python
# Add migration origin for 1Password origin/source field (STRING type)
if credential.source_platform == "jenkins":
    migrated.metadata["migration_origin"] = "Migrated from Jenkins"
```

## Field Type Specification

The changes ensure that the "origin/source" field in 1Password items is created with the correct field specification:

```json
{
  "label": "origin/source",
  "type": "STRING",
  "value": "Migrated from Jenkins"
}
```

**Not** as a concealed/password field:
```json
{
  "label": "origin/source",
  "type": "CONCEALED",  // ← This was the problem
  "value": "Migrated from Jenkins"
}
```

## Field Duplication Prevention

To avoid field duplication in migrated credentials, the OnePasswordCredentialProvider now conditionally creates the "notesPlain" field:

- **For migrated credentials** (when `migration_origin` metadata is present): Only creates "origin/source" field, skips "notesPlain"
- **For non-migrated credentials** (when `migration_origin` metadata is absent): Creates "notesPlain" field for the description

This ensures that migrated credentials have clean field structures without duplicate information:

### Migrated Credential Fields:
```json
{
  "username": {"type": "STRING", "value": "deploy"},
  "password": {"type": "CONCEALED", "value": "secret123"},
  "origin/source": {"type": "STRING", "value": "Migrated from Jenkins"},
  "website": {"type": "URL", "value": "https://github.com/project/repo"}
}
```

### Non-Migrated Credential Fields:
```json
{
  "username": {"type": "STRING", "value": "user"},
  "password": {"type": "CONCEALED", "value": "pass"},
  "notesPlain": {"type": "STRING", "value": "Regular credential description"}
}
```

## Impact on Future Migrations

### For ONAP Project
When migrating ONAP credentials in the future:
1. Use the repository migration command: `repository-migrate repository`
2. Or use the general migration command: `lftools-ng jenkins migrate`
3. Both will now automatically create the correct "origin/source" field type

### For Other Linux Foundation Projects
All future migrations using lftools-ng will now:
- Automatically add "origin/source" field with `STRING` type (visible in 1Password UI)
- Maintain consistency with the O-RAN-SC corrected credential format
- No longer require manual field type correction scripts

## Testing

Created comprehensive test suite (`tests/test_onepassword_migration_field_types.py`) that verifies:
- LOGIN items get correct origin/source field with STRING type
- Non-LOGIN items (SECURE_NOTE, etc.) get correct origin/source field with STRING type
- Credentials without migration metadata don't get unnecessary origin/source fields
- All field types are preserved correctly (username=STRING, password=CONCEALED, etc.)

## Verification

To verify the changes work:

```bash
# Test repository migration credential creation
python -c "
from lftools_ng.commands.repository_migrate import ProjectAwareMigrationManager, RepositoryCredentialMapping
from lftools_ng.core.platform_providers import OnePasswordCredentialProvider

# Create test credential
mapping = RepositoryCredentialMapping('jenkins-id', 'repo-name', 'https://github.com/test/repo', 'user', 'pass', 'Project')
manager = ProjectAwareMigrationManager()
credential = manager.create_onepassword_credential(mapping)

# Generate 1Password template
op_provider = OnePasswordCredentialProvider('TestVault')
template = op_provider._create_op_item_template(credential)

# Check origin/source field
origin_field = next((f for f in template['fields'] if f['label'] == 'origin/source'), None)
print(f'Origin field type: {origin_field[\"type\"]}')  # Should print: STRING
"
```

This ensures all future migrations will create credentials that match the corrected O-RAN-SC format without requiring additional field type correction scripts.
