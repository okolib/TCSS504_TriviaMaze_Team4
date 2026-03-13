"""Waxworks: The Midnight Curse — Qt View Module

PySide6 GUI implementation of ViewProtocol (interfaces.md §3.4).
Replaces the CLI View with a full graphical interface:
  - Maze canvas with fog-of-war
  - Sidebar with curse meter, room info, and navigation buttons
  - Trivia confrontation dialog
  - Game log panel

Imports maze types only — never imports db.
"""

import sys
import textwrap

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QDialog, QDialogButtonBox,
    QGridLayout, QProgressBar, QGroupBox, QMessageBox, QMenuBar,
    QSplitter, QFrame, QSizePolicy, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QAction, QIcon

from maze import (
    Direction, DoorState, GameStatus,
    Position, Room, GameState,
)

# Try importing from maze, fall back to stubs
try:
    from maze import RoomVisibility, FogMapCell
except ImportError:
    from view import RoomVisibility, FogMapCell

from maze_canvas import MazeCanvas
from first_person_canvas import FirstPersonCanvas


# ======================================================================
# Style Constants
# ======================================================================

WINDOW_STYLE = """
QMainWindow {
    background-color: #120c1c;
}
QWidget {
    color: #dcd2f0;
    font-family: 'Courier New', 'Menlo';
}
QLabel {
    color: #dcd2f0;
}
QGroupBox {
    border: 1px solid #5a3d8a;
    border-radius: 6px;
    margin-top: 8px;
    padding: 12px 8px 8px 8px;
    font-weight: bold;
    color: #b8a0d8;
}
QGroupBox::title {
    subcontrol-position: top left;
    padding: 2px 8px;
    color: #e6b832;
}
QPushButton {
    background-color: #2d233c;
    border: 1px solid #5a3d8a;
    border-radius: 4px;
    padding: 8px 16px;
    color: #dcd2f0;
    font-weight: bold;
    min-width: 60px;
}
QPushButton:hover {
    background-color: #3d2f52;
    border-color: #8a6cc0;
}
QPushButton:pressed {
    background-color: #553d7a;
}
QPushButton:disabled {
    background-color: #1a1228;
    color: #5a4a70;
    border-color: #2d233c;
}
QTextEdit {
    background-color: #1a1228;
    border: 1px solid #3d2f52;
    border-radius: 4px;
    color: #b8a0d8;
    padding: 6px;
    font-size: 12px;
}
QProgressBar {
    background-color: #1a1228;
    border: 1px solid #3d2f52;
    border-radius: 4px;
    text-align: center;
    color: #dcd2f0;
    height: 22px;
}
QProgressBar::chunk {
    border-radius: 3px;
}
QMenuBar {
    background-color: #120c1c;
    color: #b8a0d8;
    border-bottom: 1px solid #3d2f52;
}
QMenuBar::item:selected {
    background-color: #2d233c;
}
QMenu {
    background-color: #1a1228;
    color: #dcd2f0;
    border: 1px solid #3d2f52;
}
QMenu::item:selected {
    background-color: #3d2f52;
}
"""

CURSE_COLORS = {
    "low": "#64c882",       # Green — safe
    "medium": "#e6b832",    # Gold — warning
    "high": "#e65050",      # Red — danger
}


# ======================================================================
# Trivia Dialog
# ======================================================================

