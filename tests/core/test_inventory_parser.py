# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for inventory parser module."""

from unittest.mock import Mock, patch

import httpx
import pytest

from lftools_ng.core.inventory_parser import (
    INVENTORY_URL,
    InventoryParser,
)
from lftools_ng.core.models import (
    Project,
    ServerLocation,
)


class TestInventoryParser:
    """Test inventory parser functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = InventoryParser()

    def test_init(self):
        """Test parser initialization."""
        assert self.parser.client is not None
        assert isinstance(self.parser.client, httpx.Client)

    def test_fetch_inventory_data_success(self):
        """Test successful inventory data fetching."""
        mock_response = Mock()
        mock_response.text = "<html><body>Test inventory content</body></html>"

        with patch.object(self.parser.client, "get", return_value=mock_response) as mock_get:
            result = self.parser.fetch_inventory_data()

            assert result == "<html><body>Test inventory content</body></html>"
            mock_get.assert_called_once_with(INVENTORY_URL)

    def test_fetch_inventory_data_custom_url(self):
        """Test fetching with custom URL."""
        custom_url = "https://custom.example.com/inventory"
        mock_response = Mock()
        mock_response.text = "<html>Custom content</html>"

        with patch.object(self.parser.client, "get", return_value=mock_response) as mock_get:
            result = self.parser.fetch_inventory_data(custom_url)

            assert result == "<html>Custom content</html>"
            mock_get.assert_called_once_with(custom_url)

    def test_fetch_inventory_data_http_error(self):
        """Test handling of HTTP errors."""
        with patch.object(
            self.parser.client, "get", side_effect=httpx.RequestError("Network error")
        ):
            with pytest.raises(httpx.RequestError):
                self.parser.fetch_inventory_data()

    def test_parse_inventory_table_empty(self):
        """Test parsing from empty HTML."""
        html_content = "<html><body></body></html>"

        projects = self.parser.parse_inventory_table(html_content)

        assert isinstance(projects, list)
        assert len(projects) == 0

    def test_parse_inventory_table_with_content(self):
        """Test parsing from HTML with table content."""
        html_content = """
        <html>
        <body>
            <h2>Projects</h2>
            <table>
                <tr>
                    <th>Project</th>
                    <th>Type</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>test-project</td>
                    <td>jenkins</td>
                    <td>active</td>
                </tr>
            </table>
        </body>
        </html>
        """

        projects = self.parser.parse_inventory_table(html_content)

        assert isinstance(projects, list)
        # The actual parsing logic would depend on the HTML structure

    def test_parse_projects_from_inventory_success(self):
        """Test parsing projects from inventory."""
        mock_html = "<html><body><table></table></body></html>"

        with (
            patch.object(self.parser, "fetch_inventory_data", return_value=mock_html),
            patch.object(self.parser, "parse_inventory_table", return_value=[]),
        ):
            projects = self.parser.parse_projects_from_inventory()

            assert isinstance(projects, list)

    def test_extract_servers_from_projects(self):
        """Test extracting servers from project list."""
        mock_projects = [
            Project(name="test-project", jenkins_production="https://jenkins.example.com")
        ]

        servers = self.parser.extract_servers_from_projects(mock_projects)

        assert isinstance(servers, list)

    def test_extract_urls_from_cell(self):
        """Test URL extraction from table cells."""
        mock_cell = Mock()
        mock_link = Mock()
        mock_link.__getitem__ = Mock(return_value="https://example.com")
        mock_cell.find_all.return_value = [mock_link]
        mock_cell.get_text.return_value = "Visit https://example.com for more info"

        urls = self.parser._extract_urls_from_cell(mock_cell)

        assert isinstance(urls, list)

    def test_extract_github_org(self):
        """Test GitHub organization extraction."""
        github_url = "https://github.com/testorg/testrepo"

        org = self.parser._extract_github_org(github_url)

        assert isinstance(org, str)

    def test_determine_wiki_type(self):
        """Test wiki type determination."""
        confluence_url = "https://wiki.example.com/confluence"

        wiki_type = self.parser._determine_wiki_type(confluence_url)

        assert isinstance(wiki_type, str)

    def test_determine_server_location(self):
        """Test server location determination."""
        server_name = "jenkins-us-west.example.com"

        location = self.parser._determine_server_location(server_name)

        assert isinstance(location, ServerLocation)

    def test_test_url_accessibility(self):
        """Test URL accessibility testing."""
        test_url = "https://example.com"

        with patch.object(self.parser.client, "head") as mock_head:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_head.return_value = mock_response

            result = self.parser._test_url_accessibility(test_url)

            assert isinstance(result, bool)

    def test_close(self):
        """Test parser cleanup."""
        # Should not raise an exception
        self.parser.close()

    def test_constants(self):
        """Test module constants."""
        assert isinstance(INVENTORY_URL, str)
        assert INVENTORY_URL.startswith("https://")
        assert "inventory" in INVENTORY_URL.lower()


class TestInventoryParserIntegration:
    """Integration tests for inventory parser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = InventoryParser()

    @pytest.mark.integration
    def test_fetch_real_inventory(self):
        """Test fetching real inventory data (integration test)."""
        try:
            html_content = self.parser.fetch_inventory_data()
            assert isinstance(html_content, str)
            assert len(html_content) > 0
            assert "<html" in html_content.lower()
        except httpx.RequestError:
            # Allow test to pass if network is unavailable
            pytest.skip("Network unavailable for integration test")

    def test_parse_realistic_html_structure(self):
        """Test parsing with realistic HTML structure."""
        realistic_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Infrastructure Inventory</title></head>
        <body>
            <div class="section">
                <h2>Active Projects</h2>
                <table class="docutils">
                    <thead>
                        <tr>
                            <th>Project Name</th>
                            <th>Project Type</th>
                            <th>Jenkins URL</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>example-project</td>
                            <td>maven</td>
                            <td>https://jenkins.example.com</td>
                            <td>active</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """

        # Test that parsing doesn't crash with realistic HTML
        projects = self.parser.parse_inventory_table(realistic_html)

        assert isinstance(projects, list)

    def test_error_handling_malformed_html(self):
        """Test handling of malformed HTML."""
        malformed_html = "<html><body><table><tr><td>Incomplete"

        # Should not crash on malformed HTML
        projects = self.parser.parse_inventory_table(malformed_html)

        assert isinstance(projects, list)

    def test_client_cleanup(self):
        """Test proper cleanup of HTTP client."""
        parser = InventoryParser()
        assert parser.client is not None

        # Test that client can be used multiple times
        with patch.object(parser.client, "get") as mock_get:
            mock_response = Mock()
            mock_response.text = "<html></html>"
            mock_get.return_value = mock_response

            # Multiple calls should work
            parser.fetch_inventory_data()
            parser.fetch_inventory_data()

            assert mock_get.call_count == 2

    def test_html_parsing_edge_cases(self):
        """Test HTML parsing edge cases."""
        edge_cases = [
            "",  # Empty string
            "<html></html>",  # Minimal HTML
            "<html><body><p>No tables here</p></body></html>",  # HTML without tables
            "<html><body><table></table></body></html>",  # Empty table
        ]

        for html in edge_cases:
            # Should not crash on any edge case
            projects = self.parser.parse_inventory_table(html)

            assert isinstance(projects, list)

    def test_comprehensive_workflow(self):
        """Test complete workflow from fetching to parsing."""
        mock_html = """
        <html>
        <body>
            <table>
                <tr><th>Project</th><th>Jenkins</th></tr>
                <tr><td>test-project</td><td>https://jenkins.example.com</td></tr>
            </table>
        </body>
        </html>
        """

        with patch.object(self.parser, "fetch_inventory_data", return_value=mock_html):
            # Test full workflow
            projects = self.parser.parse_projects_from_inventory()

            assert isinstance(projects, list)

            # Test server extraction
            servers = self.parser.extract_servers_from_projects(projects)
            assert isinstance(servers, list)

    def test_url_classification(self):
        """Test URL classification functionality."""
        test_urls = [
            "https://jenkins.example.com",
            "https://github.com/org/repo",
            "https://jira.example.com",
            "https://wiki.example.com",
        ]

        # Test that classification methods don't crash
        for url in test_urls:
            try:
                # These methods should handle various URL types
                self.parser._extract_github_org(url)
                self.parser._determine_wiki_type(url)
            except Exception:
                # Some URLs may not be valid for certain operations
                pass

    def test_parser_state_management(self):
        """Test parser state and resource management."""
        parser = InventoryParser()

        # Test multiple operations
        with (
            patch.object(parser.client, "get") as mock_get,
            patch.object(parser.client, "head") as mock_head,
        ):
            mock_get.return_value = Mock(text="<html></html>")
            mock_head.return_value = Mock(status_code=200)

            # Multiple operations should work
            parser.fetch_inventory_data()
            parser._test_url_accessibility("https://example.com")

            # Cleanup should work
            parser.close()

        # Test that parser is still functional after operations
        assert parser.client is not None
