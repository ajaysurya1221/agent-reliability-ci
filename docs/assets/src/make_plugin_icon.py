"""Draw the plugin's listing icon: earlier days in one band, recent days well below it.

Standard library only. The picture is the README banner reduced to a square: four dots for
earlier days inside a band, a dashed line for the split, two dots for recent days below.

    python docs/assets/src/make_plugin_icon.py           # write the PNG
    python docs/assets/src/make_plugin_icon.py --check   # fail if the file's pixels differ
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

SIZE = 1024
SAMPLES = 4  # sub-samples per pixel edge, for smooth dot edges
TARGET = Path(__file__).resolve().parents[3] / "plugins/realornoise/.claude-plugin/icon.png"

GROUND = (0x0D, 0x11, 0x17)
BEFORE = (0x6C, 0xB6, 0xFF)
AFTER = (0xFF, 0x9F, 0x45)
SPLIT = (0x5B, 0x68, 0x78)
BAND = (262, 498)  # rows of the band the earlier days stay in
BAND_OPACITY = 0.10
# Everything stays 90 pixels or more from the edge: listings mask icons to rounded shapes.
DOTS: tuple[tuple[int, int, int, tuple[int, int, int]], ...] = (
    (170, 330, 52, BEFORE),
    (305, 430, 52, BEFORE),
    (440, 352, 52, BEFORE),
    (575, 416, 52, BEFORE),
    (776, 742, 52, AFTER),
    (882, 678, 52, AFTER),
    *((682, y, 7, SPLIT) for y in range(180, 860, 36)),
)


def _blend(under: tuple[int, int, int], over: tuple[int, int, int], share: float) -> bytes:
    return bytes(round(u + (o - u) * share) for u, o in zip(under, over, strict=True))


def pixels() -> list[bytearray]:
    """Rows of RGB bytes, top to bottom."""
    band = _blend(GROUND, BEFORE, BAND_OPACITY)
    rows = [
        bytearray((band if BAND[0] <= y < BAND[1] else bytes(GROUND)) * SIZE) for y in range(SIZE)
    ]
    step = 1 / SAMPLES
    for cx, cy, radius, colour in DOTS:
        for y in range(cy - radius - 1, cy + radius + 2):
            row = rows[y]
            for x in range(cx - radius - 1, cx + radius + 2):
                inside = 0
                for sy in range(SAMPLES):
                    dy = y + (sy + 0.5) * step - cy
                    for sx in range(SAMPLES):
                        dx = x + (sx + 0.5) * step - cx
                        inside += dx * dx + dy * dy <= radius * radius
                if inside:
                    under = (row[3 * x], row[3 * x + 1], row[3 * x + 2])
                    row[3 * x : 3 * x + 3] = _blend(under, colour, inside / SAMPLES**2)
    return rows


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))


def encode(rows: list[bytearray]) -> bytes:
    """An 8-bit RGB PNG; every row uses filter 0, so decoding needs no filter step."""
    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def decode(data: bytes) -> bytes:
    """The filtered rows of a PNG written by `encode` (IDAT chunks joined and inflated)."""
    position, packed = 8, b""
    while position < len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        if kind == b"IDAT":
            packed += data[position + 8 : position + 8 + length]
        position += 12 + length
    return zlib.decompress(packed)


def main(argv: list[str]) -> int:
    rows = pixels()
    if argv == ["--check"]:
        expected = b"".join(b"\x00" + bytes(row) for row in rows)
        same = TARGET.is_file() and decode(TARGET.read_bytes()) == expected
        print("Icon pixels match." if same else "Icon pixels differ from the generator.")
        return 0 if same else 1
    TARGET.write_bytes(encode(rows))
    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
