# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Tests for project name matching and alias resolution."""

from lftools_ng.core.project_matcher import (
    ProjectMatcher,
    get_project_matcher,
    resolve_project_name,
    get_project_aliases,
    is_same_project,
    normalize_project_name,
)


class TestProjectMatcher:
    """Test cases for ProjectMatcher."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.matcher = ProjectMatcher()

    def test_normalize_name(self) -> None:
        """Test project name normalization."""
        assert self.matcher.normalize_name("Anuket (Formerly OPNFV)") == "anuket"
        assert self.matcher.normalize_name("O-RAN Software Community") == "o-ran software community"
        assert self.matcher.normalize_name("  ONAP  ") == "onap"
        assert self.matcher.normalize_name("") == ""

    def test_normalize_name_edge_cases(self) -> None:
        """Test edge cases for project name normalization."""
        # Test various parenthetical patterns
        assert self.matcher.normalize_name("Project (Formerly Other)") == "project"
        assert self.matcher.normalize_name("Project (Beta)") == "project"
        assert self.matcher.normalize_name("Project (Version 2)") == "project"

        # Test special characters and spacing
        assert self.matcher.normalize_name("Project-Name") == "project-name"
        assert self.matcher.normalize_name("Project_Name") == "project_name"
        assert self.matcher.normalize_name("Project.Name") == "project.name"
        assert self.matcher.normalize_name("   Multiple   Spaces   ") == "multiple spaces"

        # Test Unicode and special characters
        assert self.matcher.normalize_name("Projéct Nàme") == "projéct nàme"

        # Test empty and None cases
        assert self.matcher.normalize_name("") == ""
        assert self.matcher.normalize_name("   ") == ""

    def test_find_project_key_exact_match(self) -> None:
        """Test finding project keys with exact matches."""
        assert self.matcher.find_project_key("anuket") == "anuket"
        assert self.matcher.find_project_key("OPNFV") == "anuket"
        assert self.matcher.find_project_key("onap") == "onap"
        assert self.matcher.find_project_key("ECOMP") == "onap"
        assert self.matcher.find_project_key("o-ran-sc") == "o-ran-sc"
        assert self.matcher.find_project_key("oran") == "o-ran-sc"

    def test_find_project_key_fuzzy_match(self) -> None:
        """Test finding project keys with fuzzy matching."""
        assert self.matcher.find_project_key("Anuket (Formerly OPNFV)") == "anuket"
        assert self.matcher.find_project_key("O-RAN") == "o-ran-sc"
        assert self.matcher.find_project_key("O-RAN Software Community") == "o-ran-sc"

    def test_find_project_key_edge_cases(self) -> None:
        """Test edge cases for project key finding."""
        # Test empty and None inputs
        assert self.matcher.find_project_key("") is None
        assert self.matcher.find_project_key("   ") is None

        # Test non-existent projects
        assert self.matcher.find_project_key("nonexistent-project") is None
        assert self.matcher.find_project_key("completely-unknown") is None

        # Test case variations
        assert self.matcher.find_project_key("ANUKET") == "anuket"
        assert self.matcher.find_project_key("anuket") == "anuket"
        assert self.matcher.find_project_key("Anuket") == "anuket"

    def test_fuzzy_matching_thresholds(self) -> None:
        """Test fuzzy matching with different similarity thresholds."""
        # Test partial matches that should work
        assert self.matcher.find_project_key("Anuke") == "anuket"  # Should fuzzy match

        # Test partial matches that are too different (these should not match)
        assert self.matcher.find_project_key("xyz") is None  # Too different
        assert self.matcher.find_project_key("a") is None  # Too short/different

    def test_fuzzy_match_patterns_direct(self) -> None:
        """Test fuzzy pattern matching directly."""
        # Test with high threshold - should not match
        result = self.matcher._fuzzy_match_patterns("completely different", threshold=0.9)
        assert result is None

        # Test with reasonable threshold - should match similar patterns
        result = self.matcher._fuzzy_match_patterns("anuket formerly", threshold=0.6)
        assert result == "anuket"

    def test_fuzzy_match_aliases_direct(self) -> None:
        """Test fuzzy alias matching directly."""
        # Test with high threshold - should not match dissimilar
        result = self.matcher._fuzzy_match_aliases("xyz", threshold=0.9)
        assert result is None

        # Test with reasonable threshold - should match similar aliases
        result = self.matcher._fuzzy_match_aliases("opnf", threshold=0.6)
        assert result == "anuket"

    def test_get_project_info(self) -> None:
        """Test getting complete project information."""
        info = self.matcher.get_project_info("anuket")
        assert info is not None
        assert info["primary_name"] == "Anuket"
        assert "OPNFV" in info["aliases"]
        assert "opnfv" in info["aliases"]

        info = self.matcher.get_project_info("O-RAN")
        assert info is not None
        assert info["primary_name"] == "O-RAN Software Community"
        assert "oran" in info["aliases"]
        assert "o-ran-sc" in info["aliases"]

    def test_get_project_info_edge_cases(self) -> None:
        """Test edge cases for getting project info."""
        # Test with empty string
        info = self.matcher.get_project_info("")
        assert info is None

        # Test with non-existent project
        info = self.matcher.get_project_info("nonexistent")
        assert info is None

        # Test with whitespace
        info = self.matcher.get_project_info("   ")
        assert info is None

    def test_get_aliases(self) -> None:
        """Test getting project aliases."""
        aliases = self.matcher.get_aliases("anuket")
        assert "OPNFV" in aliases
        assert "opnfv" in aliases

        aliases = self.matcher.get_aliases("O-RAN")
        assert "oran" in aliases
        assert "o-ran-sc" in aliases

        # Test non-existent project
        aliases = self.matcher.get_aliases("nonexistent")
        assert aliases == []

    def test_get_aliases_edge_cases(self) -> None:
        """Test edge cases for getting aliases."""
        # Test with empty string
        aliases = self.matcher.get_aliases("")
        assert aliases == []

        # Test with whitespace
        aliases = self.matcher.get_aliases("   ")
        assert aliases == []

    def test_get_primary_name(self) -> None:
        """Test getting primary project names."""
        assert self.matcher.get_primary_name("anuket") == "Anuket"
        assert self.matcher.get_primary_name("OPNFV") == "Anuket"
        assert self.matcher.get_primary_name("Anuket (Formerly OPNFV)") == "Anuket"

        assert self.matcher.get_primary_name("O-RAN") == "O-RAN Software Community"
        assert self.matcher.get_primary_name("oran") == "O-RAN Software Community"

        # Test non-existent project
        assert self.matcher.get_primary_name("nonexistent") is None

    def test_get_primary_name_edge_cases(self) -> None:
        """Test edge cases for getting primary names."""
        # Test with empty string
        primary = self.matcher.get_primary_name("")
        assert primary is None

        # Test with whitespace
        primary = self.matcher.get_primary_name("   ")
        assert primary is None

    def test_is_alias(self) -> None:
        """Test checking if names are aliases."""
        assert self.matcher.is_alias("anuket", "OPNFV")
        assert self.matcher.is_alias("OPNFV", "anuket")
        assert self.matcher.is_alias("O-RAN", "oran")
        assert self.matcher.is_alias("o-ran-sc", "O-RAN-SC")

        # Different projects
        assert not self.matcher.is_alias("anuket", "onap")
        assert not self.matcher.is_alias("O-RAN", "anuket")

    def test_is_alias_edge_cases(self) -> None:
        """Test edge cases for alias checking."""
        # Test with empty strings
        assert not self.matcher.is_alias("", "anuket")
        assert not self.matcher.is_alias("anuket", "")
        assert not self.matcher.is_alias("", "")

        # Test with whitespace
        assert not self.matcher.is_alias("   ", "anuket")
        assert not self.matcher.is_alias("anuket", "   ")

        # Test with non-existent projects
        assert not self.matcher.is_alias("nonexistent1", "nonexistent2")
        assert not self.matcher.is_alias("anuket", "nonexistent")

    def test_match_any_name(self) -> None:
        """Test matching against a list of candidates."""
        candidates = ["Anuket", "ONAP", "OpenDaylight"]

        assert self.matcher.match_any_name("OPNFV", candidates) == "Anuket"
        assert self.matcher.match_any_name("ECOMP", candidates) == "ONAP"
        assert self.matcher.match_any_name("ODL", candidates) == "OpenDaylight"

        # No match
        assert self.matcher.match_any_name("nonexistent", candidates) is None

    def test_match_any_name_edge_cases(self) -> None:
        """Test edge cases for matching against candidate lists."""
        candidates = ["Anuket", "ONAP", "OpenDaylight"]

        # Test with empty name
        result = self.matcher.match_any_name("", candidates)
        assert result is None

        # Test with non-existent name
        result = self.matcher.match_any_name("nonexistent", candidates)
        assert result is None

        # Test with empty candidates list
        result = self.matcher.match_any_name("OPNFV", [])
        assert result is None

        # Test with candidates that don't match
        result = self.matcher.match_any_name("OPNFV", ["Zowe", "EdgeX"])
        assert result is None

    def test_comprehensive_alias_coverage(self) -> None:
        """Test comprehensive coverage of all known aliases."""
        # Test all Anuket variations
        anuket_variations = ["anuket", "ANUKET", "Anuket", "OPNFV", "opnfv", "Anuket (Formerly OPNFV)"]
        for variation in anuket_variations:
            assert self.matcher.find_project_key(variation) == "anuket"
            assert self.matcher.get_primary_name(variation) == "Anuket"

        # Test all O-RAN variations
        oran_variations = ["o-ran", "O-RAN", "oran", "ORAN", "o-ran-sc", "O-RAN-SC", "O-RAN Software Community"]
        for variation in oran_variations:
            assert self.matcher.find_project_key(variation) == "o-ran-sc"
            assert self.matcher.get_primary_name(variation) == "O-RAN Software Community"

        # Test all ONAP variations
        onap_variations = ["onap", "ONAP", "ecomp", "ECOMP"]
        for variation in onap_variations:
            assert self.matcher.find_project_key(variation) == "onap"
            assert self.matcher.get_primary_name(variation) == "ONAP"

        # Test all OpenDaylight variations
        odl_variations = ["opendaylight", "OpenDaylight", "odl", "ODL"]
        for variation in odl_variations:
            assert self.matcher.find_project_key(variation) == "opendaylight"
            assert self.matcher.get_primary_name(variation) == "OpenDaylight"

    def test_case_insensitive_matching(self) -> None:
        """Test that all matching is case insensitive."""
        test_cases = [
            ("anuket", "ANUKET"),
            ("opnfv", "OPNFV"),
            ("onap", "ONAP"),
            ("ecomp", "ECOMP"),
            ("o-ran", "O-RAN"),
            ("oran", "ORAN"),
            ("odl", "ODL"),
            ("opendaylight", "OPENDAYLIGHT"),
        ]

        for lower_case, upper_case in test_cases:
            assert self.matcher.find_project_key(lower_case) == self.matcher.find_project_key(upper_case)
            assert self.matcher.get_primary_name(lower_case) == self.matcher.get_primary_name(upper_case)
            assert self.matcher.is_alias(lower_case, upper_case)

    def test_sequence_matcher_similarity(self) -> None:
        """Test the SequenceMatcher similarity logic."""
        # Test that very similar strings don't match if they're below threshold
        assert self.matcher.find_project_key("completely different name") is None
        assert self.matcher.find_project_key("xyz123") is None

        # Test close matches that do work
        assert self.matcher.find_project_key("Anuke") == "anuket"  # Close enough to match


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_resolve_project_name(self) -> None:
        """Test project name resolution."""
        assert resolve_project_name("OPNFV") == "Anuket"
        assert resolve_project_name("oran") == "O-RAN Software Community"
        assert resolve_project_name("nonexistent") is None

    def test_resolve_project_name_edge_cases(self) -> None:
        """Test edge cases for project name resolution."""
        # Test empty and whitespace
        assert resolve_project_name("") is None
        assert resolve_project_name("   ") is None

        # Test case variations
        assert resolve_project_name("ANUKET") == "Anuket"
        assert resolve_project_name("anuket") == "Anuket"
        assert resolve_project_name("Anuket") == "Anuket"

    def test_get_project_aliases(self) -> None:
        """Test getting project aliases."""
        aliases = get_project_aliases("anuket")
        assert "OPNFV" in aliases

        aliases = get_project_aliases("nonexistent")
        assert aliases == []

    def test_get_project_aliases_edge_cases(self) -> None:
        """Test edge cases for getting project aliases."""
        # Test empty and whitespace
        aliases = get_project_aliases("")
        assert aliases == []

        aliases = get_project_aliases("   ")
        assert aliases == []

        # Test case variations
        aliases_lower = get_project_aliases("anuket")
        aliases_upper = get_project_aliases("ANUKET")
        assert aliases_lower == aliases_upper

    def test_is_same_project(self) -> None:
        """Test checking if two names refer to the same project."""
        assert is_same_project("anuket", "OPNFV")
        assert is_same_project("O-RAN", "oran")
        assert not is_same_project("anuket", "onap")

    def test_is_same_project_edge_cases(self) -> None:
        """Test edge cases for checking if projects are the same."""
        # Test empty strings
        assert not is_same_project("", "anuket")
        assert not is_same_project("anuket", "")
        assert not is_same_project("", "")

        # Test whitespace
        assert not is_same_project("   ", "anuket")
        assert not is_same_project("anuket", "   ")

        # Test non-existent projects
        assert not is_same_project("nonexistent1", "nonexistent2")
        assert not is_same_project("anuket", "nonexistent")

        # Test same string
        assert is_same_project("anuket", "anuket")
        assert is_same_project("OPNFV", "OPNFV")

    def test_normalize_project_name(self) -> None:
        """Test project name normalization."""
        assert normalize_project_name("Anuket (Formerly OPNFV)") == "anuket"
        assert normalize_project_name("O-RAN Software Community") == "o-ran software community"

    def test_normalize_project_name_edge_cases(self) -> None:
        """Test edge cases for project name normalization."""
        # Test empty and whitespace
        assert normalize_project_name("") == ""
        assert normalize_project_name("   ") == ""

        # Test various patterns
        assert normalize_project_name("PROJECT (BETA)") == "project"
        assert normalize_project_name("Project-Name_Test") == "project-name_test"
        assert normalize_project_name("   Multiple   Spaces   ") == "multiple spaces"

    def test_global_matcher_singleton(self) -> None:
        """Test that the global matcher is a singleton."""
        matcher1 = get_project_matcher()
        matcher2 = get_project_matcher()
        assert matcher1 is matcher2

    def test_comprehensive_integration(self) -> None:
        """Test comprehensive integration of all convenience functions."""
        # Test a complete workflow for each major project
        projects_to_test = [
            ("OPNFV", "Anuket"),
            ("oran", "O-RAN Software Community"),
            ("ECOMP", "ONAP"),
            ("ODL", "OpenDaylight"),
        ]

        for alias, expected_primary in projects_to_test:
            # Test resolution
            primary = resolve_project_name(alias)
            assert primary == expected_primary

            # Test aliases
            aliases = get_project_aliases(alias)
            assert len(aliases) > 0
            assert alias.upper() in [a.upper() for a in aliases] or alias.lower() in [a.lower() for a in aliases]

            # Test same project check
            assert is_same_project(alias, expected_primary)

            # Test normalization
            normalized = normalize_project_name(alias)
            assert len(normalized) > 0
            assert normalized.islower() or not normalized.isalpha()  # Should be lowercase or contain non-alpha


class TestProjectManagerIntegration:
    """Test integration between ProjectMatcher and ProjectManager."""

    def test_project_manager_fuzzy_matching(self, tmp_path: str) -> None:
        """Test that ProjectManager can use fuzzy matching."""
        from lftools_ng.core.projects import ProjectManager
        import yaml
        import pathlib

        manager = ProjectManager(pathlib.Path(tmp_path))

        # Create test data that matches the real database structure
        test_data = {
            "projects": [
                {
                    "name": "Anuket (Formerly OPNFV)",
                    "aliases": ["OPNFV", "anuket", "opnfv"],
                },
                {
                    "name": "O-RAN",
                    "aliases": ["O-RAN", "ORAN", "O-RAN-SC", "o-ran-sc", "oran"],
                }
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test that ProjectManager can find projects using fuzzy matching
        project = manager.find_project_by_name("OPNFV")
        assert project is not None
        assert project["name"] == "Anuket (Formerly OPNFV)"

        project = manager.find_project_by_name("oran")
        assert project is not None
        assert project["name"] == "O-RAN"

        # Test resolution
        resolved = manager.resolve_project_name("OPNFV")
        assert resolved == "Anuket (Formerly OPNFV)"

        # Test same project check
        assert manager.is_same_project("OPNFV", "anuket")
        assert manager.is_same_project("oran", "O-RAN-SC")

    def test_error_handling_integration(self, tmp_path: str) -> None:
        """Test error handling between ProjectMatcher and ProjectManager."""
        from lftools_ng.core.projects import ProjectManager
        import pathlib

        manager = ProjectManager(pathlib.Path(tmp_path))

        # Test with empty database
        assert manager.find_project_by_name("OPNFV") is None
        assert manager.resolve_project_name("nonexistent") is None
        assert manager.get_project_aliases("nonexistent") == []
        assert not manager.is_same_project("nonexistent1", "nonexistent2")


class TestAdditionalCoverage:
    """Additional tests to achieve better coverage."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.matcher = ProjectMatcher()

    def test_pattern_matching_coverage(self) -> None:
        """Test the pattern matching path that was missing coverage."""
        # This should match via the pattern lookup (line 96 in project_matcher.py)
        # Test with known patterns that should match exactly

        # Test known patterns that should hit the pattern matching path
        # These patterns are defined in PROJECT_ALIASES and should match exactly
        test_patterns = [
            ("anuket formerly opnfv", "anuket"),
            ("o-ran software community", "o-ran-sc"),
        ]

        for pattern, expected_key in test_patterns:
            result = self.matcher.find_project_key(pattern)
            assert result == expected_key, f"Pattern '{pattern}' should match key '{expected_key}'"

    def test_fuzzy_alias_matching_return_path(self) -> None:
        """Test the fuzzy alias matching return path (line 106)."""
        # Test edge case where pattern matching fails but alias matching succeeds
        # Use a misspelled alias that's close enough to match
        result = self.matcher.find_project_key("opnf")  # Close to "opnfv"
        assert result == "anuket"

        # Test another fuzzy alias match
        result = self.matcher.find_project_key("ecom")  # Close to "ecomp"
        assert result == "onap"

    def test_name_variations_with_patterns(self) -> None:
        """Test matching with various name patterns and edge cases."""
        # Test names that should match via different paths
        test_cases = [
            # Test case variations that hit different code paths
            ("anuket", "anuket"),           # Direct key match
            ("ANUKET", "anuket"),           # Case variation
            ("opnfv", "anuket"),            # Alias match
            ("OPNFV", "anuket"),            # Case variation of alias
            ("onap", "onap"),               # Direct key match
            ("ECOMP", "onap"),              # Alias match
        ]

        for input_name, expected_key in test_cases:
            result = self.matcher.find_project_key(input_name)
            assert result == expected_key, f"Expected {expected_key} for input '{input_name}', got {result}"

    def test_special_character_handling(self) -> None:
        """Test handling of special characters in project names."""
        # Test names with various special characters
        test_cases = [
            ("O-RAN", "o-ran-sc"),
            ("O_RAN", "o-ran-sc"),  # Should still match with underscore
            ("O.RAN", "o-ran-sc"),  # Should still match with period
            ("O RAN", "o-ran-sc"),  # Should still match with space
        ]

        for input_name, expected_key in test_cases:
            result = self.matcher.find_project_key(input_name)
            assert result == expected_key, f"Expected {expected_key} for input '{input_name}', got {result}"

    def test_match_any_name_comprehensive(self) -> None:
        """Test match_any_name with comprehensive scenarios."""
        # Test with various candidate lists and inputs
        candidates = ["Anuket", "ONAP", "OpenDaylight", "EdgeX Foundry"]

        # Test exact matches
        assert self.matcher.match_any_name("Anuket", candidates) == "Anuket"
        assert self.matcher.match_any_name("ONAP", candidates) == "ONAP"

        # Test alias matches
        assert self.matcher.match_any_name("OPNFV", candidates) == "Anuket"
        assert self.matcher.match_any_name("ECOMP", candidates) == "ONAP"
        assert self.matcher.match_any_name("ODL", candidates) == "OpenDaylight"

        # Test fuzzy matches
        assert self.matcher.match_any_name("Anuke", candidates) == "Anuket"
        assert self.matcher.match_any_name("EdgeX", candidates) == "EdgeX Foundry"

        # Test no matches
        assert self.matcher.match_any_name("CompleteLyDifferent", candidates) is None

    def test_get_project_info_comprehensive(self) -> None:
        """Test get_project_info with all possible inputs."""
        # Test known project keys
        test_projects = ["anuket", "onap", "opendaylight", "o-ran-sc"]

        for project_key in test_projects:
            info = self.matcher.get_project_info(project_key)
            assert info is not None, f"Should get info for project key: {project_key}"
            assert "primary_name" in info
            assert "aliases" in info
            assert isinstance(info["aliases"], list)


