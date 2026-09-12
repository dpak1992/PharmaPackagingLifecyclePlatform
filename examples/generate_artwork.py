#!/usr/bin/env python3
"""Generate a pharmaceutical carton artwork PDF from product specifications.

Usage:
    python examples/generate_artwork.py

Output:
    output/azicure_500_artwork.pdf — open in Adobe Illustrator or CorelDRAW

This demonstrates the core technical feasibility:
  - PDF with editable text (not outlines)
  - CMYK colors (spot color equivalents)
  - Vector barcode (EAN-13)
  - Panel-based layout on computed dieline
  - Coding zones (batch, MRP, dates)
  - Dieline overlay layer
  - All content driven from structured product data
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from packaging_model import *
from packaging_model.enums import *
from dieline_engine.geometry import compute_dieline
from dieline_engine.dxf_export import export_dxf
from artwork_engine.text_layout import generate_default_artwork
from artwork_engine.pdf_composer import compose_artwork_pdf


def main():
    print("=" * 60)
    print("PHARMACEUTICAL ARTWORK COMPOSITOR — POC")
    print("=" * 60)
    print()

    # --- Define the product ---
    product = Product(
        id="AZI-500",
        brand_name="AZICURE",
        generic_name="Azithromycin",
        strength=Strength(value=500, unit="mg"),
        dosage_form=DosageForm.FILM_COATED_TABLET,
        composition=(
            "Each film coated tablet contains:\n"
            "Azithromycin IP equivalent to\n"
            "Azithromycin Anhydrous 500 mg"
        ),
        manufacturer=Manufacturer(
            name="PharmaCure Laboratories Pvt. Ltd.",
            address=(
                "Plot No. 45, MIDC Industrial Area,\n"
                "Mahad, Dist. Raigad,\n"
                "Maharashtra - 402309, India"
            ),
            license_no="MH/15/2024/000123",
        ),
        storage_conditions="Store below 25°C. Protect from light and moisture.",
    )

    blister = BlisterSpec(
        configuration="1x10",
        length=120.0,
        width=50.0,
        height=8.0,
    )

    config = PackagingConfig(
        product=product,
        blister=blister,
        pack_size="1 x 10",
        mrp="₹125.50",
    )

    # --- Calculate carton from blister ---
    config.carton.calculate_from_blister(blister)

    print(f"Product: {product.brand_name} {product.strength}")
    print(f"Generic: {product.generic_name}")
    print(f"Dosage: {product.dosage_form.value}")
    print(f"Pack: {config.pack_size}")
    print(f"MRP: {config.mrp}")
    print()

    print(f"Blister: {blister.length} × {blister.width} × {blister.height} mm")
    print(f"Carton: {config.carton.internal_length} × {config.carton.internal_width} "
          f"× {config.carton.internal_depth} mm (internal)")
    print()

    # --- Generate dieline ---
    dieline = compute_dieline(config.carton)
    print(f"Dieline: {dieline.total_width} × {dieline.total_height} mm flat layout")

    # --- Generate artwork specification ---
    artwork = generate_default_artwork(config)
    print(f"Artwork elements:")
    print(f"  Text objects: {len(artwork.text_elements)}")
    print(f"  Barcodes: {len(artwork.barcodes)}")
    print(f"  Coding zones: {len(artwork.coding_zones)}")
    print(f"  Spot colors: {[sc.name for sc in artwork.spot_colors]}")
    print(f"  Layers: {[l.value for l in artwork.layers]}")
    print()

    # --- Generate output files ---
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)

    # DXF dieline
    dxf_path = output_dir / "azicure_500_dieline.dxf"
    export_dxf(dieline, config.carton, dxf_path)
    print(f"DXF dieline: {dxf_path} ({dxf_path.stat().st_size:,} bytes)")

    # PDF artwork
    pdf_path = output_dir / "azicure_500_artwork.pdf"
    compose_artwork_pdf(config, dieline, artwork, pdf_path)
    print(f"PDF artwork:  {pdf_path} ({pdf_path.stat().st_size:,} bytes)")

    # JSON packaging config (structured data)
    json_path = output_dir / "azicure_500_config.json"
    with open(json_path, "w") as f:
        f.write(config.model_dump_json(indent=2))
    print(f"JSON config:  {json_path} ({json_path.stat().st_size:,} bytes)")

    print()
    print("=" * 60)
    print("VERIFICATION CHECKLIST")
    print("=" * 60)
    print()
    print("Open the PDF in Adobe Illustrator or CorelDRAW and verify:")
    print("  [ ] Text is editable (click on text, can modify)")
    print("  [ ] Font is Helvetica (not outlined/rasterized)")
    print("  [ ] Colors are CMYK (check color panel)")
    print("  [ ] Barcode is vector (zoom in, no pixels)")
    print("  [ ] Dieline is visible as magenta lines")
    print("  [ ] All panels are labeled (front, back, sides)")
    print("  [ ] Coding zones show dashed outlines")
    print("  [ ] Brand name, strength, generic name are present")
    print("  [ ] Schedule H warning is present")
    print("  [ ] Manufacturer details are present")
    print()
    print("Open the DXF in AutoCAD or LibreCAD and verify:")
    print("  [ ] CUT layer (red) shows panel outlines")
    print("  [ ] CREASE layer (green) shows fold lines")
    print("  [ ] GLUE layer (blue) shows glue area")
    print("  [ ] Dimensions match the calculated values above")
    print()
    print("Open the JSON to see the structured packaging data model.")


if __name__ == "__main__":
    main()
