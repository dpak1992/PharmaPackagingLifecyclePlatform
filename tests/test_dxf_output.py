"""Tests for DXF export — verify layer structure and geometry."""
import os
import pytest
import ezdxf

from packaging_model import BlisterSpec, CartonSpec
from dieline_engine.geometry import compute_dieline
from dieline_engine.dxf_export import export_dxf


@pytest.fixture
def sample_dxf(tmp_path):
    """Generate a sample DXF and return the file path."""
    blister = BlisterSpec(length=120, width=50, height=8)
    carton = CartonSpec()
    carton.calculate_from_blister(blister)
    dieline = compute_dieline(carton)
    path = tmp_path / "test.dxf"
    export_dxf(dieline, carton, path)
    return path


class TestDxfOutput:
    def test_file_created(self, sample_dxf):
        assert sample_dxf.exists()
        assert sample_dxf.stat().st_size > 0

    def test_valid_dxf(self, sample_dxf):
        """DXF should be parseable by ezdxf."""
        doc = ezdxf.readfile(str(sample_dxf))
        assert doc is not None

    def test_has_required_layers(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        layer_names = {l.dxf.name for l in doc.layers}
        assert "CUT" in layer_names
        assert "CREASE" in layer_names
        assert "GLUE" in layer_names
        assert "ANNOTATION" in layer_names

    def test_cut_layer_color_is_red(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        cut_layer = doc.layers.get("CUT")
        assert cut_layer.color == 1  # ACI red

    def test_crease_layer_color_is_green(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        crease_layer = doc.layers.get("CREASE")
        assert crease_layer.color == 3  # ACI green

    def test_has_entities_on_cut_layer(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        msp = doc.modelspace()
        cut_entities = [e for e in msp if e.dxf.layer == "CUT"]
        assert len(cut_entities) > 0

    def test_has_crease_lines(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        msp = doc.modelspace()
        crease_entities = [e for e in msp if e.dxf.layer == "CREASE"]
        assert len(crease_entities) > 0

    def test_has_glue_area(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        msp = doc.modelspace()
        glue_entities = [e for e in msp if e.dxf.layer == "GLUE"]
        assert len(glue_entities) > 0

    def test_has_annotations(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        msp = doc.modelspace()
        anno = [e for e in msp if e.dxf.layer == "ANNOTATION"]
        assert len(anno) > 0

    def test_units_are_mm(self, sample_dxf):
        doc = ezdxf.readfile(str(sample_dxf))
        # ezdxf units constant for mm = 4
        assert doc.units == 4  # millimeters
