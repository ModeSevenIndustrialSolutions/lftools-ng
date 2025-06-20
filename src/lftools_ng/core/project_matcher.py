# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation

"""Project name matching and alias resolution utilities."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional
from difflib import SequenceMatcher

from lftools_ng.core.models import PROJECT_ALIASES


class ProjectMatcher:
    """Fuzzy project name matching and alias resolution."""

    def __init__(self) -> None:
        """Initialize the project matcher."""
        # Create reverse lookups for faster matching
        self._name_to_key: Dict[str, str] = {}
        self._alias_to_key: Dict[str, str] = {}
        self._pattern_to_key: Dict[str, str] = {}

        self._build_lookup_tables()

    def _build_lookup_tables(self) -> None:
        """Build reverse lookup tables for project names, aliases, and patterns."""
        for key, project_info in PROJECT_ALIASES.items():
            # Map primary name
            primary_name = project_info["primary_name"].lower()
            self._name_to_key[primary_name] = key

            # Map aliases
            for alias in project_info.get("aliases", []):
                self._alias_to_key[alias.lower()] = key

            # Map name patterns
            for pattern in project_info.get("name_patterns", []):
                self._pattern_to_key[pattern.lower()] = key

            # Map previous names
            for prev_name in project_info.get("previous_names", []):
                self._alias_to_key[prev_name.lower()] = key

    def normalize_name(self, name: str) -> str:
        """Normalize a project name for consistent matching.

        Args:
            name: Project name to normalize.

        Returns:
            Normalized project name.
        """
        if not name:
            return ""

        # Convert to lowercase and clean up
        normalized = name.lower().strip()

        # Remove common parenthetical suffixes
        normalized = re.sub(r'\s*\(formerly\s+[^)]+\)', '', normalized)
        normalized = re.sub(r'\s*\([^)]*\)', '', normalized)

        # Clean up whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def find_project_key(self, name: str) -> Optional[str]:
        """Find the project key for a given name using fuzzy matching.

        Args:
            name: Project name to look up.

        Returns:
            Project key if found, None otherwise.
        """
        if not name:
            return None

        normalized_name = self.normalize_name(name)

        # Try exact matches first

        # Check primary names
        if normalized_name in self._name_to_key:
            return self._name_to_key[normalized_name]

        # Check aliases
        if normalized_name in self._alias_to_key:
            return self._alias_to_key[normalized_name]

        # Check patterns
        if normalized_name in self._pattern_to_key:
            return self._pattern_to_key[normalized_name]

        # Try fuzzy matching with patterns
        best_match = self._fuzzy_match_patterns(normalized_name)
        if best_match:
            return best_match

        # Try fuzzy matching with aliases
        best_match = self._fuzzy_match_aliases(normalized_name)
        if best_match:
            return best_match

        return None

    def _fuzzy_match_patterns(self, name: str, threshold: float = 0.8) -> Optional[str]:
        """Fuzzy match against name patterns.

        Args:
            name: Normalized name to match.
            threshold: Minimum similarity threshold.

        Returns:
            Project key if match found, None otherwise.
        """
        best_ratio = 0.0
        best_key = None

        for pattern, key in self._pattern_to_key.items():
            ratio = SequenceMatcher(None, name, pattern).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_key = key

        return best_key

    def _fuzzy_match_aliases(self, name: str, threshold: float = 0.8) -> Optional[str]:
        """Fuzzy match against aliases.

        Args:
            name: Normalized name to match.
            threshold: Minimum similarity threshold.

        Returns:
            Project key if match found, None otherwise.
        """
        best_ratio = 0.0
        best_key = None

        for alias, key in self._alias_to_key.items():
            ratio = SequenceMatcher(None, name, alias).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_key = key

        return best_key

    def get_project_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get complete project information for a given name.

        Args:
            name: Project name to look up.

        Returns:
            Project information dictionary if found, None otherwise.
        """
        key = self.find_project_key(name)
        if key and key in PROJECT_ALIASES:
            return PROJECT_ALIASES[key].copy()
        return None

    def get_aliases(self, name: str) -> list[str]:
        """Get all aliases for a project name.

        Args:
            name: Project name to look up.

        Returns:
            List of aliases, empty list if not found.
        """
        info = self.get_project_info(name)
        return info.get("aliases", []) if info else []

    def get_primary_name(self, name: str) -> Optional[str]:
        """Get the primary name for a project.

        Args:
            name: Project name to look up.

        Returns:
            Primary name if found, None otherwise.
        """
        info = self.get_project_info(name)
        return info.get("primary_name") if info else None

    def get_domain(self, name: str) -> Optional[str]:
        """Get the domain for a project.

        Args:
            name: Project name to look up.

        Returns:
            Domain if found, None otherwise.
        """
        info = self.get_project_info(name)
        return info.get("domain") if info else None

    def is_alias(self, name: str, target: str) -> bool:
        """Check if one name is an alias of another.

        Args:
            name: Name to check.
            target: Target name to check against.

        Returns:
            True if name is an alias of target, False otherwise.
        """
        name_key = self.find_project_key(name)
        target_key = self.find_project_key(target)

        return name_key is not None and name_key == target_key

    def match_any_name(self, name: str, candidates: list[str]) -> Optional[str]:
        """Find if a name matches any candidate using fuzzy matching.

        Args:
            name: Name to match.
            candidates: List of candidate names to match against.

        Returns:
            Best matching candidate if found, None otherwise.
        """
        name_key = self.find_project_key(name)
        if not name_key:
            return None

        for candidate in candidates:
            candidate_key = self.find_project_key(candidate)
            if candidate_key == name_key:
                return candidate

        return None


# Global instance for easy access
_project_matcher: Optional[ProjectMatcher] = None


def get_project_matcher() -> ProjectMatcher:
    """Get the global project matcher instance."""
    global _project_matcher
    if _project_matcher is None:
        _project_matcher = ProjectMatcher()
    return _project_matcher


# Convenience functions
def resolve_project_name(name: str) -> Optional[str]:
    """Resolve a project name to its primary name.

    Args:
        name: Project name to resolve.

    Returns:
        Primary project name if found, None otherwise.
    """
    return get_project_matcher().get_primary_name(name)


def get_project_aliases(name: str) -> list[str]:
    """Get all aliases for a project.

    Args:
        name: Project name to look up.

    Returns:
        List of aliases, empty list if not found.
    """
    return get_project_matcher().get_aliases(name)


def is_same_project(name1: str, name2: str) -> bool:
    """Check if two names refer to the same project.

    Args:
        name1: First project name.
        name2: Second project name.

    Returns:
        True if both names refer to the same project, False otherwise.
    """
    return get_project_matcher().is_alias(name1, name2)


def normalize_project_name(name: str) -> str:
    """Normalize a project name for consistent handling.

    Args:
        name: Project name to normalize.

    Returns:
        Normalized project name.
    """
    return get_project_matcher().normalize_name(name)
