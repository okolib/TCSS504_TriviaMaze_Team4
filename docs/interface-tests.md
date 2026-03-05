# Waxworks: The Midnight Curse — Interface Tests

> Contract tests that each module must pass before integration.
> Each test is independent — a module owner can run their suite without the other modules.
>
> **Updated for MVP** based on `rfc_merged.md`. New tests are marked with `# [NEW]`.
> Stubs use `assert False, "Not yet implemented"` — each feature branch makes its tests pass.

---

## 1. Test Philosophy

Each module is developed on its own `feature/` branch. Before a PR is opened,
the module must pass every test in its contract section below. Tests use only
`pytest` and the Python standard library.

**Design PR stubs:** New tests in this document are initially failing stubs.
Each feature branch makes its subset pass. When all branches merge, all tests pass.

---

## 2. `test_maze_contract.py` — Domain Logic Tests

> **Owner:** Domain Architect (`maze.py`)
> **Imports:** `from maze import Maze, Position, Direction, DoorState, GameStatus, RoomVisibility, FogMapCell, GameState`
> **Constraint:** No file I/O, no `print()`, no imports of `db` or `main`.

### 2.1 Construction & Layout

```python
def test_maze_creates_5x5_grid():                          # [NEW]
    """Maze has 25 rooms keyed by (row, col) for the 5×5 MVP layout."""
    m = Maze(rows=5, cols=5)
    rooms = m.get_rooms()
    assert len(rooms) == 25
    for r in range(5):
        for c in range(5):
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

def test_figure_rooms_exist():                             # [NEW]
    """At least three rooms contain wax figures (for 5×5 MVP layout)."""
    m = Maze()
    rooms = m.get_rooms()
    figure_rooms = [r for r in rooms.values() if r.figure_name is not None]
    assert len(figure_rooms) >= 3

def test_figure_rooms_have_zones():                        # [NEW]
    """Every room with a figure also has a zone."""
    m = Maze()
    rooms = m.get_rooms()
    for room in rooms.values():
        if room.figure_name is not None:
            assert room.zone is not None, f"Room {room.position} has figure but no zone"

def test_expanded_maze_has_more_rooms():                   # [NEW]
    """Grid is larger than 3×3."""
    m = Maze()
    rooms = m.get_rooms()
    assert len(rooms) > 9

def test_maze_is_solvable():                               # [NEW]
    """BFS confirms a path from entrance to exit."""
    m = Maze()
    assert m.is_solvable() is True

def test_trivia_from_constructor():                        # [NEW]
    """Maze uses passed-in trivia_data, not hardcoded figures."""
    custom_data = [
        {"figure_name": "Test Figure", "zone": "Test Zone", "position": (1, 1)}
    ]
    m = Maze(rows=3, cols=3, trivia_data=custom_data)
    room = m.get_room(Position(1, 1))
    assert room.figure_name == "Test Figure"
    assert room.zone == "Test Zone"
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
    result = m.move(Direction.SOUTH)  # (0,0) → (1,0) per 5×5 layout
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
    room = m.get_room(pos_before)
    wall_dirs = [d for d, s in room.doors.items() if s == DoorState.WALL]
    assert len(wall_dirs) > 0, "Expected at least one WALL direction at (0,0)"
    result = m.move(wall_dirs[0])
    assert result == "wall"
    assert m.get_player_position() == pos_before

def test_move_into_locked_door_rejected():
    """Moving through a LOCKED door returns 'locked'; position unchanged."""
    m = Maze()
    _navigate_to_figure_room(m)
    pos_before = m.get_player_position()
    room = m.get_room(pos_before)
    locked_dirs = [d for d, s in room.doors.items() if s == DoorState.LOCKED]
    assert len(locked_dirs) > 0, "Expected at least one LOCKED direction"
    result = m.move(locked_dirs[0])
    assert result == "locked"
    assert m.get_player_position() == pos_before

def test_move_into_border_wall_rejected():
    """Moving into a border (e.g. north from (0,0)) returns 'wall'; position unchanged."""
    m = Maze()
    result = m.move(Direction.NORTH)
    assert result == "wall"
    assert m.get_player_position() == Position(0, 0)
```

### 2.4 Trivia — Happy Path

