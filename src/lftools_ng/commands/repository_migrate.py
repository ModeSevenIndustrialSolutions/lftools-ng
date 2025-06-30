#!/usr/bin/env python3
"""
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2025 The Linux Foundation

Jenkins to 1Password Repository Credential Migration Tool

This script provides generic migration capabilities for migrating Jenkins repository-specific
credentials to 1Password for Linux Foundation projects. Repository credentials are typically
used for publishing artifacts to repositories like Nexus, but can be used for any repository
publishing workflow.
"""

import logging
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from lftools_ng.core.credential_manager import (
    MigrationResult,
    Credential, CredentialType, CredentialScope
)
from lftools_ng.core.jenkins_provider import JenkinsCredentialProvider
from lftools_ng.core.platform_providers import OnePasswordCredentialProvider


@dataclass
class RepositoryCredentialMapping:
    """Mapping for a repository credential."""
    jenkins_credential_id: str
    repository_name: str
    github_url: str
    username: str
    password: str
    project: Optional[str]


class ProjectAwareMigrationManager:
    """Generic migration manager for Linux Foundation projects."""

    def __init__(self):
        self.console = Console()
        self.logger = logging.getLogger(__name__)

        # Use unified data loading through ProjectManager
        from pathlib import Path
        config_dir = Path.home() / ".config" / "lftools-ng"
        from lftools_ng.core.projects import ProjectManager
        self.project_manager = ProjectManager(config_dir)
        self.projects_data = self._load_projects_data()

    def _load_projects_data(self) -> Dict[str, Any]:
        """Load projects data using unified data loading mechanism."""
        try:
            projects_list = self.project_manager.get_projects_data()
            return {"projects": projects_list}
        except Exception as e:
            self.logger.warning(f"Could not load projects data via ProjectManager: {e}")
            return {}

    def find_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """
        Find a project using fuzzy name matching.

        Args:
            project_name: Project name to search for (can be primary name or alias)

        Returns:
            Project data dictionary if found, None otherwise
        """
        if not project_name:
            return None

        projects = self.projects_data.get("projects", [])
        project_name_upper = project_name.upper()

        # First try exact matches (case insensitive)
        for proj in projects:
            # Check primary name
            if proj.get("name", "").upper() == project_name_upper:
                return proj

            # Check primary_name field
            if proj.get("primary_name", "").upper() == project_name_upper:
                return proj

            # Check aliases
            aliases = proj.get("aliases", [])
            for alias in aliases:
                if alias.upper() == project_name_upper:
                    return proj

            # Check previous_names
            previous_names = proj.get("previous_names", [])
            for prev_name in previous_names:
                if prev_name.upper() == project_name_upper:
                    return proj

        # If no exact match, try fuzzy matching
        for proj in projects:
            project_names = [proj.get("name", ""), proj.get("primary_name", "")]
            project_names.extend(proj.get("aliases", []))
            project_names.extend(proj.get("previous_names", []))

            for name in project_names:
                if name and (project_name_upper in name.upper() or name.upper() in project_name_upper):
                    self.logger.info(f"Fuzzy matched '{project_name}' to project '{proj.get('name')}'")
                    return proj

        return None

    def extract_repository_name_from_credential_id(self, credential_id: str, pattern: Optional[str] = None) -> Optional[str]:
        """
        Extract repository name from Jenkins credential ID using a configurable pattern.

        Args:
            credential_id: The Jenkins credential ID
            pattern: The regex pattern to use for extraction. If None, uses default pattern.

        Returns:
            Repository name if pattern matches, None otherwise
        """
        if pattern is None:
            # Default pattern matches: "repository-name repository deployment"
            pattern = r'^(.+?)\s+\w+\s+deployment$'

        if pattern is None:
            # Default pattern matches: "repository-name repository deployment"
            pattern = r'^(.+?)\s+\w+\s+deployment$'

        match = re.match(pattern, credential_id, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        # If the pattern doesn't match, check if the credential_id itself is a repository name
        # This handles cases where the credential ID is simply the repository name (like O-RAN-SC)
        if re.match(r'^[a-zA-Z0-9\-_]+$', credential_id):
            return credential_id

        return None

    def get_github_url_for_repository(self, repository_name: str, project: Optional[str] = None) -> str:
        """
        Generate GitHub URL for a repository.

        Args:
            repository_name: The repository name (e.g., "aal-virt")
            project: The project name (required for URL generation)

        Returns:
            GitHub URL for the repository
        """
        # Look up project data
        if project:
            projects = self.projects_data.get("projects", [])
            project_data = None

            for proj in projects:
                if proj.get("name") == project or (project and project.upper() in proj.get("aliases", [])):
                    project_data = proj
                    break

            if project_data and 'github_mirror_org' in project_data:
                github_org = project_data['github_mirror_org']
                return f"https://github.com/{github_org}/{repository_name}"

            # Fallback to lowercase project name
            return f"https://github.com/{project.lower()}/{repository_name}"
        else:
            # If no project specified, return a generic placeholder
            return f"https://github.com/UNKNOWN-PROJECT/{repository_name}"

    def filter_repository_credentials(self, credentials: List[Credential], filter_pattern: str = "deployment") -> List[Credential]:
        """
        Filter credentials to only include repository credentials matching the pattern.

        Args:
            credentials: List of all Jenkins credentials
            filter_pattern: String pattern to match in credential names (e.g., "deployment", "nexus deployment")

        Returns:
            List of credentials that match the filter pattern
        """
        matching_credentials = []

        for credential in credentials:
            # Check if credential name or description contains the filter pattern (case insensitive)
            name_match = filter_pattern.lower() in credential.name.lower()
            description_match = filter_pattern.lower() in (credential.description or "").lower()

            if name_match or description_match:
                # Ensure it's a username/password credential (required for repository publishing)
                if credential.type == CredentialType.USERNAME_PASSWORD:
                    matching_credentials.append(credential)
                else:
                    self.logger.warning(
                        f"Skipping {credential.name}: Not a username/password credential"
                    )

        return matching_credentials

    def create_repository_credential_mappings(self,
                                       repository_credentials: List[Credential],
                                       project: Optional[str] = None,
                                       pattern: Optional[str] = None) -> List[RepositoryCredentialMapping]:
        """
        Create mapping objects for repository credentials.

        Args:
            repository_credentials: List of filtered repository credentials
            project: Project name for URL generation
            pattern: Regex pattern for extracting repository names from credential IDs

        Returns:
            List of RepositoryCredentialMapping objects
        """
        mappings = []

        for credential in repository_credentials:
            repository_name = self.extract_repository_name_from_credential_id(credential.name, pattern)

            if not repository_name:
                self.logger.warning(
                    f"Could not extract repository name from credential: {credential.name}"
                )
                continue

            github_url = self.get_github_url_for_repository(repository_name, project)

            mapping = RepositoryCredentialMapping(
                jenkins_credential_id=credential.id,
                repository_name=repository_name,
                github_url=github_url,
                username=credential.username or repository_name,  # fallback to repo name
                password=credential.password or "",
                project=project
            )

            mappings.append(mapping)

        return mappings

    def create_onepassword_credential(self, mapping: RepositoryCredentialMapping) -> Credential:
        """
        Create a 1Password credential from a repository credential mapping.

        Args:
            mapping: RepositoryCredentialMapping object

        Returns:
            Credential object formatted for 1Password
        """
        return Credential(
            id=mapping.repository_name,  # Use repository name as ID
            name=mapping.repository_name,  # Use repository name as title
            type=CredentialType.USERNAME_PASSWORD,
            scope=CredentialScope.GLOBAL,
            description="Migrated from Jenkins",
            username=mapping.username,
            password=mapping.password,
            source_platform="jenkins",
            target_platform="1password",
            metadata={
                "github_url": mapping.github_url,
                "project": mapping.project,
                "migration_source": mapping.jenkins_credential_id,
                "migration_type": "repository_deployment",
                "migration_origin": "Migrated from Jenkins"  # This will create the origin/source field as STRING type
            }
        )

    def display_migration_plan(self, mappings: List[RepositoryCredentialMapping]) -> None:
        """Display the migration plan in a table format."""
        table = Table(title="Repository Credentials Migration Plan")
        table.add_column("Repository", style="cyan")
        table.add_column("Jenkins Credential ID", style="yellow")
        table.add_column("Username", style="green")
        table.add_column("GitHub URL", style="blue")

        for mapping in mappings:
            table.add_row(
                mapping.repository_name,
                mapping.jenkins_credential_id,
                mapping.username,
                mapping.github_url
            )

        self.console.print(table)

    def migrate_single_credential(self,
                                mapping: RepositoryCredentialMapping,
                                onepassword_provider: OnePasswordCredentialProvider,
                                dry_run: bool = False) -> MigrationResult:
        """
        Migrate a single repository credential to 1Password.

        Args:
            mapping: RepositoryCredentialMapping object
            onepassword_provider: 1Password provider instance
            dry_run: Whether to perform a dry run

        Returns:
            MigrationResult object
        """
        credential = self.create_onepassword_credential(mapping)

        if dry_run:
            return MigrationResult(
                success=True,
                credential=credential,
                source_platform="jenkins",
                target_platform="1password",
                action="would_create",
                message="Dry run - no changes made"
            )

        # Check if credential already exists
        exists = onepassword_provider.credential_exists(mapping.repository_name)

        if exists:
            self.console.print(f"[yellow]Credential {mapping.repository_name} already exists in 1Password[/yellow]")
            return MigrationResult(
                success=True,
                credential=credential,
                source_platform="jenkins",
                target_platform="1password",
                action="skipped",
                message="Credential already exists"
            )

        # Create the credential
        success = onepassword_provider.create_credential(credential)

        return MigrationResult(
            success=success,
            credential=credential,
            source_platform="jenkins",
            target_platform="1password",
            action="created" if success else "failed",
            message="Migration completed successfully" if success else "Migration failed"
        )

    def validate_onepassword_setup(self, vault_name: str, account: Optional[str] = None) -> bool:
        """
        Validate that 1Password CLI is set up and the vault exists.

        Args:
            vault_name: Name of the 1Password vault
            account: Optional account name

        Returns:
            True if setup is valid, False otherwise
        """
        # Test 1Password provider
        provider = OnePasswordCredentialProvider(vault=vault_name, account=account)

        if not provider.supports_write():
            self.console.print("[red]❌ 1Password CLI is not authenticated or not available[/red]")
            self.console.print("\nTo fix this, run:")
            self.console.print("  op signin")
            return False

        # Try to list items in the vault to verify access
        try:
            items = provider.list_credentials()
            self.console.print(f"[green]✅ 1Password CLI authenticated and vault '{vault_name}' accessible[/green]")
            self.console.print(f"    Found {len(items)} existing items in vault")
            return True
        except Exception as e:
            self.console.print(f"[red]❌ Error accessing vault '{vault_name}': {e}[/red]")
            return False


def main():
    """Main migration command."""
    app = typer.Typer(name="repository-migrate", help="Generic Repository Credential Migration Tool for Linux Foundation Projects")

    @app.command("repository")
    def migrate_repository_credentials(
        # Jenkins connection options
        jenkins_server: str = typer.Option(
            ...,
            "--jenkins-server", "-s",
            help="Jenkins server URL",
            envvar="JENKINS_SERVER"
        ),
        jenkins_user: str = typer.Option(
            ...,
            "--jenkins-user", "-u",
            help="Jenkins username",
            envvar="JENKINS_USER"
        ),
        jenkins_password: str = typer.Option(
            ...,
            "--jenkins-password", "-p",
            help="Jenkins password or API token",
            envvar="JENKINS_PASSWORD"
        ),

        # 1Password options
        onepassword_vault: str = typer.Option(
            "CI/CD Credentials",
            "--vault", "-v",
            help="1Password vault name"
        ),
        onepassword_account: Optional[str] = typer.Option(
            None,
            "--account", "-a",
            help="1Password account (if multiple accounts)"
        ),

        # Migration options
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Show what would be migrated without making changes"
        ),
        single_credential: Optional[str] = typer.Option(
            None,
            "--single", "-1",
            help="Migrate only a single credential by repository name (e.g., 'aal-virt')"
        ),
        project: Optional[str] = typer.Option(
            None,
            "--project",
            help="Project name for repository URL generation (required for proper GitHub URLs)"
        ),
        filter_pattern: str = typer.Option(
            "deployment",
            "--filter-pattern", "-f",
            help="Pattern to match in credential names (e.g., 'deployment', 'nexus deployment')"
        ),
        extraction_pattern: Optional[str] = typer.Option(
            None,
            "--extraction-pattern", "-e",
            help="Regex pattern for extracting repository names from credential IDs"
        ),
        skip_validation: bool = typer.Option(
            False,
            "--skip-validation",
            help="Skip 1Password setup validation"
        )
    ):
        """
        Migrate repository deployment credentials from Jenkins to 1Password.

        This command:
        1. Fetches all credentials from Jenkins
        2. Filters for repository credentials matching the specified pattern
        3. Maps repository names to GitHub URLs
        4. Creates properly formatted credentials in 1Password

        Examples:

        # Dry run to see what would be migrated (O-RAN-SC Nexus credentials)
        repository-migrate repository --jenkins-server https://jenkins.o-ran-sc.org --jenkins-user admin --jenkins-password token --project "O-RAN-SC" --filter-pattern "nexus deployment" --dry-run

        # Migrate all repository credentials with default pattern
        repository-migrate repository --jenkins-server https://jenkins.example.org --jenkins-user admin --jenkins-password token --project "MyProject"

        # Migrate ONAP credentials with custom pattern
        repository-migrate repository --jenkins-server https://jenkins.onap.org --jenkins-user admin --jenkins-password token --project "ONAP" --filter-pattern "artifact deployment"

        # Migrate a single credential
        repository-migrate repository --jenkins-server https://jenkins.o-ran-sc.org --jenkins-user admin --jenkins-password token --project "O-RAN-SC" --single aal-virt
        """
        console = Console()

        console.print("[bold blue]Repository Credentials Migration Tool[/bold blue]\n")

        # Initialize migration manager
        migration_manager = ProjectAwareMigrationManager()

        # Validate 1Password setup unless skipped
        if not skip_validation:
            console.print("[cyan]Validating 1Password setup...[/cyan]")
            if not migration_manager.validate_onepassword_setup(onepassword_vault, onepassword_account):
                raise typer.Exit(1)
            console.print()

        # Initialize Jenkins provider
        console.print("[cyan]Connecting to Jenkins...[/cyan]")
        jenkins_provider = JenkinsCredentialProvider(
            server=jenkins_server,
            username=jenkins_user,
            password=jenkins_password,
            enable_classification=True
        )

        # Get all Jenkins credentials
        try:
            all_credentials = jenkins_provider.list_credentials()
            console.print(f"[green]✅ Connected to Jenkins. Found {len(all_credentials)} total credentials[/green]\n")
        except Exception as e:
            console.print(f"[red]❌ Failed to connect to Jenkins: {e}[/red]")
            raise typer.Exit(1)

        # Filter for repository credentials using the specified pattern
        repository_credentials = migration_manager.filter_repository_credentials(all_credentials, filter_pattern)
        console.print(f"[green]Found {len(repository_credentials)} repository credentials matching '{filter_pattern}'[/green]\n")

        if not repository_credentials:
            console.print(f"[yellow]No repository credentials found matching pattern '{filter_pattern}'. Exiting.[/yellow]")
            raise typer.Exit(0)

        # Create credential mappings
        mappings = migration_manager.create_repository_credential_mappings(
            repository_credentials,
            project,
            extraction_pattern
        )

        # Filter for single credential if specified
        if single_credential:
            mappings = [m for m in mappings if m.repository_name == single_credential]
            if not mappings:
                console.print(f"[red]No credential found for repository '{single_credential}'[/red]")
                raise typer.Exit(1)
            console.print(f"[yellow]Migrating single credential: {single_credential}[/yellow]\n")

        # Display migration plan
        migration_manager.display_migration_plan(mappings)
        console.print()

        # Confirm migration unless dry run
        if not dry_run:
            if not Confirm.ask(f"Proceed with migrating {len(mappings)} credentials to 1Password?"):
                console.print("[yellow]Migration cancelled[/yellow]")
                raise typer.Exit(0)
            console.print()

        # Initialize 1Password provider
        onepassword_provider = OnePasswordCredentialProvider(
            vault=onepassword_vault,
            account=onepassword_account
        )

        # Perform migrations
        console.print("[cyan]Starting migration...[/cyan]")
        results = []

        for i, mapping in enumerate(mappings, 1):
            console.print(f"[cyan]Migrating {i}/{len(mappings)}: {mapping.repository_name}[/cyan]")

            result = migration_manager.migrate_single_credential(
                mapping,
                onepassword_provider,
                dry_run=dry_run
            )
            results.append(result)

            # Display result
            if result.success:
                if result.action == "would_create":
                    console.print(f"  [green]✅ Would create credential for {mapping.repository_name}[/green]")
                elif result.action == "created":
                    console.print(f"  [green]✅ Created credential for {mapping.repository_name}[/green]")
                elif result.action == "skipped":
                    console.print(f"  [yellow]⏭️  Skipped {mapping.repository_name} (already exists)[/yellow]")
            else:
                console.print(f"  [red]❌ Failed to migrate {mapping.repository_name}: {result.error or result.message}[/red]")

        # Summary
        console.print("\n[bold]Migration Summary:[/bold]")

        successful = len([r for r in results if r.success])
        failed = len([r for r in results if not r.success])
        skipped = len([r for r in results if r.action == "skipped"])

        if dry_run:
            console.print(f"[green]✅ {successful} credentials would be migrated[/green]")
        else:
            console.print(f"[green]✅ {successful} credentials migrated successfully[/green]")
            if skipped > 0:
                console.print(f"[yellow]⏭️  {skipped} credentials skipped (already exist)[/yellow]")
            if failed > 0:
                console.print(f"[red]❌ {failed} credentials failed to migrate[/red]")

        # Exit with appropriate code
        if failed > 0 and not dry_run:
            raise typer.Exit(1)
        else:
            raise typer.Exit(0)

    if __name__ == "__main__":
        app()


if __name__ == "__main__":
    main()