class TriviaDialog(QDialog):
    """Modal dialog for wax figure confrontations."""

    answer_selected = Signal(str)  # Emits "A", "B", or "C"

    def __init__(self, question_dict: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🗿 Wax Figure Confrontation")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1228;
                border: 2px solid #e6b832;
                border-radius: 8px;
            }
            QLabel {
                color: #dcd2f0;
            }
            QPushButton {
                background-color: #2d233c;
                border: 1px solid #5a3d8a;
                border-radius: 6px;
                padding: 10px 20px;
                color: #dcd2f0;
                font-weight: bold;
                font-size: 13px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #553d7a;
                border-color: #e6b832;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        figure = question_dict.get("figure_name", "Unknown Figure")
        question = question_dict.get("question_text", "")
        choices = question_dict.get("choices", {})

        # Header
        header = QLabel("A wax figure stirs...")
        header.setFont(QFont("Courier New", 11))
        header.setStyleSheet("color: #88c8e8;")
        layout.addWidget(header)

        # Figure name
        name_label = QLabel(f"The eyes of {figure.upper()} snap open.")
        name_label.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #e6b832;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Flavor text
        desc = QLabel("Wax cracks along the jaw as it confronts you:")
        desc.setFont(QFont("Courier New", 10))
        desc.setStyleSheet("color: #786890;")
        layout.addWidget(desc)

        # Question
        q_label = QLabel(f'"{question}"')
        q_label.setFont(QFont("Courier New", 12))
        q_label.setStyleSheet("color: #88c8e8;")
        q_label.setWordWrap(True)
        layout.addWidget(q_label)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3d2f52;")
        layout.addWidget(line)

        # Answer buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        if isinstance(choices, dict):
            for key, text in choices.items():
                btn = QPushButton(f"  {key})  {text}")
                btn.clicked.connect(lambda checked, k=key: self._select(k))
                btn_layout.addWidget(btn)
        elif isinstance(choices, list):
            for i, choice in enumerate(choices):
                key = choice.get("key", chr(65 + i))
                text = choice.get("text", str(choice))
                btn = QPushButton(f"  {key})  {text}")
                btn.clicked.connect(lambda checked, k=key: self._select(k))
                btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)

    def _select(self, key: str):
        """Handle answer button click."""
        self.answer_selected.emit(key.upper())
        self.accept()


# ======================================================================
# Qt View — Implements ViewProtocol
# ======================================================================

