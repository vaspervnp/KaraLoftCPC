"""Amstrad CPC Mode 0 encoding, palette quantisation and screen layout.

Every asset exporter in this project goes through this module so that the
bit-interleaving is written down exactly once. The encoding here is the one
verified against the emulator (see CLAUDE.md 6.3), NOT the table in plan.md.

    Mode 0 byte, both pixels packed together:
        bit 7 -> left  pixel, pen bit 0      bit 6 -> right pixel, pen bit 0
        bit 5 -> left  pixel, pen bit 2      bit 4 -> right pixel, pen bit 2
        bit 3 -> left  pixel, pen bit 1      bit 2 -> right pixel, pen bit 1
        bit 1 -> left  pixel, pen bit 3      bit 0 -> right pixel, pen bit 3
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Mode 0 pixel packing
# --------------------------------------------------------------------------

# Which byte bit carries which pen bit, per pixel. Left pixel uses the odd
# bits, right pixel the even ones.
_LEFT_BITS = {0: 7, 2: 5, 1: 3, 3: 1}     # pen bit -> byte bit
_RIGHT_BITS = {0: 6, 2: 4, 1: 2, 3: 0}

MASK_LEFT = 0b10101010    # the four byte bits belonging to the left pixel
MASK_RIGHT = 0b01010101   # ... and to the right pixel


def encode_pixels(left: int, right: int) -> int:
    """Pack two pen numbers (0-15) into one Mode 0 byte."""
    if not (0 <= left <= 15 and 0 <= right <= 15):
        raise ValueError(f"pen out of range: {left}, {right}")
    byte = 0
    for pen_bit, byte_bit in _LEFT_BITS.items():
        byte |= ((left >> pen_bit) & 1) << byte_bit
    for pen_bit, byte_bit in _RIGHT_BITS.items():
        byte |= ((right >> pen_bit) & 1) << byte_bit
    return byte


def decode_byte(byte: int) -> tuple[int, int]:
    """Unpack a Mode 0 byte back into (left pen, right pen)."""
    left = right = 0
    for pen_bit, byte_bit in _LEFT_BITS.items():
        left |= ((byte >> byte_bit) & 1) << pen_bit
    for pen_bit, byte_bit in _RIGHT_BITS.items():
        right |= ((byte >> byte_bit) & 1) << pen_bit
    return left, right


def encode_row(pens: list[int]) -> bytes:
    """Pack a row of pen numbers into bytes. Length must be even."""
    if len(pens) % 2:
        raise ValueError("Mode 0 packs 2 pixels per byte; row length must be even")
    return bytes(encode_pixels(pens[i], pens[i + 1]) for i in range(0, len(pens), 2))


def decode_row(data: bytes) -> list[int]:
    pens = []
    for byte in data:
        pens.extend(decode_byte(byte))
    return pens


def solid_pen_byte(pen: int) -> int:
    """The byte that paints both of its pixels in `pen`."""
    return encode_pixels(pen, pen)


# --------------------------------------------------------------------------
# Transparency masks
#
# The blitter does  SCREEN = (SCREEN AND MASK) OR DATA, so a transparent
# pixel needs all four of its mask bits set and all four data bits clear.
# --------------------------------------------------------------------------

def encode_mask(left_opaque: bool, right_opaque: bool) -> int:
    mask = 0
    if not left_opaque:
        mask |= MASK_LEFT
    if not right_opaque:
        mask |= MASK_RIGHT
    return mask


# --------------------------------------------------------------------------
# Hardware palette
#
# hardware colour index -> RGB, read back off the emulator rather than
# transcribed. See docs/cpc_palette.md. The gate array wants &40 | index.
# --------------------------------------------------------------------------

HW_COLOURS: dict[int, tuple[int, int, int]] = {
    20: (0, 2, 1),        4: (0, 2, 107),      21: (12, 2, 244),
    28: (108, 2, 1),     24: (105, 2, 104),    29: (108, 2, 242),
    12: (243, 5, 6),      5: (240, 2, 104),    13: (243, 2, 244),
    22: (2, 120, 1),      6: (0, 120, 104),    23: (12, 123, 244),
    30: (110, 123, 1),    0: (110, 125, 107),  31: (110, 123, 246),
    14: (243, 125, 13),   7: (243, 125, 107),  15: (250, 128, 249),
    18: (2, 240, 1),      2: (0, 243, 107),    19: (15, 243, 242),
    26: (113, 245, 4),   25: (113, 243, 107),  27: (113, 243, 244),
    10: (243, 243, 13),   3: (243, 243, 109),  11: (255, 243, 249),
}

HW_NAMES = {
    20: "Black", 4: "Blue", 21: "Bright Blue", 28: "Red", 24: "Magenta",
    29: "Mauve", 12: "Bright Red", 5: "Purple", 13: "Bright Magenta",
    22: "Green", 6: "Cyan", 23: "Sky Blue", 30: "Yellow", 0: "White",
    31: "Pastel Blue", 14: "Orange", 7: "Pink", 15: "Pastel Magenta",
    18: "Bright Green", 2: "Sea Green", 19: "Bright Cyan", 26: "Lime",
    25: "Pastel Green", 27: "Pastel Cyan", 10: "Bright Yellow",
    3: "Pastel Yellow", 11: "Bright White",
}


def gate_array_value(hw: int) -> int:
    """The byte to write to &7Fxx after selecting a pen."""
    return 0x40 | hw


def nearest_hw(rgb: tuple[int, int, int]) -> int:
    """Nearest hardware colour to an RGB triple, by squared distance."""
    r, g, b = rgb[:3]
    return min(HW_COLOURS,
               key=lambda hw: (HW_COLOURS[hw][0] - r) ** 2
                            + (HW_COLOURS[hw][1] - g) ** 2
                            + (HW_COLOURS[hw][2] - b) ** 2)


def nearest_in(rgb: tuple[int, int, int], hw_list: list[int]) -> int:
    """Index into `hw_list` of the closest entry to an RGB triple."""
    r, g, b = rgb[:3]
    return min(range(len(hw_list)),
               key=lambda i: (HW_COLOURS[hw_list[i]][0] - r) ** 2
                           + (HW_COLOURS[hw_list[i]][1] - g) ** 2
                           + (HW_COLOURS[hw_list[i]][2] - b) ** 2)


# --------------------------------------------------------------------------
# Quantisation
# --------------------------------------------------------------------------

def choose_palette(pixels, count=16, forced=None):
    """Pick `count` hardware colours for an iterable of RGB pixels.

    Snaps every pixel to the nearest of the 27 hardware colours, then keeps
    the most used ones. `forced` entries are always included and come first,
    which is how pen 0 gets pinned to the background/transparency colour.
    """
    forced = list(forced or [])
    if len(forced) > count:
        raise ValueError("more forced colours than pens")

    usage: dict[int, int] = {}
    for px in pixels:
        hw = nearest_hw(px)
        usage[hw] = usage.get(hw, 0) + 1

    palette = list(forced)
    for hw, _ in sorted(usage.items(), key=lambda kv: -kv[1]):
        if len(palette) >= count:
            break
        if hw not in palette:
            palette.append(hw)
    while len(palette) < count:                       # pad unused pens
        for hw in HW_COLOURS:
            if hw not in palette:
                palette.append(hw)
                break
    return palette


def quantise(image, palette):
    """RGB(A) PIL image -> 2D list of pen indices into `palette`."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    cache: dict[tuple[int, int, int], int] = {}
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            c = px[x, y]
            pen = cache.get(c)
            if pen is None:
                pen = cache[c] = nearest_in(c, palette)
            row.append(pen)
        out.append(row)
    return out


