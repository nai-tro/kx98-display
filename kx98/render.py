"""Matrix rendering utilities for KX98 51x5 RGB matrix display."""

from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from kx98.config import COLS, ROWS
from kx98.font3x5 import get_char_matrix
from kx98.palette import BLACK, WHITE
from kx98.transliterate import to_latin

CJK_FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
THAI_FONT = "/System/Library/Fonts/Supplemental/Thonburi.ttc"


def create_blank_frame(color: tuple[int, int, int] = BLACK) -> Image.Image:
    """Create a new blank frame of size (COLS, ROWS)."""
    return Image.new("RGB", (COLS, ROWS), color)


def draw_text_3x5(
    img: Image.Image,
    text: str,
    x: int = 0,
    y: int = 0,
    color: tuple[int, int, int] = WHITE,
) -> int:
    """Draw 3x5 text onto image at position (x, y). Returns next available x."""
    cur_x = x
    for ch in text:
        matrix = get_char_matrix(ch)
        for row_idx in range(5):
            target_y = y + row_idx
            if 0 <= target_y < ROWS:
                for col_idx in range(3):
                    target_x = cur_x + col_idx
                    if 0 <= target_x < COLS:
                        if matrix[row_idx][col_idx]:
                            img.putpixel((target_x, target_y), color)
        cur_x += 4
    return cur_x


def render_animated_omp_bar(
    fraction: float,
    bar_color: tuple[int, int, int],
    prefix: str,       # e.g. "C", "G1", "X"
    pct_text: str,     # e.g. "15%", "67%"
    num_frames: int = 4,
) -> list[Image.Image]:
    """
    Layout on 51 columns:
    [Prefix]       [==== Sweeping Bar ====]       [Percent]
    Col 0..6       Col 8..35 (28px wide)          Col 37..50
    """
    frames = []

    # Calculate right-aligned percent text position
    # Each char is 4px (3px glyph + 1px space)
    pct_w = len(pct_text) * 4 - 1
    pct_x = COLS - pct_w  # e.g. 51 - 11 = 40

    # Prefix width
    prefix_w = len(prefix) * 4 - 1
    prefix_x = 0

    # Bar boundaries in between
    bar_start_x = prefix_x + prefix_w + 3  # e.g. 0 + 3 + 3 = 6 or 0 + 7 + 3 = 10
    bar_end_x = pct_x - 3                  # e.g. 40 - 3 = 37
    total_bar_w = max(10, bar_end_x - bar_start_x + 1)

    clamped_frac = max(0.0, min(1.0, fraction))
    fill_w = int(round(clamped_frac * total_bar_w)) if clamped_frac > 0 else 0

    for f in range(num_frames):
        img = create_blank_frame(BLACK)

        # Draw Prefix on left
        draw_text_3x5(img, prefix, x=prefix_x, y=0, color=WHITE)

        # Draw Percentage on right
        draw_text_3x5(img, pct_text, x=pct_x, y=0, color=WHITE)

        # Bar track on rows 1..3
        for x in range(bar_start_x, bar_end_x + 1):
            for y in (1, 3):
                img.putpixel((x, y), (25, 25, 25))
        img.putpixel((bar_start_x, 2), (25, 25, 25))
        img.putpixel((bar_end_x, 2), (25, 25, 25))

        # Filled progress in 100% pure model color (no white pixels)
        for x in range(bar_start_x, bar_start_x + fill_w):
            if x <= bar_end_x:
                for y in (1, 2, 3):
                    img.putpixel((x, y), bar_color)

        frames.append(img)

    return frames


def get_font_for_text(text: str, size: int = 7) -> ImageFont.FreeTypeFont:
    """Select font with proper glyph coverage for Thai, Japanese, CJK, or Latin."""
    if any("\u0E00" <= ch <= "\u0E7F" for ch in text):
        return ImageFont.truetype(THAI_FONT, size)
    return ImageFont.truetype(CJK_FONT, size)


def render_multilingual_strip(text: str, color: tuple[int, int, int]) -> Image.Image:
    """Render any Unicode text (Thai, Japanese, Latin) into a 5px-high strip."""
    font = get_font_for_text(text, size=7)
    dummy = Image.new("L", (1, 1), 0)
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, -2), text, font=font)
    text_w = max(COLS, bbox[2] - bbox[0] + 4)

    strip = Image.new("L", (text_w, ROWS), 0)
    draw = ImageDraw.Draw(strip)
    draw.text((0, -2), text, font=font, fill=255)

    rgb_strip = Image.new("RGB", (text_w, ROWS), BLACK)
    for x in range(text_w):
        for y in range(ROWS):
            val = strip.getpixel((x, y))
            if val > 50:
                factor = min(1.0, val / 180.0)
                rgb = (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))
                rgb_strip.putpixel((x, y), rgb)

    return rgb_strip


def paginate_text(text: str, max_chars: int = 12) -> list[str]:
    """Break text into word-aligned chunks of at most max_chars."""
    words = text.split()
    pages = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            pages.append(cur)
            cur = w
    if cur:
        pages.append(cur)
    return pages or [text[:max_chars]]


EQ_PATTERNS = [
    ([2, 5, 3], [3, 5, 2]),
    ([4, 2, 5], [5, 2, 4]),
    ([5, 4, 2], [2, 4, 5]),
    ([3, 5, 4], [4, 5, 3]),
]


def draw_eq_bar(img: Image.Image, col: int, height: int, color: tuple[int, int, int]):
    """Draw vertical audio equalizer level bar of height (1..5) from bottom row 4 upwards."""
    for r in range(height):
        y = (ROWS - 1) - r
        # Top tip pixel gets bright white-green highlight
        pixel_color = (200, 255, 200) if r == height - 1 else color
        img.putpixel((col, y), pixel_color)


def render_music_single_card(
    page_text: str,
    color: tuple[int, int, int] = (30, 215, 96),
) -> list[Image.Image]:
    """
    Render a single static text card (Title or Artist) with dancing 3-bar sound waves on both edges.
    Returns 4 animated frames where the audio equalizers bounce at 150ms rhythm.
    """
    center_start = 4
    center_end = 46
    center_w = center_end - center_start + 1

    text_w = len(page_text) * 4 - 1
    text_x = center_start + max(0, (center_w - text_w) // 2)

    frames = []
    for left_h, right_h in EQ_PATTERNS:
        img = create_blank_frame(BLACK)
        for i, h in enumerate(left_h):
            draw_eq_bar(img, i, h, color)
        for i, h in enumerate(right_h):
            draw_eq_bar(img, 48 + i, h, color)
        draw_text_3x5(img, page_text, x=text_x, y=0, color=WHITE)
        frames.append(img)

    return frames


def get_music_cards(text: str, max_chars: int = 10) -> list[tuple[str, str]]:
    """
    Parse and paginate track into discrete Romanized Latin cards.
    Returns list of (type, text), e.g. [('TITLE', 'SUBTITLE'), ('ARTIST', 'OFFICIAL HIG')].
    """
    latin = to_latin(text)
    if " - " in latin:
        parts = latin.split(" - ", 1)
        title_raw = parts[0].strip()
        artist_raw = parts[1].strip()
        title_pages = paginate_text(title_raw, max_chars=max_chars)
        artist_pages = paginate_text(artist_raw, max_chars=max_chars)
        cards = []
        for tp in title_pages[:2]:
            cards.append(("TITLE", tp))
        for ap in artist_pages[:1]:
            cards.append(("ARTIST", ap))
        return cards
    else:
        pages = paginate_text(latin, max_chars=max_chars)
        return [("TITLE", p) for p in pages[:2]]
