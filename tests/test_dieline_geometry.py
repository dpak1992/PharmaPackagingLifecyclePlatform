"""Tests for parametric dieline geometry calculations."""
import math
import pytest

from packaging_model import BlisterSpec, CartonSpec, BoardSpec
from packaging_model.enums import CartonConstruction, PanelType, BoardGrade
from dieline_engine.geometry import compute_dieline, bend_allowance


class TestBendAllowance:
    def test_90_degree_bend(self):
        """π × caliper / 4 for 90° fold."""
        cal = 0.40  # mm
        ba = bend_allowance(cal, 90.0)
        expected = math.pi * 0.40 / 4.0
        assert abs(ba - expected) < 0.001

    def test_zero_caliper(self):
        assert bend_allowance(0.0) == 0.0

    def test_thicker_board_gives_larger_allowance(self):
        assert bend_allowance(0.50) > bend_allowance(0.35)


class TestComputeDieline:
    @pytest.fixture
    def standard_blister(self):
        return BlisterSpec(length=120, width=50, height=8)

    @pytest.fixture
    def standard_carton(self, standard_blister):
        carton = CartonSpec()
        carton.calculate_from_blister(standard_blister)
        return carton

    def test_carton_dimensions_from_blister(self, standard_carton):
        """Carton internal dimensions = blister dims + clearances + leaflet."""
        assert standard_carton.internal_length == 124.0  # 120 + 2*2
        assert standard_carton.internal_width == 54.0    # 50 + 2*2
        assert standard_carton.internal_depth == 15.0    # 8 + 5 + 2

    def test_dieline_has_11_panels(self, standard_carton):
        """ECMA A-20-20 should produce 11 panels:
        glue tab + 4 body + 2 tuck + 4 dust flaps."""
        dieline = compute_dieline(standard_carton)
        assert len(dieline.panels) == 11

    def test_dieline_panel_types(self, standard_carton):
        """Verify all expected panel types are present."""
        dieline = compute_dieline(standard_carton)
        types = [p.panel_type for p in dieline.panels]
        assert PanelType.GLUE_TAB in types
        assert PanelType.FRONT in types
        assert PanelType.BACK in types
        assert PanelType.SIDE_RIGHT in types
        assert PanelType.SIDE_LEFT in types
        assert types.count(PanelType.TOP_TUCK) == 1
        assert types.count(PanelType.BOTTOM_TUCK) == 1
        assert types.count(PanelType.TOP_DUST) == 2
        assert types.count(PanelType.BOTTOM_DUST) == 2

    def test_body_panel_heights_match(self, standard_carton):
        """All body panels should have the same height (carton length)."""
        dieline = compute_dieline(standard_carton)
        body = [
            p for p in dieline.panels
            if p.panel_type in (PanelType.FRONT, PanelType.BACK,
                                PanelType.SIDE_RIGHT, PanelType.SIDE_LEFT)
        ]
        heights = [p.height for p in body]
        assert all(abs(h - heights[0]) < 0.01 for h in heights)

    def test_width_panels_wider_than_depth_panels(self, standard_carton):
        """Front/back (width) panels should be wider than side (depth) panels."""
        dieline = compute_dieline(standard_carton)
        front = next(p for p in dieline.panels if p.panel_type == PanelType.FRONT)
        side = next(p for p in dieline.panels if p.panel_type == PanelType.SIDE_RIGHT)
        assert front.width > side.width

    def test_panels_do_not_overlap(self, standard_carton):
        """No two body panels should overlap horizontally."""
        dieline = compute_dieline(standard_carton)
        body = sorted(
            [p for p in dieline.panels if p.panel_type in (
                PanelType.GLUE_TAB, PanelType.FRONT, PanelType.BACK,
                PanelType.SIDE_RIGHT, PanelType.SIDE_LEFT,
            )],
            key=lambda p: p.x,
        )
        for i in range(len(body) - 1):
            right_edge = body[i].x + body[i].width
            next_left = body[i + 1].x
            # Allow for bend allowance gap
            assert right_edge <= next_left + 0.01, (
                f"Panel {body[i].panel_type} overlaps {body[i+1].panel_type}"
            )

    def test_total_width_positive(self, standard_carton):
        dieline = compute_dieline(standard_carton)
        assert dieline.total_width > 0
        assert dieline.total_height > 0

    def test_glue_tab_width(self, standard_carton):
        dieline = compute_dieline(standard_carton)
        glue = next(p for p in dieline.panels if p.panel_type == PanelType.GLUE_TAB)
        assert glue.width == 15.0  # standard pharma glue tab

    def test_tuck_depth_is_80pct_of_width(self, standard_carton):
        dieline = compute_dieline(standard_carton)
        expected = standard_carton.internal_width * 0.80
        assert abs(dieline.tuck_flap_depth - expected) < 0.01

    def test_rejects_non_a20_20(self):
        carton = CartonSpec(construction=CartonConstruction.ECMA_A55_03)
        carton.internal_length = 100
        carton.internal_width = 50
        carton.internal_depth = 15
        with pytest.raises(ValueError, match="ECMA A-20-20"):
            compute_dieline(carton)

    def test_rejects_zero_dimensions(self):
        carton = CartonSpec()  # dimensions are 0
        with pytest.raises(ValueError, match="positive"):
            compute_dieline(carton)

    def test_different_blister_sizes(self):
        """Verify dieline scales correctly with different blister sizes."""
        small = BlisterSpec(length=80, width=30, height=6)
        large = BlisterSpec(length=150, width=70, height=12)

        c_small = CartonSpec()
        c_small.calculate_from_blister(small)
        d_small = compute_dieline(c_small)

        c_large = CartonSpec()
        c_large.calculate_from_blister(large)
        d_large = compute_dieline(c_large)

        assert d_large.total_width > d_small.total_width
        assert d_large.total_height > d_small.total_height

    def test_thicker_board_changes_dimensions(self):
        """Thicker board should produce slightly different panel sizes."""
        blister = BlisterSpec(length=120, width=50, height=8)

        thin = CartonSpec(board=BoardSpec(caliper=0.35))
        thin.calculate_from_blister(blister)
        d_thin = compute_dieline(thin)

        thick = CartonSpec(board=BoardSpec(caliper=0.50))
        thick.calculate_from_blister(blister)
        d_thick = compute_dieline(thick)

        assert d_thick.total_width > d_thin.total_width
