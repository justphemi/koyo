"""Generate simple placeholder PNG and ICO files with no dependencies."""

from __future__ import annotations

import struct
import zlib

LOGO_RGB = (79, 70, 229)
ICON_RGB = (15, 118, 110)
FAVICON_RGB = (30, 27, 75)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    block = kind + data
    crc = zlib.crc32(block) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + block + struct.pack(">I", crc)


def make_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = bytes(rgb) * width
    scanlines = b"".join(b"\x00" + row for _ in range(height))
    idat = zlib.compress(scanlines, 9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def make_ico(entries: list[tuple[int, bytes]]) -> bytes:
    count = len(entries)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    directory = b""
    payload = b""
    for size, png in entries:
        width_byte = size if size < 256 else 0
        directory += struct.pack(
            "<BBBBHHII", width_byte, width_byte, 0, 0, 1, 32, len(png), offset
        )
        payload += png
        offset += len(png)
    return header + directory + payload


def make_favicon_ico() -> bytes:
    return make_ico(
        [
            (16, make_png(16, 16, FAVICON_RGB)),
            (32, make_png(32, 32, FAVICON_RGB)),
            (48, make_png(48, 48, FAVICON_RGB)),
            (256, make_png(256, 256, FAVICON_RGB)),
        ]
    )