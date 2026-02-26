"""
conftest.py — Shared test helpers for the Waxworks test suite.

Provides helper functions used across multiple test files.
These are referenced in docs/interface-tests.md Section 5.
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from maze import Direction


def _navigate_to_trivia_room(m):
    """Move player to the nearest room with trivia.

    Skeleton layout: (0,0) → south → (1,0).
    Room (1,0) has Leonardo da Vinci trivia.
    """
    m.move(Direction.SOUTH)  # (0,0) → (1,0)


def _get_wrong_key(correct_key: str) -> str:
    """Return an answer key that is NOT the correct one."""
    keys = ["A", "B", "C"]
    keys.remove(correct_key)
    return keys[0]
