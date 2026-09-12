"""Parametric dieline geometry calculations for pharmaceutical cartons.

All dimensions are in millimeters. The origin (0, 0) is at the bottom-left
corner of the flat dieline layout.

Coordinate system:
  - X axis: horizontal (across panels, left to right)
  - Y axis: vertical (along carton height / length)

For ECMA A-20-20 reverse tuck-end, the flat layout is:

  Glue Tab | Panel 1 (W) | Panel 2 (D) | Panel 3 (W) | Panel 4 (D)

Where W = carton width, D = carton depth. The carton "length" (height of the
carton when erected) runs along the Y axis.

Tuck flaps extend above and below the main body panels.
Dust flaps extend above and below Panels 1 and 3 (the width panels).
"""
from __future__ import annotations

import math
from packaging_model.models import CartonSpec, DielineSpec, Panel
from packaging_model.enums import CartonConstruction, PanelType


def bend_allowance(caliper: float, angle_deg: float = 90.0) -> float:
    """Calculate bend allowance for a fold in carton board.

    For a 90-degree fold, the outer panel must be slightly wider to account
    for the material thickness at the bend. The standard approximation is:
        BA = π × caliper × angle / 360

    For a 90° fold: BA = π × caliper / 4 ≈ 0.785 × caliper

    In practice, carton designers use lookup tables per board grade. This
    formula provides a reasonable approximation for our POC.

    Returns the bend allowance in mm (amount to ADD to outer panel dimension).
    """
    return math.pi * caliper * angle_deg / 360.0


def compute_dieline(carton: CartonSpec) -> DielineSpec:
    """Generate a complete ECMA A-20-20 reverse tuck-end dieline from carton specs.

    The carton must have internal dimensions already calculated
    (call carton.calculate_from_blister() first).

    Returns a DielineSpec with all panels, flaps, and dimensions.
    """
    if carton.construction != CartonConstruction.ECMA_A20_20:
        raise ValueError(
            f"Only ECMA A-20-20 is supported, got {carton.construction}"
        )

    if carton.internal_length <= 0 or carton.internal_width <= 0 or carton.internal_depth <= 0:
        raise ValueError("Carton internal dimensions must be positive. Call calculate_from_blister() first.")

    cal = carton.board.caliper
    ba = bend_allowance(cal)

    # External panel dimensions (internal + caliper compensation)
    # Each panel is slightly larger than internal to account for board thickness
    panel_w = carton.internal_width + cal  # width panels (front/back)
    panel_d = carton.internal_depth + cal  # depth panels (sides)
    body_h = carton.internal_length + cal  # height of main body

    # Glue tab
    glue_w = 15.0  # standard pharmaceutical carton glue tab

    # Tuck flap depth: ~80% of internal width (enough to hold, not interfere)
    tuck_depth = carton.internal_width * 0.80

    # Dust flap depth: ~45% of internal depth
    dust_depth = carton.internal_depth * 0.45

    # Small gap between dust flap and adjacent tuck flap to prevent collision
    flap_gap = 0.5  # mm

    # --- Build panel list ---
    panels = []
    x_cursor = 0.0
    y_body_bottom = tuck_depth + flap_gap  # body starts above bottom tuck flaps

    # 1. Glue tab
    panels.append(Panel(
        panel_type=PanelType.GLUE_TAB,
        x=x_cursor,
        y=y_body_bottom,
        width=glue_w,
        height=body_h,
    ))
    x_cursor += glue_w + ba

    # 2. Panel 1 — front (width)
    p1_x = x_cursor
    panels.append(Panel(
        panel_type=PanelType.FRONT,
        x=p1_x,
        y=y_body_bottom,
        width=panel_w,
        height=body_h,
    ))
    # Top dust flap on Panel 1
    panels.append(Panel(
        panel_type=PanelType.TOP_DUST,
        x=p1_x,
        y=y_body_bottom + body_h + ba,
        width=panel_w,
        height=dust_depth,
    ))
    # Bottom dust flap on Panel 1
    panels.append(Panel(
        panel_type=PanelType.BOTTOM_DUST,
        x=p1_x,
        y=y_body_bottom - ba - dust_depth,
        width=panel_w,
        height=dust_depth,
    ))
    x_cursor += panel_w + ba

    # 3. Panel 2 — side right (depth)
    p2_x = x_cursor
    panels.append(Panel(
        panel_type=PanelType.SIDE_RIGHT,
        x=p2_x,
        y=y_body_bottom,
        width=panel_d,
        height=body_h,
    ))
    # Top tuck flap on Panel 2
    panels.append(Panel(
        panel_type=PanelType.TOP_TUCK,
        x=p2_x,
        y=y_body_bottom + body_h + ba,
        width=panel_d,
        height=tuck_depth,
    ))
    # Bottom tuck flap on Panel 2
    panels.append(Panel(
        panel_type=PanelType.BOTTOM_TUCK,
        x=p2_x,
        y=y_body_bottom - ba - tuck_depth,
        width=panel_d,
        height=tuck_depth,
    ))
    x_cursor += panel_d + ba

    # 4. Panel 3 — back (width)
    p3_x = x_cursor
    panels.append(Panel(
        panel_type=PanelType.BACK,
        x=p3_x,
        y=y_body_bottom,
        width=panel_w,
        height=body_h,
    ))
    # Top dust flap on Panel 3
    panels.append(Panel(
        panel_type=PanelType.TOP_DUST,
        x=p3_x,
        y=y_body_bottom + body_h + ba,
        width=panel_w,
        height=dust_depth,
    ))
    # Bottom dust flap on Panel 3
    panels.append(Panel(
        panel_type=PanelType.BOTTOM_DUST,
        x=p3_x,
        y=y_body_bottom - ba - dust_depth,
        width=panel_w,
        height=dust_depth,
    ))
    x_cursor += panel_w + ba

    # 5. Panel 4 — side left (depth)
    p4_x = x_cursor
    panels.append(Panel(
        panel_type=PanelType.SIDE_LEFT,
        x=p4_x,
        y=y_body_bottom,
        width=panel_d,
        height=body_h,
    ))
    x_cursor += panel_d

    # Total layout dimensions
    total_width = x_cursor
    total_height = (
        tuck_depth + flap_gap  # below body
        + body_h               # body
        + ba                   # bend above body
        + tuck_depth           # tuck flap above (tallest)
    )

    return DielineSpec(
        version="1.0",
        construction=CartonConstruction.ECMA_A20_20,
        panels=panels,
        total_width=round(total_width, 2),
        total_height=round(total_height, 2),
        glue_tab_width=glue_w,
        tuck_flap_depth=round(tuck_depth, 2),
        dust_flap_depth=round(dust_depth, 2),
    )
