"""Main daemon service for KX98 display: smooth rotation between OMP stats and Spotify music."""

import logging
import signal
import time
from typing import Optional
from PIL import Image

from kx98.config import (
    INTERVAL_SPOTIFY,
    INTERVAL_OMP,
    PUSH_MODE,
    DWELL_OMP,
    MAX_LOG_LINES,
    LOG_PATH,
)
from kx98.hiddev import Display
from kx98.scenes import scene_omp, scene_music_card, SceneContext
from kx98.sources.omp import OmpSource
from kx98.sources.spotify import SpotifySource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kx98.daemon")

CARD_DWELL_SECONDS = DWELL_OMP  # 15.0s per card


def truncate_log_file(log_path=LOG_PATH, max_lines=MAX_LOG_LINES) -> None:
    """Auto-purge/truncate log file to retain only the most recent max_lines lines."""
    if not log_path.is_file():
        return
    try:
        lines = log_path.read_text(errors="replace").splitlines()
        if len(lines) > max_lines:
            kept = lines[-max_lines:]
            log_path.write_text("\n".join(kept) + "\n")
    except Exception:
        pass


class DisplayDaemon:
    def __init__(self):
        self.display = Display(push_mode=PUSH_MODE)
        self.omp_source = OmpSource()
        self.spotify_source = SpotifySource()

        self.ctx = SceneContext()
        self.running = True

        # Polling timestamps
        self.last_omp_poll = 0.0
        self.last_spot_poll = 0.0
        self.last_truncate_time = 0.0

        # Rotation state
        # Active sequence of card items: list of ("omp", index) or ("music", 0/1)
        self.rotation_items: list[tuple[str, int]] = []
        self.rotation_cursor = 0
        self.scene_start_time = 0.0

        # Spotify tracking
        self.last_spotify_playing = False
        self.last_spotify_track: Optional[str] = None

    def setup_signals(self):
        def _handle_signal(sig, frame):
            logger.info(f"Received termination signal ({sig}), shutting down cleanly...")
            self.running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def poll_sources(self, now: float, force: bool = False) -> tuple[bool, bool]:
        """
        Poll data sources.
        Returns (new_track, playback_toggled).
        """
        new_track = False
        playback_toggled = False

        if force or (now - self.last_spot_poll >= INTERVAL_SPOTIFY) or self.last_spot_poll == 0.0:
            self.ctx.spotify = self.spotify_source.poll()
            self.last_spot_poll = now
            is_playing = bool(self.ctx.spotify and self.ctx.spotify.playing and self.ctx.spotify.track)
            cur_track = self.ctx.spotify.track if is_playing else None

            if is_playing != self.last_spotify_playing:
                self.last_spotify_playing = is_playing
                playback_toggled = True

            if cur_track != self.last_spotify_track:
                self.last_spotify_track = cur_track
                if cur_track is not None:
                    new_track = True

        if force or (now - self.last_omp_poll >= INTERVAL_OMP) or self.last_omp_poll == 0.0:
            self.ctx.omp_list = self.omp_source.poll_all()
            self.last_omp_poll = now

        return new_track, playback_toggled

    def rebuild_rotation_items(self) -> None:
        """
        Construct sequence of cards:
        - OMP cards: [("omp", 0), ("omp", 1), ...] for all active models
        - Music cards (if Spotify is playing): [("music", 0), ("music", 1)] for Title and Artist
        """
        items: list[tuple[str, int]] = []

        # Add all active OMP accounts
        if self.ctx.omp_list:
            for idx in range(len(self.ctx.omp_list)):
                items.append(("omp", idx))

        # Add Spotify Title (0) and Artist (1) if playing
        if self.ctx.spotify and self.ctx.spotify.playing and self.ctx.spotify.track:
            items.append(("music", 0))  # Song Title card
            items.append(("music", 1))  # Artist Name card

        if not items:
            items = [("omp", 0)]

        self.rotation_items = items

    def push_frames(self, frames: list[Image.Image], label_log: str, delay_ms: int = 150) -> bool:
        """Push animation frames to the keyboard matrix."""
        if not frames:
            return False

        logger.info(f"Uploading [{label_log}] ({len(frames)} frames, delay {delay_ms}ms)...")
        try:
            ok = self.display.show(frames, delay_ms=delay_ms)
            if ok:
                self.scene_start_time = time.time()
            return ok
        except Exception as e:
            logger.error(f"Error flashing display: {e}")
            return False

    def show_current_card(self) -> bool:
        """Render and upload the card at rotation_cursor."""
        if not self.rotation_items:
            self.rebuild_rotation_items()

        self.rotation_cursor = self.rotation_cursor % len(self.rotation_items)
        card_type, card_idx = self.rotation_items[self.rotation_cursor]

        if card_type == "music":
            res = scene_music_card(self.ctx, card_idx=card_idx)
            if res:
                label_log, frames = res
                return self.push_frames(frames, label_log, delay_ms=150)
            # If music unavailable, fallback to OMP
            card_type = "omp"
            card_idx = 0

        if card_type == "omp":
            if self.ctx.omp_list:
                item_idx = card_idx % len(self.ctx.omp_list)
                self.ctx.active_omp = self.ctx.omp_list[item_idx]
                frames = scene_omp(self.ctx)
                if frames:
                    return self.push_frames(
                        frames,
                        f"OMP: {self.ctx.active_omp.prefix} {self.ctx.active_omp.pct_text}",
                        delay_ms=150,
                    )

        return False

    def advance_rotation(self) -> None:
        """Advance cursor to next card in rotation sequence."""
        self.rebuild_rotation_items()
        self.rotation_cursor = (self.rotation_cursor + 1) % len(self.rotation_items)
        self.show_current_card()

    def jump_to_music_title(self) -> None:
        """Immediately switch to Spotify Song Title card when a new track plays."""
        self.rebuild_rotation_items()
        for idx, (ctype, cidx) in enumerate(self.rotation_items):
            if ctype == "music" and cidx == 0:
                self.rotation_cursor = idx
                self.show_current_card()
                return
        self.show_current_card()

    def run(self):
        truncate_log_file()
        self.last_truncate_time = time.time()
        logger.info(f"Starting KX98 Display Daemon (Dwell={CARD_DWELL_SECONDS}s, OMP+Music rotation)...")
        self.setup_signals()

        # Connect to HID device
        while self.running:
            try:
                self.display.open()
                break
            except Exception as e:
                logger.warning(f"Could not open KX98 display: {e}. Retrying in 5s...")
                time.sleep(5.0)

        # Initial source poll & first push
        now = time.time()
        self.poll_sources(now, force=True)
        self.rebuild_rotation_items()
        self.show_current_card()

        # Main loop
        while self.running:
            now = time.time()
            new_track, playback_toggled = self.poll_sources(now)

            # If a new song starts playing: jump to Title card immediately
            if new_track:
                logger.info("New Spotify track detected, jumping to Title card...")
                self.jump_to_music_title()

            # If music stopped or started: update rotation sequence
            elif playback_toggled:
                self.rebuild_rotation_items()
                self.show_current_card()

            # Rotate when dwell time (15s) expires
            if now - self.scene_start_time >= CARD_DWELL_SECONDS:
                self.advance_rotation()

            # Periodic log file truncation (every 30 minutes)
            if now - self.last_truncate_time >= 1800.0:
                truncate_log_file()
                self.last_truncate_time = now

            time.sleep(1.0)

        logger.info("Daemon stopped. Leaving display state intact.")
        self.display.close()


def main():
    daemon = DisplayDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
