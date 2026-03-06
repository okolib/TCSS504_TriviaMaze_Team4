"""Waxworks: The Midnight Curse — View Module

Dedicated rendering module. Receives pure data from the Engine,
produces themed CLI output. Owns all print() and input() calls.

Imports maze types only — never imports db.
"""

import os
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from maze import (
    Direction, DoorState, GameStatus,
    Position, Room, GameState,
)

# RoomVisibility and FogMapCell are added by the maze team on feature/fog-of-war.
# Define local stubs so view.py works before that branch is merged.
try:
    from maze import RoomVisibility, FogMapCell
except ImportError:
    class RoomVisibility(Enum):
        """Fog of War visibility states (stub — replaced when maze team merges)."""
        HIDDEN = "hidden"
        VISIBLE = "visible"
        VISITED = "visited"
        CURRENT = "current"

    @dataclass
    class FogMapCell:
        """One cell in the fog map (stub — replaced when maze team merges)."""
        position: Position
        visibility: RoomVisibility
        has_trivia: bool = False
        figure_name: Optional[str] = None
        is_entrance: bool = False
        is_exit: bool = False
        doors: Optional[dict] = None


# ======================================================================
# ANSI Colors
# ======================================================================

class Colors:
    """ANSI escape codes for themed terminal output."""

    RESET   = "\033[0m"

    # Game states
    DANGER  = "\033[91m"   # Red — wrong answer, high curse, game over
    SUCCESS = "\033[92m"   # Green — correct answer, open doors, victory
    WARNING = "\033[93m"   # Yellow — locked gates, curse warnings
    INFO    = "\033[96m"   # Cyan — room descriptions, figure speech

    # Map rendering
    DIM     = "\033[2m"    # Dimmed — visited rooms, corridors
    BOLD    = "\033[1m"    # Bold — current room, headers, figures
    HIDDEN  = "\033[90m"   # Dark gray — unexplored fog

    @classmethod
    def disable(cls):
        """Disable ANSI codes for terminals without color support."""
        for attr in list(vars(cls)):
            if not attr.startswith("_") and attr != "disable":
                setattr(cls, attr, "")


# Respect NO_COLOR convention (https://no-color.org/)
if os.environ.get("NO_COLOR"):
    Colors.disable()


# ======================================================================
# Themed Content
# ======================================================================

ZONE_TEXT = {
    "Art Gallery": {
        "entrance": (
            "Paint-stained easels line the walls. In the center, "
            "a figure hunches over a canvas, brush frozen mid-stroke..."
        ),
        "ambient": "The Mona Lisa's eyes seem to follow you across the room.",
    },
    "American History": {
        "entrance": (
            "A tall figure in a stovepipe hat stands behind a podium. "
            "The air smells of old parchment and gunpowder..."
        ),
        "ambient": (
            "A brass eagle gleams on the wall. "
            "Dust motes drift through streaks of moonlight."
        ),
    },
    "Ancient History": {
        "entrance": (
            "Sand crunches under your feet. Hieroglyphs flicker in "
            "torchlight. A queen sits on a gilded throne..."
        ),
        "ambient": (
            "The faint hiss of a serpent echoes from "
            "somewhere in the shadows."
        ),
    },
    "Science Lab": {
        "entrance": (
            "Beakers bubble softly on a long bench. A chalkboard covered "
            "in equations glows faintly. A wild-haired figure adjusts "
            "his spectacles..."
        ),
        "ambient": (
            "A clock on the wall ticks at an impossible rate — "
            "faster, slower, faster."
        ),
    },
    "Library": {
        "entrance": (
            "Leather-bound books tower to the ceiling. A quill scratches "
            "across parchment by itself. A man in an Elizabethan ruff "
            "looks up..."
        ),
        "ambient": "Pages rustle though there is no wind.",
    },
    "Map Room": {
        "entrance": (
            "Yellowed maps cover every surface. The compass needle spins "
            "wildly. A man in explorer's garb traces a route across "
            "the Atlantic..."
        ),
        "ambient": "The smell of salt air and old rope hangs in the room.",
    },
}

