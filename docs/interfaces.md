# Waxworks: The Midnight Curse — Module Interfaces

> MVP Spec · 5×5 Maze · Fog of War · SQLModel · View Separation
>
> Updated from walking skeleton based on converged RFC (`rfc_merged.md`).

---

## 1. Guiding Principles

| Rule | Why |
|------|-----|
| **maze.py imports nothing** | Domain logic is pure Python (`enum`, `dataclasses`, `typing` only). No I/O, no `print()`, no framework imports. |
| **db.py imports nothing from maze** | Persistence is a separate concern. It stores JSON-safe primitives only. Uses `sqlmodel` for SQLite. |
| **view.py imports maze types only** | Read-only type dependency (`Direction`, `DoorState`, `GameStatus`, `RoomVisibility`, `FogMapCell`, `Position`). Never calls Maze methods directly. |
| **main.py is the only wiring point** | It imports `maze`, `db`, and `view`, translates between them, and orchestrates the game loop. |
| **Data crosses boundaries as dicts/primitives** | Complex objects (dataclasses, Enums) are converted to dicts/strings at the boundary by `main.py`. |

---

## 2. Shared Vocabulary (Conceptual — not a shared import)

These types are **defined inside `maze.py`** but are never imported by `db.py`.
`view.py` may import them for type-safe rendering. When data must cross the
`maze ↔ db` boundary, `main.py` converts it.

### 2.1 Enumerations

```python
from enum import Enum

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

class RoomVisibility(Enum):
    """Fog of War visibility states."""
    HIDDEN = "hidden"        # Never seen — fog covers this room
    VISIBLE = "visible"      # Adjacent to player — can see but haven't entered
    VISITED = "visited"      # Player has been here before
    CURRENT = "current"      # Player is here right now
```

### 2.2 Dataclasses

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class Position:
    """A (row, col) coordinate in the maze grid. Immutable."""
    row: int
    col: int

@dataclass
class Room:
    """One cell of the maze grid.
    Every room defines all four cardinal directions in its doors dict.
    Grid-edge directions are represented as DoorState.WALL.
    Rooms no longer store TriviaQuestion — only which figure lives there.
    """
    position: Position
    doors: dict[Direction, DoorState]
    figure_name: str | None = None    # Which wax figure lives here (None = corridor)
    zone: str | None = None           # Thematic zone ("Art Gallery", etc.)
    is_entrance: bool = False
    is_exit: bool = False

@dataclass
class FogMapCell:
    """One cell in the fog-of-war map representation.
    The View uses this to render the map without calling Maze methods.
    """
    position: Position
    visibility: RoomVisibility
    has_trivia: bool = False         # True if room has a wax figure
    figure_name: str | None = None   # Name of the figure (only if VISITED/CURRENT)
    is_entrance: bool = False
    is_exit: bool = False
    doors: dict[Direction, DoorState] | None = None  # Only if VISIBLE/VISITED/CURRENT

@dataclass
class GameState:
    """Complete snapshot of a game in progress."""
    player_position: Position
    curse_level: int                # 0–100 (the curse consumes you)
    game_status: GameStatus
    defeated_figures: list[str]     # figure_name values already cleared
    visited_positions: list[Position]
    door_states: dict[tuple[int, int], dict[Direction, DoorState]]
    # Fog is computed from visited_positions — not stored
```

> **Removed:** `TriviaQuestion` dataclass. Questions are now fetched from the DB at runtime by the Engine via `repo.get_random_question(figure_name)` and passed to the View as a plain dict.

---

## 3. Module Interfaces (Protocols)

### 3.1 `maze.py` — Domain Logic

The Maze class owns all game rules. It exposes **pure data** — no I/O.

```python
from typing import Protocol

