# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""
Enhanced Jenkins commands using the unified credential management system.

This module provides CLI commands for Jenkins operations using the new
unified credential management architecture.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console

from lftools_ng.core.credential_manager import CredentialFilter, CredentialManager, CredentialType, Credential
from lftools_ng.core.jenkins_provider import JenkinsCredentialProvider
from lftools_ng.core.jenkins import JenkinsClient  # For backwards compatibility with tests
from lftools_ng.core.jenkins_config import JenkinsConfigReader, JenkinsConfig
from lftools_ng.core.output import format_and_output, create_filter_from_options

# Constants
JENKINS_SERVER_HELP = "Jenkins server URL"
JENKINS_USER_HELP = "Jenkins username"
JENKINS_PASSWORD_HELP = "Jenkins password or API token"
JENKINS_OUTPUT_FORMAT_HELP = "Output format: table, json, yaml, csv"
JENKINS_CONFIG_HELP = "Path to jenkins_jobs.ini configuration file"

# Environment variable names
JENKINS_SERVER_ENV = "JENKINS_URL"
JENKINS_USER_ENV = "JENKINS_USER"
JENKINS_PASSWORD_ENV = "JENKINS_PASSWORD"

logger = logging.getLogger(__name__)
console = Console()

# Create Jenkins app
jenkins_app = typer.Typer(help="Jenkins server operations with unified credential management")


def get_jenkins_credentials(
    server: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    config_file: Optional[Path] = None
) -> tuple[str, str, str]:
    """
    Get Jenkins credentials from config file or command line arguments.

    Priority order:
    1. Command line arguments (if all provided)
    2. jenkins_jobs.ini from specified config file path
    3. jenkins_jobs.ini from current directory
    4. jenkins_jobs.ini from ~/.config/jenkins_jobs/

    Args:
        server: Jenkins server URL from command line
        user: Jenkins username from command line
        password: Jenkins password from command line
        config_file: Optional path to jenkins_jobs.ini file

    Returns:
        Tuple of (server_url, username, password)

    Raises:
        typer.Exit: If credentials cannot be found or are incomplete
    """
    config_reader = JenkinsConfigReader()

    # If all command line arguments provided, use them
    if server and user and password:
        return server, user, password

    # Try to get credentials from config file
    jenkins_config: Optional[JenkinsConfig] = None

    if config_file:
        # Use specified config file
        jenkins_config = config_reader.get_config_by_url(server, config_file) if server else None
        if not jenkins_config:
            configs = config_reader.get_jenkins_configs(config_file)
            if configs:
                jenkins_config = next(iter(configs.values()))
    else:
        # Search standard locations
        if server:
            jenkins_config = config_reader.get_config_by_url(server)
        else:
            configs = config_reader.get_jenkins_configs()
            if configs:
                jenkins_config = next(iter(configs.values()))

    # Use config file credentials, with command line overrides
    if jenkins_config:
        final_server = server or jenkins_config.url
        final_user = user or jenkins_config.user
        final_password = password or jenkins_config.password
        return final_server, final_user, final_password

    # If no config found, all parameters must be provided via command line
    missing_params = []
    if not server:
        missing_params.append("server")
    if not user:
        missing_params.append("user")
    if not password:
        missing_params.append("password")

    if missing_params:
        console.print(f"[red]Error: Missing required parameters: {', '.join(missing_params)}[/red]")
        console.print("\n[yellow]Options to provide Jenkins credentials:[/yellow]")
        console.print("1. [bold]Recommended:[/bold] Create a jenkins_jobs.ini file in:")
        console.print("   - Current directory: ./jenkins_jobs.ini")
        console.print("   - User config: ~/.config/jenkins_jobs/jenkins_jobs.ini")
        console.print("2. Specify config file with --config-file option")
        console.print("3. Provide --server, --user, and --password via command line")

        if config_reader.get_standard_config_paths():
            console.print("\n[cyan]Available servers in config files:[/cyan]")
            servers = config_reader.list_available_servers()
            for section_name, url in servers:
                console.print(f"  - {section_name}: {url}")

        raise typer.Exit(1)

    return server, user, password  # type: ignore


