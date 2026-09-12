"""Vector barcode generation for pharmaceutical packaging.

Generates EAN-13 and pharmacode barcodes as vector drawing instructions
that can be rendered into PDF without rasterization.
"""
from __future__ import annotations

from typing import List, Tuple


class VectorBarcodeData:
    """Holds barcode bar positions for vector rendering."""

    def __init__(self, bars: List[Tuple[float, float, float]], text: str, total_width: float):
        """
        Args:
            bars: List of (x_offset_mm, width_mm, height_mm) for each black bar.
            text: Human-readable text below the barcode.
            total_width: Total width of the barcode in mm.
        """
        self.bars = bars
        self.text = text
        self.total_width = total_width


# EAN-13 encoding tables
_L_PATTERNS = [
    "0001101", "0011001", "0010011", "0111101", "0100011",
    "0110001", "0101111", "0111011", "0110111", "0001011",
]
_G_PATTERNS = [
    "0100111", "0110011", "0011011", "0100001", "0011101",
    "0111001", "0000101", "0010001", "0001001", "0010111",
]
_R_PATTERNS = [
    "1110010", "1100110", "1101100", "1000010", "1011100",
    "1001110", "1010000", "1000100", "1001000", "1110100",
]
_PARITY_PATTERNS = [
    "LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
    "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL",
]


def _ean13_checksum(digits_12: str) -> int:
    """Calculate EAN-13 check digit."""
    total = 0
    for i, ch in enumerate(digits_12):
        d = int(ch)
        total += d if i % 2 == 0 else d * 3
    return (10 - total % 10) % 10


def generate_ean13_bars(
    data: str,
    module_width_mm: float = 0.33,
    height_mm: float = 22.85,
) -> VectorBarcodeData:
    """Generate EAN-13 barcode as vector bar positions.

    Args:
        data: 12 or 13 digit EAN-13 code.
        module_width_mm: Width of one module (narrow bar).
        height_mm: Height of bars.

    Returns:
        VectorBarcodeData with bar positions for rendering.
    """
    if len(data) == 12:
        data = data + str(_ean13_checksum(data))
    elif len(data) == 13:
        pass  # assume valid
    else:
        raise ValueError(f"EAN-13 needs 12 or 13 digits, got {len(data)}")

    digits = [int(ch) for ch in data]
    first_digit = digits[0]
    parity = _PARITY_PATTERNS[first_digit]

    # Build binary string: start guard + left 6 digits + center guard + right 6 digits + end guard
    binary = "101"  # start guard

    for i in range(6):
        d = digits[1 + i]
        if parity[i] == "L":
            binary += _L_PATTERNS[d]
        else:
            binary += _G_PATTERNS[d]

    binary += "01010"  # center guard

    for i in range(6):
        d = digits[7 + i]
        binary += _R_PATTERNS[d]

    binary += "101"  # end guard

    # Convert binary to bar positions
    bars: List[Tuple[float, float, float]] = []
    x = 0.0
    current_bar_start = None

    for bit_char in binary:
        if bit_char == "1":
            if current_bar_start is None:
                current_bar_start = x
        else:
            if current_bar_start is not None:
                bar_width = x - current_bar_start
                bars.append((current_bar_start, bar_width, height_mm))
                current_bar_start = None
        x += module_width_mm

    if current_bar_start is not None:
        bar_width = x - current_bar_start
        bars.append((current_bar_start, bar_width, height_mm))

    return VectorBarcodeData(
        bars=bars,
        text=data,
        total_width=x,
    )


def generate_pharmacode_bars(
    code: int,
    narrow_mm: float = 0.5,
    wide_mm: float = 1.5,
    gap_mm: float = 0.5,
    height_mm: float = 8.0,
) -> VectorBarcodeData:
    """Generate a pharmacode (Laetus code) as vector bar positions.

    Pharmacode encodes an integer from 3 to 131070 using thin and wide bars.
    Used in pharmaceutical packaging for product verification at the packaging line.
    """
    if code < 3 or code > 131070:
        raise ValueError(f"Pharmacode must be 3-131070, got {code}")

    bars_pattern = []
    n = code
    while n > 0:
        if n % 2 == 1:
            bars_pattern.append("thin")
            n = (n - 1) // 2
        else:
            bars_pattern.append("wide")
            n = (n - 2) // 2

    bars_pattern.reverse()

    bars = []
    x = 0.0
    for bar_type in bars_pattern:
        w = narrow_mm if bar_type == "thin" else wide_mm
        bars.append((x, w, height_mm))
        x += w + gap_mm

    total_width = x - gap_mm

    return VectorBarcodeData(
        bars=bars,
        text=str(code),
        total_width=total_width,
    )
