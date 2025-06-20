#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 The Linux Foundation
"""
Test script for the new repository commands in lftools-ng.
"""

import sys
import os
import subprocess
import tempfile
import shutil
from pathlib import Path

def run_command(cmd):
    """Run a command and return the result."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def test_repositories_commands():
    """Test the new repositories commands."""
    print("Testing lftools-ng repositories commands...")

    # Setup test environment
    test_config_dir = tempfile.mkdtemp()
    repos_file = os.path.join(os.path.dirname(__file__), 'resources', 'repositories.yaml')
    test_repos_file = os.path.join(test_config_dir, 'repositories.yaml')

    # Copy sample data
    shutil.copy(repos_file, test_repos_file)

    base_cmd = f"python -c \"from lftools_ng.cli import app; app()\" projects repositories"

    tests = [
        {
            "name": "List all active repositories",
            "cmd": f"{base_cmd} list --config-dir {test_config_dir}",
            "expected_in_output": ["aai/aai-common", "controller", "releng"]
        },
        {
            "name": "List all repositories including archived",
            "cmd": f"{base_cmd} list --config-dir {test_config_dir} --include-archived",
            "expected_in_output": ["policy/engine", "vswitchperf", "Archived"]
        },
        {
            "name": "List repositories for specific project",
            "cmd": f"{base_cmd} list --config-dir {test_config_dir} ONAP",
            "expected_in_output": ["aai/aai-common", "aai/babel"]
        },
        {
            "name": "Get repository info",
            "cmd": f"{base_cmd} info --config-dir {test_config_dir} ONAP \"aai/aai-common\"",
            "expected_in_output": ["ONAP AAI Common modules", "aai-aai-common"]
        },
        {
            "name": "List archived repositories",
            "cmd": f"{base_cmd} archived --config-dir {test_config_dir}",
            "expected_in_output": ["policy/engine", "vswitchperf"]
        },
        {
            "name": "JSON output format",
            "cmd": f"{base_cmd} list --config-dir {test_config_dir} --format json-pretty ONAP",
            "expected_in_output": ["\"project\": \"ONAP\"", "\"gerrit_path\": \"aai/aai-common\""]
        }
    ]

    passed = 0
    failed = 0

    for test in tests:
        print(f"\n{test['name']}...")
        returncode, stdout, stderr = run_command(test['cmd'])

        if returncode != 0:
            print(f"  ❌ FAILED: Command returned {returncode}")
            print(f"     stderr: {stderr}")
            failed += 1
            continue

        all_found = True
        for expected in test['expected_in_output']:
            if expected not in stdout:
                print(f"  ❌ FAILED: Expected '{expected}' not found in output")
                all_found = False

        if all_found:
            print(f"  ✅ PASSED")
            passed += 1
        else:
            print(f"  ❌ FAILED: Missing expected output")
            print(f"     stdout: {stdout}")
            failed += 1

    # Cleanup
    shutil.rmtree(test_config_dir)

    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")

    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed!")
        return False

if __name__ == "__main__":
    # Change to the project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    success = test_repositories_commands()
    sys.exit(0 if success else 1)
