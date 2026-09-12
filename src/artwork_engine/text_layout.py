"""Text layout utilities for panel-based pharmaceutical artwork.

Maps product data fields to text elements positioned on carton panels,
following real Indian pharma packaging conventions (Ventimox-250 style).

Layout convention for standard cartons (depth >= 25mm):
  FRONT panel  — Rx, generic name (large), brand name (bold, color), Hindi name, pack size
  BACK panel   — Same display content as FRONT (both shelf-facing panels identical)
  SIDE RIGHT   — All regulatory/composition text, manufacturer, marketer, warnings, barcode
  SIDE LEFT    — Coding zones (batch, dates, MRP), Mfg. Lic. No., marketer info, barcode

All side-panel text is HORIZONTAL (rotation=0) when the carton depth >= 25mm.
Only when depth < 25mm is text rotated 90° to fit the narrow panel.

Y coordinates are calculated as PERCENTAGES of panel height so the layout
scales correctly for any carton size.
"""
from __future__ import annotations

from typing import List

from packaging_model.models import (
    PackagingConfig,
    TextElement,
    BarcodeElement,
    CodingZone,
    ArtworkSpec,
    SpotColor,
)
from packaging_model.enums import (
    PanelType,
    BarcodeType,
    ArtworkStatus,
    LayerName,
    DosageForm,
)


_DOSAGE_FORM_LABELS = {
    DosageForm.TABLET: "Tablets IP",
    DosageForm.CAPSULE: "Capsules IP",
    DosageForm.FILM_COATED_TABLET: "Film Coated Tablets IP",
    DosageForm.CHEWABLE_TABLET: "Chewable Tablets IP",
    DosageForm.HARD_GELATIN_CAPSULE: "Capsules IP",
    DosageForm.SOFT_GELATIN_CAPSULE: "Soft Gelatin Capsules IP",
}

_NARROW_DEPTH_THRESHOLD = 25.0


def _pct(panel_dim: float, pct: float) -> float:
    """Convert a percentage (0-100) of a panel dimension to mm offset."""
    return panel_dim * pct / 100.0


