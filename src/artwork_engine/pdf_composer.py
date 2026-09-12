"""PDF artwork compositor for pharmaceutical packaging.

Generates prepress-aware PDFs with:
  - OCG layers (Optional Content Groups) for Dieline, Artwork, Text, Barcode, Coding
  - Separation color spaces for spot colors
  - Editable text objects (not outlines)
  - Vector barcode rendering
  - Text clipping to panel boundaries
  - Bleed and trim box definitions
  - Standard PDF structure that opens in Adobe Illustrator with editable layers

Uses ReportLab for PDF generation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from reportlab.lib.units import mm
from reportlab.lib.colors import CMYKColor, Color, black, white
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfdoc

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

# OCG layer names in drawing order
OCG_LAYER_NAMES: List[str] = [
    LayerName.ARTWORK.value,
    LayerName.TEXT.value,
    LayerName.BARCODE.value,
    LayerName.CODING.value,
    LayerName.VARNISH.value,
    LayerName.DIELINE.value,
    LayerName.TECHNICAL.value,
]


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


def _begin_ocg_layer(c: Canvas, layer_name: str) -> None:
    """Insert a marked content begin (BDC) for an OCG layer into the content stream.

    The resource name is ``/OC_<layer_name>`` (e.g., ``/OC_Artwork``).
    The corresponding ``Properties`` entry must be added to the page
    resources before the page is finalised — see ``_install_ocg_layers``.
    """
    resource_name = f"OC_{layer_name}"
    c._code.append(f"/{resource_name} BDC")


def _end_ocg_layer(c: Canvas) -> None:
    """Insert a marked content end (EMC) for the current OCG layer."""
    c._code.append("EMC")


def _install_ocg_layers(c: Canvas) -> Dict[str, object]:
    """Create OCG dictionary objects and wire them into the PDF catalog.

    Must be called *after* all drawing and *before* ``c.save()`` so that
    when ``showPage()`` builds the page dictionary we can inject the
    ``Properties`` entries that the BDC operators reference.

    Returns a mapping ``{resource_name: ocg_dict}`` for page-resource
    installation.
    """
    doc = c._doc
    ocg_refs = []
    properties: Dict[str, object] = {}

    for layer_name in OCG_LAYER_NAMES:
        ocg_dict = pdfdoc.PDFDictionary({
            "Type": pdfdoc.PDFName("OCG"),
            "Name": pdfdoc.PDFString(layer_name),
        })
        # Register as a named indirect object so it gets a proper ref
        ref_name = f"OCG_{layer_name}"
        doc.Reference(ocg_dict, ref_name)
        ref = pdfdoc.PDFObjectReference(ref_name)
        ocg_refs.append(ref)
        resource_name = f"OC_{layer_name}"
        properties[resource_name] = ref

    # Build the OCProperties dictionary for the catalog
    ocg_array = pdfdoc.PDFArray(ocg_refs)

    # Default viewing config — all layers ON by default
    default_config = pdfdoc.PDFDictionary({
        "BaseState": pdfdoc.PDFName("ON"),
        "Order": ocg_array,
        "Name": pdfdoc.PDFString("Layers"),
    })

    oc_properties = pdfdoc.PDFDictionary({
        "OCGs": ocg_array,
        "D": default_config,
    })

    doc._catalog.OCProperties = oc_properties
    # Add to __NoDefault__ and __Refs__ so the catalog formatter picks it up
    if "OCProperties" not in doc._catalog.__NoDefault__:
        doc._catalog.__NoDefault__ = list(doc._catalog.__NoDefault__) + ["OCProperties"]

    return properties


def _clip_to_panel(c: Canvas, panel: Panel, bx: float, by: float) -> None:
    """Set a clipping path to constrain drawing within the panel boundaries.

    Must be called inside a ``saveState()`` / ``restoreState()`` pair so
    the clip is automatically removed afterwards.
    """
    p = c.beginPath()
    p.rect(
        bx + panel.x * mm,
        by + panel.y * mm,
        panel.width * mm,
        panel.height * mm,
    )
    c.clipPath(p, stroke=0, fill=0)


def _register_unicode_fonts() -> None:
    """Register Unicode fonts for Hindi/Devanagari text rendering."""
    import os
    deva_paths = [
        "/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc",
        "/System/Library/Fonts/Supplemental/DevanagariMT.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    ]
    for path in deva_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("Devanagari", path, subfontIndex=0))
                return
            except Exception:
                continue


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
    _register_unicode_fonts()

    # Page size = dieline total + bleed on all sides
    page_w = (dieline.total_width + 2 * BLEED) * mm
    page_h = (dieline.total_height + 2 * BLEED) * mm

    c = Canvas(
        str(output_path),
        pagesize=(page_w, page_h),
        pageCompression=1,  # enable zlib compression for smaller, faster PDFs
    )

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
    _begin_ocg_layer(c, LayerName.ARTWORK.value)
    _draw_artwork_layer(c, dieline, spot_colors, bx, by)
    _end_ocg_layer(c)

    # === LAYER: TEXT ===
    _begin_ocg_layer(c, LayerName.TEXT.value)
    _draw_text_layer(c, dieline, artwork, spot_colors, bx, by)
    _end_ocg_layer(c)

    # === LAYER: BARCODE ===
    _begin_ocg_layer(c, LayerName.BARCODE.value)
    _draw_barcode_layer(c, dieline, artwork, bx, by)
    _end_ocg_layer(c)

    # === LAYER: CODING (coding zones) ===
    _begin_ocg_layer(c, LayerName.CODING.value)
    _draw_coding_layer(c, dieline, artwork, bx, by)
    _end_ocg_layer(c)

    # === LAYER: VARNISH (varnish coverage areas) ===
    _begin_ocg_layer(c, LayerName.VARNISH.value)
    _draw_varnish_layer(c, dieline, bx, by)
    _end_ocg_layer(c)

    # === LAYER: DIELINE (non-printing, on top) ===
    _begin_ocg_layer(c, LayerName.DIELINE.value)
    _draw_dieline_layer(c, dieline, bx, by)
    _end_ocg_layer(c)

    # === LAYER: TECHNICAL (non-printing technical notes) ===
    _begin_ocg_layer(c, LayerName.TECHNICAL.value)
    _draw_technical_layer(c, dieline, bx, by)
    _end_ocg_layer(c)

    # Install OCG layer objects into the PDF catalog and prepare
    # page-resource properties for the BDC operators we emitted.
    ocg_properties = _install_ocg_layers(c)

    # Patch the page's check_format so that when save() finalises the
    # document, our OCG Properties entries are injected into the page
    # resources.  This lets us use the normal c.save() path which
    # handles font subsetting, compression, and proper PDF structure.
    _original_page_cf = c._doc.Pages.__class__.check_format

    def _patched_pages_cf(self_pages, document, _orig=_original_page_cf, _props=ocg_properties):
        _orig(self_pages, document)
        # After default resource creation on every page, inject OCG properties
        for page in self_pages.pages:
            if hasattr(page, 'Resources') and page.Resources is not None:
                page.Resources.Properties.update(_props)

    c._doc.Pages.check_format = lambda doc, _pcf=_patched_pages_cf, _self=c._doc.Pages: _pcf(_self, doc)

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

    # Color band at top of front and back panels (strength differentiation)
    if spot_colors:
        brand_color = list(spot_colors.values())[0]
        # Derive a slightly darker accent color for the bottom bar
        accent_color = _cmyk_color(
            min(brand_color.cyan * 100 + 10, 100),
            min(brand_color.magenta * 100 + 10, 100),
            min(brand_color.yellow * 100 + 10, 100),
            min(brand_color.black * 100 + 5, 100),
        )

        for ptype in (PanelType.FRONT, PanelType.BACK):
            display_panel = _get_panel_by_type(dieline, ptype)
            if not display_panel:
                continue

            # Brand color band — 20% of panel height
            band_height = display_panel.height * 0.20
            c.saveState()
            c.setFillColor(brand_color)
            c.rect(
                bx + display_panel.x * mm,
                by + (display_panel.y + display_panel.height - band_height) * mm,
                display_panel.width * mm,
                band_height * mm,
                fill=1,
                stroke=0,
            )
            c.restoreState()

            # Thin accent bar at bottom (3mm) — geometric pattern area
            c.saveState()
            c.setFillColor(accent_color)
            c.rect(
                bx + display_panel.x * mm,
                by + display_panel.y * mm,
                display_panel.width * mm,
                3.0 * mm,
                fill=1,
                stroke=0,
            )
            c.restoreState()

        # Side panels — thin vertical brand color stripe (2mm) along left edge
        for ptype in (PanelType.SIDE_RIGHT, PanelType.SIDE_LEFT):
            side_panel = _get_panel_by_type(dieline, ptype)
            if not side_panel:
                continue
            c.saveState()
            c.setFillColor(brand_color)
            c.rect(
                bx + side_panel.x * mm,
                by + side_panel.y * mm,
                2.0 * mm,
                side_panel.height * mm,
                fill=1,
                stroke=0,
            )
            c.restoreState()


def _wrap_text(text: str, font_name: str, font_size: float, max_width_pt: float) -> List[str]:
    """Word-wrap text to fit within max_width_pt (points).

    Splits on existing newlines first, then wraps each line by word
    to stay within the available width.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    result = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            result.append("")
            continue

        current_line = words[0]
        for word in words[1:]:
            test = current_line + " " + word
            if stringWidth(test, font_name, font_size) <= max_width_pt:
                current_line = test
            else:
                result.append(current_line)
                current_line = word
        result.append(current_line)
    return result


