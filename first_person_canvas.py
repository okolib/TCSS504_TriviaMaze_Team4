"""Waxworks: The Midnight Curse — First-Person Perspective Canvas

A QPainter-based widget that renders a pseudo-3D dungeon crawler view.
The player looks down corridors, seeing walls, doors, and wax figures
from a first-person perspective.

Uses trapezoid-based depth layers — no raycasting needed for a grid maze.
Imports maze types only — never imports db.
"""

import math
from pathlib import Path

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QPolygonF, QPixmap, QImage,
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


ZONE_TINTS = {
    0: QColor(80, 70, 120),    # Row 0 — Entrance: cool blue-purple
    1: QColor(110, 50, 60),    # Row 1 — warm crimson
    2: QColor(50, 90, 80),     # Row 2 — teal green
    3: QColor(100, 85, 50),    # Row 3 — sandy amber
    4: QColor(80, 60, 110),    # Row 4 — violet
    5: QColor(60, 100, 70),    # Row 5 — emerald
    6: QColor(100, 60, 80),    # Row 6 — rose
    7: QColor(50, 100, 90),    # Row 7 — Exit: aquamarine
}

COL_BRIGHTNESS = {
    0: -10, 1: 0, 2: 5, 3: -5, 4: 10, 5: -8, 6: 3, 7: -3,
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


_PORTRAIT_DIR = Path(__file__).parent / "assets" / "portraits"
_PORTRAIT_FILES = {
    "Leonardo DiCaprio": "dicaprio_wax.png",
    "Michael Jackson": "jackson_wax.png",
    "Abraham Lincoln": "lincoln_wax.png",
    "Walt Disney": "disney_wax.png",
    "Taylor Swift": "swift_wax.png",
}


class FirstPersonCanvas(QWidget):
    """Renders a first-person perspective of the maze corridor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fog_map = None
        self._player_pos = (0, 0)
        self._facing = Direction.SOUTH
        self._defeated_figures: set[str] = set()

        # Walking animation state
        self._walk_frame = 0
        self._walk_total = 8
        self._walking = False
        self._walk_timer = QTimer(self)
        self._walk_timer.setInterval(45)
        self._walk_timer.timeout.connect(self._advance_walk)

        # Figure come-to-life animation
        self._figure_anim_frame = 0
        self._figure_anim_active = False
        self._figure_anim_timer = QTimer(self)
        self._figure_anim_timer.setInterval(60)
        self._figure_anim_timer.timeout.connect(self._advance_figure_anim)

        # Pre-load portrait pixmaps
        self._portraits: dict[str, QPixmap] = {}
        for name, fname in _PORTRAIT_FILES.items():
            path = _PORTRAIT_DIR / fname
            if path.exists():
                self._portraits[name] = QPixmap(str(path))

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

    def set_defeated_figures(self, defeated: list) -> None:
        """Update the set of defeated figure names."""
        self._defeated_figures = set(defeated)
        self.update()

    def start_walk_animation(self) -> None:
        """Trigger the corridor-zoom walking animation."""
        self._walk_frame = 0
        self._walking = True
        self._walk_timer.start()

    def start_figure_animation(self) -> None:
        """Trigger the figure come-to-life animation (eye glow + sway)."""
        self._figure_anim_frame = 0
        self._figure_anim_active = True
        self._figure_anim_timer.start()

    def _advance_walk(self):
        self._walk_frame += 1
        if self._walk_frame >= self._walk_total:
            self._walking = False
            self._walk_timer.stop()
        self.update()

    def _advance_figure_anim(self):
        self._figure_anim_frame += 1
        if self._figure_anim_frame >= 30:
            self._figure_anim_active = False
            self._figure_anim_timer.stop()
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

        # Walking bobbing effect
        if self._walking and self._walk_frame < self._walk_total:
            t = self._walk_frame / self._walk_total
            bob_y = math.sin(t * math.pi * 3) * 6
            zoom = 1.0 + t * 0.08
            painter.translate(0, bob_y)
            painter.translate(w / 2, h / 2)
            painter.scale(zoom, zoom)
            painter.translate(-w / 2, -h / 2)

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

        # Check for wax figure ahead (only undefeated)
        if ahead_1 and front_door != DoorState.WALL:
            if (ahead_1.has_trivia and ahead_1.figure_name and
                    ahead_1.figure_name not in self._defeated_figures and
                    ahead_1.visibility in (RoomVisibility.VISIBLE,
                                           RoomVisibility.VISITED)):
                self._draw_figure_silhouette(painter, w, h, depth=1,
                                             name=ahead_1.figure_name)

        # Current room figure (only undefeated)
        if (current.has_trivia and current.figure_name and
                current.figure_name not in self._defeated_figures):
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
        """Draw a wax figure — real portrait at depth 0, silhouette at depth 1."""
        if depth == 0:
            cx, cy, scale = w * 0.5, h * 0.48, 1.0
        else:
            cx, cy, scale = w * 0.5, h * 0.46, 0.5

        sway_x = 0.0
        glow_alpha = 60
        if self._figure_anim_active and depth == 0:
            t = self._figure_anim_frame / 30.0
            sway_x = math.sin(t * math.pi * 4) * 3 * scale
            glow_alpha = int(60 + 80 * abs(math.sin(t * math.pi * 6)))

        glow = QRadialGradient(cx + sway_x, cy, 55 * scale)
        glow.setColorAt(0, QColor(200, 60, 60, glow_alpha))
        glow.setColorAt(1, QColor(200, 60, 60, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx + sway_x, cy), 65 * scale, 75 * scale)

        adj_cx = cx + sway_x

        # At depth 0, draw the real portrait image if available
        portrait = self._portraits.get(name)
        if portrait and depth == 0:
            img_h = int(h * 0.55)
            scaled = portrait.scaledToHeight(
                img_h, Qt.TransformationMode.SmoothTransformation
            )
            img_w = scaled.width()
            draw_x = int(adj_cx - img_w / 2)
            draw_y = int(cy - img_h * 0.55)

            # Slight purple vignette overlay around the image
            painter.setOpacity(0.92)
            painter.drawPixmap(draw_x, draw_y, scaled)
            painter.setOpacity(1.0)

            # Subtle border glow
            painter.setPen(QPen(QColor(230, 184, 50, 100), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(draw_x, draw_y, img_w, img_h))
        elif portrait and depth == 1:
            # Small thumbnail at distance
            img_h = int(h * 0.22)
            scaled = portrait.scaledToHeight(
                img_h, Qt.TransformationMode.SmoothTransformation
            )
            img_w = scaled.width()
            draw_x = int(cx - img_w / 2)
            draw_y = int(cy - img_h * 0.5)
            painter.setOpacity(0.6)
            painter.drawPixmap(draw_x, draw_y, scaled)
            painter.setOpacity(1.0)
        else:
            # Fallback to geometric silhouette
            name_lower = name.lower()
            if "dicaprio" in name_lower:
                self._draw_dicaprio(painter, adj_cx, cy, scale)
            elif "jackson" in name_lower:
                self._draw_jackson(painter, adj_cx, cy, scale)
            elif "lincoln" in name_lower:
                self._draw_lincoln(painter, adj_cx, cy, scale)
            elif "disney" in name_lower:
                self._draw_disney(painter, adj_cx, cy, scale)
            elif "swift" in name_lower:
                self._draw_swift(painter, adj_cx, cy, scale)
            else:
                self._draw_generic_figure(painter, adj_cx, cy, scale)

        if self._figure_anim_active and depth == 0:
            self._draw_wax_particles(painter, adj_cx, cy, scale)

        if depth == 0:
            painter.setPen(FPTheme.TEXT_GOLD)
            painter.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            bh = 50 * scale
            painter.drawText(QRectF(cx - 100, cy + bh + 8, 200, 20),
                           Qt.AlignmentFlag.AlignCenter, name.upper())

    # -- DiCaprio: slicked-back hair, sharp suit, smirk --

    def _draw_dicaprio(self, painter: QPainter, cx, cy, scale):
        s = scale
        suit = QColor(50, 45, 60)
        skin = QColor(110, 85, 70)

        body = QPainterPath()
        body.moveTo(cx - 18*s, cy + 50*s)
        body.lineTo(cx - 15*s, cy + 5*s)
        body.lineTo(cx - 16*s, cy - 25*s)
        body.lineTo(cx + 16*s, cy - 25*s)
        body.lineTo(cx + 15*s, cy + 5*s)
        body.lineTo(cx + 18*s, cy + 50*s)
        body.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(suit))
        painter.drawPath(body)

        painter.setPen(QPen(QColor(60, 55, 70), 1.5*s))
        painter.drawLine(QPointF(cx, cy - 8*s), QPointF(cx - 7*s, cy - 22*s))
        painter.drawLine(QPointF(cx, cy - 8*s), QPointF(cx + 7*s, cy - 22*s))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(skin))
        painter.drawEllipse(QPointF(cx, cy - 36*s), 10*s, 12*s)

        hair = QPainterPath()
        hair.moveTo(cx - 11*s, cy - 38*s)
        hair.quadTo(cx - 12*s, cy - 52*s, cx, cy - 50*s)
        hair.quadTo(cx + 12*s, cy - 52*s, cx + 11*s, cy - 38*s)
        hair.closeSubpath()
        painter.setBrush(QBrush(QColor(80, 60, 40)))
        painter.drawPath(hair)

        eye_y = cy - 37*s
        painter.setBrush(QBrush(QColor(100, 150, 200)))
        painter.drawEllipse(QPointF(cx - 4*s, eye_y), 2.5*s, 2*s)
        painter.drawEllipse(QPointF(cx + 4*s, eye_y), 2.5*s, 2*s)

        painter.setPen(QPen(skin.darker(130), 1*s))
        painter.drawLine(QPointF(cx - 3*s, cy - 30*s), QPointF(cx + 3*s, cy - 30*s))

    # -- Michael Jackson: military jacket, single glove, curly hair --

    def _draw_jackson(self, painter: QPainter, cx, cy, scale):
        s = scale
        jacket = QColor(130, 30, 30)
        skin = QColor(100, 75, 60)

        body = QPainterPath()
        body.moveTo(cx - 16*s, cy + 50*s)
        body.lineTo(cx - 14*s, cy + 5*s)
        body.lineTo(cx - 15*s, cy - 25*s)
        body.lineTo(cx + 15*s, cy - 25*s)
        body.lineTo(cx + 14*s, cy + 5*s)
        body.lineTo(cx + 16*s, cy + 50*s)
        body.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(jacket))
        painter.drawPath(body)

        painter.setPen(QPen(QColor(200, 170, 50), 1.5*s))
        for i in range(4):
            y_off = cy - 18*s + i * 8*s
            painter.drawLine(QPointF(cx - 8*s, y_off), QPointF(cx + 8*s, y_off))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(skin))
        painter.drawEllipse(QPointF(cx, cy - 36*s), 10*s, 12*s)

        hair = QPainterPath()
        hair.moveTo(cx - 12*s, cy - 34*s)
        hair.quadTo(cx - 16*s, cy - 55*s, cx, cy - 52*s)
        hair.quadTo(cx + 16*s, cy - 55*s, cx + 12*s, cy - 34*s)
        hair.closeSubpath()
        painter.setBrush(QBrush(QColor(25, 20, 20)))
        painter.drawPath(hair)

        painter.setPen(QPen(jacket, 3*s))
        painter.drawLine(QPointF(cx + 15*s, cy - 20*s), QPointF(cx + 28*s, cy + 5*s))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(220, 220, 220)))
        painter.drawEllipse(QPointF(cx + 30*s, cy + 6*s), 4*s, 5*s)

        eye_y = cy - 37*s
        painter.setBrush(QBrush(QColor(60, 40, 30)))
        painter.drawEllipse(QPointF(cx - 4*s, eye_y), 2.5*s, 2*s)
        painter.drawEllipse(QPointF(cx + 4*s, eye_y), 2.5*s, 2*s)

    # -- Lincoln: stovepipe hat, angular body, bow tie --

    def _draw_lincoln(self, painter: QPainter, cx, cy, scale):
        s = scale
        suit_color = QColor(40, 35, 45)
        skin_color = QColor(90, 65, 55)

        body = QPainterPath()
        body.moveTo(cx - 16*s, cy + 50*s)
        body.lineTo(cx - 14*s, cy + 10*s)
        body.lineTo(cx - 16*s, cy - 10*s)
        body.lineTo(cx - 18*s, cy - 28*s)
        body.lineTo(cx + 18*s, cy - 28*s)
        body.lineTo(cx + 16*s, cy - 10*s)
        body.lineTo(cx + 14*s, cy + 10*s)
        body.lineTo(cx + 16*s, cy + 50*s)
        body.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(suit_color))
        painter.drawPath(body)

        painter.setPen(QPen(QColor(55, 50, 60), 1.5*s))
        painter.drawLine(QPointF(cx, cy - 10*s), QPointF(cx - 8*s, cy - 25*s))
        painter.drawLine(QPointF(cx, cy - 10*s), QPointF(cx + 8*s, cy - 25*s))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(skin_color))
        painter.drawEllipse(QPointF(cx, cy - 38*s), 9*s, 12*s)

        hat_bottom = cy - 48*s
        hat_top = cy - 78*s
        hw, bw = 12*s, 16*s
        painter.setBrush(QBrush(QColor(30, 25, 35)))
        painter.drawRect(QRectF(cx - hw, hat_top, hw * 2, hat_bottom - hat_top))
        painter.drawRect(QRectF(cx - bw, hat_bottom - 2*s, bw * 2, 4*s))
        painter.setPen(QPen(QColor(100, 80, 60), 2*s))
        painter.drawLine(QPointF(cx - hw, hat_bottom - 6*s),
                        QPointF(cx + hw, hat_bottom - 6*s))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(60, 50, 65)))
        bow_y = cy - 26*s
        for sign in (-1, 1):
            tri = QPainterPath()
            tri.moveTo(cx, bow_y)
            tri.lineTo(cx + sign*7*s, bow_y - 3*s)
            tri.lineTo(cx + sign*7*s, bow_y + 3*s)
            tri.closeSubpath()
            painter.drawPath(tri)
        painter.drawEllipse(QPointF(cx, bow_y), 2*s, 2*s)

        beard = QPainterPath()
        beard.moveTo(cx - 7*s, cy - 32*s)
        beard.quadTo(cx - 9*s, cy - 24*s, cx, cy - 22*s)
        beard.quadTo(cx + 9*s, cy - 24*s, cx + 7*s, cy - 32*s)
        painter.setBrush(QBrush(QColor(50, 40, 35)))
        painter.drawPath(beard)

        eye_y = cy - 39*s
        painter.setBrush(QBrush(QColor(120, 160, 200)))
        painter.drawEllipse(QPointF(cx - 4*s, eye_y), 2*s, 2*s)
        painter.drawEllipse(QPointF(cx + 4*s, eye_y), 2*s, 2*s)

    # -- Walt Disney: warm suit, thin mustache, Mickey ears silhouette --

    def _draw_disney(self, painter: QPainter, cx, cy, scale):
        s = scale
        suit = QColor(60, 50, 45)
        skin = QColor(110, 85, 70)

        body = QPainterPath()
        body.moveTo(cx - 17*s, cy + 50*s)
        body.lineTo(cx - 14*s, cy + 5*s)
        body.lineTo(cx - 15*s, cy - 25*s)
        body.lineTo(cx + 15*s, cy - 25*s)
        body.lineTo(cx + 14*s, cy + 5*s)
        body.lineTo(cx + 17*s, cy + 50*s)
        body.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(suit))
        painter.drawPath(body)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(skin))
        painter.drawEllipse(QPointF(cx, cy - 36*s), 10*s, 12*s)

        hair = QPainterPath()
        hair.moveTo(cx - 10*s, cy - 40*s)
        hair.quadTo(cx - 11*s, cy - 52*s, cx, cy - 50*s)
        hair.quadTo(cx + 11*s, cy - 52*s, cx + 10*s, cy - 40*s)
        hair.closeSubpath()
        painter.setBrush(QBrush(QColor(50, 40, 35)))
        painter.drawPath(hair)

        painter.setPen(QPen(QColor(50, 40, 35), 1.5*s))
        painter.drawLine(QPointF(cx - 5*s, cy - 30*s), QPointF(cx - 2*s, cy - 29*s))
        painter.drawLine(QPointF(cx + 2*s, cy - 29*s), QPointF(cx + 5*s, cy - 30*s))

        painter.setPen(QPen(suit, 3*s))
        painter.drawLine(QPointF(cx + 15*s, cy - 18*s), QPointF(cx + 25*s, cy + 10*s))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(20, 18, 22)))
        painter.drawEllipse(QPointF(cx + 20*s, cy - 55*s), 6*s, 6*s)
        painter.drawEllipse(QPointF(cx + 30*s, cy - 55*s), 6*s, 6*s)
        painter.drawEllipse(QPointF(cx + 25*s, cy - 48*s), 5*s, 5*s)

        eye_y = cy - 37*s
        painter.setBrush(QBrush(QColor(100, 130, 180)))
        painter.drawEllipse(QPointF(cx - 4*s, eye_y), 2.5*s, 2*s)
        painter.drawEllipse(QPointF(cx + 4*s, eye_y), 2.5*s, 2*s)

    # -- Taylor Swift: sparkly dress, flowing hair, microphone --

    def _draw_swift(self, painter: QPainter, cx, cy, scale):
        s = scale
        dress = QColor(90, 50, 110)
        skin = QColor(115, 90, 75)

        gown = QPainterPath()
        gown.moveTo(cx - 25*s, cy + 50*s)
        gown.lineTo(cx - 10*s, cy + 5*s)
        gown.lineTo(cx - 10*s, cy - 15*s)
        gown.lineTo(cx - 12*s, cy - 25*s)
        gown.lineTo(cx + 12*s, cy - 25*s)
        gown.lineTo(cx + 10*s, cy - 15*s)
        gown.lineTo(cx + 10*s, cy + 5*s)
        gown.lineTo(cx + 25*s, cy + 50*s)
        gown.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(dress))
        painter.drawPath(gown)

        painter.setPen(QPen(QColor(200, 170, 230, 120), 1*s))
        for i in range(6):
            sparkle_y = cy - 10*s + i * 10*s
            painter.drawEllipse(QPointF(cx - 5*s + (i % 3)*5*s, sparkle_y), 1.5*s, 1.5*s)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(skin))
        painter.drawEllipse(QPointF(cx, cy - 36*s), 10*s, 12*s)

        hair = QPainterPath()
        hair.moveTo(cx - 12*s, cy - 20*s)
        hair.quadTo(cx - 14*s, cy - 50*s, cx, cy - 52*s)
        hair.quadTo(cx + 14*s, cy - 50*s, cx + 12*s, cy - 20*s)
        hair.closeSubpath()
        painter.setBrush(QBrush(QColor(160, 120, 60)))
        painter.drawPath(hair)

        painter.setPen(QPen(dress, 3*s))
        painter.drawLine(QPointF(cx + 12*s, cy - 18*s), QPointF(cx + 24*s, cy - 8*s))
        painter.setPen(QPen(QColor(80, 80, 80), 2*s))
        painter.drawLine(QPointF(cx + 24*s, cy - 8*s), QPointF(cx + 24*s, cy - 22*s))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(80, 80, 80)))
        painter.drawEllipse(QPointF(cx + 24*s, cy - 24*s), 4*s, 3*s)

        eye_y = cy - 37*s
        painter.setBrush(QBrush(QColor(100, 160, 200)))
        painter.drawEllipse(QPointF(cx - 4*s, eye_y), 2.5*s, 2*s)
        painter.drawEllipse(QPointF(cx + 4*s, eye_y), 2.5*s, 2*s)

        painter.setPen(QPen(QColor(180, 50, 50), 1.5*s))
        painter.drawLine(QPointF(cx - 3*s, cy - 28*s), QPointF(cx + 3*s, cy - 28*s))

    # -- Fallback generic silhouette --

    def _draw_generic_figure(self, painter: QPainter, cx, cy, scale):
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

    # -- Wax cracking particles --

    def _draw_wax_particles(self, painter: QPainter, cx, cy, scale):
        s = scale
        t = self._figure_anim_frame / 30.0
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(8):
            angle = (i / 8.0) * math.pi * 2 + t * 3
            dist = 20 * s + t * 40 * s
            px = cx + math.cos(angle) * dist
            py = cy + math.sin(angle) * dist - t * 30 * s
            alpha = int(200 * (1 - t))
            painter.setBrush(QBrush(QColor(180, 160, 120, max(0, alpha))))
            painter.drawEllipse(QPointF(px, py), 2*s, 1.5*s)

    def _draw_room_label(self, painter: QPainter, w: int, h: int,
                          text: str, color: QColor):
        painter.setPen(color)
        painter.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(0, h * 0.88, w, 30),
                        Qt.AlignmentFlag.AlignCenter, text)

    def _draw_compass(self, painter: QPainter, w: int, h: int):
        """Rotated compass — the direction you're facing is always on top."""
        cx = w - 40
        cy = 35
        radius = 18

        painter.setPen(QPen(FPTheme.WALL_TRIM, 1))
        painter.setBrush(QBrush(QColor(20, 15, 30, 200)))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

        rotation = {
            Direction.NORTH: 0,
            Direction.EAST: -90,
            Direction.SOUTH: -180,
            Direction.WEST: -270,
        }
        angle = math.radians(rotation[self._facing])

        base_positions = {
            "N": (0, -1),
            "S": (0, 1),
            "E": (1, 0),
            "W": (-1, 0),
        }

        painter.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        for label, (bx, by) in base_positions.items():
            rx = bx * math.cos(angle) - by * math.sin(angle)
            ry = bx * math.sin(angle) + by * math.cos(angle)
            lx = cx + rx * (radius - 7)
            ly = cy + ry * (radius - 7) + 3

            is_facing = (
                (label == "N" and self._facing == Direction.NORTH) or
                (label == "S" and self._facing == Direction.SOUTH) or
                (label == "E" and self._facing == Direction.EAST) or
                (label == "W" and self._facing == Direction.WEST)
            )
            painter.setPen(FPTheme.TEXT_GOLD if is_facing else FPTheme.TEXT)
            painter.drawText(int(lx - 3), int(ly), label)

        painter.setPen(QPen(FPTheme.TEXT_GOLD, 2))
        painter.drawLine(
            QPointF(cx, cy + 4),
            QPointF(cx, cy - radius + 6),
        )

    def _draw_minimap(self, painter: QPainter, w: int, h: int):
        """Enhanced minimap with larger cells, glow border, locked-door dots."""
        if not self._fog_map:
            return

        rows = len(self._fog_map)
        cols = len(self._fog_map[0]) if rows else 0
        cell_size = 11
        margin = 12
        map_w = cols * cell_size
        map_h = rows * cell_size

        mx = margin
        my = h - margin - map_h

        painter.setPen(QPen(FPTheme.WALL_TRIM, 1))
        painter.setBrush(QBrush(QColor(20, 15, 30, 200)))
        painter.drawRect(QRectF(mx - 3, my - 3, map_w + 6, map_h + 6))

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

                # Glow border on current room
                if cell.visibility == RoomVisibility.CURRENT:
                    glow = QRadialGradient(
                        x + cell_size / 2, y + cell_size / 2, cell_size
                    )
                    glow.setColorAt(0, QColor(255, 210, 80, 60))
                    glow.setColorAt(1, QColor(255, 210, 80, 0))
                    painter.setBrush(QBrush(glow))
                    painter.drawRect(QRectF(x - 2, y - 2, cell_size + 3, cell_size + 3))

                # Locked doors as gold dots between cells
                if cell.doors and cell.visibility != RoomVisibility.HIDDEN:
                    from maze import Direction as D, DoorState as DS
                    if D.EAST in cell.doors and cell.doors[D.EAST] == DS.LOCKED:
                        painter.setBrush(QBrush(QColor(200, 170, 50)))
                        painter.drawEllipse(
                            QPointF(x + cell_size, y + cell_size / 2), 2, 2
                        )
                    if D.SOUTH in cell.doors and cell.doors[D.SOUTH] == DS.LOCKED:
                        painter.setBrush(QBrush(QColor(200, 170, 50)))
                        painter.drawEllipse(
                            QPointF(x + cell_size / 2, y + cell_size), 2, 2
                        )
