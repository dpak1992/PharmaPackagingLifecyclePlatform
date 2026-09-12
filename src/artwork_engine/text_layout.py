"""Text layout utilities for panel-based pharmaceutical artwork.

Maps product data fields to text elements positioned on carton panels,
following Indian pharma packaging conventions.

On narrow side panels (depth panels), text is rotated 90° to run vertically,
which is standard practice for pharmaceutical cartons.
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
)


def generate_default_artwork(config: PackagingConfig) -> ArtworkSpec:
    """Generate a default artwork specification from a packaging configuration.

    Creates text elements, barcodes, and coding zones following standard
    Indian pharmaceutical carton layout conventions.
    """
    product = config.product
    brand_color = SpotColor(
        name="Brand Blue",
        cyan=100.0,
        magenta=58.0,
        yellow=0.0,
        black=7.0,
    )

    text_elements: List[TextElement] = []

    # --- PANEL 1 (FRONT) — wide panel, horizontal text ---
    text_elements.append(TextElement(
        id="front-brand",
        content=product.brand_name,
        source_field="product.brand_name",
        panel_type=PanelType.FRONT,
        x=5.0, y=90.0,
        font_size=18.0,
        font_bold=True,
        color_name=brand_color.name,
    ))

    text_elements.append(TextElement(
        id="front-strength",
        content=str(product.strength),
        source_field="product.strength",
        panel_type=PanelType.FRONT,
        x=5.0, y=75.0,
        font_size=14.0,
        font_bold=True,
        color_name=brand_color.name,
    ))

    text_elements.append(TextElement(
        id="front-generic",
        content=f"{product.generic_name} Tablets IP",
        source_field="product.generic_name",
        panel_type=PanelType.FRONT,
        x=5.0, y=62.0,
        font_size=10.0,
    ))

    text_elements.append(TextElement(
        id="front-packsize",
        content=f"{config.pack_size} Tablet{'s' if '10' in config.pack_size else ''}",
        source_field="config.pack_size",
        panel_type=PanelType.FRONT,
        x=5.0, y=50.0,
        font_size=9.0,
    ))

    text_elements.append(TextElement(
        id="front-rx",
        content="Rx",
        source_field="static",
        panel_type=PanelType.FRONT,
        x=5.0, y=105.0,
        font_size=14.0,
        font_bold=True,
    ))

    # --- PANEL 2 (SIDE RIGHT) — narrow panel, text rotated 90° ---
    text_elements.append(TextElement(
        id="side-composition",
        content=product.composition,
        source_field="product.composition",
        panel_type=PanelType.SIDE_RIGHT,
        x=12.0, y=5.0,
        font_size=5.0,
        rotation=90.0,
    ))

    text_elements.append(TextElement(
        id="side-storage",
        content=product.storage_conditions,
        source_field="product.storage_conditions",
        panel_type=PanelType.SIDE_RIGHT,
        x=4.0, y=5.0,
        font_size=5.0,
        rotation=90.0,
    ))

    # --- PANEL 3 (BACK) — wide panel, horizontal text ---
    mfg_text = (
        f"Mfd. by: {product.manufacturer.name}\n"
        f"{product.manufacturer.address}\n"
        f"Mfg. Lic. No.: {product.manufacturer.license_no}"
    )
    text_elements.append(TextElement(
        id="back-manufacturer",
        content=mfg_text,
        source_field="product.manufacturer",
        panel_type=PanelType.BACK,
        x=5.0, y=100.0,
        font_size=5.5,
    ))

    text_elements.append(TextElement(
        id="back-warning",
        content=product.schedule_warning,
        source_field="product.schedule_warning",
        panel_type=PanelType.BACK,
        x=5.0, y=10.0,
        font_size=5.0,
        font_bold=True,
    ))

    text_elements.append(TextElement(
        id="back-children",
        content="Keep out of reach of children.",
        source_field="static",
        panel_type=PanelType.BACK,
        x=5.0, y=5.0,
        font_size=5.0,
    ))

    # --- PANEL 4 (SIDE LEFT) — narrow panel, text rotated 90° ---
    text_elements.append(TextElement(
        id="side-left-brand",
        content=f"{product.brand_name} {product.strength}",
        source_field="product.brand_name",
        panel_type=PanelType.SIDE_LEFT,
        x=10.0, y=20.0,
        font_size=6.0,
        font_bold=True,
        color_name=brand_color.name,
        rotation=90.0,
    ))

    # --- BARCODES ---
    barcodes = [
        BarcodeElement(
            id="ean13",
            barcode_type=BarcodeType.EAN_13,
            data="890123456789",
            panel_type=PanelType.BACK,
            x=5.0, y=45.0,
            width=37.29,
            height=22.85,
        ),
    ]

    # --- CODING ZONES ---
    coding_zones = [
        CodingZone(
            id="batch-area",
            purpose="B.No.:",
            panel_type=PanelType.BACK,
            x=5.0, y=82.0,
            width=40.0, height=4.0,
        ),
        CodingZone(
            id="mfg-date",
            purpose="Mfg. Date:",
            panel_type=PanelType.BACK,
            x=5.0, y=77.0,
            width=30.0, height=4.0,
        ),
        CodingZone(
            id="exp-date",
            purpose="Exp. Date:",
            panel_type=PanelType.BACK,
            x=5.0, y=72.0,
            width=30.0, height=4.0,
        ),
    ]

    if config.mrp:
        # Replace ₹ with "Rs." for Helvetica compatibility
        mrp_display = config.mrp.replace("₹", "Rs.")
        coding_zones.append(CodingZone(
            id="mrp-area",
            purpose=f"MRP: {mrp_display} (Incl. of all taxes)",
            panel_type=PanelType.BACK,
            x=5.0, y=37.0,
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
        ],
    )
