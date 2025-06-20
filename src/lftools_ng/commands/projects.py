# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Enhanced project management commands for lftools-ng."""

import pathlib
from typing import Optional

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


@projects_app.command("list")
def list_projects(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format (table, json, yaml)"
    ),
) -> None:
    """List all registered projects with their Jenkins server mappings."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        projects = manager.list_projects()

        if output_format == "json":
            import json
            console.print(json.dumps(projects, indent=2))
        elif output_format == "yaml":
            console.print(yaml.dump(projects, default_flow_style=False))
        else:
            # Default table format
            table = Table()
            table.add_column("Project", style="cyan")
            table.add_column("Aliases", style="magenta")

            for project in projects:
                aliases_str = ", ".join(project.get("aliases", []))
                if not aliases_str:
                    aliases_str = "None"

                table.add_row(
                    project.get("name", ""),
                    aliases_str
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
        "table", "--format", "-f", help="Output format (table, json, yaml)"
    ),
) -> None:
    """List all registered Jenkins servers."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)
        servers = manager.list_servers()

        if output_format == "json":
            import json
            console.print(json.dumps(servers, indent=2))
        elif output_format == "yaml":
            console.print(yaml.dump(servers, default_flow_style=False))
        else:
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
) -> None:
    """Rebuild the projects database from source configuration."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        console.print("[blue]Rebuilding projects database...[/blue]")
        result = manager.rebuild_projects_database(source_url=source_url, force=force)

        console.print("[green]Successfully rebuilt projects database[/green]")
        console.print(f"Projects loaded: {result.get('projects_count', 0)}")
        console.print(f"Servers discovered: {result.get('servers_count', 0)}")

    except Exception as e:
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
) -> None:
    """Rebuild the servers database from source configuration."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        console.print("[blue]Rebuilding servers database...[/blue]")
        result = manager.rebuild_servers_database(force=force)

        console.print("[green]Successfully rebuilt servers database[/green]")
        console.print(f"Servers loaded: {result.get('servers_count', 0)}")
        console.print(f"Projects mapped: {result.get('projects_mapped', 0)}")

    except Exception as e:
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

        manager.add_project(project_data)
        console.print(f"[green]Successfully added project: {name}[/green]")

    except Exception as e:
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
) -> None:
    """Add a new server to the database."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        server_data = {
            "name": name,
            "url": url,
            "type": server_type,
            "location": location,
            "vpn_address": vpn_address,
            "is_production": True,
            "projects": []
        }

        manager.add_server(server_data)
        console.print(f"[green]Successfully added server: {name}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@projects_app.command("enhance-servers")
def enhance_servers(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
) -> None:
    """Enhance existing servers with inferred URLs for servers missing URLs."""
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        console.print("Enhancing servers with inferred URLs...")
        result = manager.enhance_existing_servers()

        console.print(f"✅ Enhanced {result['servers_enhanced']} out of {result['servers_total']} servers")

        if result['servers_enhanced'] > 0:
            console.print("Use 'lftools-ng projects servers' to see the updated server list.")
        else:
            console.print("No servers needed URL enhancement.")

    except Exception as e:
        console.print(f"❌ Error enhancing servers: {e}")
        raise typer.Exit(1)
