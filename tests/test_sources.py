"""Tests for data sources (spotify, omp)."""

from kx98.sources.spotify import SpotifySource
from kx98.sources.omp import OmpSource


def test_spotify_source():
    src = SpotifySource()
    data = src.poll()
    if data:
        assert data.playing is True
        assert isinstance(data.track, str)


def test_omp_source():
    src = OmpSource()
    data = src.poll()
    if data:
        assert 0.0 <= data.used_fraction <= 1.0
        assert len(data.pct_text) > 0
        assert len(data.prefix) > 0
        assert len(data.color) == 3