@jenkins_app.command("credentials")
def get_unified_credentials(
    server: Optional[str] = typer.Option(
        None, "--server", "-s",
        help=JENKINS_SERVER_HELP,
        envvar=JENKINS_SERVER_ENV
    ),
    user: Optional[str] = typer.Option(
        None, "--user", "-u",
        help=JENKINS_USER_HELP,
        envvar=JENKINS_USER_ENV
    ),
    password: Optional[str] = typer.Option(
        None, "--password", "-p",
        help=JENKINS_PASSWORD_HELP,
        envvar=JENKINS_PASSWORD_ENV
    ),
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c",
        help=JENKINS_CONFIG_HELP
    ),
    output_format: str = typer.Option("table", "--format", "-f", help=JENKINS_OUTPUT_FORMAT_HELP),

    # Filtering options
    include: Optional[List[str]] = typer.Option(
        None, "--include", "-i",
        help="Include filters (e.g., 'type=ssh_private_key', 'name~=deploy', 'tags=nexus')"
    ),
    exclude: Optional[List[str]] = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters (same syntax as include filters)"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields",
        help="Fields to include in output (comma-separated, e.g., 'id,type,username')"
    ),
    exclude_fields: Optional[str] = typer.Option(
        None, "--exclude-fields",
        help="Fields to exclude from output (comma-separated)"
    ),

    # Type-specific filters
    types: Optional[List[str]] = typer.Option(
        None, "--type", "-t",
        help="Filter by credential types: username_password, ssh_private_key, secret_text, secret_file"
    ),
    has_username: Optional[bool] = typer.Option(
        None, "--has-username",
        help="Filter credentials that have/don't have username"
    ),
    has_password: Optional[bool] = typer.Option(
        None, "--has-password",
        help="Filter credentials that have/don't have password"
    ),
    has_passphrase: Optional[bool] = typer.Option(
        None, "--has-passphrase",
        help="Filter credentials that have/don't have passphrase"
    ),

    # Pattern matching
    name_pattern: Optional[List[str]] = typer.Option(
        None, "--name-pattern",
        help="Filter by name patterns (supports wildcards and regex)"
    ),
    id_pattern: Optional[List[str]] = typer.Option(
        None, "--id-pattern",
        help="Filter by ID patterns (supports wildcards and regex)"
    ),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag",
        help="Filter by tags (e.g., nexus, deploy, ssh, production)"
    ),

    # Classification-based filters
    detected_type: Optional[List[str]] = typer.Option(
        None, "--detected-type",
        help="Filter by detected credential type from classification"
    ),
    subtype: Optional[List[str]] = typer.Option(
        None, "--subtype",
        help="Filter by credential subtype (e.g., rsa, ed25519, x509)"
    ),
    strength: Optional[List[str]] = typer.Option(
        None, "--strength",
        help="Filter by credential strength (weak, moderate, strong, very_strong)"
    ),
    algorithm: Optional[List[str]] = typer.Option(
        None, "--algorithm",
        help="Filter by algorithm (e.g., RSA, ECDSA, AES)"
    ),
    key_size: Optional[List[int]] = typer.Option(
        None, "--key-size",
        help="Filter by key size (e.g., 2048, 4096)"
    ),
    has_errors: Optional[bool] = typer.Option(
        None, "--has-errors",
        help="Filter credentials that have validation errors"
    ),
    has_warnings: Optional[bool] = typer.Option(
        None, "--has-warnings",
        help="Filter credentials that have security warnings"
    ),
) -> None:
    """Extract all credentials from Jenkins server with comprehensive filtering.

    This command provides a unified interface to all Jenkins credential types with powerful
    filtering capabilities including type detection, security analysis, and metadata enrichment.

    Examples:
        # Get all credentials (using jenkins_jobs.ini)
        lftools-ng jenkins credentials

        # Get all credentials with explicit server details
        lftools-ng jenkins credentials --server https://jenkins.example.com --user admin --password token

        # Get only SSH private keys
        lftools-ng jenkins credentials --type ssh_private_key

        # Get only credentials with 'nexus' in the name
        lftools-ng jenkins credentials --name-pattern "*nexus*"

        # Get deploy credentials with usernames
        lftools-ng jenkins credentials --tag deploy --has-username true

        # Get all credentials except test ones
        lftools-ng jenkins credentials --exclude "name~=test"
    """
    try:
        # Get Jenkins credentials from config or command line
        server, user, password = get_jenkins_credentials(server, user, password, config_file)

        # Initialize credential manager
        manager = CredentialManager()

        # Register Jenkins provider
        jenkins_provider = JenkinsCredentialProvider(server, user, password)
        manager.register_provider(jenkins_provider)

        # Build credential filter
        credential_filter = CredentialFilter()

        # Type filter
        if types:
            type_set = set()
            for type_str in types:
                try:
                    cred_type = CredentialType(type_str)
                    type_set.add(cred_type)
                except ValueError:
                    console.print(f"[yellow]Warning: Unknown credential type '{type_str}'[/yellow]")
            if type_set:
                credential_filter.types = type_set

        # Field presence filters
        if has_username is not None:
            credential_filter.has_username = has_username
        if has_password is not None:
            credential_filter.has_password = has_password
        if has_passphrase is not None:
            credential_filter.has_passphrase = has_passphrase

        # Pattern filters
        if name_pattern:
            credential_filter.name_patterns = name_pattern
        if id_pattern:
            credential_filter.id_patterns = id_pattern

        # Tag filter
        if tags:
            credential_filter.tags = set(tags)

        # Get credentials
        credentials = manager.list_credentials("jenkins", credential_filter)

        # Apply additional post-processing filters for classification metadata
        # (since CredentialFilter might not support all these yet)
        filtered_credentials: List[Credential] = []
        for cred in credentials:
            # Skip credentials that don't match classification filters
            if detected_type and cred.metadata:
                cred_detected_type = cred.metadata.get("detected_type", "")
                if cred_detected_type not in detected_type:
                    continue

            if subtype and cred.metadata:
                cred_subtype = cred.metadata.get("subtype", "")
                if cred_subtype not in subtype:
                    continue

            if strength and cred.metadata:
                cred_strength = cred.metadata.get("strength", "")
                if cred_strength not in strength:
                    continue

            if algorithm and cred.metadata:
                cred_algorithm = cred.metadata.get("algorithm", "")
                if cred_algorithm not in algorithm:
                    continue

            if key_size and cred.metadata:
                cred_key_size = cred.metadata.get("key_size")
                if cred_key_size not in key_size:
                    continue

            if has_errors is not None and cred.metadata:
                cred_has_errors = bool(cred.metadata.get("validation_errors"))
                if cred_has_errors != has_errors:
                    continue

            if has_warnings is not None and cred.metadata:
                cred_has_warnings = bool(cred.metadata.get("security_warnings"))
                if cred_has_warnings != has_warnings:
                    continue

            filtered_credentials.append(cred)

        credentials = filtered_credentials

        # Apply legacy filters (for backward compatibility)
        data_filter = create_filter_from_options(include, exclude, fields, exclude_fields)

        # Convert to output format
        output_data: List[Dict[str, Any]] = []
        for cred in credentials:
            cred_dict: Dict[str, Any] = {
                "id": cred.id,
                "name": cred.name,
                "type": cred.type.value,
                "scope": cred.scope.value,
                "description": cred.description,
                "username": cred.username or "",
                "has_password": "Yes" if cred.password else "No",
                "has_secret": "Yes" if cred.secret else "No",
                "has_private_key": "Yes" if cred.private_key else "No",
                "has_passphrase": "Yes" if cred.passphrase else "No",
                "filename": cred.filename or "",
                "tags": ",".join(sorted(cred.tags)) if cred.tags else "",
                "source_platform": cred.source_platform or "",
            }

            # Add classification metadata if available
            if cred.metadata:
                cred_dict.update({
                    "detected_type": cred.metadata.get("detected_type", ""),
                    "subtype": cred.metadata.get("subtype", ""),
                    "strength": cred.metadata.get("strength", ""),
                    "key_size": str(cred.metadata.get("key_size", "")) if cred.metadata.get("key_size") else "",
                    "algorithm": cred.metadata.get("algorithm", ""),
                    "format": cred.metadata.get("format", ""),
                    "expires": cred.metadata.get("expires", ""),
                    "issuer": cred.metadata.get("issuer", ""),
                    "subject": cred.metadata.get("subject", ""),
                    "fingerprint": cred.metadata.get("fingerprint", ""),
                    "has_errors": "Yes" if cred.metadata.get("validation_errors") else "No",
                    "has_warnings": "Yes" if cred.metadata.get("security_warnings") else "No",
                })

                # Include raw metadata for JSON/YAML output
                if output_format in ["json", "yaml"]:
                    cred_dict["metadata"] = cred.metadata

            output_data.append(cred_dict)

        # Configure table output
        table_config = {
            "title": "Jenkins Credentials (Unified View)",
            "columns": [
                {"name": "ID", "field": "id", "style": "cyan"},
                {"name": "Type", "field": "type", "style": "magenta"},
                {"name": "Detected Type", "field": "detected_type", "style": "bright_magenta"},
                {"name": "Subtype", "field": "subtype", "style": "magenta"},
                {"name": "Username", "field": "username", "style": "green"},
                {"name": "Has Password", "field": "has_password", "style": "yellow"},
                {"name": "Has Secret", "field": "has_secret", "style": "yellow"},
                {"name": "Has Private Key", "field": "has_private_key", "style": "yellow"},
                {"name": "Strength", "field": "strength", "style": "red"},
                {"name": "Algorithm", "field": "algorithm", "style": "blue"},
                {"name": "Key Size", "field": "key_size", "style": "blue"},
                {"name": "Errors", "field": "has_errors", "style": "red"},
                {"name": "Warnings", "field": "has_warnings", "style": "yellow"},
                {"name": "Tags", "field": "tags", "style": "blue"},
                {"name": "Description", "field": "description", "style": "white"}
            ]
        }

        # Use enhanced formatter
        format_and_output(output_data, output_format, data_filter, table_config)

        # Print summary
        console.print(f"\n[green]Found {len(output_data)} credentials matching filters[/green]")

        # Print type breakdown
        type_counts: dict[str, int] = {}
        for cred in credentials:
            type_name = cred.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        if type_counts:
            console.print("\n[blue]Credential types:[/blue]")
            for cred_type, count in sorted(type_counts.items()):
                console.print(f"  {cred_type}: {count}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@jenkins_app.command("migrate")
def migrate_credentials(
    source_server: Optional[str] = typer.Option(
        None, "--source-server", "-s",
        help="Source Jenkins server URL",
        envvar=JENKINS_SERVER_ENV
    ),
    source_user: Optional[str] = typer.Option(
        None, "--source-user", "-u",
        help="Source Jenkins username",
        envvar=JENKINS_USER_ENV
    ),
    source_password: Optional[str] = typer.Option(
        None, "--source-password", "-p",
        help="Source Jenkins password or API token",
        envvar=JENKINS_PASSWORD_ENV
    ),
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c",
        help=JENKINS_CONFIG_HELP
    ),

    # Target platform options
    target_platform: str = typer.Option(..., "--target", "-t", help="Target platform: github, gitlab, 1password, pass"),
    target_org: Optional[str] = typer.Option(None, "--target-org", help="Target organization/group (for GitHub/GitLab)"),
    target_vault: Optional[str] = typer.Option("Private", "--target-vault", help="Target vault (for 1Password)"),
    target_token: Optional[str] = typer.Option(None, "--target-token", help="Target platform token"),

    # Filtering options (same as credentials command)
    include: Optional[List[str]] = typer.Option(
        None, "--include", "-i",
        help="Include filters (e.g., 'type=ssh_private_key', 'name~=deploy', 'tags=nexus')"
    ),
    exclude: Optional[List[str]] = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters (same syntax as include filters)"
    ),
    types: Optional[List[str]] = typer.Option(
        None, "--type",
        help="Filter by credential types: username_password, ssh_private_key, secret_text, secret_file"
    ),
    tags: Optional[List[str]] = typer.Option(
        None, "--tag",
        help="Filter by tags (e.g., nexus, deploy, ssh, production)"
    ),

    # Migration options
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be migrated without actually doing it"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing credentials in target platform"),
    name_transform: Optional[str] = typer.Option(None, "--name-transform", help="Transform credential names (e.g., 'prefix:jenkins_', 'suffix:_migrated')"),
) -> None:
    """Migrate Jenkins credentials to another platform.

    This command allows you to migrate Jenkins credentials to other supported platforms
    like GitHub, GitLab, 1Password, or UNIX pass. It supports filtering to migrate only
    specific credentials and provides options for name transformation.

    Examples:
        # Migrate all credentials to GitHub
        lftools-ng jenkins migrate --source-server https://jenkins.example.com --source-user admin --source-password token --target github

        # Migrate only deployment SSH keys to 1Password
        lftools-ng jenkins migrate --source-server https://jenkins.example.com --source-user admin --source-password token --target 1password --target-vault DevOps --type ssh_private_key --tag deploy

        # Dry run to see what would be migrated
        lftools-ng jenkins migrate --source-server https://jenkins.example.com --source-user admin --source-password token --target pass --dry-run
    """
    try:
        console.print("[bold blue]Jenkins Credential Migration Tool[/bold blue]\n")

        # Get Jenkins credentials from config or command line
        source_server, source_user, source_password = get_jenkins_credentials(
            source_server, source_user, source_password, config_file
        )

        # Initialize credential manager
        manager = CredentialManager()

        # Register Jenkins provider (source)
        jenkins_provider = JenkinsCredentialProvider(source_server, source_user, source_password)
        manager.register_provider(jenkins_provider)

        # Initialize target provider
        target_provider = None
        if target_platform == "github":
            from lftools_ng.core.platform_providers import GitHubCredentialProvider
            target_provider = GitHubCredentialProvider(target_org, target_token)
        elif target_platform == "gitlab":
            from lftools_ng.core.platform_providers import GitLabCredentialProvider
            target_provider = GitLabCredentialProvider(target_org, target_token)
        elif target_platform == "1password":
            from lftools_ng.core.platform_providers import OnePasswordCredentialProvider
            target_provider = OnePasswordCredentialProvider(target_vault or "Private")
        elif target_platform == "pass":
            from lftools_ng.core.platform_providers import UnixPassCredentialProvider
            target_provider = UnixPassCredentialProvider()
        else:
            console.print(f"[red]Error: Unsupported target platform '{target_platform}'[/red]")
            console.print("Supported platforms: github, gitlab, 1password, pass")
            raise typer.Exit(1)

        if not target_provider:
            console.print(f"[red]Failed to initialize {target_platform} provider[/red]")
            raise typer.Exit(1)

        # Check target provider capabilities
        if not target_provider.supports_write():
            console.print(f"[red]Error: {target_platform} provider does not support writing credentials[/red]")
            console.print("Please check authentication or setup requirements")
            raise typer.Exit(1)

        # Build credential filter
        credential_filter = CredentialFilter()
        if types:
            type_set = set()
            for type_str in types:
                try:
                    cred_type = CredentialType(type_str)
                    type_set.add(cred_type)
                except ValueError:
                    console.print(f"[yellow]Warning: Unknown credential type '{type_str}'[/yellow]")
            if type_set:
                credential_filter.types = type_set

        if tags:
            credential_filter.tags = set(tags)

        # Get source credentials
        console.print("[cyan]Fetching credentials from Jenkins...[/cyan]")
        credentials = manager.list_credentials("jenkins", credential_filter)

        if not credentials:
            console.print("[yellow]No credentials found matching the specified filters[/yellow]")
            raise typer.Exit(0)

        console.print(f"[green]Found {len(credentials)} credentials to migrate[/green]\n")

        # Transform credential names if requested
        if name_transform:
            credentials = _transform_credential_names(credentials, name_transform)

        # Migration summary
        migration_plan = []
        for cred in credentials:
            # Check if credential already exists in target
            exists = target_provider.credential_exists(cred.id)
            action = "skip" if exists and not overwrite else "migrate"

            migration_plan.append({
                "credential": cred,
                "action": action,
                "exists": exists
            })

        # Display migration plan
        console.print("[bold]Migration Plan:[/bold]")
        table_data = []
        for plan_item in migration_plan:
            cred = plan_item["credential"]
            table_data.append({
                "id": cred.id,
                "type": cred.type.value,
                "action": plan_item["action"],
                "exists_in_target": "Yes" if plan_item["exists"] else "No",
                "notes": "Will overwrite" if plan_item["exists"] and overwrite else ""
            })

        table_config = {
            "title": f"Migration Plan: Jenkins → {target_platform.title()}",
            "columns": [
                {"name": "ID", "field": "id", "style": "cyan"},
                {"name": "Type", "field": "type", "style": "magenta"},
                {"name": "Action", "field": "action", "style": "green"},
                {"name": "Exists in Target", "field": "exists_in_target", "style": "yellow"},
                {"name": "Notes", "field": "notes", "style": "red"},
            ]
        }

        format_and_output(table_data, "table", None, table_config)

        if dry_run:
            console.print("\n[bold yellow]Dry run completed. No credentials were actually migrated.[/bold yellow]")
            return

        # Confirm migration
        if not typer.confirm(f"\nProceed with migrating {len([p for p in migration_plan if p['action'] == 'migrate'])} credentials?"):
            console.print("[yellow]Migration cancelled[/yellow]")
            return

        # Perform migration
        console.print("\n[cyan]Starting migration...[/cyan]")
        success_count = 0
        failure_count = 0

        for plan_item in migration_plan:
            if plan_item["action"] != "migrate":
                continue

            cred = plan_item["credential"]
            console.print(f"Migrating {cred.id}...")

            try:
                # Set target platform info
                cred.target_platform = target_platform
                cred.target_id = cred.id

                # Attempt migration
                if target_provider.create_credential(cred):
                    console.print(f"  [green]✓[/green] {cred.id}")
                    success_count += 1
                else:
                    console.print(f"  [red]✗[/red] {cred.id} - Failed to create")
                    failure_count += 1

            except Exception as e:
                console.print(f"  [red]✗[/red] {cred.id} - Error: {e}")
                failure_count += 1

        # Migration summary
        console.print(f"\n[bold]Migration Complete![/bold]")
        console.print(f"[green]Successfully migrated: {success_count}[/green]")
        if failure_count > 0:
            console.print(f"[red]Failed to migrate: {failure_count}[/red]")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        console.print(f"[red]Migration failed: {e}[/red]")
        raise typer.Exit(1)


