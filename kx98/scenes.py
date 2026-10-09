"""Scene generators for KX98 display daemon."""

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
    active_omp: Optional[OmpUsageItem] = None
    spotify: Optional[SpotifyData] = None


def scene_all_omp(ctx: SceneContext) -> Optional[list[Image.Image]]:
    """
    Combine all active OMP models into a unified multi-frame hardware loop.
    Each model gets 2 frames (base + pulse highlight).
    The keyboard hardware loops through all models continuously with ZERO periodic USB writes!
    """
    if not ctx.omp_list:
        return None

    all_frames = []
    for item in ctx.omp_list:
        frames = render_animated_omp_bar(
            fraction=item.used_fraction,
            bar_color=item.color,
            prefix=item.prefix,
            pct_text=item.pct_text,
            num_frames=2,
        )
        all_frames.extend(frames)

    # Safe limit: max 8 frames
    return all_frames[:8]


def scene_omp(ctx: SceneContext) -> Optional[list[Image.Image]]:
    """Single OMP model animation."""
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


def scene_music_card(ctx: SceneContext, card_idx: int = 0) -> Optional[tuple[str, list[Image.Image]]]:
    """
    Return a single music card (Title or Artist) with dancing audio EQ sound waves on both edges.
    Returns (label_log, 4_frames).
    """
    spot = ctx.spotify
    if not spot or not spot.playing or not spot.track:
        return None

    cards = get_music_cards(spot.track.upper())
    if not cards:
        return None

    idx = card_idx % len(cards)
    card_type, card_text = cards[idx]
    frames = render_music_single_card(card_text, color=MUSIC)
    return (f"MUSIC: {card_type} '{card_text}'", frames)


def scene_music(ctx: SceneContext) -> Optional[list[Image.Image]]:
    """Default scene_music returning the first card."""
    res = scene_music_card(ctx, card_idx=0)
    return res[1] if res else None
