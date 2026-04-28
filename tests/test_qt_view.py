"""
test_qt_view.py — Qt View Module Contract Tests

Tests for qt_view.py (Mario — GUI/View Engineer).
Verifies QtView implements ViewProtocol per interfaces.md §3.4,
and that MazeCanvas accepts fog map data correctly.

Tests run headless: QApplication is created once per session.
Constraint: Must NOT import db.
"""

import ast
import inspect
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from maze import (
    Direction, DoorState, GameStatus, Position,
    Room, GameState, RoomVisibility, FogMapCell,
)

from qt_view import QtView, TriviaDialog
from maze_canvas import MazeCanvas, Theme


# ======================================================================
# QApplication singleton (required for any Qt widget test)
# ======================================================================

_app = QApplication.instance() or QApplication(sys.argv)


# ======================================================================
# Test Helpers
# ======================================================================

def _make_room(position=(0, 0), figure_name=None, zone=None,
               is_entrance=False, is_exit=False, doors=None):
    """Helper to build a Room for testing."""
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
    """Helper to build a GameState for testing."""
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


def _make_question_dict(figure="Leonardo da Vinci"):
    """Helper to build a question dict for testing."""
    return {
        "figure_name": figure,
        "question_text": "Who painted the Mona Lisa?",
        "choices": {"A": "Michelangelo", "B": "Leonardo da Vinci", "C": "Raphael"},
        "correct_key": "B",
    }


# ======================================================================
# §1 — Module Isolation Tests
# ======================================================================

class TestQtModuleIsolation:
    """Verify qt_view.py and maze_canvas.py respect dependency rules."""

    def test_qt_view_does_not_import_db(self):
        """qt_view.py must not import db."""
        import qt_view
        source = inspect.getsource(qt_view)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "db", "qt_view.py must not import db"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "db", "qt_view.py must not import from db"

    def test_maze_canvas_does_not_import_db(self):
        """maze_canvas.py must not import db."""
        import maze_canvas
        source = inspect.getsource(maze_canvas)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "db", "maze_canvas.py must not import db"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "db", "maze_canvas.py must not import from db"

    def test_maze_canvas_does_not_import_main(self):
        """maze_canvas.py must not import main."""
        import maze_canvas
        source = inspect.getsource(maze_canvas)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "main", "maze_canvas.py must not import main"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "main", "maze_canvas.py must not import from main"


# ======================================================================
# §2 — QtView Construction & Protocol Compliance
# ======================================================================

class TestQtViewConstruction:
    """Verify QtView can be constructed and satisfies ViewProtocol."""

    def test_qt_view_creates_successfully(self):
        """QtView() constructor works with no arguments."""
        v = QtView()
        assert v is not None

    def test_qt_view_has_all_protocol_methods(self):
        """QtView implements all 11 ViewProtocol methods."""
        v = QtView()
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
            assert hasattr(v, method_name), f"QtView missing method: {method_name}"
            assert callable(getattr(v, method_name)), f"{method_name} is not callable"

    def test_qt_view_has_command_signal(self):
        """QtView has a command_issued signal for event-driven communication."""
        v = QtView()
        assert hasattr(v, "command_issued")

    def test_qt_view_is_qmainwindow(self):
        """QtView inherits from QMainWindow."""
        from PySide6.QtWidgets import QMainWindow
        v = QtView()
        assert isinstance(v, QMainWindow)


# ======================================================================
# §3 — Display Methods (widget state verification)
# ======================================================================

