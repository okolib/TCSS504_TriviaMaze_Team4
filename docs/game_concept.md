# Sowmya's Trivia Maze Concept
# Waxworks: The Midnight Curse  


## Section A: The Theme (The Hook)

### Game Title
**Waxworks: The Midnight Curse**

### Setting
An abandoned museum—the **Grand Hall of History**—explored at night. The player is an urban explorer who broke in on a dare, not a tourist.
Chose this concept because it helps to ask different kinds of questions within the same theme.

### The Backstory

| Element | Description |
|--------|-------------|
| **Hook** | You are an urban explorer who broke into the abandoned "Grand Hall of History" on a dare. |
| **Twist** | The museum is a **Soul Trap**. The "wax figures" are the trapped spirits of history's greatest minds, frozen in time by **The Curator** (the villain). |
| **Stake** | The doors vanish when you enter. Your hand is turning shiny and stiff—you are slowly turning into wax. You have until **sunrise** (or until your **Wax Meter** hits 100%) to break the curse, or you become the newest exhibit forever. |

### Maze layout (example)

The maze is solvable from start to exit, with the winning path passing through multiple wax-figure rooms (e.g. Da Vinci → Lincoln → Cleopatra) as mandatory gates—there is no route to the exit that bypasses any of them. Between each pair of wax-figure rooms the player travels a stretch of corridors (turns, branches, dead ends), so reaching the exit involves both navigation and answering at each figure. The player sees only their current room and open neighboring cells; the rest of the maze is hidden until visited.

![Waxworks maze map — solvable path through multiple wax figures, player view highlighted](docs/waxworks_maze_map_v3.png)

### Trivia: Wax Figures & Questions

| # | Figure | Zone | Question | A | B | C | **Answer** |
|---|--------|------|----------|---|---|---|------------|
| 1 | **Leonardo da Vinci** (Artist) | Art Gallery | I painted the most famous woman in the world—no eyebrows, mysterious smile. Name the painting. | The Last Supper | The Mona Lisa | Starry Night | **B** |
| 2 | **Abraham Lincoln** (Leader) | American History Wing | 16th President, "Honest Abe," led the US through the Civil War. My face is on the smallest US coin. Which? | The Quarter | The Dime | The Penny | **C** |
| 3 | **Cleopatra** (Queen) | Ancient History Hall | Last Pharaoh of Egypt. I died by the bite of a snake. What kind? | A Python | An Asp (Cobra) | A Rattlesnake | **B** |
| 4 | **Albert Einstein** (Genius) | Science Lab | Relative to you I stand still; relative to the sun we move fast. What world-changing formula did I write? | F=ma | E=mc² | a²+b²=c² | **B** |
| 5 | **William Shakespeare** (Playwright) | Library | "To be, or not to be?" In *Romeo and Juliet*, which family did Romeo belong to? | The Capulets | The Montagues | The Potters | **B** |
| 6 | **Christopher Columbus** (Explorer) | Map Room | In 1492 I sailed the ocean blue seeking a route to India. Where did I land? | Australia | The Americas (Bahamas) | Japan | **B** |

---

## Section B: The Test Strategy (QA & Algorithms)

We use **Test Driven Development (TDD)**. Below is how we will verify the system.

### The Happy Path

**Scenario:** Standard successful flow from start to exit, including navigation between wax-figure rooms.

1. Player starts at the entrance and **moves** through corridors (N/S/E/W). Only the current room and open neighboring cells are visible.
2. To progress toward the exit, the player must pass through **wax-figure rooms** in order (e.g., Da Vinci → Lincoln → Cleopatra). There is no path that skips any figure.
3. When the player enters a room with a **wax figure** and a **locked passage** ahead, they trigger the figure → system shows the **trivia question** and choices (A, B, C).
4. Player selects the **correct answer** (e.g., B for Mona Lisa).
5. System validates answer → **passage unlocks**. **Wax Meter** does not increase (or decreases slightly, per design).
6. Player **moves** through the unlocked passage and continues along the path (possibly through more corridors, turns, or dead ends) until the next wax-figure room or the exit.
7. After passing through **all** wax-figure rooms on the path and answering correctly each time, the player reaches the **exit** before the Wax Meter hits 100% → **win**.

**Testable:** Correct answer → door state changes to unlocked; player position updates after each move; Wax Meter value as specified; winning path requires traversing multiple rooms between figures.

---

### The Edge Case

**Scenario:** Boundary and invalid-input behavior.

| Edge Case | Input / Condition | Expected Behavior |
|-----------|-------------------|-------------------|
| **Move into locked passage** | Player tries to move through a door that has an unanswered (or failed) trivia. | System **rejects** the move. Player stays at current (x, y). Message: e.g. *"The way is sealed. Answer the figure first."* |
| **Move off the maze** | Player issues move North at the northernmost row (or any out-of-bounds direction). | System **rejects** the move. Coordinates remain valid; no crash. |
| **Wax Meter at 99%** | Player has one "strike" left before turning to wax. | Next **wrong** answer → Wax Meter 100% → **game over**. Next **correct** answer → progression allowed. |
| **Multiple correct answers in one room** | Room has one figure but multiple doors (if design allows). | Only the **linked** door for that figure unlocks; other doors stay locked until their figure is answered. |

