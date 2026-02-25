# Waxworks: The Midnight Curse — RUNBOOK

> Walking Skeleton · Build & Integration Guide

---

## 1. Dependency Rules (The Law)

These rules are **non-negotiable**. If a module violates its rule, the PR is rejected.

| Module | May Import | May NOT Import | May Use `print()` / `input()` |
|--------|-----------|----------------|-------------------------------|
| `maze.py` | `enum`, `dataclasses`, `typing` (stdlib only) | `db`, `main`, `json`, `os` | **No** |
| `db.py` | `json`, `os`, `typing` (stdlib only) | `maze`, `main` | **No** |
| `main.py` | `maze`, `db`, anything in stdlib | — | **Yes** (only module allowed) |

### Quick check (run before every PR):

```bash
# Must return nothing — if it prints a filename, that module is cheating
grep -l "import db\|from db" maze.py
grep -l "import maze\|from maze" db.py
grep -l "print(" maze.py db.py
grep -l "input(" maze.py db.py
```

---

## 2. Repository Structure

```
waxworks/
├── maze.py                  # Domain logic (pure Python)
├── db.py                    # Persistence (JSON I/O)
├── main.py                  # Engine (wiring + CLI)
├── docs/
│   ├── interfaces.md        # Protocol & dataclass specs
│   ├── interface-tests.md   # Contract test definitions
│   └── RUNBOOK.md           # This file
├── tests/
│   ├── conftest.py          # Shared test helpers
│   ├── test_maze_contract.py
│   ├── test_repo_contract.py
│   └── test_engine_integration.py
├── save_game.json           # (generated at runtime, gitignored)
└── README.md
```

---

## 3. Branch Strategy

```
main
 ├── design/mario        ← Part 1: your personal design docs
 ├── design/megan        ← Part 1: teammate design docs
 ├── design/sowmya       ← ...
 ├── design/boma         ← ...
 ├── feat/maze           ← Role 1: Domain Owner
 ├── feat/db             ← Role 2: Persistence Owner
 ├── feat/engine         ← Role 3: Engine Owner
 └── feat/tests          ← Role 4: Test & Quality Lead (Track B)
```

### Workflow

1. **Part 1:** Push `docs/` to your `design/` branch. Open PR for team review.
2. **Part 2:** Team agrees on one design. Each member creates `feat/` branch from `main`.
3. **Part 3:** PRs merged to `main` in order: `feat/maze` → `feat/db` → `feat/tests` → `feat/engine` (engine depends on both).

---

## 4. P0 Tests — Definition of "Done"

The skeleton is **not done** until every P0 test passes on `main`.

### P0: Critical (Must Pass)

| # | Test | Module | What It Proves |
|---|------|--------|----------------|
| P0-1 | `test_maze_creates_3x3_grid` | maze | Grid exists |
| P0-2 | `test_entrance_is_at_0_0` | maze | Entrance room marked |
| P0-3 | `test_exit_exists` | maze | Exit room exists |
| P0-4 | `test_trivia_rooms_exist` | maze | At least two trivia rooms |
| P0-5 | `test_player_starts_at_entrance` | maze | Initial state is correct |
| P0-6 | `test_move_through_open_door` | maze | Basic movement works |
| P0-7 | `test_available_directions_excludes_walls` | maze | Available dirs are attemptable (OPEN + LOCKED) |
| P0-8 | `test_move_into_wall_rejected` | maze | Boundary enforcement |
| P0-9 | `test_move_into_locked_door_rejected` | maze | Locked door blocks move |
| P0-10 | `test_move_into_border_wall_rejected` | maze | Border walls enforced |
| P0-11 | `test_correct_answer_unlocks_door` | maze | Trivia unlocks gates |
| P0-12 | `test_correct_answer_does_not_increase_wax` | maze | Correct answer leaves wax unchanged |
| P0-13 | `test_wrong_answer_increases_wax` | maze | Failure penalty works |
| P0-14 | `test_wrong_answer_keeps_door_locked` | maze | Wrong answer does not unlock |
| P0-15 | `test_wax_meter_at_100_means_game_over` | maze | Lose condition works |
| P0-16 | `test_get_game_state_returns_dataclass` | maze | State snapshot shape |
| P0-17 | `test_restore_game_state_roundtrip` | maze | State roundtrip in domain |
| P0-18 | `test_restore_preserves_unlocked_doors` | maze | Unlocked doors survive save/load |
| P0-19 | `test_save_creates_file` | db | Persistence writes to disk |
| P0-20 | `test_load_returns_saved_data` | db | Persistence reads back correctly |
| P0-21 | `test_save_is_valid_json` | db | Output is valid JSON |
| P0-22 | `test_load_missing_file_returns_none` | db | Graceful handling of no save |
| P0-23 | `test_load_corrupt_file_raises_value_error` | db | Corrupt data doesn't crash |
| P0-24 | `test_load_empty_file_raises_value_error` | db | Empty file rejected |
| P0-25 | `test_game_state_to_dict_serializes_position` | engine | Boundary crossing works |
| P0-26 | `test_game_state_to_dict_serializes_enums` | engine | Enums become strings |
| P0-27 | `test_dict_to_game_state_roundtrip` | engine | Deserialization works |
| P0-28 | `test_save_and_load_game_roundtrip` | engine | Full save/load pipeline |
| P0-29 | `test_full_winning_game` | maze | Full winning path validates game rules |
| P0-30 | `test_full_losing_game` | maze | Full losing path validates game rules |
| P0-31 | `test_attempt_answer_after_game_over` | maze | No state change after game ends |

