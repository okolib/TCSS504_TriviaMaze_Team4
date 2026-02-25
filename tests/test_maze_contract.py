"""
test_maze_contract.py — Domain Logic Contract Tests

Tests the Maze module against the MazeProtocol defined in docs/interfaces.md.
Covers all P0 (1–18) and P1 (1–3) maze-related tests from the RUNBOOK.

CURRENTLY IMPORTS FROM: mock_maze (stub)
TO SWITCH TO REAL MODULE: Replace 'from mock_maze import ...' with 'from maze import ...'
"""

import sys
import os

# Ensure the tests directory is on the path for mock imports
sys.path.insert(0, os.path.dirname(__file__))

from mock_maze import (
    Maze, Position, Direction, DoorState, GameStatus, GameState, TriviaQuestion,
)
from conftest import _navigate_to_trivia_room, _get_wrong_key


# ===========================================================================
# P0-1 to P0-4: Construction & Layout
# ===========================================================================

def test_maze_creates_3x3_grid():
    """P0-1: Maze has exactly 9 rooms keyed by (row, col)."""
    m = Maze(rows=3, cols=3)
    rooms = m.get_rooms()
    assert len(rooms) == 9
    for r in range(3):
        for c in range(3):
            assert (r, c) in rooms


def test_entrance_is_at_0_0():
    """P0-2: Room (0,0) is marked as the entrance."""
    m = Maze()
    room = m.get_room(Position(0, 0))
    assert room.is_entrance is True


def test_exit_exists():
    """P0-3: At least one room is marked as the exit."""
    m = Maze()
    rooms = m.get_rooms()
    exits = [r for r in rooms.values() if r.is_exit]
    assert len(exits) >= 1


def test_trivia_rooms_exist():
    """P0-4: At least two rooms contain trivia questions."""
    m = Maze()
    rooms = m.get_rooms()
    trivia_rooms = [r for r in rooms.values() if r.trivia is not None]
    assert len(trivia_rooms) >= 2


# ===========================================================================
# P0-5 to P0-7: Movement — Happy Path
# ===========================================================================

def test_player_starts_at_entrance():
    """P0-5: Player initial position is (0,0)."""
    m = Maze()
    assert m.get_player_position() == Position(0, 0)


def test_move_through_open_door():
    """P0-6: Moving through an OPEN door updates player position."""
    m = Maze()
    # (0,0) south door should be OPEN per skeleton layout
    result = m.move(Direction.SOUTH)
    assert result == "moved"
    assert m.get_player_position() == Position(1, 0)


def test_available_directions_excludes_walls():
    """P0-7: get_available_directions() never includes WALL directions."""
    m = Maze()
    room = m.get_room(m.get_player_position())
    available = m.get_available_directions()
    for d in available:
        assert room.doors[d] != DoorState.WALL


# ===========================================================================
# P0-8 to P0-10: Movement — Edge Cases
# ===========================================================================

def test_move_into_wall_rejected():
    """P0-8: Moving into a WALL returns 'wall' and position is unchanged."""
    m = Maze()
    pos_before = m.get_player_position()
    # (0,0) has NORTH and WEST as WALL per skeleton layout
    room = m.get_room(pos_before)
    wall_dirs = [d for d, s in room.doors.items() if s == DoorState.WALL]
    assert len(wall_dirs) > 0, "Expected at least one WALL direction at (0,0)"
    result = m.move(wall_dirs[0])
    assert result == "wall"
    assert m.get_player_position() == pos_before


def test_move_into_locked_door_rejected():
    """P0-9: Moving through a LOCKED door returns 'locked'; position unchanged."""
    m = Maze()
    # (1,0) has LOCKED east toward (1,1) — Da Vinci room
    m.move(Direction.SOUTH)  # (0,0) -> (1,0)
    pos_before = m.get_player_position()
    room = m.get_room(pos_before)
    locked_dirs = [d for d, s in room.doors.items() if s == DoorState.LOCKED]
    assert len(locked_dirs) > 0, "Expected at least one LOCKED direction at (1,0)"
    result = m.move(locked_dirs[0])
    assert result == "locked"
    assert m.get_player_position() == pos_before


def test_move_into_border_wall_rejected():
    """P0-10: Moving into a border wall returns 'wall'; position unchanged."""
    m = Maze()
    # Player starts at (0,0) — north is grid edge, represented as WALL
    result = m.move(Direction.NORTH)
    assert result == "wall"
    assert m.get_player_position() == Position(0, 0)


# ===========================================================================
# P0-11 to P0-12: Trivia — Happy Path
# ===========================================================================

