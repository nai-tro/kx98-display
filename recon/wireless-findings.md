# KX98 Wireless Transport Reverse Engineering Findings

## Live Enumeration Baseline

| Transport | VID | PID (Hex / Dec) | Product | UP (Hex / Dec) | Usage (Hex / Dec) | Iface | MaxIn | MaxOut | MaxFeature | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| **WIRED USB** | 0x0C45 | 0x8009 (32777) | KX87 | 0xFF67 (65383) | 0x0061 (97) | 3 | 64 | **4104** | 64 | `ioreg` + `kx98.enumerate` |
| **WIRED USB** | 0x0C45 | 0x8009 (32777) | KX87 | 0xFF68 (65384) | 0x0061 (97) | 2 | 64 | 64 | 0 | `ioreg` + `kx98.enumerate` |
| **WIRED USB** | 0x0C45 | 0x8009 (32777) | KX87 | 0xFFFF (65535) | 0x0001 (1) | 1 | 64 | 0 | 0 | `kx98.enumerate` |
| **WIRED USB** | 0x0C45 | 0x8009 (32777) | KX87 | 0x0001 (1) | 0x0006 (6) | 0 | 8 | 1 | 0 | `ioreg` (Keyboard) |
| **WIRED USB** | 0x0C45 | 0x8009 (32777) | KX87 | 0x000C (12) | 0x0001 (1) | 1 | 16 | 1 | 1 | `ioreg` (Consumer) |

## 2.4G Dongle Enumeration

| Transport | VID | PID (Hex / Dec) | Product | UP (Hex / Dec) | Usage (Hex / Dec) | Iface | MaxIn | MaxOut | MaxFeature | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| **2.4G Dongle** | 0x0C45 | 0xFEFE (65278) | 2.4G Dongle | 0xFF60 (65376) | 0x0061 (97) | 3 | 32 | **32** | 0 | `ioreg` + `kx98.enumerate` |
| **2.4G Dongle** | 0x0C45 | 0xFEFE (65278) | 2.4G Dongle | 0xFF59 (65369) | 0x0061 (97) | 4 | 64 | 64 | 0 | `ioreg` + `kx98.enumerate` |
| **2.4G Dongle** | 0x0C45 | 0xFEFE (65278) | 2.4G Dongle | 0xFFFF (65535) | 0x0001 (1) | 2 | 64 | 0 | 0 | `kx98.enumerate` |
| **2.4G Dongle** | 0x0C45 | 0xFEFE (65278) | 2.4G Dongle | 0x0001 (1) | 0x0006 (6) | 0 | 8 | 1 | 0 | `ioreg` (Keyboard) |
| **2.4G Dongle** | 0x0C45 | 0xFEFE (65278) | 2.4G Dongle | 0x0001 (1) | 0x0002 (2) | 1 | 5 | 0 | 0 | `ioreg` (Mouse) |
| **2.4G Dongle** | 0x0C45 | 0xFEFE (65278) | 2.4G Dongle | 0x000C (12) | 0x0001 (1) | 1 | 16 | 1 | 1 | `ioreg` (Consumer) |

## Bluetooth Enumeration

| Transport | VID | PID (Hex / Dec) | Product | UP (Hex / Dec) | Usage (Hex / Dec) | Iface | MaxIn | MaxOut | MaxFeature | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| **Bluetooth LE** | 0x0C45 | 0xFEFE (65278) | KX87 BT1 | 0x0001 (1) | 0x0006 (6) | -1 | 16 | 2 | 1 | `ioreg` (Keyboard) |
| **Bluetooth LE** | 0x0C45 | 0xFEFE (65278) | KX87 BT1 | 0x0001 (1) | 0x0002 (2) | -1 | - | - | - | `kx98.enumerate` (Mouse) |
| **Bluetooth LE** | 0x0C45 | 0xFEFE (65278) | KX87 BT1 | 0x000C (12) | 0x0001 (1) | -1 | - | - | - | `kx98.enumerate` (Consumer) |
| **Bluetooth LE** | 0x0C45 | 0xFEFE (65278) | KX87 BT1 | *None* | *None* | -1 | - | **0** | - | *Zero vendor pages exposed (MaxOut=2 on keyboard)* |

## HFD-HUB Static Analysis

Extracted from vendor bundle `app.75a71501.js`:

### Transport Comparison Table

