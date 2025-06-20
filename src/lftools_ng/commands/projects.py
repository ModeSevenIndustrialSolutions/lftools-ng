# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Enhanced project management commands for lftools-ng."""

import pathlib
from typing import Any, Dict, Optional

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
        console.print(json.dumps(data, separators=(',', ':')))
    elif output_format == "json-pretty":
        import json
        console.print(json.dumps(data, indent=2))
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
) -> None:
    """List all registered projects with their Jenkins server mappings."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        projects = manager.list_projects()

        if output_format in ["json", "json-pretty", "yaml"]:
            format_output(projects, output_format)
            return

        # Default table format
        table = Table()
        table.add_column("Project", style="cyan")
        table.add_column("Aliases", style="magenta")
        table.add_column("GitHub Org", style="green")
        table.add_column("Gerrit", style="blue")

        for project in projects:
            aliases_str = ", ".join(project.get("aliases", []))
            if not aliases_str:
                aliases_str = "None"

            github_org = project.get("github_mirror_org", "")
            if not github_org:
                github_org = "Not found"

            gerrit_url = project.get("gerrit_url", "")
            if gerrit_url:
                # Show just the domain for brevity
                gerrit_domain = gerrit_url.replace("https://", "").replace("http://", "").split("/")[0]
            else:
                gerrit_domain = "None"

            table.add_row(
                project.get("name", ""),
                aliases_str,
                github_org,
                gerrit_domain
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
    """List all registered Jenkins servers."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        servers = manager.list_servers()

        if output_format in ["json", "json-pretty", "yaml"]:
            format_output(servers, output_format)
            return

        # Default table format
            table = Table()
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="blue")
            table.add_column("URL", style="magenta")
            table.add_column("Location", style="yellow")
            table.add_column("VPN Address", style="green")
            table.add_column("Projects", style="white")

            for server in servers:
                # Show project count or "shared" for shared infrastructure
                projects_info = str(server.get("project_count", 0))
                if server.get("project_count", 0) == 0 and server.get("type") == "nexus-iq":
                    projects_info = "shared"

                table.add_row(
                    server.get("name", ""),
                    server.get("type", ""),
                    server.get("url", ""),
                    server.get("location", ""),
                    server.get("vpn_address", ""),
                    projects_info
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@projects_app.command("rebuild-projects")
def rebuild_projects_db(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    source_url: Optional[str] = typer.Option(
        None, "--source", "-s", help="Source URL for project configuration"
    ),
    force: bool = typer.Option(
        False, "--force", help="Force rebuild even if database exists"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
) -> None:
    """Rebuild the projects database from source configuration."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        if output_format not in ["json", "json-pretty"]:
            console.print("[blue]Rebuilding projects database...[/blue]")

        result = manager.rebuild_projects_database(source_url=source_url, force=force)

        if output_format in ["json", "json-pretty"]:
            format_output(result, output_format)
        else:
            console.print("[green]Successfully rebuilt projects database[/green]")
            console.print(f"Projects loaded: {result.get('projects_count', 0)}")
            console.print(f"Servers discovered: {result.get('servers_count', 0)}")

    except Exception as e:
        if output_format in ["json", "json-pretty"]:
            error_result = {"error": str(e), "success": False}
            format_output(error_result, output_format)
        else:
            console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@projects_app.command("rebuild-servers")
def rebuild_servers_db(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    source_url: Optional[str] = typer.Option(
        None, "--source", "-s", help="Source URL for server configuration"
    ),
    force: bool = typer.Option(
        False, "--force", help="Force rebuild even if database exists"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
) -> None:
    """Rebuild the servers database from source configuration."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        if output_format not in ["json", "json-pretty"]:
            console.print("[blue]Rebuilding servers database...[/blue]")

        result = manager.rebuild_servers_database(force=force)

        if output_format in ["json", "json-pretty"]:
            format_output(result, output_format)
        else:
            console.print("[green]Successfully rebuilt servers database[/green]")
            console.print(f"Servers loaded: {result.get('servers_count', 0)}")
            console.print(f"Projects mapped: {result.get('projects_mapped', 0)}")

    except Exception as e:
        if output_format in ["json", "json-pretty"]:
            error_result = {"error": str(e), "success": False}
            format_output(error_result, output_format)
        else:
            console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@projects_app.command("add-project")
def add_project(
    name: str = typer.Argument(..., help="Project name"),
    primary_name: Optional[str] = typer.Option(None, "--primary", "-p", help="Primary project name"),
    aliases: Optional[str] = typer.Option(None, "--aliases", "-a", help="Project aliases (comma-separated)"),
    jenkins_production: Optional[str] = typer.Option(None, "--jenkins-prod", help="Production Jenkins URL"),
    jenkins_sandbox: Optional[str] = typer.Option(None, "--jenkins-sandbox", help="Sandbox Jenkins URL"),
    gerrit_url: Optional[str] = typer.Option(None, "--gerrit", help="Gerrit repository URL"),
    github_org: Optional[str] = typer.Option(None, "--github", help="GitHub organization"),
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
) -> None:
    """Add a new project to the database."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        project_data = {
            "name": name,
            "primary_name": primary_name or name,
            "aliases": aliases.split(",") if aliases else [],
            "previous_names": [],
            "jenkins_production": jenkins_production,
            "jenkins_sandbox": jenkins_sandbox,
            "gerrit_url": gerrit_url,
            "github_mirror_org": github_org,
        }

        # Attempt GitHub discovery if no GitHub org provided
        if not github_org:
            if output_format not in ["json", "json-pretty"]:
                console.print(f"[blue]Discovering GitHub organization for {name}...[/blue]")

            from lftools_ng.core.github_discovery import GitHubDiscovery

            with GitHubDiscovery() as github_discovery:
                discovered_org = github_discovery.discover_github_organization(project_data)
                if discovered_org:
                    project_data["github_mirror_org"] = discovered_org
                    if output_format not in ["json", "json-pretty"]:
                        console.print(f"[green]Discovered GitHub organization: {discovered_org}[/green]")
                else:
                    if output_format not in ["json", "json-pretty"]:
                        console.print("[yellow]No GitHub organization found[/yellow]")

        manager.add_project(project_data)

        if output_format in ["json", "json-pretty"]:
            result = {
                "success": True,
                "message": f"Successfully added project: {name}",
                "project": project_data
            }
            format_output(result, output_format)
        else:
            console.print(f"[green]Successfully added project: {name}[/green]")

        # Show project summary
        if project_data.get("github_mirror_org") and output_format not in ["json", "json-pretty"]:
            console.print(f"GitHub organization: {project_data['github_mirror_org']}")

    except Exception as e:
        if output_format in ["json", "json-pretty"]:
            error_result = {"error": str(e), "success": False}
            format_output(error_result, output_format)
        else:
            console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@projects_app.command("add-server")
def add_server(
    name: str = typer.Argument(..., help="Server name"),
    url: str = typer.Option(..., "--url", "-u", help="Server URL"),
    server_type: str = typer.Option("jenkins", "--type", "-t", help="Server type (jenkins, gerrit, nexus, nexus3, etc.)"),
    location: str = typer.Option("other", "--location", "-l", help="Server location (vexxhost, aws, korg, other)"),
    vpn_address: Optional[str] = typer.Option(None, "--vpn", help="VPN IP address"),
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help=OUTPUT_FORMAT_HELP
    ),
) -> None:
    """Add a new server to the database."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        server_data: Dict[str, Any] = {
            "name": name,
            "url": url,
            "type": server_type,
            "location": location,
            "vpn_address": vpn_address,
            "is_production": True,
            "projects": []
        }

        manager.add_server(server_data)

        if output_format in ["json", "json-pretty"]:
            result = {
                "success": True,
                "message": f"Successfully added server: {name}",
                "server": server_data
            }
            format_output(result, output_format)
        else:
            console.print(f"[green]Successfully added server: {name}[/green]")

    except Exception as e:
        if output_format in ["json", "json-pretty"]:
            error_result = {"error": str(e), "success": False}
            format_output(error_result, output_format)
        else:
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
            console.print(json.dumps(repositories, separators=(',', ':')))
        elif output_format == "json-pretty":
            import json
            console.print(json.dumps(repositories, indent=2))
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
            console.print(json.dumps(repo_info, separators=(',', ':')))
        elif output_format == "json-pretty":
            import json
            console.print(json.dumps(repo_info, indent=2))
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
            console.print(json.dumps({"repositories": archived_repos}, separators=(',', ':')))
        elif output_format == "json-pretty":
            import json
            console.print(json.dumps({"repositories": archived_repos}, indent=2))
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
