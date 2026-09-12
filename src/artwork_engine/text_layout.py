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


def generate_default_artwork(config: PackagingConfig) -> ArtworkSpec:
    """Generate a default artwork specification from a packaging configuration.

    Creates text elements, barcodes, and coding zones following standard
    Indian pharmaceutical carton layout conventions. Supports bilingual
    text (English + Hindi), manufacturer/marketer distinction, and
    multi-blister pack configurations.
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

    text_elements: List[TextElement] = []

    # --- PANEL 1 (FRONT) — wide panel, horizontal text ---
    # Rx symbol
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

    # Pack size
    text_elements.append(TextElement(
        id="front-packsize",
        content=f"{config.pack_size} {dosage_label.split()[0]}s",
        source_field="config.pack_size",
        panel_type=PanelType.FRONT,
        x=5.0, y=10.0,
        font_size=8.0,
    ))

    # --- PANEL 2 (SIDE RIGHT) — narrow panel, rotated text ---
    # Composition
    text_elements.append(TextElement(
        id="side-composition",
        content=product.composition,
        source_field="product.composition",
        panel_type=PanelType.SIDE_RIGHT,
        x=12.0, y=5.0,
        font_size=4.5,
        rotation=90.0,
    ))

    # Storage conditions
    text_elements.append(TextElement(
        id="side-storage",
        content=product.storage_conditions,
        source_field="product.storage_conditions",
        panel_type=PanelType.SIDE_RIGHT,
        x=4.0, y=5.0,
        font_size=4.5,
        rotation=90.0,
    ))

    # --- PANEL 3 (BACK) — wide panel, horizontal text ---
    # Generic name repeated on back
    text_elements.append(TextElement(
        id="back-generic",
        content=generic_line,
        source_field="product.generic_name",
        panel_type=PanelType.BACK,
        x=5.0, y=105.0,
        font_size=10.0,
        font_bold=True,
    ))

    # Brand name on back
    text_elements.append(TextElement(
        id="back-brand",
        content=f"{product.brand_name}-{int(product.strength.value)}",
        source_field="product.brand_name",
        panel_type=PanelType.BACK,
        x=5.0, y=92.0,
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
            x=5.0, y=83.0,
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

    # Manufacturer info on back side
    mfg_lines = [
        f"Manufactured in India by:",
        f"{product.manufacturer.name}",
        f"{product.manufacturer.address}",
        f"Mfg. Lic. No.: {product.manufacturer.license_no}",
    ]
    # Marketer info (if different from manufacturer)
    if product.marketer:
        mfg_lines.append("")
        mfg_lines.append("Marketed by:")
        mfg_lines.append(product.marketer.name)
        mfg_lines.append(product.marketer.address)

    text_elements.append(TextElement(
        id="back-manufacturer",
        content="\n".join(mfg_lines),
        source_field="product.manufacturer",
        panel_type=PanelType.BACK,
        x=5.0, y=70.0,
        font_size=5.0,
    ))

    # Schedule warning
    text_elements.append(TextElement(
        id="back-warning",
        content=product.schedule_warning,
        source_field="product.schedule_warning",
        panel_type=PanelType.BACK,
        x=5.0, y=15.0,
        font_size=4.5,
        font_bold=True,
    ))

    # Keep out of reach
    text_elements.append(TextElement(
        id="back-children",
        content="Keep medicine out of reach of children.",
        source_field="static",
        panel_type=PanelType.BACK,
        x=5.0, y=5.0,
        font_size=4.5,
    ))

    # --- PANEL 4 (SIDE LEFT) — narrow panel, rotated text ---
    # Brand name repeated for shelf identification
    text_elements.append(TextElement(
        id="side-left-brand",
        content=f"{product.brand_name}-{int(product.strength.value)}",
        source_field="product.brand_name",
        panel_type=PanelType.SIDE_LEFT,
        x=10.0, y=20.0,
        font_size=6.0,
        font_bold=True,
        color_name=brand_color.name,
        rotation=90.0,
    ))

    # Generic name on side
    text_elements.append(TextElement(
        id="side-left-generic",
        content=generic_line,
        source_field="product.generic_name",
        panel_type=PanelType.SIDE_LEFT,
        x=4.0, y=5.0,
        font_size=4.5,
        rotation=90.0,
    ))

    # --- BARCODES ---
    barcodes = [
        BarcodeElement(
            id="ean13",
            barcode_type=BarcodeType.EAN_13,
            data="4006381333931",
            panel_type=PanelType.BACK,
            x=5.0, y=40.0,
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
        mrp_display = config.mrp.replace("\u20b9", "Rs.")
        coding_zones.append(CodingZone(
            id="mrp-area",
            purpose=f"MRP: {mrp_display} (Incl. of all taxes)",
            panel_type=PanelType.BACK,
            x=5.0, y=35.0,
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