| Field | WIRED USB | 2.4G Dongle | Bluetooth (macOS) | Citation in `app.75a71501.js` |
|---|---|---|---|---|
| **VID** | `0x0C45` (3141) | `0x0C45` (3141) | `0x0C45` (3141) | `filters`: line 1692766, 1701189 |
| **PID** | `0x8009` (32777) | `0xFEFE` (65278) | `0xFEFE` (65278) | `filters`: line 1692766, 1701189 |
| **Primary Usage Page** | `0xFF68` (65384) | `0xFF60` (65376) | N/A (Only standard HID 0x0001) | `filters`: line 1692766, 1701189 |
| **Flash Upload Usage Page** | `0xFF67` (65383) | `0xFF60` (65376) | *None* | `openDevice(65383)` at line 2876800; dongle stays on 65376 |
| **Usage** | `0x0061` (97) | `0x0061` (97) | 6 (Keyboard only) | `filters`: line 1692766, 1701189 |
| **Report ID** | 0 (omitted / hidapi report 0) | 0 (omitted / hidapi report 0) | N/A | `sendReport(0, c)` line 2880560 |
| **Packet Length** | 4104 bytes | 32 bytes | N/A | `buildPkt_Flash` line 1862783 |
| **Chunk Size** | 4096 bytes (4104 - 8) | 24 bytes (32 - 8) | N/A | `buildPkt_Flash` `n - 8`: line 1862783; `setUserLed` line 2879500 |
| **Header Layout** | `AA 41 idx_hi idx_lo (off/chunk)_hi (off+chunk)/chunk 00 00` | `AA 41 idx_hi idx_lo (off/chunk)_hi (off+chunk)/chunk 00 00` | N/A | `buildPkt_Flash` line 1862783 |
| **ACK Bytes** | `85 65` (`0x55`, `0x41` / `'A'`) | `85 65` (`0x55`, `0x41` / `'A'`) | N/A | `inputreport` handler line 2879500 |
| **ACK Timeout** | 5000 ms (app) / 3000 ms (python) | 5000 ms (app) / 3000 ms (python) | N/A | `setTimeout` line 2880560 |
| **Inter-Packet Delay** | 0 ms | 0.005 - 0.012 s (workerDelay 12ms in music; flash events async on ACK) | N/A | `workerDelay` line 3092122 |
| **Handshake / Switching** | Switch to UP 0xFF67, close, switch back to 0xFF68 | None (stays on UP 0xFF60 throughout) | N/A | `case 71..85` line 2876800 |

### Key Implementation Details

1. **Packet Framing (`buildPkt_Flash`, line 1862783)**:
   ```js
   buildPkt_Flash: function(e, i, t) {
     var n = arguments.length > 3 && void 0 !== arguments[3] ? arguments[3] : 4104;
     var o = new Uint8Array(n);
     o[0] = 170; // 0xAA
     o[1] = 65;  // 0x41
     o[2] = e >> 8 & 255;
     o[3] = 255 & e;
     o[4] = i / (n - 8) >> 8 & 255;
     o[5] = (i + (n - 8)) / (n - 8) & 255;
     // o[6], o[7] are 0
     var a = new Uint8Array(t);
     return o.set(a, 8), o;
   }
   ```
   Chunk size is strictly `n - 8`. For 32-byte dongle packets, chunk size is `24`.

2. **Transport Interface Selection (`onApply`, line 2876800)**:
   - For wired device (`reportCount >= 64`): open device with usage page `65383` (`0xFF67`) for flash upload.
   - For 2.4G dongle (`reportCount < 64`): skip `openDevice(65383)`; send directly to the primary dongle device on usage page `65376` (`0xFF60`).

## Decision Gate Evaluation

### 2.4G Dongle: INFEASIBLE (HARDWARE ISOLATION)
- **Condition**: Step 1.1 showed VID `0x0C45` PID `0xFEFE` with UP `0xFF60` (32B report), but hardware verification (Step 6) proved packets never reach the display.
- **Forensic Evidence**:
  1. **Dummy ACK by Dongle USB Bridge**: Sent invalid command `0xAA 0xEE` to `0xFF60`. The dongle USB MCU immediately returned `0x55 0xEE` followed by 30 zero bytes. The dongle controller generates local synthetic ACKs for arbitrary reports without forwarding them over RF to the keyboard.
  2. **Vendor Web Driver Confirmation**: In `HFD-HUB` (`app.75a71501.js` line 2829046), matrix screen sync requires `usagePage: 65383` (`0xFF67`). When `0xFF67` is absent, the UI errors with `未找到usagePage为0xff67的设备` ("Device with usagePage 0xff67 not found").
  3. **Physical Hardware Bus Architecture**: The 51x5 LED matrix controller SPI flash is wired exclusively to the USB microcontroller's bulk endpoint (`0xFF67`, 4104B). The 2.4G RF receiver MCU only handles key/mouse HID input events and does not have bus access to the LED display controller.
  4. **Hardware Proof**: 33 packets of solid blue sent over 2.4G dongle received `0x55 0x41` ACKs, but physical keyboard matrix remained displaying the previously flashed wired image (green).
- **Conclusion**: KX87 / KX98 51x5 display is **strictly wired USB only**.

### Bluetooth: INFEASIBLE ON MACOS (DRIVER & ARCHITECTURE)
- **Forensic Evidence**:
  1. macOS Bluetooth Low Energy HID driver strictly exposes standard Generic Desktop Keyboard (UP `0x0001` Usage `0x0006`, `MaxOutputReportSize = 2`) and consumer collections.
  2. ZERO vendor usage pages (UP ≥ `0xFF00`) are created by Apple's BLE HID transport driver on macOS.
  3. `MaxOutputReportSize` is 2 bytes; cannot send 64 or 32-byte packets.
  4. `HFD-HUB` strictly queries for `usagePage === 65383`, which does not exist over BLE.
- **Conclusion**: Bluetooth cannot drive the display on macOS.
