"""
test_repo_contract.py — Persistence Contract Tests

Tests the Repository module against the RepositoryProtocol in docs/interfaces.md.
Covers all P0 (19–24) and P1 (4–5) repo-related tests from the RUNBOOK.

CURRENTLY IMPORTS FROM: mock_db (stub)
TO SWITCH TO REAL MODULE: Replace 'from mock_db import Repository' with 'from db import Repository'
"""

import sys
import os
import json

# Ensure the tests directory is on the path for mock imports
sys.path.insert(0, os.path.dirname(__file__))

from mock_db import Repository

SAVE_FILE = "test_save.json"


# ===========================================================================
# Setup / Teardown — clean up test files before and after each test
# ===========================================================================

def setup_function():
    """Clean up test file before each test."""
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)


def teardown_function():
    """Clean up test file after each test."""
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)


# ===========================================================================
# P0-19 to P0-21: Save & Load — Happy Path
# ===========================================================================

def test_save_creates_file():
    """P0-19: save() creates a JSON file on disk."""
    repo = Repository()
    repo.save({"player_position": {"row": 0, "col": 0}}, SAVE_FILE)
    assert os.path.exists(SAVE_FILE)


def test_load_returns_saved_data():
    """P0-20: load() returns exactly what was saved."""
    repo = Repository()
    data = {
        "player_position": {"row": 1, "col": 2},
        "wax_meter": 50,
        "game_status": "playing",
        "answered_figures": ["Leonardo da Vinci"],
        "visited_positions": [
            {"row": 0, "col": 0},
            {"row": 1, "col": 2},
        ],
    }
    repo.save(data, SAVE_FILE)
    loaded = repo.load(SAVE_FILE)
    assert loaded == data


def test_save_is_valid_json():
    """P0-21: The saved file is valid JSON that can be parsed independently."""
    repo = Repository()
    repo.save({"wax_meter": 25}, SAVE_FILE)
    with open(SAVE_FILE, "r") as f:
        parsed = json.load(f)
    assert parsed == {"wax_meter": 25}


# ===========================================================================
# P0-22 to P0-24: Load — Edge Cases
# ===========================================================================

def test_load_missing_file_returns_none():
    """P0-22: load() returns None if the file does not exist."""
    repo = Repository()
    result = repo.load("nonexistent_file.json")
    assert result is None


def test_load_corrupt_file_raises_value_error():
    """P0-23: load() raises ValueError if the file is not valid JSON."""
    with open(SAVE_FILE, "w") as f:
        f.write("{this is not json!!!")
    repo = Repository()
    try:
        repo.load(SAVE_FILE)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected


def test_load_empty_file_raises_value_error():
    """P0-24: load() raises ValueError for an empty file."""
    with open(SAVE_FILE, "w") as f:
        f.write("")
    repo = Repository()
    try:
        repo.load(SAVE_FILE)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected


# ===========================================================================
# P1-4 to P1-5: Save — Edge Cases
# ===========================================================================

def test_save_overwrites_existing_file():
    """P1-4: Saving twice overwrites the first save."""
    repo = Repository()
    repo.save({"wax_meter": 10}, SAVE_FILE)
    repo.save({"wax_meter": 99}, SAVE_FILE)
    loaded = repo.load(SAVE_FILE)
    assert loaded["wax_meter"] == 99


def test_save_handles_empty_dict():
    """P1-5: An empty dict can be saved and loaded."""
    repo = Repository()
    repo.save({}, SAVE_FILE)
    loaded = repo.load(SAVE_FILE)
    assert loaded == {}
