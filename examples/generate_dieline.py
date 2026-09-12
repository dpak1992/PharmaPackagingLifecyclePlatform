#!/usr/bin/env python3
"""Generate a parametric carton dieline DXF from blister dimensions.

Usage:
    python examples/generate_dieline.py

Output:
    output/azicure_500_dieline.dxf — open in AutoCAD, LibreCAD, or any DXF viewer

This demonstrates the core technical feasibility: given blister dimensions,
automatically generate a die-maker-ready DXF with proper layers (CUT, CREASE, GLUE).
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from packaging_model import BlisterSpec, CartonSpec, BoardSpec
from packaging_model.enums import BoardGrade
from dieline_engine.geometry import compute_dieline
from dieline_engine.dxf_export import export_dxf


def main():
    print("=" * 60)
    print("PARAMETRIC DIELINE GENERATOR — POC")
    print("=" * 60)
    print()

    # --- Input: Blister specification ---
    blister = BlisterSpec(
        configuration="1x10",
        length=120.0,   # mm
        width=50.0,     # mm
        height=8.0,     # mm (max cavity depth)
        material_base="PVC 250μm",
        material_lidding="Aluminium 20μm",
    )
    print(f"Blister: {blister.configuration}")
    print(f"  Dimensions: {blister.length} × {blister.width} × {blister.height} mm")
    print()

    # --- Input: Board specification ---
    board = BoardSpec(
        grade=BoardGrade.GC1,
        caliper=0.40,   # mm (400 microns)
        weight_gsm=300,
    )

    # --- Calculate carton dimensions ---
    carton = CartonSpec(
        board=board,
        clearance=2.0,           # mm per side
        leaflet_allowance=5.0,   # mm for folded leaflet
    )
    carton.calculate_from_blister(blister)

    print(f"Carton (calculated):")
    print(f"  Internal: {carton.internal_length} × {carton.internal_width} × {carton.internal_depth} mm")
    print(f"  Board: {board.grade.value}, {board.weight_gsm} gsm, caliper {board.caliper} mm")
    print(f"  Clearance: {carton.clearance} mm per side")
    print(f"  Leaflet allowance: {carton.leaflet_allowance} mm")
    print()

    # --- Generate dieline ---
    dieline = compute_dieline(carton)

    print(f"Dieline (ECMA A-20-20 Reverse Tuck-End):")
    print(f"  Flat layout: {dieline.total_width} × {dieline.total_height} mm")
    print(f"  Panels: {len(dieline.panels)}")
    print(f"  Glue tab: {dieline.glue_tab_width} mm")
    print(f"  Tuck flap depth: {dieline.tuck_flap_depth} mm")
    print(f"  Dust flap depth: {dieline.dust_flap_depth} mm")
    print()

    for panel in dieline.panels:
        print(f"  {panel.panel_type.value:15s}  x={panel.x:7.2f}  y={panel.y:7.2f}  "
              f"w={panel.width:7.2f}  h={panel.height:7.2f}")
    print()

    # --- Export DXF ---
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    dxf_path = output_dir / "azicure_500_dieline.dxf"

    export_dxf(dieline, carton, dxf_path)
    print(f"DXF written: {dxf_path}")
    print(f"  File size: {dxf_path.stat().st_size:,} bytes")
    print(f"  Layers: CUT (red), CREASE (green), GLUE (blue), ANNOTATION")
    print()
    print("Open in AutoCAD, LibreCAD, or a DXF viewer to inspect.")
    print("Verify: panels are correctly sized, fold lines are on CREASE layer,")
    print("cut lines are on CUT layer, glue tab has glue area marked.")


if __name__ == "__main__":
    main()
