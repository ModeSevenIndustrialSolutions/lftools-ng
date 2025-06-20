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

### Jenkins Integration

- **Credential Extraction**: Export Jenkins credentials, secrets, and SSH
  private keys
- **Groovy Script Execution**: Run arbitrary Groovy scripts on Jenkins servers
- **Multiple Output Formats**: Support for table, JSON, and YAML output
- **Extensible Architecture**: Built for easy extension of Jenkins functionality

### Project Management

- **Project Enumeration**: List and manage projects with their Jenkins server
  mappings
- **Server Management**: Track and manage Jenkins server configurations
- **Database Rebuilding**: Dynamically update project and server databases
- **Short Aliases**: Support for project short names and aliases

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

### Environment Variables

- `JENKINS_URL`: Default Jenkins server URL
- `JENKINS_USER`: Default Jenkins username
- `JENKINS_PASSWORD`: Default Jenkins password/token

## Library Usage

lftools-ng can also be used as a Python library:

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
# Run all tests
pdm run pytest

# Run with coverage
pdm run pytest --cov

# Run specific test file
pdm run pytest tests/core/test_jenkins.py
```

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

This project is licensed under the Apache License 2.0. See the
[LICENSE](LICENSE) file for details.

## Support

- **Bug Reports**: [GitHub Issues](https://github.com/ModeSevenIndustrialSolutions/lftools-ng/issues)
- **Documentation**: [GitHub Repository](https://github.com/ModeSevenIndustrialSolutions/lftools-ng)

## Acknowledgments

- Based on the original [lftools](https://github.com/lfit/releng-lftools)
  by the Linux Foundation
- Built with [Typer](https://typer.tiangolo.com/) for CLI framework
- Uses [Rich](https://rich.readthedocs.io/) for beautiful terminal output
