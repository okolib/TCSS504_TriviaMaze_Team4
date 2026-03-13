# Branch Changelog: `feat/qt-gui-mario`

> **Purpose:** This document describes every change on this branch so teammate
> AI assistants can understand the current state and integrate safely.
>
> **Base branch:** `feat/final-maze` (which branched from `main`)
>
> **Owner:** Mario (GUI / View Engineer)

---

## Summary

This branch adds a PySide6 Qt GUI to the game while preserving the CLI.
The game is fully playable via `python main.py --gui`. No existing module
contracts (`MazeProtocol`, `RepositoryProtocol`, `ViewProtocol`) were broken.

Includes two view modes: a **first-person dungeon crawler** perspective
(default) and a **top-down fog-of-war map**, switchable via a toggle button.

---

## New Files (5)

### `qt_view.py` — Qt Implementation of ViewProtocol

- **Implements all 11 ViewProtocol methods** with identical signatures to `view.py`
- Main window: left panel (maze canvas) + right sidebar (room info, curse meter, doors, nav buttons, actions, game log)
- `TriviaDialog` — modal `QDialog` with answer buttons, emits `answer_selected` signal
- `command_issued = Signal(str)` — the primary bridge to the Engine. Emits strings like `"move north"`, `"answer B"`, `"save"`, `"quit"`
- Toggle button switches between first-person and top-down views via `QStackedWidget`
- Tracks `_player_facing` direction (updated on each successful move)
- **Does NOT import `db`** — only imports `maze` types

### `maze_canvas.py` — Top-Down Maze Grid (QPainter)

- `MazeCanvas(QWidget)` renders a 5×5 grid from `FogMapCell` data
- Public API: `update_map(fog_map: list[list[FogMapCell]]) -> None`
- Renders: cell visibility (hidden/visible/visited/current), doors (open/locked/wall), player `@`, figure initials, entrance/exit markers
- **Does NOT import `db` or `main`**

### `first_person_canvas.py` — First-Person Dungeon View (QPainter)

- `FirstPersonCanvas(QWidget)` renders pseudo-3D corridor using trapezoid layers
- Public API: `update_map(fog_map)` + `set_facing(direction)`
- **Corridor rendering:** Perspective walls (3 depth layers), locked golden gates with vertical/horizontal bars and lock icon, open archways with stone frame, solid brick walls
- **Zone-tinted walls:** Color shifts by row with per-column brightness variation:
  - Row 0 (Foyer) → cool blue-purple
  - Row 1 (Art Gallery) → warm crimson
  - Row 2 (History) → teal green
  - Row 3 (Ancient) → sandy amber
  - Row 4 (Exit) → emerald
- **Character-specific wax figure silhouettes** (not generic ghosts):
  - **Da Vinci** — wide beret, flowing grey beard, paintbrush in hand, warm amber eyes
  - **Lincoln** — tall stovepipe hat, dark suit with lapels and bow tie, chin-strap beard, steel blue eyes
  - **Cleopatra** — nemes headdress with gold stripes, uraeus cobra, gold scepter, kohl eyeliner, emerald green eyes
  - Unknown figures fall back to a generic humanoid silhouette
- **Decorative elements:** Wall-mounted torch sconces with flame glow, compass indicator (top-right), minimap (bottom-left)
- Figures scale at depth 0 (current room, large) vs depth 1 (one cell ahead, 50% scale)
- **Does NOT import `db` or `main`**

### `docs/qt_contracts.md` — Interface Contracts for Qt Layer

- Documents `MazeCanvas`, `QtView`, `TriviaDialog`, and Engine adapter contracts
- Signal flow diagram, dependency rules, testing contracts

---

## Modified Files (5)

### `main.py` — Engine Refactored for Dual-Mode

**This is the most important file for teammates to understand.**

#### What changed:

1. **Private methods made public:**
   - `_handle_command()` → `handle_command(command: str)`
   - `_handle_move()` → `handle_move(direction_str: str)`
   - `_handle_answer()` → `handle_answer(answer_key: str)`
   - `_handle_map()` → `handle_map()`

2. **New methods added:**
   - `refresh_display()` — pushes room, fog map, and confrontation state to the View. Called after every command.
   - `_check_endgame()` → checks game status and calls `display_endgame()` if won/lost. Returns `bool`.
   - `start_qt(app)` — wires `command_issued` signal → `handle_command()`, calls welcome/refresh, starts `app.exec()`.

3. **Entry point updated:**
   ```python
   if "--gui" in sys.argv:
       # Qt mode: QApplication + QtView + Engine.start_qt(app)
   else:
       # CLI mode: View + Engine.run() (unchanged behavior)
   ```

4. **Confrontation tracking:**
   - `self._current_question` — stores the DB-fetched question dict
   - `self._confronted_figure` — prevents re-fetching the same question on repeated `refresh_display()` calls

#### What was NOT changed:
- `game_state_to_dict()` / `dict_to_game_state()` — unchanged
- `save_game()` / `load_game()` — unchanged (both called by `handle_command`)
- `GameState` field access: uses `state.wax_meter` and `state.answered_figures` (the existing field names from `maze.py`)

