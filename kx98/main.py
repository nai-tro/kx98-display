"""Main event-driven daemon service for KX98 display.

Zero periodic flash writes:
- When Spotify plays: flashes track animation ONCE when track starts. Loops in hardware for the full song.
- When Spotify stops: flashes unified multi-model OMP loop ONCE. Loops in hardware for the work session.
- Only flashes when content actually changes (new track, playback toggle, or OMP % update).
- Eliminates TFT 'loading' blinks and periodic screen resets completely.
"""

import logging
import signal
import time
from typing import Optional

from kx98.config import (
    INTERVAL_SPOTIFY,
    INTERVAL_OMP,
    PUSH_MODE,
    MAX_LOG_LINES,
    LOG_PATH,
)
from kx98.hiddev import Display
from kx98.scenes import scene_all_omp, scene_music_card, SceneContext
from kx98.sources.omp import OmpSource
from kx98.sources.spotify import SpotifySource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kx98.daemon")


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

        # State tracking
        self.last_spotify_playing: Optional[bool] = None
        self.last_spotify_track: Optional[str] = None
        self.last_omp_sig: Optional[str] = None

    def setup_signals(self):
        def _handle_signal(sig, frame):
            logger.info(f"Received termination signal ({sig}), shutting down cleanly...")
            self.running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def poll_sources(self, now: float, force: bool = False) -> None:
        """Poll Spotify and OMP data sources."""
        if force or (now - self.last_spot_poll >= INTERVAL_SPOTIFY) or self.last_spot_poll == 0.0:
            self.ctx.spotify = self.spotify_source.poll()
            self.last_spot_poll = now

        if force or (now - self.last_omp_poll >= INTERVAL_OMP) or self.last_omp_poll == 0.0:
            self.ctx.omp_list = self.omp_source.poll_all()
            self.last_omp_poll = now

    def update_display(self) -> None:
        """Check if displayed content changed and push flash animation if needed."""
        is_playing = bool(self.ctx.spotify and self.ctx.spotify.playing and self.ctx.spotify.track)
        cur_track = self.ctx.spotify.track if is_playing else None

        # Case 1: Spotify state or track changed
        if is_playing != self.last_spotify_playing or (is_playing and cur_track != self.last_spotify_track):
            self.last_spotify_playing = is_playing
            self.last_spotify_track = cur_track

            if is_playing:
                card = scene_music_card(self.ctx, card_idx=0)
                if card:
                    label_log, frames = card
                    logger.info(f"Spotify playing: uploading [{label_log}]...")
                    self.display.show(frames, delay_ms=150)
                return
            else:
                logger.info("Spotify stopped: reverting to unified OMP overview...")
                frames = scene_all_omp(self.ctx)
                if frames:
                    self.display.show(frames, delay_ms=250)
                return

        # Case 2: Not playing music -> check if OMP stats changed
        if not is_playing and self.ctx.omp_list:
            omp_sig = "-".join(f"{it.prefix}:{it.pct_text}" for it in self.ctx.omp_list)
            if omp_sig != self.last_omp_sig:
                self.last_omp_sig = omp_sig
                logger.info(f"OMP stats updated ({omp_sig}), uploading unified hardware loop...")
                frames = scene_all_omp(self.ctx)
                if frames:
                    self.display.show(frames, delay_ms=250)

    def run(self):
        truncate_log_file()
        self.last_truncate_time = time.time()
        logger.info(f"Starting KX98 Display Daemon (Event-driven, no periodic flash writes)...")
        self.setup_signals()

        # Connect to HID device
        while self.running:
            try:
                self.display.open()
                break
            except Exception as e:
                logger.warning(f"Could not open KX98 display: {e}. Retrying in 5s...")
                time.sleep(5.0)

        # Initial source poll & first update
        now = time.time()
        self.poll_sources(now, force=True)
        self.update_display()

        # Main loop (checks state every 1s, writes ONLY on change)
        while self.running:
            now = time.time()
            self.poll_sources(now)
            self.update_display()

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
