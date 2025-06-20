<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2025 The Linux Foundation
-->

# GitHub Organization Discovery

This document describes the GitHub organization discovery feature added to
lftools-ng, which automatically discovers and tracks GitHub organizations for
Linux Foundation projects.

## Overview

The GitHub discovery feature enhances the project rebuild process by
automatically discovering GitHub organizations/mirrors for projects using
different discovery methods. This ensures that projects have accurate GitHub
organization information for future GitHub-related operations.

## Discovery Methods

The system uses different methods to discover GitHub organizations, attempting
them in order until a match occurs:

### 1. Existing Verification

- Checks if the project already has a `github_mirror_org` field
- Verifies that the organization still exists on GitHub
- If verification fails, continues with other discovery methods

### 2. Gerrit Mirror Discovery

- Queries the project's Gerrit server for mirror configurations
- Attempts to access Gerrit REST API endpoints to find GitHub mirrors
- Falls back to scraping the Gerrit web interface if API access fails
- Looks for GitHub organization patterns in the response

### 3. Direct Name Matching

- Tries the project name and aliases directly as GitHub organization names
- Cleans names by removing common words like "project", "foundation", etc.
- Tests variations with different separators (hyphens, underscores)

### 4. Name Variation Testing

- Generates common variations of project names:
  - With prefixes: `{name}-project`, `project-{name}`, `{name}-foundation`
  - With suffixes: `{name}org`, `{name}foundation`
  - Without separators: removes hyphens and underscores
  - Different separators: converts between hyphens and underscores

### 5. Homepage/Documentation Search

- Searches project homepage and documentation URLs for GitHub links
- Generates candidate URLs based on project name and aliases:
  - `https://{name}.org`
  - `https://{name}.io`
  - `https://www.{name}.org`
- Scrapes pages looking for GitHub organization links

### 6. Wikipedia Search

- Searches Wikipedia for project information
- Uses both Wikipedia API summary and full page content
- Looks for GitHub organization mentions in project descriptions

## Usage

### Automatic Integration with Project Rebuild

GitHub discovery is automatically integrated into the project rebuild process and runs whenever projects are rebuilt or discovered:

```bash
# GitHub discovery runs automatically during project rebuild
lftools-ng projects rebuild-projects
```

The rebuild process will:

1. Fetch project configuration from the source
2. Extract project data
3. **Run GitHub discovery for each project**
4. Save enhanced project data with GitHub organizations

### Integration with Repository Commands

Once GitHub organizations exist, they enable repository enumeration and
management:

```bash
# List repositories (uses discovered GitHub orgs)
lftools-ng projects repositories list

# Get repository information
lftools-ng projects repositories info ONAP "aai/aai-common"

# List archived repositories
lftools-ng projects repositories archived
```

### Adding Projects

When adding new projects, GitHub discovery runs automatically during the next rebuild:

```bash
# Add a project (GitHub org will exist after next rebuild)
lftools-ng projects add-project "MyProject" --aliases "myproj,mp"

# Force rebuild to discover GitHub org now
lftools-ng projects rebuild-projects --force
```

### Viewing GitHub Organizations

The enhanced list command now shows GitHub organization information:

```bash
lftools-ng projects list
```

Output will include columns for:

- Project name
- Aliases
- **GitHub Organization**
- Gerrit domain

## Configuration

### Project Data Structure

Projects now include the following GitHub-related fields:

```yaml
projects:
  - name: "ONAP"
    primary_name: "ONAP"
    aliases: ["onap", "ECOMP"]
    github_mirror_org: "onap"  # Discovered automatically
    gerrit_url: "https://gerrit.onap.org"
    # ... other fields
```

### Discovery Settings

The discovery process includes built-in caching and verification:

- **Organization Verification**: Each discovered organization exists on GitHub
- **Caching**: Verified and non-existent organizations have cached status to avoid repeated API calls
- **Timeout Handling**: All HTTP requests have reasonable timeouts (10-30 seconds)
- **Error Handling**: Network errors and timeouts get logged but don't stop the discovery process

## Examples

### Example: Successful Discovery

```bash
$ lftools-ng projects rebuild-projects --force
Rebuilding projects database...
Starting GitHub organization discovery for projects...
✓ Found GitHub org for ONAP: onap
✓ Found GitHub org for OpenDaylight: opendaylight
✓ Found GitHub org for Anuket: opnfv
GitHub discovery completed. Enhanced 3 projects.
Completed rebuilding projects database
```

### Example: Project Rebuild with Discovery

```bash
$ lftools-ng projects rebuild-projects --force
Rebuilding projects database...
Starting GitHub organization discovery for projects...
Discovered GitHub org for ONAP: onap
Discovered GitHub org for OpenDaylight: opendaylight
Discovered GitHub org for Anuket: opnfv
GitHub discovery completed. Enhanced 3 projects.
Completed rebuilding projects database
Projects loaded: 15
Servers discovered: 8
```

### Example: Enhanced Project Listing

```bash
$ lftools-ng projects list
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃ Project       ┃ Aliases                 ┃ GitHub Org      ┃ Gerrit            ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│ ONAP          │ onap, ECOMP             │ onap            │ gerrit.onap.org   │
│ OpenDaylight  │ ODL, opendaylight       │ opendaylight    │ git.opendaylight… │
│ Anuket        │ OPNFV, anuket           │ opnfv           │ gerrit.opnfv.org  │
└───────────────┴─────────────────────────┴─────────────────┴───────────────────┘
```

## Benefits

1. **Automated Discovery**: No manual effort required to maintain GitHub organization mappings
2. **Diverse Methods**: Robust discovery using different sources (Gerrit, websites, Wikipedia)
3. **Verification**: All discovered organizations exist
4. **Integration**: Seamlessly integrated into project rebuild workflows
5. **Repository Management**: Enables comprehensive repository listing and management

## Repository Integration

The GitHub organization information discovered enables repository management commands:

- `lftools-ng projects repositories list` - List repositories across projects with Gerrit/GitHub mapping
- `lftools-ng projects repositories info` - Get detailed repository information
- `lftools-ng projects repositories archived` - List archived repositories

## Troubleshooting

### Common Issues

1. **Network Connectivity**: Ensure internet access for GitHub verification and website scraping
2. **Rate Limiting**: GitHub requests are rate-limited; large discovery runs may take time
3. **False Positives**: Some discovery methods may find unrelated organizations; verification helps reduce this

### Logging

Enable debug logging to see detailed discovery information:

```bash
export PYTHONPATH=/path/to/lftools-ng/src
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Your discovery command here
"
```

### Manual Override

If automatic discovery fails or finds incorrect organizations, you can manually edit the project configuration:

```bash
# Edit projects.yaml to manually specify GitHub org
# Then rebuild to apply changes
lftools-ng projects rebuild-projects --force
```

## API Reference

### GitHubDiscovery Class

```python
from lftools_ng.core.github_discovery import GitHubDiscovery

with GitHubDiscovery() as discovery:
    org = discovery.discover_github_organization({
        "name": "Project Name",
        "aliases": ["alias1", "alias2"],
        "gerrit_url": "https://gerrit.example.org"
    })
    print(f"Discovered organization: {org}")
```

### Key Methods

- `discover_github_organization(project_data)`: Main discovery method
- `_verify_github_org_exists(org_name)`: Verify organization exists
- `_generate_name_variations(name)`: Generate name variations for testing
- `_clean_organization_name(name)`: Clean names for GitHub compatibility
