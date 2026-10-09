"""Universal macOS Now Playing source (Spotify, Apple Music, YouTube, Safari, Chrome, etc.)."""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import subprocess
from typing import Optional

from kx98.config import PROJECT_ROOT
from kx98.sources.spotify import SpotifySource

logger = logging.getLogger("kx98.sources.music")

NOWPLAYING_SWIFT = PROJECT_ROOT / "sources" / "nowplaying.swift"


@dataclass
class MusicData:
    playing: bool
    track: Optional[str] = None
    title: Optional[str] = None
    artist: Optional[str] = None


class MusicSource:
    def __init__(self):
        self.spotify_fallback = SpotifySource()
        self._last_data: Optional[MusicData] = None

    def poll(self) -> Optional[MusicData]:
        """
        Poll system Now Playing information from macOS MediaRemote.
        Covers all platforms: Spotify, Apple Music, YouTube (Safari/Chrome), Podcasts, VLC.
        """
        # 1. Primary: macOS MediaRemote via nowplaying.swift
        if NOWPLAYING_SWIFT.is_file():
            try:
                res = subprocess.run(
                    ["swift", str(NOWPLAYING_SWIFT)],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                if res.returncode == 0 and res.stdout.strip():
                    info = json.loads(res.stdout.strip())
                    if info.get("playing") and info.get("title"):
                        title = info.get("title", "").strip()
                        artist = info.get("artist", "").strip()
                        track_str = f"{title} - {artist}" if artist else title
                        data = MusicData(playing=True, track=track_str, title=title, artist=artist)
                        self._last_data = data
                        return data
            except Exception as e:
                logger.debug(f"MediaRemote query error: {e}")

        # 2. Fallback: Direct Spotify check
        spot = self.spotify_fallback.poll()
        if spot and spot.playing and spot.track:
            parts = spot.track.split(" - ", 1)
            title = parts[0].strip()
            artist = parts[1].strip() if len(parts) > 1 else ""
            data = MusicData(playing=True, track=spot.track, title=title, artist=artist)
            self._last_data = data
            return data

        return MusicData(playing=False, track=None)
