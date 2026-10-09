"""Native macOS CoreFoundation transliteration engine for Unicode (Japanese, Thai, CJK -> Latin)."""

import ctypes
from ctypes import c_void_p, c_char_p, c_int
import logging

logger = logging.getLogger("kx98.transliterate")

try:
    cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

    cf.CFStringCreateWithCString.restype = c_void_p
    cf.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_int]

    cf.CFStringCreateMutableCopy.restype = c_void_p
    cf.CFStringCreateMutableCopy.argtypes = [c_void_p, c_int, c_void_p]

    cf.CFStringTransform.restype = c_int
    cf.CFStringTransform.argtypes = [c_void_p, c_void_p, c_void_p, c_int]

    cf.CFStringGetCString.restype = c_int
    cf.CFStringGetCString.argtypes = [c_void_p, c_char_p, c_int, c_int]

    cf.CFRelease.argtypes = [c_void_p]

    kCFStringEncodingUTF8 = 0x08000100
    kCFStringTransformToLatin = c_void_p.in_dll(cf, "kCFStringTransformToLatin")
    kCFStringTransformStripCombiningMarks = c_void_p.in_dll(cf, "kCFStringTransformStripCombiningMarks")
    _CF_AVAILABLE = True
except Exception as e:
    logger.warning(f"CoreFoundation transliterator not available: {e}")
    _CF_AVAILABLE = False


def to_latin(text: str) -> str:
    """
    Transliterate non-Latin text (Japanese Kanji/Kana, Thai, Chinese, Cyrillic, etc.)
    into ASCII uppercase Latin using Apple's built-in ICU transliteration engine.
    """
    if not text:
        return ""

    # If pure ASCII already, just uppercase and return
    if all(ord(c) < 128 for c in text):
        return text.upper()

    if not _CF_AVAILABLE:
        # Fallback: remove non-ascii characters
        return "".join(c for c in text if ord(c) < 128).upper()

    try:
        s = cf.CFStringCreateWithCString(None, text.encode("utf-8"), kCFStringEncodingUTF8)
        ms = cf.CFStringCreateMutableCopy(None, 0, s)
        cf.CFRelease(s)

        # 1. Transform to Latin
        cf.CFStringTransform(ms, None, kCFStringTransformToLatin, 0)
        # 2. Strip diacritics / combining marks
        cf.CFStringTransform(ms, None, kCFStringTransformStripCombiningMarks, 0)

        buf = ctypes.create_string_buffer(512)
        cf.CFStringGetCString(ms, buf, 512, kCFStringEncodingUTF8)
        cf.CFRelease(ms)
        latin = buf.value.decode("utf-8", errors="replace").upper()
        # Clean any remaining non-printable characters
        cleaned = "".join(c if (ord(c) < 128 and c.isprintable()) else " " for c in latin)
        return " ".join(cleaned.split())
    except Exception as e:
        logger.debug(f"Transliteration error: {e}")
        return "".join(c for c in text if ord(c) < 128).upper()
