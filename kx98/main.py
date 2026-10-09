"""Main daemon service for KX98 display with 15s music cards and instant reconnect sync."""

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

CARD_DWELL_SECONDS = DWELL_OMP  # 15.0s per card (both OMP and Music Title/Artist)


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

        # Rotation state
        self.omp_cursor = 0
        self.music_card_idx = 0
        self.current_mode = "omp"  # "omp" or "music"
        self.scene_start_time = 0.0
        self.last_truncate_time = 0.0

        # Content change triggers
        self.last_spotify_track: Optional[str] = None

    def setup_signals(self):
        def _handle_signal(sig, frame):
            logger.info(f"Received termination signal ({sig}), shutting down cleanly...")
            self.running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def poll_sources(self, now: float, force: bool = False) -> bool:
        """Poll data sources. Returns True if a new Spotify song started playing."""
        new_track = False

        if force or (now - self.last_spot_poll >= INTERVAL_SPOTIFY) or self.last_spot_poll == 0.0:
            self.ctx.spotify = self.spotify_source.poll()
            self.last_spot_poll = now
            cur_track = self.ctx.spotify.track if (self.ctx.spotify and self.ctx.spotify.playing) else None
            if cur_track != self.last_spotify_track:
                self.last_spotify_track = cur_track
                if cur_track is not None:
                    new_track = True

        if force or (now - self.last_omp_poll >= INTERVAL_OMP) or self.last_omp_poll == 0.0:
            self.ctx.omp_list = self.omp_source.poll_all()
            self.last_omp_poll = now

        return new_track

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

    def advance_rotation(self) -> None:
        """Rotate through OMP providers and 15s Music Title/Artist cards."""
        spotify_active = bool(self.ctx.spotify and self.ctx.spotify.playing and self.ctx.spotify.track)

        if not self.ctx.omp_list:
            self.ctx.omp_list = self.omp_source.poll_all()

        num_omp = len(self.ctx.omp_list)

        # Rotation state machine
        if self.current_mode == "music":
            # Advance music card (Title -> Artist)
            self.music_card_idx += 1
            if self.music_card_idx >= 2:
                # Finished both Title & Artist -> switch back to OMP
                self.current_mode = "omp"
                self.omp_cursor = 0
                self.music_card_idx = 0
        else:
            # In OMP mode: advance to next model
            self.omp_cursor += 1
            if self.omp_cursor >= num_omp:
                if spotify_active:
                    self.current_mode = "music"
                    self.music_card_idx = 0
                else:
                    self.omp_cursor = 0

        # Execute Music
        if self.current_mode == "music" and spotify_active:
            card = scene_music_card(self.ctx, card_idx=self.music_card_idx)
            if card:
                label_log, frames = card
                self.push_frames(frames, label_log, delay_ms=150)
                return

        # Execute OMP
        self.current_mode = "omp"
        if self.ctx.omp_list:
            self.omp_cursor = self.omp_cursor % len(self.ctx.omp_list)
            self.ctx.active_omp = self.ctx.omp_list[self.omp_cursor]
            frames = scene_omp(self.ctx)
            if frames:
                self.push_frames(
                    frames,
                    f"OMP: {self.ctx.active_omp.prefix} {self.ctx.active_omp.pct_text}",
                    delay_ms=150,
                )

    def run(self):
        truncate_log_file()
        self.last_truncate_time = time.time()
        logger.info(f"Starting KX98 Display Daemon (Dwell={CARD_DWELL_SECONDS}s per card, OMP sync={INTERVAL_OMP}s)...")
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
        self.advance_rotation()

        # Main loop
        while self.running:
            now = time.time()
            new_track = self.poll_sources(now)

            # If a new song starts playing, immediately switch to Title card for 15s
            if new_track and self.ctx.spotify and self.ctx.spotify.playing:
                logger.info("New Spotify track detected, switching immediately to Title card...")
                self.current_mode = "music"
                self.music_card_idx = 0
                card = scene_music_card(self.ctx, card_idx=0)
                if card:
                    self.push_frames(card[1], card[0], delay_ms=150)

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
