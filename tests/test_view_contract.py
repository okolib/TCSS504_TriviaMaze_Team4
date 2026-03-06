"""
test_view_contract.py — View Module Contract Tests

Tests for view.py (Role 4 — View Engineer).
Verifies ViewProtocol implementation per interfaces.md §3.4.

Constraint: Must NOT import db.
"""

import ast
import inspect
import sys
import os
from io import StringIO
from unittest.mock import patch
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from maze import (
    Direction, DoorState, GameStatus, Position,
    Room, GameState, TriviaQuestion,
)

from view import View, Colors

# Import RoomVisibility and FogMapCell from view.py, which has its own
# try/except stubs for when the maze team hasn't added them yet.
# This ensures we use the SAME enum instances that view.py uses.
from view import RoomVisibility, FogMapCell


# ======================================================================
# §1 — Module Isolation Tests
# ======================================================================

class TestModuleIsolation:
    """Verify view.py respects dependency rules."""

    def test_view_does_not_import_db(self):
        """Separation of concerns: view.py must not import db."""
        import view
        source = inspect.getsource(view)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "db", "view.py must not import db"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "db", "view.py must not import from db"

    def test_view_does_not_import_main(self):
        """view.py must not import main."""
        import view
        source = inspect.getsource(view)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "main", "view.py must not import main"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "main", "view.py must not import from main"


# ======================================================================
# §2 — View Construction
# ======================================================================

class TestViewConstruction:
    """Verify View can be constructed."""

    def test_view_creates_successfully(self):
        """View() constructor works with no arguments."""
        v = View()
        assert v is not None

    def test_view_has_all_protocol_methods(self):
        """View implements all ViewProtocol methods."""
        v = View()
        required_methods = [
            "display_welcome",
            "display_room",
            "display_fog_map",
            "display_move_result",
            "display_confrontation",
            "display_answer_result",
            "display_save_result",
            "display_load_result",
            "display_endgame",
            "display_error",
            "get_input",
        ]
        for method_name in required_methods:
            assert hasattr(v, method_name), f"View missing method: {method_name}"
            assert callable(getattr(v, method_name)), f"{method_name} is not callable"


# ======================================================================
# §3 — Display Methods (output capture)
# ======================================================================

def _make_room(position=(0, 0), figure_name=None, zone=None,
               is_entrance=False, is_exit=False,
               doors=None):
    """Helper to build a Room for testing.

    Uses RFC-compliant Room fields (figure_name, zone).
    """
    if doors is None:
        doors = {
            Direction.NORTH: DoorState.WALL,
            Direction.SOUTH: DoorState.OPEN,
            Direction.EAST: DoorState.OPEN,
            Direction.WEST: DoorState.WALL,
        }
    return Room(
        position=Position(*position),
        doors=doors,
        figure_name=figure_name,
        zone=zone,
        is_entrance=is_entrance,
        is_exit=is_exit,
    )


def _make_game_state(player_pos=(0, 0), curse_level=0,
                     status=GameStatus.PLAYING,
                     defeated_figures=None):
    """Helper to build a GameState for testing (RFC-compliant)."""
    if defeated_figures is None:
        defeated_figures = []
    return GameState(
        player_position=Position(*player_pos),
        curse_level=curse_level,
        game_status=status,
        defeated_figures=defeated_figures,
        visited_positions=[Position(*player_pos)],
        door_states={},
    )


def _make_fog_grid(rows=5, cols=5, player_pos=(0, 0)):
    """Helper to build a 5×5 FogMapCell grid for testing."""
    grid = []
    for r in range(rows):
        row = []
        for c in range(cols):
            pos = Position(r, c)
            if (r, c) == player_pos:
                vis = RoomVisibility.CURRENT
            elif abs(r - player_pos[0]) + abs(c - player_pos[1]) == 1:
                vis = RoomVisibility.VISIBLE
            else:
                vis = RoomVisibility.HIDDEN
            cell = FogMapCell(
                position=pos,
                visibility=vis,
                is_entrance=(r == 0 and c == 0),
                is_exit=(r == 4 and c == 4),
            )
            row.append(cell)
        grid.append(row)
    return grid


