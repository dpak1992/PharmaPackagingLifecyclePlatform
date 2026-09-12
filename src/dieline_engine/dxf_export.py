"""DXF export for pharmaceutical carton dielines.

Generates die-maker-ready DXF files with industry-standard layer conventions:
  - CUT (red, color index 1) — through-cut lines
  - CREASE (green, color index 3) — fold/score lines
  - GLUE (blue, color index 5) — glue application areas

All geometry is polylines at 1:1 scale in millimeters.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import ezdxf
from ezdxf.enums import TextEntityAlignment

from packaging_model.models import DielineSpec, CartonSpec, Panel
from packaging_model.enums import PanelType


# DXF color indices (ACI)
COLOR_CUT = 1     # Red
COLOR_CREASE = 3  # Green
COLOR_GLUE = 5    # Blue
COLOR_ANNO = 7    # White/Black (annotation)


def _setup_layers(doc: ezdxf.document.Drawing) -> None:
    """Create standard dieline layers."""
    doc.layers.add("CUT", color=COLOR_CUT)
    doc.layers.add("CREASE", color=COLOR_CREASE)
    doc.layers.add("GLUE", color=COLOR_GLUE)
    doc.layers.add("ANNOTATION", color=COLOR_ANNO)


def _draw_rect(msp, x: float, y: float, w: float, h: float, layer: str) -> None:
    """Draw a rectangle as a closed polyline."""
    points = [
        (x, y),
        (x + w, y),
        (x + w, y + h),
        (x, y + h),
    ]
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})


def _draw_tuck_flap(
    msp,
    panel: Panel,
    parent_width: float,
    is_top: bool,
) -> None:
    """Draw a tuck flap with tapered edges (trapezoidal shape).

    Tuck flaps are slightly narrower at the tip than at the base, creating
    a trapezoidal shape that helps insertion. The taper is typically 2-3mm
    per side.
    """
    taper = 2.5  # mm inset on each side at the tip
    x, y, w, h = panel.x, panel.y, panel.width, panel.height

    if is_top:
        # Base at bottom (attached to body), tip at top
        points = [
            (x, y),              # bottom-left (base)
            (x + w, y),          # bottom-right (base)
            (x + w - taper, y + h),  # top-right (tip, tapered)
            (x + taper, y + h),      # top-left (tip, tapered)
        ]
    else:
        # Base at top (attached to body), tip at bottom
        points = [
            (x + taper, y),          # bottom-left (tip, tapered)
            (x + w - taper, y),      # bottom-right (tip, tapered)
            (x + w, y + h),          # top-right (base)
            (x, y + h),             # top-left (base)
        ]

    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "CUT"})


def _draw_glue_tab(msp, panel: Panel) -> None:
    """Draw a glue tab with tapered top and bottom edges."""
    taper = 3.0  # mm
    x, y, w, h = panel.x, panel.y, panel.width, panel.height

    points = [
        (x, y + taper),          # left-bottom (tapered)
        (x, y + h - taper),      # left-top (tapered)
        (x + w, y + h),          # right-top (full height, at fold)
        (x + w, y),              # right-bottom (full height, at fold)
    ]
    msp.add_lwpolyline(points, close=True, dxfattribs={"layer": "CUT"})

    # Glue application area (inset rectangle)
    inset = 2.0
    _draw_rect(
        msp,
        x + inset,
        y + taper + inset,
        w - 2 * inset,
        h - 2 * taper - 2 * inset,
        "GLUE",
    )


def _add_panel_annotation(msp, panel: Panel, label: str) -> None:
    """Add a panel label annotation for reference."""
    cx = panel.x + panel.width / 2
    cy = panel.y + panel.height / 2
    msp.add_text(
        label,
        height=3.0,
        dxfattribs={
            "layer": "ANNOTATION",
            "halign": ezdxf.const.CENTER,
            "valign": ezdxf.const.MIDDLE,
        },
    ).set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)


def export_dxf(
    dieline: DielineSpec,
    carton: CartonSpec,
    output_path: Union[str, Path],
) -> Path:
    """Export a dieline specification as a DXF file.

    Args:
        dieline: The computed dieline specification.
        carton: The carton specification (for dimension reference).
        output_path: File path for the output DXF.

    Returns:
        Path to the written DXF file.
    """
    output_path = Path(output_path)
    doc = ezdxf.new("R2018")
    doc.units = ezdxf.units.MM

    _setup_layers(doc)
    msp = doc.modelspace()

    for panel in dieline.panels:
        ptype = panel.panel_type

        if ptype == PanelType.GLUE_TAB:
            _draw_glue_tab(msp, panel)
            _add_panel_annotation(msp, panel, "GLUE TAB")

        elif ptype in (PanelType.TOP_TUCK, PanelType.BOTTOM_TUCK):
            is_top = ptype == PanelType.TOP_TUCK
            _draw_tuck_flap(msp, panel, panel.width, is_top)
            label = "TOP TUCK" if is_top else "BOTTOM TUCK"
            _add_panel_annotation(msp, panel, label)

        elif ptype in (PanelType.TOP_DUST, PanelType.BOTTOM_DUST):
            # Dust flaps are simple rectangles
            _draw_rect(msp, panel.x, panel.y, panel.width, panel.height, "CUT")
            label = "TOP DUST" if ptype == PanelType.TOP_DUST else "BOTTOM DUST"
            _add_panel_annotation(msp, panel, label)

        else:
            # Main body panels: outline is CUT
            _draw_rect(msp, panel.x, panel.y, panel.width, panel.height, "CUT")

            # Panel label
            label_map = {
                PanelType.FRONT: "PANEL 1\n(FRONT)",
                PanelType.SIDE_RIGHT: "PANEL 2\n(SIDE R)",
                PanelType.BACK: "PANEL 3\n(BACK)",
                PanelType.SIDE_LEFT: "PANEL 4\n(SIDE L)",
            }
            _add_panel_annotation(msp, panel, label_map.get(ptype, str(ptype)))

    # Draw CREASE lines at fold boundaries between body panels
    # Crease lines run vertically along the full body height
    body_panels = [
        p for p in dieline.panels
        if p.panel_type in (
            PanelType.FRONT, PanelType.SIDE_RIGHT,
            PanelType.BACK, PanelType.SIDE_LEFT,
        )
    ]
    body_panels.sort(key=lambda p: p.x)

    for panel in body_panels:
        # Left edge crease (between this panel and the one to its left)
        y_bottom = panel.y
        y_top = panel.y + panel.height
        msp.add_line(
            (panel.x, y_bottom),
            (panel.x, y_top),
            dxfattribs={"layer": "CREASE"},
        )

    # Also crease between body panels and their tuck/dust flaps (horizontal)
    for panel in dieline.panels:
        if panel.panel_type in (
            PanelType.TOP_TUCK, PanelType.TOP_DUST,
            PanelType.BOTTOM_TUCK, PanelType.BOTTOM_DUST,
        ):
            # Horizontal crease at the fold line (where flap meets body)
            if "TOP" in panel.panel_type.value.upper():
                crease_y = panel.y  # bottom edge of top flap
            else:
                crease_y = panel.y + panel.height  # top edge of bottom flap

            msp.add_line(
                (panel.x, crease_y),
                (panel.x + panel.width, crease_y),
                dxfattribs={"layer": "CREASE"},
            )

    # Crease at glue tab fold
    glue_panels = [p for p in dieline.panels if p.panel_type == PanelType.GLUE_TAB]
    if glue_panels:
        gp = glue_panels[0]
        msp.add_line(
            (gp.x + gp.width, gp.y),
            (gp.x + gp.width, gp.y + gp.height),
            dxfattribs={"layer": "CREASE"},
        )

    # Add dimension annotations
    # Overall dimensions text
    dim_text = (
        f"Internal: {carton.internal_length:.1f} x "
        f"{carton.internal_width:.1f} x "
        f"{carton.internal_depth:.1f} mm\n"
        f"Board: {carton.board.weight_gsm} gsm, "
        f"caliper {carton.board.caliper:.2f} mm"
    )
    msp.add_text(
        dim_text,
        height=2.5,
        dxfattribs={"layer": "ANNOTATION"},
    ).set_placement(
        (0, -10),
        align=TextEntityAlignment.BOTTOM_LEFT,
    )

    doc.saveas(str(output_path))
    return output_path
