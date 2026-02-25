# Waxworks: The Midnight Curse — Module Interfaces

> Walking Skeleton Spec · 3×3 Maze · CLI-Based

---

## 1. Guiding Principles

| Rule | Why |
|------|-----|
| **maze.py imports nothing** | Domain logic is pure Python. No I/O, no `print()`, no framework imports. |
| **db.py imports nothing from maze** | Persistence is a separate concern. It stores JSON-safe primitives only. |
| **main.py is the only wiring point** | It imports both `maze` and `db`, translates between them, and owns all I/O (`input()` / `print()`). |
| **Data crosses boundaries as dicts/primitives** | Complex objects (dataclasses, Enums) are converted to dicts/strings at the boundary by `main.py`. |

---

## 2. Shared Vocabulary (Conceptual — not a shared import)

These types are **defined inside `maze.py`** but are never imported by `db.py`.
When data must cross the boundary, `main.py` converts it.

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
class TriviaQuestion:
    """A single trivia question attached to a wax figure."""
    figure_name: str       # e.g. "Leonardo da Vinci"
    zone: str              # e.g. "Art Gallery"
    question_text: str
    choices: dict[str, str] # {"A": "...", "B": "...", "C": "..."}
    correct_key: str        # "A", "B", or "C"

@dataclass
class Room:
    """One cell of the maze grid.
    Every room defines all four cardinal directions in its doors dict.
    Grid-edge directions are represented as DoorState.WALL (e.g. (0,0): NORTH: WALL, WEST: WALL).
    """
    position: Position
    doors: dict[Direction, DoorState]          # What's in each direction
    trivia: Optional[TriviaQuestion] = None    # None means ordinary corridor
    is_entrance: bool = False
    is_exit: bool = False

@dataclass
class GameState:
    """Complete snapshot of a game in progress."""
    player_position: Position
    wax_meter: int                  # 0–100
    game_status: GameStatus
    answered_figures: list[str]     # figure_name values already cleared
    visited_positions: list[Position]
    door_states: dict[tuple[int, int], dict[Direction, DoorState]]  # current state of every door (unlocked doors survive save/load)
```

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

    def get_wax_meter(self) -> int:
        """Current wax meter value (0–100)."""
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
          - Success:  "moved"
          - Locked:   "locked"
          - Wall:     "wall" (includes grid borders; every room has all four directions, edges are WALL)
          - Off-grid: "invalid" (defensive; not expected in skeleton layout)
        Side effects: updates player_position if successful.
        """
        ...

    def attempt_answer(self, answer_key: str) -> str:
        """Submit an answer (\"A\", \"B\", or \"C\") for the trivia
        question in the player's current room.
        Returns:
          - "correct"   — door unlocks, figure added to answered list
          - "wrong"     — wax_meter increases, door stays locked
          - "no_trivia" — current room has no trivia question
          - "already_answered" — figure was already cleared
          - "game_over" — game_status is not PLAYING; no action taken
        Side effects: may update wax_meter, game_status, doors.
        Doors are bidirectional: unlocking a door updates both sides of the
        connection (e.g. answering at (1,0) sets both (1,0).EAST and (1,1).WEST to OPEN).
        """
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

    def __init__(self, rows: int = 3, cols: int = 3,
                 trivia_data: list[TriviaQuestion] | None = None):
        """Build a new maze.
        - rows, cols: grid dimensions (3×3 for the skeleton)
        - trivia_data: list of TriviaQuestion objects. If None, uses a built-in default set.
        """
```

#### Wax Meter Rules (Skeleton)

| Event | Wax Meter Change |
|-------|-----------------|
| Wrong answer | +25 |
| Correct answer | +0 |
| Meter reaches 100 | GameStatus → LOST |

#### Win Condition

Player reaches a room where `is_exit == True` and `game_status == PLAYING`.

---

### 3.2 `db.py` — Persistence (JSON I/O)

The repository stores and retrieves **JSON-safe dictionaries only**.
It has **no knowledge** of `Position`, `Direction`, or any maze type.

```python
class RepositoryProtocol(Protocol):
    """Public contract for game-state persistence."""

    def save(self, data: dict, filepath: str = "save_game.json") -> None:
        """Persist a JSON-safe dict to a file.
        Raises IOError on write failure."""
        ...

    def load(self, filepath: str = "save_game.json") -> dict | None:
        """Load a previously saved dict from a file.
        Returns None if the file does not exist.
        Raises ValueError if the file is corrupt / not valid JSON."""
        ...
```

#### JSON Schema (what gets saved)

