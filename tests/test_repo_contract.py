"""
test_repo_contract.py — Persistence Contract Tests

Tests the Repository module against the RepositoryProtocol in docs/interfaces.md.
Updated for SQLModel/SQLite-backed Repository with Question Bank.

Covers:
- Save / Load (slot-based SQLite API)
- Question Bank (get_random_question, reset_questions, seed_questions)
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import Repository

TEST_DB = "test_repo.db"


# ===========================================================================
# Setup / Teardown — clean up test DB before and after each test
# ===========================================================================

def setup_function():
    """Clean up test DB before each test."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def teardown_function():
    """Clean up test DB after each test."""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


# ===========================================================================
# P0-19 to P0-21: Save & Load — Happy Path
# ===========================================================================

def test_save_and_load_returns_data():
    """P0-19/20: save() stores data, load() returns exactly what was saved."""
    repo = Repository(db_path=TEST_DB)
    data = {
        "player_position": {"row": 1, "col": 2},
        "wax_meter": 50,
        "game_status": "playing",
        "answered_figures": ["Leonardo da Vinci"],
        "visited_positions": [
            {"row": 0, "col": 0},
            {"row": 1, "col": 2},
        ],
    }
    repo.save(data, "test_slot")
    loaded = repo.load("test_slot")
    assert loaded == data


def test_save_creates_db_file():
    """P0-21: save() creates the SQLite database file."""
    repo = Repository(db_path=TEST_DB)
    repo.save({"wax_meter": 25}, "default")
    assert os.path.exists(TEST_DB)


# ===========================================================================
# P0-22 to P0-24: Load — Edge Cases
# ===========================================================================

def test_load_missing_slot_returns_none():
    """P0-22: load() returns None if the slot does not exist."""
    repo = Repository(db_path=TEST_DB)
    result = repo.load("nonexistent_slot")
    assert result is None


def test_save_overwrites_existing_slot():
    """P1-4: Saving twice to the same slot overwrites the first save."""
    repo = Repository(db_path=TEST_DB)
    repo.save({"wax_meter": 10}, "slot1")
    repo.save({"wax_meter": 99}, "slot1")
    loaded = repo.load("slot1")
    assert loaded["wax_meter"] == 99


def test_save_handles_empty_dict():
    """P1-5: An empty dict can be saved and loaded."""
    repo = Repository(db_path=TEST_DB)
    repo.save({}, "empty_slot")
    loaded = repo.load("empty_slot")
    assert loaded == {}


# ===========================================================================
# Question Bank — get_random_question
# ===========================================================================

def test_get_random_question_returns_dict():
    """get_random_question() returns a dict with expected keys."""
    repo = Repository(db_path=TEST_DB)
    q = repo.get_random_question("Leonardo da Vinci")
    assert q is not None
    assert "figure_name" in q
    assert "question_text" in q
    assert "choices" in q
    assert "correct_key" in q
    assert q["figure_name"] == "Leonardo da Vinci"
    assert isinstance(q["choices"], dict)
    assert "A" in q["choices"] and "B" in q["choices"] and "C" in q["choices"]


def test_get_random_question_marks_as_asked():
    """After fetching, the question is marked as asked and won't repeat immediately."""
    repo = Repository(db_path=TEST_DB)
    seen_texts = set()
    for _ in range(3):
        q = repo.get_random_question("Leonardo da Vinci")
        assert q is not None
        assert q["question_text"] not in seen_texts, "Got a repeat question!"
        seen_texts.add(q["question_text"])


def test_get_random_question_returns_none_when_exhausted():
    """Returns None when all questions for a figure have been asked."""
    repo = Repository(db_path=TEST_DB)
    # Da Vinci has 3 questions in seed data
    for _ in range(3):
        q = repo.get_random_question("Leonardo da Vinci")
        assert q is not None
    # 4th call should return None
    assert repo.get_random_question("Leonardo da Vinci") is None


def test_get_random_question_unknown_figure_returns_none():
    """Returns None for a figure not in the question bank."""
    repo = Repository(db_path=TEST_DB)
    assert repo.get_random_question("Unknown Figure") is None


def test_get_random_question_different_figures():
    """Each figure gets questions from their own pool."""
    repo = Repository(db_path=TEST_DB)
    dv_q = repo.get_random_question("Leonardo da Vinci")
    al_q = repo.get_random_question("Abraham Lincoln")
    cl_q = repo.get_random_question("Cleopatra")
    assert dv_q["figure_name"] == "Leonardo da Vinci"
    assert al_q["figure_name"] == "Abraham Lincoln"
    assert cl_q["figure_name"] == "Cleopatra"


# ===========================================================================
# Question Bank — reset_questions
# ===========================================================================

def test_reset_questions_makes_all_unasked():
    """reset_questions() allows all questions to be asked again."""
    repo = Repository(db_path=TEST_DB)
    # Exhaust Da Vinci questions
    for _ in range(3):
        repo.get_random_question("Leonardo da Vinci")
    assert repo.get_random_question("Leonardo da Vinci") is None
    # Reset
    repo.reset_questions()
    q = repo.get_random_question("Leonardo da Vinci")
    assert q is not None


# ===========================================================================
# Question Bank — seed_questions
# ===========================================================================

def test_seed_questions_is_idempotent():
    """Calling seed_questions twice does not duplicate data."""
    repo = Repository(db_path=TEST_DB)
    custom = [
        {
            "figure_name": "Test Figure",
            "zone": "Test Zone",
            "question_text": "Custom Q?",
            "choice_a": "A1",
            "choice_b": "B1",
            "choice_c": "C1",
            "correct_key": "A",
        },
    ]
    # Auto-seeded with 9 questions on init — calling seed again does nothing
    repo.seed_questions(custom)
    # Should still return Da Vinci questions (original seed), not custom
    q = repo.get_random_question("Leonardo da Vinci")
    assert q is not None


def test_auto_seed_populates_questions():
    """Repository auto-seeds questions on construction if DB is empty."""
    repo = Repository(db_path=TEST_DB)
    # Should have questions for all three figures
    assert repo.get_random_question("Leonardo da Vinci") is not None
    assert repo.get_random_question("Abraham Lincoln") is not None
    assert repo.get_random_question("Cleopatra") is not None


# ===========================================================================
# Question Bank — anti-repeat
# ===========================================================================

def test_anti_repeat_avoids_same_question_consecutively():
    """get_random_question avoids the immediately previous question.

    Simulates multiple game restarts (reset between each) and verifies
    no back-to-back repeats. With 3 questions, this should always hold.
    """
    repo = Repository(db_path=TEST_DB)
    prev_text = None
    for _ in range(10):
        repo.reset_questions()
        q = repo.get_random_question("Leonardo da Vinci")
        assert q is not None
        if prev_text is not None:
            assert q["question_text"] != prev_text, (
                f"Got same question back-to-back: {q['question_text']}"
            )
        prev_text = q["question_text"]
