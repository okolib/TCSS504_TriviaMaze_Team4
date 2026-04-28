# Waxworks: The Midnight Curse 🕯

A trivia maze game built in Python with PySide6. Navigate a cursed museum, confront
wax figures with trivia questions, and escape before the Curse Meter reaches 100%.

> **TCSS 504 — Team 4** · University of Washington Tacoma

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/mrod440/TCSS504_TriviaMaze_Team4.git
cd TCSS504_TriviaMaze_Team4
pip install -r requirements.txt

# 2. Play (Qt GUI — recommended)
python main_gui.py

# 3. Or play in the terminal
python main.py
```

> See [INSTALL.md](INSTALL.md) for full setup details and controls reference.

### Requirements

- Python 3.10+
- PySide6 ≥ 6.5
- SQLModel ≥ 0.0.14

### Running Tests

```bash
python -m pytest tests/ -v
```

---

## How to Play

You are trapped in a cursed wax museum at midnight. To escape:

1. **Explore** the randomized 8×8 maze using compass directions (N/S/E/W)
2. **Confront** wax figures that block locked gates — answer their trivia to pass
3. **Defeat all 5 figures** to unlock the path to the exit
4. **Escape** before the Curse Meter reaches 100%

Wrong answers increase the curse by 20%. There are no alternate routes around
a wax figure — you must answer correctly to proceed.

### Controls (GUI Mode)

| Input | Action |
|-------|--------|
| `↑`/`W`, `↓`/`S`, `←`/`A`, `→`/`D` | Move North, South, West, East |
| Navigation buttons | Click ▲N / ▼S / ◀W / ▶E |
| Trivia answers | Click answer in popup dialog |
| View toggle | Switch between first-person and top-down map |

### Controls (CLI Mode)

| Command | Action |
|---------|--------|
| `move north/south/east/west` | Move in a direction |
| `answer A/B/C` | Answer a trivia question |
| `save` / `load` | Save or load your game |
| `map` | Display the fog-of-war map |
| `quit` | Exit the game |

---

## Architecture

The project follows a strict **Model–View–Controller** architecture with
dependency injection and protocol-based interfaces.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  maze.py    │     │  main.py         │     │  qt_view.py     │
│  (Model)    │◄───►│  (Engine/Ctrl)   │◄───►│  (Qt GUI View)  │
│             │     │                  │     │  maze_canvas.py │
│  Pure       │     │  Wires all       │     │  first_person_  │
│  domain     │     │  modules         │     │  canvas.py      │
│  logic      │     │  together        │     ├─────────────────┤
└─────────────┘     │                  │     │  view.py        │
                    │                  │◄───►│  (CLI View)     │
                    │                  │     └─────────────────┘
                    │                  │
                    │                  │◄───►┌─────────────────┐
                    └──────────────────┘     │  db.py          │
                                            │  (Repository)   │
                                            │  SQLite + ORM   │
                                            └─────────────────┘
```

### Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `maze.py` | Domain logic: grid, rooms, doors, movement, fog-of-war, game state, win/loss conditions |
| `db.py` | SQLModel + SQLite persistence: question bank, save/load, anti-repeat logic |
| `main.py` | Engine orchestration: wires Model ↔ View ↔ Repository, handles commands |
| `qt_view.py` | PySide6 GUI: sidebar, trivia dialogs, compass navigation, audio |
| `first_person_canvas.py` | QPainter pseudo-3D dungeon renderer with zone-tinted walls |
| `maze_canvas.py` | QPainter top-down fog-of-war grid view |
| `view.py` | CLI fallback: ASCII map, terminal I/O |
| `audio.py` | Sound effects and ambient music playback |
| `main_gui.py` | Dedicated GUI launcher with resume-or-new-game dialog |

### Design Patterns

| Pattern | Where | Why |
|---------|-------|-----|
| **MVC** | `maze.py` / `main.py` / `qt_view.py` | Separates domain, control, and presentation |
| **Repository** | `db.py` | Isolates persistence from domain logic |
| **Observer** | Qt Signals/Slots | Event-driven GUI without polling |
| **ViewProtocol** | `qt_view.py`, `view.py` | Swappable views via Python `Protocol` — CLI ↔ Qt |
| **Dependency Injection** | `Engine.__init__()` | Engine accepts any View + Repository at construction |
| **Strategy** | Maze generation | Randomized DFS + BFS critical path, seed param for deterministic tests |

### Interfaces & Contracts

