# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Developer guidelines for implementing universal filtering.

This module provides templates and guidelines for developers adding new
CLI commands to ensure they properly support the universal filtering system.

The universal filtering system is a CORE FEATURE of lftools-ng and MUST be
implemented in every command that returns tabular data.
"""

from typing import Any, Dict, List, Optional
import typer
from rich.console import Console
from lftools_ng.core.output import format_and_output, create_filter_from_options

console = Console()


def filtering_command_template(
    # Your command-specific parameters here
    config_dir: Optional[str] = typer.Option(None, "--config-dir", "-c", help="Configuration directory"),
    output_format: str = typer.Option("table", "--format", "-f", help="Output format (table, json, json-pretty, yaml)"),

    # REQUIRED: Universal filtering parameters - MUST be included in every data command
    include: Optional[List[str]] = typer.Option(
        None, "--include", "-i",
        help="Include filters (e.g., 'field=value', 'field~=substring', 'field>5')"
    ),
    exclude: Optional[List[str]] = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters (same syntax as include filters)"
    ),
    fields: Optional[str] = typer.Option(
        None, "--fields",
        help="Fields to include in output (comma-separated)"
    ),
    exclude_fields: Optional[str] = typer.Option(
        None, "--exclude-fields",
        help="Fields to exclude from output (comma-separated)"
    ),
) -> None:
    """Template function showing how to implement filtering in CLI commands.

    CRITICAL IMPLEMENTATION REQUIREMENTS:

    1. MUST include all four filtering parameters:
       - include: List[str] for include filters
       - exclude: List[str] for exclude filters
       - fields: str for field selection
       - exclude_fields: str for field exclusion

    2. MUST use create_filter_from_options() to create filter

    3. MUST use format_and_output() for output formatting

    4. MUST include filtering examples in docstring

    5. MUST add integration tests in tests/integration/test_universal_filtering.py

    Filter examples:
    - Include specific values: --include 'status=active'
    - Exclude test data: --exclude 'name~=test'
    - Show only certain fields: --fields 'name,status,url'
    - Complex filtering: --include 'count>5' --exclude 'type=deprecated'
    """
    try:
        # 1. Get your data using existing logic
        data = get_your_data()  # Replace with actual data retrieval

        # 2. Enhance data with computed fields if needed
        enhanced_data = []
        for item in data:
            enhanced_item = item.copy()
            # Add any computed fields here
            enhanced_item["computed_field"] = compute_something(item)
            enhanced_data.append(enhanced_item)

        # 3. REQUIRED: Create filter from options
        data_filter = create_filter_from_options(include, exclude, fields, exclude_fields)

        # 4. REQUIRED: Configure table output (optional but recommended)
        table_config = {
            "title": "Your Data Title",
            "columns": [
                {"name": "Name", "field": "name", "style": "cyan"},
                {"name": "Status", "field": "status", "style": "green"},
                {"name": "URL", "field": "url", "style": "blue"}
            ]
        }

        # 5. REQUIRED: Use enhanced formatter with filtering
        format_and_output(enhanced_data, output_format, data_filter, table_config)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def get_your_data() -> List[Dict[str, Any]]:
    """Placeholder for your data retrieval logic."""
    return [
        {"name": "example1", "status": "active", "url": "https://example1.com"},
        {"name": "example2", "status": "inactive", "url": "https://example2.com"}
    ]


def compute_something(item: Dict[str, Any]) -> str:
    """Placeholder for computed field logic."""
    return f"computed_{item.get('name', 'unknown')}"


# REQUIRED IMPLEMENTATION CHECKLIST:
#
# When implementing a new CLI command that returns data, you MUST:
#
# □ 1. Include all four filtering parameters in your command function
# □ 2. Use create_filter_from_options() to create the filter
# □ 3. Use format_and_output() for consistent output formatting
# □ 4. Include filtering examples in your command docstring
# □ 5. Support all output formats: table, json, json-pretty, yaml
# □ 6. Add integration tests in tests/integration/test_universal_filtering.py
# □ 7. Add your command to TestFilteringSystemRequirements.test_all_data_commands_have_filtering_options
# □ 8. Update README.md with examples of your command's filtering capabilities
# □ 9. Test your command with various filter combinations
# □ 10. Ensure error handling for invalid filter expressions
#
# FAILURE TO IMPLEMENT FILTERING SUPPORT WILL RESULT IN:
# - Failed integration tests
# - Inconsistent user experience
# - Rejection of pull requests
#
# The filtering system is a PRIMARY FEATURE of lftools-ng and must be
# consistently implemented across all data-returning commands.


# Filter Operator Reference for Documentation:
FILTER_OPERATORS = {
    "=": "Equals (exact match)",
    "!=": "Not equals",
    "~=": "Contains substring",
    "!~=": "Does not contain substring",
    "^=": "Starts with",
    "$=": "Ends with",
    "@=": "Regular expression match",
    "*=": "Glob pattern match",
    ">": "Greater than",
    "<": "Less than",
    ">=": "Greater than or equal",
    "<=": "Less than or equal",
    ":empty": "Field is empty/null",
    ":not-empty": "Field is not empty"
}


# Common Filter Examples for Documentation:
FILTER_EXAMPLES = [
    "name=production",
    "status!=inactive",
    "name~=test",
    "url!~=staging",
    "name^=prod",
    "name$=_backup",
    "version@=v[0-9]+",
    "name*=test-*",
    "count>10",
    "score>=85",
    "description:empty",
    "url:not-empty"
]
