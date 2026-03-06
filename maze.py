from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Set, Union
from sqlmodel import SQLModel, Field, Session, Relationship, select
from pydantic import ConfigDict

# --- Gothic Vocabulary & Enums ---

class Direction(str, Enum):
    """Cardinal directions for exploration."""
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"

class ThresholdState(str, Enum):
    """State of a threshold between exhibits."""
    OPEN = "open"
    LOCKED = "locked"
    WALL = "wall"

class Fate(str, Enum):
    """Thematic GameStatus: top-level game state."""
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"

class RoomVisibility(str, Enum):
    """Fog of War visibility states for the contract."""
    HIDDEN = "hidden"
    VISIBLE = "visible"
    VISITED = "visited"
    CURRENT = "current"

@dataclass(frozen=True)
class Position:
    """A (row, col) coordinate in the museum grid."""
    row: int
    col: int

@dataclass
class FogMapCell:
    """One cell in the fog-of-war map representation."""
    position: Position
    visibility: RoomVisibility
    has_trivia: bool = False
    figure_name: Optional[str] = None
    is_entrance: bool = False
    is_exit: bool = False
    doors: Optional[Dict[Direction, "ThresholdState"]] = None

# --- SQLModel Definitions (The Schema) ---

class Threshold(SQLModel, table=True):
    """Defines a connection between two Exhibits."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    from_exhibit_id: int = Field(foreign_key="exhibit.id")
    to_exhibit_id: Optional[int] = Field(default=None, foreign_key="exhibit.id")
    direction: Direction
    state: ThresholdState

    # Link back to the origin exhibit
    from_exhibit: "Exhibit" = Relationship(
        back_populates="thresholds",
        sa_relationship_kwargs={"foreign_keys": "Threshold.from_exhibit_id"}
    )

class Exhibit(SQLModel, table=True):
    """A discrete location in the Waxworks Museum."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: Optional[int] = Field(default=None, primary_key=True)
    row: int
    col: int
    figure_name: Optional[str] = None
    zone: Optional[str] = None
    is_entrance: bool = False
    is_exit: bool = False
    
    # Fog of War flags
    is_visible: bool = False
    is_discovered: bool = False

    # Outgoing connections
    thresholds: List[Threshold] = Relationship(
        back_populates="from_exhibit",
        sa_relationship_kwargs={"foreign_keys": "Threshold.from_exhibit_id"}
    )

    @property
    def position(self) -> Position:
        return Position(self.row, self.col)
    
    @property
    def doors(self) -> Dict[Direction, ThresholdState]:
        return {t.direction: t.state for t in self.thresholds}

