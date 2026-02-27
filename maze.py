from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Protocol, List, Dict, Tuple

class Direction(Enum):
    """Cardinal directions for movement."""
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

class DoorState(Enum):
    """State of a passage between two rooms."""
    OPEN = "open"        # Always passable
    LOCKED = "locked"    # Requires correct trivia answer to unlock
    WALL = "wall"        # Impassable — no door here

class GameStatus(Enum):
    """Top-level game state."""
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"

@dataclass(frozen=True)
class Position:
    """A (row, col) coordinate in the maze grid. Immutable."""
    row: int
    col: int

@dataclass
class TriviaQuestion:
    """A single trivia question attached to a wax figure."""
    figure_name: str       # e.g. "Leonardo da Vinci"
    zone: str              # e.g. "Art Gallery"
    question_text: str
    choices: Dict[str, str] # {"A": "...", "B": "...", "C": "..."}
    correct_key: str        # "A", "B", or "C"

@dataclass
class Room:
    """One cell of the maze grid.
    Every room defines all four cardinal directions in its doors dict.
    Grid-edge directions are represented as DoorState.WALL.
    """
    position: Position
    doors: Dict[Direction, DoorState]          # What's in each direction
    trivia: Optional[TriviaQuestion] = None    # None means ordinary corridor
    is_entrance: bool = False
    is_exit: bool = False

@dataclass
class GameState:
    """Complete snapshot of a game in progress."""
    player_position: Position
    wax_meter: int                  # 0–100
    game_status: GameStatus
    answered_figures: List[str]     # figure_name values already cleared
    visited_positions: List[Position]
    door_states: Dict[Tuple[int, int], Dict[Direction, DoorState]]  # current state of every door

class MazeProtocol(Protocol):
    """Public contract for the Maze domain object."""

    def get_rooms(self) -> Dict[Tuple[int, int], Room]:
        """Return the full room grid keyed by (row, col)."""
        ...

    def get_room(self, position: Position) -> Room:
        """Return the Room at the given position."""
        ...

    def get_player_position(self) -> Position:
        """Current player position."""
        ...

    def get_wax_meter(self) -> int:
        """Current wax meter value (0–100)."""
        ...

    def get_game_status(self) -> GameStatus:
        """Current game status: PLAYING, WON, or LOST."""
        ...

    def get_available_directions(self) -> List[Direction]:
        """Attemptable directions from the player's current room (OPEN or LOCKED)."""
        ...

    def move(self, direction: Direction) -> str:
        """Attempt to move the player in the given direction."""
        ...

    def attempt_answer(self, answer_key: str) -> str:
        """Submit an answer for the trivia question in the player's current room."""
        ...

    def get_game_state(self) -> GameState:
        """Return a full GameState snapshot for serialization."""
        ...

    def restore_game_state(self, state: GameState) -> None:
        """Restore a game from a previously saved GameState."""
        ...

