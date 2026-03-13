"""Waxworks: The Midnight Curse — First-Person Perspective Canvas

A QPainter-based widget that renders a pseudo-3D dungeon crawler view.
The player looks down corridors, seeing walls, doors, and wax figures
from a first-person perspective.

Uses trapezoid-based depth layers — no raycasting needed for a grid maze.
Imports maze types only — never imports db.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QPolygonF,
)

from maze import Direction, DoorState

try:
    from maze import RoomVisibility, FogMapCell
except ImportError:
    from view import RoomVisibility, FogMapCell


# ======================================================================
# Color Palette — Midnight Museum
# ======================================================================

class FPTheme:
    """Colors for the first-person dungeon view."""

    # Sky / ceiling
    CEILING_NEAR = QColor(25, 15, 40)
    CEILING_FAR = QColor(12, 8, 20)

    # Floor
    FLOOR_NEAR = QColor(50, 35, 25)
    FLOOR_FAR = QColor(30, 20, 15)
    FLOOR_TILE_A = QColor(45, 32, 22)
    FLOOR_TILE_B = QColor(38, 28, 18)

    # Walls
    WALL_LEFT = QColor(55, 40, 70)
    WALL_RIGHT = QColor(45, 32, 58)
    WALL_FRONT = QColor(50, 36, 65)
    WALL_FRONT_FAR = QColor(35, 25, 48)
    WALL_TRIM = QColor(80, 60, 100)
    WALL_DARK = QColor(25, 18, 35)

    # Doors / passages
    PASSAGE_OPEN = QColor(20, 14, 30)       # Dark void — open corridor
    GATE_GOLD = QColor(200, 160, 40)        # Golden locked gate
    GATE_GOLD_DARK = QColor(140, 110, 30)
    GATE_BAR = QColor(160, 130, 35)

    # Lighting
    TORCH_GLOW = QColor(255, 200, 80, 40)
    TORCH_FLAME = QColor(255, 180, 50)
    TORCH_CORE = QColor(255, 240, 200)

    # Figures
    FIGURE_SILHOUETTE = QColor(80, 50, 50)
    FIGURE_EYES = QColor(200, 60, 60)
    FIGURE_GLOW = QColor(200, 60, 60, 60)

    # Fog / distance fade
    FOG = QColor(15, 10, 25, 180)
    DARKNESS = QColor(8, 5, 15)

    # Text
    TEXT = QColor(220, 210, 240)
    TEXT_GOLD = QColor(255, 210, 80)


# Zone color tints — each row/wing has a distinct mood
# (hue shift applied to walls, ceiling, floor)
ZONE_TINTS = {
    0: QColor(80, 70, 120),    # Row 0 — Foyer: cool blue-purple
    1: QColor(110, 50, 60),    # Row 1 — Art Gallery: warm crimson
    2: QColor(50, 90, 80),     # Row 2 — History: teal green
    3: QColor(100, 85, 50),    # Row 3 — Ancient: sandy amber
    4: QColor(50, 100, 70),    # Row 4 — Exit: emerald
}

# Column brightness offsets — subtle variation within a row
COL_BRIGHTNESS = {
    0: -10,
    1: 0,
    2: 5,
    3: -5,
    4: 10,
}


# Direction rotation helpers
_LEFT_OF = {
    Direction.NORTH: Direction.WEST,
    Direction.SOUTH: Direction.EAST,
    Direction.EAST: Direction.NORTH,
    Direction.WEST: Direction.SOUTH,
}
_RIGHT_OF = {
    Direction.NORTH: Direction.EAST,
    Direction.SOUTH: Direction.WEST,
    Direction.EAST: Direction.SOUTH,
    Direction.WEST: Direction.NORTH,
}
_BEHIND = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
}
_DELTA = {
    Direction.NORTH: (-1, 0),
    Direction.SOUTH: (1, 0),
    Direction.EAST: (0, 1),
    Direction.WEST: (0, -1),
}


class FirstPersonCanvas(QWidget):
    """Renders a first-person perspective of the maze corridor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fog_map = None
        self._player_pos = (0, 0)
        self._facing = Direction.SOUTH  # Default facing
        self.setMinimumSize(500, 400)
        self.setStyleSheet("background-color: #080514;")

    # ------------------------------------------------------------------
    # Zone color helpers
    # ------------------------------------------------------------------

    def _zone_tint(self, base: QColor, strength: float = 0.25) -> QColor:
        """Blend a base color toward the current zone's tint color.

        strength 0.0 = pure base, 1.0 = pure zone color.
        Also applies a subtle brightness offset based on column.
        """
        row, col = self._player_pos
        tint = ZONE_TINTS.get(row, ZONE_TINTS[0])
        bright = COL_BRIGHTNESS.get(col, 0)

        r = int(base.red()   * (1 - strength) + tint.red()   * strength) + bright
        g = int(base.green() * (1 - strength) + tint.green() * strength) + bright
        b = int(base.blue()  * (1 - strength) + tint.blue()  * strength) + bright

        return QColor(
            max(0, min(255, r)),
            max(0, min(255, g)),
            max(0, min(255, b)),
            base.alpha(),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_map(self, fog_map: list) -> None:
        """Receive new fog map data and trigger repaint."""
        self._fog_map = fog_map
        # Find current player position
        if fog_map:
            for r, row in enumerate(fog_map):
                for c, cell in enumerate(row):
                    if cell.visibility == RoomVisibility.CURRENT:
                        self._player_pos = (r, c)
        self.update()

    def set_facing(self, direction: Direction) -> None:
        """Update the direction the player is facing."""
        self._facing = direction
        self.update()

    # ------------------------------------------------------------------
    # Cell lookup helpers
    # ------------------------------------------------------------------

    def _get_cell(self, row: int, col: int):
        """Get a FogMapCell at the given position, or None."""
        if (self._fog_map and
                0 <= row < len(self._fog_map) and
                0 <= col < len(self._fog_map[0])):
            return self._fog_map[row][col]
        return None

    def _get_current_cell(self):
        """Get the cell at the player's current position."""
        return self._get_cell(*self._player_pos)

    def _get_door_state(self, cell, direction: Direction):
        """Get the door state for a direction from a cell."""
        if cell and cell.doors and direction in cell.doors:
            return cell.doors[direction]
        return DoorState.WALL

    def _cell_ahead(self, from_pos, direction, steps=1):
        """Get the cell N steps ahead in the given direction."""
        dr, dc = _DELTA[direction]
        r, c = from_pos
        return self._get_cell(r + dr * steps, c + dc * steps)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        if not self._fog_map:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Draw the scene
        self._draw_ceiling(painter, w, h)
        self._draw_floor(painter, w, h)

        current = self._get_current_cell()
        if not current:
            painter.end()
            return

        facing = self._facing
        left_dir = _LEFT_OF[facing]
        right_dir = _RIGHT_OF[facing]

        # Get door states
        front_door = self._get_door_state(current, facing)
        left_door = self._get_door_state(current, left_dir)
        right_door = self._get_door_state(current, right_dir)

        # Depth: what's ahead
        ahead_1 = self._cell_ahead(self._player_pos, facing, 1)
        ahead_2 = self._cell_ahead(self._player_pos, facing, 2)

        # Draw back-to-front (painter's algorithm)
        # Layer 2 — far end of corridor (if visible)
        if front_door != DoorState.WALL and ahead_1:
            ahead_1_front = self._get_door_state(ahead_1, facing)
            if ahead_1_front != DoorState.WALL and ahead_2:
                self._draw_corridor_depth2(painter, w, h, ahead_2)
            self._draw_corridor_depth1(painter, w, h, ahead_1, ahead_1_front)

        # Side walls
        self._draw_left_wall(painter, w, h, left_door)
        self._draw_right_wall(painter, w, h, right_door)

        # Front wall / door
        self._draw_front(painter, w, h, front_door, ahead_1)

        # Torch sconces on side walls
        self._draw_torch(painter, int(w * 0.12), int(h * 0.35))
        self._draw_torch(painter, int(w * 0.88), int(h * 0.35))

        # Check for wax figure ahead
        if ahead_1 and front_door != DoorState.WALL:
            if (ahead_1.has_trivia and ahead_1.figure_name and
                    ahead_1.visibility in (RoomVisibility.VISIBLE,
                                           RoomVisibility.VISITED)):
                self._draw_figure_silhouette(painter, w, h, depth=1,
                                             name=ahead_1.figure_name)

        # Current room figure (confrontation!)
        if (current.has_trivia and current.figure_name):
            self._draw_figure_silhouette(painter, w, h, depth=0,
                                         name=current.figure_name)

        # Entrance/exit label
        if current.is_entrance:
            self._draw_room_label(painter, w, h, "🌙 ENTRANCE", FPTheme.TEXT)
        elif current.is_exit:
            self._draw_room_label(painter, w, h, "✨ EXIT", QColor(100, 230, 130))

        # Compass indicator
        self._draw_compass(painter, w, h)

        # Mini-map in corner
        self._draw_minimap(painter, w, h)

        painter.end()

    # ------------------------------------------------------------------
    # Scene Elements
    # ------------------------------------------------------------------

    def _draw_ceiling(self, painter: QPainter, w: int, h: int):
        """Draw the ceiling with zone-tinted gradient."""
        grad = QLinearGradient(0, 0, 0, h * 0.45)
        grad.setColorAt(0, self._zone_tint(FPTheme.CEILING_FAR, 0.15))
        grad.setColorAt(1, self._zone_tint(FPTheme.CEILING_NEAR, 0.2))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawRect(QRectF(0, 0, w, h * 0.45))

    def _draw_floor(self, painter: QPainter, w: int, h: int):
        """Draw the floor with zone-tinted perspective tiles."""
        grad = QLinearGradient(0, h * 0.55, 0, h)
        grad.setColorAt(0, self._zone_tint(FPTheme.FLOOR_FAR, 0.15))
        grad.setColorAt(1, self._zone_tint(FPTheme.FLOOR_NEAR, 0.15))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawRect(QRectF(0, h * 0.55, w, h * 0.45))

        # Perspective floor lines
        painter.setPen(QPen(QColor(60, 45, 32, 60), 1))
        vanish_x = w / 2
        vanish_y = h * 0.5
        for i in range(6):
            t = i / 5.0
            y = vanish_y + (h - vanish_y) * (t ** 1.5)
            painter.drawLine(QPointF(0, y), QPointF(w, y))

        for i in range(-3, 4):
            bx = vanish_x + i * (w * 0.2)
            painter.drawLine(QPointF(vanish_x, vanish_y), QPointF(bx, h))

    def _draw_left_wall(self, painter: QPainter, w: int, h: int,
                        door_state):
        """Draw the left wall with optional door/passage."""
        # Wall trapezoid
        wall = QPolygonF([
            QPointF(0, h * 0.05),          # top-left
            QPointF(w * 0.22, h * 0.2),    # top-right (inner)
            QPointF(w * 0.22, h * 0.8),    # bottom-right (inner)
            QPointF(0, h * 0.95),          # bottom-left
        ])

        wall_left = self._zone_tint(FPTheme.WALL_LEFT)
        grad = QLinearGradient(0, 0, w * 0.22, 0)
        grad.setColorAt(0, wall_left.darker(120))
        grad.setColorAt(1, wall_left)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPolygon(wall)

        # Wall trim line
        painter.setPen(QPen(self._zone_tint(FPTheme.WALL_TRIM, 0.15), 2))
        painter.drawLine(QPointF(w * 0.22, h * 0.2),
                        QPointF(w * 0.22, h * 0.8))

        # Door indication on left wall
        if door_state == DoorState.OPEN:
            # Dark archway
            arch = QPolygonF([
                QPointF(w * 0.03, h * 0.3),
                QPointF(w * 0.18, h * 0.28),
                QPointF(w * 0.18, h * 0.75),
                QPointF(w * 0.03, h * 0.78),
            ])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.PASSAGE_OPEN))
            painter.drawPolygon(arch)
            # Archway border
            painter.setPen(QPen(FPTheme.WALL_TRIM, 2))
            painter.drawPolyline(arch)

        elif door_state == DoorState.LOCKED:
            # Golden gate
            gate = QPolygonF([
                QPointF(w * 0.03, h * 0.3),
                QPointF(w * 0.18, h * 0.28),
                QPointF(w * 0.18, h * 0.75),
                QPointF(w * 0.03, h * 0.78),
            ])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.PASSAGE_OPEN))
            painter.drawPolygon(gate)

            # Gate bars
            painter.setPen(QPen(FPTheme.GATE_GOLD, 2))
            for i in range(5):
                t = i / 4.0
                x = w * 0.03 + t * (w * 0.15)
                y_top = h * 0.3 + t * (h * -0.02)
                y_bot = h * 0.78 + t * (h * -0.03)
                painter.drawLine(QPointF(x, y_top), QPointF(x, y_bot))

            # Cross bar
            painter.drawLine(QPointF(w * 0.03, h * 0.5),
                           QPointF(w * 0.18, h * 0.49))

    def _draw_right_wall(self, painter: QPainter, w: int, h: int,
                         door_state):
        """Draw the right wall with optional door/passage."""
        wall = QPolygonF([
            QPointF(w, h * 0.05),
            QPointF(w * 0.78, h * 0.2),
            QPointF(w * 0.78, h * 0.8),
            QPointF(w, h * 0.95),
        ])

        wall_right = self._zone_tint(FPTheme.WALL_RIGHT)
        grad = QLinearGradient(w, 0, w * 0.78, 0)
        grad.setColorAt(0, wall_right.darker(120))
        grad.setColorAt(1, wall_right)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawPolygon(wall)

        painter.setPen(QPen(self._zone_tint(FPTheme.WALL_TRIM, 0.15), 2))
        painter.drawLine(QPointF(w * 0.78, h * 0.2),
                        QPointF(w * 0.78, h * 0.8))

        if door_state == DoorState.OPEN:
            arch = QPolygonF([
                QPointF(w * 0.97, h * 0.3),
                QPointF(w * 0.82, h * 0.28),
                QPointF(w * 0.82, h * 0.75),
                QPointF(w * 0.97, h * 0.78),
            ])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.PASSAGE_OPEN))
            painter.drawPolygon(arch)
            painter.setPen(QPen(FPTheme.WALL_TRIM, 2))
            painter.drawPolyline(arch)

        elif door_state == DoorState.LOCKED:
            gate = QPolygonF([
                QPointF(w * 0.97, h * 0.3),
                QPointF(w * 0.82, h * 0.28),
                QPointF(w * 0.82, h * 0.75),
                QPointF(w * 0.97, h * 0.78),
            ])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.PASSAGE_OPEN))
            painter.drawPolygon(gate)

            painter.setPen(QPen(FPTheme.GATE_GOLD, 2))
            for i in range(5):
                t = i / 4.0
                x = w * 0.97 - t * (w * 0.15)
                y_top = h * 0.3 + t * (h * -0.02)
                y_bot = h * 0.78 + t * (h * -0.03)
                painter.drawLine(QPointF(x, y_top), QPointF(x, y_bot))

            painter.drawLine(QPointF(w * 0.97, h * 0.5),
                           QPointF(w * 0.82, h * 0.49))

    def _draw_front(self, painter: QPainter, w: int, h: int,
                    door_state, cell_ahead):
        """Draw the front wall, open passage, or locked gate."""
        # Front wall area
        wall_rect = QRectF(w * 0.22, h * 0.2, w * 0.56, h * 0.6)

        if door_state == DoorState.WALL:
            # Solid stone wall
            grad = QLinearGradient(w * 0.22, h * 0.2, w * 0.78, h * 0.8)
            wall_front = self._zone_tint(FPTheme.WALL_FRONT)
            grad.setColorAt(0, wall_front)
            grad.setColorAt(0.5, wall_front.lighter(110))
            grad.setColorAt(1, wall_front)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRect(wall_rect)

            # Stone brick pattern
            painter.setPen(QPen(FPTheme.WALL_DARK, 1))
            brick_h = h * 0.06
            for row in range(10):
                y = h * 0.2 + row * brick_h
                painter.drawLine(QPointF(w * 0.22, y), QPointF(w * 0.78, y))
                offset = (w * 0.08) if row % 2 == 0 else 0
                for col in range(4):
                    x = w * 0.22 + offset + col * (w * 0.14)
                    if w * 0.22 < x < w * 0.78:
                        painter.drawLine(QPointF(x, y),
                                       QPointF(x, y + brick_h))

            # Wall trim
            painter.setPen(QPen(FPTheme.WALL_TRIM, 2))
            painter.drawRect(wall_rect)

        elif door_state == DoorState.OPEN:
            # Open archway — dark corridor ahead
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.PASSAGE_OPEN))
            painter.drawRect(wall_rect)

            # Archway frame
            painter.setPen(QPen(FPTheme.WALL_TRIM, 3))
            painter.drawRect(wall_rect)

            # Arch top
            arch_path = QPainterPath()
            arch_path.moveTo(w * 0.22, h * 0.22)
            arch_path.quadTo(w * 0.5, h * 0.15, w * 0.78, h * 0.22)
            painter.setPen(QPen(FPTheme.WALL_TRIM, 3))
            painter.setBrush(QBrush(FPTheme.WALL_FRONT))
            painter.drawPath(arch_path)

        elif door_state == DoorState.LOCKED:
            # Locked golden gate
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.PASSAGE_OPEN))
            painter.drawRect(wall_rect)

            # Gate frame
            painter.setPen(QPen(FPTheme.GATE_GOLD, 3))
            painter.drawRect(wall_rect)

            # Vertical bars
            num_bars = 8
            for i in range(num_bars + 1):
                t = i / num_bars
                x = w * 0.22 + t * (w * 0.56)
                painter.setPen(QPen(FPTheme.GATE_BAR, 3))
                painter.drawLine(QPointF(x, h * 0.2), QPointF(x, h * 0.8))

            # Horizontal cross bars
            for y_frac in [0.35, 0.5, 0.65]:
                painter.drawLine(QPointF(w * 0.22, h * y_frac),
                               QPointF(w * 0.78, h * y_frac))

            # Lock symbol in center
            painter.setPen(QPen(FPTheme.GATE_GOLD, 2))
            painter.setBrush(QBrush(FPTheme.GATE_GOLD_DARK))
            lock_cx = w * 0.5
            lock_cy = h * 0.5
            painter.drawEllipse(QPointF(lock_cx, lock_cy - 8), 12, 12)
            painter.drawRect(QRectF(lock_cx - 10, lock_cy, 20, 16))

            # "LOCKED" text
            painter.setPen(FPTheme.GATE_GOLD)
            painter.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
            painter.drawText(wall_rect, Qt.AlignmentFlag.AlignBottom |
                           Qt.AlignmentFlag.AlignHCenter, "🔒 LOCKED")

    def _draw_corridor_depth1(self, painter: QPainter, w: int, h: int,
                               cell, front_door):
        """Draw the corridor 1 cell ahead (smaller, deeper)."""
        # Inner corridor walls
        inner_rect = QRectF(w * 0.3, h * 0.26, w * 0.4, h * 0.48)

        if front_door == DoorState.WALL:
            grad = QLinearGradient(w * 0.3, h * 0.26, w * 0.7, h * 0.74)
            grad.setColorAt(0, FPTheme.WALL_FRONT_FAR)
            grad.setColorAt(1, FPTheme.WALL_FRONT_FAR.darker(110))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawRect(inner_rect)

            painter.setPen(QPen(FPTheme.WALL_TRIM.darker(130), 1))
            painter.drawRect(inner_rect)
        elif front_door == DoorState.OPEN:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.DARKNESS))
            painter.drawRect(inner_rect)

            painter.setPen(QPen(FPTheme.WALL_TRIM.darker(150), 1))
            painter.drawRect(inner_rect)
        elif front_door == DoorState.LOCKED:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(FPTheme.DARKNESS))
            painter.drawRect(inner_rect)

            # Tiny gate bars
            painter.setPen(QPen(FPTheme.GATE_GOLD.darker(130), 1))
            for i in range(6):
                x = w * 0.3 + (i / 5.0) * (w * 0.4)
                painter.drawLine(QPointF(x, h * 0.26), QPointF(x, h * 0.74))

        # Side wall connectors (trapezoidal transition)
        # Left connector
        left_trap = QPolygonF([
            QPointF(w * 0.22, h * 0.2),
            QPointF(w * 0.3, h * 0.26),
            QPointF(w * 0.3, h * 0.74),
            QPointF(w * 0.22, h * 0.8),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._zone_tint(FPTheme.WALL_LEFT).darker(130)))
        painter.drawPolygon(left_trap)

        # Right connector
        right_trap = QPolygonF([
            QPointF(w * 0.78, h * 0.2),
            QPointF(w * 0.7, h * 0.26),
            QPointF(w * 0.7, h * 0.74),
            QPointF(w * 0.78, h * 0.8),
        ])
        painter.setBrush(QBrush(self._zone_tint(FPTheme.WALL_RIGHT).darker(130)))
        painter.drawPolygon(right_trap)

    def _draw_corridor_depth2(self, painter: QPainter, w: int, h: int,
                               cell):
        """Draw a hint of the corridor 2 cells ahead."""
        inner = QRectF(w * 0.37, h * 0.32, w * 0.26, h * 0.36)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(FPTheme.DARKNESS))
        painter.drawRect(inner)

        # Faint trim
        painter.setPen(QPen(FPTheme.WALL_TRIM.darker(180), 1))
        painter.drawRect(inner)

    # ------------------------------------------------------------------
    # Decorative Elements
    # ------------------------------------------------------------------

    def _draw_torch(self, painter: QPainter, x: int, y: int):
        """Draw a wall-mounted torch sconce."""
        # Bracket
        painter.setPen(QPen(FPTheme.WALL_TRIM, 2))
        painter.drawLine(QPointF(x, y + 20), QPointF(x, y + 35))
        painter.drawLine(QPointF(x - 5, y + 35), QPointF(x + 5, y + 35))

        # Flame glow
        glow = QRadialGradient(x, y + 10, 25)
        glow.setColorAt(0, FPTheme.TORCH_GLOW)
        glow.setColorAt(1, QColor(255, 200, 80, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(x, y + 10), 25, 25)

        # Flame
        flame = QPainterPath()
        flame.moveTo(x - 4, y + 18)
        flame.quadTo(x - 6, y + 5, x, y - 2)
        flame.quadTo(x + 6, y + 5, x + 4, y + 18)
        flame.closeSubpath()

        painter.setBrush(QBrush(FPTheme.TORCH_FLAME))
        painter.drawPath(flame)

        # Inner flame
        inner = QPainterPath()
        inner.moveTo(x - 2, y + 14)
        inner.quadTo(x - 3, y + 6, x, y + 2)
        inner.quadTo(x + 3, y + 6, x + 2, y + 14)
        inner.closeSubpath()
        painter.setBrush(QBrush(FPTheme.TORCH_CORE))
        painter.drawPath(inner)

    def _draw_figure_silhouette(self, painter: QPainter, w: int, h: int,
                                 depth: int, name: str):
        """Draw a character-specific wax figure silhouette."""
        if depth == 0:
            cx, cy, scale = w * 0.5, h * 0.48, 1.0
        else:
            cx, cy, scale = w * 0.5, h * 0.46, 0.5

        # Red glow behind figure
        glow = QRadialGradient(cx, cy, 45 * scale)
        glow.setColorAt(0, FPTheme.FIGURE_GLOW)
        glow.setColorAt(1, QColor(200, 60, 60, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), 55 * scale, 65 * scale)

        # Dispatch to character-specific drawing
        name_lower = name.lower()
        if "vinci" in name_lower or "leonardo" in name_lower:
            self._draw_davinci(painter, cx, cy, scale)
        elif "lincoln" in name_lower or "abraham" in name_lower:
            self._draw_lincoln(painter, cx, cy, scale)
        elif "cleopatra" in name_lower:
            self._draw_cleopatra(painter, cx, cy, scale)
        else:
            self._draw_generic_figure(painter, cx, cy, scale)

        # Name label
        if depth == 0:
            painter.setPen(FPTheme.TEXT_GOLD)
            painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            bh = 50 * scale
            painter.drawText(QRectF(cx - 100, cy + bh + 8, 200, 20),
                           Qt.AlignmentFlag.AlignCenter, name.upper())

    # -- Da Vinci: beret, beard, paintbrush --

    def _draw_davinci(self, painter: QPainter, cx, cy, scale):
        """Leonardo da Vinci — artist with beret and paintbrush."""
        s = scale
        body_color = QColor(90, 55, 55)
        robe_color = QColor(70, 45, 50)

        # Robe / body (wider, artistic flowing garment)
        robe = QPainterPath()
        robe.moveTo(cx - 22*s, cy + 50*s)      # bottom-left
        robe.lineTo(cx - 18*s, cy - 5*s)        # waist left
        robe.lineTo(cx - 14*s, cy - 25*s)       # shoulder left
        robe.lineTo(cx + 14*s, cy - 25*s)       # shoulder right
        robe.lineTo(cx + 18*s, cy - 5*s)        # waist right
        robe.lineTo(cx + 22*s, cy + 50*s)       # bottom-right
        robe.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(robe_color))
        painter.drawPath(robe)

        # Head (round, slightly larger for the genius)
        painter.setBrush(QBrush(body_color))
        painter.drawEllipse(QPointF(cx, cy - 35*s), 11*s, 13*s)

        # Beret (wide, floppy artist's cap)
        beret = QPainterPath()
        beret.moveTo(cx - 16*s, cy - 42*s)
        beret.quadTo(cx - 18*s, cy - 58*s, cx, cy - 55*s)
        beret.quadTo(cx + 14*s, cy - 52*s, cx + 12*s, cy - 42*s)
        beret.closeSubpath()
        painter.setBrush(QBrush(QColor(110, 40, 40)))
        painter.drawPath(beret)

        # Beard (long, flowing)
        beard = QPainterPath()
        beard.moveTo(cx - 8*s, cy - 26*s)
        beard.quadTo(cx - 10*s, cy - 12*s, cx - 6*s, cy - 5*s)
        beard.quadTo(cx, cy - 2*s, cx + 6*s, cy - 5*s)
        beard.quadTo(cx + 10*s, cy - 12*s, cx + 8*s, cy - 26*s)
        beard.closeSubpath()
        painter.setBrush(QBrush(QColor(160, 150, 140)))
        painter.drawPath(beard)

        # Right arm holding paintbrush
        painter.setPen(QPen(robe_color, 3*s))
        painter.drawLine(QPointF(cx + 14*s, cy - 20*s),
                        QPointF(cx + 28*s, cy + 5*s))
        # Paintbrush
        painter.setPen(QPen(QColor(139, 90, 43), 2*s))
        painter.drawLine(QPointF(cx + 26*s, cy + 2*s),
                        QPointF(cx + 35*s, cy - 18*s))
        # Brush tip
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(200, 50, 30)))
        painter.drawEllipse(QPointF(cx + 35*s, cy - 20*s), 3*s, 4*s)

        # Eyes (warm amber — artist's gaze)
        eye_color = QColor(220, 170, 60)
        eye_y = cy - 36*s
        painter.setBrush(QBrush(eye_color))
        painter.drawEllipse(QPointF(cx - 5*s, eye_y), 2.5*s, 2*s)
        painter.drawEllipse(QPointF(cx + 5*s, eye_y), 2.5*s, 2*s)

    # -- Lincoln: stovepipe hat, angular body, bow tie --

    def _draw_lincoln(self, painter: QPainter, cx, cy, scale):
        """Abraham Lincoln — tall hat, angular, presidential."""
        s = scale
        suit_color = QColor(40, 35, 45)
        skin_color = QColor(90, 65, 55)

        # Body (tall, thin, angular — suit jacket)
        body = QPainterPath()
        body.moveTo(cx - 16*s, cy + 50*s)       # bottom-left
        body.lineTo(cx - 14*s, cy + 10*s)        # hip left
        body.lineTo(cx - 16*s, cy - 10*s)        # chest left (broad)
        body.lineTo(cx - 18*s, cy - 28*s)        # shoulder left (wide)
        body.lineTo(cx + 18*s, cy - 28*s)        # shoulder right
        body.lineTo(cx + 16*s, cy - 10*s)        # chest right
        body.lineTo(cx + 14*s, cy + 10*s)        # hip right
        body.lineTo(cx + 16*s, cy + 50*s)        # bottom-right
        body.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(suit_color))
        painter.drawPath(body)

        # Suit lapels (V-shape)
        painter.setPen(QPen(QColor(55, 50, 60), 1.5*s))
        painter.drawLine(QPointF(cx, cy - 10*s), QPointF(cx - 8*s, cy - 25*s))
        painter.drawLine(QPointF(cx, cy - 10*s), QPointF(cx + 8*s, cy - 25*s))

        # Head (narrow, gaunt)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(skin_color))
        painter.drawEllipse(QPointF(cx, cy - 38*s), 9*s, 12*s)

        # Stovepipe hat (very tall!)
        hat_bottom = cy - 48*s
        hat_top = cy - 78*s
        hat_width = 12*s
        brim_width = 16*s

        # Hat body (tall rectangle)
        painter.setBrush(QBrush(QColor(30, 25, 35)))
        painter.drawRect(QRectF(cx - hat_width, hat_top,
                               hat_width * 2, hat_bottom - hat_top))
        # Hat brim
        painter.drawRect(QRectF(cx - brim_width, hat_bottom - 2*s,
                               brim_width * 2, 4*s))
        # Hat band
        painter.setPen(QPen(QColor(100, 80, 60), 2*s))
        painter.drawLine(QPointF(cx - hat_width, hat_bottom - 6*s),
                        QPointF(cx + hat_width, hat_bottom - 6*s))

        # Bow tie
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(60, 50, 65)))
        bow_y = cy - 26*s
        # Left wing
        bow_l = QPainterPath()
        bow_l.moveTo(cx, bow_y)
        bow_l.lineTo(cx - 7*s, bow_y - 3*s)
        bow_l.lineTo(cx - 7*s, bow_y + 3*s)
        bow_l.closeSubpath()
        painter.drawPath(bow_l)
        # Right wing
        bow_r = QPainterPath()
        bow_r.moveTo(cx, bow_y)
        bow_r.lineTo(cx + 7*s, bow_y - 3*s)
        bow_r.lineTo(cx + 7*s, bow_y + 3*s)
        bow_r.closeSubpath()
        painter.drawPath(bow_r)
        # Knot
        painter.drawEllipse(QPointF(cx, bow_y), 2*s, 2*s)

        # Beard (chin strap, no mustache)
        beard = QPainterPath()
        beard.moveTo(cx - 7*s, cy - 32*s)
        beard.quadTo(cx - 9*s, cy - 24*s, cx, cy - 22*s)
        beard.quadTo(cx + 9*s, cy - 24*s, cx + 7*s, cy - 32*s)
        painter.setBrush(QBrush(QColor(50, 40, 35)))
        painter.drawPath(beard)

        # Eyes (steel blue — steady presidential gaze)
        eye_color = QColor(120, 160, 200)
        eye_y = cy - 39*s
        painter.setBrush(QBrush(eye_color))
        painter.drawEllipse(QPointF(cx - 4*s, eye_y), 2*s, 2*s)
        painter.drawEllipse(QPointF(cx + 4*s, eye_y), 2*s, 2*s)

    # -- Cleopatra: nemes headdress, scepter, regal --

    def _draw_cleopatra(self, painter: QPainter, cx, cy, scale):
        """Cleopatra — Egyptian queen with headdress and scepter."""
        s = scale
        dress_color = QColor(100, 70, 45)
        skin_color = QColor(110, 75, 55)
        gold = QColor(200, 170, 50)

        # Dress (wider at hips, regal flowing gown)
        dress = QPainterPath()
        dress.moveTo(cx - 25*s, cy + 50*s)       # bottom-left
        dress.lineTo(cx - 12*s, cy + 5*s)         # hip left
        dress.lineTo(cx - 10*s, cy - 15*s)        # waist left
        dress.lineTo(cx - 12*s, cy - 25*s)        # shoulder left
        dress.lineTo(cx + 12*s, cy - 25*s)        # shoulder right
        dress.lineTo(cx + 10*s, cy - 15*s)        # waist right
        dress.lineTo(cx + 12*s, cy + 5*s)         # hip right
        dress.lineTo(cx + 25*s, cy + 50*s)        # bottom-right
        dress.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(dress_color))
        painter.drawPath(dress)

        # Gold belt/sash at waist
        painter.setPen(QPen(gold, 2*s))
        painter.drawLine(QPointF(cx - 11*s, cy - 12*s),
                        QPointF(cx + 11*s, cy - 12*s))

        # Gold collar / necklace
        collar = QPainterPath()
        collar.moveTo(cx - 12*s, cy - 25*s)
        collar.quadTo(cx, cy - 18*s, cx + 12*s, cy - 25*s)
        painter.setPen(QPen(gold, 2.5*s))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(collar)

        # Head
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(skin_color))
        painter.drawEllipse(QPointF(cx, cy - 36*s), 10*s, 12*s)

        # Nemes headdress (Egyptian striped cloth)
        nemes = QPainterPath()
        nemes.moveTo(cx - 14*s, cy - 25*s)       # left shoulder drape
        nemes.lineTo(cx - 12*s, cy - 44*s)        # left temple
        nemes.quadTo(cx, cy - 55*s, cx + 12*s, cy - 44*s)  # top arc
        nemes.lineTo(cx + 14*s, cy - 25*s)        # right shoulder drape
        nemes.closeSubpath()
        painter.setBrush(QBrush(QColor(50, 60, 100)))
        painter.drawPath(nemes)

        # Headdress stripes (gold bands)
        painter.setPen(QPen(gold, 1.5*s))
        for i in range(4):
            t = (i + 1) / 5.0
            y = cy - 25*s + t * (-25*s)
            x_offset = 12*s * (1 - t * 0.6)
            painter.drawLine(QPointF(cx - x_offset, y),
                           QPointF(cx + x_offset, y))

        # Uraeus (cobra) at forehead
        cobra = QPainterPath()
        cobra.moveTo(cx, cy - 50*s)
        cobra.quadTo(cx - 3*s, cy - 58*s, cx, cy - 62*s)
        cobra.quadTo(cx + 3*s, cy - 58*s, cx, cy - 50*s)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gold))
        painter.drawPath(cobra)
        # Cobra eye
        painter.setBrush(QBrush(QColor(200, 50, 50)))
        painter.drawEllipse(QPointF(cx, cy - 57*s), 1.5*s, 1.5*s)

        # Left hand holding scepter
        painter.setPen(QPen(dress_color, 3*s))
        painter.drawLine(QPointF(cx - 12*s, cy - 20*s),
                        QPointF(cx - 22*s, cy + 10*s))
        # Scepter (was/djed style)
        painter.setPen(QPen(gold, 2.5*s))
        painter.drawLine(QPointF(cx - 24*s, cy + 15*s),
                        QPointF(cx - 20*s, cy - 25*s))
        # Scepter head (ankh-like)
        painter.setBrush(QBrush(gold))
        painter.drawEllipse(QPointF(cx - 20*s, cy - 28*s), 4*s, 4*s)

        # Eyes (emerald green — Cleopatra's legendary gaze)
        eye_color = QColor(80, 200, 100)
        eye_y = cy - 37*s
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(eye_color))
        painter.drawEllipse(QPointF(cx - 5*s, eye_y), 2.5*s, 2*s)
        painter.drawEllipse(QPointF(cx + 5*s, eye_y), 2.5*s, 2*s)

        # Kohl eyeliner (classic Egyptian)
        painter.setPen(QPen(QColor(20, 15, 15), 1.2*s))
        painter.drawLine(QPointF(cx - 8*s, eye_y), QPointF(cx - 2*s, eye_y))
        painter.drawLine(QPointF(cx + 2*s, eye_y), QPointF(cx + 8*s, eye_y))

    # -- Fallback generic silhouette --

    def _draw_generic_figure(self, painter: QPainter, cx, cy, scale):
        """Generic humanoid for unknown figures."""
        s = scale
        body = QPainterPath()
        bw, bh = 20*s, 50*s
        body.moveTo(cx - bw, cy + bh)
        body.lineTo(cx - bw * 0.8, cy - bh * 0.3)
        body.lineTo(cx - bw * 0.4, cy - bh * 0.7)
        body.quadTo(cx, cy - bh, cx + bw * 0.4, cy - bh * 0.7)
        body.lineTo(cx + bw * 0.8, cy - bh * 0.3)
        body.lineTo(cx + bw, cy + bh)
        body.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(FPTheme.FIGURE_SILHOUETTE))
        painter.drawPath(body)

        eye_y = cy - bh * 0.55
        painter.setBrush(QBrush(FPTheme.FIGURE_EYES))
        painter.drawEllipse(QPointF(cx - 6*s, eye_y), 3*s, 2*s)
        painter.drawEllipse(QPointF(cx + 6*s, eye_y), 3*s, 2*s)

    def _draw_room_label(self, painter: QPainter, w: int, h: int,
                          text: str, color: QColor):
        """Draw a label at the top of the view."""
        painter.setPen(color)
        painter.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(0, h * 0.88, w, 30),
                        Qt.AlignmentFlag.AlignCenter, text)

    def _draw_compass(self, painter: QPainter, w: int, h: int):
        """Draw a small compass showing facing direction."""
        cx = w - 40
        cy = 35
        r = 18

        # Background circle
        painter.setPen(QPen(FPTheme.WALL_TRIM, 1))
        painter.setBrush(QBrush(QColor(20, 15, 30, 200)))
        painter.drawEllipse(QPointF(cx, cy), r, r)

        # Direction labels
        painter.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        dirs = {"N": (cx, cy - r + 10), "S": (cx, cy + r - 4),
                "E": (cx + r - 8, cy + 3), "W": (cx - r + 3, cy + 3)}
        for label, (x, y) in dirs.items():
            is_facing = (
                (label == "N" and self._facing == Direction.NORTH) or
                (label == "S" and self._facing == Direction.SOUTH) or
                (label == "E" and self._facing == Direction.EAST) or
                (label == "W" and self._facing == Direction.WEST)
            )
            color = FPTheme.TEXT_GOLD if is_facing else FPTheme.TEXT
            painter.setPen(color)
            painter.drawText(int(x), int(y), label)

        # Direction arrow
        painter.setPen(QPen(FPTheme.TEXT_GOLD, 2))
        arrow_map = {
            Direction.NORTH: (cx, cy - r + 14, cx, cy + 4),
            Direction.SOUTH: (cx, cy + r - 14, cx, cy - 4),
            Direction.EAST: (cx + r - 14, cy, cx - 4, cy),
            Direction.WEST: (cx - r + 14, cy, cx + 4, cy),
        }
        ax1, ay1, ax2, ay2 = arrow_map[self._facing]
        painter.drawLine(QPointF(ax2, ay2), QPointF(ax1, ay1))

    def _draw_minimap(self, painter: QPainter, w: int, h: int):
        """Draw a tiny 5×5 minimap in the bottom-left corner."""
        if not self._fog_map:
            return

        rows = len(self._fog_map)
        cols = len(self._fog_map[0]) if rows else 0
        cell_size = 8
        margin = 12
        map_w = cols * cell_size
        map_h = rows * cell_size

        # Background
        mx = margin
        my = h - margin - map_h
        painter.setPen(QPen(FPTheme.WALL_TRIM, 1))
        painter.setBrush(QBrush(QColor(20, 15, 30, 180)))
        painter.drawRect(QRectF(mx - 2, my - 2, map_w + 4, map_h + 4))

        for r in range(rows):
            for c in range(cols):
                cell = self._fog_map[r][c]
                x = mx + c * cell_size
                y = my + r * cell_size

                if cell.visibility == RoomVisibility.CURRENT:
                    color = FPTheme.TEXT_GOLD
                elif cell.visibility == RoomVisibility.VISITED:
                    color = QColor(70, 55, 90)
                elif cell.visibility == RoomVisibility.VISIBLE:
                    color = QColor(50, 40, 65)
                else:
                    color = QColor(20, 15, 30)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawRect(QRectF(x, y, cell_size - 1, cell_size - 1))