```python
def test_correct_answer_unlocks_door():
    """Answering correctly returns 'correct' and unlocks the passage."""
    m = Maze()
    _navigate_to_figure_room(m)
    room = m.get_room(m.get_player_position())
    assert room.figure_name is not None
    result = m.attempt_answer("B", "B")  # Engine passes correct_key
    assert result == "correct"

def test_correct_answer_does_not_increase_curse():         # [NEW]
    """Curse level stays the same after a correct answer."""
    m = Maze()
    _navigate_to_figure_room(m)
    curse_before = m.get_curse_level()
    m.attempt_answer("B", "B")
    assert m.get_curse_level() == curse_before

def test_correct_answer_adds_to_defeated():                # [NEW]
    """Correct answer adds the figure to defeated_figures."""
    m = Maze()
    _navigate_to_figure_room(m)
    room = m.get_room(m.get_player_position())
    m.attempt_answer("B", "B")
    state = m.get_game_state()
    assert room.figure_name in state.defeated_figures
```

### 2.5 Trivia — Failure / Curse Level

```python
def test_wrong_answer_increases_curse():                   # [NEW]
    """Wrong answer increases curse level by 20."""
    m = Maze()
    _navigate_to_figure_room(m)
    curse_before = m.get_curse_level()
    m.attempt_answer("A", "B")  # Wrong answer
    assert m.get_curse_level() == curse_before + 20

def test_wrong_answer_keeps_door_locked():
    """Door stays locked after a wrong answer."""
    m = Maze()
    _navigate_to_figure_room(m)
    room_before = m.get_room(m.get_player_position())
    locked_dirs = [d for d, s in room_before.doors.items()
                   if s == DoorState.LOCKED]
    m.attempt_answer("A", "B")  # Wrong answer
    room_after = m.get_room(m.get_player_position())
    for d in locked_dirs:
        assert room_after.doors[d] == DoorState.LOCKED

def test_curse_at_100_means_game_over():                   # [NEW]
    """When curse level hits 100, game status becomes LOST."""
    m = Maze()
    _navigate_to_figure_room(m)
    # Answer wrong 5 times (5 × 20 = 100)
    for _ in range(5):
        if m.get_game_status() != GameStatus.PLAYING:
            break
        m.attempt_answer("A", "B")
    assert m.get_curse_level() >= 100
    assert m.get_game_status() == GameStatus.LOST

def test_curse_level_never_exceeds_100():                  # [NEW]
    """Curse level is capped at 100."""
    m = Maze()
    _navigate_to_figure_room(m)
    for _ in range(10):
        m.attempt_answer("A", "B")
    assert m.get_curse_level() <= 100

def test_attempt_answer_after_game_over():
    """attempt_answer returns 'game_over' once the game is no longer PLAYING."""
    m = Maze()
    _navigate_to_figure_room(m)
    for _ in range(5):
        m.attempt_answer("A", "B")
    assert m.get_game_status() == GameStatus.LOST
    curse_before = m.get_curse_level()
    result = m.attempt_answer("A", "B")
    assert result == "game_over"
    assert m.get_curse_level() == curse_before

def test_no_figure_in_empty_room():                        # [NEW]
    """attempt_answer in a room without a figure returns 'no_figure'."""
    m = Maze()
    # (0,0) is the entrance — no figure
    result = m.attempt_answer("A", "B")
    assert result == "no_figure"

def test_already_defeated_figure():                        # [NEW]
    """Answering a defeated figure returns 'already_answered'."""
    m = Maze()
    _navigate_to_figure_room(m)
    m.attempt_answer("B", "B")  # Defeat the figure
    result = m.attempt_answer("B", "B")  # Try again
    assert result == "already_answered"
```

### 2.6 Fog of War                                          # [NEW SECTION]