# --------------------------------------------------------------------------
# Screen layout
# --------------------------------------------------------------------------

SCREEN_BASE = 0xC000
SCREEN_WIDTH_BYTES = 80
SCREEN_HEIGHT = 200


def screen_offset(x_byte: int, line: int, width_bytes: int = SCREEN_WIDTH_BYTES) -> int:
    """Offset from the screen base of a byte on the standard CPC layout.

        offset = (line AND 7) * &0800 + (line >> 3) * width + x
    """
    return (line & 7) * 0x0800 + (line >> 3) * width_bytes + x_byte


def linear_to_screen(data: bytes, width_bytes: int, height: int,
                     size: int = 0x4000, fill: int = 0) -> bytearray:
    """Re-order a top-to-bottom linear bitmap into CPC screen order."""
    out = bytearray([fill]) * size
    for line in range(height):
        base = screen_offset(0, line, width_bytes)
        src = line * width_bytes
        out[base:base + width_bytes] = data[src:src + width_bytes]
    return out


# --------------------------------------------------------------------------
# Overscan layout (192 x 272)
#
# The CRTC only puts MA0-MA9 on the address bus, so one raster block can
# cover 1024 words = 2048 bytes. At 48 chars per line that is 21 character
# rows, and overscan needs 34. A full-height overscan screen therefore
# CANNOT be one linear buffer: it is two halves of 17 rows, each laid out
# exactly like a normal CPC screen, with the display code re-pointing
# R12/R13 at the second half partway down the frame.
#
#   96 bytes/line x 136 lines = 13,056 bytes per half
#   x 2 halves                = 26,112 bytes total, as plan.md 2 states
#
# Within a half:  offset = (line AND 7) * &0800 + (line >> 3) * 96 + x
# which peaks at 15,967 and so still fits one 16K page.
#
# The file is written as the 16 raster blocks in copy order, so the loader
# is eight LDIRs per half rather than a scatter:
#
#   half 0 RA0, half 0 RA1 ... half 0 RA7, half 1 RA0 ... half 1 RA7
#
# each block being 17 rows x 96 bytes = 1,632 bytes.
# --------------------------------------------------------------------------

