<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2025 The Linux Foundation
-->

# Universal Filtering System for lftools-ng

The lftools-ng CLI now includes a comprehensive filtering system that allows you to filter results from all commands.
This filtering applies to both table output and JSON data returned by commands.

## Overview

The filtering system supports:

- **Include filters**: Only show results that match these criteria
- **Exclude filters**: Hide results that match these criteria
- **Field selection**: Show only specific fields in the output
- **Field exclusion**: Hide specific fields from the output

## Filter Syntax

Filters use a simple syntax: `field operator value`

### Supported Operators

| Operator | Alias | Description | Example |
|----------|-------|-------------|---------|
| `=` | `eq` | Equals (exact match) | `type=jenkins` |
| `!=` | `ne` | Not equals | `name!=test` |
| `~=` | `contains` | Contains substring | `name~=linux` |
| `!~=` | `not-contains` | Does not contain | `url!~=test` |
| `^=` | `starts-with` | Starts with | `name^=prod` |
| `$=` | `ends-with` | Ends with | `name$=_test` |
| `@=` | `regex` | Regular expression | `name@=.*[0-9]+.*` |
| `*=` | `glob` | Glob pattern | `name*=test-*` |
| `>` | `gt` | Greater than | `count>5` |
| `<` | `lt` | Less than | `count<10` |
| `>=` | `gte` | Greater than or equal | `count>=5` |
| `<=` | `lte` | Less than or equal | `count<=10` |
| `:empty` | `empty` | Field is empty/null | `description:empty` |
| `:not-empty` | `not-empty` | Field is not empty | `url:not-empty` |

### Nested Fields

You can access nested fields using dot notation:

- `config.enabled=true`
- `metadata.version>=2.0`
- `server.location~=virginia`

## Command Options

All commands now support these filtering options:

```bash
--include, -i     Include filters (can be used multiple times)
--exclude, -e     Exclude filters (can be used multiple times)
--fields          Fields to include (comma-separated)
--exclude-fields  Fields to exclude (comma-separated)
```

## Examples

### Basic Filtering

List only Jenkins servers:

```bash
lftools-ng projects servers --include 'type=jenkins'
```

List projects excluding test projects:

```bash
lftools-ng projects list --exclude 'name~=test'
```

### Multiple Filters

List Jenkins servers in Virginia:

```bash
lftools-ng projects servers --include 'type=jenkins' --include 'location~=virginia'
```

List active projects with GitHub mirrors:

```bash
lftools-ng projects list --include 'status=active' --include 'github_mirror_org:not-empty'
```

### Field Selection

Show only name and URL for servers:

```bash
lftools-ng projects servers --fields 'name,url'
```

Hide internal fields:

```bash
lftools-ng projects list --exclude-fields 'internal_id,created_at'
```

### Advanced Filtering

Using regex to find projects with version numbers:

```bash
lftools-ng projects list --include 'name@=.*v[0-9]+.*'
```

Using glob patterns:

```bash
lftools-ng projects list --include 'name*=linux-*'
```

Find servers with high project counts:

```bash
lftools-ng projects servers --include 'project_count>10'
```

### Jenkins Command Examples

Filter Jenkins credentials by type:

```bash
lftools-ng jenkins credentials --server https://jenkins.example.com \
  --user admin --password token \
  --include 'type=ssh'
```

Show only credential IDs and usernames:

```bash
lftools-ng jenkins credentials --server https://jenkins.example.com \
  --user admin --password token \
  --fields 'id,username'
```

Exclude test credentials:

```bash
lftools-ng jenkins credentials --server https://jenkins.example.com \
  --user admin --password token \
  --exclude 'id~=test'
```

## JSON Output with Filtering

Filtering works with all output formats:

```bash
# Filtered JSON output
lftools-ng projects list --include 'type=jenkins' --format json

# Filtered pretty JSON with specific fields
lftools-ng projects servers --fields 'name,url,type' --format json-pretty

# Filtered YAML output
lftools-ng projects list --exclude 'name~=test' --format yaml
```

## Tips and Best Practices

1. **Quote complex values**: Use quotes around values with spaces or special characters:

   ```bash
   --include 'description="Test Environment"'
   ```

2. **Combine include and exclude**: Use both types of filters for precise control:

   ```bash
   --include 'type=jenkins' --exclude 'name~=test'
   ```

3. **Use field selection for cleaner output**: Reduce noise by showing only relevant fields:

   ```bash
   --fields 'name,status,url'
   ```

4. **Test filters with table output first**: See your filters in action before switching to JSON:

   ```bash
   # Test first
   lftools-ng projects list --include 'type=jenkins'
   # Then export
   lftools-ng projects list --include 'type=jenkins' --format json > jenkins-servers.json
   ```

5. **Use empty/not-empty for data quality**: Find incomplete records:

   ```bash
   --include 'description:empty'  # Find records missing descriptions
   --exclude 'url:empty'          # Exclude records without URLs
   ```

## Integration with Existing Commands

The filtering system is integrated into all major commands:

- `lftools-ng projects list` - Filter project listings
- `lftools-ng projects servers` - Filter server listings
- `lftools-ng jenkins credentials` - Filter Jenkins credentials
- `lftools-ng jenkins secrets` - Filter Jenkins secrets
- `lftools-ng jenkins private-keys` - Filter SSH private keys

All commands maintain backward compatibility - existing scripts will continue to work unchanged.
