"""Waxworks: The Midnight Curse — Engine Module

The orchestrator: imports maze, db, and view. Runs the game loop.
Delegates ALL rendering to the View module.

Emergency fallback implementation — local only, not pushed.
"""

import sys

from maze import (
    Direction, DoorState, GameStatus, Position,
    TriviaQuestion, Room, GameState,
)


class Engine:
    """Orchestrates the game loop, translation layer, and save/load."""

    def __init__(self, maze, repo, view, save_filepath="default"):
        """Inject dependencies.

        Parameters
        ----------
        maze : MazeProtocol
        repo : RepositoryProtocol
        view : ViewProtocol
        save_filepath : str — slot name for save/load
        """
        self._maze = maze
        self._repo = repo
        self._view = view
        self._save_filepath = save_filepath
        self._current_question = None  # Current DB-fetched question dict
        self._confronted_figure = None  # Track which figure we've already fetched a question for

    # ------------------------------------------------------------------
    # Serialization helpers (unchanged from skeleton)
    # ------------------------------------------------------------------

    @staticmethod
    def game_state_to_dict(state: GameState) -> dict:
        """Convert a GameState dataclass to a JSON-safe dict."""
        door_states_list = []
        for (r, c), doors in state.door_states.items():
            door_entry = {
                "position": {"row": r, "col": c},
                "doors": {d.value: s.value for d, s in doors.items()}
            }
            door_states_list.append(door_entry)

        return {
            "player_position": {
                "row": state.player_position.row,
                "col": state.player_position.col,
            },
            "curse_level": state.curse_level,
            "game_status": state.game_status.value,
            "defeated_figures": state.defeated_figures,
            "visited_positions": [
                {"row": p.row, "col": p.col} for p in state.visited_positions
            ],
            "door_states": door_states_list,
        }

    @staticmethod
    def dict_to_game_state(data: dict) -> GameState:
        """Convert a JSON-safe dict back to a GameState dataclass."""
        if not isinstance(data, dict):
            raise ValueError("Expected a dict for game state")

        player_pos = Position(
            data["player_position"]["row"],
            data["player_position"]["col"],
        )

        door_states = {}
        for entry in data.get("door_states", []):
            pos_data = entry["position"]
            pos_tuple = (pos_data["row"], pos_data["col"])
            doors = {
                Direction(k): DoorState(v)
                for k, v in entry["doors"].items()
            }
            door_states[pos_tuple] = doors

        return GameState(
            player_position=player_pos,
            curse_level=data.get("curse_level", data.get("wax_meter", 0)),
            game_status=GameStatus(data["game_status"]),
            defeated_figures=data.get("defeated_figures", data.get("answered_figures", [])),
            visited_positions=[
                Position(p["row"], p["col"])
                for p in data.get("visited_positions", [])
            ],
            door_states=door_states,
        )

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save_game(self):
        """Get state from maze -> convert to dict -> pass to repo.save()."""
        state = self._maze.get_game_state()
        data = self.game_state_to_dict(state)
        try:
            self._repo.save(data, self._save_filepath)
            self._view.display_save_result(True)
        except Exception as e:
            self._view.display_save_result(False, str(e))

    def load_game(self) -> bool:
        """repo.load() -> convert dict to GameState -> maze.restore().

        Returns True if load succeeded, False otherwise.
        """
        try:
            data = self._repo.load(self._save_filepath)
            if data is None:
                self._view.display_load_result(False)
                return False
            state = self.dict_to_game_state(data)
            self._maze.restore_game_state(state)
            self._view.display_load_result(True)
            return True
        except (ValueError, KeyError) as e:
            self._view.display_error(f"Failed to load: {e}")
            return False

    # ------------------------------------------------------------------
    # Game Loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main game loop with View-based rendering."""
        # Reset question bank for a fresh game (per RFC §8)
        self._repo.reset_questions()
        self._view.display_welcome()

        while self._maze.get_game_status() == GameStatus.PLAYING:
            # Display current room
            pos = self._maze.get_player_position()
            room = self._maze.get_room(pos)
            state = self._maze.get_game_state()
            self._view.display_room(room, pos, state.wax_meter, state)

            # Always show the fog map
            fog_map = self._maze.get_fog_map()
            self._view.display_fog_map(fog_map)

            # Check for trivia confrontation (undefeated figure in room)
            # Only fetch a NEW question when entering for the first time
            if (room.figure_name and
                    room.figure_name not in state.defeated_figures):
                if self._confronted_figure != room.figure_name:
                    # First time seeing this figure — fetch from DB
                    q = self._repo.get_random_question(room.figure_name)
                    if q:
                        self._current_question = q
                        self._confronted_figure = room.figure_name
                        self._view.display_confrontation(q)
                    else:
                        # All questions exhausted — auto-open gate
                        self._current_question = None
                        self._confronted_figure = room.figure_name
                        self._view.display_error(
                            "The figure sighs and steps aside. "
                            "The curse releases its grip on this gate."
                        )
                else:
                    # Already confronted — re-display same question
                    if self._current_question:
                        self._view.display_confrontation(self._current_question)
            else:
                # Not in a figure room, or figure already defeated
                self._confronted_figure = None
                self._current_question = None

            # Get player input
            command = self._view.get_input()
            if not command or command == "quit":
                return

            self._handle_command(command)

        # Game ended (won or lost)
        state = self._maze.get_game_state()
        self._view.display_endgame(
            status=self._maze.get_game_status(),
            curse_level=state.wax_meter,
            rooms_explored=len(state.visited_positions),
            total_rooms=25,
            figures_defeated=len(state.answered_figures),
            total_figures=3,
        )

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def _handle_command(self, command: str) -> None:
        """Parse and dispatch a player command."""
        parts = command.strip().lower().split()
        if not parts:
            return

        action = parts[0]

        if action == "move" and len(parts) >= 2:
            self._handle_move(parts[1])
        elif action == "answer" and len(parts) >= 2:
            self._handle_answer(parts[1])
        elif action == "save":
            self.save_game()
        elif action == "load":
            self.load_game()
        elif action == "map":
            self._handle_map()
        elif action == "quit":
            return
        else:
            self._view.display_error(
                f"Unknown command: '{command}'. "
                "Try: move <direction>, answer <A|B|C>, save, load, map, quit"
            )

    def _handle_move(self, direction_str: str) -> None:
        """Attempt to move the player in the given direction."""
        try:
            direction = Direction(direction_str.lower())
        except ValueError:
            self._view.display_error(
                f"Invalid direction: '{direction_str}'. "
                "Use: north, south, east, west"
            )
            return

        result = self._maze.move(direction)
        self._view.display_move_result(result, direction_str)

    def _handle_answer(self, answer_key: str) -> None:
        """Submit a trivia answer using the DB-fetched correct key."""
        correct_key = None
        if self._current_question:
            correct_key = self._current_question.get("correct_key")
        result = self._maze.attempt_answer(answer_key, correct_key)
        state = self._maze.get_game_state()
        self._view.display_answer_result(result, state.wax_meter)
        # Clear current question on correct answer
        if result == "correct":
            self._current_question = None

    def _handle_map(self) -> None:
        """Display the fog-of-war map."""
        fog_map = self._maze.get_fog_map()
        self._view.display_fog_map(fog_map)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    from maze import Maze
    from db import Repository
    from view import View

    maze = Maze()
    repo = Repository(db_path="waxworks.db")
    view = View()
    engine = Engine(maze, repo, view)

    # Offer to load a saved game
    try:
        response = view.get_input("\n  Load saved game? (y/n) > ")
        if response == "y":
            if engine.load_game():
                pass  # load_game already shows confirmation
            else:
                pass  # load_game already shows "no save found"
        else:
            # New game — reset question bank for fresh questions
            repo.reset_questions()
    except (EOFError, KeyboardInterrupt):
        pass

    engine.run()
