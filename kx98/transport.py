"""Transport profiles for KX87 / KX98 display interfaces."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Profile:
    """Hardware and protocol parameters for a specific connection transport."""

    name: str
    pids: tuple[int, ...]
    usage_page_cmd: int
    usage_page_flash: int
    usage: int
    packet_len: int
    chunk_size: int
    read_len: int
    ack_timeout_ms: int
    inter_packet_delay_s: float


# Wired USB: Primary UP=0xFF68, Flash UP=0xFF67, 4104-byte packets (4096-byte payload chunk)
WIRED = Profile(
    name="WIRED USB",
    pids=(int(os.environ.get("KX_PID", "0x8009"), 16),),
    usage_page_cmd=int(os.environ.get("KX_USAGE_PAGE", "0xFF68"), 16),
    usage_page_flash=int(os.environ.get("KX_USAGE_PAGE_FLASH", "0xFF67"), 16),
    usage=int(os.environ.get("KX_USAGE", "0x0061"), 16),
    packet_len=4104,
    chunk_size=4096,
    read_len=64,
    ack_timeout_ms=3000,
    inter_packet_delay_s=0.0,
)

# 2.4G Dongle: Single UP=0xFF60, 32-byte packets (24-byte payload chunk)
# 15ms inter-packet delay ensures RF buffer stability across multi-frame payloads
DONGLE = Profile(
    name="2.4G DONGLE",
    pids=(int(os.environ.get("KX_PID_DONGLE", "0xFEFE"), 16),),
    usage_page_cmd=int(os.environ.get("KX_UP_DONGLE", "0xFF60"), 16),
    usage_page_flash=int(os.environ.get("KX_UP_DONGLE", "0xFF60"), 16),
    usage=int(os.environ.get("KX_USAGE", "0x0061"), 16),
    packet_len=32,
    chunk_size=24,
    read_len=32,
    ack_timeout_ms=3000,
    inter_packet_delay_s=0.015,
)

# Priority order: Wired USB > 2.4G Dongle (Bluetooth is infeasible on macOS due to missing vendor HID collections)
PROFILES = (WIRED, DONGLE)
