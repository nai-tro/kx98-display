# KX98 / KX87 Matrix Display Daemon

A lightweight macOS background service that drives the 51×5 RGB LED matrix on **SARU Space KX98 / KX87** (and compatible Sonix / HFD-HUB matrix keyboards) with live AI model token usage and Spotify track information.

---

## Features

- **Multi-Account AI Token Usage**:
  - Live token usage progress bar + percentage from `~/.omp/agent/agent.db`.
  - Supports multiple accounts with 1-letter prefixes:
    - `C` (or `C1`, `C2`): Claude Enterprise (monthly limit).
    - `G1`, `G2`: Google Gemini accounts (5-hour limit).
    - `X`: OpenAI Codex (5-hour / monthly limit).
  - Filters out weekly stats; refreshes data every 5 minutes.
  - Clean layout: `[ Prefix ]  [ ==== Sweeping Neon Bar ==== ]  [ Percent ]`
- **Spotify Now-Playing with Dual Sound Waves**:
  - Automatically activates when Spotify is playing.
  - **Native ICU Transliteration**: Romanizes Japanese (Kanji/Kana), Thai, Cyrillic, and CJK to clean Latin uppercase using Apple's CoreFoundation engine (`CFStringTransform`).
  - **Word-Aligned Pagination**: Alternates between Title and Artist cards without text cutting or scrolling blur.
  - **Dual Dancing Equalizers**: Symmetrical 3-bar animated sound wave equalizers bounce on both the left and right edges of the screen.
  - 30-second music display duration.
- **Log Auto-Purge**:
  - Daemon automatically caps `~/Library/Logs/kx98-display.log` to 500 lines at startup and every 30 minutes, preventing unbounded disk growth.
- **Device Portability**:
  - Supports any Sonix / Ajazz / Epomaker / Aula HFD matrix keyboard via environment variable overrides.

---

## Hardware Architecture & Connectivity

| Connection | Supported? | Notes |
|---|---|---|
| **Wired USB Cable** | **YES (Recommended)** | 100% reliable 4104-byte bulk packets on `0xFF67` with prepare handshake on `0xFF68`. |
| **2.4G USB Dongle** | Keyboard Only | Vendor radio firmware only syncs keypresses over the air; the LED matrix controller requires the USB cable. |
| **Bluetooth** | Keyboard Only | macOS restricts Bluetooth HID to generic Keyboard/Mouse profiles; vendor HID endpoints are blocked by macOS. |

---

## Quick Start

### 1. Requirements
- macOS 13+ (Apple Silicon or Intel)
- Python 3.12+ (or [uv](https://github.com/astral-sh/uv))

### 2. Setup
```bash
cd poc/kx98-display
uv sync
```

### 3. Run Standalone (Testing)
```bash
uv run python -m kx98.main
```

### 4. Install as a Background Service (macOS launchd)
```bash
# Copy launchd plist to user LaunchAgents
cp launchd/io.bankx.kx98-display.plist ~/Library/LaunchAgents/

# Start service
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/io.bankx.kx98-display.plist
```

To stop or restart:
```bash
# Stop
launchctl bootout gui/$(id -u)/io.bankx.kx98-display

# Restart
launchctl kickstart -k gui/$(id -u)/io.bankx.kx98-display
```

### 5. Check Live Logs
```bash
tail -f ~/Library/Logs/kx98-display.log
```

---

## Customizing for Other Keyboards / Resolutions

You can configure other keyboards or LED matrix sizes without modifying any code using environment variables:

| Environment Variable | Default | Description |
|---|---|---|
| `KX_VID` | `0x0C45` | Vendor ID (Sonix) |
| `KX_PID` | `0x8009` | Product ID (KX87 / KX98 wired) |
| `KX_COLS` | `51` | Matrix columns (e.g. `70` for 70x7 boards) |
| `KX_ROWS` | `5` | Matrix rows (e.g. `7` for 70x7 boards) |
| `KX_DWELL_OMP` | `15.0` | Dwell duration per AI stats screen (seconds) |
| `KX_DWELL_MUSIC` | `30.0` | Dwell duration for Spotify screen (seconds) |
| `KX_INTERVAL_OMP` | `300.0` | OMP database fetch interval (seconds) |
| `KX_MAX_LOG_LINES`| `500` | Log retention line cap |

### Discovering Connected Keyboard IDs
Run the built-in HID discovery tool:
```bash
uv run python -m kx98.enumerate
```

---

## Manual Display Pusher CLI

Test custom colors, frames, or single-shot images directly:
```bash
# Solid color
uv run python -m kx98.push --solid "#00ff88"

# Single image (auto-resized to matrix dimensions)
uv run python -m kx98.push --image path/to/art.png

# Directory of numbered animation frames
uv run python -m kx98.push --frames path/to/frames_dir/ --delay 120
```

---

## Running Tests
```bash
uv run pytest
```
All unit tests verify byte-for-byte fidelity against captured ground-truth fixtures.