class MazeProtocol(Protocol):
    """Public contract for the Maze domain object."""

    def get_rooms(self) -> dict[tuple[int, int], Room]:
        """Return the full room grid keyed by (row, col)."""
        ...

    def get_room(self, position: Position) -> Room:
        """Return the Room at the given position.
        Raises KeyError if position is out of bounds."""
        ...

    def get_player_position(self) -> Position:
        """Current player position."""
        ...

    def get_curse_level(self) -> int:
        """Current curse level (0–100)."""
        ...

    def get_game_status(self) -> GameStatus:
        """Current game status: PLAYING, WON, or LOST."""
        ...

    def get_available_directions(self) -> list[Direction]:
        """Attemptable directions from the player's current room.
        Returns all directions where the door is OPEN or LOCKED (excludes WALL)."""
        ...

    def move(self, direction: Direction) -> str:
        """Attempt to move the player in the given direction.
        Returns a status message string:
          - "moved"   — success
          - "locked"  — passage is locked
          - "wall"    — impassable (includes grid borders)
          - "invalid" — defensive fallback
        Side effects: updates player_position, visited_positions if successful.
        """
        ...

    def attempt_answer(self, answer_key: str, correct_key: str) -> str:
        """Submit an answer for the figure in the player's current room.
        The Engine passes the correct_key fetched from the DB.
        Returns:
          - "correct"          — gates unlock, figure added to defeated list
          - "wrong"            — curse_level increases (+20), gates stay locked
          - "no_figure"        — current room has no figure
          - "already_answered" — figure was already defeated
          - "game_over"        — game_status is not PLAYING; no action taken
        Side effects: may update curse_level, game_status, doors.
        Doors are bidirectional: unlocking updates both sides of the connection.
        """
        ...

    def get_fog_map(self) -> list[list[FogMapCell]]:
        """Return a 2D grid of FogMapCell for the View to render.

        Visibility rules:
        - CURRENT: the room the player is in
        - VISITED: rooms the player has previously entered
        - VISIBLE: rooms adjacent to the player's current room (can see doors)
        - HIDDEN: everything else (no info leaked)
        """
        ...

    def is_solvable(self) -> bool:
        """Run BFS from entrance to exit, treating LOCKED doors as passable
        (assumes player will eventually answer correctly).
        Returns True if a path exists."""
        ...

    def get_game_state(self) -> GameState:
        """Return a full GameState snapshot for serialization."""
        ...

    def restore_game_state(self, state: GameState) -> None:
        """Restore a game from a previously saved GameState.
        Raises ValueError if the state is invalid."""
        ...
```

#### Construction

```python
class Maze:
    """Concrete implementation of MazeProtocol."""

    def __init__(self, rows: int = 5, cols: int = 5,
                 trivia_data: list[dict] | None = None):
        """Build a new maze.
        - rows, cols: grid dimensions (5×5 for the MVP)
        - trivia_data: list of dicts with figure_name, zone, and room positions.
          If None, uses the built-in 5×5 layout.
        """
```

#### Curse Level Rules (MVP)

| Event | Curse Level Change |
|-------|--------------------|
| Wrong answer | +20 |
| Correct answer | +0 |
| Curse reaches 100 | GameStatus → LOST |

> 5 wrong answers = game over. Player **can retry** the same question.

#### Win Condition

Player reaches a room where `is_exit == True` and `game_status == PLAYING`.

---

### 3.2 `db.py` — Persistence (SQLModel + SQLite)

The repository stores and retrieves **JSON-safe dictionaries only**.
It has **no knowledge** of `Position`, `Direction`, or any maze type.
Backed by SQLModel + SQLite instead of flat JSON files.

```python
class RepositoryProtocol(Protocol):
    """Public contract for SQLModel-backed persistence."""

    # -- Save / Load (BREAKING: filepath → slot_name, JSON file → SQLite) --
    def save(self, data: dict, slot_name: str = "default") -> None:
        """Persist a JSON-safe dict to the database.
        Internally serializes the dict to JSON text and stores in SaveRecord.
        Raises IOError on write failure."""
        ...

    def load(self, slot_name: str = "default") -> dict | None:
        """Load a previously saved dict. Returns None if slot not found.
        Raises ValueError if stored data is corrupt."""
        ...

    # -- Question Bank (NEW) --
    def get_random_question(self, figure_name: str) -> dict | None:
        """Return a random unasked question for a specific wax figure.
        Filters by figure_name so each figure only asks from their own pool.
        Dict keys: figure_name, zone, question_text, choices, correct_key.
        Side effect: marks the question as asked (has_been_asked = True).
        Returns None if all questions for that figure have been asked."""
        ...

    def reset_questions(self) -> None:
        """Reset all questions to unasked (for new game)."""
        ...

    def seed_questions(self, questions: list[dict]) -> None:
        """Populate the Question Bank from a list of dicts (idempotent)."""
        ...
