"""Frame and animation packet encoders for KX87 / KX98 display."""

from PIL import Image
from kx98.config import COLS, ROWS, TOTAL_PIXELS, PACKET_LEN, PACKET_LEN_FLASH


def image_to_rgb_tuples(image: Image.Image) -> list[tuple[int, int, int]]:
    """Convert a Pillow image to a list of 255 (R, G, B) tuples in row-major order."""
    if image.size != (COLS, ROWS):
        image = image.resize((COLS, ROWS))
    if image.mode != "RGB":
        image = image.convert("RGB")

    pixels = []
    for row in range(ROWS):
        for col in range(COLS):
            r, g, b = image.getpixel((col, row))[:3]
            pixels.append((r, g, b))
    return pixels


def encode_frame(image: Image.Image) -> list[bytes]:
    """
    Encode a single RGB frame into live streaming packets (cmd 66, 0x42) for UP_MAIN (0xFF68).
    Returns 14 packets of 64 bytes each.
    """
    pixels = image_to_rgb_tuples(image)
    raw_rgb = bytearray()
    for r, g, b in pixels:
        raw_rgb.extend([r & 0xFF, g & 0xFF, b & 0xFF])

    chunk_size = 56
    offset = 0
    packets = []

    while offset < len(raw_rgb):
        chunk = raw_rgb[offset : offset + chunk_size]
        pkt = bytearray(PACKET_LEN)
        pkt[0] = 0xAA
        pkt[1] = 66  # 0x42
        pkt[2] = len(chunk)
        pkt[3] = offset & 0xFF
        pkt[4] = (offset >> 8) & 0xFF
        pkt[5] = 0
        pkt[6] = 1 if (offset + chunk_size >= len(raw_rgb)) else 0
        pkt[7] = 0
        pkt[8 : 8 + len(chunk)] = chunk
        packets.append(bytes(pkt))
        offset += chunk_size

    return packets


def encode_animation(frames: list[Image.Image], delay_ms: int = 100) -> list[bytes]:
    """
    Encode an animation of one or more frames into flash storage packet(s) (cmd 65, 0x41)
    for UP_FLASH (0xFF67).
    Returns 4104-byte packets.
    """
    if not frames:
        raise ValueError("Frames list cannot be empty")

    num_frames = len(frames)
    delay_ticks = max(1, delay_ms // 10)  # ~10ms per tick

    header = bytearray([
        num_frames & 0xFF,
        (num_frames >> 8) & 0xFF,
        delay_ticks & 0xFF,
        (delay_ticks >> 8) & 0xFF,
    ])

    raw_rgb = bytearray()
    for frame in frames:
        for r, g, b in image_to_rgb_tuples(frame):
            raw_rgb.extend([r & 0xFF, g & 0xFF, b & 0xFF])

    total_buf = header + raw_rgb
    total_len = len(total_buf)

    chunk_size = 4096
    num_packets = (total_len + chunk_size - 1) // chunk_size

    packets = []
    for pkt_idx in range(num_packets):
        start = pkt_idx * chunk_size
        end = min(start + chunk_size, total_len)
        chunk = total_buf[start:end]

        pkt = bytearray(PACKET_LEN_FLASH)
        pkt[0] = 0xAA
        pkt[1] = 65  # 0x41
        pkt[2] = (pkt_idx >> 8) & 0xFF
        pkt[3] = pkt_idx & 0xFF
        pkt[4] = (total_len // chunk_size) >> 8 & 0xFF
        pkt[5] = ((total_len + chunk_size) // chunk_size) & 0xFF
        pkt[6] = 0
        pkt[7] = 0
        pkt[8 : 8 + len(chunk)] = chunk
        packets.append(bytes(pkt))

    return packets

def encode_dongle_animation(frames: list[Image.Image], delay_ms: int = 150) -> list[bytes]:
    """
    Encode animation into 32-byte flash packets (cmd 65, 0x41) for 2.4G Dongle on UP=0xFF60.
    Chunk size = 24 bytes per packet.
    """
    if not frames:
        raise ValueError("Frames list cannot be empty")

    num_frames = len(frames)
    delay_ticks = max(1, delay_ms // 10)

    header = bytearray([
        num_frames & 0xFF,
        (num_frames >> 8) & 0xFF,
        delay_ticks & 0xFF,
        (delay_ticks >> 8) & 0xFF,
    ])

    raw_rgb = bytearray()
    for frame in frames:
        for r, g, b in image_to_rgb_tuples(frame):
            raw_rgb.extend([r & 0xFF, g & 0xFF, b & 0xFF])

    total_buf = header + raw_rgb
    total_len = len(total_buf)

    chunk_size = 24  # 32 - 8
    num_packets = (total_len + chunk_size - 1) // chunk_size

    packets = []
    for pkt_idx in range(num_packets):
        start = pkt_idx * chunk_size
        end = min(start + chunk_size, total_len)
        chunk = total_buf[start:end]

        pkt = bytearray(32)
        pkt[0] = 0xAA
        pkt[1] = 65  # 0x41
        pkt[2] = (pkt_idx >> 8) & 0xFF
        pkt[3] = pkt_idx & 0xFF
        pkt[4] = (total_len // chunk_size) >> 8 & 0xFF
        pkt[5] = ((total_len + chunk_size) // chunk_size) & 0xFF
        pkt[6] = 0
        pkt[7] = 0
        pkt[8 : 8 + len(chunk)] = chunk
        packets.append(bytes(pkt))

    return packets
