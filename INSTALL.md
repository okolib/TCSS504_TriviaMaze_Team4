# Waxworks: The Midnight Curse — Setup & Run

## Prerequisites

- **Python 3.10+**

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mrod440/TCSS504_TriviaMaze_Team4.git
   cd TCSS504_TriviaMaze_Team4
   git checkout feat/qt-gui-mario
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
python main.py --gui
```

### CLI Mode
```bash
python main.py
```

## Running Tests
```bash
pytest
```

## Notes

- The database (`waxworks.db`) is **auto-created and seeded** on first run — no manual setup needed.
- Save files are stored in the same SQLite database.
