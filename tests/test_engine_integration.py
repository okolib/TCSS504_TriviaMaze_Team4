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

# Ensure the tests directory is on the path for mock imports
sys.path.insert(0, os.path.dirname(__file__))

from mock_maze import (
    Maze, Position, Direction, GameStatus, GameState, DoorState,
)
from mock_db import Repository
from conftest import _get_wrong_key


# ===========================================================================
# Mock Engine — Translation Layer
#
# This stub implements Engine.game_state_to_dict and Engine.dict_to_game_state
# per the interface in docs/interfaces.md §3.3.
# When main.py is delivered, replace this with: from main import Engine
# ===========================================================================

class Engine:
    """Stub Engine with translation layer and save/load pipeline."""

    def __init__(self, maze, repo):
        self._maze = maze
        self._repo = repo

    @staticmethod
    def game_state_to_dict(state: GameState) -> dict:
        """Convert a GameState dataclass to a JSON-safe dict."""
        return {
            "player_position": {
                "row": state.player_position.row,
                "col": state.player_position.col,
            },
            "wax_meter": state.wax_meter,
            "game_status": state.game_status.value,
            "answered_figures": list(state.answered_figures),
            "visited_positions": [
                {"row": p.row, "col": p.col} for p in state.visited_positions
            ],
            "door_states": [
                {
                    "position": {"row": pos[0], "col": pos[1]},
                    "doors": {d.value: s.value for d, s in doors.items()},
                }
                for pos, doors in state.door_states.items()
            ],
        }

    @staticmethod
    def dict_to_game_state(data: dict) -> GameState:
        """Convert a JSON-safe dict back to a GameState dataclass.
        Raises ValueError if the dict is malformed."""
        try:
            pp = data["player_position"]
            player_position = Position(pp["row"], pp["col"])
            wax_meter = data["wax_meter"]
            game_status = GameStatus(data["game_status"])
            answered_figures = list(data["answered_figures"])
            visited_positions = [
                Position(v["row"], v["col"]) for v in data["visited_positions"]
            ]
            door_states = {}
            for entry in data["door_states"]:
                pos = (entry["position"]["row"], entry["position"]["col"])
                doors = {
                    Direction(dk): DoorState(dv)
                    for dk, dv in entry["doors"].items()
                }
                door_states[pos] = doors

            return GameState(
                player_position=player_position,
                wax_meter=wax_meter,
                game_status=game_status,
                answered_figures=answered_figures,
                visited_positions=visited_positions,
                door_states=door_states,
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Malformed game state dict: {e}") from e

    def save_game(self) -> None:
        """Get state from maze → convert to dict → pass to repo.save()."""
        state = self._maze.get_game_state()
        data = self.game_state_to_dict(state)
        self._repo.save(data, SAVE_FILE)

    def load_game(self) -> bool:
        """repo.load() → convert dict to GameState → maze.restore().
        Returns True if load succeeded, False otherwise."""
        data = self._repo.load(SAVE_FILE)
        if data is None:
            return False
        state = self.dict_to_game_state(data)
        self._maze.restore_game_state(state)
        return True


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
    engine = Engine(m, repo)

    # Play a move
    m.move(Direction.SOUTH)

    # Save
    engine.save_game()

    # Create a fresh maze + engine, load into it
    m2 = Maze()
    engine2 = Engine(m2, repo)
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
    engine = Engine(m, repo)
    success = engine.load_game()
    assert success is False
