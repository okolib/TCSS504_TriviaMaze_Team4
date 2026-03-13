"""Waxworks: The Midnight Curse — Maze Canvas Widget

A QWidget that renders the 5×5 museum maze with fog-of-war.
Receives FogMapCell data from the Engine (via QtView) and paints it.

Imports maze types only — never imports db.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath,
)

from maze import Direction, DoorState

# Try importing from maze, fall back to stubs
try:
    from maze import RoomVisibility, FogMapCell
except ImportError:
    from view import RoomVisibility, FogMapCell


# ======================================================================
# Theme Colors
# ======================================================================

class Theme:
    """Color palette for the maze canvas — Waxworks midnight aesthetic."""

    # Backgrounds
    BG_WINDOW = QColor(18, 12, 28)          # Deep midnight purple
    BG_CELL_HIDDEN = QColor(25, 18, 35)     # Dark fog
    BG_CELL_VISIBLE = QColor(45, 35, 60)    # Dimly lit room seen from afar
    BG_CELL_VISITED = QColor(55, 45, 75)    # Room you've been to
    BG_CELL_CURRENT = QColor(85, 60, 120)   # Current room — glowing purple

    # Door / passage colors
    DOOR_OPEN = QColor(100, 200, 130)       # Green — open passage
    DOOR_LOCKED = QColor(230, 180, 50)      # Gold — locked gate
    DOOR_WALL = QColor(40, 30, 55)          # Dark — wall (barely visible)

    # Map feature colors
    PLAYER = QColor(255, 210, 80)           # Golden glow — the player
    FIGURE = QColor(200, 80, 80)            # Red-wax — undefeated figure
    FIGURE_DEFEATED = QColor(100, 100, 120) # Dim gray — defeated figure
    ENTRANCE = QColor(100, 200, 230)        # Cyan — entrance marker
    EXIT = QColor(100, 230, 130)            # Green — exit marker
    FOG_OVERLAY = QColor(15, 10, 25, 200)   # Semi-transparent fog

    # Grid lines
    GRID = QColor(60, 45, 80)              # Subtle grid lines
    GRID_BORDER = QColor(90, 70, 130)       # Outer border

    # Text
    TEXT_PRIMARY = QColor(220, 210, 240)
    TEXT_DIM = QColor(120, 110, 140)
    TEXT_GLOW = QColor(255, 220, 100)


FIGURE_INITIALS = {
    "Leonardo da Vinci": "DV",
    "Abraham Lincoln": "AL",
    "Cleopatra": "CL",
}

WING_NAMES = ["FOYER", "ART", "HISTORY", "ANCIENT", "EXIT"]


class MazeCanvas(QWidget):
    """Renders the Waxworks maze as a 2D grid with fog-of-war."""

    # Geometry constants
    CELL_SIZE = 80
    DOOR_WIDTH = 6
    MARGIN = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fog_map = None  # list[list[FogMapCell]] — set by update_map()
        self.setMinimumSize(500, 500)
        self.setStyleSheet(f"background-color: {Theme.BG_WINDOW.name()};")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_map(self, fog_map: list) -> None:
        """Receive new fog map data and trigger repaint."""
        self._fog_map = fog_map
        self.update()  # Schedules a paintEvent

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        """Render the maze grid."""
        if not self._fog_map:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rows = len(self._fog_map)
        cols = len(self._fog_map[0]) if rows > 0 else 0
        cell = self.CELL_SIZE

        # Center the grid in the widget
        grid_w = cols * cell
        grid_h = rows * cell
        offset_x = (self.width() - grid_w) / 2
        offset_y = (self.height() - grid_h) / 2

        # Draw cells
        for r in range(rows):
            for c in range(cols):
                fog_cell = self._fog_map[r][c]
                x = offset_x + c * cell
                y = offset_y + r * cell
                self._draw_cell(painter, fog_cell, x, y, cell)

        # Draw doors / passages between cells
        for r in range(rows):
            for c in range(cols):
                fog_cell = self._fog_map[r][c]
                x = offset_x + c * cell
                y = offset_y + r * cell
                self._draw_doors(painter, fog_cell, x, y, cell, rows, cols)

        # Draw wing labels on the left
        painter.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        for r in range(rows):
            label = WING_NAMES[r] if r < len(WING_NAMES) else f"W{r}"
            y = offset_y + r * cell + cell / 2 + 4
            painter.setPen(Theme.TEXT_DIM)
            painter.drawText(int(offset_x - 48), int(y), label)

        # Column numbers on top
        for c in range(cols):
            x = offset_x + c * cell + cell / 2 - 4
            painter.setPen(Theme.TEXT_DIM)
            painter.drawText(int(x), int(offset_y - 8), str(c))

        painter.end()

    # ------------------------------------------------------------------
    # Cell drawing
    # ------------------------------------------------------------------

    def _draw_cell(self, painter: QPainter, cell, x: float, y: float,
                   size: int) -> None:
        """Draw a single maze cell with visibility-based styling."""
        rect = QRectF(x + 1, y + 1, size - 2, size - 2)

        # Background based on visibility
        if cell.visibility == RoomVisibility.CURRENT:
            # Glowing current room
            grad = QRadialGradient(x + size/2, y + size/2, size * 0.7)
            grad.setColorAt(0, Theme.BG_CELL_CURRENT.lighter(130))
            grad.setColorAt(1, Theme.BG_CELL_CURRENT)
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(Theme.GRID_BORDER, 2))
        elif cell.visibility == RoomVisibility.VISITED:
            painter.setBrush(QBrush(Theme.BG_CELL_VISITED))
            painter.setPen(QPen(Theme.GRID, 1))
        elif cell.visibility == RoomVisibility.VISIBLE:
            painter.setBrush(QBrush(Theme.BG_CELL_VISIBLE))
            painter.setPen(QPen(Theme.GRID, 1))
        else:  # HIDDEN
            painter.setBrush(QBrush(Theme.BG_CELL_HIDDEN))
            painter.setPen(QPen(Theme.BG_CELL_HIDDEN.lighter(110), 1))

        painter.drawRoundedRect(rect, 4, 4)

        # Cell content
        if cell.visibility == RoomVisibility.HIDDEN:
            # Fog pattern — draw a subtle "?" or nothing
            painter.setPen(Theme.TEXT_DIM)
            painter.setFont(QFont("Courier New", 12))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "▓")
            return

        # Draw cell features
        if cell.visibility == RoomVisibility.CURRENT:
            self._draw_player(painter, x, y, size)
        elif cell.is_entrance:
            painter.setPen(Theme.ENTRANCE)
            painter.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "EN")
        elif cell.is_exit:
            painter.setPen(Theme.EXIT)
            painter.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "EX")
        elif cell.has_trivia and cell.figure_name:
            initials = FIGURE_INITIALS.get(cell.figure_name, "??")
            painter.setPen(Theme.FIGURE)
            painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"🗿{initials}")

        # Show entrance/exit labels on current room too
        if cell.visibility == RoomVisibility.CURRENT:
            if cell.is_entrance:
                painter.setPen(Theme.ENTRANCE)
                painter.setFont(QFont("Courier New", 7))
                painter.drawText(
                    QRectF(x, y + size - 16, size, 14),
                    Qt.AlignmentFlag.AlignCenter, "ENTRANCE"
                )
            elif cell.is_exit:
                painter.setPen(Theme.EXIT)
                painter.setFont(QFont("Courier New", 7))
                painter.drawText(
                    QRectF(x, y + size - 16, size, 14),
                    Qt.AlignmentFlag.AlignCenter, "EXIT"
                )

    def _draw_player(self, painter: QPainter, x: float, y: float,
                     size: int) -> None:
        """Draw the player icon (golden candle glow)."""
        cx = x + size / 2
        cy = y + size / 2

        # Outer glow
        glow = QRadialGradient(cx, cy, size * 0.35)
        glow.setColorAt(0, QColor(255, 220, 80, 120))
        glow.setColorAt(1, QColor(255, 220, 80, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), size * 0.35, size * 0.35)

        # Player symbol
        painter.setPen(Theme.PLAYER)
        painter.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        painter.drawText(
            QRectF(x, y, size, size),
            Qt.AlignmentFlag.AlignCenter, "@"
        )

    # ------------------------------------------------------------------
    # Door drawing
    # ------------------------------------------------------------------

    def _draw_doors(self, painter: QPainter, cell, x: float, y: float,
                    size: int, rows: int, cols: int) -> None:
        """Draw passage indicators between cells."""
        if cell.visibility == RoomVisibility.HIDDEN:
            return
        if not cell.doors:
            return

        dw = self.DOOR_WIDTH
        r, c = cell.position.row, cell.position.col

        # East door (draw on right edge)
        if c < cols - 1 and Direction.EAST in cell.doors:
            door = cell.doors[Direction.EAST]
            dy = y + size/2 - dw
            dx = x + size - 1
            color = self._door_color(door)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(QRectF(dx - 2, dy, 6, dw * 2))

            if door == DoorState.LOCKED:
                painter.setPen(QPen(Theme.DOOR_LOCKED, 1))
                painter.setFont(QFont("Courier", 8, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(dx - 6, dy - 2, 14, dw * 2 + 4),
                    Qt.AlignmentFlag.AlignCenter, "🔒"
                )

        # South door (draw on bottom edge)
        if r < rows - 1 and Direction.SOUTH in cell.doors:
            door = cell.doors[Direction.SOUTH]
            dx = x + size/2 - dw
            dy = y + size - 1
            color = self._door_color(door)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRect(QRectF(dx, dy - 2, dw * 2, 6))

            if door == DoorState.LOCKED:
                painter.setPen(QPen(Theme.DOOR_LOCKED, 1))
                painter.setFont(QFont("Courier", 8, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(dx - 2, dy - 6, dw * 2 + 4, 14),
                    Qt.AlignmentFlag.AlignCenter, "🔒"
                )

    def _door_color(self, door_state) -> QColor:
        """Return the color for a door based on its state."""
        if door_state == DoorState.OPEN:
            return Theme.DOOR_OPEN
        elif door_state == DoorState.LOCKED:
            return Theme.DOOR_LOCKED
        else:
            return Theme.DOOR_WALL
