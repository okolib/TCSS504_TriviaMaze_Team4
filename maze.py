"""Waxworks: The Midnight Curse — Maze Module (8×8)

Domain logic: grid layout, movement, trivia, fog of war.
This is the ONLY module that owns game rules.
"""

from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Protocol, List, Dict, Tuple
import random


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

FIGURES = [
    ("Leonardo DiCaprio", "Hollywood Wing"),
    ("Michael Jackson", "Music Hall"),
    ("Abraham Lincoln", "History Gallery"),
    ("Walt Disney", "Animation Vault"),
    ("Taylor Swift", "Pop Culture Lounge"),
]


# ======================================================================
# Maze Implementation
# ======================================================================

class Maze:
    """Concrete 8×8 Maze with randomised layout, fog of war, and trivia.

    Uses DFS-carved spanning tree + BFS critical-path analysis to place
    5 locked gates guarded by pop-culture wax figures.
    """

    def __init__(self, rows: int = 8, cols: int = 8,
                 trivia_data: Optional[List[TriviaQuestion]] = None,
                 seed: Optional[int] = None):
        self._seed = seed if seed is not None else random.randint(0, 2**31)
        self.rows = rows
        self.cols = cols
        self.player_position = Position(0, 0)
        self.curse_level = 0
        self.game_status = GameStatus.PLAYING
        self.defeated_figures: List[str] = []
        self.visited_positions: List[Position] = [Position(0, 0)]
        self.rooms: Dict[Tuple[int, int], Room] = {}

        self._neighbors: Dict[Tuple[int, int, Direction], Tuple[int, int]] = {}
        self._rng = random.Random(self._seed)
        self._build_maze()

    # ------------------------------------------------------------------
    # Randomized maze generator
    # ------------------------------------------------------------------

    def _build_maze(self):
        """Build a randomized 8×8 maze using DFS + BFS critical path."""
        num_figures = len(FIGURES)

        # Step 1: Initialize all rooms with WALLs
        for r in range(self.rows):
            for c in range(self.cols):
                self.rooms[(r, c)] = Room(
                    position=Position(r, c),
                    doors={d: DoorState.WALL for d in Direction},
                )

        # Step 2: Carve a spanning tree via randomized DFS
        visited = set()
        self._dfs_carve(0, 0, visited)

        # Step 3: Add extra edges (shortcuts) for exploration variety
        self._add_shortcuts(max(4, self.rows // 2))

        # Step 4: Find critical path from entrance to exit via BFS
        path = self._bfs_path((0, 0), (self.rows - 1, self.cols - 1))
        if not path or len(path) < num_figures + 3:
            self.rooms.clear()
            self._neighbors.clear()
            self._build_maze()
            return

        # Step 5: Place locked gates along the critical path
        gate_positions = self._select_gate_edges(path, num_figures)
        figure_rooms_list = []
        for (r1, c1), direction, (r2, c2) in gate_positions:
            self._set_door(r1, c1, direction, r2, c2, OPPOSITE[direction],
                          DoorState.LOCKED)
            # Figure goes on the entrance-side room of the gate
            figure_rooms_list.append((r1, c1))

        # Step 6: Mark entrance and exit
        self.rooms[(0, 0)].is_entrance = True
        self.rooms[(self.rows - 1, self.cols - 1)].is_exit = True

        # Step 7: Place figures randomly in the gate-adjacent rooms
        figures = list(FIGURES)
        self._rng.shuffle(figures)
        for (r, c), (name, zone) in zip(figure_rooms_list, figures):
            self.rooms[(r, c)].figure_name = name
            self.rooms[(r, c)].zone = zone

        # Safety: verify solvability (locked treated as passable)
        if not self.is_solvable():
            self.rooms.clear()
            self._neighbors.clear()
            self._build_maze()

    def _dfs_carve(self, r: int, c: int, visited: set):
        """Randomized DFS to carve corridors (spanning tree)."""
        visited.add((r, c))
        directions = list(Direction)
        self._rng.shuffle(directions)
        for d in directions:
            dr, dc = DELTA[d]
            nr, nc = r + dr, c + dc
            if (0 <= nr < self.rows and 0 <= nc < self.cols
                    and (nr, nc) not in visited):
                self._set_door(r, c, d, nr, nc, OPPOSITE[d], DoorState.OPEN)
                self._dfs_carve(nr, nc, visited)

    def _add_shortcuts(self, count: int):
        """Add extra open edges to create loops and alternate paths."""
        candidates = []
        for r in range(self.rows):
            for c in range(self.cols):
                for d in [Direction.EAST, Direction.SOUTH]:
                    dr, dc = DELTA[d]
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < self.rows and 0 <= nc < self.cols):
                        if self.rooms[(r, c)].doors[d] == DoorState.WALL:
                            candidates.append((r, c, d, nr, nc))
        self._rng.shuffle(candidates)
        for r, c, d, nr, nc in candidates[:count]:
            self._set_door(r, c, d, nr, nc, OPPOSITE[d], DoorState.OPEN)

    def _bfs_path(self, start: Tuple[int, int],
                  goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        """BFS shortest path through OPEN doors. Returns list of positions."""
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            (r, c), path = queue.popleft()
            if (r, c) == goal:
                return path
            room = self.rooms[(r, c)]
            for d in Direction:
                if room.doors[d] == DoorState.OPEN:
                    dr, dc = DELTA[d]
                    nr, nc = r + dr, c + dc
                    if (0 <= nr < self.rows and 0 <= nc < self.cols
                            and (nr, nc) not in visited):
                        visited.add((nr, nc))
                        queue.append(((nr, nc), path + [(nr, nc)]))
        return []

    def _select_gate_edges(self, path: List[Tuple[int, int]],
                           count: int):
        """Select evenly spaced edges along the critical path for gates.

        Returns list of ((r1,c1), direction, (r2,c2)) tuples.
        Avoids gates on the first or last edge of the path.
        """
        edges = []
        for i in range(len(path) - 1):
            r1, c1 = path[i]
            r2, c2 = path[i + 1]
            # Determine direction
            for d in Direction:
                dr, dc = DELTA[d]
                if r1 + dr == r2 and c1 + dc == c2:
                    edges.append(((r1, c1), d, (r2, c2)))
                    break

        # Pick evenly spaced edges, avoiding very first and last
        if len(edges) <= count + 1:
            # Short path — take all middle edges
            selected = edges[1:count + 1]
        else:
            # Space them out
            step = len(edges) / (count + 1)
            selected = [edges[int(step * (i + 1))] for i in range(count)]

        return selected[:count]

    def _set_door(self, r1, c1, d1, r2, c2, d2, state):
        """Set bidirectional door state."""
        self.rooms[(r1, c1)].doors[d1] = state
        self.rooms[(r2, c2)].doors[d2] = state

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_seed(self) -> int:
        """Return the RNG seed used to generate this maze."""
        return self._seed

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

        # Win condition — must defeat ALL figures before exit counts
        total_figures = sum(1 for r in self.rooms.values() if r.figure_name)
        if (self.rooms[(new_row, new_col)].is_exit
                and len(self.defeated_figures) >= total_figures):
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
        """Return the grid of FogMapCells with visibility info."""
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
