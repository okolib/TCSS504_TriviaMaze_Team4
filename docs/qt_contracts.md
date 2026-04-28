# Waxworks: The Midnight Curse — Qt GUI Contracts

> Final Maze · PySide6 GUI · Canvas + Sidebar · Event-Driven Engine
>
> Companion to [interfaces.md](file:///Users/mario/Documents/TCSS-504-Class/Fleshing-out-MVP/docs/interfaces.md) — extends the existing module contracts with Qt-specific interfaces.

---

## 1. Guiding Principles (Qt Extension)

| Rule | Why |
|------|-----|
| **`qt_view.py` implements `ViewProtocol`** | The Engine doesn't know if it's talking to CLI or Qt. Drop-in replacement. |
| **`maze_canvas.py` imports maze types only** | Same read-only type dependency as `view.py` — `Direction`, `DoorState`, `FogMapCell`, etc. Never imports `db`. |
| **Event-driven, not blocking** | Qt uses an event loop (`QApplication.exec()`). The Engine must expose public callbacks, not a `while True` loop. |
| **Signals → Engine → View** | User clicks a button → `command_issued` signal fires → Engine processes → Engine calls `QtView.display_*()` to update UI. |
| **CLI still works** | `python main.py` → CLI. `python main.py --gui` → Qt. Both use the same Engine. |

---

## 2. New Module Interfaces

### 2.1 `maze_canvas.py` — Maze Grid Widget

```python
class MazeCanvas(QWidget):
    """Renders the Waxworks maze as a 2D grid with fog-of-war.
    
    Receives FogMapCell data from QtView and paints it using QPainter.
    Does NOT call any Engine or Maze methods directly.
    """

    def __init__(self, parent: QWidget = None):
        """Initialize the canvas. Sets minimum size and background."""
        ...

    def update_map(self, fog_map: list[list[FogMapCell]]) -> None:
        """Receive new fog map data and trigger repaint.
        
        Called by QtView.display_fog_map() after each game state change.
        Stores the data and calls self.update() to schedule a paintEvent.
        """
        ...
```

#### Rendering Contract

| Cell Visibility | Background | Content |
|----------------|------------|---------|
| `CURRENT` | Radial gradient (purple glow) | `@` player symbol with golden glow |
| `VISITED` | Dark purple `#372d4b` | Figure initials `DV`/`AL`/`CL`, or `EN`/`EX`, or `░░` |
| `VISIBLE` | Dimmer purple `#2d233c` | `··` (seen but not entered) |
| `HIDDEN` | Near-black `#191223` | `▓` fog character |

| Door State | Indicator |
|-----------|-----------|
| `OPEN` | Green bar on cell edge |
| `LOCKED` | Gold bar + 🔒 icon |
| `WALL` | No indicator (dark edge) |

---

### 2.2 `qt_view.py` — Qt View (Implements ViewProtocol)

```python
class QtView(QMainWindow):
    """PySide6 GUI for Waxworks: The Midnight Curse.
    
    Implements ViewProtocol from interfaces.md §3.4.
    The Engine calls display_*() methods to update the UI.
    User actions emit the command_issued signal.
    """

    # -- Signal: how user actions reach the Engine --
    command_issued = Signal(str)  # Emits: "move north", "answer A", "save", etc.

    def __init__(self):
        """Build the main window: canvas (left) + sidebar (right)."""
        ...
```

#### ViewProtocol Methods (all 11 — same signatures as CLI View)

```python
def display_welcome(self) -> None: ...
def display_room(self, room: Room, position: Position,
                 curse_level: int, game_state: GameState) -> None: ...
def display_fog_map(self, fog_map: list[list[FogMapCell]]) -> None: ...
def display_move_result(self, result: str, direction: str) -> None: ...
def display_confrontation(self, question_dict: dict) -> None: ...
def display_answer_result(self, result: str, curse_level: int) -> None: ...
def display_save_result(self, success: bool, error: str = "") -> None: ...
def display_load_result(self, success: bool) -> None: ...
def display_endgame(self, status: GameStatus, curse_level: int,
                    rooms_explored: int = 0, total_rooms: int = 25,
                    figures_defeated: int = 0, total_figures: int = 3) -> None: ...
def display_error(self, message: str) -> None: ...
def get_input(self, prompt: str = "") -> str: ...
```

> [!IMPORTANT]
> `get_input()` is a **no-op** in Qt mode. It exists to satisfy ViewProtocol but returns `""` immediately. User input arrives via `command_issued` signal instead.

#### TriviaDialog

```python
class TriviaDialog(QDialog):
    """Modal dialog for wax figure confrontations.
    
    Launched by QtView.display_confrontation().
    Shows figure name, question text, and A/B/C answer buttons.
    """

    answer_selected = Signal(str)  # Emits "A", "B", or "C" on button click

    def __init__(self, question_dict: dict, parent: QWidget = None):
        """Build the dialog from the Engine's question dict.
        
        Expected dict keys: figure_name, question_text, choices, correct_key.
        'choices' may be dict[str, str] ({"A": "text"}) or list[dict].
        """
        ...
```

---

## 3. Engine Adapter Contract (Sowmya's Work)

The current `Engine.run()` is a **blocking `while True` loop** that calls `view.get_input()`. For Qt, the Engine must become **callback-driven**.

### Required Changes to `main.py`

```python
class Engine:
    """Orchestrates game logic. Adapted for both CLI and Qt modes."""

    # -- Existing private methods → make PUBLIC --

    def handle_command(self, command: str) -> None:
        """Parse and dispatch a player command.
        Renamed from _handle_command(). Called by Qt on button click.
        """
        ...

    def handle_move(self, direction_str: str) -> None:
        """Attempt to move. Renamed from _handle_move()."""
        ...

    def handle_answer(self, answer_key: str) -> None:
        """Submit trivia answer. Renamed from _handle_answer()."""
        ...

    def handle_map(self) -> None:
        """Refresh the fog map display. Renamed from _handle_map()."""
        ...

    # -- NEW: State refresh for Qt --

    def refresh_display(self) -> None:
        """Push current state to the View.
        
        Called after every command in Qt mode.
        Fetches room, position, fog map, and calls view.display_*().
        """
        ...

    # -- Entry points --

    def run(self) -> None:
        """Blocking CLI game loop (unchanged for CLI mode)."""
        ...

    def start_qt(self, app: QApplication) -> None:
        """Non-blocking Qt startup.
        
        Wires command_issued signal → handle_command(),
        calls display_welcome(), initial refresh_display(),
        then hands control to app.exec().
        """
        ...
```

### Dual-Mode Entry Point

```python
# main.py — bottom of file
if __name__ == "__main__":
    import sys

    maze = Maze()
    repo = Repository(db_path="waxworks.db")

    if "--gui" in sys.argv:
        from PySide6.QtWidgets import QApplication
        from qt_view import QtView

        app = QApplication(sys.argv)
        view = QtView()
        engine = Engine(maze, repo, view)
        engine.start_qt(app)
    else:
        from view import View

        view = View()
        engine = Engine(maze, repo, view)
        engine.run()
```

---

## 4. Signal Flow Diagram

```
┌──────────────┐   command_issued("move north")   ┌────────────────┐
│  Qt Buttons  │  ─────────────────────────────▶   │ Engine         │
│  (QtView)    │                                   │ .handle_command│
└──────────────┘                                   └───────┬────────┘
                                                           │
                                                    maze.move(NORTH)
                                                           │
                                                           ▼
┌──────────────┐   view.display_move_result()      ┌────────────────┐
│  QtView      │  ◀─────────────────────────────   │ Engine         │
│  (updates UI)│   view.display_room()             │ .refresh_display│
│              │   canvas.update_map()             │                │
└──────────────┘                                   └────────────────┘
```

---

## 5. Dependency Rules (Updated)

| Module | May Import | May NOT Import | I/O |
|--------|-----------|----------------|-----|
| `maze.py` | `enum`, `dataclasses`, `typing` | `db`, `main`, `view`, `qt_view` | **No** |
| `db.py` | `sqlmodel`, `typing`, stdlib | `maze`, `main`, `view`, `qt_view` | **No** |
| `maze_canvas.py` | `maze` (types only), `PySide6` | `db`, `main` | QPainter only |
| `qt_view.py` | `maze` (types), `maze_canvas`, `PySide6` | `db` | Qt widgets |
| `view.py` | `maze` (types only), stdlib | `db` | `print()`/`input()` |
| `main.py` | `maze`, `db`, `view`, `qt_view`, `PySide6` | — | Via view |

---

## 6. Testing Contracts

### `tests/test_qt_view.py` — Mario

| Test | Validates |
|------|-----------|
| `test_qt_view_has_all_protocol_methods` | All 11 ViewProtocol methods exist |
| `test_command_issued_signal_emits` | Button clicks fire `command_issued` with correct strings |
| `test_trivia_dialog_emits_answer` | `TriviaDialog.answer_selected` emits A/B/C |
| `test_curse_meter_updates` | `display_room()` updates the progress bar value and color |
| `test_canvas_accepts_fog_map` | `MazeCanvas.update_map()` stores data without crashing |

### `tests/test_engine_qt.py` — Sowmya

| Test | Validates |
|------|-----------|
| `test_handle_command_dispatches_move` | `handle_command("move north")` calls `maze.move()` |
| `test_handle_command_dispatches_answer` | `handle_command("answer A")` calls `maze.attempt_answer()` |
| `test_refresh_display_calls_view` | `refresh_display()` calls `view.display_room()` and `view.display_fog_map()` |
| `test_dual_mode_startup` | `--gui` flag imports Qt; no flag uses CLI |

---

*Contract version: 1.0 — Qt GUI Extension · Waxworks: The Midnight Curse*