### P1: Important (Should Pass)

| # | Test | What It Proves |
|---|------|----------------|
| P1-1 | `test_no_trivia_in_empty_room` | Edge case handling |
| P1-2 | `test_already_answered_trivia` | Re-answer protection |
| P1-3 | `test_wax_meter_never_exceeds_100` | Cap enforcement |
| P1-4 | `test_save_overwrites_existing_file` | Idempotent saves |
| P1-5 | `test_save_handles_empty_dict` | Empty dict roundtrip |
| P1-6 | `test_dict_to_game_state_rejects_bad_data` | Bad data doesn't crash |
| P1-7 | `test_load_game_with_no_save_returns_false` | Graceful no-save UX |

### Conftest

`tests/conftest.py` (or shared helper section in test files) must provide: `_navigate_to_trivia_room(m)` and `_get_wrong_key(correct_key)`. See `docs/interface-tests.md` Section 5.

---

## 5. How to Run

### Prerequisites

```bash
python --version   # 3.10+
pip install pytest
```

### Run Everything

```bash
# All tests, verbose output
pytest tests/ -v

# Stop on first failure
pytest tests/ -v -x
```

### Run by Role

```bash
# Domain Owner — can run without db.py or main.py existing
pytest tests/test_maze_contract.py -v

# Persistence Owner — can run without maze.py or main.py existing
pytest tests/test_repo_contract.py -v

# Engine Owner / Test Lead — requires all modules
pytest tests/test_engine_integration.py -v
```

### Run the Game

```bash
python main.py
```

Expected CLI interaction:

```
=== WAXWORKS: THE MIDNIGHT CURSE ===
You are in room (0, 0) — The Entrance.
Wax Meter: [░░░░░░░░░░] 0%
Doors: SOUTH (open), EAST (open)

> move south

You are in room (1, 0) — A dark corridor.
...
```

---

## 6. PR Checklist

Before opening a PR, verify:

- [ ] **Dependency rules:** `grep` check passes (Section 1)
- [ ] **Contract tests pass:** `pytest tests/test_<your_module>.py -v` — all green
- [ ] **No `print()` in maze.py or db.py**
- [ ] **No imports of other game modules** (except in main.py)
- [ ] **Code reviewed by AI:** Paste your module into your AI tool, ask for review, apply reasonable suggestions
- [ ] **Docstrings on all public methods**

---

## 7. Integration Day Checklist

When all `feat/` branches are ready to merge:

1. [ ] Merge `feat/maze` to `main`
2. [ ] Merge `feat/db` to `main`
3. [ ] Merge `feat/tests` to `main` (if Track B)
4. [ ] Merge `feat/engine` to `main`
5. [ ] Run full test suite: `pytest tests/ -v`
6. [ ] Run the game: `python main.py` — play through a win and a loss
7. [ ] AI review of assembled code on `main`
8. [ ] Apply fixes from AI review
9. [ ] Final `pytest tests/ -v` — all green
10. [ ] Tag release: `git tag v0.1-skeleton`

---

## 8. Known Constraints (Skeleton Scope)

These are **intentionally deferred** to keep the skeleton minimal:

| Feature | Skeleton | Next Stage |
|---------|----------|------------|
| Maze size | Fixed 3×3 | Configurable / random generation |
| Persistence | JSON file | SQLite database |
| UI | CLI `print()`/`input()` | PyQt6 GUI |
| Trivia source | Hardcoded in maze.py | External JSON or DB |
| Difficulty | Fixed (+25 wax per wrong) | Configurable difficulty levels |
| BFS solvability check | Not needed (fixed layout) | Required for random mazes |

---

*Document version: 1.0 — Walking Skeleton · Waxworks: The Midnight Curse*