#### ⚠️ Important for Sowmya (Engine owner):
The Engine now references `state.wax_meter` and `state.answered_figures`. If `maze.py` renames these fields, `main.py` must be updated to match. The `display_endgame()` call also uses these:
```python
self._view.display_endgame(
    status=status,
    curse_level=state.wax_meter,
    rooms_explored=len(state.visited_positions),
    figures_defeated=len(state.answered_figures),
    ...
)
```

#### ⚠️ Important for Megan (Maze owner):
The Engine calls these `MazeProtocol` methods. If signatures change, `main.py` must be updated:
- `maze.move(direction)` → returns result string
- `maze.attempt_answer(answer_key, correct_key)` → returns result string
- `maze.get_fog_map()` → returns `list[list[FogMapCell]]`
- `maze.get_game_state()` → returns `GameState`
- `maze.get_room(position)` → returns `Room`
- `maze.get_player_position()` → returns `Position`
- `maze.get_game_status()` → returns `GameStatus`

#### ⚠️ Important for Boma (DB owner):
The Engine calls `self._repo.get_random_question(figure_name)` inside `refresh_display()`. This must return a dict with keys: `figure_name`, `question_text`, `choices`, `correct_key`. The `choices` value can be `dict[str, str]` (e.g. `{"A": "text"}`) or `list[dict]`.

### `requirements.txt`

Added one line:
```
PySide6>=6.5
```

### `README.md`

Rewritten with: install instructions, `--gui` flag, architecture diagram, design patterns, project structure, and requirements.

### `maze.py` — Randomized Maze Generator (Option B)

**Major rewrite — every game now generates a completely different maze layout.**

#### What changed:

1. **`import random`** added at top of module
2. **`FIGURE_PLACEMENTS` dict removed.** Replaced with:
   ```python
   FIGURES = [
       ("Leonardo da Vinci", "Art Gallery"),
       ("Abraham Lincoln", "American History"),
       ("Cleopatra", "Ancient History"),
   ]
   ```
3. **`Maze.__init__()` now accepts `seed: Optional[int]`** for deterministic layouts in tests
4. **`_build_maze()` fully rewritten** with randomized generation algorithm:
   - Step 1: Initialize 5×5 grid with all WALLs
   - Step 2: Randomized DFS carves a spanning tree (all rooms reachable)
   - Step 3: +2 shortcut edges added for exploration variety
   - Step 4: BFS finds shortest path from (0,0) to (4,4)
   - Step 5: 3 locked gates placed evenly along the critical path
   - Step 6: Entrance/exit marked
   - Step 7: 3 figures shuffled into rooms adjacent to locked gates
   - Safety: `is_solvable()` verified; regenerates if invalid
5. **New private methods:** `_dfs_carve()`, `_add_shortcuts()`, `_bfs_path()`, `_select_gate_edges()`
6. **Old staircase layout completely removed** (no more diagonal "staircase" neighbors)

#### What was NOT changed:
- `MazeProtocol` interface — all public methods identical
- `move()`, `attempt_answer()`, `get_fog_map()`, `get_game_state()`, `restore_game_state()` — unchanged
- `is_solvable()` — still works (used as safety check in generator)
- `GameState`, `Room`, `FogMapCell` data classes — unchanged

#### Validation:
- 100 consecutive random mazes tested: **100/100 solvable**, all had 3 figures, all had locked gates, all produced **unique layouts**

#### ⚠️ Important for Megan (Maze owner):
- `FIGURE_PLACEMENTS` and `FIGURE_ROOMS` no longer exist. The generator places figures dynamically.
- `Maze.__init__()` now has a `seed` parameter. Tests can use `Maze(seed=42)` for deterministic layouts.
- The diagonal staircase `_neighbors` dict is no longer used (standard grid adjacency only).
- If adding more figures (Option C), just append to the `FIGURES` list — the generator will place them automatically.

#### 🐛 Bug Fix: Win Condition

The original `move()` granted victory simply for reaching the exit room. With the randomized maze adding shortcut edges, players could bypass locked gates and reach the exit without defeating all figures.

**Fix:** The win condition now requires `len(self.defeated_figures) >= total_figures` before triggering `GameStatus.WON` at the exit. If you reach the exit early, you must backtrack and defeat the remaining figures.

```python
# Before (broken):
if self.rooms[(new_row, new_col)].is_exit:
    self.game_status = GameStatus.WON

# After (fixed):
total_figures = sum(1 for r in self.rooms.values() if r.figure_name)
if (self.rooms[(new_row, new_col)].is_exit
        and len(self.defeated_figures) >= total_figures):
    self.game_status = GameStatus.WON
```

---

## Modified Test Files

### `tests/test_qt_view.py` — 40 tests (NEW)

