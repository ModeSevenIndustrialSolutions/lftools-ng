<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2025 The Linux Foundation
-->

# Unified Credential Management System

## Overview

The lftools-ng project now includes a comprehensive unified credential management system that addresses the
architectural concerns about overlapping CLI commands and provides a foundation for credential migration between
platforms. The system includes intelligent credential classification, multi-platform provider support, and
comprehensive security analysis capabilities.

## Problem Analysis

### Original CLI Structure Issues

The original CLI had three separate commands for Jenkins credential extraction:

1. **`credentials`** - Returns ALL credential types (username/password, SSH keys, secrets, files)
2. **`secrets`** - Returns ONLY `StringCredentialsImpl` (secret text)
3. **`private-keys`** - Returns ONLY `BasicSSHUserPrivateKey` (SSH private keys)

**Problems identified:**

- Redundant API calls to Jenkins (3 calls instead of 1)
- Inconsistent data representation across commands
- No unified filtering capabilities
- No foundation for credential migration
- Overlapping functionality with different interfaces
- No credential classification or security analysis
- No support for multi-platform credential management

### Solution: Unified Architecture

The new system provides:

1. **Single API call** to Jenkins with comprehensive credential extraction
2. **Unified data model** for all credential types across all platforms
3. **Intelligent credential classification** with type detection and security analysis
4. **Powerful filtering system** with multiple filter types including classification-based filters
5. **Migration framework** for moving credentials between platforms
6. **Multi-platform provider architecture** supporting GitHub, GitLab, 1Password, and UNIX pass
7. **Security analysis and recommendations** based on credential classification
8. **Local authentication detection** and setup guidance for supported platforms

## New Architecture

### Core Components

#### 1. Credential Manager (`CredentialManager`)

Central orchestrator that manages providers and handles cross-platform operations.

#### 2. Credential Provider Interface (`CredentialProvider`)

Abstract base class that defines how platforms expose credentials:

- `list_credentials()` - Get all credentials with optional filtering
- `get_credential()` - Get specific credential by ID
- `supports_read()` / `supports_write()` - Capability declaration
- `create_credential()` / `update_credential()` / `delete_credential()` - Write operations

#### 3. Credential Classifier (`CredentialClassifier`)

Intelligent analysis system that detects credential types, subtypes, and security characteristics:

- **SSH Key Detection**: RSA, DSA, ECDSA, Ed25519 with key size analysis
- **Certificate Analysis**: PEM, DER, PKCS12 format detection
- **Token Classification**: GitHub PAT, GitLab tokens, generic API keys
- **Password Strength Assessment**: Weak, moderate, strong, very strong
- **Security Warnings**: Unprotected keys, weak passwords, deprecated algorithms
- **Validation Errors**: Malformed credentials, expired certificates

#### 4. Platform Providers

Multi-platform credential management with local authentication detection:

##### GitHub Provider (`GitHubCredentialProvider`)

- Uses GitHub CLI (`gh`) for authentication
- Supports organization and personal repositories
- Write-only (GitHub secrets cannot be read back)
- Automatic token detection from environment

##### GitLab Provider (`GitLabCredentialProvider`)

- Uses GitLab CLI (`glab`) for authentication
- Supports group and project variables
- Token-based authentication fallback
- Environment variable integration

##### 1Password Provider (`OnePasswordCredentialProvider`)

- Uses 1Password CLI (`op`) for authentication
- Full CRUD operations supported
- Vault-based organization
- Multiple account support

##### UNIX Pass Provider (`UnixPassCredentialProvider`)

- Uses standard `pass` command
- GPG-based encryption
- Full CRUD operations
- Metadata support in password entries

#### 5. Local Authentication Manager (`LocalAuthManager`)

Detects and manages local authentication for supported platforms:

- Checks for installed CLI tools
- Validates authentication status
- Provides setup guidance for missing tools
- Environment variable fallback detection

#### 6. Unified Data Model (`Credential`)