def _transform_credential_names(credentials: List[Credential], transformation: str) -> List[Credential]:
    """Transform credential names based on the specified transformation."""
    if not transformation:
        return credentials

    if transformation.startswith("prefix:"):
        prefix = transformation[7:]
        for cred in credentials:
            cred.id = f"{prefix}{cred.id}"
            cred.name = f"{prefix}{cred.name}"
    elif transformation.startswith("suffix:"):
        suffix = transformation[7:]
        for cred in credentials:
            cred.id = f"{cred.id}{suffix}"
            cred.name = f"{cred.name}{suffix}"

    return credentials


@jenkins_app.command("analyze")
def analyze_credentials(
    server: Optional[str] = typer.Option(
        None, "--server", "-s",
        help=JENKINS_SERVER_HELP,
        envvar=JENKINS_SERVER_ENV
    ),
    user: Optional[str] = typer.Option(
        None, "--user", "-u",
        help=JENKINS_USER_HELP,
        envvar=JENKINS_USER_ENV
    ),
    password: Optional[str] = typer.Option(
        None, "--password", "-p",
        help=JENKINS_PASSWORD_HELP,
        envvar=JENKINS_PASSWORD_ENV
    ),
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c",
        help=JENKINS_CONFIG_HELP
    ),
    output_format: str = typer.Option("table", "--format", "-f", help=JENKINS_OUTPUT_FORMAT_HELP),

    # Analysis options
    show_warnings: bool = typer.Option(True, "--show-warnings", help="Show security warnings"),
    show_errors: bool = typer.Option(True, "--show-errors", help="Show validation errors"),
    show_stats: bool = typer.Option(True, "--show-stats", help="Show statistics summary"),
    show_recommendations: bool = typer.Option(True, "--show-recommendations", help="Show security recommendations"),
) -> None:
    """Analyze Jenkins credentials for security issues and best practices.

    This command performs a comprehensive security analysis of Jenkins credentials,
    including strength assessment, format validation, and security recommendations.

    Examples:
        # Full security analysis
        lftools-ng jenkins analyze --server https://jenkins.example.com --user admin --password token

        # Just show credentials with security warnings
        lftools-ng jenkins analyze --server https://jenkins.example.com --user admin --password token --show-stats false --show-recommendations false
    """
    try:
        console.print("[bold blue]Jenkins Credential Security Analysis[/bold blue]\n")

        # Get Jenkins credentials from config or command line
        server, user, password = get_jenkins_credentials(server, user, password, config_file)

        # Initialize credential manager
        manager = CredentialManager()

        # Register Jenkins provider
        jenkins_provider = JenkinsCredentialProvider(server, user, password, enable_classification=True)
        manager.register_provider(jenkins_provider)

        # Get all credentials with classification
        console.print("[cyan]Analyzing Jenkins credentials...[/cyan]")
        credentials = manager.list_credentials("jenkins")

        if not credentials:
            console.print("[yellow]No credentials found on Jenkins server[/yellow]")
            return

        console.print(f"[green]Analyzed {len(credentials)} credentials[/green]\n")

        # Collect analysis data
        analysis_results = []
        warnings_count = 0
        errors_count = 0
        strength_counts = {"weak": 0, "moderate": 0, "strong": 0, "very_strong": 0, "unknown": 0}
        type_counts: Dict[str, int] = {}

        for cred in credentials:
            result = {
                "id": cred.id,
                "name": cred.name,
                "type": cred.type.value,
                "detected_type": cred.metadata.get("detected_type", "") if cred.metadata else "",
                "subtype": cred.metadata.get("subtype", "") if cred.metadata else "",
                "strength": cred.metadata.get("strength", "unknown") if cred.metadata else "unknown",
                "algorithm": cred.metadata.get("algorithm", "") if cred.metadata else "",
                "key_size": cred.metadata.get("key_size", "") if cred.metadata else "",
                "has_errors": bool(cred.metadata.get("validation_errors")) if cred.metadata else False,
                "has_warnings": bool(cred.metadata.get("security_warnings")) if cred.metadata else False,
                "errors": cred.metadata.get("validation_errors", []) if cred.metadata else [],
                "warnings": cred.metadata.get("security_warnings", []) if cred.metadata else [],
            }

            analysis_results.append(result)

            # Update counts
            if result["has_errors"]:
                errors_count += 1
            if result["has_warnings"]:
                warnings_count += 1

            strength = result["strength"]
            if strength in strength_counts:
                strength_counts[strength] += 1
            else:
                strength_counts["unknown"] += 1

            cred_type = result["type"]
            type_counts[cred_type] = type_counts.get(cred_type, 0) + 1

        # Display statistics if requested
        if show_stats:
            console.print("[bold]Security Statistics:[/bold]")
            console.print(f"  Total credentials: {len(credentials)}")
            console.print(f"  [red]Credentials with errors: {errors_count}[/red]")
            console.print(f"  [yellow]Credentials with warnings: {warnings_count}[/yellow]")
            console.print()

            console.print("[bold]Strength Distribution:[/bold]")
            for strength, count in strength_counts.items():
                if count > 0:
                    percentage = (count / len(credentials)) * 100
                    color = "red" if strength == "weak" else "yellow" if strength == "moderate" else "green"
                    console.print(f"  [{color}]{strength.replace('_', ' ').title()}: {count} ({percentage:.1f}%)[/{color}]")
            console.print()

            console.print("[bold]Type Distribution:[/bold]")
            for cred_type, count in sorted(type_counts.items()):
                percentage = (count / len(credentials)) * 100
                console.print(f"  {cred_type}: {count} ({percentage:.1f}%)")
            console.print()

        # Filter results based on what to show
        display_results = analysis_results
        if not show_warnings and not show_errors:
            # Show all if neither warnings nor errors are specifically requested
            pass
        else:
            display_results = []
            for result in analysis_results:
                include = True
                if show_warnings and not show_errors:
                    include = result["has_warnings"]
                elif show_errors and not show_warnings:
                    include = result["has_errors"]
                elif show_warnings and show_errors:
                    include = result["has_warnings"] or result["has_errors"]

                if include:
                    display_results.append(result)

        # Display detailed results
        if display_results:
            table_config = {
                "title": "Credential Security Analysis",
                "columns": [
                    {"name": "ID", "field": "id", "style": "cyan"},
                    {"name": "Type", "field": "type", "style": "magenta"},
                    {"name": "Detected", "field": "detected_type", "style": "bright_magenta"},
                    {"name": "Subtype", "field": "subtype", "style": "magenta"},
                    {"name": "Strength", "field": "strength", "style": "red"},
                    {"name": "Algorithm", "field": "algorithm", "style": "blue"},
                    {"name": "Key Size", "field": "key_size", "style": "blue"},
                    {"name": "Errors", "field": "has_errors", "style": "red"},
                    {"name": "Warnings", "field": "has_warnings", "style": "yellow"},
                ]
            }

            # Convert boolean values to readable format for table display
            for result in display_results:
                result["has_errors"] = "Yes" if result["has_errors"] else "No"
                result["has_warnings"] = "Yes" if result["has_warnings"] else "No"

            format_and_output(display_results, output_format, None, table_config)

            # Show detailed errors and warnings if in table mode
            if output_format == "table":
                for result in analysis_results:
                    if (show_errors and result["errors"]) or (show_warnings and result["warnings"]):
                        console.print(f"\n[bold cyan]{result['id']}:[/bold cyan]")

                        if show_errors and result["errors"]:
                            console.print("  [red]Validation Errors:[/red]")
                            for error in result["errors"]:
                                console.print(f"    • {error}")

                        if show_warnings and result["warnings"]:
                            console.print("  [yellow]Security Warnings:[/yellow]")
                            for warning in result["warnings"]:
                                console.print(f"    • {warning}")

        # Show security recommendations if requested
        if show_recommendations:
            console.print("\n[bold]Security Recommendations:[/bold]")
            recommendations = []

            if strength_counts["weak"] > 0:
                recommendations.append(f"Replace {strength_counts['weak']} weak credentials with stronger alternatives")

            if strength_counts["moderate"] > 0:
                recommendations.append(f"Consider strengthening {strength_counts['moderate']} moderate-strength credentials")

            ssh_without_passphrase = sum(1 for r in analysis_results
                                       if r["type"] == "ssh_private_key" and
                                       "passphrase protected" in str(r.get("warnings", [])))
            if ssh_without_passphrase > 0:
                recommendations.append(f"Add passphrases to {ssh_without_passphrase} unprotected SSH keys")

            old_credentials = sum(1 for r in analysis_results
                                if r["key_size"] and str(r["key_size"]).isdigit() and int(r["key_size"]) < 2048)
            if old_credentials > 0:
                recommendations.append(f"Upgrade {old_credentials} credentials with key sizes < 2048 bits")

            if not recommendations:
                console.print("  [green]✓ No major security issues found![/green]")
            else:
                for i, rec in enumerate(recommendations, 1):
                    console.print(f"  {i}. {rec}")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        console.print(f"[red]Analysis failed: {e}[/red]")
        raise typer.Exit(1)


