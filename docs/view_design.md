# Waxworks: The Midnight Curse — View Design Spec

> Creative playbook for `view.py` · All ASCII mockups, text, and rendering details.

---

## 1. Welcome Banner

```
╔══════════════════════════════════════════════════════════════╗
║              WAXWORKS: THE MIDNIGHT CURSE                   ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   The doors slam shut behind you.                            ║
║   The Grand Hall of History stretches into darkness.         ║
║   Your hand... is it shinier than before?                    ║
║                                                              ║
║   Find the exit before the Curse Meter reaches 100%          ║
║   or become the newest exhibit — forever.                    ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  Commands: move <north|south|east|west>  answer <A|B|C>     ║
║            save  load  map  quit                             ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 2. Curse Meter — Melting Candle

The candle shrinks as the curse rises. Use ANSI colors: green (safe), yellow (warning), red (danger).

```
 Curse: 0%           Curse: 20%          Curse: 40%          Curse: 80%          Curse: 100%
    )                   )                   )                                    
   (  )                (  )                (  )                                  
  (    )              (    )                                                     
 │ ░░░░░ │           │ ░░░░░ │           │ ░░░░░ │           │ ░░░░░ │          ┌─────────┐
 │ ░░░░░ │           │ ░░░░░ │           │▓▓▓▓▓▓▓│           │▓▓▓▓▓▓▓│          │▓▓▓▓▓▓▓▓▓│
 │ ░░░░░ │           │▓▓▓▓▓▓▓│           │▓▓▓▓▓▓▓│           │▓▓▓▓▓▓▓│          │▓▓▓▓▓▓▓▓▓│
 │ ░░░░░ │           │▓▓▓▓▓▓▓│           │▓▓▓▓▓▓▓│           │▓▓▓▓▓▓▓│          │▓▓▓▓▓▓▓▓▓│
 └───────┘           └───────┘           └───────┘           └───────┘          └─────────┘
  You're fine.     Fingers stiff.      Arm won't bend.     Legs heavy.          YOU ARE WAX.
```

### Progressive dread messages

| Curse Level | Body message |
|-------------|-------------|
| 0 | *"You feel normal. For now."* |
| 20 | *"Your fingers feel stiff and waxy."* |
| 40 | *"Your arm won't bend. The curse is spreading."* |
| 60 | *"Your joints are seizing. The curse tightens its grip."* |
| 80 | *"You can barely move your legs. Time is running out."* |
| 100 | *"Your eyes glaze over. You cannot move. The curse is complete."* |

---

## 3. Zone Flavor Text

Each zone has an entrance description and ambient details.

### Art Gallery (Leonardo da Vinci)
- **Entrance:** *"Paint-stained easels line the walls. In the center, a figure hunches over a canvas, brush frozen mid-stroke..."*
- **Ambient:** *"The Mona Lisa's eyes seem to follow you across the room."*

### American History Wing (Abraham Lincoln)
- **Entrance:** *"A tall figure in a stovepipe hat stands behind a podium. The air smells of old parchment and gunpowder..."*
- **Ambient:** *"A brass eagle gleams on the wall. Dust motes drift through streaks of moonlight."*

### Ancient History Hall (Cleopatra)
- **Entrance:** *"Sand crunches under your feet. Hieroglyphs flicker in torchlight. A queen sits on a gilded throne..."*
- **Ambient:** *"The faint hiss of a serpent echoes from somewhere in the shadows."*

### Science Lab (Albert Einstein)
- **Entrance:** *"Beakers bubble softly on a long bench. A chalkboard covered in equations glows faintly. A wild-haired figure adjusts his spectacles..."*
- **Ambient:** *"A clock on the wall ticks at an impossible rate — faster, slower, faster."*

### Library (William Shakespeare)
- **Entrance:** *"Leather-bound books tower to the ceiling. A quill scratches across parchment by itself. A man in an Elizabethan ruff looks up..."*
- **Ambient:** *"Pages rustle though there is no wind."*

### Map Room (Christopher Columbus)
- **Entrance:** *"Yellowed maps cover every surface. The compass needle spins wildly. A man in explorer's garb traces a route across the Atlantic..."*
- **Ambient:** *"The smell of salt air and old rope hangs in the room."*

### Corridors (no figure)
- **Empty:** *"The hallway stretches into shadow. Your footsteps echo off cold marble."*
- **Dead end:** *"The passage ends abruptly. Dust and cobwebs. Nothing here but darkness."*

---

## 4. Wax Figure Confrontations

When the player enters a trivia room with an undefeated figure:

```
┌──────────────────────────────────────────────────┐
│                                                  │
│   A wax figure stirs...                          │
│                                                  │
│   The eyes of LEONARDO DA VINCI snap open.       │
│   Wax cracks along his jaw as he confronts you:  │
│                                                  │
│   "I painted the most famous woman in the        │
│    world — no eyebrows, mysterious smile.        │
│    Name the painting."                           │
│                                                  │
│   A) The Last Supper                             │
│   B) The Mona Lisa                               │
│   C) Starry Night                                │
│                                                  │
└──────────────────────────────────────────────────┘
```

### Answer feedback

**Correct:**
```
  ✓ The figure is defeated!
  The curse recedes. The gate grinds open.
  The figure nods slowly and returns to stillness.
```

**Wrong:**
```
  ✗ Wrong!
  The curse tightens its grip... you feel your fingers stiffening.
  A grinding of stone. The gate stays sealed.
  Curse Level: [██████░░░░] 60
