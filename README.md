<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2025 The Linux Foundation
-->

# lftools-ng

Next-generation Linux Foundation Release Engineering Tools

## Overview

**lftools-ng** is a modern Python CLI tool that reimplements and extends the
functionality of the original [lftools](https://github.com/lfit/releng-lftools)
repository. Built with modern Python standards and designed for both
command-line use and library integration.

## Features

### 🔍 Universal Filtering System ⭐ **PRIMARY FEATURE**

**lftools-ng** includes a comprehensive filtering system that works across ALL commands returning data.
This is a **core feature** that provides powerful data manipulation capabilities:

- **Include/Exclude Filters**: Filter results by any field using various operators
- **Field Selection**: Show only specific fields in output
- **Multiple Output Formats**: Works with table, JSON, and YAML output
- **Complex Expressions**: Support for regex, glob patterns, numeric comparisons
- **Nested Field Access**: Filter on nested data using dot notation

#### Quick Filtering Examples

```bash
# Show only Jenkins servers
lftools-ng projects servers --include 'type=jenkins'

# Exclude test/sandbox environments
lftools-ng projects servers --exclude 'name~=test' --exclude 'name~=sandbox'

# Show specific fields only
lftools-ng projects list --fields 'name,source,github_mirror_org'

# Complex filtering with multiple conditions
lftools-ng projects servers --include 'type=jenkins' --include 'location~=virginia' --fields 'name,url'

# Find projects with GitHub mirrors
lftools-ng projects list --exclude 'github_mirror_org:empty'
```

See [docs/filtering.md](docs/filtering.md) for complete filtering documentation.

### Jenkins Integration

- **Credential Extraction**: Export Jenkins credentials, secrets, and SSH
  private keys
- **Groovy Script Execution**: Run arbitrary Groovy scripts on Jenkins servers
- **Output Formats**: Support for table, JSON, and YAML output
- **Extensible Architecture**: Built for easy extension of Jenkins functionality

### Project Management

- **Project Enumeration**: List and manage projects with their Jenkins server
  mappings
- **Server Management**: Track and manage Jenkins server configurations
- **Database Rebuilding**: Dynamically update project and server databases
- **Short Aliases**: Support for project short names and aliases

### 🚀 Repository Discovery ⭐ **NEW FEATURE**

- **SSH-based Gerrit Discovery**: Enumerate repositories from Gerrit instances using SSH (no web scraping)
- **GitHub API Integration**: Discover repositories from GitHub organizations
- **Bidirectional Mapping**: Map between Gerrit repository paths and GitHub repository names
- **Cross-platform Support**: Handle repositories that exist in both Gerrit and GitHub
- **SSH Configuration**: Respects user's SSH config and authentication settings
- **Large Project Support**: Efficiently handles large projects like ONAP and O-RAN-SC

## Installation

### From PyPI (when available)

```bash
pip install lftools-ng
```

### From Source

```bash
git clone https://github.com/ModeSevenIndustrialSolutions/lftools-ng.git
cd lftools-ng
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/ModeSevenIndustrialSolutions/lftools-ng.git
cd lftools-ng
pdm install --dev
```

## Usage

### Jenkins Operations

#### Extract Credentials

```bash
# Table format (default)
lftools-ng jenkins credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123

# JSON format
lftools-ng jenkins credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123 \
  --format json

# YAML format
lftools-ng jenkins credentials \
  --server https://jenkins.example.com \
  --user admin \
  --password token123 \
  --format yaml
```

#### Extract Secrets

```bash
lftools-ng jenkins secrets \
  --server https://jenkins.example.com \
  --user admin \
  --password token123
```

#### Extract SSH Private Keys

```bash
lftools-ng jenkins private-keys \
  --server https://jenkins.example.com \
  --user admin \
  --password token123
```

#### Run Groovy Scripts

```bash
lftools-ng jenkins groovy script.groovy \
  --server https://jenkins.example.com \
  --user admin \
  --password token123
```

### Project Operations

#### List Projects

```bash
# List all projects
lftools-ng projects list

# List with custom config directory
lftools-ng projects list --config-dir /path/to/config

# JSON output
lftools-ng projects list --format json
```

#### List Jenkins Servers

```bash
lftools-ng projects servers
```

#### Add New Project

```bash
lftools-ng projects add-project "My Project" \
  --alias myproj \
  --server jenkins.example.com
```

#### Add New Server

```bash
lftools-ng projects add-server "jenkins.example.com" \
  --url https://jenkins.example.com
```

#### Rebuild Databases

```bash
# Rebuild projects database
lftools-ng projects rebuild-projects --force

# Rebuild servers database
lftools-ng projects rebuild-servers --force
```

### Repository Operations

#### List Repositories

```bash
# List all active repositories
lftools-ng projects repositories list

# List repositories for a specific project
lftools-ng projects repositories list ONAP

# Include archived repositories
lftools-ng projects repositories list --include-archived

# JSON output
lftools-ng projects repositories list --format json-pretty
```

#### Repository Information

```bash
# Get detailed repository info
lftools-ng projects repositories info ONAP "aai/aai-common"

# Works with GitHub names too
lftools-ng projects repositories info ONAP "aai-aai-common"
```

#### List Archived Repositories

```bash
# List all archived repositories
lftools-ng projects repositories archived

# List archived repositories for a specific project
lftools-ng projects repositories archived ONAP
```

#### Rebuild Repository Database

```bash
# Rebuild repositories database (SSH-based discovery)
lftools-ng projects rebuild repositories --force

# Rebuild for specific project only
lftools-ng projects rebuild repositories ONAP --force

# Test SSH connectivity first
lftools-ng projects repositories test-ssh ONAP
```

### SSH-Based Repository Discovery

lftools-ng uses SSH to connect to Gerrit instances for repository discovery,
providing more reliable and efficient access than web scraping methods.

#### Prerequisites

1. **SSH Access**: Ensure you have SSH access to the relevant Gerrit instances
2. **SSH Keys**: Your SSH keys should be set up and available via SSH agent
3. **SSH Config**: Configure usernames in `~/.ssh/config` for Gerrit hosts

#### Example SSH Configuration

```bash
# ~/.ssh/config
Host gerrit.onap.org
    User mygerrituser
    IdentityFile ~/.ssh/id_rsa

Host gerrit.o-ran-sc.org
    User mygerrituser
    IdentityFile ~/.ssh/id_rsa
```

#### Repository Discovery Process

1. **SSH Connection**: Connects to Gerrit via SSH using your configured credentials
2. **Project Enumeration**: Runs `gerrit ls-projects --format json --all` command
3. **GitHub Mapping**: Maps Gerrit repository paths to GitHub repository names
4. **Cross-Reference**: Links repositories that exist in both Gerrit and GitHub
5. **Database Update**: Stores repository information in local database

#### Supported Gerrit Features

- **All Projects**: Discovers all accessible projects, including archived ones
- **Project Metadata**: Captures descriptions, states, and access permissions
- **Nested Paths**: Handles complex repository hierarchies (e.g., `aai/aai-common`)
- **State Detection**: Identifies active vs. read-only (archived) repositories

### General Commands

#### Version Information

```bash
lftools-ng --version
```

#### Tool Information

```bash
lftools-ng info
```

#### Enable Verbose Logging

```bash
lftools-ng --verbose <command>
```

## Configuration

### Configuration Directory

By default, lftools-ng stores configuration in:

- `~/.config/lftools-ng/` on Linux/macOS
- `%USERPROFILE%\.config\lftools-ng\` on Windows

### Configuration Files

- `projects.yaml`: Project definitions and Jenkins server mappings
- `servers.yaml`: Jenkins server configurations

#### Automatic Initialization

When you first run a command that requires server data (e.g., `lftools-ng projects servers list`),
the tool will automatically detect if the `servers.yaml` file is missing and prompt you to create
an initial database:

```bash
$ lftools-ng projects servers list

⚠️  No servers database found!
Expected location: ~/.config/lftools-ng/servers.yaml

The servers database contains information about Jenkins servers,
Gerrit instances, Nexus repositories, and other infrastructure.

Would you like to create an initial servers database?
This will help you get started with basic server configurations.

Initialize servers database [y/n]: y

✓ Created initial servers database at: ~/.config/lftools-ng/servers.yaml
```

The initial database contains sample entries that you can customize:

- Add your actual server configurations
- Update VPN addresses and other details
- Remove sample entries
- Use `lftools-ng projects rebuild-servers` to populate from existing data sources

### Environment Variables

- `JENKINS_URL`: Default Jenkins server URL
- `JENKINS_USER`: Default Jenkins username
- `JENKINS_PASSWORD`: Default Jenkins password/token

## Library Usage

lftools-ng also works as a Python library:

```python
from lftools_ng import JenkinsClient
from lftools_ng.core.projects import ProjectManager

# Jenkins operations
client = JenkinsClient(
    server="https://jenkins.example.com",
    username="admin",
    password="token123"
)

credentials = client.get_credentials()
secrets = client.get_secrets()
ssh_keys = client.get_ssh_private_keys()

# Project management
import pathlib
config_dir = pathlib.Path.home() / ".config" / "lftools-ng"
manager = ProjectManager(config_dir)

projects = manager.list_projects()
servers = manager.list_servers()
```

## Development

### Requirements

- Python 3.10+
- PDM for dependency management
- Pre-commit for code quality

### Setup Development Environment

```bash
git clone https://github.com/ModeSevenIndustrialSolutions/lftools-ng.git
cd lftools-ng
pdm install --dev
pre-commit install
```

### Running Tests

```bash
# Run all tests (excludes integration tests by default)
pdm run pytest

# Run with coverage
pdm run pytest --cov

# Run specific test file
pdm run pytest tests/core/test_jenkins.py

# Run integration tests (may require external resources like Jenkins servers)
pdm run pytest -m integration

# Run both unit and integration tests
pdm run pytest -m "not slow"  # or use specific markers
```

**Note**: Integration tests are skipped by default because they may require external
resources (like Jenkins servers with proper credentials). They can be run explicitly using
the `-m integration` flag.

### Code Quality

```bash
# Run pre-commit checks
pre-commit run --all-files

# Run type checking
pdm run mypy src/

# Run linting
pdm run ruff check src/ tests/
```

### Building

```bash
# Build package
pdm build

# Install locally
pip install dist/lftools_ng-*.whl
```

## Architecture

### Core Modules

- `lftools_ng.core.jenkins`: Jenkins client and operations
- `lftools_ng.core.projects`: Project and server management

### Command Modules

- `lftools_ng.commands.jenkins`: Jenkins CLI commands
- `lftools_ng.commands.projects`: Project management CLI commands

### CLI Entry Point

- `lftools_ng.cli`: Main CLI application using Typer

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with proper tests
4. Ensure all pre-commit checks pass
5. Submit a pull request

### Code Standards

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Maintain >80% test coverage
- Include docstrings for all public functions
- Add SPDX license headers to all files

## License

This project uses the Apache License 2.0. See the
[LICENSE](LICENSE) file for details.

## Support

- **Bug Reports**: [GitHub Issues](https://github.com/ModeSevenIndustrialSolutions/lftools-ng/issues)
- **Documentation**: [GitHub Repository](https://github.com/ModeSevenIndustrialSolutions/lftools-ng)

## Acknowledgments

- Based on the original [lftools](https://github.com/lfit/releng-lftools)
  by the Linux Foundation
- Built with [Typer](https://typer.tiangolo.com/) for CLI framework
- Uses [Rich](https://rich.readthedocs.io/) for beautiful terminal output

## 🚨 **CRITICAL**: Developer Requirements for New Commands

### Universal Filtering System Implementation

**ALL new CLI commands that return data MUST implement the universal filtering system.**
This is a **non-negotiable requirement** and a **primary feature** of lftools-ng.

#### Required Implementation Steps

When adding a new CLI command that returns tabular data, you **MUST**:

1. **Include filtering parameters** in your command function:

   ```python
   include: Optional[List[str]] = typer.Option(None, "--include", "-i", help="Include filters"),
   exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Exclude filters"),
   fields: Optional[str] = typer.Option(None, "--fields", help="Fields to include"),
   exclude_fields: Optional[str] = typer.Option(None, "--exclude-fields", help="Fields to exclude")
   ```

2. **Use the standard output system**:

   ```python
   from lftools_ng.core.output import format_and_output, create_filter_from_options

   data_filter = create_filter_from_options(include, exclude, fields, exclude_fields)
   format_and_output(data, output_format, data_filter, table_config)
   ```

3. **Add comprehensive tests** in `tests/integration/test_universal_filtering.py`

4. **Update filtering requirements tests** to include your new command

5. **Include filtering examples** in your command's help text

#### Implementation Template

See `src/lftools_ng/core/filtering_guidelines.py` for a complete implementation template.

#### Testing Requirements

- **Integration tests**: Add to `tests/integration/test_universal_filtering.py`
- **Requirements tests**: Update `TestFilteringSystemRequirements` class
- **All output formats**: Verify table, JSON, and YAML output work with filtering
- **Error handling**: Test invalid filter expressions

#### Documentation Requirements

- **Command help**: Include filtering examples in docstrings
- **README examples**: Add your command's filtering examples to this README
- **Filter documentation**: Update `docs/filtering.md` if adding new field types

### ⚠️ Pull Request Requirements

**Pull requests adding data-returning commands will be REJECTED if they do not properly implement filtering.**

The universal filtering system ensures:

- **Consistent user experience** across all commands
- **Powerful data manipulation** capabilities
- **Programmatic integration** through JSON output
- **Future-proofing** as the codebase grows

See [docs/filtering.md](docs/filtering.md) for complete implementation details.
