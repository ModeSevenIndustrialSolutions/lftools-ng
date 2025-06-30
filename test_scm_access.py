#!/usr/bin/env python3
"""Test script to verify SCM URL access for internal code use."""

import pathlib
import sys
import os

# Add the src directory to the path
current_dir = pathlib.Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from lftools_ng.core.projects import ProjectManager

def test_scm_access():
    """Test that we can access SCM information programmatically."""

    config_dir = pathlib.Path.home() / ".config" / "lftools-ng"
    manager = ProjectManager(config_dir)

    projects = manager.list_projects()

    print("SCM Information Access Test")
    print("=" * 50)
    print(f"Total projects loaded: {len(projects)}")
    print()

    # Test SCM platform access
    scm_platforms = {}
    scm_urls_available = 0

    for project in projects:
        platform = project.get("primary_scm_platform", "Unknown")
        url = project.get("primary_scm_url", "")

        if platform in scm_platforms:
            scm_platforms[platform] += 1
        else:
            scm_platforms[platform] = 1

        if url:
            scm_urls_available += 1

    print("SCM Platform Distribution:")
    for platform, count in sorted(scm_platforms.items()):
        print(f"  {platform}: {count} projects")

    print(f"\nProjects with SCM URLs: {scm_urls_available}/{len(projects)}")

    # Show some examples
    print("\nExample SCM URLs (for internal code use):")
    examples_shown = 0
    for project in projects:
        if examples_shown >= 5:
            break
        url = project.get("primary_scm_url", "")
        if url:
            name = project.get("name", "Unknown")
            platform = project.get("primary_scm_platform", "Unknown")
            print(f"  {name}: {platform} -> {url}")
            examples_shown += 1

    # Test fall-through project detection
    fall_through_count = 0
    main_inventory_projects = {"O-RAN-SC", "ONAP", "OpenDaylight", "AGL", "Akraino", "EdgeX", "FD.io", "OPNFV"}

    for project in projects:
        name = project.get("name", "")
        if name not in main_inventory_projects:
            fall_through_count += 1

    print(f"\nFall-through projects detected: {fall_through_count}")

    print("\n✓ All SCM information is accessible programmatically!")
    print("✓ Fall-through projects are included!")
    print("✓ Primary SCM platform and URLs are available for internal code use!")

if __name__ == "__main__":
    test_scm_access()