```

---

## 5. Fog of War Map

### Symbol legend

| Symbol | Meaning | ANSI Color |
|--------|---------|------------|
| `★` | Your position (current room) | BOLD + WHITE |
| `░` | Visited room | DIM |
| `··` | Visible room (adjacent, not entered) | NORMAL |
| `▓▓` | Hidden room (unexplored) | DIM + DARK |
| `──` | Open passage (horizontal) | GREEN |
| `│` | Open passage (vertical) | GREEN |
| `═╡` | Locked gate (horizontal) | YELLOW |
| `╞═` | Locked gate (horizontal) | YELLOW |
| `🗿` | Wax figure room (visited) | BOLD |
| `EXIT` | Exit room (if visible) | GREEN + BOLD |

### Example renders

**Early game (few rooms explored):**
```
  THE GRAND HALL OF HISTORY
    0     1     2     3     4
  ┌─────┬─────┬─────┬─────┬─────┐
0 │  ★  │ ··  │ ▓▓  │ ▓▓  │ ▓▓  │
  │     ──    │     │     │     │
  ├─────┼─────┼─────┼─────┼─────┤
1 │ ··  │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │
  │     │     │     │     │     │
  ├─────┼─────┼─────┼─────┼─────┤
2 │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │
  │     │     │     │     │     │
  ├─────┼─────┼─────┼─────┼─────┤
3 │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │
  │     │     │     │     │     │
  ├─────┼─────┼─────┼─────┼─────┤
4 │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │
  └─────┴─────┴─────┴─────┴─────┘
```

**Mid game (several rooms explored, a figure defeated):**
```
  THE GRAND HALL OF HISTORY
    0     1     2     3     4
  ┌─────┬─────┬─────┬─────┬─────┐
0 │  ░  ── ░  ── ░  │ ▓▓  │ ▓▓  │
  ├─────┼─────┼─────┼─────┼─────┤
1 │ ░🗿 ── ★  ══╡L│ ▓▓  │ ▓▓  │
  ├─────┼─────┼─────┼─────┼─────┤
2 │ ▓▓  │ ··  │ ▓▓  │ ▓▓  │ ▓▓  │
  ├─────┼─────┼─────┼─────┼─────┤
3 │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │
  ├─────┼─────┼─────┼─────┼─────┤
4 │ ▓▓  │ ▓▓  │ ▓▓  │ ▓▓  │EXIT │
  └─────┴─────┴─────┴─────┴─────┘
```

---

## 6. Game Over — Turning to Wax

A three-phase sequence:

### Phase 1: Transformation
```
  Your skin hardens...
  Your joints lock...
  Your eyes glaze over...
```

### Phase 2: Museum plaque
```
  ┌─────────────────────────────────────┐
  │                                     │
  │   "THE NEWEST EXHIBIT"              │
  │                                     │
  │    Name:  Unknown Explorer          │
  │    Date:  March 1, 2026             │
  │    Cause: Curiosity                 │
  │                                     │
  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
  │    ░░░  PERMANENT  COLLECTION  ░░░  │
  │    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │
  │                                     │
  └─────────────────────────────────────┘
```

### Phase 3: Game over banner
```
  ╔═══════════════════════════════════════╗
  ║          === GAME OVER ===            ║
  ╠═══════════════════════════════════════╣
  ║  Rooms explored:   5/25              ║
  ║  Figures defeated:  1/6              ║
  ║  Curse Level:      100               ║
  ╚═══════════════════════════════════════╝
```

---

## 7. Victory — Dawn Breaks

```
  The last gate opens...

  Warm orange light floods the hallway.
  The wax on your skin cracks and falls away.
  Behind you, the figures slump — lifeless once more.

  ╔═══════════════════════════════════════╗
  ║     THE CURSE IS BROKEN.              ║
  ║     Dawn breaks over the museum.      ║
  ║     You are free.                     ║
  ╠═══════════════════════════════════════╣
  ║  Rooms explored:  18/25              ║
  ║  Figures defeated: 6/6               ║
  ║  Curse Level:     50                ║
  ╚═══════════════════════════════════════╝
```

---

## 8. ANSI Color Palette

```python
class Colors:
    # Reset
    RESET   = "\033[0m"

    # Game states
    DANGER  = "\033[91m"   # Red — wrong answer, high curse, game over
    SUCCESS = "\033[92m"   # Green — correct answer, open doors, victory
    WARNING = "\033[93m"   # Yellow — locked gates, curse warnings
    INFO    = "\033[96m"   # Cyan — room descriptions, figure speech

    # Map rendering
    DIM     = "\033[2m"    # Dimmed — visited rooms, corridors
    BOLD    = "\033[1m"    # Bold — current room, headers, figures
    HIDDEN  = "\033[90m"   # Dark gray — unexplored fog

    @classmethod
    def disable(cls):
        """Fallback for terminals without ANSI support."""
        for attr in vars(cls):
            if not attr.startswith('_') and attr != 'disable':
                setattr(cls, attr, "")
```

---

## 9. Ambient / Idle Text

If the player pauses, cycle through atmospheric messages:

- *"Somewhere in the distance, a clock chimes midnight."*
- *"The floorboards creak behind you. But when you turn... nothing."*
- *"A candle flickers and goes out."*
- *"You hear the faint scraping of wax on stone."*
- *"The air grows colder."*

---

## 10. Command Prompt

The prompt itself should be themed:

```
  🕯 What do you do? >
```

Or without emoji:
```
  [Curse: 20] >
```

---

*View Design Spec · Waxworks: The Midnight Curse · Authors: Mario, Megan*
