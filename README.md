# Waxworks: The Midnight Curse 🕯

A trivia maze game with fog-of-war, built in Python with PySide6.

Navigate the cursed museum, confront wax figures with trivia questions,
and escape before the Curse Meter reaches 100%.

---

## Quick Start

### Install

```bash
pip install -r requirements.txt
```

### Play

```bash
# Qt GUI (recommended)
python main.py --gui

# Terminal / CLI
python main.py
```

### Run Tests

```bash
python -m pytest tests/ -v
```

---

## Architecture

```
maze.py    →  main.py (Engine)  →  qt_view.py (Qt GUI)
(Domain)         ↕                  maze_canvas.py
              db.py (SQLite)        view.py (CLI fallback)
```

| Module | Owner | Responsibility |
|--------|-------|---------------|
| `maze.py` | Megan | Domain logic, rules, fog-of-war |
| `db.py` | Boma | SQLModel + SQLite persistence, question bank |
| `main.py` | Sowmya | Engine orchestration, command dispatch |
| `qt_view.py` | Mario | PySide6 GUI, maze canvas, trivia dialogs |
| `view.py` | Mario | CLI fallback (original interface) |

### Design Patterns

- **MVC** — Model (`maze.py`), View (`qt_view.py` / `view.py`), Controller (`main.py`)
- **Repository Pattern** — `db.py` isolates domain from persistence
- **Observer Pattern** — Qt Signals/Slots for event-driven UI
- **ViewProtocol** — Swappable views via Python Protocol (CLI ↔ Qt)
- **Dependency Injection** — Engine accepts any View + Repository at construction

---

## Game Features

- 🗺 **5×5 Maze** with fog-of-war exploration
- 🗿 **3 Wax Figures** — Da Vinci, Lincoln, Cleopatra — each with trivia
- 🕯 **Curse Meter** — Wrong answers increase the curse (+20 each)
- 💾 **Save/Load** — SQLite-backed game persistence
- 🎨 **Qt GUI** — Dark midnight theme with visual maze canvas

---

## Project Structure

```
├── main.py              # Engine — game loop & command dispatch
├── maze.py              # Domain logic — grid, movement, trivia
├── db.py                # Persistence — SQLModel + SQLite
├── qt_view.py           # Qt GUI — ViewProtocol implementation
├── maze_canvas.py       # QPainter maze grid renderer
├── view.py              # CLI view — original terminal interface
├── requirements.txt     # Dependencies (sqlmodel, PySide6)
├── tests/
│   ├── test_maze_contract.py
│   ├── test_repo_contract.py
│   ├── test_view_contract.py
│   ├── test_qt_view.py
│   └── test_integration.py
└── docs/
    ├── interfaces.md    # Module interface contracts
    ├── qt_contracts.md  # Qt GUI interface contracts
    ├── work_split.md    # Team responsibilities
    └── rfc_merged.md    # Original design RFC
```

---

## Requirements

- Python 3.10+
- PySide6 ≥ 6.5
- SQLModel ≥ 0.0.14