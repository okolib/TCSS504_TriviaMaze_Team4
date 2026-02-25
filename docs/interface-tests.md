# Waxworks: The Midnight Curse — Interface Tests

> Contract tests that each module must pass before integration.
> Each test is independent — a module owner can run their suite without the other modules.

---

## 1. Test Philosophy

Each module is developed on its own `feat/` branch. Before a PR is opened,
the module must pass every test in its contract section below. Tests use only
`pytest` and the Python standard library — no external mocking frameworks needed
for the skeleton.

---

## 2. `test_maze_contract.py` — Domain Logic Tests

> **Owner:** Domain Owner (`maze.py`)
> **Imports:** `from maze import Maze, Position, Direction, DoorState, GameStatus, TriviaQuestion, GameState`
> **Constraint:** No file I/O, no `print()`, no imports of `db` or `main`.

### 2.1 Construction & Layout

```python
def test_maze_creates_3x3_grid():
    """Maze has exactly 9 rooms keyed by (row, col)."""
    m = Maze(rows=3, cols=3)
    rooms = m.get_rooms()
    assert len(rooms) == 9
    for r in range(3):
        for c in range(3):
            assert (r, c) in rooms

def test_entrance_is_at_0_0():
    """Room (0,0) is marked as the entrance."""
    m = Maze()
    room = m.get_room(Position(0, 0))
    assert room.is_entrance is True

def test_exit_exists():
    """At least one room is marked as the exit."""
    m = Maze()
    rooms = m.get_rooms()
    exits = [r for r in rooms.values() if r.is_exit]
    assert len(exits) >= 1

def test_trivia_rooms_exist():
    """At least two rooms contain trivia questions (for 3×3 skeleton)."""
    m = Maze()
    rooms = m.get_rooms()
    trivia_rooms = [r for r in rooms.values() if r.trivia is not None]
    assert len(trivia_rooms) >= 2
```

### 2.2 Movement — Happy Path

```python
def test_player_starts_at_entrance():
    """Player initial position is (0,0)."""
    m = Maze()
    assert m.get_player_position() == Position(0, 0)

def test_move_through_open_door():
    """Moving through an OPEN door updates player position."""
    m = Maze()
    # (0,0) south door should be OPEN per skeleton layout
    result = m.move(Direction.SOUTH)
    assert result == "moved"
    assert m.get_player_position() == Position(1, 0)

def test_available_directions_excludes_walls():
    """get_available_directions() never includes WALL directions."""
    m = Maze()
    room = m.get_room(m.get_player_position())
    available = m.get_available_directions()
    for d in available:
        assert room.doors[d] != DoorState.WALL
```

### 2.3 Movement — Edge Cases

```python
def test_move_into_wall_rejected():
    """Moving into a WALL returns 'wall' and position is unchanged."""
    m = Maze()
    pos_before = m.get_player_position()
    # (0,0) has NORTH and WEST as WALL per skeleton layout
    room = m.get_room(pos_before)
    wall_dirs = [d for d, s in room.doors.items() if s == DoorState.WALL]
    assert len(wall_dirs) > 0, "Expected at least one WALL direction at (0,0)"
    result = m.move(wall_dirs[0])
    assert result == "wall"
    assert m.get_player_position() == pos_before

def test_move_into_locked_door_rejected():
    """Moving through a LOCKED door returns 'locked'; position unchanged."""
    m = Maze()
    # (1,0) has LOCKED east toward (1,1) — Da Vinci room
    m.move(Direction.SOUTH)   # (0,0) -> (1,0)
    pos_before = m.get_player_position()
    room = m.get_room(pos_before)
    locked_dirs = [d for d, s in room.doors.items() if s == DoorState.LOCKED]
    assert len(locked_dirs) > 0, "Expected at least one LOCKED direction at (1,0)"
    result = m.move(locked_dirs[0])
    assert result == "locked"
    assert m.get_player_position() == pos_before

def test_move_into_border_wall_rejected():
    """Moving into a border (e.g. north from (0,0)) returns 'wall'; position unchanged."""
    m = Maze()
    # Player starts at (0,0) — north is grid edge, represented as WALL
    result = m.move(Direction.NORTH)
    assert result == "wall"
    assert m.get_player_position() == Position(0, 0)
```

### 2.4 Trivia — Happy Path