```python
def test_fog_map_initial_state():                          # [NEW]
    """Only entrance is CURRENT, adjacent rooms are VISIBLE, rest HIDDEN."""
    m = Maze()
    fog = m.get_fog_map()
    for row in fog:
        for cell in row:
            if cell.position == Position(0, 0):
                assert cell.visibility == RoomVisibility.CURRENT
            elif cell.position in [Position(0, 1), Position(1, 0)]:
                # Adjacent to (0,0) via open doors
                assert cell.visibility in [RoomVisibility.VISIBLE, RoomVisibility.HIDDEN]
            else:
                assert cell.visibility == RoomVisibility.HIDDEN

def test_fog_map_after_move():                             # [NEW]
    """After moving, previous room becomes VISITED, new room is CURRENT."""
    m = Maze()
    m.move(Direction.SOUTH)  # (0,0) → (1,0)
    fog = m.get_fog_map()
    for row in fog:
        for cell in row:
            if cell.position == Position(0, 0):
                assert cell.visibility == RoomVisibility.VISITED
            elif cell.position == Position(1, 0):
                assert cell.visibility == RoomVisibility.CURRENT

def test_fog_map_hides_trivia_in_hidden_rooms():           # [NEW]
    """Figure names are not leaked for HIDDEN rooms."""
    m = Maze()
    fog = m.get_fog_map()
    for row in fog:
        for cell in row:
            if cell.visibility == RoomVisibility.HIDDEN:
                assert cell.figure_name is None, \
                    f"Hidden room {cell.position} leaks figure_name"

def test_fog_map_returns_2d_grid():                        # [NEW]
    """get_fog_map() returns a list of lists matching maze dimensions."""
    m = Maze()
    fog = m.get_fog_map()
    assert len(fog) == 5  # rows
    for row in fog:
        assert len(row) == 5  # cols
```

### 2.7 Game State Snapshot

```python
def test_get_game_state_returns_dataclass():
    """get_game_state() returns a GameState instance with correct initial values."""
    m = Maze()
    state = m.get_game_state()
    assert isinstance(state, GameState)
    assert state.player_position == Position(0, 0)
    assert state.curse_level == 0
    assert state.game_status == GameStatus.PLAYING
    assert state.defeated_figures == []
    assert hasattr(state, "door_states") and isinstance(state.door_states, dict)

def test_restore_game_state_roundtrip():
    """Saving and restoring state reproduces the same game."""
    m = Maze()
    m.move(Direction.SOUTH)
    state = m.get_game_state()
    m2 = Maze()
    m2.restore_game_state(state)
    assert m2.get_player_position() == state.player_position
    assert m2.get_curse_level() == state.curse_level
    assert m2.get_game_status() == state.game_status
    assert m2.get_game_state().door_states == state.door_states

def test_restore_preserves_unlocked_doors():
    """After defeating a figure, save and restore; unlocked door stays open."""
    m = Maze()
    _navigate_to_figure_room(m)
    assert m.attempt_answer("B", "B") == "correct"
    state = m.get_game_state()
    m2 = Maze()
    m2.restore_game_state(state)
    # Verify the gate that was unlocked stays open
    room_after = m2.get_room(m.get_player_position())
    open_doors = [d for d, s in room_after.doors.items() if s == DoorState.OPEN]
    assert len(open_doors) > 0, "Previously locked door should be OPEN after restore"
```

### 2.8 Test Helpers

```python
def _navigate_to_figure_room(m):
    """Move player to the nearest room with a wax figure.
    MVP layout: (0,0) → east → (0,1) → east → (0,2) → south → ... → (1,1) Da Vinci.
    Exact path depends on 5×5 layout implementation.
    """
    # Path to Da Vinci at (1,1): go east twice, then south, then... 
    # Adjust based on actual connected rooms in 5×5 layout
    m.move(Direction.EAST)    # (0,0) → (0,1)
    m.move(Direction.EAST)    # (0,1) → (0,2)
    m.move(Direction.SOUTH)   # (0,2) → (1,2)  -- or adjust
    m.move(Direction.WEST)    # (1,2) → (1,1) Da Vinci

def _get_wrong_key(correct_key: str) -> str:
    """Return an answer key that is NOT the correct one."""
    keys = ["A", "B", "C"]
    keys.remove(correct_key)
    return keys[0]
```

---

## 3. `test_repo_contract.py` — Persistence Tests (SQLModel)

> **Owner:** Persistence Engineer (`db.py`)
> **Imports:** `from db import Repository`
> **Constraint:** No imports from `maze` or `main`. Tests use plain dicts.
> **BREAKING:** All old JSON file tests are obsolete. Rewritten for SQLite.

### 3.1 Save & Load — Happy Path                           # [NEW SECTION]

