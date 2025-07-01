<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2025 The Linux Foundation
-->

# SSH-Based Gerrit Repository Discovery Implementation

## Overview

This document describes the implementation of SSH-based Gerrit repository discovery in lftools-ng, replacing all HTTP/HTTPS-based Gerrit access to avoid Cloudflare bot protection and leverage local SSH authentication.

## Key Changes

### 1. New SSH-Based Infrastructure

- **GerritSSHClient** (`src/lftools_ng/core/gerrit_ssh.py`)
  - SSH-based Gerrit project listing via `gerrit ls-projects --format json --all`
  - Connects to Gerrit via SSH on TCP/29418
  - Respects local SSH configuration (`~/.ssh/config`)
  - Uses SSH agent, hardware tokens (YubiKey), and secure enclave keys (Secretive)

- **Enhanced RepositoryDiscovery** (`src/lftools_ng/core/repository_discovery.py`)
  - Integrated SSH-based Gerrit discovery
  - Removed all HTTP/HTTPS Gerrit API access
  - Bidirectional repository name mapping between Gerrit and GitHub

### 2. SSH Configuration Integration

- **SSHConfigParser** (existing, enhanced usage)
  - Reads `~/.ssh/config` for usernames and connection settings
  - Supports SSH agent forwarding and key-based authentication
  - Works with modern SSH authentication methods

- **ConnectivityTester** (existing, leveraged)
  - Tests SSH connectivity before attempting repository discovery
  - Provides detailed error reporting for SSH issues

### 3. Repository Discovery Workflow

1. **Gerrit Discovery** (SSH-based):

   ```bash
   ssh username@gerrit.example.org -p 29418 gerrit ls-projects --format json --all
   ```

2. **GitHub Discovery** (API-based):

   ```bash
   https://api.github.com/orgs/{organization}/repos
   ```

3. **Cross-Platform Mapping**:
   - Maps Gerrit paths to GitHub repository names
   - Handles nested Gerrit projects (e.g., `project/subproject/repo`)
   - Provides bidirectional lookup capabilities

## Benefits

### 1. Cloudflare Bot Protection Bypass

- SSH connections (TCP/29418) bypass Cloudflare HTTP/HTTPS bot detection
- No more rate limiting or blocking of automated repository discovery
- Reliable access to Gerrit instances behind CDNs

### 2. Enhanced Security

- Leverages existing SSH key infrastructure
- Supports hardware security keys (YubiKey, etc.)
- Works with secure enclave solutions (macOS Secretive)
- No need to store or manage additional API tokens

### 3. Improved Reliability

- SSH connections are more reliable than HTTP scraping
- Native Gerrit SSH API provides structured JSON output
- Better error handling and connectivity diagnostics

### 4. Local Configuration Respect

- Uses existing SSH configuration in `~/.ssh/config`
- Respects SSH agent settings and key preferences
- Works with SSH multiplexing and connection reuse

## Usage Examples

### Basic Repository Discovery

```bash
# Discover repositories for ONAP project via SSH
lftools-ng projects repositories rebuild --force

# List discovered repositories
lftools-ng projects repositories list ONAP
```

### SSH Configuration Example

```ssh
# ~/.ssh/config
Host gerrit.onap.org
    User myusername
    Port 29418
    IdentityFile ~/.ssh/gerrit_key

Host gerrit.o-ran-sc.org
    User myusername
    Port 29418
    IdentityFile ~/.ssh/gerrit_key
```

### Testing SSH Connectivity

```python
from lftools_ng.core.gerrit_ssh import GerritSSHClient

client = GerritSSHClient()
success, message = client.test_connection('https://gerrit.onap.org')
print(f"SSH test: {message}")

projects = client.list_projects('https://gerrit.onap.org')
print(f"Found {len(projects)} projects via SSH")
```

## Implementation Details

### Gerrit SSH Commands Used

- `gerrit version` - Test connectivity and verify Gerrit version
- `gerrit ls-projects --format json --all` - List all projects with metadata

### Repository Mapping Logic

- **Gerrit → GitHub**: `project/subproject/repo` → `repo` or `project-subproject-repo`
- **GitHub → Gerrit**: Reverse lookup with candidate matching
- **Bidirectional**: Maintains mapping tables for cross-platform operations

### Error Handling

- SSH connection timeouts and retries
- Authentication failure detection
- Graceful fallback for missing SSH configuration
- Detailed logging for troubleshooting

## Migration from HTTP/HTTPS

### Removed Components

- HTTP-based Gerrit API access (`/a/projects/` endpoints)
- Web scraping of Gerrit interfaces
- HTTP authentication and session management

### Preserved Components

- GitHub API access (still uses HTTPS as appropriate)
- Existing SSH infrastructure (enhanced and integrated)
- Repository database format and CLI commands

## Testing

The implementation has been tested with:

- ONAP Gerrit (441 projects discovered)
- O-RAN-SC Gerrit (158 projects discovered)
- Multiple SSH authentication methods
- Various SSH agent configurations

## Future Enhancements

1. **Parallel SSH Connections**: Discover from multiple Gerrit instances concurrently
2. **SSH Connection Pooling**: Reuse SSH connections for multiple operations
3. **Enhanced Mapping**: Machine learning-based repository name mapping
4. **SSH Key Management**: Integration with key management tools

## Troubleshooting

### Common Issues

1. **SSH Authentication Failure**
   - Verify SSH keys are added to Gerrit
   - Check SSH agent is running: `ssh-add -l`
   - Test manual connection: `ssh username@gerrit.example.org -p 29418 gerrit version`

2. **No Username Configured**
   - Add SSH config entry for the Gerrit host
   - Ensure username matches Gerrit account

3. **Connection Timeout**
   - Verify port 29418 is accessible
   - Check firewall and network connectivity
   - Confirm Gerrit SSH is enabled

### Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
# Enable detailed SSH and discovery logging
```

## Conclusion

The SSH-based Gerrit repository discovery implementation provides a robust, secure, and reliable method for enumerating repositories across Linux Foundation projects. By eliminating HTTP/HTTPS dependencies for Gerrit access, the system bypasses modern bot protection mechanisms while leveraging proven SSH infrastructure that developers already use for daily operations.
