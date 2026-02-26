"""
test_engine_integration.py — Engine / Integration Tests

Tests the Engine translation layer and full save/load pipeline,
plus full game simulations (win/loss paths).

Covers all P0 (25–31) and P1 (6–7) engine tests from the RUNBOOK.

CURRENTLY IMPORTS FROM: mock_maze, mock_db (stubs)
TO SWITCH TO REAL MODULES:
    from mock_maze import ...  →  from maze import ...
    from mock_db import ...    →  from db import ...
    from mock_engine import Engine  →  from main import Engine
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
from conftest import _get_wrong_key


# ===========================================================================
# Test file paths and setup/teardown
# ===========================================================================

SAVE_FILE = "test_integration_save.json"


def setup_function():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)


def teardown_function():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)


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


def test_dict_to_game_state_roundtrip():
    """P0-27: Converting state → dict → state produces equivalent data."""
    m = Maze()
    m.move(Direction.SOUTH)
    original = m.get_game_state()
    d = Engine.game_state_to_dict(original)
    restored = Engine.dict_to_game_state(d)
    assert restored.player_position == original.player_position
    assert restored.wax_meter == original.wax_meter
    assert restored.game_status == original.game_status
    assert restored.answered_figures == original.answered_figures
    assert restored.door_states == original.door_states


# ===========================================================================
# P0-28: Save / Load Integration
# ===========================================================================

def test_save_and_load_game_roundtrip():
    """P0-28: Full roundtrip: maze → engine.save → file → engine.load → maze."""
    m = Maze()
    repo = Repository()
    engine = Engine(m, repo, save_file=SAVE_FILE)

    # Play a move
    m.move(Direction.SOUTH)

    # Save
    engine.save_game()

    # Create a fresh maze + engine, load into it
    m2 = Maze()
    engine2 = Engine(m2, repo, save_file=SAVE_FILE)
    success = engine2.load_game()
    assert success is True
    assert m2.get_player_position() == Position(1, 0)


# ===========================================================================
# P0-29 to P0-31: Full Game Simulation (Maze-Rule Validation)
# ===========================================================================

def test_full_winning_game():
    """P0-29: Simulate a complete winning run through the skeleton maze."""
    m = Maze()

    # Navigate to Da Vinci room (1,0) and answer correctly
    m.move(Direction.SOUTH)   # (0,0) → (1,0)
    room = m.get_room(m.get_player_position())
    assert m.attempt_answer(room.trivia.correct_key) == "correct"

    # Navigate to Cleopatra room (2,1) and answer correctly
    m.move(Direction.EAST)    # (1,0) → (1,1)
    m.move(Direction.SOUTH)   # (1,1) → (2,1)
    room = m.get_room(m.get_player_position())
    assert m.attempt_answer(room.trivia.correct_key) == "correct"

    # Move to exit (2,2)
    m.move(Direction.EAST)    # (2,1) → (2,2)

    assert m.get_game_status() == GameStatus.WON


def test_full_losing_game():
    """P0-30: Simulate a losing run — wax meter hits 100."""
    m = Maze()

    # Navigate to Da Vinci room (1,0)
    m.move(Direction.SOUTH)   # (0,0) → (1,0)

    room = m.get_room(m.get_player_position())
    wrong = _get_wrong_key(room.trivia.correct_key)

    # Answer wrong 4 times
    for _ in range(4):
        m.attempt_answer(wrong)

    assert m.get_game_status() == GameStatus.LOST
    assert m.get_wax_meter() >= 100


def test_attempt_answer_after_game_over():
    """P0-31: attempt_answer returns 'game_over' once game is no longer PLAYING."""
    m = Maze()

    # Navigate to Da Vinci room and lose
    m.move(Direction.SOUTH)
    room = m.get_room(m.get_player_position())
    wrong = _get_wrong_key(room.trivia.correct_key)
    for _ in range(4):
        m.attempt_answer(wrong)

    assert m.get_game_status() == GameStatus.LOST
    wax_before = m.get_wax_meter()
    result = m.attempt_answer(wrong)
    assert result == "game_over"
    assert m.get_wax_meter() == wax_before  # no state change


# ===========================================================================
# P1-6 to P1-7: Important (Should Pass)
# ===========================================================================

def test_dict_to_game_state_rejects_bad_data():
    """P1-6: Malformed dict raises ValueError."""
    try:
        Engine.dict_to_game_state({"garbage": True})
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_load_game_with_no_save_returns_false():
    """P1-7: Loading when no save file exists returns False gracefully."""
    m = Maze()
    repo = Repository()
    engine = Engine(m, repo, save_file=SAVE_FILE)
    success = engine.load_game()
    assert success is False
