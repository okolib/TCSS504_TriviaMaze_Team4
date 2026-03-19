"""Waxworks: The Midnight Curse — Audio Manager

Provides ambient music loop and event sound effects via Qt Multimedia.
Gracefully degrades to silence when audio files are missing.
"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QSoundEffect

_ASSET_DIR = Path(__file__).parent / "assets" / "audio"
_MUSIC_VOLUME = 0.35
_EFFECT_VOLUME = 0.5

_STING_FILES = {
    "move":     "step.wav",
    "locked":   "locked.wav",
    "correct":  "correct.wav",
    "wrong":    "wrong.wav",
    "confront": "confront.wav",
    "won":      "won.wav",
    "lost":     "lost.wav",
}


class AudioManager:
    """Manages ambient music and short event stings."""

    def __init__(self):
        self._muted = False

        self._music_player = QMediaPlayer()
        self._music_output = QAudioOutput()
        self._music_output.setVolume(_MUSIC_VOLUME)
        self._music_player.setAudioOutput(self._music_output)

        music_path = _ASSET_DIR / "ambient.wav"
        if music_path.exists():
            self._music_player.setSource(QUrl.fromLocalFile(str(music_path)))
            self._music_player.setLoops(QMediaPlayer.Loops.Infinite)

        self._effects: dict[str, QSoundEffect] = {}
        for key, filename in _STING_FILES.items():
            path = _ASSET_DIR / filename
            if path.exists():
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(str(path)))
                effect.setVolume(_EFFECT_VOLUME)
                self._effects[key] = effect

    def start_music(self) -> None:
        """Begin the ambient loop (respects current mute state)."""
        if not self._muted:
            self._music_player.play()

    def stop_music(self) -> None:
        self._music_player.stop()

    def play(self, event: str) -> None:
        """Play a short event sting by name (e.g. 'move', 'correct')."""
        if self._muted:
            return
        effect = self._effects.get(event)
        if effect:
            effect.play()

    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns True if now muted."""
        self._muted = not self._muted
        self._apply_mute()
        return self._muted

    def set_muted(self, muted: bool) -> None:
        """Explicitly set mute state."""
        self._muted = muted
        self._apply_mute()

    @property
    def muted(self) -> bool:
        return self._muted

    def _apply_mute(self) -> None:
        if self._muted:
            self._music_output.setVolume(0.0)
        else:
            self._music_output.setVolume(_MUSIC_VOLUME)
            if self._music_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                self._music_player.play()