```python
import os

DB_FILE = "test_waxworks.db"

def setup_function():
    """Clean up test DB before each test."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def teardown_function():
    """Clean up test DB after each test."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def test_save_creates_db_record():                         # [NEW]
    """save() writes to SQLite, not JSON."""
    repo = Repository(db_path=DB_FILE)
    repo.save({"player_position": {"row": 0, "col": 0}})
    assert os.path.exists(DB_FILE)

def test_load_returns_saved_data():                        # [NEW]
    """load() returns exactly what was saved."""
    repo = Repository(db_path=DB_FILE)
    data = {
        "player_position": {"row": 1, "col": 2},
        "curse_level": 40,
        "game_status": "playing",
        "defeated_figures": ["Leonardo da Vinci"],
        "visited_positions": [
            {"row": 0, "col": 0},
            {"row": 1, "col": 2}
        ]
    }
    repo.save(data)
    loaded = repo.load()
    assert loaded == data

def test_save_with_slot_name():                            # [NEW]
    """save() and load() respect slot_name parameter."""
    repo = Repository(db_path=DB_FILE)
    repo.save({"curse_level": 10}, slot_name="slot1")
    repo.save({"curse_level": 20}, slot_name="slot2")
    assert repo.load(slot_name="slot1")["curse_level"] == 10
    assert repo.load(slot_name="slot2")["curse_level"] == 20

def test_save_overwrites_existing_slot():                  # [NEW]
    """Saving to the same slot overwrites the previous save."""
    repo = Repository(db_path=DB_FILE)
    repo.save({"curse_level": 10})
    repo.save({"curse_level": 99})
    loaded = repo.load()
    assert loaded["curse_level"] == 99
```

### 3.2 Load — Edge Cases

```python
def test_load_missing_slot_returns_none():                 # [NEW]
    """load() returns None if the slot does not exist."""
    repo = Repository(db_path=DB_FILE)
    result = repo.load(slot_name="nonexistent")
    assert result is None

def test_save_handles_empty_dict():
    """An empty dict can be saved and loaded."""
    repo = Repository(db_path=DB_FILE)
    repo.save({})
    loaded = repo.load()
    assert loaded == {}
```

### 3.3 Question Bank                                      # [NEW SECTION]

```python
def test_get_random_question_returns_unasked():            # [NEW]
    """Question Bank returns an unasked question for a given figure."""
    repo = Repository(db_path=DB_FILE)
    _seed_test_questions(repo)
    q = repo.get_random_question("Leonardo da Vinci")
    assert q is not None
    assert q["figure_name"] == "Leonardo da Vinci"
    assert "question_text" in q
    assert "choices" in q
    assert "correct_key" in q

def test_get_random_question_scoped_to_figure():           # [NEW]
    """Da Vinci query never returns a Cleopatra question."""
    repo = Repository(db_path=DB_FILE)
    _seed_test_questions(repo)
    for _ in range(20):
        q = repo.get_random_question("Leonardo da Vinci")
        if q is None:
            break
        assert q["figure_name"] == "Leonardo da Vinci"

def test_get_random_question_marks_asked():                # [NEW]
    """After fetching a question, has_been_asked flips to True."""
    repo = Repository(db_path=DB_FILE)
    _seed_test_questions(repo)
    q1 = repo.get_random_question("Leonardo da Vinci")
    q2 = repo.get_random_question("Leonardo da Vinci")
    q3 = repo.get_random_question("Leonardo da Vinci")
    # With 3 questions seeded, all should be different (or None after exhausted)
    questions = [q for q in [q1, q2, q3] if q is not None]
    texts = [q["question_text"] for q in questions]
    assert len(texts) == len(set(texts)), "Should not repeat questions"

def test_get_random_question_returns_none_when_exhausted(): # [NEW]
    """All questions for a figure asked → returns None."""
    repo = Repository(db_path=DB_FILE)
    _seed_test_questions(repo)
    for _ in range(10):
        q = repo.get_random_question("Leonardo da Vinci")
        if q is None:
            break
    assert q is None, "Should return None when all questions exhausted"

def test_reset_questions():                                 # [NEW]
    """All questions go back to unasked after reset."""
    repo = Repository(db_path=DB_FILE)
    _seed_test_questions(repo)
    # Exhaust all Da Vinci questions
    while repo.get_random_question("Leonardo da Vinci") is not None:
        pass
    # Reset
    repo.reset_questions()
    q = repo.get_random_question("Leonardo da Vinci")
    assert q is not None, "After reset, questions should be available again"

def test_seed_questions_idempotent():                       # [NEW]
    """Seeding twice doesn't duplicate questions."""
    repo = Repository(db_path=DB_FILE)
    _seed_test_questions(repo)
    _seed_test_questions(repo)
    count = 0
    while repo.get_random_question("Leonardo da Vinci") is not None:
        count += 1
    assert count == 3, "Should have exactly 3 questions, not duplicates"
```

