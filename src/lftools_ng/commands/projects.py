# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Enhanced project management commands for lftools-ng."""

import pathlib
from typing import Any, Dict, List, Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from lftools_ng.core.projects import ProjectManager
from lftools_ng.core.output import format_and_output, create_filter_from_options

projects_app = typer.Typer(
    name="projects",
    help="Project management operations",
    no_args_is_help=True,
)

# Create servers subcommand group
servers_app = typer.Typer(
    name="servers",
    help="Server management and connectivity testing",
    no_args_is_help=False,
)
projects_app.add_typer(servers_app, name="servers")

# Create rebuild subcommand group
rebuild_app = typer.Typer(
    name="rebuild",
    help="Rebuild project and server databases",
    no_args_is_help=True,
)
projects_app.add_typer(rebuild_app, name="rebuild")

console = Console()

# Constants for configuration
DEFAULT_CONFIG_DIR = pathlib.Path.home() / ".config" / "lftools-ng"
PROJECTS_DB_FILE = DEFAULT_CONFIG_DIR / "projects.yaml"
SERVERS_DB_FILE = DEFAULT_CONFIG_DIR / "servers.yaml"
CONFIG_DIR_HELP = "Configuration directory path"
OUTPUT_FORMAT_HELP = "Output format (table, json, json-pretty)"

def format_output(data: Any, output_format: str) -> None:
    """Format and print output in the specified format.

    Args:
        data: Data to output
        output_format: Format to use (table, json, json-pretty, yaml)
    """
    if output_format == "json":
        import json
        import sys
        print(json.dumps(data, separators=(',', ':')), file=sys.stdout)
    elif output_format == "json-pretty":
        import json
        import sys
        print(json.dumps(data, indent=2), file=sys.stdout)
    elif output_format == "yaml":
        console.print(yaml.dump(data, default_flow_style=False))
    # If table format, let the calling function handle it


@projects_app.command("list")
def list_projects(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
    check_uniformity: bool = typer.Option(
        False, "--check-uniformity", help="Check for uniform column values (potential data issues)"
    ),
    include: Optional[List[str]] = typer.Option(
        None, "--include", "-i",
        help="Include filters (e.g., 'name=*test*', 'github_mirror_org!=', 'source=github')"
    ),
    exclude: Optional[List[str]] = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters (same syntax as include filters)"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields",
        help="Fields to include in output (comma-separated, e.g., 'name,github_mirror_org,source')"
    ),
    exclude_fields: Optional[str] = typer.Option(
        None, "--exclude-fields",
        help="Fields to exclude from output (comma-separated)"
    ),
) -> None:
    """List all registered projects with powerful filtering capabilities.

    Filter examples:
    - Include projects with 'test' in name: --include 'name~=test'
    - Exclude projects without GitHub org: --exclude 'github_mirror_org:empty'
    - Only show specific fields: --fields 'name,github_mirror_org'
    - Multiple filters: --include 'source=github' --include 'name~=linux'
    """
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        # Check if projects database exists, prompt for rebuild if needed
        if not manager.ensure_projects_database_exists():
            console.print("[yellow]⚠️  Cannot proceed without projects database.[/yellow]")
            console.print("To manually build the database, run:")
            console.print("  [cyan]lftools-ng projects rebuild projects --force[/cyan]")
            raise typer.Exit(1)

        projects = manager.list_projects()

        # Enhance projects data with computed fields
        enhanced_projects = []
        for project in projects:
            enhanced_project = project.copy()

            # Add computed aliases field
            aliases_str = _get_aliases_string(project)
            enhanced_project["aliases_display"] = aliases_str

            # Add computed github_mirror_org field
            github_org = project.get("github_mirror_org", "")
            enhanced_project["github_mirror_org_display"] = github_org if github_org else "Not found"

            # Add computed primary_scm field
            enhanced_project["primary_scm"] = _determine_project_primary_scm(project, manager)

            enhanced_projects.append(enhanced_project)

        # Check for column uniformity if requested
        if check_uniformity:
            uniform_issues = _check_column_uniformity(enhanced_projects, manager)
            if any(uniform_issues.values()):
                console.print("\n[yellow]⚠️  Data Quality Warning:[/yellow]")
                for column, is_uniform in uniform_issues.items():
                    if is_uniform:
                        console.print(f"[yellow]  - Column '{column}' has uniform values across all projects[/yellow]")
                console.print()

        # Create filter from options
        data_filter = create_filter_from_options(include, exclude, fields, exclude_fields)

        # Configure table output
        table_config = {
            "title": "Registered Projects",
            "columns": [
                {"name": "Project", "field": "name", "style": "cyan"},
                {"name": "Aliases", "field": "aliases_display", "style": "magenta"},
                {"name": "GitHub Org", "field": "github_mirror_org_display", "style": "green"},
                {"name": "Primary SCM", "field": "primary_scm", "style": "blue"}
            ]
        }

        # Use enhanced formatter
        format_and_output(enhanced_projects, output_format, data_filter, table_config)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _get_aliases_string(project: Dict[str, Any]) -> str:
    """Get aliases as a display string."""
    aliases_str = ""
    if "aliases" in project and project["aliases"]:
        if isinstance(project["aliases"], list):
            aliases_str = ", ".join(str(alias) for alias in project["aliases"])
        else:
            aliases_str = str(project["aliases"])
    elif "alias" in project and project["alias"]:
        aliases_str = str(project["alias"])

    return aliases_str if aliases_str else "None"


