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

projects_app = typer.Typer(
    name="projects",
    help="Project management operations",
    no_args_is_help=True,
)
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
) -> None:
    """List all registered projects."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        projects = manager.list_projects()

        # Check for column uniformity if requested
        if check_uniformity:
            uniform_issues = _check_column_uniformity(projects, manager)
            if any(uniform_issues.values()):
                console.print("\n[yellow]⚠️  Data Quality Warning:[/yellow]")
                for column, is_uniform in uniform_issues.items():
                    if is_uniform:
                        console.print(f"[yellow]  - Column '{column}' has uniform values across all projects[/yellow]")
                console.print()

        if output_format in ["json", "json-pretty", "yaml"]:
            format_output(projects, output_format)
            return

        # Default table format
        table = Table()
        table.add_column("Project", style="cyan")
        table.add_column("Aliases", style="magenta")
        table.add_column("GitHub Org", style="green")
        table.add_column("Source", style="blue")

        for project in projects:
            # Handle both 'aliases' (list) and 'alias' (string) fields
            aliases_str = ""
            if "aliases" in project and project["aliases"]:
                if isinstance(project["aliases"], list):
                    aliases_str = ", ".join(project["aliases"])
                else:
                    aliases_str = str(project["aliases"])
            elif "alias" in project and project["alias"]:
                aliases_str = str(project["alias"])

            if not aliases_str:
                aliases_str = "None"

            github_org = project.get("github_mirror_org", "")
            if not github_org:
                github_org = "Not found"

            # Determine source repository type
            source = _determine_project_source(project, manager)

            table.add_row(
                project.get("name", ""),
                aliases_str,
                github_org,
                source
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@projects_app.command("servers")
def list_servers(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
) -> None:
    """List all registered servers (Jenkins, Gerrit, Nexus, etc.)."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        servers = manager.list_servers()

        if output_format in ["json", "json-pretty", "yaml"]:
            format_output(servers, output_format)
            return

        # Default table format
        table = Table()
        table.add_column("Server", style="cyan")
        table.add_column("Type", style="blue")
        table.add_column("URL", style="magenta")
        table.add_column("Location", style="yellow")
        table.add_column("VPN Address", style="green")
        table.add_column("Projects", style="white")

        for server in servers:
            table.add_row(
                server.get("name", ""),
                server.get("type", ""),
                server.get("url", ""),
                server.get("location", ""),
                server.get("vpn_address", ""),
                str(server.get("project_count", 0))
            )

        console.print(table)

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
    project: Optional[str] = typer.Argument(None, help="Project name to list repositories for"),
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
    include_archived: bool = typer.Option(
        False, "--include-archived", help="Include archived/read-only repositories"
    ),
) -> None:
    """List repositories for projects."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        repositories = manager.list_repositories(project, include_archived)

        if output_format == "json":
            import json
            import sys
            print(json.dumps(repositories, separators=(',', ':')), file=sys.stdout)
        elif output_format == "json-pretty":
            import json
            import sys
            print(json.dumps(repositories, indent=2), file=sys.stdout)
        else:
            # Default table format
            table = Table()
            table.add_column("Repository", style="cyan")
            table.add_column("GitHub Mirror", style="green")
            table.add_column("Status", style="blue")
            table.add_column("Project", style="yellow")

            active_count = 0
            archived_count = 0

            for repo in repositories["repositories"]:
                status = "Archived" if repo.get("archived", False) else "Active"
                if repo.get("archived", False):
                    archived_count += 1
                else:
                    active_count += 1

                table.add_row(
                    repo.get("gerrit_path", repo.get("github_name", "")),
                    repo.get("github_name", ""),
                    status,
                    repo.get("project", "")
                )

            console.print(table)
            console.print(f"\nTotal repositories: {len(repositories['repositories'])}")
            console.print(f"Active repositories: {active_count}")
            console.print(f"Archived repositories: {archived_count}")

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


@projects_app.command("rebuild-projects")
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


@projects_app.command("rebuild-servers")
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
        source = _determine_project_source(project, manager)
        columns["source"].append(source)

    # Check for uniformity
    uniform_columns = {}
    for column_name, values in columns.items():
        unique_values = set(values)
        uniform_columns[column_name] = len(unique_values) == 1

    return uniform_columns


def _determine_project_source(project: Dict[str, Any], manager: ProjectManager) -> str:
    """Determine the primary source repository type for a project.

    Args:
        project: Project data dictionary
        manager: ProjectManager instance for accessing server data

    Returns:
        Source type: "Gerrit", "GitHub", or "Unknown"
    """
    project_name = project.get("name", "")

    # Check if project has an active Gerrit server - this is the definitive indicator
    try:
        servers = manager.list_servers()

        # Look for Gerrit servers associated with this project
        for server in servers:
            if server.get("type") == "gerrit":
                server_projects = server.get("projects", [])
                if project_name in server_projects:
                    return "Gerrit"

    except Exception:
        # If we can't load servers, fall back to other checks
        pass

    # Check repository data for Gerrit indicators
    try:
        repositories_data = manager.list_repositories(project_name)
        repositories = repositories_data.get("repositories", [])

        for repo in repositories:
            # Check if repository's project matches our project name
            if repo.get("project", "").lower() == project_name.lower():
                # Check if repository description mentions gerrit
                description = repo.get("description", "")
                if "gerrit" in description.lower():
                    return "Gerrit"

                # Check if repository has gerrit_path
                if repo.get("gerrit_path"):
                    return "Gerrit"

    except Exception:
        # If we can't load repositories, continue with fallbacks
        pass

    # Fallback: Check if project has explicit gerrit_url configuration
    gerrit_url = project.get("gerrit_url")
    if gerrit_url:
        return "Gerrit"

    # Default to GitHub if we have a GitHub org, otherwise Unknown
    github_org = project.get("github_mirror_org")
    if github_org:
        return "GitHub"

    return "Unknown"