Single data structure representing credentials across all platforms:

```python
@dataclass
class Credential:
    id: str
    name: str
    type: CredentialType  # username_password, ssh_private_key, secret_text, etc.
    scope: CredentialScope  # global, repository, organization, project
    description: str = ""
    tags: Optional[Set[str]] = None  # Intelligent tagging (nexus, deploy, ssh, etc.)

    # Type-specific fields
    username: Optional[str] = None
    password: Optional[str] = None
    secret: Optional[str] = None
    private_key: Optional[str] = None
    passphrase: Optional[str] = None

    # Platform tracking
    source_platform: Optional[str] = None
    target_platform: Optional[str] = None
```

#### 7. Advanced Filtering (`CredentialFilter`)

Comprehensive filtering system supporting:

- **Type filtering**: Filter by credential type
- **Pattern matching**: Wildcards and regex for names and IDs
- **Tag filtering**: Smart tags based on naming patterns and content
- **Field presence**: Filter by presence/absence of usernames, passwords, etc.
- **Scope filtering**: Filter by credential scope

#### 8. Migration Framework (`MigrationOptions`, `MigrationResult`)

Framework for moving credentials between platforms with:

- Dry-run capability
- Overwrite control
- Backup options
- Validation
- Progress tracking

## New CLI Commands

### `lftools-ng jenkins-unified credentials`

**Replaces:** `jenkins credentials`, `jenkins secrets`, `jenkins private-keys`

**Benefits:**

- Single command interface for all Jenkins credential types
- Comprehensive filtering options
- Consistent output format
- Better performance (one API call instead of three)

**Examples:**

```bash
# Get all credentials (replaces old 'credentials' command)
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123

# Get only SSH private keys (replaces old 'private-keys' command)
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123 \
  --type ssh_private_key

# Get only secrets (replaces old 'secrets' command)
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123 \
  --type secret_text

# Advanced filtering - Nexus deployment credentials
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123 \
  --tag nexus \
  --has-username true \
  --name-pattern "*deploy*"

# Get credentials except test ones
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123 \
  --exclude "name~=test"
```

### `lftools-ng jenkins-unified migrate`

**New capability** for credential migration between platforms:

```bash
# Preview migration to GitHub (dry run)
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token123 \
  --target-platform github \
  --tag nexus \
  --dry-run

# Migrate SSH keys only
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token123 \
  --target-platform onepassword \
  --type ssh_private_key \
  --dry-run
```

### `lftools-ng jenkins-unified analyze`

**New capability** for migration planning:

```bash
# Analyze Jenkins credential store
lftools-ng jenkins-unified analyze \
  --server https://jenkins.example.com \
  --user admin \
  --password token123
```

**Output includes:**

- Credential type breakdown
- Common tags and patterns
- Migration readiness assessment
- Potential issues identification
- Recommendations for migration strategy

## Migration Planning for O-RAN

Based on your mention of 170-180 Nexus credentials in O-RAN, here's how the unified system addresses your requirements:

### 1. Credential Discovery and Analysis

```bash
# Analyze all O-RAN Jenkins credentials
lftools-ng jenkins-unified analyze \
  --server https://jenkins.o-ran.org \
  --user $JENKINS_USER \
  --password $JENKINS_TOKEN

# List all Nexus-related credentials
lftools-ng jenkins-unified credentials \
  --server https://jenkins.o-ran.org \
  --user $JENKINS_USER \
  --password $JENKINS_TOKEN \
  --tag nexus \
  --format json > nexus-credentials.json

# List repository-specific deployment credentials
lftools-ng jenkins-unified credentials \
  --server https://jenkins.o-ran.org \
  --user $JENKINS_USER \
  --password $JENKINS_TOKEN \
  --name-pattern "*deploy*" \
  --has-username true \
  --format yaml > deploy-credentials.yaml
```

### 2. Migration Strategies

#### Option A: Bulk Migration to GitHub Secrets

