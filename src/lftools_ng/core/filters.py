# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Universal filtering system for lftools-ng CLI commands."""

import re
from typing import Any, Dict, List, Optional
from fnmatch import fnmatch


class FilterExpression:
    """Represents a single filter expression."""

    def __init__(self, field: str, operator: str, value: str):
        self.field = field
        self.operator = operator
        self.value = value

    def matches(self, data: Dict[str, Any]) -> bool:
        """Check if data matches this filter expression."""
        field_value = self._get_nested_field(data, self.field)

        # Handle empty/not-empty operators first since they have special None handling
        if self.operator == "empty":
            if field_value is None:
                return True
            if isinstance(field_value, str) and field_value == "":
                return True
            if isinstance(field_value, (list, dict)) and len(field_value) == 0:
                return True
            return False
        elif self.operator == "not-empty":
            if field_value is None:
                return False
            if isinstance(field_value, str) and field_value == "":
                return False
            if isinstance(field_value, (list, dict)) and len(field_value) == 0:
                return False
            return True

        # Handle None values for other operators
        if field_value is None:
            return self.operator == "!=" or self.operator == "not-contains"

        # Convert to string for comparison
        field_str = str(field_value).lower()
        value_str = self.value.lower()

        if self.operator == "==" or self.operator == "eq":
            return field_str == value_str
        elif self.operator == "!=" or self.operator == "ne":
            return field_str != value_str
        elif self.operator == "contains":
            return value_str in field_str
        elif self.operator == "not-contains":
            return value_str not in field_str
        elif self.operator == "starts-with":
            return field_str.startswith(value_str)
        elif self.operator == "ends-with":
            return field_str.endswith(value_str)
        elif self.operator == "regex":
            try:
                return bool(re.search(self.value, str(field_value), re.IGNORECASE))
            except re.error:
                return False
        elif self.operator == "glob":
            return fnmatch(field_str, value_str)
        elif self.operator == ">" or self.operator == "gt":
            try:
                return float(field_str) > float(value_str)
            except (ValueError, TypeError):
                return field_str > value_str
        elif self.operator == "<" or self.operator == "lt":
            try:
                return float(field_str) < float(value_str)
            except (ValueError, TypeError):
                return field_str < value_str
        elif self.operator == ">=" or self.operator == "gte":
            try:
                return float(field_str) >= float(value_str)
            except (ValueError, TypeError):
                return field_str >= value_str
        elif self.operator == "<=" or self.operator == "lte":
            try:
                return float(field_str) <= float(value_str)
            except (ValueError, TypeError):
                return field_str <= value_str

        return False

    def _get_nested_field(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        parts = field_path.split('.')
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index] if 0 <= index < len(current) else None
                except (ValueError, IndexError):
                    return None
            else:
                return None

        return current