class Maze:
    """Concrete implementation of MazeProtocol."""

    def __init__(self, rows: int = 3, cols: int = 3,
                 trivia_data: Optional[List[TriviaQuestion]] = None):
        """Build a new maze.
        - rows, cols: grid dimensions (3×3 for the skeleton)
        - trivia_data: list of TriviaQuestion objects. If None, uses a built-in default set.
        """
        self.rows = rows
        self.cols = cols
        self.player_position = Position(0, 0)
        self.wax_meter = 0
        self.game_status = GameStatus.PLAYING
        self.answered_figures: List[str] = []
        self.visited_positions: List[Position] = [self.player_position]
        self.rooms: Dict[Tuple[int, int], Room] = {}
        
        # Build the 3x3 layout as specified in Section 5 of interfaces.md
        self._build_skeleton_maze()

    def _build_skeleton_maze(self):
        """Hardcodes the 3x3 layout defined in Section 5 of the spec."""
        # Initialize all rooms with WALLs in every direction
        for r in range(self.rows):
            for c in range(self.cols):
                pos = Position(r, c)
                self.rooms[(r, c)] = Room(
                    position=pos,
                    doors={d: DoorState.WALL for d in Direction}
                )

        # Connect rooms according to the spec's ASCII layout
        # (0,0) <-> (0,1) OPEN
        self._set_door(0, 0, Direction.EAST, 0, 1, Direction.WEST, DoorState.OPEN)
        # (0,1) <-> (0,2) OPEN
        self._set_door(0, 1, Direction.EAST, 0, 2, Direction.WEST, DoorState.OPEN)
        # (0,0) <-> (1,0) OPEN
        self._set_door(0, 0, Direction.SOUTH, 1, 0, Direction.NORTH, DoorState.OPEN)
        # (0,2) <-> (1,2) OPEN
        self._set_door(0, 2, Direction.SOUTH, 1, 2, Direction.NORTH, DoorState.OPEN)
        # (1,0) <-> (1,1) LOCKED (Da Vinci)
        self._set_door(1, 0, Direction.EAST, 1, 1, Direction.WEST, DoorState.LOCKED)
        # (1,1) <-> (2,1) OPEN
        self._set_door(1, 1, Direction.SOUTH, 2, 1, Direction.NORTH, DoorState.OPEN)
        # (2,1) <-> (2,2) LOCKED (Cleopatra)
        self._set_door(2, 1, Direction.EAST, 2, 2, Direction.WEST, DoorState.LOCKED)

        # Mark Entrance and Exit
        self.rooms[(0, 0)].is_entrance = True
        self.rooms[(2, 2)].is_exit = True

        # Assign Trivia Figures
        # (1,0) Leonardo da Vinci
        self.rooms[(1, 0)].trivia = TriviaQuestion(
            figure_name="Leonardo da Vinci",
            zone="Art Gallery",
            question_text="Who painted the Mona Lisa?",
            choices={"A": "Michelangelo", "B": "Leonardo da Vinci", "C": "Raphael"},
            correct_key="B"
        )
        # (2,1) Cleopatra
        self.rooms[(2, 1)].trivia = TriviaQuestion(
            figure_name="Cleopatra",
            zone="Egypt",
            question_text="Who was the last pharaoh of Ancient Egypt?",
            choices={"A": "Nefertiti", "B": "Cleopatra", "C": "Hatshepsut"},
            correct_key="B"
        )

    def _set_door(self, r1: int, c1: int, d1: Direction, r2: int, c2: int, d2: Direction, state: DoorState):
        """Internal helper to set bidirectional door state."""
        self.rooms[(r1, c1)].doors[d1] = state
        self.rooms[(r2, c2)].doors[d2] = state

    def get_rooms(self) -> Dict[Tuple[int, int], Room]:
        return self.rooms

    def get_room(self, position: Position) -> Room:
        if (position.row, position.col) not in self.rooms:
            raise KeyError(f"Position {position} is out of bounds.")
        return self.rooms[(position.row, position.col)]

    def get_player_position(self) -> Position:
        return self.player_position

    def get_wax_meter(self) -> int:
        return self.wax_meter

    def get_game_status(self) -> GameStatus:
        return self.game_status

    def get_available_directions(self) -> List[Direction]:
        room = self.get_room(self.player_position)
        return [d for d, state in room.doors.items() if state != DoorState.WALL]

    def move(self, direction: Direction) -> str:
        """Attempt to move the player. No change if wall or locked."""
        if self.game_status != GameStatus.PLAYING:
            return "invalid"
            
        room = self.get_room(self.player_position)
        door_state = room.doors.get(direction, DoorState.WALL)

        if door_state == DoorState.WALL:
            return "wall"
        if door_state == DoorState.LOCKED:
            return "locked"

        # Valid move through OPEN door
        new_row, new_col = self.player_position.row, self.player_position.col
        if direction == Direction.NORTH: new_row -= 1
        elif direction == Direction.SOUTH: new_row += 1
        elif direction == Direction.EAST: new_col += 1
        elif direction == Direction.WEST: new_col -= 1

        # Defensive check for grid boundaries (though layout is walled)
        if 0 <= new_row < self.rows and 0 <= new_col < self.cols:
            self.player_position = Position(new_row, new_col)
            if self.player_position not in self.visited_positions:
                self.visited_positions.append(self.player_position)
            
            # Check win condition
            if self.rooms[(new_row, new_col)].is_exit:
                self.game_status = GameStatus.WON
            
            return "moved"
        else:
            return "invalid"

    def attempt_answer(self, answer_key: str) -> str:
        """Submit trivia answer and unlock gates on success."""
        if self.game_status != GameStatus.PLAYING:
            return "game_over"

        room = self.get_room(self.player_position)
        if not room.trivia:
            return "no_trivia"

        if room.trivia.figure_name in self.answered_figures:
            return "already_answered"

        if answer_key.upper() == room.trivia.correct_key:
            # Correct answer: unlock bidirectional doors for the specific gates
            self.answered_figures.append(room.trivia.figure_name)
            if self.player_position == Position(1, 0):
                self._set_door(1, 0, Direction.EAST, 1, 1, Direction.WEST, DoorState.OPEN)
            elif self.player_position == Position(2, 1):
                self._set_door(2, 1, Direction.EAST, 2, 2, Direction.WEST, DoorState.OPEN)
            
            return "correct"
        else:
            # Wrong answer: penalty
            self.wax_meter += 25
            if self.wax_meter >= 100:
                self.wax_meter = 100
                self.game_status = GameStatus.LOST
            return "wrong"

    def get_game_state(self) -> GameState:
        """Return snapshot for serialization."""
        return GameState(
            player_position=self.player_position,
            wax_meter=self.wax_meter,
            game_status=self.game_status,
            answered_figures=self.answered_figures.copy(),
            visited_positions=self.visited_positions.copy(),
            door_states={pos: room.doors.copy() for pos, room in self.rooms.items()}
        )

    def restore_game_state(self, state: GameState) -> None:
        """Restore from snapshot."""
        if not (0 <= state.player_position.row < self.rows and 
                0 <= state.player_position.col < self.cols):
            raise ValueError("Invalid player position in restored state")

        self.player_position = state.player_position
        self.wax_meter = state.wax_meter
        self.game_status = state.game_status
        self.answered_figures = state.answered_figures.copy()
        self.visited_positions = state.visited_positions.copy()
        
        # Sync doors with saved state
        for pos_tuple, doors in state.door_states.items():
            if pos_tuple in self.rooms:
                self.rooms[pos_tuple].doors = doors.copy()
