"""Waxworks: The Midnight Curse — Engine Module

The orchestrator: imports maze, db, and view. Runs the game loop.
Delegates ALL rendering to the View module.

Supports both CLI (blocking loop) and Qt (callback-driven) modes.
"""

import sys

from maze import (
    Direction, DoorState, GameStatus, Position, GameState, FIGURES,
)


class Engine:
    """Orchestrates the game loop, translation layer, and save/load."""

    def __init__(self, maze, repo, view, save_filepath="default"):
        """Inject dependencies.

        Parameters
        ----------
        maze : MazeProtocol
        repo : RepositoryProtocol
        view : ViewProtocol (View or QtView)
        save_filepath : str — slot name for save/load
        """
        self._maze = maze
        self._repo = repo
        self._view = view
        self._save_filepath = save_filepath
        self._current_question = None  # Current DB-fetched question dict
        self._confronted_figure = None  # Track which figure we've already fetched a question for

    # ------------------------------------------------------------------
    # Serialization helpers
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

    def save_game(self, silent: bool = False):
        """Get state from maze -> convert to dict -> pass to repo.save()."""
        state = self._maze.get_game_state()
        data = self.game_state_to_dict(state)
        data["maze_seed"] = self._maze.get_seed()
        data["maze_rows"] = self._maze.rows
        data["maze_cols"] = self._maze.cols
        try:
            self._repo.save(data, self._save_filepath)
            if not silent:
                self._view.display_save_result(True)
        except Exception as e:
            if not silent:
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
    # State Refresh (used by both CLI and Qt)
    # ------------------------------------------------------------------

    def refresh_display(self) -> None:
        """Push current game state to the View.

        Displays the current room, fog map, and any active confrontation.
        Called after every command in Qt mode, and inside the CLI loop.
        """
        if self._maze.get_game_status() != GameStatus.PLAYING:
            return

        pos = self._maze.get_player_position()
        room = self._maze.get_room(pos)
        state = self._maze.get_game_state()
        self._view.display_room(room, pos, state.wax_meter, state)

        # Always show the fog map
        fog_map = self._maze.get_fog_map()
        self._view.display_fog_map(fog_map)

        # Check for trivia confrontation (undefeated figure in room)
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

    def _check_endgame(self) -> bool:
        """Check if the game has ended and display the result.

        Returns True if game is over, False if still playing.
        """
        status = self._maze.get_game_status()
        if status != GameStatus.PLAYING:
            state = self._maze.get_game_state()
            total_rooms = self._maze.rows * self._maze.cols
            total_figures = len(FIGURES)
            figures_defeated = len(state.defeated_figures)
            rooms_explored = len(state.visited_positions)

            score = self.calculate_score(
                figures_defeated=figures_defeated,
                rooms_explored=rooms_explored,
                curse_level=state.curse_level,
                won=(status == GameStatus.WON),
            )

            self._repo.delete_save(self._save_filepath)

            self._view.display_endgame(
                status=status,
                curse_level=state.curse_level,
                rooms_explored=rooms_explored,
                total_rooms=total_rooms,
                figures_defeated=figures_defeated,
                total_figures=total_figures,
                score=score,
            )
            return True
        return False

    @staticmethod
    def calculate_score(figures_defeated: int, rooms_explored: int,
                        curse_level: int, won: bool) -> dict:
        """Calculate the end-of-game score breakdown."""
        figure_pts = figures_defeated * 200
        explore_pts = rooms_explored * 10
        curse_pts = max(0, (100 - curse_level) * 2) if won else 0
        win_bonus = 500 if won else 0
        total = figure_pts + explore_pts + curse_pts + win_bonus
        return {
            "figure_pts": figure_pts,
            "explore_pts": explore_pts,
            "curse_pts": curse_pts,
            "win_bonus": win_bonus,
            "total": total,
        }

    # ------------------------------------------------------------------
    # Command Dispatch (public — callable from CLI loop or Qt signals)
    # ------------------------------------------------------------------

    def handle_command(self, command: str) -> None:
        """Parse and dispatch a player command.

        Public API: called by the CLI loop or via Qt's command_issued signal.
        """
        parts = command.strip().lower().split()
        if not parts:
            return

        action = parts[0]

        if action == "move" and len(parts) >= 2:
            self.handle_move(parts[1])
        elif action == "answer" and len(parts) >= 2:
            self.handle_answer(parts[1])
        elif action == "save":
            self.save_game()
        elif action == "load":
            if self.load_game():
                self.refresh_display()
        elif action == "map":
            self.handle_map()
        elif action == "quit":
            self._handle_quit()
        elif action == "help":
            self._view.display_error(
                "Commands: move <north|south|east|west>, answer <A|B|C>, "
                "save, load, map, quit"
            )
        else:
            self._view.display_error(
                f"Unknown command: '{command}'. "
                "Try: move <direction>, answer <A|B|C>, save, load, map, quit"
            )

    def handle_move(self, direction_str: str) -> None:
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
        self.refresh_display()
        self._check_endgame()

    def handle_answer(self, answer_key: str) -> None:
        """Submit a trivia answer using the DB-fetched correct key."""
        correct_key = None
        if self._current_question:
            correct_key = self._current_question.get("correct_key")
        result = self._maze.attempt_answer(answer_key, correct_key)
        state = self._maze.get_game_state()
        self._view.display_answer_result(result, state.wax_meter)

        if result == "correct":
            self._current_question = None
            self._confronted_figure = None
        elif result == "wrong":
            figure_name = self._confronted_figure
            if figure_name:
                q = self._repo.get_random_question(figure_name)
                if q:
                    self._current_question = q
                else:
                    self._current_question = None

        self.refresh_display()
        self._check_endgame()

    def handle_map(self) -> None:
        """Display the fog-of-war map."""
        fog_map = self._maze.get_fog_map()
        self._view.display_fog_map(fog_map)

    def _handle_quit(self) -> None:
        """Handle quit command — prompts to save if game is still in progress."""
        if self._maze.get_game_status() == GameStatus.PLAYING:
            if hasattr(self._view, 'ask_save_before_quit'):
                answer = self._view.ask_save_before_quit()
                if answer == "save":
                    self.save_game()
                elif answer == "cancel":
                    return
        if hasattr(self._view, 'force_close'):
            self._view.force_close()
        elif hasattr(self._view, 'close'):
            self._view.close()
        sys.exit(0)

    # ------------------------------------------------------------------
    # CLI Game Loop (blocking — unchanged behavior)
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main CLI game loop with View-based rendering."""
        self._repo.reset_questions()
        self._view.display_welcome()

        while self._maze.get_game_status() == GameStatus.PLAYING:
            self.refresh_display()

            # Get player input (blocking in CLI mode)
            command = self._view.get_input()
            if not command or command == "quit":
                return

            self.handle_command(command)

        # Game ended (won or lost) — already handled by _check_endgame
        # but call once more in case loop exited naturally
        self._check_endgame()

    # ------------------------------------------------------------------
    # Qt Game Mode (callback-driven — non-blocking)
    # ------------------------------------------------------------------

    def start_qt(self, app) -> None:
        """Start the game in Qt mode.

        Wires the QtView's command_issued signal to handle_command(),
        displays welcome, and starts the Qt event loop.

        Parameters
        ----------
        app : QApplication
        """
        self._view.command_issued.connect(self._handle_qt_command)

        if hasattr(self._view, 'play_again_requested'):
            self._view.play_again_requested.connect(
                lambda: self._restart_game()
            )

        self._view.show()
        app.exec()

    def _handle_qt_command(self, cmd: str) -> None:
        """Route Qt commands, handling the title-screen start trigger."""
        if cmd == "__start__":
            self._view.display_welcome()
            self.refresh_display()
            return
        self.handle_command(cmd)

    def _restart_game(self) -> None:
        """Reset the maze and repo for a new game."""
        from maze import Maze
        new_maze = Maze()
        self._maze = new_maze
        self._repo.reset_questions()
        self._repo.delete_save(self._save_filepath)
        self._current_question = None
        self._confronted_figure = None
        self._view.display_welcome()
        self.refresh_display()


# ======================================================================
# CLI Entry point — run `python main.py` for the text-based game.
# For the GUI version, run `python main_gui.py`.
# ======================================================================

def _start_cli():
    """Launch the CLI game loop with resume-or-new-game logic."""
    from view import View
    from maze import Maze
    from db import Repository

    repo = Repository(db_path="waxworks.db")
    view = View()

    saved_data = repo.load("default")
    resuming = False

    if saved_data and saved_data.get("game_status") == "playing":
        try:
            response = view.get_input(
                "\n  A saved game was found. Resume? (y/n) > "
            )
            if response and response.strip().lower() == "y":
                seed = saved_data.get("maze_seed")
                rows = saved_data.get("maze_rows", 8)
                cols = saved_data.get("maze_cols", 8)
                maze = Maze(rows=rows, cols=cols, seed=seed)
                engine = Engine(maze, repo, view)
                engine.load_game()
                resuming = True
            else:
                maze = Maze()
                repo.delete_save("default")
                engine = Engine(maze, repo, view)
        except (EOFError, KeyboardInterrupt):
            maze = Maze()
            engine = Engine(maze, repo, view)
    else:
        if saved_data:
            repo.delete_save("default")
        maze = Maze()
        engine = Engine(maze, repo, view)

    if not resuming:
        repo.reset_questions()

    engine.run()


if __name__ == "__main__":
    _start_cli()