@jenkins_app.command("platforms")
def check_platforms() -> None:
    """Check available credential platforms and their setup status.

    This command detects which credential management platforms are available
    on the local system and provides setup instructions for those that aren't.

    Examples:
        # Check platform availability
        lftools-ng jenkins platforms
    """
    try:
        console.print("[bold blue]Credential Platform Availability[/bold blue]\n")

        # Import platform detection functions
        from lftools_ng.core.platform_providers import detect_available_providers, get_provider_suggestions

        # Detect available providers
        providers = detect_available_providers()
        suggestions = get_provider_suggestions()

        # Display results
        console.print("[bold]Platform Status:[/bold]")

        # Map platform keys to display names
        platform_display_names = {
            'github': 'Github',
            'gitlab': 'Gitlab',
            '1password': '1Password',
            'pass': 'Pass'
        }

        for platform, available in providers.items():
            status = "[green]✓ Available[/green]" if available else "[red]✗ Not Available[/red]"
            display_name = platform_display_names.get(platform, platform.title())
            console.print(f"  {display_name:12} {status}")

        # Show setup suggestions for unavailable platforms
        if suggestions:
            console.print("\n[bold]Setup Instructions:[/bold]")
            for platform, instruction in suggestions.items():
                display_name = platform_display_names.get(platform, platform.title())
                console.print(f"\n[yellow]{display_name}:[/yellow]")
                console.print(f"  {instruction}")

        # Show summary
        available_count = sum(providers.values())
        total_count = len(providers)
        console.print(f"\n[bold]Summary:[/bold] {available_count}/{total_count} platforms available")

        if available_count == total_count:
            console.print("[green]All credential platforms are ready for use![/green]")
        elif available_count > 0:
            console.print(f"[yellow]{total_count - available_count} platforms need setup[/yellow]")
        else:
            console.print("[red]No credential platforms are currently available[/red]")

    except Exception as e:
        logger.error(f"Platform check failed: {e}")
        console.print(f"[red]Platform check failed: {e}[/red]")
        raise typer.Exit(1)