@servers_app.command("list")
def list_servers(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
    include: Optional[List[str]] = typer.Option(
        None, "--include", "-i",
        help="Include filters (e.g., 'type=jenkins', 'location~=virginia', 'project_count>5')"
    ),
    exclude: Optional[List[str]] = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters (same syntax as include filters)"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields",
        help="Fields to include in output (comma-separated, e.g., 'name,type,url')"
    ),
    exclude_fields: Optional[str] = typer.Option(
        None, "--exclude-fields",
        help="Fields to exclude from output (comma-separated)"
    ),
) -> None:
    """List all registered servers (Jenkins, Gerrit, Nexus, etc.) with filtering capabilities.

    Filter examples:
    - Only Jenkins servers: --include 'type=jenkins'
    - Servers in Virginia: --include 'location~=virginia'
    - Exclude test servers: --exclude 'name~=test'
    - Show only name and URL: --fields 'name,url'
    """
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        servers = manager.list_servers()

        # Enhance servers with project display field
        for server in servers:
            projects_list = server.get("projects", [])
            if projects_list:
                # Use the first project as the primary project for display
                server["project"] = projects_list[0] if len(projects_list) == 1 else f"{projects_list[0]} (+{len(projects_list)-1})"
            else:
                server["project"] = "None"

        # Create filter from options
        data_filter = create_filter_from_options(include, exclude, fields, exclude_fields)

        # Configure table output with new column layout
        table_config = {
            "title": "Registered Servers",
            "columns": [
                {"name": "VPN Address", "field": "vpn_address", "style": "green"},
                {"name": "Location", "field": "location", "style": "yellow"},
                {"name": "Type", "field": "type", "style": "blue"},
                {"name": "Project", "field": "project", "style": "cyan"},
                {"name": "URL", "field": "url", "style": "magenta"}
            ]
        }

        # Use enhanced formatter
        format_and_output(servers, output_format, data_filter, table_config)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)





# Repository-related commands

repositories_app = typer.Typer(
    name="repositories",
    help="Repository management operations",
    no_args_is_help=True,
)

# Add the repositories sub-app to projects app
projects_app.add_typer(repositories_app, name="repositories")