```

#### SQLModel Schema

```python
from sqlmodel import SQLModel, Field
from typing import Optional

class FigureRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    zone: str
    is_defeated: bool = False

class QuestionRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    figure_name: str
    zone: str
    question_text: str
    choice_a: str
    choice_b: str
    choice_c: str
    correct_key: str
    has_been_asked: bool = False

class SaveRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slot_name: str = "default"
    state_json: str
```

---

### 3.3 `main.py` — Engine (The Wiring)

The engine is the **only module** that imports `maze`, `db`, and `view`.
It owns the game loop, trivia-from-DB flow, and translation layer.

```python
class Engine:
    """Orchestrates the game loop."""

    def __init__(self, maze: MazeProtocol, repo: RepositoryProtocol,
                 view: "ViewProtocol", save_filepath: str = "waxworks.db"):
        """Inject dependencies. View is the new rendering module."""
        ...

    # ---- Translation Layer (the boundary glue) ----

    @staticmethod
    def game_state_to_dict(state: GameState) -> dict:
        """Convert a GameState dataclass to a JSON-safe dict.
        - Position → {"row": int, "col": int}
        - GameStatus → str (e.g., "playing")
        - Direction/DoorState Enums → str values
        - curse_level, defeated_figures serialized as-is
        """
        ...

    @staticmethod
    def dict_to_game_state(data: dict) -> GameState:
        """Convert a JSON-safe dict back to a GameState dataclass.
        Raises ValueError if the dict is malformed.
        """
        ...

    # ---- I/O Layer ----

    def save_game(self) -> None:
        """Get state from maze → convert to dict → pass to repo.save()."""
        ...

    def load_game(self) -> bool:
        """repo.load() → convert dict to GameState → maze.restore().
        Returns True if load succeeded, False otherwise."""
        ...

    def run(self) -> None:
        """Main game loop:
        1. Display fog map and current room (via View).
        2. If room has undefeated figure: fetch question from DB, display confrontation.
        3. Read player input (via View).
        4. Dispatch to maze.move() or maze.attempt_answer(answer, correct_key).
        5. Check win/loss conditions.
        6. Repeat until game_status != PLAYING.
        """
        ...
```

#### Accepted Commands

| Command | Effect |
|--------|--------|
| `move <north\|south\|east\|west>` | Attempt to move in the given direction |
| `answer <A\|B\|C>` | Answer the figure's question in the current room |
| `save` | Save game to SQLite |
| `load` | Load game from SQLite |
| `map` | Redraw the fog map |
| `help` | Show available commands |
| `quit` | Exit the game |

---

### 3.4 `view.py` — View / UI (NEW — Role 4)

Dedicated rendering module. Receives pure data, produces themed CLI output.
May use `print()` and `input()`. Must NOT import `db`.

```python
class ViewProtocol(Protocol):
    """Public contract for the View rendering module."""

    def display_welcome(self) -> None:
        """Show the themed welcome banner."""
        ...

    def display_room(self, room: Room, position: Position,
                     curse_level: int, game_state: GameState) -> None:
        """Display the current room description with zone flavor text."""
        ...

    def display_fog_map(self, fog_map: list[list[FogMapCell]]) -> None:
        """Render the fog-of-war ASCII map."""
        ...

    def display_move_result(self, result: str, direction: str) -> None:
        """Display the result of a move attempt."""
        ...

    def display_confrontation(self, question_dict: dict) -> None:
        """Display a wax figure confrontation with the trivia question."""
        ...

    def display_answer_result(self, result: str, curse_level: int) -> None:
        """Display the result of answering a question."""
        ...

    def display_save_result(self, success: bool, error: str = "") -> None:
        """Display save confirmation or error."""
        ...

    def display_load_result(self, success: bool) -> None:
        """Display load confirmation or failure."""
        ...

    def display_endgame(self, status: GameStatus, curse_level: int) -> None:
        """Display victory or game-over sequence."""
        ...

    def display_error(self, message: str) -> None:
        """Display an error message."""
        ...

    def get_input(self, prompt: str = "> ") -> str:
        """Read player input from the CLI."""
        ...
