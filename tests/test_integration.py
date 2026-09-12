"""Integration tests — full pipeline from product spec to output files."""
import pytest

from packaging_model import *
from packaging_model.enums import *
from dieline_engine.geometry import compute_dieline
from dieline_engine.dxf_export import export_dxf
from artwork_engine.text_layout import generate_default_artwork
from artwork_engine.pdf_composer import compose_artwork_pdf


def _make_config(
    brand: str,
    generic: str,
    strength_val: float,
    blister_l: float,
    blister_w: float,
    blister_h: float,
    mrp: str = None,
):
    product = Product(
        id=f"{brand}-{int(strength_val)}",
        brand_name=brand,
        generic_name=generic,
        strength=Strength(value=strength_val, unit="mg"),
        dosage_form=DosageForm.TABLET,
        composition=f"Each tablet contains: {generic} IP {int(strength_val)} mg",
        manufacturer=Manufacturer(
            name="IntegTest Pharma Ltd.",
            address="Test Address, Mumbai",
            license_no="MH/TEST/000001",
        ),
    )
    blister = BlisterSpec(length=blister_l, width=blister_w, height=blister_h)
    config = PackagingConfig(
        product=product, blister=blister, pack_size="1 x 10", mrp=mrp
    )
    config.carton.calculate_from_blister(blister)
    return config


class TestEndToEnd:
    def test_full_pipeline_dxf(self, tmp_path):
        """Product spec → dieline → DXF file."""
        config = _make_config("AZICURE", "Azithromycin", 500, 120, 50, 8)
        dieline = compute_dieline(config.carton)
        path = tmp_path / "output.dxf"
        result = export_dxf(dieline, config.carton, path)
        assert result.exists()
        assert result.stat().st_size > 1000  # reasonable file size

    def test_full_pipeline_pdf(self, tmp_path):
        """Product spec → dieline → artwork → PDF file."""
        config = _make_config(
            "AZICURE", "Azithromycin", 500, 120, 50, 8, mrp="₹125.50"
        )
        dieline = compute_dieline(config.carton)
        artwork = generate_default_artwork(config)
        path = tmp_path / "output.pdf"
        result = compose_artwork_pdf(config, dieline, artwork, path)
        assert result.exists()
        assert result.stat().st_size > 1000

    def test_multiple_strengths(self, tmp_path):
        """Different strengths should produce different artwork content."""
        configs = [
            _make_config("PARACIP", "Paracetamol", 250, 100, 40, 6),
            _make_config("PARACIP", "Paracetamol", 500, 120, 50, 8),
            _make_config("PARACIP", "Paracetamol", 650, 130, 55, 9),
        ]

        pdfs = []
        for i, config in enumerate(configs):
            dieline = compute_dieline(config.carton)
            artwork = generate_default_artwork(config)
            path = tmp_path / f"strength_{int(config.product.strength.value)}.pdf"
            compose_artwork_pdf(config, dieline, artwork, path)
            pdfs.append(path)
            assert path.exists()

        # All PDFs should be different sizes (different carton dimensions)
        sizes = [p.stat().st_size for p in pdfs]
        # At minimum, different content should produce different file sizes
        # (This is a weak check — content comparison would be stronger)
        assert len(set(sizes)) >= 2

    def test_different_blisters_produce_different_dielines(self, tmp_path):
        """Different blister sizes must produce different carton dimensions."""
        small = _make_config("DRUG", "Test", 100, 80, 30, 5)
        large = _make_config("DRUG", "Test", 100, 150, 70, 12)

        d_small = compute_dieline(small.carton)
        d_large = compute_dieline(large.carton)

        assert d_large.total_width > d_small.total_width
        assert d_large.total_height > d_small.total_height

    def test_serialization_roundtrip(self):
        """PackagingConfig should serialize to JSON and back."""
        config = _make_config("AZICURE", "Azithromycin", 500, 120, 50, 8)
        json_str = config.model_dump_json(indent=2)
        restored = PackagingConfig.model_validate_json(json_str)
        assert restored.product.brand_name == "AZICURE"
        assert restored.blister.length == 120
        assert restored.carton.internal_length == 124.0
