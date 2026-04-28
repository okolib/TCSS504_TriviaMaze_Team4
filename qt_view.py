"""Waxworks: The Midnight Curse — Qt View Module

PySide6 GUI implementation of ViewProtocol (interfaces.md §3.4).
Replaces the CLI View with a full graphical interface:
  - Maze canvas with fog-of-war
  - Sidebar with curse meter, room info, and navigation buttons
  - Trivia confrontation dialog with typewriter effect
  - Game log panel
  - Arrow-key movement
  - Audio mute toggle
  - End-of-game scoreboard

Imports maze types only — never imports db.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QDialog,
    QGridLayout, QProgressBar, QGroupBox, QMessageBox,
    QFrame, QSizePolicy, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QAction, QKeyEvent, QPixmap

from maze import (
    Direction, DoorState, GameStatus,
    Position, Room, GameState,
)

try:
    from maze import RoomVisibility, FogMapCell
except ImportError:
    from view import RoomVisibility, FogMapCell

from maze_canvas import MazeCanvas
from first_person_canvas import FirstPersonCanvas
from audio import AudioManager


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

_PORTRAIT_DIR = Path(__file__).parent / "assets" / "portraits"
_PORTRAIT_MAP = {
    "Leonardo DiCaprio": "dicaprio_wax.png",
    "Michael Jackson": "jackson_wax.png",
    "Abraham Lincoln": "lincoln_wax.png",
    "Walt Disney": "disney_wax.png",
    "Taylor Swift": "swift_wax.png",
}


class TriviaDialog(QDialog):
    """Modal dialog for wax figure confrontations with typewriter effect."""

    answer_selected = Signal(str)

    def __init__(self, question_dict: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wax Figure Confrontation")
        self.setMinimumWidth(580)
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1228;
                border: 2px solid #e6b832;
                border-radius: 8px;
            }
            QLabel { color: #dcd2f0; }
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

        # Portrait image
        portrait_file = _PORTRAIT_MAP.get(figure)
        if portrait_file:
            portrait_path = _PORTRAIT_DIR / portrait_file
            if portrait_path.exists():
                pix = QPixmap(str(portrait_path))
                img_label = QLabel()
                img_label.setPixmap(
                    pix.scaledToWidth(540, Qt.TransformationMode.SmoothTransformation)
                )
                img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img_label.setStyleSheet(
                    "border: 2px solid #e6b832; border-radius: 6px;"
                )
                layout.addWidget(img_label)

        name_label = QLabel(f"The eyes of {figure.upper()} snap open.")
        name_label.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #e6b832;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        desc = QLabel("Wax cracks along the jaw as it confronts you:")
        desc.setFont(QFont("Courier New", 10))
        desc.setStyleSheet("color: #786890;")
        layout.addWidget(desc)

        # Question with typewriter effect
        self._q_label = QLabel("")
        self._q_label.setFont(QFont("Courier New", 12))
        self._q_label.setStyleSheet("color: #88c8e8;")
        self._q_label.setWordWrap(True)
        self._q_label.setMinimumHeight(50)
        layout.addWidget(self._q_label)

        self._full_question = f'"{question}"'
        self._typed_chars = 0
        self._type_timer = QTimer(self)
        self._type_timer.setInterval(30)
        self._type_timer.timeout.connect(self._type_next_char)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3d2f52;")
        layout.addWidget(line)

        self._answer_buttons: list[QPushButton] = []
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        if isinstance(choices, dict):
            for key, text in choices.items():
                btn = QPushButton(f"  {key})  {text}")
                btn.setEnabled(False)
                btn.clicked.connect(lambda checked, k=key: self._select(k))
                btn_layout.addWidget(btn)
                self._answer_buttons.append(btn)
        elif isinstance(choices, list):
            for i, choice in enumerate(choices):
                key = choice.get("key", chr(65 + i))
                text = choice.get("text", str(choice))
                btn = QPushButton(f"  {key})  {text}")
                btn.setEnabled(False)
                btn.clicked.connect(lambda checked, k=key: self._select(k))
                btn_layout.addWidget(btn)
                self._answer_buttons.append(btn)

        layout.addLayout(btn_layout)

        self._type_timer.start()

    def _type_next_char(self):
        self._typed_chars += 1
        self._q_label.setText(self._full_question[:self._typed_chars])
        if self._typed_chars >= len(self._full_question):
            self._type_timer.stop()
            for btn in self._answer_buttons:
                btn.setEnabled(True)

    def _select(self, key: str):
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

    play_again_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waxworks: The Midnight Curse")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(WINDOW_STYLE)

        self._pending_input_callback = None
        self._current_question = None
        self._in_confrontation = False
        self._pending_confrontation = None
        self._view_mode = "first_person"
        self._player_facing = Direction.SOUTH
        self._audio = AudioManager()
        self._force_close = False
        self._game_started = False
        self._setup_ui()
        self._setup_menu()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the main window layout with a title screen and game screen."""
        self._root_stack = QStackedWidget()
        self.setCentralWidget(self._root_stack)

        # --- Page 0: Title / Start Screen ---
        self._title_page = QWidget()
        self._title_page.setStyleSheet("background-color: #0a0612;")
        tp_layout = QVBoxLayout(self._title_page)
        tp_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tp_layout.addStretch(2)

        glow_title = QLabel("WAXWORKS")
        glow_title.setFont(QFont("Courier New", 52, QFont.Weight.Bold))
        glow_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glow_title.setStyleSheet(
            "color: #e6b832;"
            "background: transparent;"
        )
        tp_layout.addWidget(glow_title)

        subtitle = QLabel("THE MIDNIGHT CURSE")
        subtitle.setFont(QFont("Courier New", 20, QFont.Weight.Bold))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #8a6cc0; background: transparent;")
        tp_layout.addWidget(subtitle)

        tp_layout.addSpacing(12)

        tagline = QLabel("Escape the cursed museum before you become\nthe newest exhibit — forever.")
        tagline.setFont(QFont("Courier New", 12))
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet("color: #786890; background: transparent;")
        tagline.setWordWrap(True)
        tp_layout.addWidget(tagline)

        tp_layout.addSpacing(40)

        _TITLE_BTN_STYLE = """
            QPushButton {
                background-color: #2d233c;
                border: 2px solid #e6b832;
                border-radius: 10px;
                color: #e6b832;
            }
            QPushButton:hover {
                background-color: #3d2f52;
                border-color: #ffd84a;
                color: #ffd84a;
            }
            QPushButton:pressed {
                background-color: #553d7a;
            }
        """

        self._btn_start = QPushButton("▶  START GAME")
        self._btn_start.setFont(QFont("Courier New", 18, QFont.Weight.Bold))
        self._btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_start.setFixedSize(320, 64)
        self._btn_start.setStyleSheet(_TITLE_BTN_STYLE)
        self._btn_start.clicked.connect(self._on_start_clicked)

        self._btn_music_toggle = QPushButton("♫ Music: ON")
        self._btn_music_toggle.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        self._btn_music_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_music_toggle.setFixedSize(180, 48)
        self._btn_music_toggle.setStyleSheet(_TITLE_BTN_STYLE)
        self._btn_music_toggle.clicked.connect(self._toggle_title_music)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.setSpacing(16)
        btn_row.addWidget(self._btn_start)
        btn_row.addWidget(self._btn_music_toggle)
        tp_layout.addLayout(btn_row)

        tp_layout.addStretch(3)

        footer = QLabel("TCSS 504 — Team 4")
        footer.setFont(QFont("Courier New", 9))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #3d2f52; background: transparent;")
        tp_layout.addWidget(footer)
        tp_layout.addSpacing(16)

        self._root_stack.addWidget(self._title_page)  # index 0

        # --- Page 1: Game Screen ---
        self._game_page = QWidget()
        main_layout = QHBoxLayout(self._game_page)
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

        # Navigation buttons (absolute compass directions)
        nav_group = QGroupBox("🧭 Navigation")
        nav_grid = QGridLayout(nav_group)

        _nav_btn_style = """
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                min-width: 36px;
                min-height: 28px;
                padding: 2px 4px;
            }
        """
        self._btn_north = QPushButton("▲ N")
        self._btn_south = QPushButton("▼ S")
        self._btn_west = QPushButton("◀ W")
        self._btn_east = QPushButton("▶ E")

        for btn in (self._btn_north, self._btn_south,
                    self._btn_west, self._btn_east):
            btn.setStyleSheet(_nav_btn_style)

        self._btn_north.clicked.connect(lambda: self._issue_command("move north"))
        self._btn_south.clicked.connect(lambda: self._issue_command("move south"))
        self._btn_west.clicked.connect(lambda: self._issue_command("move west"))
        self._btn_east.clicked.connect(lambda: self._issue_command("move east"))

        nav_grid.addWidget(self._btn_north, 0, 1)
        nav_grid.addWidget(self._btn_west, 1, 0)
        nav_grid.addWidget(self._btn_east, 1, 2)
        nav_grid.addWidget(self._btn_south, 2, 1)
        sidebar.addWidget(nav_group)

        # Controls help
        controls_group = QGroupBox("🎮 Controls")
        controls_layout = QVBoxLayout(controls_group)
        controls_label = QLabel(
            "<b>Move:</b> Arrow keys or W/A/S/D<br>"
            "&nbsp;&nbsp;↑/W = North &nbsp; ↓/S = South<br>"
            "&nbsp;&nbsp;←/A = West &nbsp;&nbsp; →/D = East<br>"
            "<b>Trivia:</b> Click answer in dialog<br>"
            "<b>View:</b> Toggle 🗺/👁 button"
        )
        controls_label.setFont(QFont("Courier New", 9))
        controls_label.setWordWrap(True)
        controls_label.setStyleSheet("color: #786890;")
        controls_layout.addWidget(controls_label)
        sidebar.addWidget(controls_group)

        # Action buttons
        action_group = QGroupBox("Actions")
        action_layout = QHBoxLayout(action_group)
        self._btn_load = QPushButton("Load")
        self._btn_mute = QPushButton("Mute")

        self._btn_load.clicked.connect(lambda: self._issue_command("load"))
        self._btn_mute.clicked.connect(self._toggle_mute)

        action_layout.addWidget(self._btn_load)
        action_layout.addWidget(self._btn_mute)
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

        self._root_stack.addWidget(self._game_page)  # index 1
        self._root_stack.setCurrentIndex(0)  # show title screen first

    def _on_start_clicked(self):
        """Transition from the title screen to the game."""
        if self._game_started:
            return
        self._game_started = True
        self._root_stack.setCurrentIndex(1)
        self._audio.start_music()
        self.command_issued.emit("__start__")

    def _toggle_title_music(self):
        """Toggle music on/off from the title screen."""
        muted = self._audio.toggle_mute()
        self._btn_music_toggle.setText("♫ Music: OFF" if muted else "♫ Music: ON")
        self._btn_mute.setText("Unmute" if muted else "Mute")

    def _setup_menu(self):
        """Build the menu bar."""
        menu_bar = self.menuBar()
        game_menu = menu_bar.addMenu("&Game")

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
        """Show the themed welcome banner in the game log."""
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
        defeated = getattr(game_state, "defeated_figures",
                           getattr(game_state, "answered_figures", []))
        self._fp_canvas.set_defeated_figures(defeated)

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
            "Hollywood Wing": {
                "entrance": "Movie posters line the walls. A man in a sharp suit leans against an Oscar...",
                "ambient": "Spotlights sweep across faded film reels.",
            },
            "Music Hall": {
                "entrance": "A sequined glove glistens under a single spotlight. A figure strikes a pose...",
                "ambient": "Faint echoes of a bass line drift through the hall.",
            },
            "History Gallery": {
                "entrance": "A tall figure in a stovepipe hat stands behind a podium...",
                "ambient": "A brass eagle gleams on the wall.",
            },
            "Animation Vault": {
                "entrance": "Animated sketches float along the walls. A man holds a familiar mouse-eared silhouette...",
                "ambient": "The faint sound of a music box plays 'When You Wish Upon a Star'.",
            },
            "Pop Culture Lounge": {
                "entrance": "Glittering stage lights pulse. A figure clutches a microphone, hair flowing...",
                "ambient": "Friendship bracelets crunch softly under your feet.",
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
        dir_map = {
            "north": Direction.NORTH, "south": Direction.SOUTH,
            "east": Direction.EAST, "west": Direction.WEST,
            "n": Direction.NORTH, "s": Direction.SOUTH,
            "e": Direction.EAST, "w": Direction.WEST,
        }
        if direction.lower() in dir_map and result in ("moved", "staircase"):
            self._player_facing = dir_map[direction.lower()]
            self._fp_canvas.start_walk_animation()
            self._audio.play("move")

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
            self._audio.play("locked")
            self._log(
                f"<span style='color:#e6b832;'>The gate to the {direction} is sealed. "
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
        if self._in_confrontation:
            self._pending_confrontation = question_dict
            return

        self._current_question = question_dict
        self._pending_confrontation = None
        self._in_confrontation = True
        figure = question_dict.get("figure_name", "Unknown")

        self._audio.play("confront")
        self._fp_canvas.start_figure_animation()

        self._log(
            f"<b style='color:#e65050;'>A wax figure stirs...</b><br>"
            f"<b style='color:#e6b832;'>The eyes of {figure.upper()} snap open.</b>"
        )

        dialog = TriviaDialog(question_dict, parent=self)
        dialog.answer_selected.connect(self._on_trivia_answer)
        dialog.exec()
        self._in_confrontation = False

        if self._pending_confrontation:
            QTimer.singleShot(100, lambda: self.display_confrontation(
                self._pending_confrontation))

    def display_answer_result(self, result: str, curse_level: int) -> None:
        """Display the result of answering a question."""
        if result == "correct":
            self._audio.play("correct")
            self._log(
                "<span style='color:#64c882;'>The figure is defeated!</span><br>"
                "<span style='color:#64c882;'>The curse recedes. The gate grinds open.</span><br>"
                "<span style='color:#786890;'>The figure nods slowly and returns to stillness.</span>"
            )
        elif result == "wrong":
            self._audio.play("wrong")
            self._log(
                "<span style='color:#e65050;'>Wrong!</span><br>"
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
                        rooms_explored: int = 0, total_rooms: int = 64,
                        figures_defeated: int = 0, total_figures: int = 5,
                        score: dict = None) -> None:
        """Display victory or game-over sequence with scoreboard."""
        self._audio.stop_music()
        if status == GameStatus.WON:
            self._audio.play("won")
        elif status == GameStatus.LOST:
            self._audio.play("lost")

        score = score or {}
        if status == GameStatus.WON:
            self._show_scoreboard_dialog(
                title="THE CURSE IS BROKEN",
                narrative=(
                    "The last gate opens...\n"
                    "Warm orange light floods the hallway.\n"
                    "The wax on your skin cracks and falls away.\n"
                    "Dawn breaks over the museum. You are free."
                ),
                rooms_explored=rooms_explored, total_rooms=total_rooms,
                figures_defeated=figures_defeated, total_figures=total_figures,
                curse_level=curse_level, score=score, color="#64c882",
            )
        elif status == GameStatus.LOST:
            self._show_scoreboard_dialog(
                title="GAME OVER",
                narrative=(
                    "Your skin hardens... your joints lock...\n"
                    "Your eyes glaze over.\n\n"
                    '"THE NEWEST EXHIBIT"\n'
                    "PERMANENT COLLECTION"
                ),
                rooms_explored=rooms_explored, total_rooms=total_rooms,
                figures_defeated=figures_defeated, total_figures=total_figures,
                curse_level=curse_level, score=score, color="#e65050",
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

    def _show_scoreboard_dialog(self, title: str, narrative: str,
                                rooms_explored: int, total_rooms: int,
                                figures_defeated: int, total_figures: int,
                                curse_level: int, score: dict,
                                color: str) -> None:
        """Show a styled scoreboard dialog with Play Again button."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(480)
        dialog.setStyleSheet(f"""
            QDialog {{ background-color: #1a1228; border: 2px solid {color}; }}
            QLabel {{ color: #dcd2f0; }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 24, 24, 24)

        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        t_lbl.setStyleSheet(f"color: {color};")
        t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(t_lbl)

        n_lbl = QLabel(narrative)
        n_lbl.setFont(QFont("Courier New", 10))
        n_lbl.setWordWrap(True)
        n_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(n_lbl)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #3d2f52;")
        layout.addWidget(line)

        # Scoreboard rows
        sb_lbl = QLabel("SCOREBOARD")
        sb_lbl.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        sb_lbl.setStyleSheet(f"color: {color};")
        sb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sb_lbl)

        rows = [
            (f"Figures Defeated  ({figures_defeated}/{total_figures})",
             score.get("figure_pts", 0)),
            (f"Rooms Explored    ({rooms_explored}/{total_rooms})",
             score.get("explore_pts", 0)),
            (f"Curse Resistance  ({100 - curse_level}%)",
             score.get("curse_pts", 0)),
            ("Victory Bonus", score.get("win_bonus", 0)),
        ]

        for label_text, pts in rows:
            row_w = QWidget()
            row_l = QHBoxLayout(row_w)
            row_l.setContentsMargins(20, 2, 20, 2)
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Courier New", 10))
            pts_lbl = QLabel(f"+{pts}")
            pts_lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            pts_lbl.setStyleSheet(f"color: {color};")
            pts_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            row_l.addWidget(lbl)
            row_l.addWidget(pts_lbl)
            layout.addWidget(row_w)

        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("color: #5a3d8a;")
        layout.addWidget(line2)

        total_w = QWidget()
        total_l = QHBoxLayout(total_w)
        total_l.setContentsMargins(20, 4, 20, 4)
        total_label = QLabel("TOTAL SCORE")
        total_label.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        total_pts = QLabel(str(score.get("total", 0)))
        total_pts.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        total_pts.setStyleSheet(f"color: {color};")
        total_pts.setAlignment(Qt.AlignmentFlag.AlignRight)
        total_l.addWidget(total_label)
        total_l.addWidget(total_pts)
        layout.addWidget(total_w)

        btn_style = f"""
            QPushButton {{
                background-color: #2d233c; border: 1px solid {color};
                border-radius: 4px; padding: 10px 24px;
                color: {color}; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3d2f52; }}
        """

        btn_row = QHBoxLayout()
        play_btn = QPushButton("Play Again")
        play_btn.setStyleSheet(btn_style)
        play_btn.clicked.connect(lambda: self._on_play_again(dialog))
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(btn_style)
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(play_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _on_play_again(self, dialog: QDialog) -> None:
        dialog.accept()
        self.play_again_requested.emit()

    # ------------------------------------------------------------------
    # Keyboard input
    # ------------------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle arrow-key movement with absolute compass directions."""
        if not self._game_started:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self._on_start_clicked()
            else:
                super().keyPressEvent(event)
            return

        compass_map = {
            Qt.Key.Key_Up: "north",
            Qt.Key.Key_W: "north",
            Qt.Key.Key_Down: "south",
            Qt.Key.Key_S: "south",
            Qt.Key.Key_Left: "west",
            Qt.Key.Key_A: "west",
            Qt.Key.Key_Right: "east",
            Qt.Key.Key_D: "east",
        }
        direction = compass_map.get(event.key())
        if direction:
            self._issue_command(f"move {direction}")
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    def _toggle_mute(self) -> None:
        muted = self._audio.toggle_mute()
        self._btn_mute.setText("Unmute" if muted else "Mute")
        self._btn_music_toggle.setText("♫ Music: OFF" if muted else "♫ Music: ON")

    # ------------------------------------------------------------------
    # Save-before-quit dialog
    # ------------------------------------------------------------------

    def ask_save_before_quit(self) -> str:
        """Show a dialog asking whether to save before quitting.
        Returns 'save', 'quit', or 'cancel'.
        """
        box = QMessageBox(self)
        box.setWindowTitle("Quit")
        box.setText("Save your progress before quitting?")
        box.setStyleSheet("""
            QMessageBox { background-color: #1a1228; }
            QLabel {
                color: #e6b832;
                font-family: 'Courier New';
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2d233c;
                border: 1px solid #5a3d8a;
                border-radius: 6px;
                padding: 8px 20px;
                color: #dcd2f0;
                font-family: 'Courier New';
                font-size: 13px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3d2f52;
                border-color: #e6b832;
            }
        """)
        save_btn = box.addButton("Save & Quit", QMessageBox.ButtonRole.AcceptRole)
        quit_btn = box.addButton("Quit", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == save_btn:
            return "save"
        elif clicked == quit_btn:
            return "quit"
        return "cancel"

    def force_close(self) -> None:
        """Close the window without triggering the save prompt."""
        self._force_close = True
        self.close()

    def closeEvent(self, event) -> None:
        """Intercept window close to offer save prompt."""
        if self._force_close:
            event.accept()
            return
        event.ignore()
        self._issue_command("quit")
