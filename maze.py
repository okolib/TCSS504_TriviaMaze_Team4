"""Waxworks: The Midnight Curse — Maze Module (5×5 MVP)

Domain logic: grid layout, movement, trivia, fog of war.
This is the ONLY module that owns game rules.

Emergency fallback implementation — local only, not pushed.
"""

from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Protocol, List, Dict, Tuple


# ======================================================================
# Types
# ======================================================================

class Direction(Enum):
    """Cardinal directions for movement."""
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class DoorState(Enum):
    """State of a passage between two rooms."""
    OPEN = "open"
    LOCKED = "locked"
    WALL = "wall"


class GameStatus(Enum):
    """Top-level game state."""
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"


class RoomVisibility(Enum):
    """Fog of War visibility states."""
    HIDDEN = "hidden"
    VISIBLE = "visible"
    VISITED = "visited"
    CURRENT = "current"


@dataclass(frozen=True)
class Position:
    """A (row, col) coordinate in the maze grid. Immutable."""
    row: int
    col: int


@dataclass
class TriviaQuestion:
    """A single trivia question attached to a wax figure.
    Kept for backward compatibility; the DB now serves questions."""
    figure_name: str
    zone: str
    question_text: str
    choices: Dict[str, str]
    correct_key: str


@dataclass
class Room:
    """One cell of the maze grid.
    Per RFC §2.2: Rooms store *which figure lives here*, not the question."""
    position: Position
    doors: Dict[Direction, DoorState]
    figure_name: Optional[str] = None     # Which wax figure lives here
    zone: Optional[str] = None            # Thematic zone ("Art Gallery", etc.)
    is_entrance: bool = False
    is_exit: bool = False

    # Backward compat — expose a trivia-like interface for tests
    @property
    def trivia(self) -> Optional[TriviaQuestion]:
        """Returns a lightweight TriviaQuestion stub if a figure is present.
        This allows existing code (room.trivia.figure_name) to keep working.
        The actual question content comes from the DB at runtime."""
        if self.figure_name:
            return TriviaQuestion(
                figure_name=self.figure_name,
                zone=self.zone or "",
                question_text="",   # placeholder; real q comes from DB
                choices={},
                correct_key="",
            )
        return None


@dataclass
class FogMapCell:
    """One cell in the fog-of-war map view."""
    position: Position
    visibility: RoomVisibility
    has_trivia: bool = False
    figure_name: Optional[str] = None
    is_entrance: bool = False
    is_exit: bool = False
    doors: Optional[Dict[Direction, DoorState]] = None


@dataclass
class GameState:
    """Complete snapshot of a game in progress.
    Per RFC §2.2: uses curse_level and defeated_figures as primary names."""
    player_position: Position
    curse_level: int                               # 0–100 (RFC name)
    game_status: GameStatus
    defeated_figures: List[str]                    # figure names cleared (RFC name)
    visited_positions: List[Position]
    door_states: Dict[Tuple[int, int], Dict[Direction, DoorState]]

    # Backward-compat aliases
    @property
    def wax_meter(self) -> int:
        return self.curse_level

    @property
    def answered_figures(self) -> List[str]:
        return self.defeated_figures


# ======================================================================
# Opposite direction helper
# ======================================================================

OPPOSITE = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
}

DELTA = {
    Direction.NORTH: (-1, 0),
    Direction.SOUTH: (1, 0),
    Direction.EAST: (0, 1),
    Direction.WEST: (0, -1),
}


# ======================================================================
# Protocol
# ======================================================================

class MazeProtocol(Protocol):
    """Public contract for the Maze domain object."""

    def get_rooms(self) -> Dict[Tuple[int, int], Room]: ...
    def get_room(self, position: Position) -> Room: ...
    def get_player_position(self) -> Position: ...
    def get_wax_meter(self) -> int: ...
    def get_curse_level(self) -> int: ...
    def get_game_status(self) -> GameStatus: ...
    def get_available_directions(self) -> List[Direction]: ...
    def move(self, direction: Direction) -> str: ...
    def attempt_answer(self, answer_key: str, correct_key: Optional[str] = None) -> str: ...
    def get_game_state(self) -> GameState: ...
    def restore_game_state(self, state: GameState) -> None: ...
    def get_fog_map(self) -> List[List[FogMapCell]]: ...
    def is_solvable(self) -> bool: ...