```json
{
  "player_position": {"row": 1, "col": 0},
  "wax_meter": 25,
  "game_status": "playing",
  "answered_figures": ["Leonardo da Vinci"],
  "visited_positions": [
    {"row": 0, "col": 0},
    {"row": 1, "col": 0}
  ],
  "door_states": [
    {
      "position": {"row": 0, "col": 0},
      "doors": {"north": "wall", "south": "open", "east": "open", "west": "wall"}
    }
  ]
}
```

> **Key design decision:** `main.py` is responsible for converting
> `GameState ↔ dict`. `db.py` never sees a `Position` object — it only
> sees `{"row": 1, "col": 0}`.

---

### 3.3 `main.py` — Engine (The Wiring)

The engine is the **only module** that imports both `maze` and `db`.
It owns all user-facing I/O and the translation layer.

```python
class Engine:
    """Orchestrates the game loop."""

    def __init__(self, maze: MazeProtocol, repo: RepositoryProtocol):
        """Inject dependencies."""
        ...

    # ---- Translation Layer (the boundary glue) ----

    @staticmethod
    def game_state_to_dict(state: GameState) -> dict:
        """Convert a GameState dataclass to a JSON-safe dict.
        - Position → {"row": int, "col": int}
        - GameStatus → str (e.g., "playing")
        - Direction/DoorState Enums → str values
        - door_states → list of {"position": {...}, "doors": {direction: str, ...}}
        """
        ...

    @staticmethod
    def dict_to_game_state(data: dict) -> GameState:
        """Convert a JSON-safe dict back to a GameState dataclass.
        Includes door_states (list of position + doors) → dict keyed by (row, col).
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
        1. Display current room, available directions, wax meter.
        2. Read player input (move / answer / save / quit).
        3. Dispatch to maze.move() or maze.attempt_answer().
        4. Check win/loss conditions.
        5. Repeat until game_status != PLAYING.
        """
        ...
```

#### Accepted Commands

| Command | Effect |
|--------|--------|
| `move <north\|south\|east\|west>` | Attempt to move in the given direction |
| `answer <A\|B\|C>` | Answer the trivia question in the current room |
| `save` | Save game to file |
| `load` | Load game from file |
| `quit` | Exit the game |

---

## 4. Boundary Crossing — The Position Problem

This is the most architecturally important detail.

```
┌─────────────┐       dict        ┌────────────┐       dict        ┌──────────┐
│  maze.py    │  ──GameState──▶   │  main.py   │  ──JSON-safe──▶   │  db.py   │
│  (Position, │  ◀──GameState──   │  (converts) │  ◀──JSON-safe──   │  (dicts)  │
│   Enums)    │                   │             │                   │          │
└─────────────┘                   └────────────┘                   └──────────┘
```

**Serialization rules (owned by `main.py`):**

| Maze Type | JSON Representation |
|-----------|-------------------|
| `Position(row=1, col=2)` | `{"row": 1, "col": 2}` |
| `GameStatus.PLAYING` | `"playing"` |
| `Direction.NORTH` | `"north"` |
| `DoorState.LOCKED` | `"locked"` |
| `list[Position]` | `[{"row": r, "col": c}, ...]` |
| `dict[tuple, dict[Direction, DoorState]]` (door_states) | `[{"position": {"row": r, "col": c}, "doors": {"north": "...", ...}}, ...]` |

---

## 5. Walking Skeleton Maze Layout (3×3)

Both wax figures are mandatory gates; there is no route to the exit that bypasses either of them.

```
 (0,0)  ──OPEN──  (0,1)  ──OPEN──   (0,2)
   │                │                    │
  OPEN            WALL               OPEN
   │                │                    │
 (1,0)  ──LOCKED── (1,1)  ──WALL──  (1,2)
   │                │                    │
  WALL            OPEN              WALL
   │                │                    │
 (2,0)  ──WALL──  (2,1)  ──LOCKED── (2,2)
```

| Room | Role | Trivia |
|------|------|--------|
| (0,0) | **Entrance** | — |
| (1,0) | Wax Figure Room | Leonardo da Vinci (east door LOCKED until answered) |
| (2,1) | Wax Figure Room | Cleopatra (east door LOCKED until answered) |
| (2,2) | **Exit** | — |
| (0,1), (0,2), (1,2) | Corridors / dead-end branch | — |

**Winning path:** (0,0) → (1,0) answer Da Vinci → (1,1) → (2,1) answer Cleopatra → (2,2) exit.

---

*Document version: 1.0 — Walking Skeleton · Waxworks: The Midnight Curse*