class QtView(QMainWindow):
    """PySide6 GUI for Waxworks: The Midnight Curse.

    Implements ViewProtocol from interfaces.md §3.4.
    The Engine calls these methods to update the display.
    """

    # Signals for communicating back to Engine
    command_issued = Signal(str)  # "move north", "answer A", "save", etc.

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🕯 Waxworks: The Midnight Curse")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(WINDOW_STYLE)

        self._pending_input_callback = None  # For get_input() async bridge
        self._current_question = None        # Currently displayed question dict
        self._in_confrontation = False       # Prevents dialog reentrancy
        self._view_mode = "first_person"     # "top_down" or "first_person"
        self._player_facing = Direction.SOUTH  # Track last move direction
        self._setup_ui()
        self._setup_menu()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the main window layout."""
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # --- Left side: Maze Canvas ---
        left_panel = QVBoxLayout()

        # Title bar with view toggle
        title_bar = QHBoxLayout()
        title = QLabel("WAXWORKS: THE MIDNIGHT CURSE")
        title.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #e6b832; padding: 4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_bar.addWidget(title, stretch=1)

        self._btn_toggle_view = QPushButton("🗺 Top-Down")
        self._btn_toggle_view.setMaximumWidth(130)
        self._btn_toggle_view.clicked.connect(self._toggle_view)
        title_bar.addWidget(self._btn_toggle_view)
        left_panel.addLayout(title_bar)

        # Stacked canvas: first-person (default) + top-down
        self._canvas_stack = QStackedWidget()

        self._fp_canvas = FirstPersonCanvas()
        self._fp_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas_stack.addWidget(self._fp_canvas)  # index 0

        self._canvas = MazeCanvas()
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas_stack.addWidget(self._canvas)  # index 1

        self._canvas_stack.setCurrentIndex(0)  # Start with first-person
        left_panel.addWidget(self._canvas_stack, stretch=1)

        main_layout.addLayout(left_panel, stretch=3)

        # --- Right side: Sidebar ---
        sidebar = QVBoxLayout()
        sidebar.setSpacing(10)

        # Room info group
        room_group = QGroupBox("📍 Current Room")
        room_layout = QVBoxLayout(room_group)
        self._room_label = QLabel("Room (0, 0)")
        self._room_label.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        self._room_desc = QLabel("The museum awaits...")
        self._room_desc.setWordWrap(True)
        self._room_desc.setFont(QFont("Courier New", 10))
        self._room_desc.setStyleSheet("color: #88c8e8;")
        room_layout.addWidget(self._room_label)
        room_layout.addWidget(self._room_desc)
        sidebar.addWidget(room_group)

        # Curse meter group
        curse_group = QGroupBox("🕯 Curse Level")
        curse_layout = QVBoxLayout(curse_group)
        self._curse_bar = QProgressBar()
        self._curse_bar.setRange(0, 100)
        self._curse_bar.setValue(0)
        self._curse_bar.setFormat("%v%")
        self._update_curse_style(0)
        self._curse_message = QLabel("You feel normal. For now.")
        self._curse_message.setFont(QFont("Courier New", 9))
        self._curse_message.setStyleSheet("color: #786890;")
        self._curse_message.setWordWrap(True)
        curse_layout.addWidget(self._curse_bar)
        curse_layout.addWidget(self._curse_message)
        sidebar.addWidget(curse_group)

        # Doors info
        doors_group = QGroupBox("🚪 Doors")
        doors_layout = QVBoxLayout(doors_group)
        self._doors_label = QLabel("...")
        self._doors_label.setWordWrap(True)
        self._doors_label.setFont(QFont("Courier New", 10))
        doors_layout.addWidget(self._doors_label)
        sidebar.addWidget(doors_group)

        # Navigation buttons
        nav_group = QGroupBox("🧭 Navigation")
        nav_grid = QGridLayout(nav_group)

        self._btn_north = QPushButton("⬆ North")
        self._btn_south = QPushButton("⬇ South")
        self._btn_east = QPushButton("East ➡")
        self._btn_west = QPushButton("⬅ West")

        self._btn_north.clicked.connect(lambda: self._issue_command("move north"))
        self._btn_south.clicked.connect(lambda: self._issue_command("move south"))
        self._btn_east.clicked.connect(lambda: self._issue_command("move east"))
        self._btn_west.clicked.connect(lambda: self._issue_command("move west"))

        nav_grid.addWidget(self._btn_north, 0, 1)
        nav_grid.addWidget(self._btn_west, 1, 0)
        nav_grid.addWidget(self._btn_east, 1, 2)
        nav_grid.addWidget(self._btn_south, 2, 1)
        sidebar.addWidget(nav_group)

        # Action buttons
        action_group = QGroupBox("⚡ Actions")
        action_layout = QHBoxLayout(action_group)
        self._btn_save = QPushButton("💾 Save")
        self._btn_load = QPushButton("📂 Load")
        self._btn_map = QPushButton("🗺 Map")

        self._btn_save.clicked.connect(lambda: self._issue_command("save"))
        self._btn_load.clicked.connect(lambda: self._issue_command("load"))
        self._btn_map.clicked.connect(lambda: self._issue_command("map"))

        action_layout.addWidget(self._btn_save)
        action_layout.addWidget(self._btn_load)
        action_layout.addWidget(self._btn_map)
        sidebar.addWidget(action_group)

        # Game log
        log_group = QGroupBox("📜 Game Log")
        log_layout = QVBoxLayout(log_group)
        self._game_log = QTextEdit()
        self._game_log.setReadOnly(True)
        self._game_log.setMaximumHeight(180)
        self._game_log.setFont(QFont("Courier New", 10))
        log_layout.addWidget(self._game_log)
        sidebar.addWidget(log_group)

        sidebar.addStretch()
        main_layout.addLayout(sidebar, stretch=1)

    def _setup_menu(self):
        """Build the menu bar."""
        menu_bar = self.menuBar()

        game_menu = menu_bar.addMenu("&Game")

        new_action = QAction("&New Game", self)
        new_action.triggered.connect(lambda: self._issue_command("new"))
        game_menu.addAction(new_action)

        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(lambda: self._issue_command("save"))
        game_menu.addAction(save_action)

        load_action = QAction("&Load", self)
        load_action.setShortcut("Ctrl+L")
        load_action.triggered.connect(lambda: self._issue_command("load"))
        game_menu.addAction(load_action)

        game_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(lambda: self._issue_command("quit"))
        game_menu.addAction(quit_action)

    # ------------------------------------------------------------------
    # ViewProtocol Implementation
    # ------------------------------------------------------------------

    def display_welcome(self) -> None:
        """Show the themed welcome banner."""
        self._log(
            "<b style='color:#e6b832;'>═══════════════════════════════════════</b><br>"
            "<b style='color:#e6b832;'>  WAXWORKS: THE MIDNIGHT CURSE</b><br>"
            "<b style='color:#e6b832;'>═══════════════════════════════════════</b><br>"
            "<span style='color:#88c8e8;'>The doors slam shut behind you.<br>"
            "The Grand Hall of History stretches into darkness.<br>"
            "Your hand... is it shinier than before?</span><br><br>"
            "<span style='color:#786890;'>Find the exit before the Curse Meter "
            "reaches 100%<br>or become the newest exhibit — forever.</span>"
        )

    def display_room(self, room: Room, position: Position,
                     curse_level: int, game_state: GameState) -> None:
        """Display the current room description with zone flavor text."""
        # Update room label
        self._room_label.setText(f"Room ({position.row}, {position.col})")

        # Build description
        desc_parts = []
        if room.is_entrance:
            desc_parts.append("🌙 The Entrance — moonlight spills in behind you.")
        elif room.is_exit:
            desc_parts.append("✨ You see the Exit ahead!")

        # Zone flavor text
        zone = getattr(room, "zone", None)
        figure_name = getattr(room, "figure_name", None)
        defeated = getattr(game_state, "defeated_figures",
                           getattr(game_state, "answered_figures", []))

        if figure_name is None and hasattr(room, "trivia") and room.trivia is not None:
            figure_name = room.trivia.figure_name
            zone = getattr(room.trivia, "zone", None)

        ZONE_TEXT = {
            "Art Gallery": {
                "entrance": "Paint-stained easels line the walls. A figure hunches over a canvas...",
                "ambient": "The Mona Lisa's eyes seem to follow you.",
            },
            "American History": {
                "entrance": "A tall figure in a stovepipe hat stands behind a podium...",
                "ambient": "A brass eagle gleams on the wall.",
            },
            "Ancient History": {
                "entrance": "Sand crunches under your feet. A queen sits on a gilded throne...",
                "ambient": "The faint hiss of a serpent echoes from the shadows.",
            },
        }

        if zone and zone in ZONE_TEXT:
            zone_info = ZONE_TEXT[zone]
            if figure_name and figure_name not in defeated:
                desc_parts.append(f"🗿 {zone_info['entrance']}")
            else:
                desc_parts.append(zone_info["ambient"])
        elif not room.is_entrance and not room.is_exit:
            desc_parts.append("The hallway stretches into shadow. "
                              "Your footsteps echo off cold marble.")

        self._room_desc.setText("\n".join(desc_parts))

        # Update curse meter
        self._curse_bar.setValue(curse_level)
        self._update_curse_style(curse_level)

        # Update dread message
        DREAD_MESSAGES = {
            0:   "You feel normal. For now.",
            20:  "Your fingers feel stiff and waxy.",
            40:  "Your arm won't bend. The curse is spreading.",
            60:  "Your joints are seizing. The curse tightens its grip.",
            80:  "You can barely move your legs. Time is running out.",
            100: "Your eyes glaze over. You cannot move. The curse is complete.",
        }
        level_key = min((curse_level // 20) * 20, 100)
        self._curse_message.setText(DREAD_MESSAGES.get(level_key, ""))

        # Update doors display
        door_strs = []
        for d in Direction:
            state = room.doors[d]
            if state == DoorState.OPEN:
                door_strs.append(f"<span style='color:#64c882;'>{d.value} (open)</span>")
            elif state == DoorState.LOCKED:
                door_strs.append(f"<span style='color:#e6b832;'>🔒 {d.value} (locked)</span>")
        self._doors_label.setText("<br>".join(door_strs) if door_strs else
                                  "<span style='color:#786890;'>No passages</span>")

    def display_fog_map(self, fog_map: list) -> None:
        """Render the fog-of-war map on both canvases."""
        self._canvas.update_map(fog_map)
        self._fp_canvas.update_map(fog_map)
        self._fp_canvas.set_facing(self._player_facing)

    def display_move_result(self, result: str, direction: str) -> None:
        """Display the result of a move attempt."""
        # Track facing direction for first-person view
        dir_map = {
            "north": Direction.NORTH, "south": Direction.SOUTH,
            "east": Direction.EAST, "west": Direction.WEST,
            "n": Direction.NORTH, "s": Direction.SOUTH,
            "e": Direction.EAST, "w": Direction.WEST,
        }
        if direction.lower() in dir_map and result in ("moved", "staircase"):
            self._player_facing = dir_map[direction.lower()]

        if result == "moved":
            self._log(f"<span style='color:#64c882;'>You move {direction}.</span>")
        elif result == "staircase":
            if direction in ("south", "s"):
                self._log(
                    "<span style='color:#88c8e8;'>You descend a winding staircase...</span><br>"
                    "<span style='color:#786890;'>The air grows colder as you step into a new wing.</span>"
                )
            else:
                self._log(
                    "<span style='color:#88c8e8;'>You climb back up the stairs...</span><br>"
                    "<span style='color:#786890;'>Familiar hallways stretch before you.</span>"
                )
        elif result == "locked":
            self._log(
                f"<span style='color:#e6b832;'>🔒 The gate to the {direction} is sealed. "
                "A wax figure guards the way.</span>"
            )
        elif result == "wall":
            self._log(
                f"<span style='color:#786890;'>There is no passage to the {direction}. "
                "Only cold stone.</span>"
            )
        else:
            self._log("<span style='color:#786890;'>You can't go that way.</span>")

    def display_confrontation(self, question_dict: dict) -> None:
        """Display a wax figure confrontation with the trivia question."""
        # Guard against reentrancy: if we're already showing a dialog, skip
        if self._in_confrontation:
            return

        self._current_question = question_dict
        self._in_confrontation = True
        figure = question_dict.get("figure_name", "Unknown")

        self._log(
            f"<b style='color:#e65050;'>🗿 A wax figure stirs...</b><br>"
            f"<b style='color:#e6b832;'>The eyes of {figure.upper()} snap open.</b>"
        )

        # Show the trivia dialog (modal — blocks until answered)
        dialog = TriviaDialog(question_dict, parent=self)
        dialog.answer_selected.connect(self._on_trivia_answer)
        dialog.exec()
        self._in_confrontation = False

    def display_answer_result(self, result: str, curse_level: int) -> None:
        """Display the result of answering a question."""
        if result == "correct":
            self._log(
                "<span style='color:#64c882;'>✓ The figure is defeated!</span><br>"
                "<span style='color:#64c882;'>The curse recedes. The gate grinds open.</span><br>"
                "<span style='color:#786890;'>The figure nods slowly and returns to stillness.</span>"
            )
        elif result == "wrong":
            self._log(
                "<span style='color:#e65050;'>✗ Wrong!</span><br>"
                "<span style='color:#e6b832;'>The curse tightens its grip... "
                "you feel your fingers stiffening.</span><br>"
                "<span style='color:#786890;'>A grinding of stone. The gate stays sealed.</span>"
            )
            self._curse_bar.setValue(curse_level)
            self._update_curse_style(curse_level)
        elif result == "no_figure":
            self._log("<span style='color:#786890;'>There is no figure to confront here.</span>")
        elif result == "already_answered":
            self._log("<span style='color:#786890;'>This figure has already been defeated.</span>")
        elif result == "game_over":
            self._log("<span style='color:#e65050;'>The curse is complete. You cannot move.</span>")

    def display_save_result(self, success: bool, error: str = "") -> None:
        """Display save confirmation or error."""
        if success:
            self._log("<span style='color:#64c882;'>💾 Game saved.</span>")
        else:
            msg = f" ({error})" if error else ""
            self._log(f"<span style='color:#e65050;'>Save failed{msg}.</span>")

    def display_load_result(self, success: bool) -> None:
        """Display load confirmation or failure."""
        if success:
            self._log(
                "<span style='color:#64c882;'>📂 Game loaded. "
                "The museum shifts around you...</span>"
            )
        else:
            self._log("<span style='color:#e6b832;'>No saved game found.</span>")

    def display_endgame(self, status: GameStatus, curse_level: int,
                        rooms_explored: int = 0, total_rooms: int = 25,
                        figures_defeated: int = 0, total_figures: int = 3) -> None:
        """Display victory or game-over sequence."""
        if status == GameStatus.WON:
            self._show_endgame_dialog(
                title="🌅 THE CURSE IS BROKEN",
                message=(
                    "The last gate opens...\n\n"
                    "Warm orange light floods the hallway.\n"
                    "The wax on your skin cracks and falls away.\n"
                    "Behind you, the figures slump — lifeless once more.\n\n"
                    "Dawn breaks over the museum.\n"
                    "You are free."
                ),
                stats=f"Rooms: {rooms_explored}/{total_rooms}  |  "
                      f"Figures: {figures_defeated}/{total_figures}  |  "
                      f"Curse: {curse_level}",
                color="#64c882",
            )
        elif status == GameStatus.LOST:
            self._show_endgame_dialog(
                title="💀 GAME OVER",
                message=(
                    "Your skin hardens...\n"
                    "Your joints lock...\n"
                    "Your eyes glaze over...\n\n"
                    '"THE NEWEST EXHIBIT"\n\n'
                    "Name:  Unknown Explorer\n"
                    "Date:  The Midnight Hour\n"
                    "Cause: Curiosity\n\n"
                    "PERMANENT COLLECTION"
                ),
                stats=f"Rooms: {rooms_explored}/{total_rooms}  |  "
                      f"Figures: {figures_defeated}/{total_figures}  |  "
                      f"Curse: {curse_level}",
                color="#e65050",
            )

    def display_error(self, message: str) -> None:
        """Display an error message."""
        self._log(f"<span style='color:#e65050;'>⚠ {message}</span>")

    def get_input(self, prompt: str = "") -> str:
        """In Qt mode, input comes from buttons/signals, not blocking input().

        This method is part of ViewProtocol but in the GUI, commands arrive
        via the command_issued signal. This returns empty string immediately;
        real input flows through _issue_command → command_issued signal.
        """
        # In callback-driven mode, this is a no-op.
        # The Engine will be refactored to use callbacks instead of polling.
        return ""

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _log(self, html: str) -> None:
        """Append HTML content to the game log."""
        self._game_log.append(html)
        # Auto-scroll to bottom
        scrollbar = self._game_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _issue_command(self, command: str) -> None:
        """Emit a command to the Engine."""
        self.command_issued.emit(command)

    def _on_trivia_answer(self, key: str) -> None:
        """Handle trivia answer from dialog."""
        self._issue_command(f"answer {key}")

    def _toggle_view(self) -> None:
        """Switch between first-person and top-down views."""
        if self._canvas_stack.currentIndex() == 0:
            # Switch to top-down
            self._canvas_stack.setCurrentIndex(1)
            self._btn_toggle_view.setText("👁 First-Person")
            self._view_mode = "top_down"
        else:
            # Switch to first-person
            self._canvas_stack.setCurrentIndex(0)
            self._btn_toggle_view.setText("🗺 Top-Down")
            self._view_mode = "first_person"

    def _update_curse_style(self, level: int) -> None:
        """Update the curse progress bar color based on level."""
        if level >= 80:
            color = CURSE_COLORS["high"]
        elif level >= 40:
            color = CURSE_COLORS["medium"]
        else:
            color = CURSE_COLORS["low"]

        self._curse_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
        )

    def _show_endgame_dialog(self, title: str, message: str,
                             stats: str, color: str) -> None:
        """Show a styled endgame dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: #1a1228;
                border: 2px solid {color};
            }}
            QLabel {{
                color: #dcd2f0;
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title_label = QLabel(title)
        title_label.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color};")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        msg_label = QLabel(message)
        msg_label.setFont(QFont("Courier New", 11))
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg_label)

        stats_label = QLabel(stats)
        stats_label.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        stats_label.setStyleSheet(f"color: {color};")
        stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(stats_label)

        ok_btn = QPushButton("Close")
        ok_btn.clicked.connect(dialog.accept)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d233c;
                border: 1px solid {color};
                border-radius: 4px;
                padding: 10px 24px;
                color: {color};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #3d2f52;
            }}
        """)
        layout.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        dialog.exec()
