"""Scene generators for KX98 display daemon."""

from dataclasses import dataclass, field
from typing import Optional
from PIL import Image

from kx98.sources.omp import OmpUsageItem
from kx98.sources.spotify import SpotifyData
from kx98.palette import MUSIC
from kx98.render import (
    render_animated_omp_bar,
    render_music_eq_frames,
)


@dataclass
class SceneContext:
    omp_list: list[OmpUsageItem] = field(default_factory=list)
    active_omp: Optional[OmpUsageItem] = None
    spotify: Optional[SpotifyData] = None


def scene_omp(ctx: SceneContext) -> Optional[list[Image.Image]]:
    """OMP usage scene: animated progress bar with prefix on left and percent on right."""
    item = ctx.active_omp
    if not item:
        if ctx.omp_list:
            item = ctx.omp_list[0]
        else:
            return None

    frames = render_animated_omp_bar(
        fraction=item.used_fraction,
        bar_color=item.color,
        prefix=item.prefix,
        pct_text=item.pct_text,
        num_frames=4,
    )
    return frames


def scene_music(ctx: SceneContext) -> Optional[list[Image.Image]]:
    """Music scene: centered Romanized Title/Artist with dancing audio EQ sound waves on both edges."""
    spot = ctx.spotify
    if not spot or not spot.playing or not spot.track:
        return None

    frames = render_music_eq_frames(
        spot.track.upper(),
        color=MUSIC,
    )
    return frames
