# Waxworks: The Midnight Curse — Setup & Run

## Prerequisites

- **Python 3.10+**

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mrod440/TCSS504_TriviaMaze_Team4.git
   cd TCSS504_TriviaMaze_Team4
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   This installs:
   - `sqlmodel` — SQLite persistence via SQLModel/SQLAlchemy
   - `PySide6` — Qt 6 GUI framework

## Running the Game

### Qt GUI Mode (recommended)
```bash
python main_gui.py
```
Or:
```bash
python main.py --gui
```

### CLI Mode
```bash
python main.py
```

## Controls (GUI Mode)

| Input | Action |
|-------|--------|
| `↑` / `W` | Move North |
| `↓` / `S` | Move South |
| `←` / `A` | Move West |
| `→` / `D` | Move East |
| Navigation buttons | Click ▲N / ▼S / ◀W / ▶E |
| Trivia answers | Click answer in popup dialog |
| View toggle | Switch between first-person and top-down map |
| Load / Mute | Sidebar action buttons |

## Running Tests
```bash
pytest
```

## Notes

- The database (`waxworks.db`) is **auto-created and seeded** on first run — no manual setup needed.
- Save files are stored in the same SQLite database.
- The maze is **randomized** each game — every playthrough has a unique layout.