class TestQtDisplayRoom:
    """Tests for display_room() — verifies sidebar widget updates."""

    def test_display_room_updates_label(self):
        """Room label updates to show current position."""
        v = QtView()
        room = _make_room(position=(2, 3))
        state = _make_game_state(player_pos=(2, 3))
        v.display_room(room, Position(2, 3), 0, state)
        assert "2" in v._room_label.text()
        assert "3" in v._room_label.text()

    def test_display_room_updates_curse_bar(self):
        """Curse meter progress bar updates to correct value."""
        v = QtView()
        room = _make_room()
        state = _make_game_state()
        v.display_room(room, Position(0, 0), 60, state)
        assert v._curse_bar.value() == 60

    def test_display_room_curse_zero_safe_message(self):
        """Curse level 0 shows the 'normal' dread message."""
        v = QtView()
        room = _make_room()
        state = _make_game_state()
        v.display_room(room, Position(0, 0), 0, state)
        assert "normal" in v._curse_message.text().lower()

    def test_display_room_curse_80_danger_message(self):
        """Curse level 80 shows danger dread message."""
        v = QtView()
        room = _make_room()
        state = _make_game_state()
        v.display_room(room, Position(0, 0), 80, state)
        text = v._curse_message.text().lower()
        assert "barely" in text or "legs" in text or "running out" in text

    def test_display_room_shows_entrance_text(self):
        """Entrance room shows themed entrance description."""
        v = QtView()
        room = _make_room(position=(0, 0), is_entrance=True)
        state = _make_game_state()
        v.display_room(room, Position(0, 0), 0, state)
        text = v._room_desc.text().lower()
        assert "entrance" in text or "moonlight" in text

    def test_display_room_shows_exit_text(self):
        """Exit room shows themed exit description."""
        v = QtView()
        room = _make_room(position=(4, 4), is_exit=True)
        state = _make_game_state(player_pos=(4, 4))
        v.display_room(room, Position(4, 4), 0, state)
        text = v._room_desc.text().lower()
        assert "exit" in text

    def test_display_room_shows_zone_flavor(self):
        """Art Gallery zone shows themed text when figure is undefeated."""
        v = QtView()
        room = _make_room(
            position=(1, 1), figure_name="Leonardo da Vinci",
            zone="Art Gallery"
        )
        state = _make_game_state(player_pos=(1, 1))
        v.display_room(room, Position(1, 1), 0, state)
        text = v._room_desc.text().lower()
        assert "easel" in text or "paint" in text or "canvas" in text

    def test_display_room_shows_doors_html(self):
        """Doors label shows open and locked doors."""
        v = QtView()
        room = _make_room(position=(1, 1), doors={
            Direction.NORTH: DoorState.WALL,
            Direction.SOUTH: DoorState.OPEN,
            Direction.EAST: DoorState.LOCKED,
            Direction.WEST: DoorState.OPEN,
        })
        state = _make_game_state(player_pos=(1, 1))
        v.display_room(room, Position(1, 1), 0, state)
        text = v._doors_label.text().lower()
        assert "south" in text
        assert "east" in text
        assert "locked" in text


class TestQtDisplayFogMap:
    """Tests for display_fog_map() — verifies canvas receives data."""

    def test_fog_map_updates_canvas(self):
        """display_fog_map stores data in MazeCanvas."""
        v = QtView()
        grid = _make_fog_grid()
        v.display_fog_map(grid)
        assert v._canvas._fog_map is not None
        assert len(v._canvas._fog_map) == 5
        assert len(v._canvas._fog_map[0]) == 5


class TestQtDisplayMoveResult:
    """Tests for display_move_result() — verifies game log output."""

    def test_move_success_logged(self):
        """Successful move is logged with direction."""
        v = QtView()
        v.display_move_result("moved", "north")
        text = v._game_log.toPlainText().lower()
        assert "north" in text

    def test_move_locked_logged(self):
        """Locked gate feedback is logged."""
        v = QtView()
        v.display_move_result("locked", "east")
        text = v._game_log.toPlainText().lower()
        assert "sealed" in text or "locked" in text or "gate" in text

    def test_move_wall_logged(self):
        """Wall collision feedback is logged."""
        v = QtView()
        v.display_move_result("wall", "west")
        text = v._game_log.toPlainText().lower()
        assert "no passage" in text or "stone" in text or "can't" in text


class TestQtDisplayAnswerResult:
    """Tests for display_answer_result()."""

    def test_correct_answer_logged(self):
        """Correct answer shows victory feedback in game log."""
        v = QtView()
        v.display_answer_result("correct", 0)
        text = v._game_log.toPlainText().lower()
        assert "defeated" in text or "✓" in v._game_log.toPlainText()

    def test_wrong_answer_logged(self):
        """Wrong answer shows failure feedback in game log."""
        v = QtView()
        v.display_answer_result("wrong", 40)
        text = v._game_log.toPlainText().lower()
        assert "wrong" in text or "✗" in v._game_log.toPlainText()

    def test_wrong_answer_updates_curse_bar(self):
        """Wrong answer updates the curse progress bar."""
        v = QtView()
        v.display_answer_result("wrong", 60)
        assert v._curse_bar.value() == 60

    def test_no_figure_logged(self):
        """No figure feedback is logged."""
        v = QtView()
        v.display_answer_result("no_figure", 0)
        text = v._game_log.toPlainText().lower()
        assert "no figure" in text

    def test_already_defeated_logged(self):
        """Already-defeated feedback is logged."""
        v = QtView()
        v.display_answer_result("already_answered", 0)
        text = v._game_log.toPlainText().lower()
        assert "already" in text or "defeated" in text


