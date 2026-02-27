"""Waxworks: The Midnight Curse — Engine Module

The orchestrator: imports maze and db, owns all I/O, runs the game loop.
This is the ONLY module allowed to use input() / print() or import other
game modules.
"""

import sys

from maze import (
    Direction, DoorState, GameStatus, Position,
    TriviaQuestion, Room, GameState,
)


class Engine:
    """Orchestrates the game loop, translation layer, and save/load."""

    def __init__(self, maze, repo, save_filepath="save_game.json"):
        """Inject dependencies.

        Parameters
        ----------
        maze : MazeProtocol
            Domain object that owns all game rules.
        repo : RepositoryProtocol
            Persistence object for JSON I/O.
        save_filepath : str
            Path used for save/load operations.
        """
        self._maze = maze
        self._repo = repo
        self._save_filepath = save_filepath

    # ------------------------------------------------------------------
    # Translation Layer
    # ------------------------------------------------------------------

    @staticmethod
    def game_state_to_dict(state: GameState) -> dict:
        """Convert a GameState dataclass to a JSON-safe dict.

        - Position      -> {"row": int, "col": int}
        - GameStatus    -> str
        - Direction      -> str (value)
        - DoorState      -> str (value)
        - door_states    -> list of {"position": {…}, "doors": {…}}
        """
        door_states_list = []
        for (row, col), doors in state.door_states.items():
            door_states_list.append({
                "position": {"row": row, "col": col},
                "doors": {d.value: s.value for d, s in doors.items()},
            })

        return {
            "player_position": {
                "row": state.player_position.row,
                "col": state.player_position.col,
            },
            "wax_meter": state.wax_meter,
            "game_status": state.game_status.value,
            "answered_figures": list(state.answered_figures),
            "visited_positions": [
                {"row": p.row, "col": p.col}
                for p in state.visited_positions
            ],
            "door_states": door_states_list,
        }

    @staticmethod
    def dict_to_game_state(data: dict) -> GameState:
        """Convert a JSON-safe dict back to a GameState dataclass.

        Raises ValueError if the dict is malformed.
        """
        try:
            player_pos = Position(
                row=data["player_position"]["row"],
                col=data["player_position"]["col"],
            )
            game_status = GameStatus(data["game_status"])
            visited = [
                Position(row=p["row"], col=p["col"])
                for p in data["visited_positions"]
            ]
            door_states: dict[tuple[int, int], dict[Direction, DoorState]] = {}
            for entry in data["door_states"]:
                pos = entry["position"]
                key = (pos["row"], pos["col"])
                doors = {
                    Direction(d): DoorState(s)
                    for d, s in entry["doors"].items()
                }
                door_states[key] = doors

            return GameState(
                player_position=player_pos,
                wax_meter=data["wax_meter"],
                game_status=game_status,
                answered_figures=list(data["answered_figures"]),
                visited_positions=visited,
                door_states=door_states,
            )
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f"Malformed game state data: {e}") from e

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save_game(self) -> None:
        """Get state from maze -> convert to dict -> pass to repo.save()."""
        state = self._maze.get_game_state()
        data = self.game_state_to_dict(state)
        self._repo.save(data, self._save_filepath)

    def load_game(self) -> bool:
        """repo.load() -> convert dict to GameState -> maze.restore().

        Returns True if load succeeded, False otherwise.
        """
        try:
            data = self._repo.load(self._save_filepath)
        except (ValueError, IOError):
            return False
        if data is None:
            return False
        try:
            state = self.dict_to_game_state(data)
            self._maze.restore_game_state(state)
            return True
        except (ValueError, KeyError):
            return False

    # ------------------------------------------------------------------
    # Game Loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main game loop.

        1. Display current room, available directions, wax meter.
        2. Read player input (move / answer / save / quit).
        3. Dispatch to maze.move() or maze.attempt_answer().
        4. Check win/loss conditions.
        5. Repeat until game_status != PLAYING.
        """
        print("\n=== WAXWORKS: THE MIDNIGHT CURSE ===")
        print("You are an urban explorer trapped in the Grand Hall of History.")
        print("Find the exit before your Wax Meter reaches 100%!")
        print("\nCommands: move <north|south|east|west>, answer <A|B|C>,"
              " save, load, quit\n")

        while self._maze.get_game_status() == GameStatus.PLAYING:
            self._display_room()

            try:
                command = input("\n> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                return

            if not command:
                continue

            self._handle_command(command)

        self._display_endgame()

    # ------------------------------------------------------------------
    # Display helpers (private)
    # ------------------------------------------------------------------

    def _display_room(self) -> None:
        """Print the current room state to the console."""
        pos = self._maze.get_player_position()
        room = self._maze.get_room(pos)
        wax = self._maze.get_wax_meter()
        game_state = self._maze.get_game_state()

        # Room header
        print(f"\n--- Room ({pos.row}, {pos.col}) ---")
        if room.is_entrance:
            print("The Entrance — moonlight spills in behind you.")
        elif room.is_exit:
            print("You see the Exit ahead!")

        # Trivia question (only if unanswered)
        if (room.trivia is not None
                and room.trivia.figure_name not in game_state.answered_figures):
            t = room.trivia
            print(f"\nA wax figure stirs... {t.figure_name}!")
            print(f'"{t.question_text}"')
            for key, text in t.choices.items():
                print(f"  {key}) {text}")

        # Wax meter bar
        filled = wax // 10
        empty = 10 - filled
        bar = "\u2588" * filled + "\u2591" * empty
        print(f"\nWax Meter: [{bar}] {wax}%")

        # Available doors
        dir_strs = []
        for d in Direction:
            state = room.doors[d]
            if state != DoorState.WALL:
                dir_strs.append(f"{d.value} ({state.value})")
        print(f"Doors: {', '.join(dir_strs) if dir_strs else 'None'}")

    def _display_endgame(self) -> None:
        """Print the win or loss message."""
        status = self._maze.get_game_status()
        if status == GameStatus.WON:
            print("\nYOU ESCAPED! The curse is broken. Dawn breaks over the museum.")
            print("=== YOU WIN ===\n")
        elif status == GameStatus.LOST:
            print("\nYour skin hardens... you are now the newest exhibit.")
            print(f"Wax Meter: {self._maze.get_wax_meter()}%")
            print("=== GAME OVER ===\n")

    # ------------------------------------------------------------------
    # Command handling (private)
    # ------------------------------------------------------------------

    def _handle_command(self, command: str) -> None:
        """Parse and dispatch a player command."""
        parts = command.split()
        action = parts[0]

        if action == "move" and len(parts) == 2:
            self._handle_move(parts[1])
        elif action == "answer" and len(parts) == 2:
            self._handle_answer(parts[1].upper())
        elif action == "save":
            self._handle_save()
        elif action == "load":
            self._handle_load()
        elif action == "quit":
            print("Goodbye, brave explorer.")
            sys.exit(0)
        else:
            print("Unknown command. "
                  "Try: move <direction>, answer <A|B|C>, save, load, quit")

    def _handle_move(self, direction_str: str) -> None:
        """Attempt to move the player in the given direction."""
        try:
            direction = Direction(direction_str)
        except ValueError:
            print(f"Invalid direction: '{direction_str}'. "
                  "Use north, south, east, or west.")
            return

        result = self._maze.move(direction)
        if result == "moved":
            print(f"You move {direction_str}.")
        elif result == "locked":
            print("The way is sealed. Answer the figure's question first.")
        elif result == "wall":
            print("There's nothing but solid wall in that direction.")
        elif result == "invalid":
            print("You can't go that way.")

    def _handle_answer(self, answer_key: str) -> None:
        """Submit a trivia answer."""
        if answer_key not in ("A", "B", "C"):
            print("Invalid answer. Choose A, B, or C.")
            return

        result = self._maze.attempt_answer(answer_key)
        if result == "correct":
            print("Correct! The passage unlocks with a grinding of stone.")
        elif result == "wrong":
            print("Wrong! The wax creeps further up your arm...")
            print(f"Wax Meter: {self._maze.get_wax_meter()}%")
        elif result == "no_trivia":
            print("There is no wax figure here to answer.")
        elif result == "already_answered":
            print("You've already answered this figure's question.")
        elif result == "game_over":
            print("The game is already over.")

    def _handle_save(self) -> None:
        """Save the current game state to file."""
        try:
            self.save_game()
            print("Game saved.")
        except (IOError, OSError) as e:
            print(f"Failed to save: {e}")

    def _handle_load(self) -> None:
        """Load a previously saved game from file."""
        success = self.load_game()
        if success:
            print("Game loaded.")
        else:
            print("No saved game found.")


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    from maze import Maze
    from db import Repository

    maze = Maze()
    repo = Repository()
    engine = Engine(maze, repo)

    print("\nWould you like to load a saved game? (yes/no)")
    try:
        choice = input("> ").strip().lower()
        if choice in ("yes", "y"):
            if engine.load_game():
                print("Saved game loaded successfully!")
            else:
                print("No saved game found. Starting a new game.")
    except (EOFError, KeyboardInterrupt):
        print("\nStarting a new game.")

    engine.run()
