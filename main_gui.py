"""Waxworks: The Midnight Curse — GUI Launcher

Run this file directly to start the graphical (PySide6) version of the game:

    python main_gui.py
"""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from qt_view import QtView
from maze import Maze
from db import Repository
from main import Engine


def _start_gui():
    """Launch the Qt GUI with resume-or-new-game logic."""
    app = QApplication(sys.argv)
    repo = Repository(db_path="waxworks.db")
    view = QtView()

    saved_data = repo.load("default")
    resuming = False

    if saved_data and saved_data.get("game_status") == "playing":
        box = QMessageBox(view)
        box.setWindowTitle("Waxworks: The Midnight Curse")
        box.setText("A saved game was found.\nResume previous game?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        box.setStyleSheet("""
            QMessageBox {
                background-color: #1a1228;
            }
            QLabel {
                color: #e6b832;
                font-family: 'Courier New';
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2d233c;
                border: 1px solid #5a3d8a;
                border-radius: 6px;
                padding: 8px 20px;
                color: #dcd2f0;
                font-family: 'Courier New';
                font-size: 13px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #3d2f52;
                border-color: #e6b832;
            }
        """)
        reply = box.exec()
        if reply == QMessageBox.StandardButton.Yes:
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
    else:
        if saved_data:
            repo.delete_save("default")
        maze = Maze()
        engine = Engine(maze, repo, view)

    if not resuming:
        repo.reset_questions()

    engine.start_qt(app)


if __name__ == "__main__":
    _start_gui()
