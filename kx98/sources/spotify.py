"""Spotify data source polling playback status via osascript."""

from dataclasses import dataclass
import logging
import subprocess
from typing import Optional

logger = logging.getLogger("kx98.sources.spotify")

SPOTIFY_SCRIPT = """
tell application "Spotify"
    if player state is playing then
        return (name of current track) & " - " & (artist of current track)
    else
        return ""
    end if
end tell
"""


@dataclass
class SpotifyData:
    playing: bool
    track: Optional[str] = None


class SpotifySource:
    def __init__(self):
        self._last_data: Optional[SpotifyData] = None

    def is_spotify_process_running(self) -> bool:
        """Fast (10ms) process check before invoking AppleScript."""
        res = subprocess.run(
            ["pgrep", "-ix", "Spotify"],
            capture_output=True,
            timeout=1,
        )
        return res.returncode == 0

    def poll(self) -> Optional[SpotifyData]:
        try:
            if not self.is_spotify_process_running():
                return None

            res = subprocess.run(
                ["osascript", "-e", SPOTIFY_SCRIPT],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if res.returncode != 0:
                logger.debug(f"osascript returned error: {res.stderr}")
                return None

            out = res.stdout.strip()
            if not out:
                return None

            data = SpotifyData(playing=True, track=out)
            self._last_data = data
            return data

        except Exception as e:
            logger.debug(f"Error polling Spotify: {e}")
            return None
