# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for the filtering system."""

import pytest

from lftools_ng.core.filters import DataFilter, create_filter_from_args, parse_filter_expression


class TestFilterExpression:
    """Test filter expressions."""

    def test_parse_simple_equals(self):
        """Test parsing simple equals expression."""
        field, operator, value = parse_filter_expression("name=test")
        assert field == "name"
        assert operator == "eq"
        assert value == "test"

    def test_parse_contains(self):
        """Test parsing contains expression."""
        field, operator, value = parse_filter_expression("name~=test")
        assert field == "name"
        assert operator == "contains"
        assert value == "test"

    def test_parse_not_equals(self):
        """Test parsing not equals expression."""
        field, operator, value = parse_filter_expression("type!=jenkins")
        assert field == "type"
        assert operator == "ne"
        assert value == "jenkins"

    def test_parse_empty(self):
        """Test parsing empty expression."""
        field, operator, value = parse_filter_expression("github_org:empty")
        assert field == "github_org"
        assert operator == "empty"
        assert value == ""

    def test_parse_with_quotes(self):
        """Test parsing expression with quotes."""
        field, operator, value = parse_filter_expression('name="test value"')
        assert field == "name"
        assert operator == "eq"
        assert value == "test value"


class TestDataFilter:
    """Test data filtering functionality."""

    def test_basic_include_filter(self):
        """Test basic include filtering."""
        data = [
            {"name": "test1", "type": "jenkins"},
            {"name": "test2", "type": "gerrit"},
            {"name": "prod1", "type": "jenkins"},
        ]

        filter_obj = DataFilter()
        filter_obj.add_include_filter("type", "eq", "jenkins")

        result = filter_obj.filter_data(data)
        assert len(result) == 2
        assert all(item["type"] == "jenkins" for item in result)

    def test_basic_exclude_filter(self):
        """Test basic exclude filtering."""
        data = [
            {"name": "test1", "type": "jenkins"},
            {"name": "test2", "type": "gerrit"},
            {"name": "prod1", "type": "jenkins"},
        ]

        filter_obj = DataFilter()
        filter_obj.add_exclude_filter("name", "contains", "test")

        result = filter_obj.filter_data(data)
        assert len(result) == 1
        assert result[0]["name"] == "prod1"

    def test_field_filtering(self):
        """Test field filtering."""
        data = [
            {"name": "test1", "type": "jenkins", "url": "http://test1.com"},
            {"name": "test2", "type": "gerrit", "url": "http://test2.com"},
        ]

        filter_obj = DataFilter()
        filter_obj.set_field_filters(["name", "type"])

        result = filter_obj.filter_data(data)
        assert len(result) == 2
        for item in result:
            assert "name" in item
            assert "type" in item
            assert "url" not in item

    def test_contains_filter(self):
        """Test contains filtering."""
        data = [
            {"name": "linux-kernel", "type": "git"},
            {"name": "windows-driver", "type": "git"},
            {"name": "linux-tools", "type": "jenkins"},
        ]

        filter_obj = DataFilter()
        filter_obj.add_include_filter("name", "contains", "linux")

        result = filter_obj.filter_data(data)
        assert len(result) == 2
        assert all("linux" in item["name"] for item in result)

    def test_nested_field_access(self):
        """Test nested field access."""
        data = [
            {"name": "test1", "config": {"enabled": True, "count": 5}},
            {"name": "test2", "config": {"enabled": False, "count": 3}},
            {"name": "test3", "config": {"enabled": True, "count": 10}},
        ]

        filter_obj = DataFilter()
        filter_obj.add_include_filter("config.enabled", "eq", "true")

        result = filter_obj.filter_data(data)
        assert len(result) == 2
        assert all(item["config"]["enabled"] for item in result)

    def test_empty_filter(self):
        """Test empty field filtering."""
        data = [
            {"name": "test1", "description": ""},
            {"name": "test2", "description": "Valid description"},
            {"name": "test3", "description": None},
        ]

        filter_obj = DataFilter()
        filter_obj.add_exclude_filter("description", "empty", "")

        result = filter_obj.filter_data(data)
        assert len(result) == 1
        assert result[0]["name"] == "test2"


class TestCreateFilterFromArgs:
    """Test creating filters from command line arguments."""

    def test_create_include_filter(self):
        """Test creating filter with include expressions."""
        filter_obj = create_filter_from_args(include_filters=["name=test", "type~=jenkins"])

        assert len(filter_obj.include_filters) == 2
        assert filter_obj.include_filters[0].field == "name"
        assert filter_obj.include_filters[0].operator == "eq"
        assert filter_obj.include_filters[1].field == "type"
        assert filter_obj.include_filters[1].operator == "contains"

    def test_create_field_filter(self):
        """Test creating filter with field specifications."""
        filter_obj = create_filter_from_args(
            fields=["name", "type"], exclude_fields=["internal_id"]
        )

        assert filter_obj.field_filters == ["name", "type"]
        assert filter_obj.exclude_fields == ["internal_id"]

    def test_invalid_expression(self):
        """Test handling of invalid filter expressions."""
        with pytest.raises(ValueError, match="Invalid filter expression"):
            parse_filter_expression("invalid_expression_format")


if __name__ == "__main__":
    pytest.main([__file__])
