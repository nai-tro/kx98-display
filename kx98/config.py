"""KX98 Display configuration constants with environment variable overrides for custom devices."""

import os
from pathlib import Path

# Hardware identifiers (Configurable via environment variables)
# Supports SONiX KX87 / KX98, Ajazz, Epomaker, Aula, and other HFD-HUB matrix keyboards.
VID = int(os.environ.get("KX_VID", "0x0C45"), 16)
PID = int(os.environ.get("KX_PID", "0x8009"), 16)
PID_DONGLE = int(os.environ.get("KX_PID_DONGLE", "0xFEFE"), 16)
PIDS = (PID, PID_DONGLE)

# HID Usage Pages
USAGE_PAGE = int(os.environ.get("KX_USAGE_PAGE", "0xFF68"), 16)        # 65384: Main wired interface
USAGE = int(os.environ.get("KX_USAGE", "0x0061"), 16)                  # 97
USAGE_PAGE_FLASH = int(os.environ.get("KX_USAGE_PAGE_FLASH", "0xFF67"), 16) # 65383: Wired flash animation
UP_DONGLE = int(os.environ.get("KX_UP_DONGLE", "0xFF60"), 16)          # 65376: 2.4G Dongle interface

# Display matrix dimensions (Override via KX_COLS / KX_ROWS for other boards, e.g. 70x7, 63x5)
COLS = int(os.environ.get("KX_COLS", "51"))
ROWS = int(os.environ.get("KX_ROWS", "5"))
MATRIX = (COLS, ROWS)
TOTAL_PIXELS = COLS * ROWS

# Wire packet sizes
PACKET_LEN = 64
PACKET_LEN_FLASH = 4104

# Mode and scenes
PUSH_MODE = os.environ.get("KX_PUSH_MODE", "flash")
SCENE_ORDER = ("omp", "music")

# Dwell durations
DWELL_OMP = float(os.environ.get("KX_DWELL_OMP", "15.0"))         # seconds per OMP stats screen
DWELL_MUSIC = float(os.environ.get("KX_DWELL_MUSIC", "30.0"))     # seconds for Spotify screen
MUSIC_FRAME_DELAY_MS = int(os.environ.get("KX_MUSIC_DELAY_MS", "150")) # 150ms for bouncing EQ

# Source polling intervals
INTERVAL_SPOTIFY = float(os.environ.get("KX_INTERVAL_SPOTIFY", "3.0"))   # fast on-change check
INTERVAL_OMP = float(os.environ.get("KX_INTERVAL_OMP", "300.0"))         # 5 minutes OMP refresh

# Log retention: keep only the latest N lines (auto-purged)
MAX_LOG_LINES = int(os.environ.get("KX_MAX_LOG_LINES", "500"))

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "recon" / "fixtures"
LOG_PATH = Path.home() / "Library" / "Logs" / "kx98-display.log"
