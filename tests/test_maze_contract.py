"""
test_maze_contract.py — Domain Logic Contract Tests

Tests the Maze module against the MazeProtocol defined in docs/interfaces.md.
Updated for RFC-compliant code:
- Room uses figure_name/zone (not trivia)
- GameState uses curse_level/defeated_figures
- Generic door unlock
- attempt_answer(answer_key, correct_key)
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from maze import (
    Maze, Position, Direction, DoorState, GameStatus, GameState, TriviaQuestion,
)
from conftest import _navigate_to_trivia_room

# A known correct key to test with — Da Vinci's room
CORRECT_KEY = "B"
WRONG_KEY = "C"


# ===========================================================================
# P0-1 to P0-4: Construction & Layout
# ===========================================================================

def test_maze_creates_5x5_grid():
    """P0-1: Default maze has 25 rooms keyed by (row, col)."""
    m = Maze()
    rooms = m.get_rooms()
    assert len(rooms) == 25
    for r in range(5):
        for c in range(5):
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
    """P0-4: At least three rooms have wax figures."""
    m = Maze()
    rooms = m.get_rooms()
    figure_rooms = [r for r in rooms.values() if r.figure_name is not None]
    assert len(figure_rooms) >= 3


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
    room = m.get_room(m.get_player_position())
    open_dir = next(d for d, s in room.doors.items() if s == DoorState.OPEN)
    result = m.move(open_dir)
    assert result in ("moved", "staircase")
    assert m.get_player_position() != Position(0, 0)


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
    room = m.get_room(pos_before)
    wall_dirs = [d for d, s in room.doors.items() if s == DoorState.WALL]
    assert len(wall_dirs) > 0
    result = m.move(wall_dirs[0])
    assert result == "wall"
    assert m.get_player_position() == pos_before


def test_move_into_locked_door_rejected():
    """P0-9: Moving through a LOCKED door returns 'locked'; position unchanged."""
    m = Maze()
    _navigate_to_trivia_room(m)
    pos_before = m.get_player_position()
    room = m.get_room(pos_before)
    locked_dirs = [d for d, s in room.doors.items() if s == DoorState.LOCKED]
    assert len(locked_dirs) > 0, "Expected at least one LOCKED direction in figure room"
    result = m.move(locked_dirs[0])
    assert result == "locked"
    assert m.get_player_position() == pos_before


def test_move_into_border_wall_rejected():
    """P0-10: Moving into a border wall returns 'wall'; position unchanged."""
    m = Maze()
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
    assert room.figure_name is not None
    # Per RFC: Engine passes correct_key from DB
    result = m.attempt_answer(CORRECT_KEY, correct_key=CORRECT_KEY)
    assert result == "correct"


def test_correct_answer_does_not_increase_wax():
    """P0-12: Curse level stays the same after a correct answer."""
    m = Maze()
    _navigate_to_trivia_room(m)
    wax_before = m.get_curse_level()
    m.attempt_answer(CORRECT_KEY, correct_key=CORRECT_KEY)
    assert m.get_curse_level() == wax_before


# ===========================================================================
# P0-13 to P0-15: Trivia — Failure / Wax Meter
# ===========================================================================

def test_wrong_answer_increases_wax():
    """P0-13: Wrong answer increases curse level by 20."""
    m = Maze()
    _navigate_to_trivia_room(m)
    wax_before = m.get_curse_level()
    m.attempt_answer(WRONG_KEY, correct_key=CORRECT_KEY)
    assert m.get_curse_level() == wax_before + 20


def test_wrong_answer_keeps_door_locked():
    """P0-14: Door stays locked after a wrong answer."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room_before = m.get_room(m.get_player_position())
    locked_dirs = [d for d, s in room_before.doors.items()
                   if s == DoorState.LOCKED]
    m.attempt_answer(WRONG_KEY, correct_key=CORRECT_KEY)
    room_after = m.get_room(m.get_player_position())
    for d in locked_dirs:
        assert room_after.doors[d] == DoorState.LOCKED


def test_wax_meter_at_100_means_game_over():
    """P0-15: When curse level hits 100, game status becomes LOST."""
    m = Maze()
    _navigate_to_trivia_room(m)
    # Answer wrong 5 times (5 × 20 = 100)
    for _ in range(5):
        if m.get_game_status() != GameStatus.PLAYING:
            break
        m.attempt_answer(WRONG_KEY, correct_key=CORRECT_KEY)
    assert m.get_curse_level() >= 100
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
    assert state.curse_level == 0
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
    assert m2.get_curse_level() == state.curse_level
    assert m2.get_game_status() == state.game_status
    assert m2.get_game_state().door_states == state.door_states


def test_restore_preserves_unlocked_doors():
    """P0-18: After answering correctly, save and restore; unlocked door stays open."""
    m = Maze()
    _navigate_to_trivia_room(m)
    pos = m.get_player_position()
    room_before = m.get_room(pos)
    locked_dirs = [d for d, s in room_before.doors.items() if s == DoorState.LOCKED]
    assert len(locked_dirs) > 0, "Figure room should have a locked gate"
    assert m.attempt_answer(CORRECT_KEY, correct_key=CORRECT_KEY) == "correct"
    state = m.get_game_state()
    m2 = Maze()
    m2.restore_game_state(state)
    # All previously locked doors should now be OPEN in the restored maze
    room_after = m2.get_room(pos)
    for d in locked_dirs:
        assert room_after.doors[d] == DoorState.OPEN


# ===========================================================================
# P1-1 to P1-3: Important (Should Pass)
# ===========================================================================

def test_no_trivia_in_empty_room():
    """P1-1: attempt_answer in a room without a figure returns 'no_trivia'."""
    m = Maze()
    result = m.attempt_answer("A")
    assert result == "no_trivia"


def test_already_answered_trivia():
    """P1-2: Answering a cleared figure returns 'already_answered'."""
    m = Maze()
    _navigate_to_trivia_room(m)
    m.attempt_answer(CORRECT_KEY, correct_key=CORRECT_KEY)
    result = m.attempt_answer(CORRECT_KEY, correct_key=CORRECT_KEY)
    assert result == "already_answered"


def test_wax_meter_never_exceeds_100():
    """P1-3: Curse level is capped at 100."""
    m = Maze()
    _navigate_to_trivia_room(m)
    for _ in range(10):
        m.attempt_answer(WRONG_KEY, correct_key=CORRECT_KEY)
    assert m.get_curse_level() <= 100


# ===========================================================================
# RFC-specific tests
# ===========================================================================

def test_get_curse_level_method():
    """RFC: get_curse_level() exists and returns same as get_wax_meter()."""
    m = Maze()
    assert m.get_curse_level() == m.get_wax_meter() == 0


def test_room_has_figure_name_and_zone():
    """RFC: At least one room uses figure_name/zone."""
    m = Maze()
    rooms = m.get_rooms()
    figure_rooms = [r for r in rooms.values() if r.figure_name is not None]
    assert len(figure_rooms) >= 1
    room = figure_rooms[0]
    assert room.figure_name is not None
    assert room.zone is not None


def test_generic_door_unlock():
    """RFC: Correct answer unlocks ALL locked doors in the room generically."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    locked_before = [d for d, s in room.doors.items() if s == DoorState.LOCKED]
    assert len(locked_before) > 0
    m.attempt_answer(CORRECT_KEY, correct_key=CORRECT_KEY)
    room_after = m.get_room(m.get_player_position())
    for d in locked_before:
        assert room_after.doors[d] == DoorState.OPEN