class MuseumLog(SQLModel, table=True):
    """Tracks the state of a specific museum visit (Save State)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    slot_name: str = Field(default="default", unique=True)
    
    player_row: int = 0
    player_col: int = 0
    curse_level: int = 0  # 0-100 (Replaces wax_meter)
    fate: Fate = Fate.PLAYING
    
    # Serialized figure tracking
    defeated_figures_json: str = "[]"

    @property
    def player_position(self) -> Position:
        return Position(self.player_row, self.player_col)
    
    @player_position.setter
    def player_position(self, pos: Position):
        self.player_row = pos.row
        self.player_col = pos.col

    @property
    def wax_meter(self) -> int:
        return self.curse_level
    
    @property
    def game_status(self) -> Fate:
        return self.fate

# --- Domain Logic (The Maze) ---

class Maze:
    """
    Pure Domain implementation of the Waxworks Museum.
    Strictly follows the session-injection pattern and Gothic vocabulary.
    """

    def __init__(self, session=None): # Make it optional with =None
        if session:
            self.session = session
        else:
            # Fallback for tests/UI: Import the engine from your db module
            from db import engine 
            from sqlmodel import Session
            self.session = Session(engine)

    def get_exhibit(self, position: Position) -> Exhibit:
        """Internal helper to get an exhibit by position."""
        return self.get_room(position)

    # --- Thematic Logic ---

    def explore(self, direction: Direction) -> str:
        """Move the player using Gothic vocabulary."""
        if self.log.fate != Fate.PLAYING:
            return "fate_sealed"

        current = self.get_exhibit(Position(self.log.player_row, self.log.player_col))
        threshold = next((t for t in current.thresholds if t.direction == direction), None)

        if not threshold or threshold.state == ThresholdState.WALL:
            return "wall"
        if threshold.state == ThresholdState.LOCKED:
            return "locked"

        # Resolve destination
        target_id = threshold.to_exhibit_id
        if target_id is None:
            return "wall"
        statement = select(Exhibit).where(Exhibit.id == target_id)
        target = self.session.exec(statement).one()

        # Update log position
        self.log.player_row = target.row
        self.log.player_col = target.col
        
        # Fog of War side effects
        target.is_discovered = True
        target.is_visible = True
        self._spread_visibility(target)

        # Win condition check
        if target.is_exit:
            self.log.fate = Fate.WON

        self.session.add(self.log)
        self.session.add(target)
        self.session.commit()
        return "explored"

    def confront_figure(self, answer_key: str, correct_key: str) -> str:
        """Submit trivia answer using Gothic vocabulary."""
        if self.log.fate != Fate.PLAYING:
            return "fate_sealed"

        current = self.get_exhibit(Position(self.log.player_row, self.log.player_col))
        if not current.figure_name:
            return "no_figure"

        import json
        defeated = json.loads(self.log.defeated_figures_json)
        if current.figure_name in defeated:
            return "already_confronted"

        if answer_key.upper() == correct_key.upper():
            # Success
            defeated.append(current.figure_name)
            self.log.defeated_figures_json = json.dumps(defeated)
            
            for t in current.thresholds:
                if t.state == ThresholdState.LOCKED:
                    t.state = ThresholdState.OPEN
                    # Bidirectional unlock
                    if t.to_exhibit_id:
                        stmt = select(Threshold).where(
                            Threshold.from_exhibit_id == t.to_exhibit_id,
                            Threshold.to_exhibit_id == current.id
                        )
                        opp = self.session.exec(stmt).first()
                        if opp:
                            opp.state = ThresholdState.OPEN
                            self.session.add(opp)
                    self.session.add(t)
            
            self.session.add(self.log)
            self.session.commit()
            return "figure_bested"
        else:
            # Failure
            self.log.curse_level += 20
            if self.log.curse_level >= 100:
                self.log.curse_level = 100
                self.log.fate = Fate.LOST
            
            self.session.add(self.log)
            self.session.commit()
            return "curse_deepens"

    def get_fate(self) -> Fate:
        return self.log.fate

    def get_curse_level(self) -> int:
        return self.log.curse_level

    # --- Contract Compatibility Methods ---

    def move(self, direction: Direction) -> str:
        res = self.explore(direction)
        return "moved" if res == "explored" else res

    def get_game_status(self) -> Fate:
        return self.get_fate()

    def get_wax_meter(self) -> int:
        return self.get_curse_level()

    def attempt_answer(self, answer_key: str, correct_key: str) -> str:
        res = self.confront_figure(answer_key, correct_key)
        if res == "figure_bested": return "correct"
        if res == "curse_deepens": return "wrong"
        if res == "no_figure": return "no_trivia"
        if res == "already_confronted": return "already_answered"
        if res == "fate_sealed": return "game_over"
        return res

    def get_rooms(self) -> Dict[Tuple[int, int], Exhibit]:
        statement = select(Exhibit)
        results = self.session.exec(statement).all()
        return {(e.row, e.col): e for e in results}

    def get_room(self, position: Position) -> Exhibit:
        statement = select(Exhibit).where(Exhibit.row == position.row, Exhibit.col == position.col)
        result = self.session.exec(statement).first()
        if not result:
            raise KeyError(f"No exhibit at {position}")
        return result

    def get_player_position(self) -> Position:
        return Position(row=self.log.player_row, col=self.log.player_col)

    def get_available_directions(self) -> List[Direction]:
        current = self.get_room(self.get_player_position())
        return [t.direction for t in current.thresholds if t.state != ThresholdState.WALL]

    def get_game_state(self) -> MuseumLog:
        return self.log

    def restore_game_state(self, state: MuseumLog) -> None:
        self.log = state
        self.session.add(self.log)
        self.session.commit()

    def get_fog_of_war_state(self) -> List[Exhibit]:
        statement = select(Exhibit).where((Exhibit.is_visible == True) | (Exhibit.is_discovered == True))
        return list(self.session.exec(statement).all())

    def get_fog_map(self) -> List[List[FogMapCell]]:
        """Return a 2D grid of FogMapCell for the contract."""
        exhibits = self.get_rooms()
        max_r = max(p[0] for p in exhibits.keys()) if exhibits else 0
        max_c = max(p[1] for p in exhibits.keys()) if exhibits else 0
        
        player_pos = self.get_player_position()
        grid = []
        for r in range(max_r + 1):
            row = []
            for c in range(max_c + 1):
                pos = Position(r, c)
                e = exhibits.get((r, c))
                
                visibility = RoomVisibility.HIDDEN
                if pos == player_pos:
                    visibility = RoomVisibility.CURRENT
                elif e and e.is_discovered:
                    visibility = RoomVisibility.VISITED
                elif e and e.is_visible:
                    visibility = RoomVisibility.VISIBLE
                
                cell = FogMapCell(
                    position=pos,
                    visibility=visibility,
                    has_trivia=bool(e.figure_name) if e else False,
                    figure_name=e.figure_name if e and (visibility in (RoomVisibility.CURRENT, RoomVisibility.VISITED)) else None,
                    is_entrance=e.is_entrance if e else False,
                    is_exit=e.is_exit if e else False,
                    doors=e.doors if e and visibility != RoomVisibility.HIDDEN else None
                )
                row.append(cell)
            grid.append(row)
        return grid

    def is_solvable(self) -> bool:
        """BFS check: can the exit be reached if all gates are opened?"""
        exhibits = self.get_rooms()
        start = self.get_player_position()
        queue = [start]
        visited = {start}
        
        while queue:
            curr_pos = queue.pop(0)
            exhibit = exhibits.get((curr_pos.row, curr_pos.col))
            if not exhibit: continue
            if exhibit.is_exit:
                return True
            
            for t in exhibit.thresholds:
                if t.state != ThresholdState.WALL and t.to_exhibit_id:
                    stmt = select(Exhibit).where(Exhibit.id == t.to_exhibit_id)
                    neighbor = self.session.exec(stmt).one()
                    n_pos = Position(neighbor.row, neighbor.col)
                    if n_pos not in visited:
                        visited.add(n_pos)
                        queue.append(n_pos)
        return False

    # --- Internal Boundary Helpers (Seeding/Init) ---

    def _ensure_museum_seeded(self):
        """Populate the museum exhibits if the database is empty."""
        if not self.session.exec(select(Exhibit)).first():
            self._seed_grand_hall()

    def _seed_grand_hall(self):
        """Populate the 3x3 Grand Hall layout."""
        exhibit_refs = {}
        for r in range(3):
            for c in range(3):
                e = Exhibit(
                    row=r, col=c,
                    is_entrance=(r == 0 and c == 0),
                    is_exit=(r == 2 and c == 2),
                    is_visible=(r == 0 and c == 0) or (r == 1 and c == 0) or (r == 0 and c == 1),
                    is_discovered=(r == 0 and c == 0)
                )
                if r == 1 and c == 1:
                    e.figure_name, e.zone = "Leonardo da Vinci", "Art Gallery"
                elif r == 2 and c == 1:
                    e.figure_name, e.zone = "Cleopatra", "Egypt"
                
                self.session.add(e)
                exhibit_refs[(r, c)] = e

        self.session.commit()

        links = [
            (0, 0, Direction.EAST, 0, 1, ThresholdState.OPEN),
            (0, 1, Direction.EAST, 0, 2, ThresholdState.OPEN),
            (0, 0, Direction.SOUTH, 1, 0, ThresholdState.OPEN),
            (0, 2, Direction.SOUTH, 1, 2, ThresholdState.OPEN),
            (1, 0, Direction.EAST, 1, 1, ThresholdState.OPEN),
            (1, 1, Direction.SOUTH, 2, 1, ThresholdState.LOCKED),
            (2, 1, Direction.EAST, 2, 2, ThresholdState.LOCKED),
        ]

        opp = {
            Direction.NORTH: Direction.SOUTH, Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST, Direction.WEST: Direction.EAST
        }

        for r1, c1, d, r2, c2, state in links:
            e1, e2 = exhibit_refs[(r1, c1)], exhibit_refs[(r2, c2)]
            t1 = Threshold(from_exhibit_id=e1.id, to_exhibit_id=e2.id, direction=d, state=state)
            t2 = Threshold(from_exhibit_id=e2.id, to_exhibit_id=e1.id, direction=opp[d], state=state)
            self.session.add(t1)
            self.session.add(t2)

        self.session.commit()

    def _load_log(self, slot: str = "default"):
        """Load or initialize the MuseumLog."""
        log = self.session.exec(select(MuseumLog).where(MuseumLog.slot_name == slot)).first()
        if not log:
            log = MuseumLog(slot_name=slot)
            self.session.add(log)
            self.session.commit()
        self.log = log

    def _spread_visibility(self, exhibit: Exhibit):
        """Internal: Mark adjacent exhibits as visible."""
        for t in exhibit.thresholds:
            if t.to_exhibit_id and t.state != ThresholdState.WALL:
                stmt = select(Exhibit).where(Exhibit.id == t.to_exhibit_id)
                neighbor = self.session.exec(stmt).first()
                if neighbor:
                    neighbor.is_visible = True
                    self.session.add(neighbor)

# --- Compatibility Aliases for the Test Suite ---
class TriviaQuestion:
    """Compatibility class for older tests. Questions now live in the DB."""
    pass

GameStatus = Fate
GameState = MuseumLog
DoorState = ThresholdState
Room = Exhibit