@repositories_app.command("list")
def list_repositories(
    project: Optional[str] = typer.Argument(None, help="Project name to filter repositories (supports fuzzy matching)"),
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, json-pretty, json-minimal)"
    ),
    include_archived: bool = typer.Option(
        False, "--include-archived", help="Include archived/read-only repositories"
    ),
    filter_field: Optional[str] = typer.Option(
        None, "--filter-field", help="Field to filter on (e.g., 'github_name', 'scm_platform', 'language')"
    ),
    filter_value: Optional[str] = typer.Option(
        None, "--filter-value", help="Value to match in the filter field (supports partial matching)"
    ),
    show_github_only: bool = typer.Option(
        False, "--github-only", help="Show only GitHub-hosted repositories"
    ),
    show_gerrit_only: bool = typer.Option(
        False, "--gerrit-only", help="Show only Gerrit-hosted repositories"
    ),
    show_mirrors: bool = typer.Option(
        True, "--show-mirrors/--hide-mirrors", help="Show/hide mirror information in table"
    ),
) -> None:
    """List repositories for projects with advanced filtering and output options.

    Examples:

    # List all repositories in table format
    lftools-ng projects repositories list

    # List repositories for a specific project (fuzzy matching)
    lftools-ng projects repositories list onap
    lftools-ng projects repositories list "o-ran"

    # Output as JSON for processing
    lftools-ng projects repositories list --format json-pretty

    # Filter by field and value
    lftools-ng projects repositories list --filter-field language --filter-value python
    lftools-ng projects repositories list --filter-field scm_platform --filter-value github

    # Show only GitHub repositories
    lftools-ng projects repositories list --github-only

    # Include archived repositories
    lftools-ng projects repositories list --include-archived
    """
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        # Check if repositories database exists, prompt for rebuild if needed
        if not manager.ensure_repositories_database_exists():
            console.print("[yellow]⚠️  Cannot proceed without repositories database.[/yellow]")
            console.print("To manually build the database, run:")
            console.print("  [cyan]lftools-ng projects rebuild repositories --force[/cyan]")
            raise typer.Exit(1)

        repositories = manager.list_repositories(project, include_archived)

        # Apply additional filters
        filtered_repos = repositories["repositories"]

        # Filter by platform
        if show_github_only:
            filtered_repos = [r for r in filtered_repos if r.get("scm_platform") == "github"]
        elif show_gerrit_only:
            filtered_repos = [r for r in filtered_repos if r.get("scm_platform") == "gerrit"]

        # Filter by custom field
        if filter_field and filter_value:
            filter_value_lower = filter_value.lower()
            filtered_repos = [
                r for r in filtered_repos
                if filter_value_lower in str(r.get(filter_field, "")).lower()
            ]

        # Project fuzzy matching if specified
        if project:
            project_lower = project.lower()
            # Support fuzzy matching on project name
            filtered_repos = [
                r for r in filtered_repos
                if project_lower in r.get("project", "").lower()
            ]

        # Update counts based on filtered results
        filtered_total = len(filtered_repos)
        filtered_active = len([r for r in filtered_repos if not r.get("archived", False)])
        filtered_archived = filtered_total - filtered_active

        # Prepare output data
        output_data = {
            "repositories": filtered_repos,
            "total": filtered_total,
            "active": filtered_active,
            "archived": filtered_archived,
            "filters_applied": {
                "project": project,
                "include_archived": include_archived,
                "github_only": show_github_only,
                "gerrit_only": show_gerrit_only,
                "custom_filter": f"{filter_field}={filter_value}" if filter_field and filter_value else None
            }
        }

        # Output in requested format
        if output_format == "json":
            import json
            import sys
            print(json.dumps(output_data, separators=(',', ':')), file=sys.stdout)
        elif output_format == "json-pretty":
            import json
            import sys
            print(json.dumps(output_data, indent=2), file=sys.stdout)
        elif output_format == "json-minimal":
            import json
            import sys
            # Minimal JSON with just essential fields
            minimal_repos = []
            for repo in filtered_repos:
                minimal = {
                    "name": repo.get("gerrit_path", repo.get("github_name", "")),
                    "project": repo.get("project", ""),
                    "platform": repo.get("scm_platform", ""),
                    "archived": repo.get("archived", False)
                }
                if repo.get("github_name"):
                    minimal["github"] = repo["github_name"]
                if repo.get("github_url"):
                    minimal["url"] = repo["github_url"]
                minimal_repos.append(minimal)
            print(json.dumps(minimal_repos, separators=(',', ':')), file=sys.stdout)
        else:
            # Enhanced table format
            table = Table(title=f"Repositories{f' for {project}' if project else ''}")
            table.add_column("Repository", style="cyan", no_wrap=True)
            table.add_column("Project", style="yellow")
            table.add_column("Platform", style="blue")
            table.add_column("Active", style="white")

            if show_mirrors:
                table.add_column("GitHub Mirror", style="green")
                table.add_column("GitHub URL", style="dim blue", max_width=40)

            # Add language and stars columns for GitHub repos
            has_github_data = any(r.get("github_language") for r in filtered_repos)
            if has_github_data:
                table.add_column("Language", style="magenta")
                table.add_column("Stars", style="dim green", justify="right")

            for repo in filtered_repos:
                status = "�" if repo.get("archived", False) else "✅"
                platform = repo.get("scm_platform", "unknown").title()

                # Primary repository name
                repo_name = repo.get("gerrit_path", repo.get("github_name", ""))
                project_name = repo.get("project", "")

                row = [repo_name, project_name, platform, status]

                if show_mirrors:
                    github_name = repo.get("github_name", "")
                    github_url = repo.get("github_url", "")
                    row.extend([github_name, github_url])

                if has_github_data:
                    language = repo.get("github_language", repo.get("language", ""))
                    stars = str(repo.get("github_stars", repo.get("stars", "")))
                    row.extend([language, stars])

                table.add_row(*row)

            console.print(table)

            # Summary with colorized counts
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"📊 Total repositories: [cyan]{filtered_total}[/cyan]")
            console.print(f"✅ Active repositories: [green]{filtered_active}[/green]")
            if filtered_archived > 0:
                console.print(f"📦 Archived repositories: [yellow]{filtered_archived}[/yellow]")

            if project or filter_field or show_github_only or show_gerrit_only:
                console.print(f"\n[dim]Filters applied - showing subset of total repositories[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@repositories_app.command("info")
def repository_info(
    project: str = typer.Argument(..., help="Project name"),
    repository: str = typer.Argument(..., help="Repository name"),
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
) -> None:
    """Get detailed information about a specific repository."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        repo_info = manager.get_repository_info(project, repository)

        if not repo_info:
            console.print(f"[red]Repository '{repository}' not found in project '{project}'[/red]")
            raise typer.Exit(1)

        if output_format == "json":
            import json
            import sys
            print(json.dumps(repo_info, separators=(',', ':')), file=sys.stdout)
        elif output_format == "json-pretty":
            import json
            import sys
            print(json.dumps(repo_info, indent=2), file=sys.stdout)
        else:
            # Default table format
            table = Table(title=f"Repository Information: {repository}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="magenta")

            table.add_row("Project", repo_info.get("project", ""))
            table.add_row("Gerrit Path", repo_info.get("gerrit_path", "N/A"))
            table.add_row("GitHub Name", repo_info.get("github_name", "N/A"))
            table.add_row("Status", "Archived" if repo_info.get("archived", False) else "Active")
            table.add_row("Description", repo_info.get("description", "N/A"))

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@repositories_app.command("archived")
def list_archived_repositories(
    project: Optional[str] = typer.Argument(None, help="Project name to list archived repositories for"),
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
) -> None:
    """List archived/read-only repositories."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        repositories = manager.list_repositories(project, include_archived=True)
        archived_repos = [repo for repo in repositories["repositories"] if repo.get("archived", False)]

        if output_format == "json":
            import json
            import sys
            print(json.dumps({"repositories": archived_repos}, separators=(',', ':')), file=sys.stdout)
        elif output_format == "json-pretty":
            import json
            import sys
            print(json.dumps({"repositories": archived_repos}, indent=2), file=sys.stdout)
        else:
            # Default table format
            table = Table(title="Archived Repositories")
            table.add_column("Repository", style="cyan")
            table.add_column("GitHub Mirror", style="green")
            table.add_column("Project", style="yellow")

            for repo in archived_repos:
                table.add_row(
                    repo.get("gerrit_path", repo.get("github_name", "")),
                    repo.get("github_name", ""),
                    repo.get("project", "")
                )

            console.print(table)
            console.print(f"\nTotal archived repositories: {len(archived_repos)}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@rebuild_app.command("projects")
def rebuild_projects_database(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Source URL for projects configuration"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force rebuild even if database exists"
    ),
) -> None:
    """Rebuild the projects database from source configuration."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        result = manager.rebuild_projects_database(source_url=source, force=force)

        console.print(f"[green]✓[/green] Successfully rebuilt projects database")
        console.print(f"  Projects: {result['projects_count']}")
        if 'servers_count' in result:
            console.print(f"  Servers: {result['servers_count']}")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@rebuild_app.command("servers")
def rebuild_servers_database(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Source URL for servers configuration"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force rebuild even if database exists"
    ),
) -> None:
    """Rebuild the servers database from source configuration."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        result = manager.rebuild_servers_database(source_url=source, force=force)

        console.print(f"[green]✓[/green] Successfully rebuilt servers database")
        console.print(f"  Servers: {result['servers_count']}")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@rebuild_app.command("repositories")
def rebuild_repositories_database(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Source URL for repositories configuration"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force rebuild even if database exists"
    ),
) -> None:
    """Rebuild the repositories database from source configuration."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        result = manager.rebuild_repositories_database(source_url=source, force=force)

        console.print(f"[green]✓[/green] Successfully rebuilt repositories database")
        console.print(f"  Repositories: {result['repositories_count']}")
        console.print(f"  Active: {result['active_count']}")
        console.print(f"  Archived: {result['archived_count']}")

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@servers_app.command("connectivity")
def test_connectivity(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    timeout: int = typer.Option(
        3, "--timeout", "-t", help="Timeout in seconds for connectivity tests"
    ),
    username: Optional[str] = typer.Option(
        None, "--username", "-u", help="SSH username to test (if not specified, tries common usernames)"
    ),
    include: Optional[List[str]] = typer.Option(
        None, "--include", "-i",
        help="Include filters to test only specific servers"
    ),
    exclude: Optional[List[str]] = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters to skip specific servers"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed SSH test information"
    ),
    live: bool = typer.Option(
        False, "--live", "-l", help="Show results in real-time as tests complete"
    ),
) -> None:
    """Test connectivity to all registered servers using local SSH configuration.

    Tests three types of connectivity:
    1. HTTP/HTTPS URL accessibility (public internet)
    2. SSH port (TCP/22) connectivity via VPN address
    3. SSH shell access using local SSH config, keys, and authentication methods

    SSH Authentication Methods Supported:
    - SSH Agent (ssh-agent)
    - SSH keys from ~/.ssh/
    - Hardware tokens (YubiKey, etc.)
    - Secure enclave keys (Secretive, 1Password, etc.)
    - SSH config file settings (~/.ssh/config)

    Results are color-coded:
    - Green (✓): Success
    - Red (✗): Failure
    - Yellow (⚠): SSH service responding but authentication failed
    - Yellow (⏱): Timeout
    """
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        servers = manager.list_servers()

        # Filter servers if specified
        if include or exclude:
            data_filter = create_filter_from_options(include, exclude, None, None)
            if data_filter:
                servers = data_filter.filter_data(servers)

        if not servers:
            console.print("[yellow]No servers to test[/yellow]")
            return

        # Show test configuration
        config_info = f"[cyan]Testing connectivity to {len(servers)} servers (timeout: {timeout}s)[/cyan]"
        if username:
            config_info += f"\n[cyan]SSH username: {username}[/cyan]"
        else:
            config_info += "\n[cyan]SSH usernames: auto-detect (SSH config, current user, common usernames)[/cyan]"

        if verbose:
            config_info += "\n[cyan]Using local SSH config and authentication methods[/cyan]"

        console.print(config_info + "\n")

        from lftools_ng.core.connectivity import ConnectivityTester

        tester = ConnectivityTester(timeout=timeout)

        if live:
            # Live mode: Show results as they come in
            _test_connectivity_live(servers, tester, username, verbose, console)
        else:
            # Progress mode: Show progress bar with final results table
            _test_connectivity_with_progress(servers, tester, username, verbose, console)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _check_column_uniformity(projects: List[Dict[str, Any]], manager: ProjectManager) -> Dict[str, bool]:
    """Check if any columns have uniform values across all projects.

    This is a utility to detect potential bugs where data isn't being loaded correctly.

    Args:
        projects: List of project dictionaries
        manager: ProjectManager instance

    Returns:
        Dictionary mapping column names to True if uniform (potential issue)
    """
    if not projects:
        return {}

    # Extract column values
    columns: Dict[str, List[str]] = {
        "aliases": [],
        "github_org": [],
        "source": []
    }

    for project in projects:
        # Get aliases
        aliases_str = ""
        if "aliases" in project and project["aliases"]:
            if isinstance(project["aliases"], list):
                aliases_str = ", ".join(str(alias) for alias in project["aliases"])
            else:
                aliases_str = str(project["aliases"])
        elif "alias" in project and project["alias"]:
            aliases_str = str(project["alias"])

        if not aliases_str:
            aliases_str = "None"
        columns["aliases"].append(aliases_str)

        # Get GitHub org
        github_org = project.get("github_mirror_org", "")
        if not github_org:
            github_org = "Not found"
        columns["github_org"].append(github_org)

        # Get source
        source = _determine_project_primary_scm(project, manager)
        columns["source"].append(source)

    # Check for uniformity
    uniform_columns = {}
    for column_name, values in columns.items():
        unique_values = set(values)
        uniform_columns[column_name] = len(unique_values) == 1

    return uniform_columns


def _determine_project_primary_scm(project: Dict[str, Any], manager: ProjectManager) -> str:
    """Determine the primary SCM (Source Code Management) platform for a project.

    Args:
        project: Project data dictionary
        manager: ProjectManager instance for accessing server data

    Returns:
        Primary SCM platform: "Gerrit", "GitHub", "GitLab", "Git", or "Unknown"
    """
    # First check if project data includes scm_platform or primary_scm
    scm_platform = project.get("scm_platform") or project.get("primary_scm")
    if scm_platform and isinstance(scm_platform, str):
        # Capitalize for display consistency
        return scm_platform.capitalize()

    # Check if project data includes primary_scm_platform
    primary_scm_platform = project.get("primary_scm_platform")
    if primary_scm_platform and isinstance(primary_scm_platform, str):
        return primary_scm_platform

    # Fallback: Check if project has explicit gerrit_url configuration
    gerrit_url = project.get("gerrit_url")
    if gerrit_url:
        return "Gerrit"

    # Check for GitHub organization
    github_org = project.get("github_mirror_org")
    if github_org:
        return "GitHub"

    # Try to find the project in aliases by name matching
    from lftools_ng.core.models import PROJECT_ALIASES
    
    project_name = project.get("name", "")
    if isinstance(project_name, str):
        project_lower = project_name.lower()
        for alias_key, alias_data in PROJECT_ALIASES.items():
            if (project_lower == alias_data.get("primary_name", "").lower() or
                project_lower in [alias.lower() for alias in alias_data.get("aliases", [])] or
                any(project_lower == pattern.lower() for pattern in alias_data.get("name_patterns", []))):
                scm_platform = alias_data.get("primary_scm_platform", "Unknown")
                if scm_platform != "Unknown" and isinstance(scm_platform, str):
                    return scm_platform

    # Final fallback
    return "Unknown"


def _test_connectivity_live(servers: List[Dict[str, Any]], tester, username: Optional[str], verbose: bool, console) -> None:
    """Test connectivity with live updating results."""
    from rich.live import Live
    from rich.table import Table

    # Create the results table
    table = Table(title="Server Connectivity Test Results (Live)")
    table.add_column("Server", style="cyan", no_wrap=True)
    table.add_column("URL Test", justify="center")
    table.add_column("SSH Port", justify="center")
    table.add_column("SSH Shell", justify="center")
    if verbose:
        table.add_column("Details", style="dim")
    table.add_column("VPN Address", style="dim")

    # Create a status message
    status_table = Table.grid()
    status_table.add_column()
    status_table.add_row("[cyan]Starting connectivity tests...[/cyan]")

    # Combine status and results
    main_table = Table.grid()
    main_table.add_column()
    main_table.add_row(status_table)
    main_table.add_row("")
    main_table.add_row(table)

    with Live(main_table, console=console, refresh_per_second=10) as live:
        for i, server in enumerate(servers):
            server_name = server.get("name", "Unknown")
            server_url = server.get("url", "")
            vpn_address = server.get("vpn_address", "")

            # Show we're starting this server
            status_table = Table.grid()
            status_table.add_column()
            status_table.add_row(f"[yellow]Testing {server_name} ({i+1}/{len(servers)}) - URL test...[/yellow]")

            main_table = Table.grid()
            main_table.add_column()
            main_table.add_row(status_table)
            main_table.add_row("")
            main_table.add_row(table)

            live.update(main_table)

            # Test URL accessibility
            url_result = tester.test_url(server_url) if server_url else "N/A"

            # Update status for SSH port test
            status_table = Table.grid()
            status_table.add_column()
            status_table.add_row(f"[yellow]Testing {server_name} ({i+1}/{len(servers)}) - SSH port test...[/yellow]")

            main_table = Table.grid()
            main_table.add_column()
            main_table.add_row(status_table)
            main_table.add_row("")
            main_table.add_row(table)

            live.update(main_table)

            # Test SSH port connectivity
            ssh_port_result = tester.test_ssh_port(vpn_address) if vpn_address else "N/A"

            # Update status for SSH shell test
            status_table = Table.grid()
            status_table.add_column()
            status_table.add_row(f"[yellow]Testing {server_name} ({i+1}/{len(servers)}) - SSH shell access...[/yellow]")

            main_table = Table.grid()
            main_table.add_column()
            main_table.add_row(status_table)
            main_table.add_row("")
            main_table.add_row(table)

            live.update(main_table)

            # Test SSH shell access
            if vpn_address:
                ssh_shell_result = tester.test_ssh_shell(vpn_address, username=username, verbose=verbose)
            else:
                ssh_shell_result = "N/A"

            # Build row data
            row_data = [
                server_name,
                url_result,
                ssh_port_result,
                ssh_shell_result,
            ]

            if verbose:
                # Add details about the test results and SSH details
                details = []
                if server_url and url_result != "N/A":
                    details.append(f"URL: {server_url}")
                if vpn_address:
                    details.append(f"SSH: {vpn_address}:22")

                    # Get SSH-specific details if available
                    ssh_details = tester.get_last_ssh_details()
                    if ssh_details:
                        if ssh_details.get("successful_username"):
                            details.append(f"User: {ssh_details['successful_username']}")
                        elif ssh_details.get("attempted_usernames"):
                            attempted = ", ".join(ssh_details["attempted_usernames"][:3])  # Limit to first 3
                            if len(ssh_details["attempted_usernames"]) > 3:
                                attempted += "..."
                            details.append(f"Tried: {attempted}")

                        if ssh_details.get("auth_methods_tried"):
                            auth_methods = ", ".join(set(ssh_details["auth_methods_tried"]))
                            details.append(f"Auth: {auth_methods}")

                details_str = " | ".join(details) if details else "No details"
                row_data.append(details_str)

            row_data.append(vpn_address or "None")
            table.add_row(*row_data)

            # Update the display with completed server
            status_table = Table.grid()
            status_table.add_column()
            status_table.add_row(f"[green]✓[/green] {server_name} completed ({i+1}/{len(servers)})")

            main_table = Table.grid()
            main_table.add_column()
            main_table.add_row(status_table)
            main_table.add_row("")
            main_table.add_row(table)

            live.update(main_table)

        # Final status
        status_table = Table.grid()
        status_table.add_column()
        status_table.add_row("[green]✓ All connectivity tests completed![/green]")

        main_table = Table.grid()
        main_table.add_column()
        main_table.add_row(status_table)
        main_table.add_row("")
        main_table.add_row(table)

        live.update(main_table)

    # Show legend
    console.print("\n[bold]Legend:[/bold]")
    console.print("  [green]✓[/green] Success")
    console.print("  [red]✗[/red] Failure")
    console.print("  [yellow]⚠[/yellow] SSH service responding, authentication failed")
    console.print("  [yellow]⏱[/yellow] Timeout")
    console.print("  [yellow]☁[/yellow] Cloudflare CDN blocked")
    console.print("  [dim]N/A[/dim] Test not applicable")


def _test_connectivity_with_progress(servers: List[Dict[str, Any]], tester, username: Optional[str], verbose: bool, console) -> None:
    """Test connectivity with progress bar and final results table."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table

    # Create the results table
    table = Table(title="Server Connectivity Test Results")
    table.add_column("Server", style="cyan", no_wrap=True)
    table.add_column("URL Test", justify="center")
    table.add_column("SSH Port", justify="center")
    table.add_column("SSH Shell", justify="center")
    if verbose:
        table.add_column("Details", style="dim")
    table.add_column("VPN Address", style="dim")

    # Set up progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        # Create main progress task
        main_task = progress.add_task(
            "[cyan]Testing server connectivity...",
            total=len(servers)
        )

        # Track current server being tested
        current_task = progress.add_task(
            "[dim]Preparing tests...",
            total=None
        )

        for server in servers:
            server_name = server.get("name", "Unknown")
            server_url = server.get("url", "")
            vpn_address = server.get("vpn_address", "")

            # Update current server status
            progress.update(
                current_task,
                description=f"[yellow]Testing {server_name}..."
            )

            # Test URL accessibility
            progress.update(current_task, description=f"[yellow]Testing {server_name} - URL...")
            url_result = tester.test_url(server_url) if server_url else "N/A"

            # Test SSH port connectivity
            progress.update(current_task, description=f"[yellow]Testing {server_name} - SSH Port...")
            ssh_port_result = tester.test_ssh_port(vpn_address) if vpn_address else "N/A"

            # Test SSH shell access with specified or auto-detected username
            progress.update(current_task, description=f"[yellow]Testing {server_name} - SSH Shell...")
            if vpn_address:
                ssh_shell_result = tester.test_ssh_shell(vpn_address, username=username, verbose=verbose)
            else:
                ssh_shell_result = "N/A"

            # Build row data
            row_data = [
                server_name,
                url_result,
                ssh_port_result,
                ssh_shell_result,
            ]

            if verbose:
                # Add details about the test results and SSH details
                details = []
                if server_url and url_result != "N/A":
                    details.append(f"URL: {server_url}")
                if vpn_address:
                    details.append(f"SSH: {vpn_address}:22")

                    # Get SSH-specific details if available
                    ssh_details = tester.get_last_ssh_details()
                    if ssh_details:
                        if ssh_details.get("successful_username"):
                            details.append(f"User: {ssh_details['successful_username']}")
                        elif ssh_details.get("attempted_usernames"):
                            attempted = ", ".join(ssh_details["attempted_usernames"][:3])  # Limit to first 3
                            if len(ssh_details["attempted_usernames"]) > 3:
                                attempted += "..."
                            details.append(f"Tried: {attempted}")

                        if ssh_details.get("auth_methods_tried"):
                            auth_methods = ", ".join(set(ssh_details["auth_methods_tried"]))
                            details.append(f"Auth: {auth_methods}")

                details_str = " | ".join(details) if details else "No details"
                row_data.append(details_str)

            row_data.append(vpn_address or "None")
            table.add_row(*row_data)

            # Update progress and show completion status
            progress.update(main_task, advance=1)
            progress.update(
                current_task,
                description=f"[green]✓[/green] {server_name} completed"
            )

        # Final status
        progress.update(current_task, description="[green]All tests completed!")

    # Show final results table
    console.print("\n")
    console.print(table)

    # Show legend
    console.print("\n[bold]Legend:[/bold]")
    console.print("  [green]✓[/green] Success")
    console.print("  [red]✗[/red] Failure")
    console.print("  [yellow]⚠[/yellow] SSH service responding, authentication failed")
    console.print("  [yellow]⏱[/yellow] Timeout")
    console.print("  [yellow]☁[/yellow] Cloudflare CDN blocked")
    console.print("  [dim]N/A[/dim] Test not applicable")