CORRIDOR_TEXT = {
    "empty": "The hallway stretches into shadow. Your footsteps echo off cold marble.",
    "dead_end": "The passage ends abruptly. Dust and cobwebs. Nothing here but darkness.",
}

DREAD_MESSAGES = {
    0:   "You feel normal. For now.",
    20:  "Your fingers feel stiff and waxy.",
    40:  "Your arm won't bend. The curse is spreading.",
    60:  "Your joints are seizing. The curse tightens its grip.",
    80:  "You can barely move your legs. Time is running out.",
    100: "Your eyes glaze over. You cannot move. The curse is complete.",
}

AMBIENT_LINES = [
    "Somewhere in the distance, a clock chimes midnight.",
    "The floorboards creak behind you. But when you turn... nothing.",
    "A candle flickers and goes out.",
    "You hear the faint scraping of wax on stone.",
    "The air grows colder.",
]


# ======================================================================
# Candle Art (curse meter visualization)
# ======================================================================

# Each candle is a list of lines; index by curse_level // 20
CANDLE_FRAMES = [
    # 0% — full candle
    [
        "    )   ",
        "   (  ) ",
        "  (    )",
        " │ ░░░░░ │",
        " │ ░░░░░ │",
        " │ ░░░░░ │",
        " │ ░░░░░ │",
        " └───────┘",
    ],
    # 20% — slight melt
    [
        "    )   ",
        "   (  ) ",
        "        ",
        " │ ░░░░░ │",
        " │ ░░░░░ │",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " └───────┘",
    ],
    # 40% — half melted
    [
        "    )   ",
        "   (  ) ",
        "        ",
        " │ ░░░░░ │",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " └───────┘",
    ],
    # 60% — mostly melted
    [
        "        ",
        "    )   ",
        "        ",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " └───────┘",
    ],
    # 80% — nearly gone
    [
        "        ",
        "        ",
        "        ",
        " │ ░░░░░ │",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓│",
        " └───────┘",
    ],
    # 100% — total meltdown (puddle)
    [
        "        ",
        "        ",
        "        ",
        " ┌─────────┐",
        " │▓▓▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓▓▓│",
        " │▓▓▓▓▓▓▓▓▓│",
        " └─────────┘",
    ],
]


# ======================================================================
# View Class
# ======================================================================

