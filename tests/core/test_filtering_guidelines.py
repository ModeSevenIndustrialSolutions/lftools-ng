# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for filtering guidelines module."""

from unittest.mock import MagicMock, patch

import pytest

from lftools_ng.core.filtering_guidelines import (
    FILTER_EXAMPLES,
    FILTER_OPERATORS,
    compute_something,
    filtering_command_template,
    get_your_data,
)


class TestFilteringGuidelines:
    """Test filtering guidelines functions."""

    def test_filtering_command_template_basic(self):
        """Test basic filtering command template execution."""
        # Mock the necessary dependencies
        with (
            patch("lftools_ng.core.filtering_guidelines.format_and_output"),
            patch("lftools_ng.core.filtering_guidelines.create_filter_from_options") as mock_filter,
        ):
            mock_filter.return_value = MagicMock()

            # Should not raise an exception
            filtering_command_template()

            # Verify the template function structure
            assert callable(filtering_command_template)

    def test_filtering_command_template_with_params(self):
        """Test filtering command template with various parameters."""
        with (
            patch("lftools_ng.core.filtering_guidelines.format_and_output"),
            patch("lftools_ng.core.filtering_guidelines.create_filter_from_options") as mock_filter,
        ):
            mock_filter.return_value = MagicMock()

            # Test with various parameter combinations
            filtering_command_template(
                config_dir="/test/config",
                output_format="json",
                include=["name=test"],
                exclude=["type=inactive"],
                fields="name,type,status",
                exclude_fields="internal_id",
            )

            # Verify filter creation was called
            mock_filter.assert_called()

    def test_get_your_data(self):
        """Test the example data retrieval function."""
        data = get_your_data()

        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure of returned data
        for item in data:
            assert isinstance(item, dict)
            assert "name" in item
            assert "status" in item
            assert "url" in item

    def test_compute_something(self):
        """Test the example computation function."""
        test_item = {"name": "test_project", "type": "jenkins"}

        result = compute_something(test_item)

        assert isinstance(result, str)
        assert "computed_" in result
        assert "test_project" in result

    def test_compute_something_missing_name(self):
        """Test computation function with missing name field."""
        test_item = {"type": "jenkins"}

        result = compute_something(test_item)

        assert isinstance(result, str)
        assert "computed_unknown" in result

    def test_filter_operators_constant(self):
        """Test that filter operators constant is properly defined."""
        assert isinstance(FILTER_OPERATORS, dict)
        assert len(FILTER_OPERATORS) > 0

        # Check for essential operators
        assert "=" in FILTER_OPERATORS
        assert "!=" in FILTER_OPERATORS
        assert "~=" in FILTER_OPERATORS
        assert ">" in FILTER_OPERATORS
        assert "<" in FILTER_OPERATORS
        assert ":empty" in FILTER_OPERATORS

    def test_filter_examples_constant(self):
        """Test that filter examples constant is properly defined."""
        assert isinstance(FILTER_EXAMPLES, list)
        assert len(FILTER_EXAMPLES) > 0

        # Check that examples contain various operators
        example_str = " ".join(FILTER_EXAMPLES)
        assert "=" in example_str
        assert "!=" in example_str
        assert "~=" in example_str
        assert ">" in example_str


class TestFilteringGuidelinesIntegration:
    """Integration tests for filtering guidelines."""

    def test_example_implementation_pattern(self):
        """Test that the example implementation pattern works correctly."""
        with (
            patch("lftools_ng.core.filtering_guidelines.format_and_output") as mock_output,
            patch("lftools_ng.core.filtering_guidelines.create_filter_from_options") as mock_filter,
        ):
            # Mock some sample data
            mock_filter.return_value = MagicMock()

            # Test the template with realistic parameters
            filtering_command_template(
                output_format="table",
                include=["status=active"],
                exclude=["type=deprecated"],
                fields="name,status",
            )

            # Verify the interaction pattern
            mock_filter.assert_called_once()
            mock_output.assert_called_once()

    def test_data_flow_integration(self):
        """Test integration of data retrieval and computation."""
        # Get sample data
        data = get_your_data()

        # Test data enhancement pattern
        enhanced_data = []
        for item in data:
            enhanced_item = item.copy()
            enhanced_item["computed_field"] = compute_something(item)
            enhanced_data.append(enhanced_item)

        # Verify enhancement worked
        assert len(enhanced_data) == len(data)
        for item in enhanced_data:
            assert "computed_field" in item
            assert item["computed_field"].startswith("computed_")

    def test_filtering_constants_completeness(self):
        """Test that filtering constants provide good coverage."""
        # Check operator coverage
        operators = set(FILTER_OPERATORS.keys())
        expected_operators = {"=", "!=", "~=", ">", ">=", ":empty"}
        assert expected_operators.issubset(operators)

        # Check examples cover different operator types
        examples_text = " ".join(FILTER_EXAMPLES)
        for op in ["=", "!=", "~=", ">", ":empty"]:
            assert op in examples_text, f"Operator {op} not covered in examples"

    def test_template_error_handling(self):
        """Test error handling in the template function."""
        import click

        with patch("lftools_ng.core.filtering_guidelines.get_your_data") as mock_get_data:
            mock_get_data.side_effect = Exception("Test error")

            # Should handle exceptions gracefully
            with pytest.raises(click.exceptions.Exit):  # typer.Exit is actually a click.Exit
                filtering_command_template()

    def test_template_with_all_options(self):
        """Test template function with all filtering options."""
        with (
            patch("lftools_ng.core.filtering_guidelines.format_and_output") as mock_output,
            patch("lftools_ng.core.filtering_guidelines.create_filter_from_options") as mock_filter,
        ):
            mock_filter.return_value = MagicMock()

            # Test with all parameter types
            filtering_command_template(
                config_dir="/custom/config",
                output_format="json-pretty",
                include=["name=test", "status=active"],
                exclude=["type=deprecated", "name~=temp"],
                fields="name,status,url,computed_field",
                exclude_fields="internal_id,debug_info",
            )

            # Verify proper calls were made
            mock_filter.assert_called_once()
            mock_output.assert_called_once()

            # Check the call arguments
            args, _ = mock_filter.call_args
            include, exclude, fields, exclude_fields = args
            assert include == ["name=test", "status=active"]
            assert exclude == ["type=deprecated", "name~=temp"]
            assert fields == "name,status,url,computed_field"
            assert exclude_fields == "internal_id,debug_info"
