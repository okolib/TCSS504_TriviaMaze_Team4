# db.py
# Persistence Owner: SQLModel + SQLite.
# Constraints:
# - Do NOT import maze or main
# - Store JSON-safe primitives only (dict/list/str/int/float/bool/None)

import json
from typing import Optional, Dict, Any, List

from sqlmodel import SQLModel, Field, Session, create_engine, select


# ======================================================================
# SQLModel Tables
# ======================================================================

class FigureRecord(SQLModel, table=True):
    """A wax figure in the museum (per RFC §2.1)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str                  # e.g. "Leonardo da Vinci"
    zone: str                  # e.g. "Art Gallery"
    is_defeated: bool = False  # True after player answers correctly


class QuestionRecord(SQLModel, table=True):
    """A single trivia question in the Question Bank."""
    id: Optional[int] = Field(default=None, primary_key=True)
    figure_name: str
    zone: str
    question_text: str
    choice_a: str
    choice_b: str
    choice_c: str
    correct_key: str          # "A", "B", or "C"
    has_been_asked: bool = False


class SaveRecord(SQLModel, table=True):
    """A saved game state slot."""
    id: Optional[int] = Field(default=None, primary_key=True)
    slot_name: str = "default"
    state_json: str            # JSON-serialized game state dict


class LastAskedRecord(SQLModel, table=True):
    """Tracks the last question asked per figure to avoid immediate repeats."""
    id: Optional[int] = Field(default=None, primary_key=True)
    figure_name: str = Field(unique=True)
    last_question_id: int


# ======================================================================
# Seed Data — Museum-themed questions (3+ per figure)
# ======================================================================

SEED_QUESTIONS: List[Dict[str, str]] = [
    # --- Leonardo da Vinci (Art Gallery) ---
    {
        "figure_name": "Leonardo da Vinci",
        "zone": "Art Gallery",
        "question_text": "Who painted the Mona Lisa?",
        "choice_a": "Michelangelo",
        "choice_b": "Leonardo da Vinci",
        "choice_c": "Raphael",
        "correct_key": "B",
    },
    {
        "figure_name": "Leonardo da Vinci",
        "zone": "Art Gallery",
        "question_text": "What famous fresco did Leonardo paint on the wall of Santa Maria delle Grazie?",
        "choice_a": "The Last Supper",
        "choice_b": "The Creation of Adam",
        "choice_c": "The School of Athens",
        "correct_key": "A",
    },
    {
        "figure_name": "Leonardo da Vinci",
        "zone": "Art Gallery",
        "question_text": "Leonardo da Vinci kept his private notes written in what unusual way?",
        "choice_a": "In invisible ink",
        "choice_b": "In mirror script (backwards)",
        "choice_c": "In Ancient Greek",
        "correct_key": "B",
    },

    # --- Abraham Lincoln (American History) ---
    {
        "figure_name": "Abraham Lincoln",
        "zone": "American History",
        "question_text": "Which president issued the Emancipation Proclamation?",
        "choice_a": "George Washington",
        "choice_b": "Abraham Lincoln",
        "choice_c": "Thomas Jefferson",
        "correct_key": "B",
    },
    {
        "figure_name": "Abraham Lincoln",
        "zone": "American History",
        "question_text": "In what year did the American Civil War begin?",
        "choice_a": "1848",
        "choice_b": "1861",
        "choice_c": "1876",
        "correct_key": "B",
    },
    {
        "figure_name": "Abraham Lincoln",
        "zone": "American History",
        "question_text": "What famous speech did Lincoln deliver at a battlefield in Pennsylvania?",
        "choice_a": "The Gettysburg Address",
        "choice_b": "The Farewell Address",
        "choice_c": "The Declaration of Independence",
        "correct_key": "A",
    },

    # --- Cleopatra (Ancient History) ---
    {
        "figure_name": "Cleopatra",
        "zone": "Ancient History",
        "question_text": "Who was the last pharaoh of Ancient Egypt?",
        "choice_a": "Nefertiti",
        "choice_b": "Cleopatra",
        "choice_c": "Hatshepsut",
        "correct_key": "B",
    },
    {
        "figure_name": "Cleopatra",
        "zone": "Ancient History",
        "question_text": "Which Roman general was Cleopatra's famous ally and lover?",
        "choice_a": "Augustus",
        "choice_b": "Julius Caesar",
        "choice_c": "Nero",
        "correct_key": "B",
    },
    {
        "figure_name": "Cleopatra",
        "zone": "Ancient History",
        "question_text": "What river was essential to the Egyptian civilization Cleopatra ruled?",
        "choice_a": "The Tigris",
        "choice_b": "The Euphrates",
        "choice_c": "The Nile",
        "correct_key": "C",
    },
]


# ======================================================================
# Repository (SQLModel-backed)
# ======================================================================

class Repository:
    """
    SQLModel-backed persistence for Waxworks.

    Contract (per docs/interfaces.md §3.2):
    - save(data, slot_name) → persist JSON-safe dict to SQLite
    - load(slot_name) → return dict or None
    - get_random_question(figure_name) → return random unasked question dict
    - reset_questions() → mark all questions as unasked
    - seed_questions(questions) → populate Question Bank (idempotent)
    """

    def __init__(self, db_path: str = "waxworks.db"):
        """Initialize the SQLite engine and create tables.

        Auto-seeds questions if the QuestionRecord table is empty.
        """
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        SQLModel.metadata.create_all(self._engine)
        # Auto-seed if empty
        with Session(self._engine) as session:
            count = session.exec(select(QuestionRecord)).first()
            if count is None:
                self.seed_questions(SEED_QUESTIONS)

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self, data: Dict[str, Any], slot_name: str = "default") -> None:
        """Persist a JSON-safe dict to the database.

        Upserts: overwrites any existing save in the same slot.
        Raises TypeError if data is not JSON-serializable.
        """
        state_json = json.dumps(data)
        with Session(self._engine) as session:
            # Find existing slot
            statement = select(SaveRecord).where(
                SaveRecord.slot_name == slot_name
            )
            existing = session.exec(statement).first()
            if existing:
                existing.state_json = state_json
                session.add(existing)
            else:
                record = SaveRecord(slot_name=slot_name, state_json=state_json)
                session.add(record)
            session.commit()

    def load(self, slot_name: str = "default") -> Optional[Dict[str, Any]]:
        """Load a previously saved dict. Returns None if not found.

        Raises ValueError if stored JSON is corrupt.
        """
        with Session(self._engine) as session:
            statement = select(SaveRecord).where(
                SaveRecord.slot_name == slot_name
            )
            record = session.exec(statement).first()
            if record is None:
                return None
            try:
                data = json.loads(record.state_json)
            except json.JSONDecodeError as e:
                raise ValueError("Saved state is corrupt.") from e
            if not isinstance(data, dict):
                raise ValueError("Saved state must be a dict.")
            return data

    # ------------------------------------------------------------------
    # Question Bank
    # ------------------------------------------------------------------

    def get_random_question(self, figure_name: str) -> Optional[Dict[str, Any]]:
        """Return a random unasked question for a specific wax figure.

        Dict keys: figure_name, zone, question_text, choices, correct_key.
        Side effect: marks the question as asked (has_been_asked = True).
        Returns None if all questions for that figure have been asked.
        Avoids returning the same question as the previous call for this figure
        (persisted in DB via LastAskedRecord, survives process restarts).
        """
        with Session(self._engine) as session:
            from sqlalchemy.sql.expression import func

            # Look up last-asked ID from DB
            last_rec = session.exec(
                select(LastAskedRecord)
                .where(LastAskedRecord.figure_name == figure_name)
            ).first()
            last_id = last_rec.last_question_id if last_rec else None

            # Try to exclude the last-asked question for variety
            statement = (
                select(QuestionRecord)
                .where(QuestionRecord.figure_name == figure_name)
                .where(QuestionRecord.has_been_asked == False)  # noqa: E712
            )
            if last_id is not None:
                statement = statement.where(QuestionRecord.id != last_id)
            statement = statement.order_by(func.random()).limit(1)
            record = session.exec(statement).first()

            # If excluding last_id left no results, try without the exclusion
            if record is None and last_id is not None:
                statement = (
                    select(QuestionRecord)
                    .where(QuestionRecord.figure_name == figure_name)
                    .where(QuestionRecord.has_been_asked == False)  # noqa: E712
                    .order_by(func.random())
                    .limit(1)
                )
                record = session.exec(statement).first()

            if record is None:
                return None

            # Mark as asked
            record.has_been_asked = True
            session.add(record)

            # Persist last-asked ID
            if last_rec:
                last_rec.last_question_id = record.id
                session.add(last_rec)
            else:
                session.add(LastAskedRecord(
                    figure_name=figure_name,
                    last_question_id=record.id,
                ))
            session.commit()

            return {
                "figure_name": record.figure_name,
                "zone": record.zone,
                "question_text": record.question_text,
                "choices": {
                    "A": record.choice_a,
                    "B": record.choice_b,
                    "C": record.choice_c,
                },
                "correct_key": record.correct_key,
            }

    def reset_questions(self) -> None:
        """Reset all questions to unasked (for new game)."""
        with Session(self._engine) as session:
            records = session.exec(select(QuestionRecord)).all()
            for record in records:
                record.has_been_asked = False
                session.add(record)
            # Don't clear LastAskedRecord — keep it to avoid repeats across games
            session.commit()

    def seed_questions(self, questions: List[Dict[str, str]]) -> None:
        """Populate the Question Bank from a list of dicts (idempotent).

        Skips insertion if the table already has data.
        """
        with Session(self._engine) as session:
            existing = session.exec(select(QuestionRecord)).first()
            if existing is not None:
                return  # Already seeded

            for q in questions:
                record = QuestionRecord(
                    figure_name=q["figure_name"],
                    zone=q["zone"],
                    question_text=q["question_text"],
                    choice_a=q["choice_a"],
                    choice_b=q["choice_b"],
                    choice_c=q["choice_c"],
                    correct_key=q["correct_key"],
                )
                session.add(record)
            session.commit()