class View:
    """Themed CLI view for Waxworks: The Midnight Curse.

    Receives pure data from the Engine, renders themed text output.
    Implements ViewProtocol from interfaces.md §3.4.
    """

    def __init__(self):
        """Initialize the View."""
        self._ambient_index = 0

    # ------------------------------------------------------------------
    # ViewProtocol methods
    # ------------------------------------------------------------------

    def display_welcome(self) -> None:
        """Show the themed welcome banner."""
        banner = (
            f"\n{Colors.BOLD}"
            "+--------------------------------------------------------------+\n"
            "|             WAXWORKS: THE MIDNIGHT CURSE                     |\n"
            "+--------------------------------------------------------------+\n"
            "|                                                              |\n"
            "|   The doors slam shut behind you.                            |\n"
            "|   The Grand Hall of History stretches into darkness.         |\n"
            "|   Your hand... is it shinier than before?                    |\n"
            "|                                                              |\n"
            "|   Find the exit before the Curse Meter reaches 100%          |\n"
            "|   or become the newest exhibit -- forever.                   |\n"
            "|                                                              |\n"
            "+--------------------------------------------------------------+\n"
            "|  Commands: move <north|south|east|west>  answer <A|B|C>      |\n"
            "|            save  load  map  quit                             |\n"
            "+--------------------------------------------------------------+"
            f"{Colors.RESET}\n"
        )
        print(banner)

    def display_room(self, room: Room, position: Position,
                     curse_level: int, game_state: GameState) -> None:
        """Display the current room description with zone flavor text."""
        lines = []

        # Room header
        lines.append(f"\n{Colors.BOLD}--- Room ({position.row}, {position.col}) ---{Colors.RESET}")

        if room.is_entrance:
            lines.append(f"{Colors.INFO}The Entrance — moonlight spills in behind you.{Colors.RESET}")
        elif room.is_exit:
            lines.append(f"{Colors.SUCCESS}You see the Exit ahead!{Colors.RESET}")

        # Zone-specific flavor text
        # Backward-compat: old Room has 'trivia', new Room has 'figure_name'/'zone'
        zone = getattr(room, "zone", None)
        figure_name = getattr(room, "figure_name", None)
        defeated = getattr(game_state, "defeated_figures",
                           getattr(game_state, "answered_figures", []))

        # Fall back to trivia-based figure name if new fields aren't available
        if figure_name is None and hasattr(room, "trivia") and room.trivia is not None:
            figure_name = room.trivia.figure_name
            zone = getattr(room.trivia, "zone", None)

        if zone and zone in ZONE_TEXT:
            zone_info = ZONE_TEXT[zone]
            if figure_name and figure_name not in defeated:
                lines.append(f"\n{Colors.INFO}{zone_info['entrance']}{Colors.RESET}")
            else:
                lines.append(f"\n{Colors.DIM}{zone_info['ambient']}{Colors.RESET}")
        elif not room.is_entrance and not room.is_exit:
            lines.append(f"\n{Colors.DIM}{CORRIDOR_TEXT['empty']}{Colors.RESET}")

        # Curse meter
        lines.append(self._render_curse_meter(curse_level))

        # Available doors
        dir_strs = []
        for d in Direction:
            state = room.doors[d]
            if state == DoorState.OPEN:
                dir_strs.append(f"{Colors.SUCCESS}{d.value} (open){Colors.RESET}")
            elif state == DoorState.LOCKED:
                dir_strs.append(f"{Colors.WARNING}{d.value} (locked){Colors.RESET}")
        doors_line = ", ".join(dir_strs) if dir_strs else "None"
        lines.append(f"Doors: {doors_line}")

        print("\n".join(lines))

    def display_fog_map(self, fog_map: list[list[FogMapCell]]) -> None:
        """Render the museum-themed fog-of-war map."""
        rows = len(fog_map)
        cols = len(fog_map[0]) if rows > 0 else 0

        WING_NAMES = ["FOYER", "ART", "HISTORY", "ANCIENT", "EXIT"]

        lines = []

        # Museum Directory header (framed, exact 39-char content width)
        lines.append("")
        lines.append(f"  {Colors.BOLD}{Colors.WARNING}+---------------------------------------+{Colors.RESET}")
        lines.append(f"  {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}  {Colors.BOLD}MUSEUM DIRECTORY{Colors.RESET}                     {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}")
        lines.append(f"  {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}  {Colors.DIM}The Grand Hall of History{Colors.RESET}            {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}")
        lines.append(f"  {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}               N                       {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}")
        lines.append(f"  {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}           W - + - E                   {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}")
        lines.append(f"  {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}               S                       {Colors.BOLD}{Colors.WARNING}|{Colors.RESET}")
        lines.append(f"  {Colors.BOLD}{Colors.WARNING}+---------------------------------------+{Colors.RESET}")

        # Column headers (free-standing grid, no side borders)
        header = "           "
        for c in range(cols):
            header += f"  {c}   "
        lines.append(header)

        # Top grid border
        lines.append("         ┌" + "┬".join(["─────"] * cols) + "┐")

        for r in range(rows):
            wing = WING_NAMES[r] if r < len(WING_NAMES) else f"W{r}"
            wing_label = f"{Colors.DIM}{wing:<7}{Colors.RESET}"

            # Cell content row with lock separators
            row_str = f"  {wing_label}│"
            for c in range(cols):
                cell = fog_map[r][c]
                row_str += self._render_fog_cell(cell)

                if c < cols - 1:
                    east_locked = False
                    if (cell.doors and Direction.EAST in cell.doors
                            and cell.doors[Direction.EAST] == DoorState.LOCKED
                            and cell.visibility != RoomVisibility.HIDDEN):
                        east_locked = True
                    if east_locked:
                        row_str += f"{Colors.WARNING}#{Colors.RESET}"
                    else:
                        row_str += "│"
                else:
                    row_str += "│"

            lines.append(row_str)

            # Passage row between grid rows
            if r < rows - 1:
                passage_str = "         ├"
                for c in range(cols):
                    cell = fog_map[r][c]
                    south_visible = False
                    south_locked = False
                    if cell.doors and Direction.SOUTH in cell.doors:
                        door = cell.doors[Direction.SOUTH]
                        if door != DoorState.WALL:
                            south_visible = True
                        if door == DoorState.LOCKED:
                            south_locked = True

                    if south_visible and cell.visibility != RoomVisibility.HIDDEN:
                        if south_locked:
                            passage_str += f"{Colors.WARNING}══#══{Colors.RESET}"
                        else:
                            passage_str += f"{Colors.SUCCESS}──│──{Colors.RESET}"
                    else:
                        passage_str += "─────"

                    if c < cols - 1:
                        passage_str += "┼"
                passage_str += "┤"
                lines.append(passage_str)

        # Bottom grid border
        lines.append("         └" + "┴".join(["─────"] * cols) + "┘")

        # Legend
        lines.append("")
        lines.append(
            f"  {Colors.BOLD}@{Colors.RESET} You   "
            f"{Colors.INFO}EN{Colors.RESET} Entry   "
            f"{Colors.SUCCESS}EX{Colors.RESET} Exit   "
            f"{Colors.DIM}[]{Colors.RESET} Figure   "
            f"{Colors.WARNING}#{Colors.RESET} Locked"
        )
        lines.append(
            f"  {Colors.DIM}░░{Colors.RESET} Visited  "
            f"·· Seen   "
            f"{Colors.HIDDEN}▓▓{Colors.RESET} Fog"
        )

        print("\n".join(lines))

    def display_move_result(self, result: str, direction: str) -> None:
        """Display the result of a move attempt."""
        if result == "moved":
            print(f"\n{Colors.SUCCESS}You move {direction}.{Colors.RESET}")
        elif result == "staircase":
            if direction in ("south", "s"):
                print(
                    f"\n{Colors.INFO}You descend a winding staircase...{Colors.RESET}"
                    f"\n{Colors.DIM}The air grows colder as you step into a new wing.{Colors.RESET}"
                )
            else:
                print(
                    f"\n{Colors.INFO}You climb back up the stairs...{Colors.RESET}"
                    f"\n{Colors.DIM}Familiar hallways stretch before you.{Colors.RESET}"
                )
        elif result == "locked":
            print(
                f"\n{Colors.WARNING}The gate to the {direction} is sealed. "
                f"A wax figure guards the way.{Colors.RESET}"
            )
        elif result == "wall":
            print(
                f"\n{Colors.DIM}There is no passage to the {direction}. "
                f"Only cold stone.{Colors.RESET}"
            )
        else:
            print(f"\n{Colors.DIM}You can't go that way.{Colors.RESET}")

    def display_confrontation(self, question_dict: dict) -> None:
        """Display a wax figure confrontation with the trivia question.

        Dynamically sizes the box to fit the longest content line.
        Wraps long questions so they don't overflow the border.
        """
        import textwrap

        figure = question_dict.get("figure_name", "Unknown Figure")
        question = question_dict.get("question_text", "")
        choices = question_dict.get("choices", {})

        # Build plain-text content lines first to measure widths
        header_text = "A wax figure stirs..."
        name_text = f"The eyes of {figure.upper()} snap open."
        desc_text = "Wax cracks along the jaw as it confronts you:"
        q_text = f'"{question}"'

        choice_lines = []
        if isinstance(choices, dict):
            for key, text in choices.items():
                choice_lines.append(f"{key}) {text}")
        elif isinstance(choices, list):
            for i, choice in enumerate(choices):
                key = choice.get("key", chr(65 + i))
                text = choice.get("text", str(choice))
                choice_lines.append(f"{key}) {text}")

        # Calculate inner width: max of all content + 6 chars padding (3 left + 3 right)
        all_content = [header_text, name_text, desc_text, q_text] + choice_lines
        min_w = max(len(line) for line in all_content) + 6
        w = max(min_w, 40)  # at least 40 chars wide

        # Wrap question if still too wide for reasonable terminal (cap at 72)
        max_w = 72
        if w > max_w:
            w = max_w
            wrap_width = w - 6  # 3 padding each side
            q_wrapped = textwrap.wrap(q_text, width=wrap_width)
        else:
            q_wrapped = [q_text]

        def _pad_line(text, inner_w):
            """Return a formatted box line with proper padding."""
            import re
            # Strip ANSI escape codes to measure visible width
            visible = re.sub(r'\033\[[0-9;]*m', '', text)
            pad = max(0, inner_w - len(visible) - 3)
            return f"{Colors.BOLD}|{Colors.RESET}   {text}{' ' * pad}{Colors.BOLD}|{Colors.RESET}"

        lines = []
        lines.append(f"\n{Colors.BOLD}+{'-' * w}+{Colors.RESET}")
        lines.append(f"{Colors.BOLD}|{Colors.RESET}{' ' * w}{Colors.BOLD}|{Colors.RESET}")
        lines.append(_pad_line(f"{Colors.INFO}{header_text}{Colors.RESET}", w))
        lines.append(f"{Colors.BOLD}|{Colors.RESET}{' ' * w}{Colors.BOLD}|{Colors.RESET}")
        lines.append(_pad_line(f"The eyes of {Colors.WARNING}{figure.upper()}{Colors.RESET}{Colors.BOLD} snap open.{Colors.RESET}", w))
        lines.append(_pad_line(f"{Colors.DIM}{desc_text}{Colors.RESET}", w))
        lines.append(f"{Colors.BOLD}|{Colors.RESET}{' ' * w}{Colors.BOLD}|{Colors.RESET}")

        for qline in q_wrapped:
            lines.append(_pad_line(f"{Colors.INFO}{qline}{Colors.RESET}", w))
        lines.append(f"{Colors.BOLD}|{Colors.RESET}{' ' * w}{Colors.BOLD}|{Colors.RESET}")

        for cl in choice_lines:
            lines.append(_pad_line(cl, w))

        lines.append(f"{Colors.BOLD}|{Colors.RESET}{' ' * w}{Colors.BOLD}|{Colors.RESET}")
        lines.append(f"{Colors.BOLD}+{'-' * w}+{Colors.RESET}")

        print("\n".join(lines))

    def display_answer_result(self, result: str, curse_level: int) -> None:
        """Display the result of answering a question."""
        if result == "correct":
            print(
                f"\n  {Colors.SUCCESS}✓ The figure is defeated!{Colors.RESET}\n"
                f"  {Colors.SUCCESS}The curse recedes. The gate grinds open.{Colors.RESET}\n"
                f"  {Colors.DIM}The figure nods slowly and returns to stillness.{Colors.RESET}"
            )
        elif result == "wrong":
            print(
                f"\n  {Colors.DANGER}✗ Wrong!{Colors.RESET}\n"
                f"  {Colors.WARNING}The curse tightens its grip... "
                f"you feel your fingers stiffening.{Colors.RESET}\n"
                f"  {Colors.DIM}A grinding of stone. The gate stays sealed.{Colors.RESET}"
            )
            print(self._render_curse_meter(curse_level))
        elif result == "no_figure":
            print(f"\n{Colors.DIM}There is no figure to confront here.{Colors.RESET}")
        elif result == "already_answered":
            print(f"\n{Colors.DIM}This figure has already been defeated. The gate is open.{Colors.RESET}")
        elif result == "game_over":
            print(f"\n{Colors.DANGER}The curse is complete. You cannot move.{Colors.RESET}")

    def display_save_result(self, success: bool, error: str = "") -> None:
        """Display save confirmation or error."""
        if success:
            print(f"\n{Colors.SUCCESS}Game saved.{Colors.RESET}")
        else:
            msg = f" ({error})" if error else ""
            print(f"\n{Colors.DANGER}Save failed{msg}.{Colors.RESET}")

    def display_load_result(self, success: bool) -> None:
        """Display load confirmation or failure."""
        if success:
            print(f"\n{Colors.SUCCESS}Game loaded. The museum shifts around you...{Colors.RESET}")
        else:
            print(f"\n{Colors.WARNING}No saved game found.{Colors.RESET}")

    def display_endgame(self, status: GameStatus, curse_level: int,
                        rooms_explored: int = 0, total_rooms: int = 25,
                        figures_defeated: int = 0, total_figures: int = 3) -> None:
        """Display victory or game-over sequence."""
        if status == GameStatus.WON:
            self._display_victory(curse_level, rooms_explored, total_rooms,
                                  figures_defeated, total_figures)
        elif status == GameStatus.LOST:
            self._display_game_over(curse_level, rooms_explored, total_rooms,
                                    figures_defeated, total_figures)

    def display_error(self, message: str) -> None:
        """Display an error message."""
        print(f"\n{Colors.DANGER}Error: {message}{Colors.RESET}")

    def get_input(self, prompt: str = "") -> str:
        """Read player input from the CLI with themed prompt."""
        themed_prompt = prompt if prompt else f"\n  {Colors.DIM}🕯{Colors.RESET} What do you do? > "
        try:
            return input(themed_prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            return "quit"

    # ------------------------------------------------------------------
    # Private rendering helpers
    # ------------------------------------------------------------------

    def _render_curse_meter(self, curse_level: int) -> str:
        """Render the curse meter bar with color and dread message."""
        # Color based on severity
        if curse_level >= 80:
            color = Colors.DANGER
        elif curse_level >= 40:
            color = Colors.WARNING
        else:
            color = Colors.SUCCESS

        # Progress bar
        filled = curse_level // 10
        empty = 10 - filled
        bar = "█" * filled + "░" * empty

        # Dread message (snap to nearest 20)
        level_key = min((curse_level // 20) * 20, 100)
        dread = DREAD_MESSAGES.get(level_key, "")

        return (
            f"\n  {color}Curse Level: [{bar}] {curse_level}{Colors.RESET}"
            f"\n  {Colors.DIM}{dread}{Colors.RESET}"
        )

    def _render_fog_cell(self, cell: FogMapCell) -> str:
        """Render a single fog map cell as a 5-char ASCII string."""
        FIGURE_INITIALS = {
            "Leonardo da Vinci": "DV",
            "Abraham Lincoln": "AL",
            "Cleopatra": "CL",
        }

        if cell.visibility == RoomVisibility.CURRENT:
            return f"{Colors.BOLD}  @  {Colors.RESET}"
        elif cell.visibility == RoomVisibility.VISITED:
            if cell.has_trivia and cell.figure_name:
                initials = FIGURE_INITIALS.get(cell.figure_name, "??")
                return f"{Colors.DIM} [{initials}]{Colors.RESET}"
            elif cell.is_exit:
                return f"{Colors.SUCCESS} EX  {Colors.RESET}"
            elif cell.is_entrance:
                return f"{Colors.INFO} EN  {Colors.RESET}"
            else:
                return f"{Colors.DIM}  ░░ {Colors.RESET}"
        elif cell.visibility == RoomVisibility.VISIBLE:
            if cell.is_exit:
                return f"{Colors.SUCCESS} EX  {Colors.RESET}"
            return f"  ·· "
        else:  # HIDDEN
            return f"{Colors.HIDDEN}  ▓▓ {Colors.RESET}"

    def _display_victory(self, curse_level: int, rooms_explored: int,
                         total_rooms: int, figures_defeated: int,
                         total_figures: int) -> None:
        """Display the victory sequence."""
        w = 40
        print(
            f"\n  {Colors.SUCCESS}The last gate opens...{Colors.RESET}\n"
            f"\n  Warm orange light floods the hallway."
            f"\n  The wax on your skin cracks and falls away."
            f"\n  Behind you, the figures slump — lifeless once more.\n"
        )

        print(f"{Colors.BOLD}{Colors.SUCCESS}")
        print(f"  +{'-' * w}+")
        print(f"  |{'THE CURSE IS BROKEN.':^{w}}|")
        print(f"  |{'Dawn breaks over the museum.':^{w}}|")
        print(f"  |{'You are free.':^{w}}|")
        print(f"  +{'-' * w}+")
        r_line = f"  Rooms explored:  {rooms_explored}/{total_rooms}"
        f_line = f"  Figures defeated: {figures_defeated}/{total_figures}"
        c_line = f"  Curse Level:     {curse_level}"
        print(f"  |{r_line:<{w}}|")
        print(f"  |{f_line:<{w}}|")
        print(f"  |{c_line:<{w}}|")
        print(f"  +{'-' * w}+")
        print(f"{Colors.RESET}")

    def _display_game_over(self, curse_level: int, rooms_explored: int,
                           total_rooms: int, figures_defeated: int,
                           total_figures: int) -> None:
        """Display the game over sequence."""
        w = 40
        print(f"\n  {Colors.DANGER}Your skin hardens...{Colors.RESET}")
        print(f"  {Colors.DANGER}Your joints lock...{Colors.RESET}")
        print(f"  {Colors.DANGER}Your eyes glaze over...{Colors.RESET}\n")

        pw = 38
        print(f"{Colors.WARNING}")
        print(f"  +{'-' * pw}+")
        print(f"  |{'':>{pw}}|")
        print(f"  |{chr(34)+'THE NEWEST EXHIBIT'+chr(34):^{pw}}|")
        print(f"  |{'':>{pw}}|")
        print(f"  |{'Name:  Unknown Explorer':^{pw}}|")
        print(f"  |{'Date:  The Midnight Hour':^{pw}}|")
        print(f"  |{'Cause: Curiosity':^{pw}}|")
        print(f"  |{'':>{pw}}|")
        print(f"  |{'PERMANENT  COLLECTION':^{pw}}|")
        print(f"  |{'':>{pw}}|")
        print(f"  +{'-' * pw}+")
        print(f"{Colors.RESET}")

        print(f"{Colors.BOLD}{Colors.DANGER}")
        print(f"  +{'-' * w}+")
        print(f"  |{'=== GAME OVER ===':^{w}}|")
        print(f"  +{'-' * w}+")
        r_line = f"  Rooms explored:  {rooms_explored}/{total_rooms}"
        f_line = f"  Figures defeated: {figures_defeated}/{total_figures}"
        c_line = f"  Curse Level:     {curse_level}"
        print(f"  |{r_line:<{w}}|")
        print(f"  |{f_line:<{w}}|")
        print(f"  |{c_line:<{w}}|")
        print(f"  +{'-' * w}+")
        print(f"{Colors.RESET}")


    def _get_ambient_line(self) -> str:
        """Cycle through ambient/idle text lines."""
        line = AMBIENT_LINES[self._ambient_index % len(AMBIENT_LINES)]
        self._ambient_index += 1
        return f"{Colors.DIM}{line}{Colors.RESET}"