class TestDisplayWelcome:
    """Tests for display_welcome()."""

    def test_display_welcome_shows_title(self):
        """Welcome banner contains the game title."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_welcome()
            output = mock_out.getvalue()
        assert "WAXWORKS" in output
        assert "MIDNIGHT CURSE" in output

    def test_display_welcome_shows_commands(self):
        """Welcome banner lists available commands."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_welcome()
            output = mock_out.getvalue()
        assert "move" in output
        assert "answer" in output
        assert "save" in output
        assert "quit" in output

    def test_display_welcome_shows_narrative(self):
        """Welcome banner has immersive narrative text."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_welcome()
            output = mock_out.getvalue()
        assert "doors slam shut" in output.lower() or "grand hall" in output.lower()


class TestDisplayRoom:
    """Tests for display_room()."""

    def test_display_room_shows_position(self):
        """Room display includes the room coordinates."""
        v = View()
        room = _make_room(position=(1, 2))
        state = _make_game_state(player_pos=(1, 2))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(1, 2), 0, state)
            output = mock_out.getvalue()
        assert "1" in output and "2" in output

    def test_display_room_shows_entrance_text(self):
        """Entrance room has themed entrance text."""
        v = View()
        room = _make_room(position=(0, 0), is_entrance=True)
        state = _make_game_state()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(0, 0), 0, state)
            output = mock_out.getvalue()
        assert "entrance" in output.lower() or "moonlight" in output.lower()

    def test_display_room_shows_exit_text(self):
        """Exit room has themed exit text."""
        v = View()
        room = _make_room(position=(4, 4), is_exit=True)
        state = _make_game_state(player_pos=(4, 4))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(4, 4), 0, state)
            output = mock_out.getvalue()
        assert "exit" in output.lower()

    def test_display_room_shows_zone_flavor(self):
        """Room in Art Gallery zone shows themed text."""
        v = View()
        room = _make_room(
            position=(1, 1), figure_name="Leonardo da Vinci",
            zone="Art Gallery"
        )
        state = _make_game_state(player_pos=(1, 1))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(1, 1), 0, state)
            output = mock_out.getvalue()
        # Should show entrance text since figure is not defeated
        assert "easel" in output.lower() or "paint" in output.lower() or "canvas" in output.lower()

    def test_display_room_shows_doors(self):
        """Room display lists available doors."""
        v = View()
        room = _make_room(position=(1, 1), doors={
            Direction.NORTH: DoorState.WALL,
            Direction.SOUTH: DoorState.OPEN,
            Direction.EAST: DoorState.LOCKED,
            Direction.WEST: DoorState.OPEN,
        })
        state = _make_game_state(player_pos=(1, 1))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(1, 1), 0, state)
            output = mock_out.getvalue()
        assert "south" in output.lower()
        assert "east" in output.lower()
        assert "locked" in output.lower()

    def test_display_room_shows_curse_meter(self):
        """Room display includes the curse meter."""
        v = View()
        room = _make_room()
        state = _make_game_state()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(0, 0), 40, state)
            output = mock_out.getvalue()
        assert "curse" in output.lower() or "40" in output

    def test_display_room_corridor_shows_corridor_text(self):
        """A corridor room (no figure, no entrance/exit) shows corridor flavor."""
        v = View()
        room = _make_room(position=(0, 1))
        state = _make_game_state(player_pos=(0, 1))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(0, 1), 0, state)
            output = mock_out.getvalue()
        assert "hallway" in output.lower() or "shadow" in output.lower() or "echo" in output.lower()


class TestDisplayCurseMeter:
    """Tests for curse meter rendering."""

    def test_curse_at_zero_shows_safe_message(self):
        """Curse level 0 shows a 'normal' message."""
        v = View()
        room = _make_room()
        state = _make_game_state()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(0, 0), 0, state)
            output = mock_out.getvalue()
        assert "normal" in output.lower() or "fine" in output.lower()

    def test_curse_at_80_shows_danger_message(self):
        """Curse level 80 shows an urgent warning."""
        v = View()
        room = _make_room()
        state = _make_game_state()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_room(room, Position(0, 0), 80, state)
            output = mock_out.getvalue()
        assert "legs" in output.lower() or "running out" in output.lower() or "barely" in output.lower()


class TestDisplayFogMap:
    """Tests for display_fog_map()."""

    def test_fog_map_shows_current_room(self):
        """Player's current room is rendered distinctly (@)."""
        v = View()
        grid = _make_fog_grid(player_pos=(0, 0))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_fog_map(grid)
            output = mock_out.getvalue()
        assert "@" in output

    def test_fog_map_shows_hidden_rooms(self):
        """Hidden rooms are rendered with fog symbol (▓)."""
        v = View()
        grid = _make_fog_grid(player_pos=(0, 0))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_fog_map(grid)
            output = mock_out.getvalue()
        assert "▓" in output

    def test_fog_map_shows_title(self):
        """Fog map includes the map title."""
        v = View()
        grid = _make_fog_grid()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_fog_map(grid)
            output = mock_out.getvalue()
        assert "GRAND HALL" in output.upper() or "HISTORY" in output.upper()

    def test_fog_map_has_grid_borders(self):
        """Fog map has box-drawing borders."""
        v = View()
        grid = _make_fog_grid()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_fog_map(grid)
            output = mock_out.getvalue()
        assert "┌" in output
        assert "┘" in output

    def test_fog_map_shows_visible_rooms(self):
        """Visible (adjacent) rooms use a different symbol than hidden."""
        v = View()
        grid = _make_fog_grid(player_pos=(2, 2))
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_fog_map(grid)
            output = mock_out.getvalue()
        # Should have both visible markers and hidden markers
        assert "·" in output or "░" in output  # visible
        assert "▓" in output  # hidden


