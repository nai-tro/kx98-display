"""Scene generators for KX98 display daemon using hardware-side looping."""

from dataclasses import dataclass, field
from typing import Optional
from PIL import Image

from kx98.sources.omp import OmpUsageItem
from kx98.sources.spotify import SpotifyData
from kx98.palette import MUSIC
from kx98.render import (
    render_animated_omp_bar,
    render_music_single_card,
    get_music_cards,
)


@dataclass
class SceneContext:
    omp_list: list[OmpUsageItem] = field(default_factory=list)
    spotify: Optional[SpotifyData] = None


def scene_idle_omp_loop(ctx: SceneContext) -> Optional[list[Image.Image]]:
    """
    Generate an animation containing all active OMP models.
    Each model gets 1 static frame with a pulsing accent.
    With delay_ms=3000 (3s per model), the keyboard loops all models in hardware
    with ZERO host USB writes during your work session!
    """
    if not ctx.omp_list:
        return None

    frames = []
    for item in ctx.omp_list:
        # Generate 1 frame per model
        f = render_animated_omp_bar(
            fraction=item.used_fraction,
            bar_color=item.color,
            prefix=item.prefix,
            pct_text=item.pct_text,
            num_frames=1,
        )[0]
        frames.append(f)

    # Safe limit: max 4 models
    return frames[:4]


def scene_music_and_omp_loop(ctx: SceneContext) -> Optional[list[Image.Image]]:
    """
    When Spotify is playing, generate a unified 4-frame animation containing:
    - Frame 0: Song Title (holds 3.5s) with dual sound wave equalizers
    - Frame 1: Artist Name (holds 3.5s) with dual sound wave equalizers
    - Frame 2: Top OMP model 1 (holds 3.5s)
    - Frame 3: Top OMP model 2 (holds 3.5s, e.g. Claude or Gemini)
    The keyboard loops through Music AND OMP continuously in hardware with ZERO host writes!
    """
    spot = ctx.spotify
    if not spot or not spot.playing or not spot.track:
        return None

    frames = []

    # 1. Music cards (Title + Artist)
    cards = get_music_cards(spot.track.upper())
    for card_type, card_text in cards[:2]:
        # 1 frame per music card
        f = render_music_single_card(card_text, color=MUSIC)[0]
        frames.append(f)

    # 2. OMP models (top 2 active models)
    if ctx.omp_list:
        for item in ctx.omp_list[:2]:
            f = render_animated_omp_bar(
                fraction=item.used_fraction,
                bar_color=item.color,
                prefix=item.prefix,
                pct_text=item.pct_text,
                num_frames=1,
            )[0]
            frames.append(f)

    return frames