The codebase enforces strict boundary rules:

| Rule | Rationale |
|------|-----------|
| `maze.py` imports **nothing** | Domain logic is pure Python — no I/O, no `print()`, no frameworks |
| `db.py` imports **nothing from maze** | Persistence is a separate concern; stores JSON-safe primitives only |
| `view.py` imports **maze types only** | Read-only type dependency for rendering (enums, dataclasses) |
| `main.py` is the **only wiring point** | Imports all modules, translates between them, orchestrates the game loop |
| Data crosses boundaries as **dicts/primitives** | Complex objects are converted at the boundary by `main.py` |

> Full contract specs: [interfaces.md](docs/interfaces.md) · [qt_contracts.md](docs/qt_contracts.md)

---

## Work Split

| Team Member | Role | Primary Files |
|-------------|------|---------------|
| **Mario** | GUI / View Engineer | `qt_view.py`, `maze_canvas.py`, `first_person_canvas.py`, `main_gui.py`, bug fixes |
| **Sowmya** | Engine / Controller, Audio & Assets | `main.py`, `main_gui.py`, `maze_canvas.py`, `audio.py`, portraits, audio assets, bug fixes |
| **Megan** | Maze / Domain Logic, Core GUI/CLI | `maze.py`, `view.py`, randomized maze generation, domain tests |
| **Boma** | Database / Persistence | `db.py`, SQLModel schema, question bank, save/load |

All team members contributed to **bug hunting and fixes** across the codebase.

> Detailed responsibilities: [work_split.md](docs/work_split.md)

---

## Key Design Decisions

1. **Randomized maze each game** — Uses DFS spanning tree + BFS critical path
   to guarantee solvability. A `seed` parameter enables deterministic tests.

2. **Dual-mode engine** — `main.py` supports both a blocking CLI loop (`run()`)
   and a callback-driven Qt mode (`start_qt()` + `handle_*` methods) without
   duplicating game logic.

3. **Protocol-based views** — `ViewProtocol` (Python `Protocol`) allows the
   Engine to work with any view implementation. CLI and Qt views are fully
   interchangeable.

4. **Anti-repeat question logic** — The database tracks asked questions
   per-figure and persists this across save/load, ensuring players don't see
   the same question twice in a session.

5. **Absolute compass navigation** — Arrow keys and buttons map to fixed
   compass directions (N/S/E/W) rather than relative (forward/back) to
   avoid confusion in the first-person view.

---

## Known Limitations

- **Integration test flakiness** — `test_full_winning_game` can occasionally
  fail due to randomized figure placement; the BFS pathfinder may encounter
  figures in an unexpected order.
- **No difficulty settings** — Curse penalty is fixed at +20 per wrong answer.
- **Single save slot** — Only one game can be saved at a time (`"default"` slot).
- **No question editor** — Trivia questions are seeded from a hardcoded bank
  in `db.py`; there is no UI to add or edit questions.
- **Audio requires PySide6 multimedia** — Sound playback depends on FFmpeg
  being available via Qt's multimedia backend.

---

## Project Structure

```
├── main.py                  # Engine — game loop & command dispatch
├── main_gui.py              # Qt GUI launcher with resume dialog
├── maze.py                  # Domain logic — grid, movement, fog-of-war
├── db.py                    # Persistence — SQLModel + SQLite
├── qt_view.py               # Qt GUI — ViewProtocol implementation
├── first_person_canvas.py   # QPainter pseudo-3D dungeon renderer
├── maze_canvas.py           # QPainter top-down fog-of-war grid
├── view.py                  # CLI view — terminal interface
├── audio.py                 # Sound effects & ambient music
├── requirements.txt         # Dependencies (sqlmodel, PySide6)
├── INSTALL.md               # Setup, run, and controls reference
├── assets/
│   ├── audio/               # WAV files (ambient, effects)
│   └── portraits/           # Wax figure portrait PNGs
├── tests/
│   ├── test_maze_contract.py
│   ├── test_repo_contract.py
│   ├── test_view_contract.py
│   ├── test_qt_view.py
│   └── test_integration.py
└── docs/
    ├── interfaces.md        # Module interface contracts
    ├── qt_contracts.md      # Qt GUI interface contracts
    ├── work_split.md        # Team responsibilities
    ├── game_concept.md      # Original game design document
    ├── rfc_merged.md        # Design RFC
    └── BRANCH_CHANGELOG.md  # AI-readable branch changelog
```