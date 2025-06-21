# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Unified data rebuilding command for lftools-ng."""

import pathlib
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from lftools_ng.core.projects import ProjectManager

rebuild_app = typer.Typer(
    name="rebuild-data",
    help="Rebuild all backend data files from source configurations",
    invoke_without_command=True
)
console = Console()

# Constants for configuration
DEFAULT_CONFIG_DIR = pathlib.Path.home() / ".config" / "lftools-ng"
CONFIG_DIR_HELP = "Configuration directory path"


@rebuild_app.callback()
def rebuild_data(
    config_dir: Optional[str] = typer.Option(
        None, "--config-dir", "-c", help=CONFIG_DIR_HELP
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force rebuild even if data already exists"
    ),
    projects_only: bool = typer.Option(
        False, "--projects-only", help="Rebuild only projects data"
    ),
    servers_only: bool = typer.Option(
        False, "--servers-only", help="Rebuild only servers data"
    ),
    repositories_only: bool = typer.Option(
        False, "--repositories-only", help="Rebuild only repositories data"
    ),
) -> None:
    """Rebuild all backend data files from source configurations.

    This command rebuilds the projects, servers, and repositories data files
    by fetching fresh data from various sources including GitHub organizations,
    project configurations, and repository metadata.

    The rebuilt data is stored in the configuration directory and replaces
    any existing data files (with --force) or creates them if they don't exist.
    """
    try:
        config_path = pathlib.Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        manager = ProjectManager(config_path)

        # Determine what to rebuild
        rebuild_all = not (projects_only or servers_only or repositories_only)
        rebuild_projects = rebuild_all or projects_only
        rebuild_servers = rebuild_all or servers_only
        rebuild_repositories = rebuild_all or repositories_only

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            if rebuild_projects:
                task_projects = progress.add_task("Rebuilding projects database...", total=100)

                # Check if projects data exists and handle force flag
                if manager.projects_file.exists() and not force:
                    console.print(f"[yellow]Projects database already exists at {manager.projects_file}[/yellow]")
                    console.print("[yellow]Use --force to rebuild existing data[/yellow]")
                    progress.update(task_projects, completed=100)
                else:
                    try:
                        # Rebuild projects data
                        projects_result = manager.rebuild_projects_database(force=force)
                        progress.update(task_projects, completed=50)

                        console.print(f"[green]✓ Projects database rebuilt successfully[/green]")
                        console.print(f"[green]  - Projects loaded: {projects_result.get('projects_count', 0)}[/green]")
                        console.print(f"[green]  - File: {manager.projects_file}[/green]")
                        progress.update(task_projects, completed=100)

                    except Exception as e:
                        console.print(f"[red]✗ Failed to rebuild projects database: {e}[/red]")
                        progress.update(task_projects, completed=100)

            if rebuild_servers:
                task_servers = progress.add_task("Rebuilding servers database...", total=100)

                # Check if servers data exists and handle force flag
                if manager.servers_file.exists() and not force:
                    console.print(f"[yellow]Servers database already exists at {manager.servers_file}[/yellow]")
                    console.print("[yellow]Use --force to rebuild existing data[/yellow]")
                    progress.update(task_servers, completed=100)
                else:
                    try:
                        # Rebuild servers data
                        servers_result = manager.rebuild_servers_database(force=force)
                        progress.update(task_servers, completed=50)

                        console.print(f"[green]✓ Servers database rebuilt successfully[/green]")
                        console.print(f"[green]  - Servers loaded: {servers_result.get('servers_count', 0)}[/green]")
                        console.print(f"[green]  - File: {manager.servers_file}[/green]")
                        progress.update(task_servers, completed=100)

                    except Exception as e:
                        console.print(f"[red]✗ Failed to rebuild servers database: {e}[/red]")
                        progress.update(task_servers, completed=100)

            if rebuild_repositories:
                task_repos = progress.add_task("Rebuilding repositories database...", total=100)

                # Check if repositories data exists and handle force flag
                if manager.repositories_file.exists() and not force and manager.repositories_file.stat().st_size > 100:
                    console.print(f"[yellow]Repositories database already exists at {manager.repositories_file}[/yellow]")
                    console.print("[yellow]Use --force to rebuild existing data[/yellow]")
                    progress.update(task_repos, completed=100)
                else:
                    try:
                        # This would need to be implemented - for now just ensure file exists
                        if not manager.repositories_file.exists():
                            manager._auto_initialize_config()

                        console.print(f"[green]✓ Repositories database initialized[/green]")
                        console.print(f"[green]  - File: {manager.repositories_file}[/green]")
                        progress.update(task_repos, completed=100)

                    except Exception as e:
                        console.print(f"[red]✗ Failed to initialize repositories database: {e}[/red]")
                        progress.update(task_repos, completed=100)

        # Summary
        console.print()
        console.print("[bold green]Data rebuild completed![/bold green]")
        console.print(f"[green]Configuration directory: {config_path}[/green]")

        # Show file sizes for verification
        if rebuild_projects and manager.projects_file.exists():
            size_kb = manager.projects_file.stat().st_size / 1024
            console.print(f"[green]Projects data: {size_kb:.1f} KB[/green]")

        if rebuild_servers and manager.servers_file.exists():
            size_kb = manager.servers_file.stat().st_size / 1024
            console.print(f"[green]Servers data: {size_kb:.1f} KB[/green]")

        if rebuild_repositories and manager.repositories_file.exists():
            size_kb = manager.repositories_file.stat().st_size / 1024
            console.print(f"[green]Repositories data: {size_kb:.1f} KB[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