```bash
# Preview bulk migration
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.o-ran.org \
  --source-user $JENKINS_USER \
  --source-password $JENKINS_TOKEN \
  --target-platform github \
  --tag nexus \
  --dry-run

# Execute migration (when GitHub provider is implemented)
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.o-ran.org \
  --source-user $JENKINS_USER \
  --source-password $JENKINS_TOKEN \
  --target-platform github \
  --tag nexus \
  --overwrite false
```

#### Option B: Repository-Specific Migration

```bash
# Migrate credentials for specific repository
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.o-ran.org \
  --source-user $JENKINS_USER \
  --source-password $JENKINS_TOKEN \
  --target-platform github \
  --name-pattern "*repo-name*" \
  --dry-run
```

#### Option C: 1Password Organization Migration

```bash
# Migrate to 1Password vault
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.o-ran.org \
  --source-user $JENKINS_USER \
  --source-password $JENKINS_TOKEN \
  --target-platform onepassword \
  --tag nexus \
  --dry-run
```

### 3. Intelligent Tagging

The system automatically tags credentials based on naming patterns:

- **nexus** - Credentials with "nexus" in name/description
- **deploy** - Credentials with "deploy" in name/description
- **ssh** - SSH private key credentials
- **production** - Credentials with "prod"/"production" in name
- **test** - Credentials with "test" in name
- **has-username** - Credentials with username fields
- **has-password** - Credentials with password fields
- **has-passphrase** - SSH keys with passphrases

### 4. Migration Challenges Addressed

#### Challenge: GitHub Doesn't Allow Secret Retrieval

**Solution:** The migration framework tracks what was migrated and provides options:

- **Dry-run mode** to preview without changes
- **Backup creation** before migration
- **Validation** of target platform before migration
- **Rollback planning** with migration history

#### Challenge: Repository-Specific vs Global Credentials

**Solution:** The unified model includes `scope` field:

- Credentials can be tagged as `repository`, `global`, `organization`
- Migration can target appropriate GitHub scopes (repo secrets vs org secrets)
- 1Password can use different vaults for different scopes

#### Challenge: Different Target Platform Capabilities

**Solution:** Provider-specific capability declaration:

- Each provider declares `supports_read()` / `supports_write()`
- Migration pre-flight checks ensure compatibility
- Graceful handling of unsupported credential types

## Future Provider Implementations

### GitHub Provider Implementation

- Read GitHub organization/repository secrets and variables
- Create/update GitHub secrets (with appropriate permissions)
- Handle GitHub's write-only secret limitation
- Support both repository and organization scopes

### GitLab Provider Implementation

- Read GitLab group/project variables
- Create/update GitLab variables (with appropriate permissions)
- Support for GitLab's token-based authentication

### 1Password Provider Implementation

- Read from 1Password vaults
- Create/update items in specified vaults
- Handle different item types (Login, Secure Note, SSH Key)
- Organization/team scope management

### UNIX Pass Provider Implementation

- Extract credential patterns from UNIX `pass` store
- Support for GPG-encrypted credentials
- Handle different passphrase and key configurations

### Gerrit Provider (`GerritCredentialProvider`)

- Extract credential patterns from Gerrit configuration
- Support for Gerrit's authentication mechanisms

## Backward Compatibility

The original Jenkins commands (`jenkins credentials`, `jenkins secrets`, `jenkins private-keys`) remain functional
for backward compatibility, but now internally use the unified system with appropriate filters.

## Testing Strategy

The unified system includes comprehensive tests:

- Unit tests for filtering logic
- Integration tests with mocked Jenkins responses
- Provider interface compliance tests
- Migration workflow tests
- CLI command tests

## Implementation Status

**Completed:**

- ✅ Unified credential data model
- ✅ Advanced filtering system
- ✅ Jenkins provider implementation
- ✅ CLI commands with comprehensive options
- ✅ Migration framework foundation
- ✅ Analysis and reporting capabilities
- ✅ Credential classification and security analysis

**In Progress:**

