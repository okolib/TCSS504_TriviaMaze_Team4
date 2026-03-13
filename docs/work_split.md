# Work Split — Waxworks: The Midnight Curse

> Final Maze Assignment · TCSS 504 · Team 4

---

## Team Members & Responsibilities

### Mario — GUI / View Engineer

**Branch:** `feat/qt-gui-mario`

| File | Action | Description |
|------|--------|-------------|
| `qt_view.py` | NEW | PySide6 implementation of `ViewProtocol` — main window, sidebar, trivia dialog |
| `maze_canvas.py` | NEW | `QPainter`-based maze grid with fog-of-war rendering |
| `main.py` | MODIFIED | Engine refactor for dual-mode (CLI + Qt callback-driven) |
| `requirements.txt` | MODIFIED | Added `PySide6>=6.5` |
| `docs/qt_contracts.md` | NEW | Interface contracts for Qt GUI components |
| `tests/test_qt_view.py` | NEW | 35 contract tests for Qt View and MazeCanvas |
| `docs/work_split.md` | NEW | This document |
| `README.md` | MODIFIED | Updated with install/run instructions |

---

### Sowmya — Engine / Controller Engineer

**Branch:** `feat/engine-qt-adapter`

| File | Action | Description |
|------|--------|-------------|
| `main.py` | REVIEW/MODIFY | Review Engine refactor, adjust as needed |

**Responsibilities:**
- Review and own the Engine's callback-driven API
- Ensure Engine works cleanly with both CLI and Qt views
- Integration testing across modules

---

### Megan — Maze / Domain Logic Engineer

**Branch:** `feat/maze-enhancements`

| File | Action | Description |
|------|--------|-------------|
| `maze.py` | MODIFY | Maze enhancements (optional: randomization, larger grids) |
| `tests/test_maze_contract.py` | MODIFY | Tests for new maze features |

**Responsibilities:**
- Domain logic improvements
- Verify fog-of-war data is sufficient for Qt canvas
- Maze layout design and documentation

---

### Boma — Database / Persistence Engineer

**Branch:** `feat/db-enhancements`

| File | Action | Description |
|------|--------|-------------|
| `db.py` | MODIFY | Question pool expansion, optional `list_saves()` |
| `tests/test_repo_contract.py` | MODIFY | Tests for new DB features |

**Responsibilities:**
- Expand trivia question pool
- Add `list_saves()` for GUI save slot selection
- Data integrity and migration safety

---

## Integration Order

```
1. Megan (maze)     → PR into feat/final-maze
2. Boma  (db)       → PR into feat/final-maze
3. Sowmya (engine)  → PR into feat/final-maze
4. Mario (qt-gui)   → PR into feat/final-maze
5. Final            → PR feat/final-maze into main
```

Each merge must pass all existing tests before the next PR is merged.
