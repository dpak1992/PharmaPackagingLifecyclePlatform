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


# Map dosage form enum to display label for generic name line
_DOSAGE_FORM_LABELS = {
    DosageForm.TABLET: "Tablets IP",
    DosageForm.CAPSULE: "Capsules IP",
    DosageForm.FILM_COATED_TABLET: "Film Coated Tablets IP",
    DosageForm.CHEWABLE_TABLET: "Chewable Tablets IP",
    DosageForm.HARD_GELATIN_CAPSULE: "Capsules IP",
    DosageForm.SOFT_GELATIN_CAPSULE: "Soft Gelatin Capsules IP",
}

# Narrow-panel threshold: below this depth (mm), side panel text is rotated 90°
_NARROW_DEPTH_THRESHOLD = 25.0


def generate_default_artwork(config: PackagingConfig) -> ArtworkSpec:
    """Generate a default artwork specification from a packaging configuration.

    Creates text elements, barcodes, and coding zones following standard
    Indian pharmaceutical carton layout conventions based on real production
    artwork (Ventimox-250 reference).

    Panel assignment:
      FRONT / BACK — identical brand display (Rx, generic, brand, Hindi, pack size)
      SIDE_RIGHT   — all regulatory text (composition, storage, dosage, warnings,
                     manufacturer, marketer, Schedule H) + barcode
      SIDE_LEFT    — coding zones (batch, dates, MRP) + Mfg. Lic. No. + marketer

    Side-panel rotation is determined by carton depth:
      depth >= 25mm → horizontal text (rotation=0)
      depth <  25mm → vertical text (rotation=90)
    """
    product = config.product
    brand_color = SpotColor(
        name="Brand Blue",
        cyan=100.0,
        magenta=58.0,
        yellow=0.0,
        black=7.0,
    )

    dosage_label = _DOSAGE_FORM_LABELS.get(product.dosage_form, "Tablets IP")
    generic_line = f"{product.generic_name} {dosage_label} {product.strength}"

    # Determine side-panel text rotation based on carton depth
    depth = config.carton.internal_depth
    side_rotation = 90.0 if depth < _NARROW_DEPTH_THRESHOLD else 0.0

    text_elements: List[TextElement] = []

    # ===================================================================
    # FRONT PANEL — brand display face (width panel, horizontal text)
    # ===================================================================
    # Rx symbol (top left)
    text_elements.append(TextElement(
        id="front-rx",
        content="Rx",
        source_field="static",
        panel_type=PanelType.FRONT,
        x=5.0, y=105.0,
        font_size=12.0,
        font_bold=True,
    ))

    # Generic name line (prominent per Indian regulation)
    text_elements.append(TextElement(
        id="front-generic",
        content=generic_line,
        source_field="product.generic_name",
        panel_type=PanelType.FRONT,
        x=5.0, y=92.0,
        font_size=10.0,
        font_bold=True,
    ))

    # Brand name — large, bold, brand color
    text_elements.append(TextElement(
        id="front-brand",
        content=f"{product.brand_name}-{int(product.strength.value)}",
        source_field="product.brand_name",
        panel_type=PanelType.FRONT,
        x=5.0, y=78.0,
        font_size=16.0,
        font_bold=True,
        color_name=brand_color.name,
    ))

    # Hindi brand name (if provided)
    if product.brand_name_hindi:
        text_elements.append(TextElement(
            id="front-brand-hindi",
            content=product.brand_name_hindi,
            source_field="product.brand_name_hindi",
            panel_type=PanelType.FRONT,
            x=5.0, y=67.0,
            font_size=9.0,
            font_bold=False,
        ))

    # Pack size at bottom
    text_elements.append(TextElement(
        id="front-packsize",
        content=f"{config.pack_size} {dosage_label.split()[0]}s",
        source_field="config.pack_size",
        panel_type=PanelType.FRONT,
        x=5.0, y=10.0,
        font_size=8.0,
    ))

    # ===================================================================
    # BACK PANEL — identical to FRONT (both shelf-facing panels show
    # the same brand display, which is standard Indian pharma practice)
    # ===================================================================
    # Rx symbol
    text_elements.append(TextElement(
        id="back-rx",
        content="Rx",
        source_field="static",
        panel_type=PanelType.BACK,
        x=5.0, y=105.0,
        font_size=12.0,
        font_bold=True,
    ))

    # Generic name repeated on back
    text_elements.append(TextElement(
        id="back-generic",
        content=generic_line,
        source_field="product.generic_name",
        panel_type=PanelType.BACK,
        x=5.0, y=92.0,
        font_size=10.0,
        font_bold=True,
    ))

    # Brand name on back
    text_elements.append(TextElement(
        id="back-brand",
        content=f"{product.brand_name}-{int(product.strength.value)}",
        source_field="product.brand_name",
        panel_type=PanelType.BACK,
        x=5.0, y=78.0,
        font_size=14.0,
        font_bold=True,
        color_name=brand_color.name,
    ))

    # Hindi brand name on back
    if product.brand_name_hindi:
        text_elements.append(TextElement(
            id="back-brand-hindi",
            content=product.brand_name_hindi,
            source_field="product.brand_name_hindi",
            panel_type=PanelType.BACK,
            x=5.0, y=67.0,
            font_size=8.0,
        ))

    # Pack size on back
    text_elements.append(TextElement(
        id="back-packsize",
        content=f"{config.pack_size} {dosage_label.split()[0]}s",
        source_field="config.pack_size",
        panel_type=PanelType.BACK,
        x=5.0, y=10.0,
        font_size=8.0,
    ))

    # ===================================================================
    # SIDE RIGHT PANEL — all regulatory/composition text (horizontal)
    # This is the primary regulatory information panel.
    # ===================================================================
    # Y positions run top-to-bottom within the panel height (~195mm)
    # Using small fonts (5.0-5.5pt body, 6pt headings) to fit 56mm width

    # Composition heading + text
    text_elements.append(TextElement(
        id="side-right-composition-heading",
        content="Composition:",
        source_field="static",
        panel_type=PanelType.SIDE_RIGHT,
        x=3.0, y=185.0,
        font_size=6.0,
        font_bold=True,
        rotation=side_rotation,
    ))

    text_elements.append(TextElement(
        id="side-right-composition",
        content=product.composition,
        source_field="product.composition",
        panel_type=PanelType.SIDE_RIGHT,
        x=3.0, y=178.0,
        font_size=5.0,
        rotation=side_rotation,
    ))

    # Dosage instruction
    text_elements.append(TextElement(
        id="side-right-dosage",
        content="Dosage: As directed by the Physician.",
        source_field="static",
        panel_type=PanelType.SIDE_RIGHT,
        x=3.0, y=165.0,
        font_size=5.0,
        rotation=side_rotation,
    ))

    # Storage conditions
    text_elements.append(TextElement(
        id="side-right-storage",
        content=product.storage_conditions,
        source_field="product.storage_conditions",
        panel_type=PanelType.SIDE_RIGHT,
        x=3.0, y=155.0,
        font_size=5.0,
        rotation=side_rotation,
    ))

    # Keep out of reach of children
    text_elements.append(TextElement(
        id="side-right-children",
        content="Keep medicine out of reach of children.",
        source_field="static",
        panel_type=PanelType.SIDE_RIGHT,
        x=3.0, y=145.0,
        font_size=5.0,
        rotation=side_rotation,
    ))

    # Schedule H warning (bold)
    text_elements.append(TextElement(
        id="side-right-schedule",
        content=product.schedule_warning,
        source_field="product.schedule_warning",
        panel_type=PanelType.SIDE_RIGHT,
        x=3.0, y=130.0,
        font_size=5.5,
        font_bold=True,
        rotation=side_rotation,
    ))

    # Manufacturer info
    mfg_lines = [
        "Manufactured in India by:",
        product.manufacturer.name,
        product.manufacturer.address,
        f"Mfg. Lic. No.: {product.manufacturer.license_no}",
    ]
    text_elements.append(TextElement(
        id="side-right-manufacturer",
        content="\n".join(mfg_lines),
        source_field="product.manufacturer",
        panel_type=PanelType.SIDE_RIGHT,
        x=3.0, y=105.0,
        font_size=5.0,
        rotation=side_rotation,
    ))

    # Marketer info (if different from manufacturer)
    if product.marketer:
        marketer_lines = [
            "Marketed by:",
            product.marketer.name,
            product.marketer.address,
        ]
        text_elements.append(TextElement(
            id="side-right-marketer",
            content="\n".join(marketer_lines),
            source_field="product.marketer",
            panel_type=PanelType.SIDE_RIGHT,
            x=3.0, y=80.0,
            font_size=5.0,
            rotation=side_rotation,
        ))

    # ===================================================================
    # SIDE LEFT PANEL — coding zones + Mfg. Lic. No. + marketer
    # ===================================================================

    # Mfg. Lic. No. at top
    text_elements.append(TextElement(
        id="side-left-license",
        content=f"Mfg. Lic. No.: {product.manufacturer.license_no}",
        source_field="product.manufacturer.license_no",
        panel_type=PanelType.SIDE_LEFT,
        x=3.0, y=185.0,
        font_size=5.0,
        rotation=side_rotation,
    ))

    # Marketer info on side left (if present)
    if product.marketer:
        marketer_lines_left = [
            "Marketed by:",
            product.marketer.name,
            product.marketer.address,
        ]
        text_elements.append(TextElement(
            id="side-left-marketer",
            content="\n".join(marketer_lines_left),
            source_field="product.marketer",
            panel_type=PanelType.SIDE_LEFT,
            x=3.0, y=30.0,
            font_size=5.0,
            rotation=side_rotation,
        ))

    # ===================================================================
    # BARCODES — on SIDE RIGHT panel (regulatory panel)
    # ===================================================================
    barcodes = [
        BarcodeElement(
            id="ean13",
            barcode_type=BarcodeType.EAN_13,
            data="4006381333931",
            panel_type=PanelType.SIDE_RIGHT,
            x=3.0, y=40.0,
            width=37.29,
            height=22.85,
        ),
    ]

    # ===================================================================
    # CODING ZONES — on SIDE LEFT panel
    # ===================================================================
    coding_zones = [
        CodingZone(
            id="batch-area",
            purpose="B.No.:",
            panel_type=PanelType.SIDE_LEFT,
            x=3.0, y=165.0,
            width=40.0, height=4.0,
        ),
        CodingZone(
            id="mfg-date",
            purpose="Mfg. Date:",
            panel_type=PanelType.SIDE_LEFT,
            x=3.0, y=155.0,
            width=30.0, height=4.0,
        ),
        CodingZone(
            id="exp-date",
            purpose="Exp. Date:",
            panel_type=PanelType.SIDE_LEFT,
            x=3.0, y=145.0,
            width=30.0, height=4.0,
        ),
    ]

    if config.mrp:
        mrp_display = config.mrp.replace("\u20b9", "Rs.")
        coding_zones.append(CodingZone(
            id="mrp-area",
            purpose=f"MRP: {mrp_display} (Incl. of all taxes)",
            panel_type=PanelType.SIDE_LEFT,
            x=3.0, y=135.0,
            width=45.0, height=5.0,
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
            LayerName.DIELINE,
            LayerName.ARTWORK,
            LayerName.TEXT,
            LayerName.BARCODE,
            LayerName.CODING,
            LayerName.VARNISH,
            LayerName.TECHNICAL,
        ],
    )