```

---

## 4. Boundary Crossing

```
┌─────────────┐     dict/pure     ┌────────────┐     dict/JSON     ┌──────────┐
│  maze.py    │  ──GameState──▶   │  main.py   │  ──JSON-safe──▶   │  db.py   │
│  (Position, │  ◀──GameState──   │  (Engine)  │  ◀──JSON-safe──   │ (SQLite) │
│   Enums)    │                   │            │                   │          │
└─────┬───────┘                   └────────────┘                   └──────────┘
      │ types only                       │
      ▼                                  ▼
┌─────────────┐                  orchestrates
│  view.py    │ ◀── pure data ── │  Engine    │
│  (renders)  │                  │            │
└─────────────┘                  └────────────┘
```

**Serialization rules (owned by `main.py`):**

| Maze Type | JSON Representation |
|-----------|-------------------|
| `Position(row=1, col=2)` | `{"row": 1, "col": 2}` |
| `GameStatus.PLAYING` | `"playing"` |
| `Direction.NORTH` | `"north"` |
| `DoorState.LOCKED` | `"locked"` |
| `list[Position]` | `[{"row": r, "col": c}, ...]` |
| `curse_level` | `int` (direct) |
| `defeated_figures` | `list[str]` (direct) |

---

## 5. Dependency Rules

| Module | May Import | May NOT Import | `print()`/`input()` |
|--------|-----------|----------------|---------------------|
| `maze.py` | `enum`, `dataclasses`, `typing` | `db`, `main`, `view` | **No** |
| `db.py` | `sqlmodel`, `typing`, stdlib | `maze`, `main`, `view` | **No** |
| `view.py` | `maze` (types only), stdlib | `db` | `print()` **Yes**, `input()` **Yes** |
| `main.py` | `maze`, `db`, `view`, stdlib | — | **Yes** (via `view`) |

---

## 6. MVP Maze Layout (5×5)

```
  WAXWORKS MUSEUM — 5×5 MAZE LAYOUT
  (all connections — horizontal AND vertical — fully specified)

    Col 0         Col 1         Col 2         Col 3         Col 4
  ┌───────────┬───────────┬───────────┬───────────┬───────────┐
  │ ENTRANCE  │           │           │           │           │
  │ (0,0)   ──── (0,1)  ──── (0,2)   │           │           │
  │ is_entr   │  corridor │  corridor │           │           │
  │     │     │           │           │           │           │
  │   SOUTH   │           │           │           │           │
  │     ↓     │           │           │           │           │
  ├───────────┼───────────┼───────────┼───────────┼───────────┤
  │           │ DA VINCI  │           │           │           │
  │ (1,0)   ──── (1,1)  ═🔒═ (1,2)  ──── (1,3)  │           │
  │ corridor  │ 🗿Art Gal │  corridor │  corridor │           │
  │           │           │     │     │           │           │
  │           │           │   SOUTH   │           │           │
  │           │           │     ↓     │           │           │
  ├───────────┼───────────┼───────────┼───────────┼───────────┤
  │           │           │ LINCOLN   │           │           │
  │           │ (2,1)   ──── (2,2)  ═🔒═ (2,3)  ──── (2,4)  │
  │           │ corridor  │ 🗿Amer H │  corridor │  corridor │
  │           │           │           │     │     │           │
  │           │           │           │   SOUTH   │           │
  │           │           │           │     ↓     │           │
  ├───────────┼───────────┼───────────┼───────────┼───────────┤
  │           │           │           │ CLEOPATRA │           │
  │           │           │ (3,2)   ──── (3,3)  ═🔒═ (3,4)  │
  │           │           │ corridor  │ 🗿Anc Hist│  corridor │
  │           │           │           │           │     │     │
  │           │           │           │           │   SOUTH   │
  │           │           │           │           │     ↓     │
  ├───────────┼───────────┼───────────┼───────────┼───────────┤
  │           │           │           │           │   EXIT    │
  │           │           │           │ (4,3)   ──── (4,4)   │
  │           │           │           │ corridor  │ is_exit   │
  └───────────┴───────────┴───────────┴───────────┴───────────┘

  Legend:  ──── = OPEN passage (horizontal)
           ═🔒═ = LOCKED gate (unlocked by defeating figure)
           ↓    = OPEN passage (vertical / SOUTH↔NORTH)
           │    = WALL (no connection)
           🗿   = Wax figure room