### 3.4 Test Helpers

```python
def _seed_test_questions(repo):
    """Seed the DB with test questions for Da Vinci and Cleopatra."""
    questions = [
        {"figure_name": "Leonardo da Vinci", "zone": "Art Gallery",
         "question_text": "Who painted the Mona Lisa?",
         "choice_a": "Michelangelo", "choice_b": "Leonardo da Vinci",
         "choice_c": "Raphael", "correct_key": "B"},
        {"figure_name": "Leonardo da Vinci", "zone": "Art Gallery",
         "question_text": "What fresco is in Santa Maria delle Grazie?",
         "choice_a": "The Last Supper", "choice_b": "The Creation of Adam",
         "choice_c": "School of Athens", "correct_key": "A"},
        {"figure_name": "Leonardo da Vinci", "zone": "Art Gallery",
         "question_text": "Da Vinci's drawing of human proportions is called?",
         "choice_a": "The Thinker", "choice_b": "David",
         "choice_c": "Vitruvian Man", "correct_key": "C"},
        {"figure_name": "Cleopatra", "zone": "Ancient History",
         "question_text": "What creature is associated with Cleopatra's death?",
         "choice_a": "Scorpion", "choice_b": "Asp", "choice_c": "Spider",
         "correct_key": "B"},
    ]
    repo.seed_questions(questions)
```

---

## 4. `test_view_contract.py` — View Tests               # [NEW SECTION]

> **Owner:** View Engineer (`view.py`)
> **Imports:** `from view import View` and maze types
> **Constraint:** Must NOT import `db`.

```python
import ast
import inspect

def test_view_does_not_import_db():                        # [NEW]
    """Separation of concerns: view.py must not import db."""
    import view
    source = inspect.getsource(view)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "db", "view.py must not import db"
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "db", "view.py must not import from db"

def test_display_fog_map_shows_visited():                  # [NEW]
    """Visited rooms render differently from hidden rooms."""
    assert False, "Not yet implemented"

def test_display_room_shows_themed_text():                 # [NEW]
    """Room descriptions use Waxworks themed language."""
    assert False, "Not yet implemented"

def test_display_curse_meter():                            # [NEW]
    """Curse meter renders with themed visualization."""
    assert False, "Not yet implemented"

def test_display_confrontation():                          # [NEW]
    """Figure confrontation displays question with choices."""
    assert False, "Not yet implemented"

def test_display_endgame_victory():                        # [NEW]
    """Victory screen shows themed congratulations."""
    assert False, "Not yet implemented"

def test_display_endgame_loss():                           # [NEW]
    """Game over screen shows 'Newest Exhibit' plaque."""
    assert False, "Not yet implemented"
```

---

## 5. `test_engine_integration.py` — Engine / Integration Tests

> **Owner:** Engine Orchestrator (`main.py`)
> **Imports:** All modules.
> **Purpose:** Verify that the wiring works end-to-end.

### 5.1 Translation Layer

