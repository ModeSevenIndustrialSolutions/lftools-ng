# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Enhanced output formatting with filtering support for lftools-ng CLI commands."""

import json
import sys
from typing import Any, Dict, List, Optional

import typer
import yaml
from rich.console import Console
from rich.table import Table

from lftools_ng.core.filters import DataFilter


console = Console()


def format_and_output(
    data: List[Dict[str, Any]],
    output_format: str = "table",
    data_filter: Optional[DataFilter] = None,
    table_config: Optional[Dict[str, Any]] = None
) -> None:
    """Format and output data with optional filtering.

    Args:
        data: Data to output
        output_format: Format to use (table, json, json-pretty, yaml)
        data_filter: Optional filter to apply to data
        table_config: Configuration for table output (columns, title, etc.)
    """
    # Apply filtering if provided
    if data_filter:
        # Check if field filtering is being applied
        has_field_filter = hasattr(data_filter, 'field_filters') and data_filter.field_filters

        data = data_filter.filter_data(data)

        # If field filtering was applied and we have table config, adjust the columns
        if has_field_filter and table_config and output_format == "table":
            table_config = _adjust_table_config_for_field_filter(table_config, data_filter.field_filters)

    if output_format == "json":
        print(json.dumps(data, separators=(',', ':')), file=sys.stdout)
    elif output_format == "json-pretty":
        print(json.dumps(data, indent=2), file=sys.stdout)
    elif output_format == "yaml":
        console.print(yaml.dump(data, default_flow_style=False))
    elif output_format == "table":
        _output_table(data, table_config or {})
    else:
        raise ValueError(f"Unsupported output format: {output_format}")


def _adjust_table_config_for_field_filter(
    table_config: Dict[str, Any],
    field_filters: List[str]
) -> Dict[str, Any]:
    """Adjust table configuration to match field filters.

    Args:
        table_config: Original table configuration
        field_filters: List of fields to include

    Returns:
        Adjusted table configuration
    """
    if not field_filters or "columns" not in table_config:
        return table_config

    # Create a mapping from field names to column configs
    field_to_column = {}
    for col in table_config.get("columns", []):
        if isinstance(col, dict):
            field_name = col.get("field", col.get("name", ""))
            if field_name:
                field_to_column[field_name] = col

    # Build new columns list based on field filters
    new_columns = []
    for field in field_filters:
        if field in field_to_column:
            new_columns.append(field_to_column[field])
        else:
            # Create a basic column config for fields not in original config
            new_columns.append({
                "name": field.replace('_', ' ').title(),
                "field": field
            })

    # Return adjusted config
    adjusted_config = table_config.copy()
    adjusted_config["columns"] = new_columns
    return adjusted_config


def _output_table(data: List[Dict[str, Any]], config: Dict[str, Any]) -> None:
    """Output data as a rich table."""
    table = Table(title=config.get("title", ""))

    # Get columns configuration
    columns = config.get("columns", [])

    # If no data and no predefined columns, show "No data to display"
    if not data and not columns:
        console.print("[yellow]No data to display[/yellow]")
        return

    # If no predefined columns, auto-detect from data
    if not columns:
        columns = _auto_detect_columns(data) if data else []

    # If still no columns and no data, show "No data to display"
    if not columns and not data:
        console.print("[yellow]No data to display[/yellow]")
        return

    # Add columns to table
    for col in columns:
        if isinstance(col, dict):
            table.add_column(
                col.get("name", ""),
                style=col.get("style", ""),
                no_wrap=col.get("no_wrap", False),
                justify=col.get("justify", "left")
            )
        else:
            table.add_column(str(col).replace('_', ' ').title())

    # Add rows
    for item in data:
        row_values = []
        for col in columns:
            if isinstance(col, dict):
                field_name = col.get("field", col.get("name", ""))
                if field_name is None:
                    field_name = ""
                value = _get_field_value(item, field_name)
                formatted_value = _format_field_value(value, col.get("format"))
            else:
                field_name = str(col)
                value = _get_field_value(item, field_name)
                formatted_value = _format_field_value(value)

            row_values.append(formatted_value)

        table.add_row(*row_values)

    console.print(table)


def _extract_field_names_from_columns(columns: List[Any]) -> List[str]:
    """Extract field names from column configurations."""
    field_names = []
    for col in columns:
        if isinstance(col, dict):
            field_names.append(col.get("field", col.get("name", "")))
        else:
            field_names.append(str(col))
    return field_names


def _auto_detect_columns(data: List[Dict[str, Any]]) -> List[str]:
    """Automatically detect columns from data."""
    if not data:
        return []

    # Get all unique keys from all items
    all_keys: set[str] = set()
    for item in data:
        all_keys.update(item.keys())

    return sorted(all_keys)


def _get_field_value(item: Dict[str, Any], field_path: str) -> Any:
    """Get field value with support for nested fields using dot notation."""
    if '.' not in field_path:
        return item.get(field_path, "")

    parts = field_path.split('.')
    current = item

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
            if current is None:
                return ""
        else:
            return ""

    return current


def _format_field_value(value: Any, format_type: Optional[str] = None) -> str:
    """Format a field value for display."""
    if value is None:
        return ""

    if isinstance(value, list):
        if format_type == "join":
            return ", ".join(str(v) for v in value)
        elif format_type == "count":
            return str(len(value))
        else:
            return ", ".join(str(v) for v in value) if value else "None"

    if isinstance(value, dict):
        if format_type == "keys":
            return ", ".join(value.keys())
        elif format_type == "count":
            return str(len(value))
        else:
            return str(value)

    if isinstance(value, bool):
        return "Yes" if value else "No"

    return str(value)


def add_filter_options(func):
    """Decorator to add common filter options to CLI commands."""
    func = typer.Option(
        None, "--include", "-i",
        help="Include filters (field=value, field!=value, field~=value, etc.)"
    )(func)
    func = typer.Option(
        None, "--exclude", "-e",
        help="Exclude filters (same syntax as include filters)"
    )(func)
    func = typer.Option(
        None, "--fields",
        help="Fields to include in output (comma-separated)"
    )(func)
    func = typer.Option(
        None, "--exclude-fields",
        help="Fields to exclude from output (comma-separated)"
    )(func)
    return func


def create_filter_from_options(
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    fields: Optional[str] = None,
    exclude_fields: Optional[str] = None
) -> Optional[DataFilter]:
    """Create a DataFilter from CLI options."""
    from lftools_ng.core.filters import create_filter_from_args

    # Parse comma-separated field lists
    fields_list = fields.split(',') if fields else None
    exclude_fields_list = exclude_fields.split(',') if exclude_fields else None

    # Clean whitespace
    if fields_list:
        fields_list = [f.strip() for f in fields_list if f.strip()]
    if exclude_fields_list:
        exclude_fields_list = [f.strip() for f in exclude_fields_list if f.strip()]

    # Only create filter if we have options
    if any([include, exclude, fields_list, exclude_fields_list]):
        return create_filter_from_args(
            include_filters=include,
            exclude_filters=exclude,
            fields=fields_list,
            exclude_fields=exclude_fields_list
        )

    return None