class TestDisplayMoveResult:
    """Tests for display_move_result()."""

    def test_move_success(self):
        """Successful move shows direction."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_move_result("moved", "north")
            output = mock_out.getvalue()
        assert "north" in output.lower()

    def test_move_wall(self):
        """Wall collision shows themed feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_move_result("wall", "east")
            output = mock_out.getvalue()
        assert "east" in output.lower()
        assert "no passage" in output.lower() or "stone" in output.lower() or "can't" in output.lower()

    def test_move_locked(self):
        """Locked gate shows themed feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_move_result("locked", "south")
            output = mock_out.getvalue()
        assert "sealed" in output.lower() or "locked" in output.lower() or "gate" in output.lower()


class TestDisplayConfrontation:
    """Tests for display_confrontation()."""

    def test_confrontation_shows_figure_name(self):
        """Confrontation displays the figure's name."""
        v = View()
        q = {
            "figure_name": "Leonardo da Vinci",
            "question_text": "Who painted the Mona Lisa?",
            "choices": {"A": "Michelangelo", "B": "Leonardo da Vinci", "C": "Raphael"},
            "correct_key": "B",
        }
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_confrontation(q)
            output = mock_out.getvalue()
        assert "LEONARDO DA VINCI" in output.upper()

    def test_confrontation_shows_question(self):
        """Confrontation displays the question text."""
        v = View()
        q = {
            "figure_name": "Cleopatra",
            "question_text": "What creature is associated with Cleopatra's death?",
            "choices": {"A": "Scorpion", "B": "Asp", "C": "Spider"},
            "correct_key": "B",
        }
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_confrontation(q)
            output = mock_out.getvalue()
        assert "creature" in output.lower() or "Cleopatra" in output

    def test_confrontation_shows_choices(self):
        """Confrontation displays all answer choices."""
        v = View()
        q = {
            "figure_name": "Lincoln",
            "question_text": "Who wrote the Gettysburg Address?",
            "choices": {"A": "Washington", "B": "Lincoln", "C": "Jefferson"},
            "correct_key": "B",
        }
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_confrontation(q)
            output = mock_out.getvalue()
        assert "A)" in output
        assert "B)" in output
        assert "C)" in output

    def test_confrontation_shows_box(self):
        """Confrontation is rendered in a box."""
        v = View()
        q = {
            "figure_name": "Test",
            "question_text": "Test question?",
            "choices": {"A": "One", "B": "Two", "C": "Three"},
            "correct_key": "A",
        }
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_confrontation(q)
            output = mock_out.getvalue()
        assert "+" in output and "|" in output

    def test_confrontation_has_stirring_narrative(self):
        """Confrontation includes 'A wax figure stirs' narrative."""
        v = View()
        q = {
            "figure_name": "Test Figure",
            "question_text": "Q?",
            "choices": {"A": "One", "B": "Two", "C": "Three"},
            "correct_key": "A",
        }
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_confrontation(q)
            output = mock_out.getvalue()
        assert "stirs" in output.lower()


