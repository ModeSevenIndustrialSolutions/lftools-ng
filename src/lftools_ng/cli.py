# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Main CLI entry point for lftools-ng."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from lftools_ng import __version__
from lftools_ng.commands.jenkins import jenkins_app
from lftools_ng.commands.projects import projects_app
from lftools_ng.commands.rebuild import rebuild_app
from lftools_ng.commands.repository_migrate import app as repository_migrate_app

app = typer.Typer(
    name="lftools-ng",
    help="Next-generation Linux Foundation Release Engineering Tools",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()

# Add subcommand groups
app.add_typer(jenkins_app, name="jenkins", help="Jenkins server operations with unified credential management")
app.add_typer(projects_app, name="projects", help="Project management operations")
app.add_typer(rebuild_app, name="rebuild-data", help="Rebuild all backend data files")
app.add_typer(repository_migrate_app, name="migrate", help="Migration tools for credentials and configurations")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show version information"
    ),
    verbose: Optional[bool] = typer.Option(
        False, "--verbose", "-V", help="Enable verbose logging"
    ),
) -> None:
    """Next-generation Linux Foundation Release Engineering Tools."""
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    if version:
        table = Table(title="lftools-ng Information")
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")

        table.add_row("Version", __version__)
        table.add_row("Purpose", "Linux Foundation Release Engineering Tools")
        table.add_row("License", "Apache-2.0")
        table.add_row("Author", "LF Release Engineering")

        console.print(table)
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    app()
