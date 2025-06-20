# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Jenkins commands for lftools-ng."""

from typing import Any

import typer
import yaml
from rich.console import Console

from lftools_ng.core.jenkins import JenkinsClient

jenkins_app = typer.Typer(
    name="jenkins",
    help="Jenkins server operations",
    no_args_is_help=True,
)
console = Console()

# Constants
OUTPUT_FORMAT_HELP = "Output format (table, json, json-pretty)"

def format_output(data: Any, output_format: str) -> None:
    """Format and print output in the specified format."""
    if output_format == "json":
        import json
        console.print(json.dumps(data, separators=(',', ':')))
    elif output_format == "json-pretty":
        import json
        console.print(json.dumps(data, indent=2))
    elif output_format == "yaml":
        console.print(yaml.dump(data, default_flow_style=False))


@jenkins_app.command("credentials")
def get_credentials(
    server: str = typer.Option(..., "--server", "-s", help="Jenkins server URL"),
    user: str = typer.Option(..., "--user", "-u", help="Jenkins username"),
    password: str = typer.Option(..., "--password", "-p", help="Jenkins password or token"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, yaml)"),
) -> None:
    """Extract credentials from Jenkins server."""
    try:
        client = JenkinsClient(server=server, username=user, password=password)
        credentials = client.get_credentials()

        if output_format == "json":
            import json
            console.print(json.dumps(credentials, indent=2))
        elif output_format == "yaml":
            import yaml
            console.print(yaml.dump(credentials, default_flow_style=False))
        else:
            # Default table format
            from rich.table import Table
            table = Table(title="Jenkins Credentials")
            table.add_column("ID", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Username", style="green")
            table.add_column("Description", style="yellow")

            for cred in credentials:
                table.add_row(
                    cred.get("id", ""),
                    cred.get("type", ""),
                    cred.get("username", ""),
                    cred.get("description", "")
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@jenkins_app.command("secrets")
def get_secrets(
    server: str = typer.Option(..., "--server", "-s", help="Jenkins server URL"),
    user: str = typer.Option(..., "--user", "-u", help="Jenkins username"),
    password: str = typer.Option(..., "--password", "-p", help="Jenkins password or token"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, yaml)"),
) -> None:
    """Extract secrets from Jenkins server."""
    try:
        client = JenkinsClient(server=server, username=user, password=password)
        secrets = client.get_secrets()

        if output_format == "json":
            import json
            console.print(json.dumps(secrets, indent=2))
        elif output_format == "yaml":
            import yaml
            console.print(yaml.dump(secrets, default_flow_style=False))
        else:
            # Default table format
            from rich.table import Table
            table = Table(title="Jenkins Secrets")
            table.add_column("ID", style="cyan")
            table.add_column("Type", style="magenta")
            table.add_column("Description", style="yellow")

            for secret in secrets:
                table.add_row(
                    secret.get("id", ""),
                    secret.get("type", ""),
                    secret.get("description", "")
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@jenkins_app.command("private-keys")
def get_private_keys(
    server: str = typer.Option(..., "--server", "-s", help="Jenkins server URL"),
    user: str = typer.Option(..., "--user", "-u", help="Jenkins username"),
    password: str = typer.Option(..., "--password", "-p", help="Jenkins password or token"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, yaml)"),
) -> None:
    """Extract SSH private keys from Jenkins server."""
    try:
        client = JenkinsClient(server=server, username=user, password=password)
        keys = client.get_ssh_private_keys()

        if output_format == "json":
            import json
            console.print(json.dumps(keys, indent=2))
        elif output_format == "yaml":
            import yaml
            console.print(yaml.dump(keys, default_flow_style=False))
        else:
            # Default table format
            from rich.table import Table
            table = Table(title="Jenkins SSH Private Keys")
            table.add_column("ID", style="cyan")
            table.add_column("Username", style="green")
            table.add_column("Description", style="yellow")
            table.add_column("Has Passphrase", style="magenta")

            for key in keys:
                table.add_row(
                    key.get("id", ""),
                    key.get("username", ""),
                    key.get("description", ""),
                    "Yes" if key.get("passphrase") else "No"
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@jenkins_app.command("groovy")
def run_groovy_script(
    script_file: str = typer.Argument(..., help="Path to Groovy script file"),
    server: str = typer.Option(..., "--server", "-s", help="Jenkins server URL"),
    user: str = typer.Option(..., "--user", "-u", help="Jenkins username"),
    password: str = typer.Option(..., "--password", "-p", help="Jenkins password or token"),
) -> None:
    """Run a Groovy script on Jenkins server."""
    try:
        import pathlib

        script_path = pathlib.Path(script_file)
        if not script_path.exists():
            console.print(f"[red]Error: Script file {script_file} not found[/red]")
            raise typer.Exit(1)

        client = JenkinsClient(server=server, username=user, password=password)
        result = client.run_groovy_script(script_path.read_text())

        console.print("[green]Script executed successfully:[/green]")
        console.print(result)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