```python
def test_correct_answer_unlocks_door():
    """Answering correctly returns 'correct' and unlocks the passage."""
    m = Maze()
    # Navigate to a trivia room (implementation-specific path)
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    assert room.trivia is not None
    result = m.attempt_answer(room.trivia.correct_key)
    assert result == "correct"

def test_correct_answer_does_not_increase_wax():
    """Wax meter stays the same after a correct answer."""
    m = Maze()
    _navigate_to_trivia_room(m)
    wax_before = m.get_wax_meter()
    room = m.get_room(m.get_player_position())
    m.attempt_answer(room.trivia.correct_key)
    assert m.get_wax_meter() == wax_before
```

### 2.5 Trivia — Failure / Wax Meter

```python
def test_wrong_answer_increases_wax():
    """Wrong answer increases wax meter by 25."""
    m = Maze()
    _navigate_to_trivia_room(m)
    wax_before = m.get_wax_meter()
    room = m.get_room(m.get_player_position())
    wrong_key = _get_wrong_key(room.trivia.correct_key)
    m.attempt_answer(wrong_key)
    assert m.get_wax_meter() == wax_before + 25

def test_wrong_answer_keeps_door_locked():
    """Door stays locked after a wrong answer."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room_before = m.get_room(m.get_player_position())
    locked_dirs = [d for d, s in room_before.doors.items()
                   if s == DoorState.LOCKED]
    wrong_key = _get_wrong_key(room_before.trivia.correct_key)
    m.attempt_answer(wrong_key)
    room_after = m.get_room(m.get_player_position())
    for d in locked_dirs:
        assert room_after.doors[d] == DoorState.LOCKED

def test_wax_meter_at_100_means_game_over():
    """When wax meter hits 100, game status becomes LOST."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    wrong_key = _get_wrong_key(room.trivia.correct_key)
    # Answer wrong 4 times (4 × 25 = 100)
    for _ in range(4):
        if m.get_game_status() != GameStatus.PLAYING:
            break
        m.attempt_answer(wrong_key)
    assert m.get_wax_meter() >= 100
    assert m.get_game_status() == GameStatus.LOST

def test_wax_meter_never_exceeds_100():
    """Wax meter is capped at 100."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    wrong_key = _get_wrong_key(room.trivia.correct_key)
    for _ in range(10):
        m.attempt_answer(wrong_key)
    assert m.get_wax_meter() <= 100

def test_attempt_answer_after_game_over():
    """attempt_answer returns 'game_over' once the game is no longer PLAYING."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    wrong_key = _get_wrong_key(room.trivia.correct_key)
    for _ in range(4):
        m.attempt_answer(wrong_key)
    assert m.get_game_status() == GameStatus.LOST
    wax_before = m.get_wax_meter()
    result = m.attempt_answer(wrong_key)
    assert result == "game_over"
    assert m.get_wax_meter() == wax_before  # no state change

def test_no_trivia_in_empty_room():
    """attempt_answer in a room without trivia returns 'no_trivia'."""
    m = Maze()
    # (0,0) is the entrance — no trivia
    result = m.attempt_answer("A")
    assert result == "no_trivia"

def test_already_answered_trivia():
    """Answering a cleared figure returns 'already_answered'."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    m.attempt_answer(room.trivia.correct_key)
    result = m.attempt_answer(room.trivia.correct_key)
    assert result == "already_answered"
```

### 2.6 Game State Snapshot

```python
def test_get_game_state_returns_dataclass():
    """get_game_state() returns a GameState instance."""
    m = Maze()
    state = m.get_game_state()
    assert isinstance(state, GameState)
    assert state.player_position == Position(0, 0)
    assert state.wax_meter == 0
    assert state.game_status == GameStatus.PLAYING
    assert hasattr(state, "door_states") and isinstance(state.door_states, dict)

def test_restore_game_state_roundtrip():
    """Saving and restoring state reproduces the same game."""
    m = Maze()
    m.move(Direction.SOUTH)
    state = m.get_game_state()
    m2 = Maze()
    m2.restore_game_state(state)
    assert m2.get_player_position() == state.player_position
    assert m2.get_wax_meter() == state.wax_meter
    assert m2.get_game_status() == state.game_status
    assert m2.get_game_state().door_states == state.door_states

def test_restore_preserves_unlocked_doors():
    """After answering trivia correctly, save and restore; unlocked door stays open."""
    m = Maze()
    _navigate_to_trivia_room(m)
    room = m.get_room(m.get_player_position())
    assert m.attempt_answer(room.trivia.correct_key) == "correct"
    state = m.get_game_state()
    m2 = Maze()
    m2.restore_game_state(state)
    # Bidirectional: both (1,0).EAST and (1,1).WEST must be OPEN after Da Vinci
    room_10_after = m2.get_room(Position(1, 0))
    room_11_after = m2.get_room(Position(1, 1))
    assert room_10_after.doors[Direction.EAST] == DoorState.OPEN
    assert room_11_after.doors[Direction.WEST] == DoorState.OPEN
```