```python
from maze import Maze, Position, Direction, GameStatus, GameState
from main import Engine
from db import Repository
from view import View

def test_game_state_to_dict_serializes_position():
    """Position objects become {"row": int, "col": int} dicts."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert d["player_position"] == {"row": 0, "col": 0}
    assert isinstance(d["player_position"], dict)

def test_game_state_to_dict_serializes_enums():
    """GameStatus enum becomes a string."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert d["game_status"] == "playing"
    assert isinstance(d["game_status"], str)

def test_game_state_to_dict_uses_curse_level():            # [NEW]
    """Serialized state uses 'curse_level', not 'wax_meter'."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert "curse_level" in d
    assert "wax_meter" not in d

def test_game_state_to_dict_uses_defeated_figures():       # [NEW]
    """Serialized state uses 'defeated_figures', not 'answered_figures'."""
    m = Maze()
    state = m.get_game_state()
    d = Engine.game_state_to_dict(state)
    assert "defeated_figures" in d
    assert "answered_figures" not in d

def test_dict_to_game_state_roundtrip():
    """Converting state → dict → state produces equivalent data."""
    m = Maze()
    m.move(Direction.EAST)
    original = m.get_game_state()
    d = Engine.game_state_to_dict(original)
    restored = Engine.dict_to_game_state(d)
    assert restored.player_position == original.player_position
    assert restored.curse_level == original.curse_level
    assert restored.game_status == original.game_status
    assert restored.defeated_figures == original.defeated_figures
    assert restored.door_states == original.door_states

def test_dict_to_game_state_rejects_bad_data():
    """Malformed dict raises ValueError."""
    try:
        Engine.dict_to_game_state({"garbage": True})
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
```

### 5.2 Save / Load Integration                            # [NEW]

```python
import os

DB_FILE = "test_integration.db"

def setup_function():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def teardown_function():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def test_engine_requires_view():                           # [NEW]
    """Engine constructor requires maze, repo, AND view."""
    m = Maze()
    repo = Repository(db_path=DB_FILE)
    view = View()
    engine = Engine(m, repo, view)
    assert engine is not None

def test_save_and_load_game_roundtrip():
    """Full roundtrip: maze → engine.save → DB → engine.load → maze."""
    m = Maze()
    repo = Repository(db_path=DB_FILE)
    view = View()
    engine = Engine(m, repo, view)

    m.move(Direction.SOUTH)   # (0,0) → (1,0)
    engine.save_game()

    m2 = Maze()
    engine2 = Engine(m2, repo, view)
    success = engine2.load_game()
    assert success is True
    assert m2.get_player_position() == Position(1, 0)

def test_load_game_with_no_save_returns_false():
    """Loading when no save exists returns False gracefully."""
    m = Maze()
    repo = Repository(db_path=DB_FILE)
    view = View()
    engine = Engine(m, repo, view)
    success = engine.load_game()
    assert success is False
```

### 5.3 Full Game Simulation

```python
def test_full_winning_game():                              # [UPDATED]
    """Simulate a complete winning run through the 5×5 maze."""
    m = Maze()

    # Navigate to Da Vinci room (1,1) and defeat
    _navigate_to_figure_room(m)
    room = m.get_room(m.get_player_position())
    assert m.attempt_answer("B", "B") == "correct"

    # Continue through maze to Lincoln and Cleopatra...
    # (exact path depends on 5×5 layout connections)
    assert False, "Not yet implemented — update path for 5×5 layout"

def test_full_losing_game():                               # [UPDATED]
    """Simulate a losing run — curse level hits 100."""
    m = Maze()
    _navigate_to_figure_room(m)
    for _ in range(5):  # 5 × 20 = 100
        m.attempt_answer("A", "B")

    assert m.get_game_status() == GameStatus.LOST
    assert m.get_curse_level() >= 100
```

---

## 6. Test Helper Utilities

Place these in a `tests/conftest.py` or at the top of each test file:

```python
def _navigate_to_figure_room(m):
    """Move player to the nearest room with a wax figure.
    MVP 5×5 staircase layout: Da Vinci is at (1,1).
    Path: (0,0) →S→ (1,0) →E→ (1,1)
    """
    m.move(Direction.SOUTH)   # (0,0) → (1,0)
    m.move(Direction.EAST)    # (1,0) → (1,1) Da Vinci

def _get_wrong_key(correct_key: str) -> str:
    """Return an answer key that is NOT the correct one."""
    keys = ["A", "B", "C"]
    keys.remove(correct_key)
    return keys[0]
```

---

## 7. Running the Tests

```bash
# Run all tests
pytest tests/ -v

# Run only maze contract tests
pytest tests/test_maze_contract.py -v

# Run only repo contract tests (SQLModel)
pytest tests/test_repo_contract.py -v

# Run only view contract tests
pytest tests/test_view_contract.py -v

# Run only integration tests
pytest tests/test_engine_integration.py -v
```

---

*Document version: 2.0 — MVP · Waxworks: The Midnight Curse · Based on rfc_merged.md*
