"""Unit tests verifying transport profiles, framing, and automatic fallback."""

import math
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from kx98.config import COLS, ROWS, VID
from kx98.encode import encode_animation, image_to_rgb_tuples
from kx98.hiddev import Display
from kx98.transport import WIRED, DONGLE, PROFILES, Profile


@pytest.mark.parametrize("profile", [WIRED, DONGLE])
@pytest.mark.parametrize("num_frames", [1, 4])
def test_encode_animation_profiles(profile: Profile, num_frames: int):
    frames = [Image.new("RGB", (COLS, ROWS), (i * 40, i * 60, i * 80)) for i in range(num_frames)]
    delay_ms = 120
    packets = encode_animation(frames, delay_ms=delay_ms, profile=profile)

    # 1. Packet length invariant
    assert len(packets) > 0
    for pkt in packets:
        assert len(pkt) == profile.packet_len

    # 2. Packet count formula: ceil((4 header bytes + 3*COLS*ROWS*N) / chunk_size)
    total_payload_bytes = 4 + 3 * COLS * ROWS * num_frames
    expected_count = math.ceil(total_payload_bytes / profile.chunk_size)
    assert len(packets) == expected_count

    # 3. Concatenated payload reconstruction matches header + RGB bytes
    delay_ticks = max(1, delay_ms // 10)
    expected_header = bytearray([
        num_frames & 0xFF,
        (num_frames >> 8) & 0xFF,
        delay_ticks & 0xFF,
        (delay_ticks >> 8) & 0xFF,
    ])
    expected_rgb = bytearray()
    for frame in frames:
        for r, g, b in image_to_rgb_tuples(frame):
            expected_rgb.extend([r & 0xFF, g & 0xFF, b & 0xFF])
    expected_stream = expected_header + expected_rgb

    reconstructed_stream = bytearray()
    for pkt_idx, pkt in enumerate(packets):
        assert pkt[0] == 0xAA
        assert pkt[1] == 65
        assert pkt[2] == (pkt_idx >> 8) & 0xFF
        assert pkt[3] == pkt_idx & 0xFF
        # Extract payload chunk (bytes 8 onwards, up to non-zero or expected slice length)
        chunk_start = pkt_idx * profile.chunk_size
        chunk_len = min(profile.chunk_size, len(expected_stream) - chunk_start)
        reconstructed_stream.extend(pkt[8 : 8 + chunk_len])

    assert reconstructed_stream == expected_stream


def test_display_open_priority_wired():
    """When both wired and dongle interfaces are present, WIRED USB takes priority."""
    mock_devices = {
        (VID, 0x8009): [{"usage_page": 0xFF68, "usage": 0x0061, "path": b"path_wired_cmd"}],
        (VID, 0xFEFE): [{"usage_page": 0xFF60, "usage": 0x0061, "path": b"path_dongle_cmd"}],
    }

    def fake_enumerate(vid, pid):
        return mock_devices.get((vid, pid), [])

    with patch("hid.enumerate", side_effect=fake_enumerate), patch("hid.device") as mock_dev_cls:
        mock_instance = MagicMock()
        mock_dev_cls.return_value = mock_instance

        disp = Display()
        disp.open()

        assert disp.profile == WIRED
        assert disp.path == b"path_wired_cmd"
        mock_instance.open_path.assert_called_once_with(b"path_wired_cmd")


def test_display_open_fallback_to_dongle():
    """When only 2.4G dongle is present, auto-fallback opens DONGLE profile."""
    mock_devices = {
        (VID, 0x8009): [],
        (VID, 0xFEFE): [{"usage_page": 0xFF60, "usage": 0x0061, "path": b"path_dongle_cmd"}],
    }

    def fake_enumerate(vid, pid):
        return mock_devices.get((vid, pid), [])

    with patch("hid.enumerate", side_effect=fake_enumerate), patch("hid.device") as mock_dev_cls:
        mock_instance = MagicMock()
        mock_dev_cls.return_value = mock_instance

        disp = Display()
        disp.open()

        assert disp.profile == DONGLE
        assert disp.path == b"path_dongle_cmd"
        mock_instance.open_path.assert_called_once_with(b"path_dongle_cmd")


def test_display_open_none_raises_oserror():
    """When no devices are present, open() raises OSError."""
    with patch("hid.enumerate", return_value=[]):
        disp = Display()
        with pytest.raises(OSError, match="No supported KX98 HID device found"):
            disp.open()