def test_correct_answer_unlocks_door():
    """P0-11: Answering correctly returns 'correct' and unlocks the passage."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    assert room.trivia is not None
    result = m.attempt_answer(room.trivia.correct_key)
    assert result == "correct"


def test_correct_answer_does_not_increase_wax():
    """P0-12: Wax meter stays the same after a correct answer."""
    m = Maze()
    _navigate_to_trivia_room(m)
    wax_before = m.get_wax_meter()
    room = m.get_room(m.get_player_position())
    m.attempt_answer(room.trivia.correct_key)
    assert m.get_wax_meter() == wax_before


# ===========================================================================
# P0-13 to P0-15: Trivia — Failure / Wax Meter
# ===========================================================================

def test_wrong_answer_increases_wax():
    """P0-13: Wrong answer increases wax meter by 25."""
    m = Maze()
    _navigate_to_trivia_room(m)
    wax_before = m.get_wax_meter()
    room = m.get_room(m.get_player_position())
    wrong_key = _get_wrong_key(room.trivia.correct_key)
    m.attempt_answer(wrong_key)
    assert m.get_wax_meter() == wax_before + 25


def test_wrong_answer_keeps_door_locked():
    """P0-14: Door stays locked after a wrong answer."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room_before = m.get_room(m.get_player_position())
    locked_dirs = [d for d, s in room_before.doors.items()
                   if s == DoorState.LOCKED]
    wrong_key = _get_wrong_key(room_before.trivia.correct_key)
    m.attempt_answer(wrong_key)
    room_after = m.get_room(m.get_player_position())
    for d in locked_dirs:
        assert room_after.doors[d] == DoorState.LOCKED


def test_wax_meter_at_100_means_game_over():
    """P0-15: When wax meter hits 100, game status becomes LOST."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    wrong_key = _get_wrong_key(room.trivia.correct_key)
    # Answer wrong 4 times (4 × 25 = 100)
    for _ in range(4):
        if m.get_game_status() != GameStatus.PLAYING:
            break
        m.attempt_answer(wrong_key)
    assert m.get_wax_meter() >= 100
    assert m.get_game_status() == GameStatus.LOST


# ===========================================================================
# P0-16 to P0-18: Game State Snapshot
# ===========================================================================

def test_get_game_state_returns_dataclass():
    """P0-16: get_game_state() returns a GameState instance."""
    m = Maze()
    state = m.get_game_state()
    assert isinstance(state, GameState)
    assert state.player_position == Position(0, 0)
    assert state.wax_meter == 0
    assert state.game_status == GameStatus.PLAYING
    assert hasattr(state, "door_states") and isinstance(state.door_states, dict)


def test_restore_game_state_roundtrip():
    """P0-17: Saving and restoring state reproduces the same game."""
    m = Maze()
    m.move(Direction.SOUTH)
    state = m.get_game_state()
    m2 = Maze()
    m2.restore_game_state(state)
    assert m2.get_player_position() == state.player_position
    assert m2.get_wax_meter() == state.wax_meter
    assert m2.get_game_status() == state.game_status
    assert m2.get_game_state().door_states == state.door_states


def test_restore_preserves_unlocked_doors():
    """P0-18: After answering correctly, save and restore; unlocked door stays open."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    assert m.attempt_answer(room.trivia.correct_key) == "correct"
    state = m.get_game_state()
    m2 = Maze()
    m2.restore_game_state(state)
    # Bidirectional: both (1,0).EAST and (1,1).WEST must be OPEN after Da Vinci
    room_10_after = m2.get_room(Position(1, 0))
    room_11_after = m2.get_room(Position(1, 1))
    assert room_10_after.doors[Direction.EAST] == DoorState.OPEN
    assert room_11_after.doors[Direction.WEST] == DoorState.OPEN


# ===========================================================================
# P1-1 to P1-3: Important (Should Pass)
# ===========================================================================

def test_no_trivia_in_empty_room():
    """P1-1: attempt_answer in a room without trivia returns 'no_trivia'."""
    m = Maze()
    # (0,0) is the entrance — no trivia
    result = m.attempt_answer("A")
    assert result == "no_trivia"


def test_already_answered_trivia():
    """P1-2: Answering a cleared figure returns 'already_answered'."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    m.attempt_answer(room.trivia.correct_key)
    result = m.attempt_answer(room.trivia.correct_key)
    assert result == "already_answered"


def test_wax_meter_never_exceeds_100():
    """P1-3: Wax meter is capped at 100."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    wrong_key = _get_wrong_key(room.trivia.correct_key)
    for _ in range(10):
        m.attempt_answer(wrong_key)
    assert m.get_wax_meter() <= 100
