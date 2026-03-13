# Replayability Proposals

> **Status:** Option A implemented. Options B–D documented for future sprints.
>
> **Problem:** The maze places figures at the same positions every game
> (Da Vinci at 1,1 — Lincoln at 2,2 — Cleopatra at 3,3). Same path,
> same encounters = low replayability.

---

## Option A — Randomize Figure Placement ✅ IMPLEMENTED

**Owner:** Mario (GUI branch) — no teammate dependency
**Effort:** ~30 min | **Impact:** Medium

### What It Does
- Keeps the staircase corridor *structure* unchanged (tests still pass)
- On each new game, randomly picks 3 rooms from the list of eligible "figure rooms" (rooms with a locked gate adjacent)
- Shuffles which figure goes where (Da Vinci might be at (3,3), Cleopatra at (1,1), etc.)

### How It Works
```python
# In maze.py — FIGURE_ROOMS is the set of eligible positions
FIGURE_ROOMS = [(1,1), (2,2), (3,3)]  # rooms next to locked gates
FIGURES = [
    ("Leonardo da Vinci", "Art Gallery"),
    ("Abraham Lincoln", "American History"),
    ("Cleopatra", "Ancient History"),
]

# In Maze.__init__:
import random
positions = FIGURE_ROOMS.copy()
figures = FIGURES.copy()
random.shuffle(positions)
random.shuffle(figures)
for pos, (name, zone) in zip(positions, figures):
    self.rooms[pos].figure_name = name
    self.rooms[pos].zone = zone
```

### What Does NOT Change
- Maze structure (staircase layout, doors, connections)
- Locked gates still block the same corridors
- `is_solvable()` still returns True
- All existing tests pass (they don't rely on specific figure positions)

---

## Option B — Randomize Door/Corridor Layout

**Owner:** Megan (maze branch)
**Effort:** ~2-3 hours | **Impact:** High

### What It Would Do
- Generate a random 5×5 maze layout using procedural algorithms (e.g., Kruskal's, DFS backtracker)
- Guarantee solvability via `is_solvable()` check
- Place locked gates at random chokepoints
- Entrance at (0,0), exit at (4,4) remain fixed

### Implementation Sketch
1. Start with a fully walled 5×5 grid
2. Use randomized DFS to carve corridors, creating a spanning tree
3. Add 1-2 extra edges for alternate paths (prevent linear mazes)
4. Place 3 locked gates at bottleneck positions (using BFS path analysis)
5. Validate with `is_solvable()` — regenerate if invalid

### Dependencies
- Requires updating `_build_maze()` in `maze.py`
- Tests for maze connectivity need updating
- First-person canvas and maze_canvas are layout-agnostic — no GUI changes needed

---

## Option C — Expand the Figure Pool

**Owner:** Boma (DB branch) + Megan (maze branch)
**Effort:** ~1 hour | **Impact:** High

### What It Would Do
- Add more historical figures to the database (5-8 total instead of 3)
- Each new game randomly picks 3 from the expanded pool
- Each figure gets their own themed zone and question set

### Proposed New Figures

| Figure | Zone | Visual (first-person) |
|--------|------|-----------------------|
| Einstein | Science Lab | Wild hair, mustache, chalkboard |
| Napoleon | War Room | Bicorne hat, hand in jacket |
| Shakespeare | Theater | Ruff collar, quill pen |
| Marie Curie | Chemistry Lab | Lab coat, glowing vial |
| Genghis Khan | Armory | Fur hat, bow |

### Dependencies
- Boma: Add question sets to `db.py` for each new figure
- Megan: Update `FIGURES` list in `maze.py`
- Mario: Add `_draw_<figure>()` methods to `first_person_canvas.py`

---

## Option D — Difficulty Modes

**Owner:** Mario (GUI) + Sowmya (Engine)
**Effort:** ~1 hour | **Impact:** Medium

### What It Would Do
- Add a difficulty selector at game start (Easy / Normal / Hard)
- Adjust game parameters per difficulty:

| Parameter | Easy | Normal | Hard |
|-----------|------|--------|------|
| Curse per wrong answer | +10% | +20% | +33% |
| Number of figures | 2 | 3 | 4+ |
| Questions per figure | 1 | 1 | 2 |
| Fog of war range | 2 cells | 1 cell | 0 (current only) |

### Implementation
- Add `difficulty` parameter to `Maze.__init__()`
- Engine passes difficulty from GUI selection dialog
- Qt GUI shows a styled difficulty picker before the game starts

---

## Priority Order

1. ✅ **Option A** — Randomize figure positions (done)
2. 🔜 **Option C** — More figures (next sprint, Boma + Megan)
3. 🔜 **Option D** — Difficulty modes (polish sprint)
4. 📋 **Option B** — Random maze layout (if time permits — complex)