class TestProjectManagerAdditionalCoverage:
    """Additional tests for ProjectManager to improve coverage."""

    def test_load_projects_db_error_handling(self, tmp_path: str) -> None:
        """Test error handling in load_projects_db."""
        from lftools_ng.core.projects import ProjectManager
        import pathlib

        manager = ProjectManager(pathlib.Path(tmp_path))

        # Test with non-existent file
        projects = manager.load_projects_db()
        assert projects == []

        # Test with invalid YAML
        with open(manager.projects_file, "w") as f:
            f.write("invalid: yaml: content: [")

        projects = manager.load_projects_db()
        assert projects == []

        # Test with valid YAML but wrong structure
        with open(manager.projects_file, "w") as f:
            f.write("not_projects: []")

        projects = manager.load_projects_db()
        assert projects == []

    def test_project_manager_basic_functionality(self, tmp_path: str) -> None:
        """Test basic ProjectManager functionality with simple test data."""
        from lftools_ng.core.projects import ProjectManager
        import yaml
        import pathlib
        from typing import Any, Dict, List

        manager = ProjectManager(pathlib.Path(tmp_path))

        # Create simple test data with proper typing
        test_data: Dict[str, List[Dict[str, Any]]] = {
            "projects": [
                {
                    "name": "Test Project",
                    "aliases": ["TP", "test-project"],
                },
                {
                    "name": "Another Project",
                    "aliases": ["AP"],
                },
            ]
        }

        with open(manager.projects_file, "w") as f:
            yaml.dump(test_data, f)

        # Test exact name matching
        project = manager.find_project_by_name("Test Project")
        assert project is not None
        assert project["name"] == "Test Project"

        # Test case insensitive matching
        project = manager.find_project_by_name("test project")
        assert project is not None
        assert project["name"] == "Test Project"

        # Test list names and aliases
        all_names = manager.list_project_names_and_aliases()
        assert "Test Project" in all_names
        assert "TP" in all_names
        assert "test-project" in all_names
        assert "Another Project" in all_names
        assert "AP" in all_names

        # Test with non-existent project
        project = manager.find_project_by_name("Non-existent")
        assert project is None

        # Test resolve with non-existent
        resolved = manager.resolve_project_name("Non-existent")
        assert resolved is None

        # Test get aliases with non-existent
        aliases = manager.get_project_aliases("Non-existent")
        assert aliases == []