class TestDisplayAnswerResult:
    """Tests for display_answer_result()."""

    def test_correct_answer_shows_success(self):
        """Correct answer shows victory feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_answer_result("correct", 0)
            output = mock_out.getvalue()
        assert "defeated" in output.lower() or "✓" in output

    def test_correct_answer_mentions_gate(self):
        """Correct answer mentions the gate opening."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_answer_result("correct", 0)
            output = mock_out.getvalue()
        assert "gate" in output.lower() or "open" in output.lower()

    def test_wrong_answer_shows_failure(self):
        """Wrong answer shows failure feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_answer_result("wrong", 40)
            output = mock_out.getvalue()
        assert "wrong" in output.lower() or "✗" in output

    def test_wrong_answer_shows_curse_level(self):
        """Wrong answer displays updated curse level."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_answer_result("wrong", 60)
            output = mock_out.getvalue()
        assert "60" in output

    def test_no_figure_feedback(self):
        """No figure in room gives appropriate feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_answer_result("no_figure", 0)
            output = mock_out.getvalue()
        assert "no figure" in output.lower() or "nothing" in output.lower()

    def test_already_answered_feedback(self):
        """Already-defeated figure gives appropriate feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_answer_result("already_answered", 0)
            output = mock_out.getvalue()
        assert "already" in output.lower() or "defeated" in output.lower()

    def test_game_over_feedback(self):
        """Game over state gives curse-complete feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_answer_result("game_over", 100)
            output = mock_out.getvalue()
        assert "curse" in output.lower() or "cannot" in output.lower()


class TestDisplaySaveLoad:
    """Tests for display_save_result() and display_load_result()."""

    def test_save_success(self):
        """Successful save shows confirmation."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_save_result(True)
            output = mock_out.getvalue()
        assert "saved" in output.lower() or "save" in output.lower()

    def test_save_failure(self):
        """Failed save shows error."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_save_result(False, "disk full")
            output = mock_out.getvalue()
        assert "fail" in output.lower() or "disk full" in output.lower()

    def test_load_success(self):
        """Successful load shows confirmation."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_load_result(True)
            output = mock_out.getvalue()
        assert "loaded" in output.lower() or "load" in output.lower()

    def test_load_failure(self):
        """Failed load shows feedback."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_load_result(False)
            output = mock_out.getvalue()
        assert "no saved" in output.lower() or "not found" in output.lower() or "fail" in output.lower()


class TestDisplayEndgame:
    """Tests for display_endgame()."""

    def test_victory_shows_curse_broken(self):
        """Victory screen shows 'curse is broken' text."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_endgame(GameStatus.WON, 40)
            output = mock_out.getvalue()
        assert "curse" in output.lower() and "broken" in output.lower()

    def test_victory_shows_dawn(self):
        """Victory screen mentions dawn."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_endgame(GameStatus.WON, 20)
            output = mock_out.getvalue()
        assert "dawn" in output.lower() or "free" in output.lower()

    def test_game_over_shows_museum_plaque(self):
        """Game over shows the 'NEWEST EXHIBIT' museum plaque."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_endgame(GameStatus.LOST, 100)
            output = mock_out.getvalue()
        assert "newest exhibit" in output.lower()

    def test_game_over_shows_transformation(self):
        """Game over shows the transformation sequence."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_endgame(GameStatus.LOST, 100)
            output = mock_out.getvalue()
        assert "skin" in output.lower() or "harden" in output.lower()

    def test_game_over_shows_game_over_text(self):
        """Game over shows GAME OVER banner."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_endgame(GameStatus.LOST, 100)
            output = mock_out.getvalue()
        assert "game over" in output.lower()


class TestDisplayError:
    """Tests for display_error()."""

    def test_error_shows_message(self):
        """Error displays the provided message."""
        v = View()
        with patch("sys.stdout", new_callable=StringIO) as mock_out:
            v.display_error("Something went wrong")
            output = mock_out.getvalue()
        assert "something went wrong" in output.lower()


class TestGetInput:
    """Tests for get_input()."""

    def test_get_input_returns_stripped_lowercase(self):
        """Input is stripped and lowercased."""
        v = View()
        with patch("builtins.input", return_value="  Move NORTH  "):
            result = v.get_input()
        assert result == "move north"

    def test_get_input_handles_eof(self):
        """EOF returns 'quit' gracefully."""
        v = View()
        with patch("builtins.input", side_effect=EOFError):
            with patch("sys.stdout", new_callable=StringIO):
                result = v.get_input()
        assert result == "quit"

    def test_get_input_handles_keyboard_interrupt(self):
        """Ctrl+C returns 'quit' gracefully."""
        v = View()
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with patch("sys.stdout", new_callable=StringIO):
                result = v.get_input()
        assert result == "quit"


class TestColorsDisable:
    """Tests for Colors.disable() (NO_COLOR support)."""

    def test_colors_disable_clears_codes(self):
        """After disable(), all color attributes are empty strings."""
        # Save originals
        originals = {}
        for attr in ["RESET", "DANGER", "SUCCESS", "WARNING", "INFO",
                      "DIM", "BOLD", "HIDDEN"]:
            originals[attr] = getattr(Colors, attr)

        Colors.disable()
        for attr in originals:
            assert getattr(Colors, attr) == "", f"Colors.{attr} should be empty after disable()"

        # Restore originals for other tests
        for attr, val in originals.items():
            setattr(Colors, attr, val)