### 2.7 Test Helpers

```python
def _navigate_to_trivia_room(m):
    """Move player to the nearest room with trivia.
    Skeleton layout: (0,0) → south → (1,0). Room (1,0) has Leonardo da Vinci trivia.
    """
    m.move(Direction.SOUTH)   # (0,0) → (1,0)

def _get_wrong_key(correct_key: str) -> str:
    """Return an answer key that is NOT the correct one."""
    keys = ["A", "B", "C"]
    keys.remove(correct_key)
    return keys[0]
```

---

## 3. `test_repo_contract.py` — Persistence Tests

> **Owner:** Persistence Owner (`db.py`)
> **Imports:** `from db import Repository` (or whatever the concrete class is named)
> **Constraint:** No imports from `maze` or `main`. Tests use plain dicts.

### 3.1 Save & Load — Happy Path

```python
import os
import json

SAVE_FILE = "test_save.json"

def setup_function():
    """Clean up test file before each test."""
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)

def teardown_function():
    """Clean up test file after each test."""
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)

def test_save_creates_file():
    """save() creates a JSON file on disk."""
    repo = Repository()
    repo.save({"player_position": {"row": 0, "col": 0}}, SAVE_FILE)
    assert os.path.exists(SAVE_FILE)

def test_load_returns_saved_data():
    """load() returns exactly what was saved."""
    repo = Repository()
    data = {
        "player_position": {"row": 1, "col": 2},
        "wax_meter": 50,
        "game_status": "playing",
        "answered_figures": ["Leonardo da Vinci"],
        "visited_positions": [
            {"row": 0, "col": 0},
            {"row": 1, "col": 2}
        ]
    }
    repo.save(data, SAVE_FILE)
    loaded = repo.load(SAVE_FILE)
    assert loaded == data

def test_save_is_valid_json():
    """The saved file is valid JSON that can be parsed independently."""
    repo = Repository()
    repo.save({"wax_meter": 25}, SAVE_FILE)
    with open(SAVE_FILE, "r") as f:
        parsed = json.load(f)
    assert parsed == {"wax_meter": 25}
```

### 3.2 Load — Edge Cases

```python
def test_load_missing_file_returns_none():
    """load() returns None if the file does not exist."""
    repo = Repository()
    result = repo.load("nonexistent_file.json")
    assert result is None

def test_load_corrupt_file_raises_value_error():
    """load() raises ValueError if the file is not valid JSON."""
    with open(SAVE_FILE, "w") as f:
        f.write("{this is not json!!!")
    repo = Repository()
    try:
        repo.load(SAVE_FILE)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected

def test_load_empty_file_raises_value_error():
    """load() raises ValueError for an empty file."""
    with open(SAVE_FILE, "w") as f:
        f.write("")
    repo = Repository()
    try:
        repo.load(SAVE_FILE)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass  # Expected
```

### 3.3 Save — Edge Cases

```python
def test_save_overwrites_existing_file():
    """Saving twice overwrites the first save."""
    repo = Repository()
    repo.save({"wax_meter": 10}, SAVE_FILE)
    repo.save({"wax_meter": 99}, SAVE_FILE)
    loaded = repo.load(SAVE_FILE)
    assert loaded["wax_meter"] == 99

def test_save_handles_empty_dict():
    """An empty dict can be saved and loaded."""
    repo = Repository()
    repo.save({}, SAVE_FILE)
    loaded = repo.load(SAVE_FILE)
    assert loaded == {}
```

---

## 4. `test_engine_integration.py` — Engine / Integration Tests

> **Owner:** Engine Owner (`main.py`) — or Test Lead in Track B
> **Imports:** All three modules.
> **Purpose:** Verify that the wiring works end-to-end.

### 4.1 Translation Layer