@jenkins_app.command("groovy")
def run_groovy_script(
    script_file: str = typer.Argument(..., help="Path to Groovy script file"),
    server: Optional[str] = typer.Option(
        None, "--server", "-s",
        help=JENKINS_SERVER_HELP,
        envvar=JENKINS_SERVER_ENV
    ),
    user: Optional[str] = typer.Option(
        None, "--user", "-u",
        help=JENKINS_USER_HELP,
        envvar=JENKINS_USER_ENV
    ),
    password: Optional[str] = typer.Option(
        None, "--password", "-p",
        help=JENKINS_PASSWORD_HELP,
        envvar=JENKINS_PASSWORD_ENV
    ),
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c",
        help=JENKINS_CONFIG_HELP
    ),
) -> None:
    """Run a Groovy script on Jenkins server.

    This command executes Groovy scripts on the Jenkins server, which is essential
    for credential extraction and management operations.

    Examples:
        # Run a simple script
        lftools-ng jenkins groovy script.groovy --server https://jenkins.example.com --user admin --password token
    """
    try:
        # Get Jenkins credentials from config or command line
        server, user, password = get_jenkins_credentials(server, user, password, config_file)

        # Read script file
        from pathlib import Path
        script_path = Path(script_file)
        if not script_path.exists():
            console.print(f"[red]Error: Script file not found: {script_file}[/red]")
            raise typer.Exit(1)

        script_content = script_path.read_text()

        # Use the JenkinsClient to run the script
        client = JenkinsClient(server, user, password)
        result = client.run_groovy_script(script_content)

        console.print(result)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