class TestQtDisplaySaveLoad:
    """Tests for display_save_result() and display_load_result()."""

    def test_save_success_logged(self):
        """Successful save is logged."""
        v = QtView()
        v.display_save_result(True)
        text = v._game_log.toPlainText().lower()
        assert "saved" in text or "save" in text

    def test_save_failure_logged(self):
        """Failed save shows error in game log."""
        v = QtView()
        v.display_save_result(False, "disk full")
        text = v._game_log.toPlainText().lower()
        assert "fail" in text or "disk full" in text

    def test_load_success_logged(self):
        """Successful load is logged."""
        v = QtView()
        v.display_load_result(True)
        text = v._game_log.toPlainText().lower()
        assert "loaded" in text or "load" in text

    def test_load_failure_logged(self):
        """Failed load shows feedback."""
        v = QtView()
        v.display_load_result(False)
        text = v._game_log.toPlainText().lower()
        assert "no saved" in text or "not found" in text


class TestQtDisplayError:
    """Tests for display_error()."""

    def test_error_logged(self):
        """Error message appears in game log."""
        v = QtView()
        v.display_error("Something broke")
        text = v._game_log.toPlainText().lower()
        assert "something broke" in text


class TestQtGetInput:
    """Tests for get_input() — in Qt mode this is a no-op."""

    def test_get_input_returns_empty(self):
        """get_input() returns empty string in Qt mode (non-blocking)."""
        v = QtView()
        result = v.get_input()
        assert result == ""

    def test_get_input_with_prompt_returns_empty(self):
        """get_input() with a prompt still returns empty in Qt mode."""
        v = QtView()
        result = v.get_input("custom prompt > ")
        assert result == ""


# ======================================================================
# §4 — Signal Wiring Tests
# ======================================================================

class TestCommandSignal:
    """Tests for the command_issued signal wiring."""

    def test_nav_button_signals(self):
        """Navigation buttons emit correct command strings."""
        v = QtView()
        received = []
        v.command_issued.connect(lambda cmd: received.append(cmd))

        v._btn_north.click()
        v._btn_south.click()
        v._btn_east.click()
        v._btn_west.click()

        assert "move north" in received
        assert "move south" in received
        assert "move east" in received
        assert "move west" in received

    def test_action_button_signals(self):
        """Save/Load/Map buttons emit correct command strings."""
        v = QtView()
        received = []
        v.command_issued.connect(lambda cmd: received.append(cmd))

        v._btn_save.click()
        v._btn_load.click()
        v._btn_map.click()

        assert "save" in received
        assert "load" in received
        assert "map" in received


# ======================================================================
# §5 — MazeCanvas Tests
# ======================================================================

class TestMazeCanvas:
    """Tests for MazeCanvas widget."""

    def test_canvas_creates_successfully(self):
        """MazeCanvas constructor works."""
        c = MazeCanvas()
        assert c is not None

    def test_canvas_accepts_fog_map(self):
        """update_map() stores the fog map data."""
        c = MazeCanvas()
        grid = _make_fog_grid()
        c.update_map(grid)
        assert c._fog_map is not None
        assert len(c._fog_map) == 5

    def test_canvas_null_map_no_crash(self):
        """Canvas does not crash with no map data set."""
        c = MazeCanvas()
        # Force a paint event with no data — should not raise
        c.update()
        assert c._fog_map is None

    def test_canvas_minimum_size(self):
        """Canvas has a reasonable minimum size."""
        c = MazeCanvas()
        assert c.minimumSize().width() >= 400
        assert c.minimumSize().height() >= 400


# ======================================================================
# §6 — TriviaDialog Tests
# ======================================================================

class TestTriviaDialog:
    """Tests for TriviaDialog."""

    def test_dialog_creates_with_question(self):
        """TriviaDialog constructor works with a question dict."""
        q = _make_question_dict()
        d = TriviaDialog(q)
        assert d is not None

    def test_dialog_has_answer_signal(self):
        """TriviaDialog has an answer_selected signal."""
        q = _make_question_dict()
        d = TriviaDialog(q)
        assert hasattr(d, "answer_selected")

    def test_dialog_has_choice_buttons(self):
        """TriviaDialog creates buttons for each choice."""
        q = _make_question_dict()
        d = TriviaDialog(q)
        from PySide6.QtWidgets import QPushButton
        buttons = d.findChildren(QPushButton)
        # Should have at least 3 answer buttons
        assert len(buttons) >= 3