@servers_app.callback(invoke_without_command=True)
def servers_default(
    ctx: typer.Context,
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
    include: Optional[List[str]] = typer.Option(
        None, "--include", "-i",
        help="Include filters (e.g., 'type=jenkins', 'location~=virginia', 'project_count>5')"
    ),
    exclude: Optional[List[str]] = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters (same syntax as include filters)"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields",
        help="Fields to include in output (comma-separated, e.g., 'name,type,url')"
    ),
    exclude_fields: Optional[str] = typer.Option(
        None, "--exclude-fields",
        help="Fields to exclude from output (comma-separated)"
    ),
) -> None:
    """List all registered servers (Jenkins, Gerrit, Nexus, etc.) with filtering capabilities.

    This is the default command when running 'projects servers' without subcommands.

    Filter examples:
    - Only Jenkins servers: --include 'type=jenkins'
    - Servers in Virginia: --include 'location~=virginia'
    - Exclude test servers: --exclude 'name~=test'
    - Show only name and URL: --fields 'name,url'
    """
    # If a subcommand was provided, don't execute the default behavior
    if ctx.invoked_subcommand is not None:
        return

    # Call the list_servers function with the same parameters
    list_servers(
        config_dir=config_dir,
        output_format=output_format,
        include=include,
        exclude=exclude,
        fields=fields,
        exclude_fields=exclude_fields,
    )