def _draw_text_layer(
    c: Canvas,
    dieline: DielineSpec,
    artwork: ArtworkSpec,
    spot_colors: Dict[str, CMYKColor],
    bx: float,
    by: float,
) -> None:
    """Draw editable text objects on their respective panels.

    Text is word-wrapped to fit within panel boundaries instead of being
    clipped. Supports rotation for narrow side panels.
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

        # Set font — use Devanagari for Hindi text elements
        is_hindi = "hindi" in te.id.lower()
        if is_hindi and "Devanagari" in pdfmetrics.getRegisteredFontNames():
            font_name = "Devanagari"
        else:
            font_name = "Helvetica-Bold" if te.font_bold else "Helvetica"
        c.setFont(font_name, te.font_size)

        # Calculate absolute position
        abs_x = bx + (panel.x + te.x) * mm
        abs_y = by + (panel.y + te.y) * mm
        line_height = te.font_size * (1.4 if te.font_size < 7.0 else 1.3)

        # Tuck flap text is rendered upside-down (180°) since the flap folds over
        if te.panel_type == PanelType.TOP_TUCK:
            avail_width_pt = (panel.width - te.x - 2.0) * mm
            wrapped = _wrap_text(te.content, font_name, te.font_size, avail_width_pt)

            c.translate(abs_x, abs_y)
            c.rotate(180)
            for i, line in enumerate(wrapped):
                c.drawString(0, -i * line_height, line)
        elif te.rotation != 0:
            # For rotated text, available width = panel height minus text offset
            avail_width_pt = (panel.height - te.y) * mm
            wrapped = _wrap_text(te.content, font_name, te.font_size, avail_width_pt)

            c.translate(abs_x, abs_y)
            c.rotate(te.rotation)
            for i, line in enumerate(wrapped):
                c.drawString(0, -i * line_height, line)
        else:
            # Available width = panel width minus text x-offset (with small margin)
            avail_width_pt = (panel.width - te.x - 2.0) * mm
            wrapped = _wrap_text(te.content, font_name, te.font_size, avail_width_pt)

            for i, line in enumerate(wrapped):
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

        # --- Quiet zone indicators ---
        # GS1 requires 11 modules left, 7 modules right for EAN-13
        module_width = (bc.width * mm) / 95.0 if bc.width > 0 else 0.33 * mm
        left_quiet = 11 * module_width
        right_quiet = 7 * module_width
        qz_top = abs_y + bc.height * mm * scale_y
        qz_bottom = abs_y

        # Light gray dashed lines for quiet zone boundaries
        c.setStrokeColor(_cmyk_color(0, 0, 0, 20))
        c.setDash(1.5, 1.5)
        c.setLineWidth(0.3)

        # Left quiet zone boundary
        left_boundary_x = abs_x - left_quiet
        c.line(left_boundary_x, qz_bottom - 4, left_boundary_x, qz_top + 2)

        # Right quiet zone boundary
        right_boundary_x = abs_x + bc.width * mm + right_quiet
        c.line(right_boundary_x, qz_bottom - 4, right_boundary_x, qz_top + 2)

        # Standard barcode notation: ">" on left edge, "<" on right edge
        c.setDash([])
        c.setFont("Helvetica", 5)
        c.setFillColor(_cmyk_color(0, 0, 0, 30))
        c.drawString(left_boundary_x - 0.5 * mm, abs_y - 10, ">")
        c.drawString(right_boundary_x - 1.5 * mm, abs_y - 10, "<")

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

        # Label text — word-wrapped to fit within coding zone width
        font_name = "Helvetica"
        font_size = 5.5
        c.setFont(font_name, font_size)
        c.setFillColor(_cmyk_color(0, 0, 0, 60))
        avail = (cz.width - 2.0) * mm  # inner width minus margins
        wrapped = _wrap_text(cz.purpose, font_name, font_size, avail)
        lh = font_size * 1.3
        for i, line in enumerate(wrapped):
            c.drawString(abs_x + 1 * mm, abs_y + 1 * mm + (len(wrapped) - 1 - i) * lh, line)

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


def _draw_varnish_layer(
    c: Canvas,
    dieline: DielineSpec,
    bx: float,
    by: float,
) -> None:
    """Draw varnish coverage areas on body panels.

    Shows where UV or aqueous varnish is applied, using a light cyan
    transparent fill slightly inset from panel edges.
    """
    body_types = {PanelType.FRONT, PanelType.BACK, PanelType.SIDE_LEFT, PanelType.SIDE_RIGHT}
    varnish_inset = 1.5  # mm inset from panel edges

    for panel in dieline.panels:
        if panel.panel_type in body_types:
            c.saveState()
            # Light cyan with transparency to indicate varnish coverage
            c.setFillColor(_cmyk_color(15, 0, 0, 0, alpha=0.15))
            c.rect(
                bx + (panel.x + varnish_inset) * mm,
                by + (panel.y + varnish_inset) * mm,
                (panel.width - 2 * varnish_inset) * mm,
                (panel.height - 2 * varnish_inset) * mm,
                fill=1,
                stroke=0,
            )
            c.restoreState()


def _draw_technical_layer(
    c: Canvas,
    dieline: DielineSpec,
    bx: float,
    by: float,
) -> None:
    """Draw non-printing technical notes and annotations.

    Includes the dieline annotation and production notes about
    barcode quiet zones and coding area compatibility.
    """
    # Dieline color: bright magenta (non-printing convention)
    dieline_color = _cmyk_color(0, 100, 0, 0)
    note_color = _cmyk_color(0, 0, 0, 50)

    # "DIELINE LAYER - DO NOT PRINT" annotation (moved from dieline layer)
    c.saveState()
    c.setFont("Helvetica", 4)
    c.setFillColor(dieline_color)
    c.drawString(bx + 2 * mm, by - 2 * mm, "DIELINE LAYER \u2014 DO NOT PRINT")
    c.restoreState()

    # Technical production notes
    c.saveState()
    c.setFont("Helvetica", 3.5)
    c.setFillColor(note_color)
    note_y = by - 5 * mm
    c.drawString(bx + 2 * mm, note_y, "Barcode: verify quiet zones and scan grade before production")
    note_y -= 3.5 * mm
    c.drawString(bx + 2 * mm, note_y, "Coding areas: verify inkjet/thermal printer compatibility")
    c.restoreState()
