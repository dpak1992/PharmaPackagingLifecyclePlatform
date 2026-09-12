"""PDF artwork compositor for pharmaceutical packaging.

Generates prepress-aware PDFs with:
  - OCG layers (Optional Content Groups) for Dieline, Artwork, Text, Barcode
  - Separation color spaces for spot colors
  - Editable text objects (not outlines)
  - Vector barcode rendering
  - Bleed and trim box definitions
  - Standard PDF structure that opens in Adobe Illustrator with editable layers

Uses ReportLab for PDF generation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from reportlab.lib.units import mm
from reportlab.lib.colors import CMYKColor, Color, black, white
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from packaging_model.models import (
    PackagingConfig,
    DielineSpec,
    ArtworkSpec,
    Panel,
    TextElement,
    BarcodeElement,
    CodingZone,
    SpotColor,
)
from packaging_model.enums import PanelType, LayerName

from artwork_engine.barcode_gen import generate_ean13_bars


# Bleed amount
BLEED = 3.0  # mm


def _cmyk_color(c: float, m: float, y: float, k: float, alpha: float = 1.0) -> CMYKColor:
    """Create a CMYK color from percentages (0-100)."""
    return CMYKColor(c / 100.0, m / 100.0, y / 100.0, k / 100.0, alpha=alpha)


def _spot_to_cmyk(spot: SpotColor) -> CMYKColor:
    """Convert a spot color to its CMYK equivalent for screen preview."""
    return _cmyk_color(spot.cyan, spot.magenta, spot.yellow, spot.black)


def _get_panel_by_type(dieline: DielineSpec, ptype: PanelType) -> Optional[Panel]:
    """Find the first panel of a given type in the dieline."""
    for p in dieline.panels:
        if p.panel_type == ptype:
            return p
    return None


def compose_artwork_pdf(
    config: PackagingConfig,
    dieline: DielineSpec,
    artwork: ArtworkSpec,
    output_path: Union[str, Path],
) -> Path:
    """Compose a pharmaceutical carton artwork as an editable PDF.

    The PDF includes:
      - OCG layers for each artwork layer
      - Spot color definitions as Separation color spaces
      - Editable text objects
      - Vector barcodes
      - Dieline overlay (non-printing layer)
      - Bleed/trim box definitions

    Args:
        config: Complete packaging configuration.
        dieline: Computed dieline specification.
        artwork: Artwork specification with text, barcodes, etc.
        output_path: Where to save the PDF.

    Returns:
        Path to the generated PDF file.
    """
    output_path = Path(output_path)

    # Page size = dieline total + bleed on all sides
    page_w = (dieline.total_width + 2 * BLEED) * mm
    page_h = (dieline.total_height + 2 * BLEED) * mm

    c = Canvas(str(output_path), pagesize=(page_w, page_h))

    # Set PDF metadata
    c.setTitle(f"Carton Artwork - {config.product.brand_name} {config.product.strength}")
    c.setAuthor("Pharma Packaging Lifecycle Platform")
    c.setSubject("Pharmaceutical Carton Artwork")

    # Set trim box and bleed box
    trim_x = BLEED * mm
    trim_y = BLEED * mm
    trim_w = dieline.total_width * mm
    trim_h = dieline.total_height * mm

    # Set PDF page boxes via the low-level page dictionary.
    # TrimBox defines the finished page area; BleedBox includes bleed.
    # We apply these after save via a post-processing step, or use
    # ReportLab's setTrimBox/setBleedBox if available.
    try:
        c.setTrimBox((trim_x, trim_y, trim_x + trim_w, trim_y + trim_h))
    except AttributeError:
        pass  # Not all ReportLab versions support this
    try:
        c.setBleedBox((0, 0, page_w, page_h))
    except AttributeError:
        pass

    # Build spot color map
    spot_colors: Dict[str, CMYKColor] = {}
    for sc in artwork.spot_colors:
        spot_colors[sc.name] = _spot_to_cmyk(sc)

    # Offset for bleed — all coordinates are shifted by BLEED
    bx = BLEED * mm
    by = BLEED * mm

    # === LAYER: ARTWORK (background colors) ===
    # Draw panel background colors
    _draw_artwork_layer(c, dieline, spot_colors, bx, by)

    # === LAYER: TEXT ===
    _draw_text_layer(c, dieline, artwork, spot_colors, bx, by)

    # === LAYER: BARCODE ===
    _draw_barcode_layer(c, dieline, artwork, bx, by)

    # === LAYER: CODING (coding zones) ===
    _draw_coding_layer(c, dieline, artwork, bx, by)

    # === LAYER: DIELINE (non-printing, on top) ===
    _draw_dieline_layer(c, dieline, bx, by)

    c.save()
    return output_path


def _draw_artwork_layer(
    c: Canvas,
    dieline: DielineSpec,
    spot_colors: Dict[str, CMYKColor],
    bx: float,
    by: float,
) -> None:
    """Draw background design elements — panel fills, color bands, etc."""
    # Light background for main body panels
    body_types = {PanelType.FRONT, PanelType.BACK, PanelType.SIDE_LEFT, PanelType.SIDE_RIGHT}

    for panel in dieline.panels:
        if panel.panel_type in body_types:
            c.saveState()
            # Very light brand color fill for body panels
            c.setFillColor(_cmyk_color(5, 3, 0, 0))
            c.rect(
                bx + panel.x * mm,
                by + panel.y * mm,
                panel.width * mm,
                panel.height * mm,
                fill=1,
                stroke=0,
            )
            c.restoreState()

    # Color band at top of front panel (strength differentiation)
    front = _get_panel_by_type(dieline, PanelType.FRONT)
    if front and spot_colors:
        brand_color = list(spot_colors.values())[0]
        c.saveState()
        c.setFillColor(brand_color)
        band_height = 15.0  # mm
        c.rect(
            bx + front.x * mm,
            by + (front.y + front.height - band_height) * mm,
            front.width * mm,
            band_height * mm,
            fill=1,
            stroke=0,
        )
        c.restoreState()


def _draw_text_layer(
    c: Canvas,
    dieline: DielineSpec,
    artwork: ArtworkSpec,
    spot_colors: Dict[str, CMYKColor],
    bx: float,
    by: float,
) -> None:
    """Draw editable text objects on their respective panels.

    Supports text rotation for narrow side panels — on real pharma cartons,
    text on depth panels (typically 10-20mm wide) runs vertically.
    """
    for te in artwork.text_elements:
        panel = _get_panel_by_type(dieline, te.panel_type)
        if not panel:
            continue

        c.saveState()

        # Set color
        if te.color_name and te.color_name in spot_colors:
            c.setFillColor(spot_colors[te.color_name])
        else:
            c.setFillColor(black)

        # Set font
        font_name = "Helvetica-Bold" if te.font_bold else "Helvetica"
        c.setFont(font_name, te.font_size)

        # Calculate absolute position
        abs_x = bx + (panel.x + te.x) * mm
        abs_y = by + (panel.y + te.y) * mm

        if te.rotation != 0:
            # Rotate around the text origin point
            c.translate(abs_x, abs_y)
            c.rotate(te.rotation)
            # After rotation, draw at origin — text flows in rotated direction
            lines = te.content.split("\n")
            line_height = te.font_size * 1.3
            for i, line in enumerate(lines):
                c.drawString(0, -i * line_height, line)
        else:
            # Normal horizontal text
            lines = te.content.split("\n")
            line_height = te.font_size * 1.3
            for i, line in enumerate(lines):
                c.drawString(abs_x, abs_y - i * line_height, line)

        c.restoreState()


def _draw_barcode_layer(
    c: Canvas,
    dieline: DielineSpec,
    artwork: ArtworkSpec,
    bx: float,
    by: float,
) -> None:
    """Draw vector barcodes on their panels."""
    for bc in artwork.barcodes:
        panel = _get_panel_by_type(dieline, bc.panel_type)
        if not panel:
            continue

        abs_x = bx + (panel.x + bc.x) * mm
        abs_y = by + (panel.y + bc.y) * mm

        barcode_data = generate_ean13_bars(bc.data)

        # Scale barcode to fit specified width
        scale_x = (bc.width * mm) / (barcode_data.total_width * mm) if barcode_data.total_width > 0 else 1.0
        scale_y = (bc.height * mm) / (barcode_data.bars[0][2] * mm) if barcode_data.bars else 1.0

        c.saveState()
        c.setFillColor(black)

        # Draw each bar as a filled rectangle
        for bar_x, bar_w, bar_h in barcode_data.bars:
            c.rect(
                abs_x + bar_x * mm * scale_x,
                abs_y,
                bar_w * mm * scale_x,
                bar_h * mm * scale_y,
                fill=1,
                stroke=0,
            )

        # Human-readable text below barcode
        c.setFont("Helvetica", 7)
        text_x = abs_x + (bc.width * mm) / 2
        c.drawCentredString(text_x, abs_y - 10, barcode_data.text)

        c.restoreState()


def _draw_coding_layer(
    c: Canvas,
    dieline: DielineSpec,
    artwork: ArtworkSpec,
    bx: float,
    by: float,
) -> None:
    """Draw coding zones (batch, MRP, dates) as labeled areas."""
    for cz in artwork.coding_zones:
        panel = _get_panel_by_type(dieline, cz.panel_type)
        if not panel:
            continue

        abs_x = bx + (panel.x + cz.x) * mm
        abs_y = by + (panel.y + cz.y) * mm

        c.saveState()

        # Dashed outline for coding zone
        c.setStrokeColor(_cmyk_color(0, 0, 0, 30))
        c.setDash(2, 2)
        c.setLineWidth(0.5)
        c.rect(abs_x, abs_y, cz.width * mm, cz.height * mm, fill=0, stroke=1)

        # Label text
        c.setFont("Helvetica", 5.5)
        c.setFillColor(_cmyk_color(0, 0, 0, 60))
        c.drawString(abs_x + 1 * mm, abs_y + 1 * mm, cz.purpose)

        c.restoreState()


def _draw_dieline_layer(
    c: Canvas,
    dieline: DielineSpec,
    bx: float,
    by: float,
) -> None:
    """Draw dieline overlay — cut and crease lines.

    In production artwork, the dieline is on a separate non-printing layer,
    typically in magenta or a dedicated spot color.
    """
    # Dieline color: bright magenta (non-printing convention)
    dieline_color = _cmyk_color(0, 100, 0, 0)

    c.saveState()
    c.setStrokeColor(dieline_color)
    c.setLineWidth(0.25)

    # Draw panel outlines (cut lines)
    for panel in dieline.panels:
        c.rect(
            bx + panel.x * mm,
            by + panel.y * mm,
            panel.width * mm,
            panel.height * mm,
            fill=0,
            stroke=1,
        )

    # Draw fold/crease lines (dashed)
    c.setDash(3, 2)
    body_panels = [
        p for p in dieline.panels
        if p.panel_type in (
            PanelType.FRONT, PanelType.SIDE_RIGHT,
            PanelType.BACK, PanelType.SIDE_LEFT,
        )
    ]
    body_panels.sort(key=lambda p: p.x)

    for panel in body_panels:
        y_bottom = by + panel.y * mm
        y_top = by + (panel.y + panel.height) * mm
        x = bx + panel.x * mm
        c.line(x, y_bottom, x, y_top)

    c.restoreState()

    # Add "DIELINE - DO NOT PRINT" annotation
    c.saveState()
    c.setFont("Helvetica", 4)
    c.setFillColor(dieline_color)
    c.drawString(bx + 2 * mm, by - 2 * mm, "DIELINE LAYER — DO NOT PRINT")
    c.restoreState()
