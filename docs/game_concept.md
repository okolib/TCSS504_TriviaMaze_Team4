# Boma's Trivia Maze Concept

## Section A: The Theme (The Hook)
**Title:** "Vaultbreak: Trivia Maze Escape"

You wake up inside a high-security research vault that has gone into lockdown. The building’s AI is malfunctioning and has turned the facility into a shifting maze. Each locked door requires solving a trivia question to open. The objective is to navigate the maze, collect keycards, and reach the exit before your “energy” runs out.

**Core Loop:**
Explore → Attempt door → Answer trivia → Door unlocks (or penalty) → Move → Repeat until exit.

**Motivation:**
You’re escaping the vault while recovering “data shards” (optional collectibles) that increase score.

---

## Section B: The Test Strategy

We will use Test Driven Development (TDD). Before implementing full features, we will write tests to verify each rule independently (movement, wall collision, scoring, question logic, saving/loading).

### 1) Happy Path (Standard Successful Interaction)
**Scenario:** Player answers correctly and progresses.
- Player is at (x,y) facing a locked door.
- Player selects an answer and it is correct.
- Expected:
  - Door state changes from `locked` → `open`
  - Player can move into the next cell
  - Score increases (e.g., +10)
  - UI updates to show new position and score

### 2) Edge Case (Boundary Condition)
**Scenario:** Player attempts to move into a wall or outside the maze.
- Player is at the top row and tries to move North.
- Expected:
  - System blocks movement
  - Player position remains unchanged
  - UI shows a message like “Blocked: wall/out of bounds”
  - No score change

### 3) Failure State (Error Handling)
**Scenario:** Save file is missing or corrupted.
- Player clicks “Load Game”
- Save file is unreadable OR schema mismatch
- Expected:
  - Game catches exception (no crash)
  - Displays “Save corrupted, starting new game”
  - Loads a new default game state safely

### 4) Algorithm Test (Pathfinding / Solvability Check)
**Goal:** Ensure randomly generated maze is solvable (exit reachable from start).

**Chosen Algorithm:** BFS (Breadth-First Search)

**Logic (No code yet):**
- Treat each open cell as a node in a graph.
- From the start cell (0,0), BFS explores all reachable cells using a queue.
- Mark visited cells to avoid loops.
- If BFS ever reaches the exit cell (exit_x, exit_y), the maze is solvable.
- If BFS finishes without reaching the exit, regenerate the maze.

**Why BFS fits:**
- BFS guarantees we explore in “layers,” making it very reliable for reachability checks.
- (Bonus for next week) BFS also gives the shortest path if we want hints.

---

## Section C: The Architecture Map (Patterns)

### MVC Mapping

#### Model (Data + Rules)
Planned scripts/classes:
- `Maze` (grid structure, walls, start, exit, generation)
- `Cell/Room` (properties like wall/door/visited, optional items)
- `QuestionBank` (loads questions from SQLite, returns random question)
- `GameState` (player position, score, inventory, timer/energy)
- `SaveLoad` (serialize/deserialize game state to file or DB)

#### View (GUI)
**GUI Library:** PyQt6 (or Tkinter if team chooses simpler)
- `MainWindow` (overall layout)
- `MazeView` (renders grid, player, exit, doors)
- `QuestionDialog` (shows question + choices)
- `HUDPanel` (score, timer, inventory, messages)

#### Controller (Glue)
- `main.py` starts the app
- `GameController` handles:
  - input events (move buttons/keys)
  - calls model logic (valid move? locked door?)
  - triggers question prompts
  - updates view based on model changes
  - calls save/load

### Additional patterns
- **Singleton** for database connection (one SQLite connection manager)
- **Factory** for question creation/loading (different categories)
- **Observer/Signals** (Qt signals) so model updates automatically refresh UI

---

## AI Review Summary
**AI review feedback:**
- Confirmed MVC separation is good: Maze/GameState in Model, PyQt widgets in View, GameController in Controller.
- Recommended BFS for solvability because it cleanly validates reachability and can later provide shortest-path hints.
- Suggested robust save/load error handling (try/except + fallback new game) to prevent crashes.

**What I will adopt:**
- Use BFS solvability check before finalizing a generated maze.
- Use a single DB manager for SQLite access.
- Add explicit tests for “wall collision” and “corrupt save handling.”

**What I will not adopt (for now):**
- Multiplayer or network features (too large for scope).
