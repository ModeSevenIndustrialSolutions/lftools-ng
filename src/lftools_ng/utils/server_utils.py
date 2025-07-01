# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Server utilities for lftools-ng."""

import logging
import pathlib
import sys
from typing import Optional, Dict, Any
import yaml
from rich.console import Console
from rich.prompt import Confirm

logger = logging.getLogger(__name__)
console = Console()

def get_servers_file_path() -> pathlib.Path:
    """Get the path to the servers.yaml file."""
    config_dir = pathlib.Path.home() / ".config" / "lftools-ng"
    return config_dir / "servers.yaml"

def ensure_servers_file_exists() -> bool:
    """
    Ensure the servers.yaml file exists. If not, prompt user to build it.

    Returns:
        bool: True if file exists or was successfully created, False otherwise
    """
    servers_file = get_servers_file_path()

    if servers_file.exists():
        return True

    console.print(f"[yellow]Servers file not found: {servers_file}[/yellow]")

    if Confirm.ask("Would you like to build the servers database now?", default=True):
        try:
            console.print("[blue]Building servers database (this will also rebuild projects if needed)...[/blue]")

            # Import here to avoid circular imports
            from lftools_ng.core.projects import ProjectManager

            config_dir = servers_file.parent
            manager = ProjectManager(config_dir)

            # Use the same code path as "lftools-ng projects rebuild-projects"
            # This will build both projects and servers together
            result = manager.rebuild_projects_database(force=True)

            if servers_file.exists():
                console.print(f"[green]Successfully built servers database with {result.get('servers_count', 0)} servers![/green]")
                if 'projects_count' in result:
                    console.print(f"[green]Also built {result['projects_count']} projects.[/green]")
                return True
            else:
                console.print("[red]Failed to create servers database.[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error building servers database: {e}[/red]")
            logger.error(f"Error building servers database: {e}")
            return False
    else:
        console.print("[yellow]Cannot proceed without servers database.[/yellow]")
        return False

def load_servers_data() -> Optional[Dict[str, Any]]:
    """
    Load servers data from the YAML file, ensuring it exists first.

    Returns:
        Optional[Dict[str, Any]]: The servers data or None if unavailable
    """
    if not ensure_servers_file_exists():
        return None

    servers_file = get_servers_file_path()

    try:
        with open(servers_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[red]Error loading servers file: {e}[/red]")
        logger.error(f"Error loading servers file: {e}")
        return None

def get_server_config(server_name: str) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific server.

    Args:
        server_name: Name of the server to get config for

    Returns:
        Optional[Dict[str, Any]]: Server configuration or None if not found
    """
    servers_data = load_servers_data()
    if not servers_data:
        return None

    servers = servers_data.get('servers', {})
    if isinstance(servers, list):
        # Handle list format - find by name
        for server in servers:
            if isinstance(server, dict) and server.get('name') == server_name:
                return server
        return None
    else:
        # Handle dict format
        return servers.get(server_name)

def get_all_servers() -> Dict[str, Any]:
    """
    Get all server configurations.

    Returns:
        Dict[str, Any]: All server configurations or empty dict if unavailable
    """
    servers_data = load_servers_data()
    if not servers_data:
        return {}

    return servers_data.get('servers', {})

def check_servers_file_availability() -> bool:
    """
    Check if servers file is available without prompting for rebuild.

    Returns:
        bool: True if servers file exists, False otherwise
    """
    return get_servers_file_path().exists()
