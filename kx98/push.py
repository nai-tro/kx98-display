"""Single-shot display pusher CLI for manual smoke tests."""

import argparse
import sys
from pathlib import Path
from PIL import Image

from kx98.config import COLS, ROWS, PUSH_MODE
from kx98.hiddev import Display


COLOR_MAP = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "amber": (255, 170, 0),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "yellow": (255, 255, 0),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
}


def parse_hex_color(hex_str: str) -> tuple[int, int, int]:
    s = hex_str.lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Invalid hex color: {hex_str}")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def main():
    parser = argparse.ArgumentParser(description="Push image or solid color to KX98 display")
    parser.add_argument(
        "--solid",
        type=str,
        help="Solid color: red, green, blue, amber, white, black, or #RRGGBB",
    )
    parser.add_argument("--image", type=str, help="Path to single image file")
    parser.add_argument("--frames", type=str, help="Directory containing numbered PNG/BMP frames")
    parser.add_argument(
        "--mode",
        choices=["live", "flash"],
        default=PUSH_MODE,
        help="Push mode (default: from config)",
    )
    parser.add_argument("--delay", type=int, default=100, help="Frame delay in ms for animation")

    args = parser.parse_args()

    frames = []

    if args.solid:
        c_str = args.solid.lower()
        rgb = COLOR_MAP.get(c_str) or parse_hex_color(c_str)
        img = Image.new("RGB", (COLS, ROWS), rgb)
        frames = [img]
    elif args.image:
        p = Path(args.image)
        if not p.is_file():
            print(f"Error: image not found: {p}", file=sys.stderr)
            sys.exit(1)
        img = Image.open(p).convert("RGB").resize((COLS, ROWS))
        frames = [img]
    elif args.frames:
        d = Path(args.frames)
        if not d.is_dir():
            print(f"Error: directory not found: {d}", file=sys.stderr)
            sys.exit(1)
        files = sorted(
            [f for f in d.iterdir() if f.suffix.lower() in (".png", ".bmp", ".jpg", ".jpeg")]
        )
        if not files:
            print(f"Error: no images found in {d}", file=sys.stderr)
            sys.exit(1)
        for f in files:
            frames.append(Image.open(f).convert("RGB").resize((COLS, ROWS)))
    else:
        parser.print_help()
        sys.exit(1)

    print(f"Pushing {len(frames)} frame(s) using {args.mode} mode...")
    display = Display(push_mode=args.mode)
    try:
        display.open()
        ok = display.show(frames, delay_ms=args.delay)
        if ok:
            print("Successfully pushed to display.")
        else:
            print("Failed to push to display.", file=sys.stderr)
            sys.exit(1)
    finally:
        display.close()


if __name__ == "__main__":
    main()
