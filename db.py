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


class ConfigRecord(SQLModel, table=True):
    """Simple key-value store for internal metadata (e.g. seed version)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True)
    value: str


SEED_DATA_VERSION = "v2-pop-culture-5fig"

SEED_QUESTIONS: List[Dict[str, str]] = [
    # ── Leonardo DiCaprio (Hollywood Wing) ──
    {"figure_name": "Leonardo DiCaprio", "zone": "Hollywood Wing",
     "question_text": "Which 1997 blockbuster features me shouting 'I'm the king of the world!' on the bow of a ship?",
     "choice_a": "Pearl Harbor", "choice_b": "Titanic", "choice_c": "The Great Gatsby", "correct_key": "B"},
    {"figure_name": "Leonardo DiCaprio", "zone": "Hollywood Wing",
     "question_text": "In 'Inception,' what small object does my character use to distinguish dreams from reality?",
     "choice_a": "A spinning top", "choice_b": "A pocket watch", "choice_c": "A coin", "correct_key": "A"},
    {"figure_name": "Leonardo DiCaprio", "zone": "Hollywood Wing",
     "question_text": "Which film earned me my first Academy Award for Best Actor?",
     "choice_a": "The Wolf of Wall Street", "choice_b": "Blood Diamond", "choice_c": "The Revenant", "correct_key": "C"},
    {"figure_name": "Leonardo DiCaprio", "zone": "Hollywood Wing",
     "question_text": "In 'The Wolf of Wall Street,' which real-life stockbroker did I portray?",
     "choice_a": "Bernie Madoff", "choice_b": "Jordan Belfort", "choice_c": "Ivan Boesky", "correct_key": "B"},
    {"figure_name": "Leonardo DiCaprio", "zone": "Hollywood Wing",
     "question_text": "Which Christopher Nolan film features me infiltrating dreams within dreams?",
     "choice_a": "Interstellar", "choice_b": "The Dark Knight", "choice_c": "Inception", "correct_key": "C"},
    {"figure_name": "Leonardo DiCaprio", "zone": "Hollywood Wing",
     "question_text": "In 'Django Unchained,' what is the name of my plantation-owning character?",
     "choice_a": "Calvin Candie", "choice_b": "Stephen", "choice_c": "Big Daddy", "correct_key": "A"},
    {"figure_name": "Leonardo DiCaprio", "zone": "Hollywood Wing",
     "question_text": "In which Martin Scorsese film do I play an undercover cop in Boston's criminal underworld?",
     "choice_a": "Goodfellas", "choice_b": "The Departed", "choice_c": "Casino", "correct_key": "B"},

    # ── Michael Jackson (Music Hall) ──
    {"figure_name": "Michael Jackson", "zone": "Music Hall",
     "question_text": "Which album, released in 1982, is the best-selling album of all time?",
     "choice_a": "Bad", "choice_b": "Thriller", "choice_c": "Off the Wall", "correct_key": "B"},
    {"figure_name": "Michael Jackson", "zone": "Music Hall",
     "question_text": "What signature dance move did I first perform on the 'Motown 25' TV special during 'Billie Jean'?",
     "choice_a": "The Robot", "choice_b": "The Moonwalk", "choice_c": "The Spin", "correct_key": "B"},
    {"figure_name": "Michael Jackson", "zone": "Music Hall",
     "question_text": "What was the name of my famous ranch and amusement park in Santa Barbara County?",
     "choice_a": "Graceland", "choice_b": "Neverland Ranch", "choice_c": "Paisley Park", "correct_key": "B"},
    {"figure_name": "Michael Jackson", "zone": "Music Hall",
     "question_text": "Which of my music videos features a 14-minute storyline with zombies and werewolves?",
     "choice_a": "Beat It", "choice_b": "Thriller", "choice_c": "Bad", "correct_key": "B"},
    {"figure_name": "Michael Jackson", "zone": "Music Hall",
     "question_text": "I started my career as the youngest member of which family group?",
     "choice_a": "The Jackson 5", "choice_b": "The Commodores", "choice_c": "The Temptations", "correct_key": "A"},
    {"figure_name": "Michael Jackson", "zone": "Music Hall",
     "question_text": "Which single features the lyric 'Annie, are you OK? Are you OK, Annie?'",
     "choice_a": "Bad", "choice_b": "Beat It", "choice_c": "Smooth Criminal", "correct_key": "C"},
    {"figure_name": "Michael Jackson", "zone": "Music Hall",
     "question_text": "What was my widely-known nickname given by the media?",
     "choice_a": "The King of Pop", "choice_b": "The Prince of Pop", "choice_c": "The Emperor of Music", "correct_key": "A"},

    # ── Abraham Lincoln (History Gallery) ──
    {"figure_name": "Abraham Lincoln", "zone": "History Gallery",
     "question_text": "Which proclamation did I issue in 1863 to free slaves in Confederate states?",
     "choice_a": "The Bill of Rights", "choice_b": "The Emancipation Proclamation", "choice_c": "The Monroe Doctrine", "correct_key": "B"},
    {"figure_name": "Abraham Lincoln", "zone": "History Gallery",
     "question_text": "In what year did the American Civil War begin during my presidency?",
     "choice_a": "1848", "choice_b": "1861", "choice_c": "1876", "correct_key": "B"},
    {"figure_name": "Abraham Lincoln", "zone": "History Gallery",
     "question_text": "What famous speech did I deliver at a Pennsylvania battlefield in November 1863?",
     "choice_a": "The Gettysburg Address", "choice_b": "The Farewell Address", "choice_c": "The First Inaugural", "correct_key": "A"},
    {"figure_name": "Abraham Lincoln", "zone": "History Gallery",
     "question_text": "At which venue was I assassinated on April 14, 1865?",
     "choice_a": "The White House", "choice_b": "Ford's Theatre", "choice_c": "The Capitol Building", "correct_key": "B"},
    {"figure_name": "Abraham Lincoln", "zone": "History Gallery",
     "question_text": "Which political party did I represent as the 16th President?",
     "choice_a": "Democratic", "choice_b": "Republican", "choice_c": "Whig", "correct_key": "B"},
    {"figure_name": "Abraham Lincoln", "zone": "History Gallery",
     "question_text": "What nickname was I commonly known by during my lifetime?",
     "choice_a": "Honest Abe", "choice_b": "Old Hickory", "choice_c": "The General", "correct_key": "A"},
    {"figure_name": "Abraham Lincoln", "zone": "History Gallery",
     "question_text": "Before becoming president, what was my primary profession?",
     "choice_a": "A farmer", "choice_b": "A lawyer", "choice_c": "A military general", "correct_key": "B"},

    # ── Walt Disney (Animation Vault) ──
    {"figure_name": "Walt Disney", "zone": "Animation Vault",
     "question_text": "What was Disney Studios' first full-length animated feature film, released in 1937?",
     "choice_a": "Pinocchio", "choice_b": "Snow White and the Seven Dwarfs", "choice_c": "Fantasia", "correct_key": "B"},
    {"figure_name": "Walt Disney", "zone": "Animation Vault",
     "question_text": "Which character did I originally voice myself, beginning in 1928?",
     "choice_a": "Donald Duck", "choice_b": "Goofy", "choice_c": "Mickey Mouse", "correct_key": "C"},
    {"figure_name": "Walt Disney", "zone": "Animation Vault",
     "question_text": "In 'The Lion King,' what is the name of Simba's father?",
     "choice_a": "Mufasa", "choice_b": "Scar", "choice_c": "Rafiki", "correct_key": "A"},
    {"figure_name": "Walt Disney", "zone": "Animation Vault",
     "question_text": "Which Disney theme park opened first, in Anaheim, California, in 1955?",
     "choice_a": "Walt Disney World", "choice_b": "Disneyland", "choice_c": "EPCOT", "correct_key": "B"},
    {"figure_name": "Walt Disney", "zone": "Animation Vault",
     "question_text": "In 'Frozen,' what is the name of the magical snowman who loves warm hugs?",
     "choice_a": "Marshmallow", "choice_b": "Olaf", "choice_c": "Sven", "correct_key": "B"},
    {"figure_name": "Walt Disney", "zone": "Animation Vault",
     "question_text": "Which Pixar film features a rat who dreams of becoming a Parisian chef?",
     "choice_a": "Finding Nemo", "choice_b": "Up", "choice_c": "Ratatouille", "correct_key": "C"},
    {"figure_name": "Walt Disney", "zone": "Animation Vault",
     "question_text": "What famous inspirational quote is attributed to me about pursuing dreams?",
     "choice_a": "If you can dream it, you can do it", "choice_b": "To infinity and beyond", "choice_c": "Hakuna Matata", "correct_key": "A"},

    # ── Taylor Swift (Pop Culture Lounge) ──
    {"figure_name": "Taylor Swift", "zone": "Pop Culture Lounge",
     "question_text": "Which album marked my transition from country music to pop, released in 2014?",
     "choice_a": "Red", "choice_b": "1989", "choice_c": "Reputation", "correct_key": "B"},
    {"figure_name": "Taylor Swift", "zone": "Pop Culture Lounge",
     "question_text": "What was the name of my record-breaking 2023-2024 concert tour?",
     "choice_a": "The Eras Tour", "choice_b": "The Reputation Tour", "choice_c": "The 1989 World Tour", "correct_key": "A"},
    {"figure_name": "Taylor Swift", "zone": "Pop Culture Lounge",
     "question_text": "Which song starts with the lyrics 'We are never ever ever getting back together'?",
     "choice_a": "Love Story", "choice_b": "We Are Never Getting Back Together", "choice_c": "Shake It Off", "correct_key": "B"},
    {"figure_name": "Taylor Swift", "zone": "Pop Culture Lounge",
     "question_text": "What was my debut single, released in 2006?",
     "choice_a": "Love Story", "choice_b": "Tim McGraw", "choice_c": "Our Song", "correct_key": "B"},
    {"figure_name": "Taylor Swift", "zone": "Pop Culture Lounge",
     "question_text": "Which album features the hit singles 'Anti-Hero' and 'Lavender Haze'?",
     "choice_a": "Folklore", "choice_b": "Evermore", "choice_c": "Midnights", "correct_key": "C"},
    {"figure_name": "Taylor Swift", "zone": "Pop Culture Lounge",
     "question_text": "My 'Taylor's Version' re-recording project began with which album?",
     "choice_a": "Fearless (Taylor's Version)", "choice_b": "Red (Taylor's Version)", "choice_c": "1989 (Taylor's Version)", "correct_key": "A"},
    {"figure_name": "Taylor Swift", "zone": "Pop Culture Lounge",
     "question_text": "Which music video features me in a satirical take on fame, ending in a bathtub of diamonds?",
     "choice_a": "Bad Blood", "choice_b": "Blank Space", "choice_c": "Look What You Made Me Do", "correct_key": "C"},
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

        Auto-seeds questions if the QuestionRecord table is empty, and
        re-seeds when the built-in question data version changes.
        """
        self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
        SQLModel.metadata.create_all(self._engine)
        self._ensure_seed_data()

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

    def _ensure_seed_data(self) -> None:
        """Reseed the question bank when SEED_DATA_VERSION changes."""
        with Session(self._engine) as session:
            cfg = session.exec(
                select(ConfigRecord).where(ConfigRecord.key == "seed_version")
            ).first()
            current = cfg.value if cfg else None

        if current == SEED_DATA_VERSION:
            return

        with Session(self._engine) as session:
            for rec in session.exec(select(QuestionRecord)).all():
                session.delete(rec)
            for rec in session.exec(select(LastAskedRecord)).all():
                session.delete(rec)
            session.commit()

        self.seed_questions(SEED_QUESTIONS)

        with Session(self._engine) as session:
            cfg = session.exec(
                select(ConfigRecord).where(ConfigRecord.key == "seed_version")
            ).first()
            if cfg:
                cfg.value = SEED_DATA_VERSION
            else:
                cfg = ConfigRecord(key="seed_version", value=SEED_DATA_VERSION)
            session.add(cfg)
            session.commit()

    def delete_save(self, slot_name: str = "default") -> None:
        """Delete a saved game slot."""
        with Session(self._engine) as session:
            record = session.exec(
                select(SaveRecord).where(SaveRecord.slot_name == slot_name)
            ).first()
            if record:
                session.delete(record)
                session.commit()