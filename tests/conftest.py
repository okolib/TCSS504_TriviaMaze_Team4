"""
conftest.py — Shared test helpers for the Waxworks test suite.

Provides helper functions used across multiple test files.
These are referenced in docs/interface-tests.md Section 5.

Updated for randomized maze layout:
- Uses BFS to find the shortest path to a trivia room
- No longer depends on hardcoded room positions
"""

import sys
import os
from collections import deque

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from maze import Direction, DoorState, Position, DELTA


def _navigate_to_trivia_room(m):
    """Move player to the nearest room with a wax figure via BFS.

    Works with any maze layout — finds the shortest OPEN-door path
    from the current position to a room with a figure_name.
    """
    start = m.get_player_position()
    target = None

    # BFS to find nearest figure room
    visited = {(start.row, start.col)}
    # queue entries: ((row, col), [list of Directions to get there])
    queue = deque([((start.row, start.col), [])])

    while queue:
        (r, c), moves = queue.popleft()
        room = m.get_room(Position(r, c))
        if room.figure_name is not None and (r, c) != (start.row, start.col):
            target = moves
            break
        for d in Direction:
            if room.doors[d] in (DoorState.OPEN,):
                dr, dc = DELTA[d]
                nr, nc = r + dr, c + dc
                if (0 <= nr < m.rows and 0 <= nc < m.cols
                        and (nr, nc) not in visited):
                    visited.add((nr, nc))
                    queue.append(((nr, nc), moves + [d]))

    if target is None:
        raise RuntimeError("No reachable trivia room found from current position")

    for d in target:
        result = m.move(d)
        assert result in ("moved", "staircase"), (
            f"BFS path should be all OPEN doors, but move({d}) returned {result!r}"
        )


def _get_wrong_key(correct_key: str) -> str:
    """Return an answer key that is NOT the correct one."""
    keys = ["A", "B", "C"]
    keys.remove(correct_key)
    return keys[0]
