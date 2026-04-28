"""
test_engine_integration.py — Engine / Integration Tests

Tests the Engine translation layer and full save/load pipeline,
plus full game simulations using the RFC-compliant APIs.

Updated for:
- 5×5 staircase layout
- attempt_answer(answer_key, correct_key) per RFC
- curse_level / defeated_figures naming
- SQLite-backed Repository
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from maze import (
    Maze, Position, Direction, GameStatus, GameState, DoorState,
)
from db import Repository
from main import Engine
from conftest import _navigate_to_trivia_room
from collections import deque
from maze import DELTA, OPPOSITE

TEST_DB = "test_integration.db"
CORRECT_KEY = "B"
WRONG_KEY = "C"


class ViewStub:
    """Minimal View stub for Engine tests — absorbs all display calls."""
    def display_welcome(self): pass
    def display_room(self, *args, **kwargs): pass
    def display_fog_map(self, *args, **kwargs): pass
    def display_move_result(self, *args, **kwargs): pass
    def display_confrontation(self, *args, **kwargs): pass
    def display_answer_result(self, *args, **kwargs): pass
    def display_save_result(self, *args, **kwargs): pass
    def display_load_result(self, *args, **kwargs): pass
    def display_endgame(self, *args, **kwargs): pass
    def display_error(self, *args, **kwargs): pass
    def get_input(self, *args, **kwargs): return "quit"


# ===========================================================================
# Setup / Teardown
# ===========================================================================

def setup_function():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def teardown_function():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ===========================================================================
# P0-25 to P0-27: Translation Layer
# ===========================================================================

def test_game_state_to_dict_serializes_position():
    """P0-25: Position objects become {"row": int, "col": int} dicts."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert d["player_position"] == {"row": 0, "col": 0}
    assert isinstance(d["player_position"], dict)
    assert "door_states" in d
    assert isinstance(d["door_states"], list)


def test_game_state_to_dict_serializes_enums():
    """P0-26: GameStatus enum becomes a string."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert d["game_status"] == "playing"
    assert isinstance(d["game_status"], str)


def test_game_state_to_dict_uses_rfc_names():
    """RFC: Serialized dict uses curse_level and defeated_figures."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert "curse_level" in d
    assert "defeated_figures" in d


def test_dict_to_game_state_roundtrip():
    """P0-27: Converting state → dict → state produces equivalent data."""
    m = Maze()
    # Move somewhere dynamic
    room = m.get_room(m.get_player_position())
    open_dir = next(d for d, s in room.doors.items() if s == DoorState.OPEN)
    m.move(open_dir)
    original = m.get_game_state()
    d = Engine.game_state_to_dict(original)
    restored = Engine.dict_to_game_state(d)
    assert restored.player_position == original.player_position
    assert restored.curse_level == original.curse_level
    assert restored.game_status == original.game_status
    assert restored.defeated_figures == original.defeated_figures
    assert restored.door_states == original.door_states


# ===========================================================================
# P0-28: Save / Load Integration
# ===========================================================================

def test_save_and_load_game_roundtrip():
    """P0-28: Full roundtrip: maze → engine.save → DB → engine.load → maze."""
    m = Maze()
    repo = Repository(db_path=TEST_DB)
    view = ViewStub()
    engine = Engine(m, repo, view, save_filepath="test_slot")

    # Move dynamically
    room = m.get_room(m.get_player_position())
    open_dir = next(d for d, s in room.doors.items() if s == DoorState.OPEN)
    m.move(open_dir)
    moved_pos = m.get_player_position()
    engine.save_game()

    m2 = Maze()
    engine2 = Engine(m2, repo, view, save_filepath="test_slot")
    success = engine2.load_game()
    assert success is True
    assert m2.get_player_position() == moved_pos


# ===========================================================================
# P0-29 to P0-31: Full Game Simulation (Maze-Rule Validation)
# ===========================================================================

def _bfs_navigate(m, target_rc):
    """BFS from current position to target, following OPEN doors."""
    start = m.get_player_position()
    visited = {(start.row, start.col)}
    queue = deque([((start.row, start.col), [])])
    while queue:
        (r, c), moves = queue.popleft()
        if (r, c) == target_rc:
            for d in moves:
                m.move(d)
            return
        room = m.get_room(Position(r, c))
        for d in Direction:
            if room.doors[d] == DoorState.OPEN:
                dr, dc = DELTA[d]
                nr, nc = r + dr, c + dc
                if (0 <= nr < m.rows and 0 <= nc < m.cols
                        and (nr, nc) not in visited):
                    visited.add((nr, nc))
                    queue.append(((nr, nc), moves + [d]))


def test_full_winning_game():
    """P0-29: Simulate a complete winning run through the randomized maze.

    Iteratively finds and defeats each figure, then navigates to exit.
    """
    m = Maze()

    # Count total figures
    rooms = m.get_rooms()
    total_figures = sum(1 for r in rooms.values() if r.figure_name is not None)
    assert total_figures >= 3

    # Defeat all figures one at a time using the BFS-based helper
    for _ in range(total_figures):
        _navigate_to_trivia_room(m)
        room = m.get_room(m.get_player_position())
        assert room.figure_name is not None
        assert room.figure_name not in m.defeated_figures
        result = m.attempt_answer(CORRECT_KEY, correct_key=CORRECT_KEY)
        assert result == "correct"

    assert len(m.defeated_figures) == total_figures

    # Navigate to exit
    exit_pos = next(pos for pos, room in rooms.items() if room.is_exit)
    _bfs_navigate(m, exit_pos)

    assert m.get_game_status() == GameStatus.WON


def test_full_losing_game():
    """P0-30: Simulate a losing run — curse level hits 100."""
    m = Maze()
    _navigate_to_trivia_room(m)

    for _ in range(5):
        if m.get_game_status() != GameStatus.PLAYING:
            break
        m.attempt_answer(WRONG_KEY, correct_key=CORRECT_KEY)

    assert m.get_game_status() == GameStatus.LOST
    assert m.get_curse_level() >= 100


def test_attempt_answer_after_game_over():
    """P0-31: attempt_answer returns 'game_over' once game is no longer PLAYING."""
    m = Maze()
    _navigate_to_trivia_room(m)

    for _ in range(5):
        m.attempt_answer(WRONG_KEY, correct_key=CORRECT_KEY)

    assert m.get_game_status() == GameStatus.LOST
    wax_before = m.get_curse_level()
    result = m.attempt_answer(WRONG_KEY, correct_key=CORRECT_KEY)
    assert result == "game_over"
    assert m.get_curse_level() == wax_before


# ===========================================================================
# P1-6 to P1-7: Important (Should Pass)
# ===========================================================================

def test_dict_to_game_state_rejects_bad_data():
    """P1-6: Malformed dict raises ValueError or KeyError."""
    try:
        Engine.dict_to_game_state({"garbage": True})
        assert False, "Should have raised ValueError or KeyError"
    except (ValueError, KeyError):
        pass


def test_load_game_with_no_save_returns_false():
    """P1-7: Loading when no save exists returns False gracefully."""
    m = Maze()
    repo = Repository(db_path=TEST_DB)
    view = ViewStub()
    engine = Engine(m, repo, view, save_filepath="nonexistent_slot")
    success = engine.load_game()
    assert success is False