def _hex_to_cmyk(hex_color: str) -> tuple:
    """Convert hex color to approximate CMYK percentages."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (100.0, 58.0, 0.0, 7.0)  # fallback blue
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    k = 1 - max(r, g, b)
    if k >= 1:
        return (0.0, 0.0, 0.0, 100.0)
    c = (1 - r - k) / (1 - k) * 100
    m = (1 - g - k) / (1 - k) * 100
    y = (1 - b - k) / (1 - k) * 100
    return (round(c, 1), round(m, 1), round(y, 1), round(k * 100, 1))


def generate_default_artwork(config: PackagingConfig) -> ArtworkSpec:
    """Generate artwork spec matching real Indian pharma carton conventions."""
    product = config.product

    # Convert org's brand color hex to CMYK for PDF
    c, m, y, k = _hex_to_cmyk(config.brand_color_hex)
    brand_color = SpotColor(
        name="Brand Color",
        cyan=c, magenta=m, yellow=y, black=k,
    )

    dosage_label = _DOSAGE_FORM_LABELS.get(product.dosage_form, "Tablets IP")
    generic_line = f"{product.generic_name} {dosage_label} {product.strength}"
    brand_line = f"{product.brand_name}-{int(product.strength.value)}"
    dosage_word = dosage_label.split()[0]  # "Capsules" or "Tablets"
    pack_line = f"{config.pack_size} {dosage_word}"

    # Panel dimensions for relative positioning
    carton = config.carton
    ph = carton.internal_length  # panel height (mm)
    pw = carton.internal_width   # front/back panel width (mm)
    sd = carton.internal_depth   # side panel width (mm)

    depth = carton.internal_depth
    side_rot = 90.0 if depth < _NARROW_DEPTH_THRESHOLD else 0.0

    text_elements: List[TextElement] = []

    # ===================================================================
    # Helper to create display face (used for FRONT and BACK)
    # Text positioned top-down using percentage of panel height
    # ===================================================================
    def add_display_face(prefix: str, panel: PanelType, brand_size: float = 16.0):
        # Rx — just below the brand color band (band is top 20%)
        text_elements.append(TextElement(
            id=f"{prefix}-rx",
            content="Rx",
            source_field="static",
            panel_type=panel,
            x=5.0, y=_pct(ph, 75),  # 75% up = just below 80% band bottom
            font_size=12.0, font_bold=True,
        ))
        # Generic name
        text_elements.append(TextElement(
            id=f"{prefix}-generic",
            content=generic_line,
            source_field="product.generic_name",
            panel_type=panel,
            x=5.0, y=_pct(ph, 65),
            font_size=10.0, font_bold=True,
        ))
        # Brand name
        text_elements.append(TextElement(
            id=f"{prefix}-brand",
            content=brand_line,
            source_field="product.brand_name",
            panel_type=panel,
            x=5.0, y=_pct(ph, 52),
            font_size=brand_size, font_bold=True,
            color_name=brand_color.name,
        ))
        # Hindi brand name
        if product.brand_name_hindi:
            text_elements.append(TextElement(
                id=f"{prefix}-brand-hindi",
                content=product.brand_name_hindi,
                source_field="product.brand_name_hindi",
                panel_type=panel,
                x=5.0, y=_pct(ph, 45),
                font_size=8.0,
            ))
        # Pack size at bottom
        text_elements.append(TextElement(
            id=f"{prefix}-packsize",
            content=pack_line,
            source_field="config.pack_size",
            panel_type=panel,
            x=5.0, y=_pct(ph, 5),
            font_size=8.0,
        ))

    add_display_face("front", PanelType.FRONT, brand_size=16.0)
    add_display_face("back", PanelType.BACK, brand_size=14.0)

    # ===================================================================
    # SIDE RIGHT — regulatory panel (top-down, horizontal text)
    # Y positions as % of panel height, starting from top
    # ===================================================================
    reg_x = 3.0  # mm left margin

    # Composition
    text_elements.append(TextElement(
        id="side-right-composition-heading",
        content="Composition:",
        source_field="static",
        panel_type=PanelType.SIDE_RIGHT,
        x=reg_x, y=_pct(ph, 92),
        font_size=6.0, font_bold=True, rotation=side_rot,
    ))
    text_elements.append(TextElement(
        id="side-right-composition",
        content=product.composition,
        source_field="product.composition",
        panel_type=PanelType.SIDE_RIGHT,
        x=reg_x, y=_pct(ph, 88),
        font_size=5.0, rotation=side_rot,
    ))

    # Dosage
    text_elements.append(TextElement(
        id="side-right-dosage",
        content="Dosage: As directed by the Physician.",
        source_field="static",
        panel_type=PanelType.SIDE_RIGHT,
        x=reg_x, y=_pct(ph, 75),
        font_size=5.0, rotation=side_rot,
    ))

    # Storage
    text_elements.append(TextElement(
        id="side-right-storage",
        content=product.storage_conditions,
        source_field="product.storage_conditions",
        panel_type=PanelType.SIDE_RIGHT,
        x=reg_x, y=_pct(ph, 68),
        font_size=5.0, rotation=side_rot,
    ))

    # Children warning
    text_elements.append(TextElement(
        id="side-right-children",
        content="Keep medicine out of reach of children.",
        source_field="static",
        panel_type=PanelType.SIDE_RIGHT,
        x=reg_x, y=_pct(ph, 60),
        font_size=5.0, rotation=side_rot,
    ))

    # Schedule H warning
    text_elements.append(TextElement(
        id="side-right-schedule",
        content=product.schedule_warning,
        source_field="product.schedule_warning",
        panel_type=PanelType.SIDE_RIGHT,
        x=reg_x, y=_pct(ph, 52),
        font_size=5.5, font_bold=True, rotation=side_rot,
    ))

    # Manufacturer
    mfg_lines = [
        "Manufactured in India by:",
        product.manufacturer.name,
        product.manufacturer.address,
        f"Mfg. Lic. No.: {product.manufacturer.license_no}",
    ]
    if product.marketer:
        mfg_lines += ["", "Marketed by:", product.marketer.name, product.marketer.address]

    text_elements.append(TextElement(
        id="side-right-manufacturer",
        content="\n".join(mfg_lines),
        source_field="product.manufacturer",
        panel_type=PanelType.SIDE_RIGHT,
        x=reg_x, y=_pct(ph, 38),
        font_size=5.0, rotation=side_rot,
    ))

    # ===================================================================
    # SIDE LEFT — coding panel (top-down)
    # ===================================================================
    code_x = 3.0

    # Mfg. Lic. No. at top
    text_elements.append(TextElement(
        id="side-left-license",
        content=f"Mfg. Lic. No.: {product.manufacturer.license_no}",
        source_field="product.manufacturer.license_no",
        panel_type=PanelType.SIDE_LEFT,
        x=code_x, y=_pct(ph, 92),
        font_size=5.0, rotation=side_rot,
    ))

    # Marketer at bottom of side left
    if product.marketer:
        text_elements.append(TextElement(
            id="side-left-marketer",
            content=f"Marketed by:\n{product.marketer.name}\n{product.marketer.address}",
            source_field="product.marketer",
            panel_type=PanelType.SIDE_LEFT,
            x=code_x, y=_pct(ph, 20),
            font_size=5.0, rotation=side_rot,
        ))

    # ===================================================================
    # BARCODES — on side right (regulatory panel)
    # ===================================================================
    barcodes = [
        BarcodeElement(
            id="ean13",
            barcode_type=BarcodeType.EAN_13,
            data="4006381333931",
            panel_type=PanelType.SIDE_RIGHT,
            x=3.0, y=_pct(ph, 5),
            width=37.29, height=22.85,
        ),
    ]

    # ===================================================================
    # CODING ZONES — on side left
    # ===================================================================
    coding_zones = [
        CodingZone(
            id="batch-area", purpose="B.No.:",
            panel_type=PanelType.SIDE_LEFT,
            x=code_x, y=_pct(ph, 80),
            width=min(sd - 6, 40.0), height=5.0,
        ),
        CodingZone(
            id="mfg-date", purpose="Mfg. Date:",
            panel_type=PanelType.SIDE_LEFT,
            x=code_x, y=_pct(ph, 73),
            width=min(sd - 6, 35.0), height=5.0,
        ),
        CodingZone(
            id="exp-date", purpose="Exp. Date:",
            panel_type=PanelType.SIDE_LEFT,
            x=code_x, y=_pct(ph, 66),
            width=min(sd - 6, 35.0), height=5.0,
        ),
    ]

    if config.mrp:
        mrp_display = config.mrp.replace("\u20b9", "Rs.")
        coding_zones.append(CodingZone(
            id="mrp-area",
            purpose=f"MRP: {mrp_display} (Incl. of all taxes)",
            panel_type=PanelType.SIDE_LEFT,
            x=code_x, y=_pct(ph, 58),
            width=min(sd - 6, 45.0), height=5.0,
        ))

    return ArtworkSpec(
        id=f"ART-{config.product.id}",
        version="1.0",
        status=ArtworkStatus.DRAFT,
        text_elements=text_elements,
        barcodes=barcodes,
        coding_zones=coding_zones,
        spot_colors=[brand_color],
        layers=[
            LayerName.DIELINE, LayerName.ARTWORK, LayerName.TEXT,
            LayerName.BARCODE, LayerName.CODING, LayerName.VARNISH,
            LayerName.TECHNICAL,
        ],
    )