```

#### Complete Room Connection Table

Only connected rooms are listed. All other direction pairs are **WALL**.
All connections are **bidirectional** (e.g., (0,0) EAST→(0,1) means (0,1) WEST→(0,0) is also OPEN).

| From | Direction | To | DoorState | Notes |
|------|-----------|-----|-----------|-------|
| (0,0) | EAST | (0,1) | OPEN | Top corridor |
| (0,0) | SOUTH | (1,0) | OPEN | Down to Da Vinci's row |
| (0,1) | EAST | (0,2) | OPEN | Top corridor |
| (1,0) | EAST | (1,1) | OPEN | Approach Da Vinci from west |
| (1,1) | EAST | (1,2) | **LOCKED** 🔒 | Da Vinci's gate |
| (1,2) | EAST | (1,3) | OPEN | Post–Da Vinci corridor |
| (1,2) | SOUTH | (2,1) | OPEN | ⬇ Drop to Lincoln's row **west** side |
| (2,1) | EAST | (2,2) | OPEN | Approach Lincoln from west |
| (2,2) | EAST | (2,3) | **LOCKED** 🔒 | Lincoln's gate |
| (2,3) | EAST | (2,4) | OPEN | Post–Lincoln corridor |
| (2,3) | SOUTH | (3,2) | OPEN | ⬇ Drop to Cleopatra's row **west** side |
| (3,2) | EAST | (3,3) | OPEN | Approach Cleopatra from west |
| (3,3) | EAST | (3,4) | **LOCKED** 🔒 | Cleopatra's gate |
| (3,4) | SOUTH | (4,4) | OPEN | ⬇ Drop straight to EXIT |
| (4,3) | EAST | (4,4) | OPEN | Alternate approach to exit |

> **Key design:** South connections drop the player to the **west** side of the next figure's row, ensuring they always approach figures from the correct side.
> Rooms not in this table (e.g., (0,3), (0,4), (2,0), (3,0), etc.) are unused — all four doors are WALL.

#### Room Index

| Room | Role | Figure |
|------|------|--------|
| (0,0) | **Entrance** | — |
| (0,1), (0,2) | Corridor (exploration) | — |
| (1,0) | Corridor (approach) | — |
| (1,1) | 🗿 Wax Figure Room | Leonardo da Vinci (Art Gallery) |
| (1,2), (1,3) | Corridor (post–Da Vinci) | — |
| (2,1) | Corridor (approach) | — |
| (2,2) | 🗿 Wax Figure Room | Abraham Lincoln (American History) |
| (2,3), (2,4) | Corridor (post–Lincoln) | — |
| (3,2) | Corridor (approach) | — |
| (3,3) | 🗿 Wax Figure Room | Cleopatra (Ancient History) |
| (3,4) | Corridor (post–Cleopatra) | — |
| (4,3) | Corridor | — |
| (4,4) | **Exit** | — |
| All others | Unused (all walls) | — |

#### Winning Path (exact steps, verified)

```
(0,0) →S→ (1,0) →E→ (1,1)   — confront Da Vinci 🗿
  defeat → gate (1,1)↔(1,2) unlocks
(1,1) →E→ (1,2) →S→ (2,1) →E→ (2,2)   — confront Lincoln 🗿
  defeat → gate (2,2)↔(2,3) unlocks
(2,2) →E→ (2,3) →S→ (3,2) →E→ (3,3)   — confront Cleopatra 🗿
  defeat → gate (3,3)↔(3,4) unlocks
(3,3) →E→ (3,4) →S→ (4,4)   — EXIT! 🎉
```

**Shortest winning path:** 10 moves + 3 correct answers = 13 actions

> [!IMPORTANT]
> **Staircase pattern:** Each figure is approached from the WEST. Their locked gate blocks EAST progress. After defeating a figure and passing east, the south connection drops the player to the **west** of the next figure's row — creating a natural **zigzag** down the grid.

---

*Document version: 2.1 — MVP · Waxworks: The Midnight Curse · Based on rfc_merged.md*