class DataFilter:
    """Universal data filtering system for CLI commands."""

    def __init__(self):
        self.include_filters: List[FilterExpression] = []
        self.exclude_filters: List[FilterExpression] = []
        self.field_filters: List[str] = []  # Fields to include in output
        self.exclude_fields: List[str] = []  # Fields to exclude from output

    def add_include_filter(self, field: str, operator: str, value: str) -> None:
        """Add an include filter (data must match this to be included)."""
        self.include_filters.append(FilterExpression(field, operator, value))

    def add_exclude_filter(self, field: str, operator: str, value: str) -> None:
        """Add an exclude filter (data matching this will be excluded)."""
        self.exclude_filters.append(FilterExpression(field, operator, value))

    def set_field_filters(self, fields: Optional[List[str]] = None, exclude_fields: Optional[List[str]] = None) -> None:
        """Set which fields to include/exclude in output."""
        if fields:
            self.field_filters = fields
        if exclude_fields:
            self.exclude_fields = exclude_fields

    def filter_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply all filters to the data."""
        if not data:
            return data

        filtered_data = []

        for item in data:
            # Check include filters (all must match)
            if self.include_filters:
                if not all(f.matches(item) for f in self.include_filters):
                    continue

            # Check exclude filters (none should match)
            if self.exclude_filters:
                if any(f.matches(item) for f in self.exclude_filters):
                    continue

            # Apply field filtering
            filtered_item = self._filter_fields(item)
            filtered_data.append(filtered_item)

        return filtered_data

    def _filter_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Filter fields in a single item."""
        if not self.field_filters and not self.exclude_fields:
            return item

        result: Dict[str, Any] = {}

        if self.field_filters:
            # Include only specified fields
            for field in self.field_filters:
                if '.' in field:
                    # Handle nested fields
                    value = self._get_nested_field_for_output(item, field)
                    if value is not None:
                        self._set_nested_field(result, field, value)
                else:
                    if field in item:
                        result[field] = item[field]
        else:
            # Include all fields
            result = item.copy()

        # Remove excluded fields
        if self.exclude_fields:
            for field in self.exclude_fields:
                if '.' in field:
                    self._remove_nested_field(result, field)
                else:
                    result.pop(field, None)

        return result

    def _get_nested_field_for_output(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get value from nested dictionary for output purposes."""
        parts = field_path.split('.')
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
                if current is None:
                    return None
            else:
                return None

        return current

    def _set_nested_field(self, data: Dict[str, Any], field_path: str, value: Any) -> None:
        """Set value in nested dictionary."""
        parts = field_path.split('.')
        current = data

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    def _remove_nested_field(self, data: Dict[str, Any], field_path: str) -> None:
        """Remove field from nested dictionary."""
        parts = field_path.split('.')
        current = data

        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return
            current = current[part]

        if isinstance(current, dict):
            current.pop(parts[-1], None)


def _remove_quotes(value: str) -> str:
    """Remove surrounding quotes from a value."""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def parse_filter_expression(expression: str) -> tuple[str, str, str]:
    """Parse a filter expression string into field, operator, and value.

    Supported formats:
    - field=value (equals)
    - field!=value (not equals)
    - field~=value (contains)
    - field!~=value (not contains)
    - field^=value (starts with)
    - field$=value (ends with)
    - field>=value (greater than or equal)
    - field<=value (less than or equal)
    - field>value (greater than)
    - field<value (less than)
    - field@=value (regex match)
    - field*=value (glob pattern)
    - field:empty (is empty)
    - field:not-empty (is not empty)
    """
    # Try different operators in order of specificity
    operators = [
        ('!~=', 'not-contains'),
        ('~=', 'contains'),
        ('^=', 'starts-with'),
        ('$=', 'ends-with'),
        ('>=', 'gte'),
        ('<=', 'lte'),
        ('!=', 'ne'),
        ('@=', 'regex'),
        ('*=', 'glob'),
        ('=', 'eq'),
        ('>', 'gt'),
        ('<', 'lt'),
    ]

    # Check for special operators first
    if ':empty' in expression:
        field = expression.replace(':empty', '').strip()
        return field, 'empty', ''
    elif ':not-empty' in expression:
        field = expression.replace(':not-empty', '').strip()
        return field, 'not-empty', ''

    # Check regular operators
    for op_str, op_name in operators:
        if op_str in expression:
            parts = expression.split(op_str, 1)
            if len(parts) == 2:
                field = parts[0].strip()
                value = _remove_quotes(parts[1].strip())
                return field, op_name, value

    # Default to equals if no operator found
    if '=' in expression:
        parts = expression.split('=', 1)
        field = parts[0].strip()
        value = _remove_quotes(parts[1].strip()) if len(parts) > 1 else ''
        return field, 'eq', value

    raise ValueError(f"Invalid filter expression: {expression}")


def create_filter_from_args(
    include_filters: Optional[List[str]] = None,
    exclude_filters: Optional[List[str]] = None,
    fields: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None
) -> DataFilter:
    """Create a DataFilter from command line arguments."""
    data_filter = DataFilter()

    # Parse include filters
    if include_filters:
        for expr in include_filters:
            try:
                field, operator, value = parse_filter_expression(expr)
                data_filter.add_include_filter(field, operator, value)
            except ValueError as e:
                raise ValueError(f"Invalid include filter '{expr}': {e}")

    # Parse exclude filters
    if exclude_filters:
        for expr in exclude_filters:
            try:
                field, operator, value = parse_filter_expression(expr)
                data_filter.add_exclude_filter(field, operator, value)
            except ValueError as e:
                raise ValueError(f"Invalid exclude filter '{expr}': {e}")

    # Set field filters
    data_filter.set_field_filters(fields, exclude_fields)

    return data_filter