```python
from maze import Maze, Position, Direction, GameStatus, GameState
from main import Engine
from db import Repository

def test_game_state_to_dict_serializes_position():
    """Position objects become {"row": int, "col": int} dicts; door_states serialized."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert d["player_position"] == {"row": 0, "col": 0}
    assert isinstance(d["player_position"], dict)
    assert "door_states" in d
    assert isinstance(d["door_states"], list)

def test_game_state_to_dict_serializes_enums():
    """GameStatus enum becomes a string."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert d["game_status"] == "playing"
    assert isinstance(d["game_status"], str)

def test_dict_to_game_state_roundtrip():
    """Converting state → dict → state produces equivalent data."""
    m = Maze()
    m.move(Direction.SOUTH)
    original = m.get_game_state()
    d = Engine.game_state_to_dict(original)
    restored = Engine.dict_to_game_state(d)
    assert restored.player_position == original.player_position
    assert restored.wax_meter == original.wax_meter
    assert restored.game_status == original.game_status
    assert restored.answered_figures == original.answered_figures
    assert restored.door_states == original.door_states

def test_dict_to_game_state_rejects_bad_data():
    """Malformed dict raises ValueError."""
    try:
        Engine.dict_to_game_state({"garbage": True})
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
```

### 4.2 Save / Load Integration

```python
import os

SAVE_FILE = "test_integration_save.json"

def setup_function():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)

def teardown_function():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)

def test_save_and_load_game_roundtrip():
    """Full roundtrip: maze → engine.save → file → engine.load → maze."""
    m = Maze()
    repo = Repository()
    engine = Engine(m, repo)

    # Play a move
    m.move(Direction.SOUTH)

    # Save
    engine.save_game()

    # Create a fresh maze + engine, load into it
    m2 = Maze()
    engine2 = Engine(m2, repo)
    success = engine2.load_game()
    assert success is True
    assert m2.get_player_position() == Position(1, 0)

def test_load_game_with_no_save_returns_false():
    """Loading when no save file exists returns False gracefully."""
    m = Maze()
    repo = Repository()
    engine = Engine(m, repo)
    success = engine.load_game()
    assert success is False
```

### 4.3 Full Game Simulation (Maze-Rule Validation)

> **Note:** These tests exercise maze rules end-to-end (win/loss paths) without
> Engine or Repository. They live in this file for convenience but are classified
> as `maze` tests in the RUNBOOK.

```python
def test_full_winning_game():
    """Simulate a complete winning run through the skeleton maze."""
    m = Maze()

    # Navigate to Da Vinci room (1,0) and answer correctly
    m.move(Direction.SOUTH)   # (0,0) → (1,0)
    room = m.get_room(m.get_player_position())
    assert m.attempt_answer(room.trivia.correct_key) == "correct"

    # Navigate to Cleopatra room (2,1) and answer correctly
    m.move(Direction.EAST)    # (1,0) → (1,1)
    m.move(Direction.SOUTH)   # (1,1) → (2,1)
    room = m.get_room(m.get_player_position())
    assert m.attempt_answer(room.trivia.correct_key) == "correct"

    # Move to exit (2,2)
    m.move(Direction.EAST)    # (2,1) → (2,2)

    assert m.get_game_status() == GameStatus.WON

def test_full_losing_game():
    """Simulate a losing run — wax meter hits 100."""
    m = Maze()

    # Navigate to Da Vinci room (1,0)
    m.move(Direction.SOUTH)   # (0,0) → (1,0)

    room = m.get_room(m.get_player_position())
    wrong = _get_wrong_key(room.trivia.correct_key)

    # Answer wrong 4 times
    for _ in range(4):
        m.attempt_answer(wrong)

    assert m.get_game_status() == GameStatus.LOST
    assert m.get_wax_meter() >= 100
```

---

## 5. Test Helper Utilities

Place these in a `tests/conftest.py` or at the top of each test file:

```python
def _navigate_to_trivia_room(m):
    """Move player to the nearest room with trivia.
    Skeleton layout: (0,0) → south → (1,0). Room (1,0) has Leonardo da Vinci trivia.
    """
    m.move(Direction.SOUTH)   # (0,0) → (1,0)

def _get_wrong_key(correct_key: str) -> str:
    """Return an answer key that is NOT the correct one."""
    keys = ["A", "B", "C"]
    keys.remove(correct_key)
    return keys[0]
```

---

## 6. Running the Tests

```bash
# Run all tests
pytest tests/ -v

# Run only maze contract tests
pytest tests/test_maze_contract.py -v

# Run only repo contract tests
pytest tests/test_repo_contract.py -v

# Run only integration tests
pytest tests/test_engine_integration.py -v
```

---

*Document version: 1.0 — Walking Skeleton · Waxworks: The Midnight Curse*