**Testable:** Invalid move leaves (x, y) unchanged; Wax Meter never exceeds 100%; no array/index out-of-bounds.

---

### The Failure State

**Scenario:** Error handling when something goes wrong.

| Failure | Trigger | Expected Behavior |
|---------|--------|-------------------|
| **Corrupt or missing save file** | Load game → save file is missing, truncated, or invalid. | System **catches** the exception. Option to start **new game** or exit; no crash. No partial/corrupt state loaded. |
| **Trivia data missing or malformed** | Game loads questions from a file (JSON/DB); file is missing or has wrong format. | System **catches** the error. Use a **fallback** set of questions if available; otherwise show a clear error and exit gracefully (no silent crash). |
| **Wrong answer** | Player selects A or C when correct is B. | **Wax Meter** increases by defined amount. Passage **stays locked**. Player may retry the same question (if design allows) or the attempt counts as a strike; game over when Wax Meter hits 100%. (There is no alternate path around a wax figure—the only way forward is through the correct answer or eventual game over.) |

**Testable:** Save load throws/catches and recovers; trivia load has fallback or safe exit; wrong answer updates Wax Meter and does not unlock the door.

---

### The Solvability Check (Algorithm Selection)

**Problem:** How do we ensure the randomly generated museum maze is solvable and the exit is reachable?

**Solution:** We will use **BFS (Breadth-First Search)** to verify solvability.

**Logic:**

- Model the museum as a **graph**: each room is a node; each unlocked passage is an edge. (For generation, we can treat "answer correct → unlock" as the condition for an edge.)
- Run **BFS** from the **starting room** (entry node). Only traverse edges that are either always open or that we consider "unlockable" by answering the figure in that room.
- If the **exit room** is in the set of visited nodes, the maze is **solvable**.
- Optionally: during **maze generation**, build the layout so that the exit is always reachable (e.g., generate a path from start to exit, then add extra rooms/doors), and then run BFS as a **verification** step.

**Why this ensures a valid path exists (graph traversal):** BFS explores the graph level by level from the start node: it visits the start, then all neighbors one step away, then all nodes two steps away, and so on, until no new nodes can be reached. Every node that is reachable from the start (via any sequence of open or unlockable passages) is eventually added to the visited set. So if the exit is in that set, we have proved that at least one path from start to exit exists; if the exit is not in the set after BFS finishes, then no such path exists. Thus BFS gives a clear, exhaustive check for solvability without having to enumerate every possible route.

*Note: Code is not written here—only the logic.*

---

## Section C: The Architecture Map (Patterns)

### MVC Mapping

| Layer | In our game |
|-------|-------------|
| **Model** | **Rooms**, **passages** (locked/unlocked), **wax figures** (identity, zone, question, correct answer). **Player state**: position (x, y), **Wax Meter**, current room. **Game state**: win, lose, time/curse rules. **Trivia set**: list of questions and answers. |
| **View** | Renders: maze/room map, current room description, wax figure and question text, choices (A/B/C), Wax Meter, messages ("The way is sealed", "You turned to wax", "You escaped!"). **GUI library: PyQt6** (or Tkinter as fallback) for a professional desktop interface. |
| **Controller** | **Input**: move (N/S/E/W), select answer (A/B/C), start new game, load/save. **Logic**: validate move (bounds, locked door), check answer, update Wax Meter, unlock passage, update position, check win/lose (exit reached or Wax Meter 100%). |

### Other Patterns (if they fit)

- **State:** Game states (e.g., exploring, answering trivia, game over, victory) with clear transitions.
- **Strategy (optional):** Different movement or trivia behaviors (e.g., different maze layouts or difficulty) without changing core controller logic.
- **Repository / Data loader:** Load trivia and room data from files or DB so Model stays separate from I/O.

---

### AI Review Summary

**AI feedback (summary):** The blueprint was reviewed for assignment alignment. Suggestions included: (1) Explicitly naming the GUI library (e.g., PyQt6) in the View—**adopted**; (2) Adding script/entry-point names (e.g., `main.py`, `maze.py`, `question.py`) for clarity—**optional**, kept conceptual mapping for now; (3) Ensuring all four test scenarios (Happy Path, Edge Case, Failure State, Algorithm) are clearly distinct—**already satisfied**. The BFS solvability explanation and theme were noted as strong. No major changes were required beyond the View library and this AI review section.

---

### Solvability algorithm — brief summary

**Why BFS ensures a valid path exists (graph traversal):** BFS explores the graph level by level from the start node: it visits the start, then all neighbors one step away, then all nodes two steps away, and so on, until no new nodes can be reached. Every node that is reachable from the start (via any sequence of open or unlockable passages) is eventually added to the visited set. So if the exit is in that set, we have proved that at least one path from start to exit exists; if the exit is not in the set after BFS finishes, then no such path exists. Thus BFS gives a clear, exhaustive check for solvability without having to enumerate every possible route.

---

*Document version: 1.0 — Waxworks: The Midnight Curse*
