"""Enumerate HID devices to locate KX98 keyboard and its vendor interface."""

import hid


def main() -> None:
    devices = hid.enumerate()
    print(f"Total HID devices detected: {len(devices)}")
    print("-" * 80)

    vendor_devices = []
    other_devices = []

    for d in devices:
        up = d.get("usage_page", 0)
        if up >= 0xFF00:
            vendor_devices.append(d)
        else:
            other_devices.append(d)

    print("=== VENDOR INTERFACES (usage_page >= 0xFF00) ===")
    if not vendor_devices:
        print("  (None found)")
    for d in vendor_devices:
        vid = d.get("vendor_id", 0)
        pid = d.get("product_id", 0)
        prod = d.get("product_string", "")
        mfr = d.get("manufacturer_string", "")
        up = d.get("usage_page", 0)
        u = d.get("usage", 0)
        iface = d.get("interface_number", -1)
        path = d.get("path", b"").decode("utf-8", errors="replace")
        print(
            f"VID=0x{vid:04X} ({vid})  PID=0x{pid:04X} ({pid})  "
            f"UP=0x{up:04X} ({up})  Usage=0x{u:04X} ({u})  "
            f"Iface={iface}  Mfr='{mfr}'  Prod='{prod}'"
        )
        print(f"    Path: {path}")

    print("\n=== OTHER KEYBOARD/INPUT DEVICES ===")
    for d in other_devices:
        vid = d.get("vendor_id", 0)
        pid = d.get("product_id", 0)
        prod = d.get("product_string", "")
        mfr = d.get("manufacturer_string", "")
        up = d.get("usage_page", 0)
        u = d.get("usage", 0)
        iface = d.get("interface_number", -1)
        if any(term in (prod + mfr).lower() for term in ["key", "kx", "hfd", "sonix", "saru", "gaming"]):
            print(
                f"  VID=0x{vid:04X} ({vid}) PID=0x{pid:04X} ({pid}) "
                f"UP=0x{up:04X} Usage=0x{u:04X} Iface={iface} Prod='{prod}' Mfr='{mfr}'"
            )


if __name__ == "__main__":
    main()
