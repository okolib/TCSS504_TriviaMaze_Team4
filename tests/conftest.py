"""
conftest.py — Shared test helpers for the Waxworks test suite.

Provides helper functions used across multiple test files.
These are referenced in docs/interface-tests.md Section 5.

Updated for 5×5 staircase layout:
- Da Vinci is at (1,1), not (1,0)
- Path: (0,0) → SOUTH → (1,0) → EAST → (1,1)
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from maze import Direction


def _navigate_to_trivia_room(m):
    """Move player to the nearest room with trivia.

    5×5 layout: (0,0) → south → (1,0) → east → (1,1).
    Room (1,1) has Leonardo da Vinci trivia.
    """
    m.move(Direction.SOUTH)  # (0,0) → (1,0)
    m.move(Direction.EAST)   # (1,0) → (1,1)


def _get_wrong_key(correct_key: str) -> str:
    """Return an answer key that is NOT the correct one."""
    keys = ["A", "B", "C"]
    keys.remove(correct_key)
    return keys[0]
