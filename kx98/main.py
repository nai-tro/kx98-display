"""Main daemon service for KX98 display using pure hardware-side looping.

Eliminates periodic host flash writes completely:
- When music plays: uploads [Title (3.5s), Artist (3.5s), OMP1 (3.5s), OMP2 (3.5s)] ONCE when track starts.
  The keyboard loops music and OMP continuously in hardware with zero host writes and zero flashing!
- When music stops: uploads [OMP1 (3s), OMP2 (3s), OMP3 (3s), OMP4 (3s)] ONCE.
  The keyboard loops all models continuously in hardware with zero host writes and zero flashing!
- Only writes to USB when a new song starts, music pauses/resumes, or token % changes.
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
from kx98.scenes import scene_music_and_omp_loop, scene_idle_omp_loop, SceneContext
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

        # State signatures to trigger updates ONLY on change
        self.last_spotify_playing: Optional[bool] = None
        self.last_spotify_track: Optional[str] = None
        self.last_omp_signature: Optional[str] = None

    def setup_signals(self):
        def _handle_signal(sig, frame):
            logger.info(f"Received termination signal ({sig}), shutting down cleanly...")
            self.running = False

        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    def poll_sources(self, now: float, force: bool = False) -> None:
        """Poll Spotify (every 3s) and OMP (every 20s)."""
        if force or (now - self.last_spot_poll >= INTERVAL_SPOTIFY) or self.last_spot_poll == 0.0:
            self.ctx.spotify = self.spotify_source.poll()
            self.last_spot_poll = now

        if force or (now - self.last_omp_poll >= INTERVAL_OMP) or self.last_omp_poll == 0.0:
            self.ctx.omp_list = self.omp_source.poll_all()
            self.last_omp_poll = now

    def update_hardware_loop(self) -> None:
        """Upload hardware animation only when content actually changes."""
        is_playing = bool(self.ctx.spotify and self.ctx.spotify.playing and self.ctx.spotify.track)
        cur_track = self.ctx.spotify.track if is_playing else None
        omp_sig = "-".join(f"{it.prefix}:{it.pct_text}" for it in self.ctx.omp_list)

        needs_upload = False
        log_reason = ""

        # Trigger 1: Spotify playback state changed (started or stopped)
        if is_playing != self.last_spotify_playing:
            self.last_spotify_playing = is_playing
            self.last_spotify_track = cur_track
            needs_upload = True
            log_reason = f"Spotify {'started' if is_playing else 'stopped'}"

        # Trigger 2: Spotify track changed
        elif is_playing and cur_track != self.last_spotify_track:
            self.last_spotify_track = cur_track
            needs_upload = True
            log_reason = f"Track changed to '{cur_track}'"

        # Trigger 3: OMP usage changed
        elif not is_playing and omp_sig != self.last_omp_signature:
            self.last_omp_signature = omp_sig
            needs_upload = True
            log_reason = f"OMP usage updated ({omp_sig})"

        if not needs_upload:
            return

        # Build and push the appropriate hardware animation
        if is_playing:
            frames = scene_music_and_omp_loop(self.ctx)
            if frames:
                logger.info(f"Uploading Music+OMP loop ({log_reason}, {len(frames)} frames, 3.5s hold)...")
                self.display.show(frames, delay_ms=3500)
        else:
            frames = scene_idle_omp_loop(self.ctx)
            if frames:
                logger.info(f"Uploading Idle OMP loop ({log_reason}, {len(frames)} frames, 3.0s hold)...")
                self.display.show(frames, delay_ms=3000)

    def run(self):
        truncate_log_file()
        self.last_truncate_time = time.time()
        logger.info("Starting KX98 Display Daemon (Pure Hardware Looping, Zero Periodic Flashing)...")
        self.setup_signals()

        # Connect to HID device
        while self.running:
            try:
                self.display.open()
                break
            except Exception as e:
                logger.warning(f"Could not open KX98 display: {e}. Retrying in 5s...")
                time.sleep(5.0)

        # Initial source poll & first hardware flash
        now = time.time()
        self.poll_sources(now, force=True)
        self.update_hardware_loop()

        # Main loop: checks state every 1s, writes ONLY when content changes!
        while self.running:
            now = time.time()
            self.poll_sources(now)
            self.update_hardware_loop()

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
