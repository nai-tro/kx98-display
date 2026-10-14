"""HID Transport and Display controller for KX87 / KX98 keyboard."""

import hashlib
import logging
import time
from typing import Optional
import hid
from PIL import Image

from kx98.config import VID, PACKET_LEN, PUSH_MODE
from kx98.transport import Profile, WIRED, PROFILES
from kx98.encode import encode_frame, encode_animation

logger = logging.getLogger("kx98.hiddev")


class Display:
    """Manages the USB HID connection and packet pushing across transport profiles."""

    def __init__(self, push_mode: str = PUSH_MODE):
        self.push_mode = push_mode
        self.device: Optional[hid.device] = None
        self.path: Optional[bytes] = None
        self.profile: Optional[Profile] = None
        self.last_write_time: float = 0.0
        self.last_payload_hash: Optional[str] = None
        self._in_flight: bool = False

    def find_path(self, profile: Profile, usage_page: int) -> Optional[bytes]:
        """Locate device path matching profile PIDs, usage_page, and usage."""
        for pid in profile.pids:
            for d in hid.enumerate(VID, pid):
                if d.get("usage_page") == usage_page and (profile.usage is None or d.get("usage") == profile.usage):
                    return d.get("path")
        return None

    def open(self) -> None:
        """Open the HID device for communication, scanning profiles in priority order."""
        self.close()
        for profile in PROFILES:
            path = self.find_path(profile, profile.usage_page_cmd)
            if path:
                dev = hid.device()
                dev.open_path(path)
                self.device = dev
                self.path = path
                self.profile = profile
                logger.info(f"Opened KX98 via {profile.name} on {path.decode('utf-8', errors='replace')}")
                return

        raise OSError("No supported KX98 HID device found")

    def close(self) -> None:
        """Close device connection if open."""
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None

    def reopen(self) -> bool:
        """Attempt to reopen connection, returning True on success."""
        try:
            self.open()
            return True
        except Exception as e:
            logger.warning(f"Reopen failed: {e}")
            return False

    def show(self, frames: list[Image.Image], delay_ms: int = 150) -> bool:
        """Push frames to display (auto-detects active transport profile)."""
        if not frames:
            return False
        if self._in_flight:
            logger.debug("Write already in-flight, skipping")
            return False

        self._in_flight = True
        try:
            return self._show_flash(frames, delay_ms)
        finally:
            self._in_flight = False

    def _show_flash(self, frames: list[Image.Image], delay_ms: int) -> bool:
        """Burn animation to flash using highest priority available transport profile."""
        for profile in PROFILES:
            path = self.find_path(profile, profile.usage_page_cmd)
            if path:
                return self._write_animation(profile, frames, delay_ms)

        raise OSError("No KX87 HID device connected")

    def _write_animation(self, profile: Profile, frames: list[Image.Image], delay_ms: int) -> bool:
        """Push animation packets to flash interface with rate limiting and deduplication."""
        packets = encode_animation(frames, delay_ms=delay_ms, profile=profile)
        payload_hash = hashlib.sha256(b"".join(packets)).hexdigest()

        if payload_hash == self.last_payload_hash:
            logger.debug(f"Payload unchanged, skipping {profile.name.lower()} flash")
            return True

        now = time.time()
        elapsed = now - self.last_write_time
        if elapsed < 15.0 and self.last_write_time > 0:
            logger.debug(f"Rate limit: {elapsed:.1f}s < 15s, deferring {profile.name.lower()} write")
            return False

        flash_path = self.find_path(profile, profile.usage_page_flash)
        if not flash_path:
            raise OSError(f"Could not locate {profile.name} flash HID interface (UP=0x{profile.usage_page_flash:04X})")

        self.close()
        h = hid.device()
        h.open_path(flash_path)
        try:
            for i, pkt in enumerate(packets):
                acked = False
                for attempt in range(3):
                    h.write(b"\x00" + pkt)
                    reply = h.read(profile.read_len, timeout_ms=profile.ack_timeout_ms)
                    if reply and reply[0] == 0x55 and reply[1] == 65:
                        acked = True
                        break
                    logger.debug(f"{profile.name} packet #{i} attempt {attempt + 1} retrying...")
                    time.sleep(0.01)
                if not acked:
                    logger.error(f"{profile.name} packet #{i} failed, reply={reply[:8] if reply else 'none'}")
                    return False
                if profile.inter_packet_delay_s > 0:
                    time.sleep(profile.inter_packet_delay_s)
        finally:
            h.close()
            time.sleep(0.05)
            self.open()

        self.last_write_time = time.time()
        self.last_payload_hash = payload_hash
        if profile == WIRED:
            logger.info(f"Flashed animation via WIRED USB ({len(frames)} frames, delay {delay_ms}ms)")
        else:
            logger.info(
                f"Flashed animation via {profile.name} ({len(frames)} frames, {len(packets)} pkts, delay {delay_ms}ms)"
            )
        return True
