# ONAP Password Migration Guide

This guide explains how to migrate passwords from the ONAP (ECOMP) Jenkins server to the LF Networking 1Password vault using the lftools-ng CLI.

## Overview

The migration will transfer repository-specific credentials used for publishing artifacts to Nexus2/3 servers from Jenkins to 1Password. Each migrated credential will have an "origin/source" field containing "Migrated from Jenkins" for tracking purposes.

## Prerequisites

1. **lftools-ng CLI installed**: Ensure you have the latest version with migration support
2. **1Password CLI installed**: The migration uses the `op` command-line tool
3. **Jenkins access**: Username and password/API token for the ONAP Jenkins server
4. **1Password access**: Authenticated with the LF Networking account

## 1Password Setup

- **Account**: `lfnetworking.1password.com`
- **Vault**: `ONAP`

## Authentication Setup

### Jenkins Authentication
Set environment variables for Jenkins access:
```bash
export JENKINS_SERVER="https://jenkins.onap.org"  # Replace with actual ONAP Jenkins URL
export JENKINS_USER="your-jenkins-username"
export JENKINS_PASSWORD="your-jenkins-api-token"
```

### 1Password Authentication
Login to 1Password CLI:
```bash
op account add --address lfnetworking.1password.com
op signin
```

## Migration Commands

### 1. Dry Run (Recommended First Step)

Before performing the actual migration, run a dry run to see what credentials will be migrated:

```bash
lftools-ng migrate repository \
  --jenkins-server $JENKINS_SERVER \
  --jenkins-user $JENKINS_USER \
  --jenkins-password $JENKINS_PASSWORD \
  --project "ONAP" \
  --vault "ONAP" \
  --account "lfnetworking.1password.com" \
  --filter-pattern "deployment" \
  --dry-run
```

**Note**: You may need to adjust the `--filter-pattern` based on how the ONAP Jenkins credentials are named. Common patterns include:
- `"deployment"` (default)
- `"nexus deployment"`
- `"artifact deployment"`
- `"repository deployment"`

### 2. Full Migration

Once you've verified the dry run results, perform the actual migration:

```bash
lftools-ng migrate repository \
  --jenkins-server $JENKINS_SERVER \
  --jenkins-user $JENKINS_USER \
  --jenkins-password $JENKINS_PASSWORD \
  --project "ONAP" \
  --vault "ONAP" \
  --account "lfnetworking.1password.com" \
  --filter-pattern "deployment"
```

### 3. Single Credential Migration (Optional)

If you need to migrate a specific credential first or separately:

```bash
lftools-ng migrate repository \
  --jenkins-server $JENKINS_SERVER \
  --jenkins-user $JENKINS_USER \
  --jenkins-password $JENKINS_PASSWORD \
  --project "ONAP" \
  --vault "ONAP" \
  --account "lfnetworking.1password.com" \
  --single "repository-name"
```

## Migration Process

The migration tool will:

1. **Connect to Jenkins**: Authenticate and list all credentials
2. **Filter credentials**: Find credentials matching the specified pattern
3. **Extract repository names**: Parse repository names from credential IDs
4. **Generate GitHub URLs**: Create GitHub URLs using the ONAP project configuration
5. **Create 1Password items**: Each credential becomes a LOGIN item with:
   - **Title**: Repository name
   - **Username**: From Jenkins credential
   - **Password**: From Jenkins credential (concealed)
   - **Website**: GitHub repository URL
   - **Origin/Source**: "Migrated from Jenkins" (text field)

## Verification

After migration, verify the credentials in 1Password:

1. Login to `lfnetworking.1password.com`
2. Navigate to the "ONAP" vault
3. Check that migrated credentials have:
   - Correct username and password
   - "origin/source" field with "Migrated from Jenkins"
   - Proper GitHub repository URLs

## Troubleshooting

### Common Issues

**Jenkins Connection Failed**:
- Verify the Jenkins server URL
- Check username and password/API token
- Ensure network connectivity

**1Password Authentication Failed**:
- Run `op signin` again
- Verify account and vault names
- Check CLI version with `op --version`

**No Credentials Found**:
- Try different filter patterns:
  ```bash
  --filter-pattern "nexus"
  --filter-pattern "artifact"
  --filter-pattern "publish"
  ```
- Use `--verbose` flag for detailed logging

**Permission Denied**:
- Ensure you have admin access to the Jenkins server
- Verify 1Password vault permissions

### Custom Extraction Patterns

If repository names aren't extracted correctly, use a custom pattern:

```bash
--extraction-pattern "^(.+?)\s+repository\s+deployment$"
```

### Skip Validation

If 1Password setup validation fails but you're confident it's configured correctly:

```bash
--skip-validation
```

## Example Output

```
Repository Credentials Migration Tool

✅ Connected to Jenkins. Found 245 total credentials

Found 67 repository credentials matching 'deployment'

Repository Credentials Migration Plan
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Repository     ┃ Jenkins Credential ID                         ┃ Username                 ┃ GitHub URL                               ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ aai-common     │ aai-common repository deployment              │ deployment               │ https://github.com/onap/aai-common      │
│ aai-data-router│ aai-data-router repository deployment         │ deployment               │ https://github.com/onap/aai-data-router │
│ ...            │ ...                                           │ ...                      │ ...                                      │
└────────────────┴───────────────────────────────────────────────┴──────────────────────────┴──────────────────────────────────────────┘

Proceed with migrating 67 credentials to 1Password? [y/N]: y

Starting migration...
Migrating 1/67: aai-common
  ✅ Created credential for aai-common
Migrating 2/67: aai-data-router
  ✅ Created credential for aai-data-router
...

Migration Summary:
✅ 67 credentials migrated successfully
```

## Support

For issues or questions about the migration process, contact the Linux Foundation Release Engineering team.