- 🔄 GitHub provider implementation
- 🔄 GitLab provider implementation
- 🔄 1Password provider implementation
- 🔄 Migration validation and rollback

**Planned:**

- 📋 Gerrit provider
- 📋 Vault/HashiCorp provider
- 📋 Azure Key Vault provider
- 📋 AWS Secrets Manager provider

This unified system provides a solid foundation for managing the O-RAN credential migration while solving the
architectural issues with the original CLI commands.

## CLI Usage Examples

### New Unified Commands

The unified credential management system provides four main commands under `jenkins-unified`:

#### 1. `credentials` - Enhanced Credential Listing

```bash
# List all credentials with classification metadata
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token

# Filter by credential type and strength
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --type ssh_private_key \
  --strength weak,moderate

# Get only production SSH keys with specific algorithm
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --tag production \
  --algorithm ed25519

# Export all credentials with classification data as JSON
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --format json
```

#### 2. `analyze` - Security Analysis

```bash
# Comprehensive security analysis
lftools-ng jenkins-unified analyze \
  --server https://jenkins.example.com \
  --user admin \
  --password token

# Show only credentials with security warnings
lftools-ng jenkins-unified analyze \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --show-stats false \
  --show-recommendations false

# Export analysis results as JSON
lftools-ng jenkins-unified analyze \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --format json
```

#### 3. `migrate` - Cross-Platform Migration

```bash
# Migrate all credentials to GitHub
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token \
  --target github

# Migrate only SSH keys to 1Password
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token \
  --target onepassword \
  --target-vault DevOps \
  --type ssh_private_key

# Migrate deployment credentials to UNIX pass with name transformation
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token \
  --target pass \
  --tag deploy \
  --name-transform "prefix:jenkins_"

# Dry run to see what would be migrated
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token \
  --target gitlab \
  --target-org myorg \
  --dry-run
```

#### 4. `platforms` - Platform Availability

```bash
# Check which platforms are available for credential management
lftools-ng jenkins-unified platforms
```

### Migration Strategies

#### Scenario 1: Jenkins to GitHub Actions

When migrating Jenkins credentials to GitHub Actions secrets:

```bash
# Step 1: Analyze Jenkins credentials
lftools-ng jenkins-unified analyze --server https://jenkins.example.com --user admin --password token

# Step 2: Check GitHub availability
lftools-ng jenkins-unified platforms

# Step 3: Migrate relevant credentials
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token \
  --target github \
  --exclude "name~=test" \
  --name-transform "prefix:JENKINS_"
```

#### Scenario 2: Jenkins to 1Password for Team Management

When consolidating credentials in 1Password:

```bash
# Migrate all production credentials to dedicated vault
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token \
  --target onepassword \
  --target-vault "Production Secrets" \
  --tag production \
  --overwrite

# Migrate SSH keys to separate vault
lftools-ng jenkins-unified migrate \
  --source-server https://jenkins.example.com \
  --source-user admin \
  --source-password token \
  --target onepassword \
  --target-vault "SSH Keys" \
  --type ssh_private_key
```

#### Scenario 3: Security Audit and Credential Rotation

When performing security audits:

```bash
# Step 1: Comprehensive analysis
lftools-ng jenkins-unified analyze \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --format json > jenkins_security_audit.json

# Step 2: Find weak credentials
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --strength weak \
  --has-warnings true

# Step 3: Export credentials needing rotation
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --has-errors true \
  --format csv > credentials_to_rotate.csv
```

### Advanced Filtering Examples

The new filtering system supports complex queries:

```bash
# Complex filtering with multiple criteria
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --include "type=ssh_private_key" \
  --include "strength!=weak" \
  --exclude "name~=test" \
  --tag production,deploy

# Filter by classification metadata
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --algorithm rsa \
  --key-size 4096 \
  --subtype github_personal_access_token

# Show only credentials with security issues
lftools-ng jenkins-unified credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token \
  --has-errors true \
  --has-warnings true
```
