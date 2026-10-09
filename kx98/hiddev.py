"""HID Transport and Display controller for KX87 / KX98 keyboard (Wired + 2.4G Dongle)."""

import hashlib
import logging
import time
from typing import Optional
import hid
from PIL import Image

from kx98.config import (
    VID,
    PID,
    PID_DONGLE,
    PIDS,
    USAGE_PAGE,
    USAGE,
    USAGE_PAGE_FLASH,
    UP_DONGLE,
    PACKET_LEN,
    PUSH_MODE,
)
from kx98.encode import encode_frame, encode_animation, encode_dongle_animation

logger = logging.getLogger("kx98.hiddev")


class Display:
    """Manages the USB HID connection and packet pushing (Wired 0x8009 & 2.4G Dongle 0xFEFE)."""

    def __init__(self, push_mode: str = PUSH_MODE):
        self.push_mode = push_mode
        self.device: Optional[hid.device] = None
        self.path: Optional[bytes] = None
        self.is_dongle: bool = False
        self.last_write_time: float = 0.0
        self.last_payload_hash: Optional[str] = None
        self._in_flight: bool = False

    def find_path(self, usage_page: int, usage: int = USAGE) -> Optional[bytes]:
        """Locate device path matching VID/PIDS (wired or 2.4G dongle), usage_page, and usage."""
        for pid in PIDS:
            for d in hid.enumerate(VID, pid):
                if d.get("usage_page") == usage_page and (usage is None or d.get("usage") == usage):
                    return d.get("path")
        return None

    def open(self) -> None:
        """Open the HID device for communication (auto-detects Dongle or Wired)."""
        self.close()
        # Priority 1: Wired USB (UP=0xFF68) - rock-solid 4104-byte bulk packets
        wired_path = self.find_path(USAGE_PAGE, USAGE)
        if wired_path:
            dev = hid.device()
            dev.open_path(wired_path)
            self.device = dev
            self.path = wired_path
            self.is_dongle = False
            logger.info(f"Opened KX98 via WIRED USB on {wired_path.decode('utf-8', errors='replace')}")
            return

        # Priority 2: 2.4G Dongle (UP=0xFF60)
        dongle_path = self.find_path(UP_DONGLE, USAGE)
        if dongle_path:
            dev = hid.device()
            dev.open_path(dongle_path)
            self.device = dev
            self.path = dongle_path
            self.is_dongle = True
            logger.info(f"Opened KX98 via 2.4G DONGLE on {dongle_path.decode('utf-8', errors='replace')}")
            return

        raise OSError(f"Neither KX87 Wired (0x{PID:04X}) nor 2.4G Dongle (0x{PID_DONGLE:04X}) found")

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
        """Push frames to display (auto-detects Dongle or Wired)."""
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
        """Burn animation to flash using either 2.4G Dongle (32-byte) or Wired (4104-byte)."""
        # Prioritize Wired USB
        wired_path = self.find_path(USAGE_PAGE, USAGE)
        if wired_path:
            return self._show_flash_wired(frames, delay_ms)

        dongle_path = self.find_path(UP_DONGLE, USAGE)
        if dongle_path:
            return self._show_flash_dongle(dongle_path, frames, delay_ms)

        raise OSError("No KX87 HID device connected")

    def _show_flash_dongle(self, path: bytes, frames: list[Image.Image], delay_ms: int) -> bool:
        """Push animation over 2.4G Dongle (32-byte packets to UP=0xFF60)."""
        packets = encode_dongle_animation(frames, delay_ms=delay_ms)
        payload_hash = hashlib.sha256(b"".join(packets)).hexdigest()

        if payload_hash == self.last_payload_hash:
            logger.debug("Payload unchanged, skipping dongle flash")
            return True

        now = time.time()
        elapsed = now - self.last_write_time
        if elapsed < 15.0 and self.last_write_time > 0:
            logger.debug(f"Rate limit: {elapsed:.1f}s < 15s, deferring dongle write")
            return False

        self.close()
        h = hid.device()
        h.open_path(path)
        try:
            for i, pkt in enumerate(packets):
                h.write(b"\x00" + pkt)
                reply = h.read(32, timeout_ms=2000)
                if not reply or reply[0] != 0x55 or reply[1] != 65:
                    logger.error(f"Dongle packet #{i} failed, reply={reply[:8] if reply else 'none'}")
                    return False
        finally:
            h.close()
            time.sleep(0.1)
            self.open()

        self.last_write_time = time.time()
        self.last_payload_hash = payload_hash
        logger.info(f"Flashed animation via 2.4G DONGLE ({len(frames)} frames, {len(packets)} pkts, delay {delay_ms}ms)")
        return True

    def _show_flash_wired(self, frames: list[Image.Image], delay_ms: int) -> bool:
        """Push animation over Wired USB (4104-byte packets via UP=0xFF68 -> 0xFF67)."""
        packets = encode_animation(frames, delay_ms=delay_ms)
        payload_hash = hashlib.sha256(b"".join(packets)).hexdigest()

        if payload_hash == self.last_payload_hash:
            logger.debug("Payload unchanged, skipping wired flash")
            return True

        now = time.time()
        elapsed = now - self.last_write_time
        if elapsed < 15.0 and self.last_write_time > 0:
            logger.debug(f"Rate limit: {elapsed:.1f}s < 15s, deferring wired write")
            return False

        path_main = self.find_path(USAGE_PAGE, USAGE)
        path_flash = self.find_path(USAGE_PAGE_FLASH, USAGE)
        if not path_main or not path_flash:
            raise OSError("Could not locate wired main and flash HID interfaces")

        # Send flash animation directly to UP_FLASH without 0x36 handshake
        # (Prevents keyboard controller from pausing CPU and blinking "LOADING" on TFT)
        self.close()
        h_flash = hid.device()
        h_flash.open_path(path_flash)
        try:
            for pkt in packets:
                h_flash.write(b"\x00" + pkt)
                reply = h_flash.read(64, timeout_ms=3000)
                if not reply or reply[0] != 0x55 or reply[1] != 65:
                    logger.error(f"Wired packet ACK failed, reply={reply[:8] if reply else 'none'}")
                    return False
        finally:
            h_flash.close()
            time.sleep(0.05)
            self.open()

        self.last_write_time = time.time()
        self.last_payload_hash = payload_hash
        logger.info(f"Flashed animation via WIRED USB ({len(frames)} frames, delay {delay_ms}ms)")
        return True
