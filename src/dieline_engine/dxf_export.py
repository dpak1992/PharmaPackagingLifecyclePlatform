"""DXF export for pharmaceutical carton dielines.

Generates die-maker-ready DXF files with industry-standard layer conventions:
  - CUT (red, color index 1) — through-cut lines
  - CREASE (green, color index 3) — fold/score lines
  - GLUE (blue, color index 5) — glue application areas
  - ANNOTATION (white/black, color index 7) — text and reference marks
  - DIMENSIONS (magenta, color index 6) — dimension lines

All geometry is polylines at 1:1 scale in millimeters.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Union

import ezdxf
from ezdxf.enums import TextEntityAlignment

from packaging_model.models import DielineSpec, CartonSpec, Panel
from packaging_model.enums import PanelType
from dieline_engine.geometry import bend_allowance


# DXF color indices (ACI)
COLOR_CUT = 1     # Red
COLOR_CREASE = 3  # Green
COLOR_GLUE = 5    # Blue
COLOR_DIMENSION = 6  # Magenta
COLOR_ANNO = 7    # White/Black (annotation)


def _setup_layers(doc: ezdxf.document.Drawing) -> None:
    """Create standard dieline layers."""
    doc.layers.add("CUT", color=COLOR_CUT)
    doc.layers.add("CREASE", color=COLOR_CREASE)
    doc.layers.add("GLUE", color=COLOR_GLUE)
    doc.layers.add("ANNOTATION", color=COLOR_ANNO)
    doc.layers.add("DIMENSIONS", color=COLOR_DIMENSION)


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


def _add_panel_annotation_with_dims(msp, panel: Panel, label: str) -> None:
    """Add a panel label with dimensions annotation."""
    cx = panel.x + panel.width / 2
    cy = panel.y + panel.height / 2
    dim_label = f"{label}\n{panel.width:.1f} x {panel.height:.1f} mm"
    msp.add_text(
        dim_label,
        height=3.0,
        dxfattribs={
            "layer": "ANNOTATION",
            "halign": ezdxf.const.CENTER,
            "valign": ezdxf.const.MIDDLE,
        },
    ).set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)


def _add_dim(msp, base, p1, p2, angle=0) -> None:
    """Add a single dimension line on the DIMENSIONS layer."""
    dim = msp.add_linear_dim(
        base=base, p1=p1, p2=p2,
        angle=angle,
        dimstyle="EZDXF",
        override={"dimtxt": 2.0},
        dxfattribs={"layer": "DIMENSIONS"},
    )
    dim.render()


def _add_dimension_lines(msp, dieline: DielineSpec, carton: CartonSpec) -> None:
    """Add dimension lines on every panel using ezdxf linear dimensions."""
    dim_offset = 8.0
    body_panels = [
        p for p in dieline.panels
        if p.panel_type in (
            PanelType.FRONT, PanelType.SIDE_RIGHT,
            PanelType.BACK, PanelType.SIDE_LEFT,
        )
    ]
    body_panels.sort(key=lambda p: p.x)

    # Width dimension on each body panel (below)
    for panel in body_panels:
        _add_dim(msp,
            base=(panel.x, panel.y - dim_offset),
            p1=(panel.x, panel.y),
            p2=(panel.x + panel.width, panel.y))

    # Height dimension on first body panel (left)
    if body_panels:
        first = body_panels[0]
        _add_dim(msp,
            base=(first.x - dim_offset, first.y),
            p1=(first.x, first.y),
            p2=(first.x, first.y + first.height),
            angle=90)

    # Glue tab width
    glue_panels = [p for p in dieline.panels if p.panel_type == PanelType.GLUE_TAB]
    if glue_panels:
        gp = glue_panels[0]
        _add_dim(msp,
            base=(gp.x, gp.y - dim_offset),
            p1=(gp.x, gp.y),
            p2=(gp.x + gp.width, gp.y))

    # Tuck flap depth
    tuck_panels = [p for p in dieline.panels if p.panel_type == PanelType.TOP_TUCK]
    if tuck_panels:
        tp = tuck_panels[0]
        _add_dim(msp,
            base=(tp.x + tp.width + dim_offset, tp.y),
            p1=(tp.x + tp.width, tp.y),
            p2=(tp.x + tp.width, tp.y + tp.height),
            angle=90)

    # Dust flap depth
    dust_panels = [p for p in dieline.panels if p.panel_type == PanelType.TOP_DUST]
    if dust_panels:
        dp = dust_panels[0]
        _add_dim(msp,
            base=(dp.x + dp.width + dim_offset, dp.y),
            p1=(dp.x + dp.width, dp.y),
            p2=(dp.x + dp.width, dp.y + dp.height),
            angle=90)


def _add_spec_block(msp, dieline: DielineSpec, carton: CartonSpec) -> None:
    """Add a technical specification block below the dieline."""
    cal = carton.board.caliper
    ba = bend_allowance(cal)
    panel_w = carton.internal_width + cal
    panel_d = carton.internal_depth + cal
    body_h = carton.internal_length + cal
    glue_w = dieline.glue_tab_width
    tuck_d = dieline.tuck_flap_depth
    dust_d = dieline.dust_flap_depth
    taper = 2.5  # matches the taper used in _draw_tuck_flap

    # Find the lowest point of the dieline to place the spec block below
    min_y = min(p.y for p in dieline.panels)
    spec_y = min_y - 30.0  # 30mm below the lowest panel

    spec_text = (
        f"CARTON STRUCTURAL SPECIFICATION\n"
        f"================================\n"
        f"Construction:    ECMA A-20-20 (Reverse Tuck-End)\n"
        f"Internal (L x W x D): {carton.internal_length:.1f} x "
        f"{carton.internal_width:.1f} x {carton.internal_depth:.1f} mm\n"
        f"Board:           {carton.board.grade.value} {carton.board.weight_gsm} gsm, "
        f"caliper {cal:.2f} mm\n"
        f"Bend Allowance:  {ba:.3f} mm (per 90 deg fold)\n"
        f"\n"
        f"PANEL DIMENSIONS (external):\n"
        f"  Front/Back (Panels 1,3): {panel_w:.1f} x {body_h:.1f} mm\n"
        f"  Sides (Panels 2,4):      {panel_d:.1f} x {body_h:.1f} mm\n"
        f"  Glue Tab:                 {glue_w:.1f} x {body_h:.1f} mm\n"
        f"  Tuck Flaps:               {tuck_d:.1f} mm deep, {taper:.1f} mm taper\n"
        f"  Dust Flaps:               {dust_d:.1f} mm deep\n"
        f"\n"
        f"TOLERANCES:\n"
        f"  Cut: +/-0.5 mm\n"
        f"  Score-to-cut: +/-0.3 mm\n"
        f"  Registration: +/-0.3 mm\n"
        f"  NOTE: These are typical values. Verify with die-maker.\n"
        f"\n"
        f"MACHINE DIRECTION:\n"
        f"  Grain: parallel to score lines (vertical)\n"
        f"  Feed:  length-first (horizontal cartoner)\n"
        f"\n"
        f"WARNINGS:\n"
        f"  ! Physical prototype required before production\n"
        f"  ! Verify fit with actual blister sample\n"
        f"  ! Confirm cartoning machine compatibility"
    )

    # Add as multi-line text (MTEXT) on the ANNOTATION layer
    msp.add_mtext(
        spec_text,
        dxfattribs={
            "layer": "ANNOTATION",
            "char_height": 2.0,
            "width": 200.0,
        },
    ).set_location((0, spec_y))


def _add_machine_direction_arrow(msp, dieline: DielineSpec) -> None:
    """Draw a machine direction arrow indicating grain/feed direction."""
    # Place arrow to the right of the dieline
    max_x = max(p.x + p.width for p in dieline.panels)
    body_panels = [
        p for p in dieline.panels
        if p.panel_type in (
            PanelType.FRONT, PanelType.SIDE_RIGHT,
            PanelType.BACK, PanelType.SIDE_LEFT,
        )
    ]
    if not body_panels:
        return

    mid_y = body_panels[0].y + body_panels[0].height / 2
    arrow_x = max_x + 20.0
    arrow_len = 30.0
    head_len = 5.0

    # Vertical arrow (grain direction)
    y_start = mid_y - arrow_len / 2
    y_end = mid_y + arrow_len / 2

    # Arrow shaft
    msp.add_line(
        (arrow_x, y_start),
        (arrow_x, y_end),
        dxfattribs={"layer": "ANNOTATION"},
    )
    # Arrowhead (two lines at 30 degrees)
    angle_rad = math.radians(30)
    dx = head_len * math.sin(angle_rad)
    dy = head_len * math.cos(angle_rad)
    msp.add_line(
        (arrow_x, y_end),
        (arrow_x - dx, y_end - dy),
        dxfattribs={"layer": "ANNOTATION"},
    )
    msp.add_line(
        (arrow_x, y_end),
        (arrow_x + dx, y_end - dy),
        dxfattribs={"layer": "ANNOTATION"},
    )

    # Label
    msp.add_text(
        "GRAIN",
        height=2.5,
        dxfattribs={
            "layer": "ANNOTATION",
            "halign": ezdxf.const.CENTER,
            "valign": ezdxf.const.MIDDLE,
        },
    ).set_placement((arrow_x, y_end + 5), align=TextEntityAlignment.MIDDLE_CENTER)

    # Horizontal arrow (feed direction)
    feed_y = y_start - 10.0
    feed_x_start = arrow_x - arrow_len / 2
    feed_x_end = arrow_x + arrow_len / 2

    msp.add_line(
        (feed_x_start, feed_y),
        (feed_x_end, feed_y),
        dxfattribs={"layer": "ANNOTATION"},
    )
    msp.add_line(
        (feed_x_end, feed_y),
        (feed_x_end - dy, feed_y + dx),
        dxfattribs={"layer": "ANNOTATION"},
    )
    msp.add_line(
        (feed_x_end, feed_y),
        (feed_x_end - dy, feed_y - dx),
        dxfattribs={"layer": "ANNOTATION"},
    )

    msp.add_text(
        "FEED",
        height=2.5,
        dxfattribs={
            "layer": "ANNOTATION",
            "halign": ezdxf.const.CENTER,
            "valign": ezdxf.const.MIDDLE,
        },
    ).set_placement(
        (feed_x_end + 8, feed_y),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )


def _add_registration_marks(msp, dieline: DielineSpec) -> None:
    """Add registration cross-hair marks at the four corners of the layout."""
    mark_size = 3.0  # mm total, so half-arm = 1.5mm
    half = mark_size / 2.0

    # Find bounding box of the entire layout
    min_x = min(p.x for p in dieline.panels)
    max_x = max(p.x + p.width for p in dieline.panels)
    min_y = min(p.y for p in dieline.panels)
    max_y = max(p.y + p.height for p in dieline.panels)

    # Offset marks slightly outside the layout
    margin = 5.0
    corners = [
        (min_x - margin, min_y - margin),
        (max_x + margin, min_y - margin),
        (min_x - margin, max_y + margin),
        (max_x + margin, max_y + margin),
    ]

    for cx, cy in corners:
        # Horizontal stroke
        msp.add_line(
            (cx - half, cy),
            (cx + half, cy),
            dxfattribs={"layer": "ANNOTATION"},
        )
        # Vertical stroke
        msp.add_line(
            (cx, cy - half),
            (cx, cy + half),
            dxfattribs={"layer": "ANNOTATION"},
        )


def export_dxf(
    dieline: DielineSpec,
    carton: CartonSpec,
    output_path: Union[str, Path],
) -> Path:
    """Export a dieline specification as a DXF file.

    Generates a production-ready DXF with:
    - Structural geometry on CUT, CREASE, and GLUE layers
    - Dimension lines on every panel (DIMENSIONS layer)
    - Technical specification block (ANNOTATION layer)
    - Machine direction arrows (ANNOTATION layer)
    - Registration marks at layout corners (ANNOTATION layer)
    - Panel annotations with dimensions (ANNOTATION layer)

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
            _add_panel_annotation_with_dims(msp, panel, "GLUE TAB")

        elif ptype in (PanelType.TOP_TUCK, PanelType.BOTTOM_TUCK):
            is_top = ptype == PanelType.TOP_TUCK
            _draw_tuck_flap(msp, panel, panel.width, is_top)
            label = "TOP TUCK" if is_top else "BOTTOM TUCK"
            _add_panel_annotation_with_dims(msp, panel, label)

        elif ptype in (PanelType.TOP_DUST, PanelType.BOTTOM_DUST):
            # Dust flaps are simple rectangles
            _draw_rect(msp, panel.x, panel.y, panel.width, panel.height, "CUT")
            label = "TOP DUST" if ptype == PanelType.TOP_DUST else "BOTTOM DUST"
            _add_panel_annotation_with_dims(msp, panel, label)

        else:
            # Main body panels: outline is CUT
            _draw_rect(msp, panel.x, panel.y, panel.width, panel.height, "CUT")

            # Panel label with dimensions
            label_map = {
                PanelType.FRONT: "PANEL 1 (FRONT)",
                PanelType.SIDE_RIGHT: "PANEL 2 (SIDE R)",
                PanelType.BACK: "PANEL 3 (BACK)",
                PanelType.SIDE_LEFT: "PANEL 4 (SIDE L)",
            }
            _add_panel_annotation_with_dims(
                msp, panel, label_map.get(ptype, str(ptype))
            )

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

    # --- Production specification enhancements ---

    # 1. Dimension lines on every panel
    _add_dimension_lines(msp, dieline, carton)

    # 2. Technical specification block
    _add_spec_block(msp, dieline, carton)

    # 3. Machine direction arrow
    _add_machine_direction_arrow(msp, dieline)

    # 4. Registration marks at layout corners
    _add_registration_marks(msp, dieline)

    doc.saveas(str(output_path))
    return output_path
