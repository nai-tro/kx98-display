"""Unit tests verifying frame and animation encoders against captured ground-truth fixtures."""

import json
from pathlib import Path
import pytest
from PIL import Image

from kx98.encode import encode_frame, encode_animation
from kx98.config import FIXTURES_DIR, COLS, ROWS


def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


def test_solid_red_encode():
    fixture = load_fixture("solid_red")
    img = Image.new("RGB", (COLS, ROWS), (255, 0, 0))

    # 1. Live streaming packets (cmd 66)
    live_pkts = encode_frame(img)
    expected_live = [bytes.fromhex(p[2]) for p in fixture["live_packets"]]
    assert len(live_pkts) == len(expected_live)
    for i, (actual, expected) in enumerate(zip(live_pkts, expected_live)):
        assert actual == expected, f"Live packet #{i} mismatch"

    # 2. Flash animation packet (cmd 65)
    flash_pkts = encode_animation([img], delay_ms=100)
    expected_flash = [bytes.fromhex(p[2]) for p in fixture["flash_packets"]]
    assert len(flash_pkts) == len(expected_flash)
    for i, (actual, expected) in enumerate(zip(flash_pkts, expected_flash)):
        assert actual == expected, f"Flash packet #{i} mismatch"


def test_solid_green_encode():
    fixture = load_fixture("solid_green")
    img = Image.new("RGB", (COLS, ROWS), (0, 255, 0))

    # 1. Live streaming packets (cmd 66)
    live_pkts = encode_frame(img)
    expected_live = [bytes.fromhex(p[2]) for p in fixture["live_packets"]]
    assert len(live_pkts) == len(expected_live)
    for i, (actual, expected) in enumerate(zip(live_pkts, expected_live)):
        assert actual == expected, f"Live packet #{i} mismatch"

    # 2. Flash animation packet (cmd 65)
    flash_pkts = encode_animation([img], delay_ms=100)
    expected_flash = [bytes.fromhex(p[2]) for p in fixture["flash_packets"]]
    assert len(flash_pkts) == len(expected_flash)
    for i, (actual, expected) in enumerate(zip(flash_pkts, expected_flash)):
        assert actual == expected, f"Flash packet #{i} mismatch"


def test_corner_white_encode():
    fixture = load_fixture("corner_white")
    img = Image.new("RGB", (COLS, ROWS), (0, 0, 0))
    img.putpixel((0, 0), (255, 255, 255))

    # 1. Live streaming packets (cmd 66)
    live_pkts = encode_frame(img)
    expected_live = [bytes.fromhex(p[2]) for p in fixture["live_packets"]]
    assert len(live_pkts) == len(expected_live)
    for i, (actual, expected) in enumerate(zip(live_pkts, expected_live)):
        assert actual == expected, f"Live packet #{i} mismatch"

    # 2. Flash animation packet (cmd 65)
    flash_pkts = encode_animation([img], delay_ms=100)
    expected_flash = [bytes.fromhex(p[2]) for p in fixture["flash_packets"]]
    assert len(flash_pkts) == len(expected_flash)
    for i, (actual, expected) in enumerate(zip(flash_pkts, expected_flash)):
        assert actual == expected, f"Flash packet #{i} mismatch"