| Section | Tests | What's Verified |
|---------|-------|----------------|
| Module isolation | 3 | `qt_view.py` and `maze_canvas.py` don't import `db` or `main` |
| Construction | 4 | QtView creates, has all 11 protocol methods, has signal, is QMainWindow |
| Display room | 8 | Room label, curse bar value/color, dread messages, entrance/exit/zone text, doors |
| Fog map | 1 | Canvas receives and stores fog data |
| Move result | 3 | Game log shows correct feedback for moved/locked/wall |
| Answer result | 5 | Correct/wrong/no_figure/already_defeated feedback + curse bar update |
| Save/Load | 4 | Success/failure messages logged |
| Error | 1 | Error message appears in game log |
| get_input | 2 | Returns empty string (Qt is event-driven) |
| Signals | 2 | Nav buttons emit correct commands, action buttons emit correct commands |
| MazeCanvas | 4 | Creates, accepts fog map, handles null map, minimum size |
| TriviaDialog | 3 | Creates with question, has signal, has 3+ choice buttons |

### `tests/conftest.py` — Updated for randomized maze

- `_navigate_to_trivia_room()` now uses BFS to find nearest figure room from current position
- Works with any maze layout (no hardcoded paths)

### `tests/test_maze_contract.py` — 4 tests updated

- `test_move_through_open_door` — dynamically finds an open direction
- `test_move_into_locked_door_rejected` — updated assertion message
- `test_restore_preserves_unlocked_doors` — uses dynamic figure room lookup
- `test_room_has_figure_name_and_zone` — searches all rooms instead of hardcoded (1,1)

### `tests/test_integration.py` — 3 tests updated

- `test_full_winning_game` — fully rewritten with BFS-based dynamic walkthrough
- `test_dict_to_game_state_roundtrip` — dynamically finds open direction for move
- `test_save_and_load_game_roundtrip` — dynamically finds open direction for move

---

## New Documentation (4 files)

### `docs/work_split.md`

Team member responsibilities and file ownership. Integration merge order:
Megan → Boma → Sowmya → Mario → `feat/final-maze` → `main`

### `docs/qt_contracts.md`

Interface contracts for `MazeCanvas`, `QtView`, `TriviaDialog`, Engine adapter,
signal flow diagram, dependency rules, and testing contracts.

### `docs/replayability_proposals.md`

Four proposals for improving replayability:
- **Option A** ✅ — Randomize figure placement (superseded by Option B)
- **Option B** ✅ — Randomize maze layout (implemented)
- **Option C** 📋 — Expand figure pool to 5-8 (Boma + Megan, future)
- **Option D** 📋 — Difficulty modes with tunable parameters (future)

### `docs/BRANCH_CHANGELOG.md`

This file — AI-readable summary of all branch changes.

---

## How to Run

```bash
pip install -r requirements.txt   # installs PySide6
python main.py --gui              # Qt GUI
python main.py                    # CLI (unchanged)
python -m pytest tests/ -v        # 138 tests (98 original + 40 new Qt tests)
```

---

## Complete File Inventory

| File | Status | Lines | Owner |
|------|--------|-------|-------|
| `qt_view.py` | NEW | ~750 | Mario |
| `maze_canvas.py` | NEW | ~250 | Mario |
| `first_person_canvas.py` | NEW | ~960 | Mario |
| `maze.py` | MODIFIED | ~580 | Mario (randomized generator), Megan (original types/protocol) |
| `main.py` | MODIFIED | ~735 | Mario (Engine refactor), Sowmya (original) |
| `requirements.txt` | MODIFIED | 2 | Mario |
| `README.md` | MODIFIED | ~80 | Mario |
| `tests/test_qt_view.py` | NEW | ~360 | Mario |
| `tests/conftest.py` | MODIFIED | ~65 | Mario (BFS navigation) |
| `tests/test_maze_contract.py` | MODIFIED | ~295 | Mario (4 tests updated) |
| `tests/test_integration.py` | MODIFIED | ~240 | Mario (3 tests updated) |
| `docs/qt_contracts.md` | NEW | ~235 | Mario |
| `docs/work_split.md` | NEW | ~70 | Mario |
| `docs/replayability_proposals.md` | NEW | ~100 | Mario |
| `docs/BRANCH_CHANGELOG.md` | NEW | ~270 | Mario |

---

## Merge Guidance

1. **If merging before this branch:** No conflicts expected. This branch only modifies `main.py`, `maze.py`, `README.md`, `requirements.txt`, and test files from the originals.

2. **If merging after this branch:** Watch for conflicts in:
   - `main.py` — `handle_command()` dispatch and `refresh_display()` method
   - `maze.py` — `_build_maze()` is completely rewritten; `FIGURE_PLACEMENTS` no longer exists
   - `tests/conftest.py` — `_navigate_to_trivia_room()` now uses BFS
   - `tests/test_integration.py` — `test_full_winning_game()` rewritten for dynamic maze

3. **If `maze.py` field names change:** Update `main.py` references to `state.wax_meter` → new name, and `state.answered_figures` → new name.

4. **If `MazeProtocol` methods change:** Update `main.py` calls in `handle_move()`, `handle_answer()`, `refresh_display()`.

5. **If adding more figures:** Just append to `FIGURES` list in `maze.py`. The generator automatically places them along the critical path.