OVERSCAN_WIDTH = 192                    # Mode 0 pixels
OVERSCAN_HEIGHT = 272                   # scanlines
OVERSCAN_WIDTH_BYTES = OVERSCAN_WIDTH // 2
OVERSCAN_HALF_LINES = 136
OVERSCAN_ROWS_PER_HALF = OVERSCAN_HALF_LINES // 8
OVERSCAN_BLOCK_BYTES = OVERSCAN_ROWS_PER_HALF * OVERSCAN_WIDTH_BYTES    # 1632
OVERSCAN_HALF_BYTES = 8 * OVERSCAN_BLOCK_BYTES                          # 13056
OVERSCAN_BYTES = 2 * OVERSCAN_HALF_BYTES                                # 26112


def overscan_page_offset(x_byte: int, line_in_half: int) -> int:
    """Offset within a half's 16K page - the address the CRTC will read."""
    return ((line_in_half & 7) * 0x0800
            + (line_in_half >> 3) * OVERSCAN_WIDTH_BYTES
            + x_byte)


def overscan_file_offset(x_byte: int, line: int) -> int:
    """Offset within overscan.bin, which is stored in copy order."""
    half, line_in_half = divmod(line, OVERSCAN_HALF_LINES)
    raster = line_in_half & 7
    row = line_in_half >> 3
    return (half * OVERSCAN_HALF_BYTES
            + raster * OVERSCAN_BLOCK_BYTES
            + row * OVERSCAN_WIDTH_BYTES
            + x_byte)


def pack_overscan(pen_rows) -> bytearray:
    """2D pen rows (272 x 192) -> overscan.bin bytes."""
    if len(pen_rows) != OVERSCAN_HEIGHT:
        raise ValueError(f"need {OVERSCAN_HEIGHT} rows, got {len(pen_rows)}")
    out = bytearray(OVERSCAN_BYTES)
    for line, row in enumerate(pen_rows):
        if len(row) != OVERSCAN_WIDTH:
            raise ValueError(f"line {line}: need {OVERSCAN_WIDTH} pixels")
        packed = encode_row(row)
        dst = overscan_file_offset(0, line)
        out[dst:dst + OVERSCAN_WIDTH_BYTES] = packed
    return out


def unpack_overscan(blob: bytes):
    """overscan.bin -> 2D pen rows, for verifying an export."""
    rows = []
    for line in range(OVERSCAN_HEIGHT):
        src = overscan_file_offset(0, line)
        rows.append(decode_row(blob[src:src + OVERSCAN_WIDTH_BYTES]))
    return rows


def overscan_half_page(blob: bytes, half: int, size: int = 0x4000,
                       fill: int = 0) -> bytearray:
    """Expand one half of overscan.bin into the 16K page image the CRTC sees."""
    page = bytearray([fill]) * size
    for line_in_half in range(OVERSCAN_HALF_LINES):
        src = overscan_file_offset(0, half * OVERSCAN_HALF_LINES + line_in_half)
        dst = overscan_page_offset(0, line_in_half)
        page[dst:dst + OVERSCAN_WIDTH_BYTES] = blob[src:src + OVERSCAN_WIDTH_BYTES]
    return page