# ======================================================================
# Figure placement data (per RFC §2.2)
# ======================================================================

# (row, col) → (figure_name, zone)
FIGURE_PLACEMENTS = {
    (1, 1): ("Leonardo da Vinci", "Art Gallery"),
    (2, 2): ("Abraham Lincoln", "American History"),
    (3, 3): ("Cleopatra", "Ancient History"),
}


# ======================================================================
# Maze Implementation
# ======================================================================

class Maze:
    """Concrete 5×5 Maze with staircase layout, fog of war, and trivia.

    Layout from interfaces.md §6:
        (0,0) ENTRANCE
        Row 0: (0,0)──(0,1)──(0,2)
        South: (0,0)↔(1,0)
        Row 1: (1,0)──(1,1)═🔒═(1,2)──(1,3)   Da Vinci at (1,1)
        South: (1,2)↔(2,1)
        Row 2: (2,1)──(2,2)═🔒═(2,3)──(2,4)   Lincoln at (2,2)
        South: (2,3)↔(3,2)
        Row 3: (3,2)──(3,3)═🔒═(3,4)           Cleopatra at (3,3)
        South: (3,4)↔(4,4)
        Row 4: (4,3)──(4,4) EXIT
    """

    def __init__(self, rows: int = 5, cols: int = 5,
                 trivia_data: Optional[List[TriviaQuestion]] = None):
        self.rows = rows
        self.cols = cols
        self.player_position = Position(0, 0)
        self.curse_level = 0
        self.game_status = GameStatus.PLAYING
        self.defeated_figures: List[str] = []
        self.visited_positions: List[Position] = [Position(0, 0)]
        self.rooms: Dict[Tuple[int, int], Room] = {}

        self._neighbors: Dict[Tuple[int, int, Direction], Tuple[int, int]] = {}
        self._build_maze()

    # ------------------------------------------------------------------
    # Layout builder
    # ------------------------------------------------------------------

    def _build_maze(self):
        """Build the 5×5 staircase layout."""
        # Initialize all rooms with WALLs
        for r in range(self.rows):
            for c in range(self.cols):
                self.rooms[(r, c)] = Room(
                    position=Position(r, c),
                    doors={d: DoorState.WALL for d in Direction},
                )

        # --- Horizontal connections ---
        # Row 0: entrance corridor
        self._set_door(0, 0, Direction.EAST, 0, 1, Direction.WEST, DoorState.OPEN)
        self._set_door(0, 1, Direction.EAST, 0, 2, Direction.WEST, DoorState.OPEN)

        # Row 1: Da Vinci row
        self._set_door(1, 0, Direction.EAST, 1, 1, Direction.WEST, DoorState.OPEN)
        self._set_door(1, 1, Direction.EAST, 1, 2, Direction.WEST, DoorState.LOCKED)  # 🔒
        self._set_door(1, 2, Direction.EAST, 1, 3, Direction.WEST, DoorState.OPEN)

        # Row 2: Lincoln row
        self._set_door(2, 1, Direction.EAST, 2, 2, Direction.WEST, DoorState.OPEN)
        self._set_door(2, 2, Direction.EAST, 2, 3, Direction.WEST, DoorState.LOCKED)  # 🔒
        self._set_door(2, 3, Direction.EAST, 2, 4, Direction.WEST, DoorState.OPEN)

        # Row 3: Cleopatra row
        self._set_door(3, 2, Direction.EAST, 3, 3, Direction.WEST, DoorState.OPEN)
        self._set_door(3, 3, Direction.EAST, 3, 4, Direction.WEST, DoorState.LOCKED)  # 🔒

        # Row 4: exit corridor
        self._set_door(4, 3, Direction.EAST, 4, 4, Direction.WEST, DoorState.OPEN)

        # --- Vertical (south) connections — staircase pattern ---
        self._set_door(0, 0, Direction.SOUTH, 1, 0, Direction.NORTH, DoorState.OPEN)
        self._set_door(1, 2, Direction.SOUTH, 2, 1, Direction.NORTH, DoorState.OPEN)  # staircase!
        self._set_door(2, 3, Direction.SOUTH, 3, 2, Direction.NORTH, DoorState.OPEN)  # staircase!
        self._set_door(3, 4, Direction.SOUTH, 4, 4, Direction.NORTH, DoorState.OPEN)

        # Register diagonal neighbors for move() calculation
        # (1,2) SOUTH -> (2,1) instead of (2,2)
        self._neighbors[(1, 2, Direction.SOUTH)] = (2, 1)
        self._neighbors[(2, 1, Direction.NORTH)] = (1, 2)
        # (2,3) SOUTH -> (3,2) instead of (3,3)
        self._neighbors[(2, 3, Direction.SOUTH)] = (3, 2)
        self._neighbors[(3, 2, Direction.NORTH)] = (2, 3)

        # --- Mark entrance and exit ---
        self.rooms[(0, 0)].is_entrance = True
        self.rooms[(4, 4)].is_exit = True

        # --- Place figures (per RFC §2.2: figure_name + zone, not trivia) ---
        for (r, c), (name, zone) in FIGURE_PLACEMENTS.items():
            self.rooms[(r, c)].figure_name = name
            self.rooms[(r, c)].zone = zone

    def _set_door(self, r1, c1, d1, r2, c2, d2, state):
        """Set bidirectional door state."""
        self.rooms[(r1, c1)].doors[d1] = state
        self.rooms[(r2, c2)].doors[d2] = state

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_rooms(self) -> Dict[Tuple[int, int], Room]:
        return self.rooms

    def get_room(self, position: Position) -> Room:
        key = (position.row, position.col)
        if key not in self.rooms:
            raise KeyError(f"Position {position} is out of bounds.")
        return self.rooms[key]

    def get_player_position(self) -> Position:
        return self.player_position

    def get_wax_meter(self) -> int:
        return self.curse_level

    def get_curse_level(self) -> int:
        """RFC-named accessor for curse level."""
        return self.curse_level

    def get_game_status(self) -> GameStatus:
        return self.game_status

    def get_available_directions(self) -> List[Direction]:
        room = self.get_room(self.player_position)
        return [d for d, state in room.doors.items() if state != DoorState.WALL]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def move(self, direction: Direction) -> str:
        """Attempt to move the player in the given direction."""
        if self.game_status != GameStatus.PLAYING:
            return "invalid"

        room = self.get_room(self.player_position)
        door_state = room.doors.get(direction, DoorState.WALL)

        if door_state == DoorState.WALL:
            return "wall"
        if door_state == DoorState.LOCKED:
            return "locked"

        # Calculate new position — check explicit neighbor map first
        key = (self.player_position.row, self.player_position.col, direction)
        is_staircase = key in self._neighbors
        if is_staircase:
            new_row, new_col = self._neighbors[key]
        else:
            dr, dc = DELTA[direction]
            new_row = self.player_position.row + dr
            new_col = self.player_position.col + dc

        if not (0 <= new_row < self.rows and 0 <= new_col < self.cols):
            return "invalid"

        self.player_position = Position(new_row, new_col)
        if self.player_position not in self.visited_positions:
            self.visited_positions.append(self.player_position)

        # Win condition
        if self.rooms[(new_row, new_col)].is_exit:
            self.game_status = GameStatus.WON

        return "staircase" if is_staircase else "moved"

    def attempt_answer(self, answer_key: str,
                        correct_key: Optional[str] = None) -> str:
        """Submit trivia answer. Unlocks ALL locked doors on success.

        Per RFC §2.2: generic door unlock — loops all LOCKED doors in
        the current room and opens them bidirectionally.

        If correct_key is provided (from DB), it is used for validation.
        Otherwise falls back to room.trivia.correct_key (backward compat).
        """
        if self.game_status != GameStatus.PLAYING:
            return "game_over"

        room = self.get_room(self.player_position)
        if not room.figure_name:
            return "no_trivia"

        figure_name = room.figure_name
        if figure_name in self.defeated_figures:
            return "already_answered"

        # Use DB-provided correct_key, or fall back to embedded trivia
        key = correct_key if correct_key else (room.trivia.correct_key if room.trivia else None)
        if not key:
            return "no_trivia"

        if answer_key.upper() == key:
            self.defeated_figures.append(figure_name)

            # Generic unlock: open ALL locked doors in the current room
            pos = self.player_position
            for direction, state in list(room.doors.items()):
                if state == DoorState.LOCKED:
                    neighbor = self._get_neighbor(pos, direction)
                    if neighbor:
                        opp = OPPOSITE[direction]
                        self._set_door(pos.row, pos.col, direction,
                                       neighbor.row, neighbor.col, opp,
                                       DoorState.OPEN)

            return "correct"
        else:
            self.curse_level += 20
            if self.curse_level >= 100:
                self.curse_level = 100
                self.game_status = GameStatus.LOST
            return "wrong"

    def _get_neighbor(self, pos: Position, direction: Direction) -> Optional[Position]:
        """Return the adjacent Position in the given direction, or None if off-grid."""
        dr, dc = DELTA[direction]
        nr, nc = pos.row + dr, pos.col + dc
        if 0 <= nr < self.rows and 0 <= nc < self.cols:
            return Position(nr, nc)
        return None

    # ------------------------------------------------------------------
    # Fog of War
    # ------------------------------------------------------------------

    def get_fog_map(self) -> List[List[FogMapCell]]:
        """Return a 5×5 grid of FogMapCells with visibility info."""
        visited_set = set((p.row, p.col) for p in self.visited_positions)
        player_rc = (self.player_position.row, self.player_position.col)

        # Adjacent to any visited room = VISIBLE
        adjacent_set = set()
        for vr, vc in visited_set:
            for d in Direction:
                dr, dc = DELTA[d]
                nr, nc = vr + dr, vc + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    room = self.rooms[(vr, vc)]
                    if room.doors[d] != DoorState.WALL:
                        adjacent_set.add((nr, nc))

        grid = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                room = self.rooms[(r, c)]

                if (r, c) == player_rc:
                    vis = RoomVisibility.CURRENT
                elif (r, c) in visited_set:
                    vis = RoomVisibility.VISITED
                elif (r, c) in adjacent_set:
                    vis = RoomVisibility.VISIBLE
                else:
                    vis = RoomVisibility.HIDDEN

                cell = FogMapCell(
                    position=Position(r, c),
                    visibility=vis,
                    has_trivia=room.figure_name is not None,
                    figure_name=room.figure_name,
                    is_entrance=room.is_entrance,
                    is_exit=room.is_exit,
                    doors=room.doors.copy() if vis != RoomVisibility.HIDDEN else None,
                )
                row.append(cell)
            grid.append(row)
        return grid

    def is_solvable(self) -> bool:
        """BFS from entrance to exit, treating LOCKED as passable."""
        start = (0, 0)
        goal = (self.rows - 1, self.cols - 1)

        visited = set()
        queue = deque([start])
        visited.add(start)

        while queue:
            r, c = queue.popleft()
            if (r, c) == goal:
                return True

            room = self.rooms[(r, c)]
            for d in Direction:
                if room.doors[d] != DoorState.WALL:
                    dr, dc = DELTA[d]
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        if (nr, nc) not in visited:
                            visited.add((nr, nc))
                            queue.append((nr, nc))
        return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def get_game_state(self) -> GameState:
        """Return snapshot for serialization."""
        return GameState(
            player_position=self.player_position,
            curse_level=self.curse_level,
            game_status=self.game_status,
            defeated_figures=self.defeated_figures.copy(),
            visited_positions=self.visited_positions.copy(),
            door_states={
                pos: room.doors.copy() for pos, room in self.rooms.items()
            },
        )

    def restore_game_state(self, state: GameState) -> None:
        """Restore from snapshot."""
        if not (0 <= state.player_position.row < self.rows and
                0 <= state.player_position.col < self.cols):
            raise ValueError("Invalid player position in restored state")

        self.player_position = state.player_position
        self.curse_level = state.curse_level
        self.game_status = state.game_status
        self.defeated_figures = state.defeated_figures.copy()
        self.visited_positions = state.visited_positions.copy()

        for pos_tuple, doors in state.door_states.items():
            if pos_tuple in self.rooms:
                self.rooms[pos_tuple].doors = doors.copy()
