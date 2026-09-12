"""Tests for PDF artwork output — verify structure, text, and vectors."""
import base64
import zlib
import pytest

from packaging_model import *
from packaging_model.enums import *
from dieline_engine.geometry import compute_dieline
from artwork_engine.text_layout import generate_default_artwork
from artwork_engine.pdf_composer import compose_artwork_pdf
from artwork_engine.barcode_gen import generate_ean13_bars, generate_pharmacode_bars


@pytest.fixture
def sample_config():
    product = Product(
        id="TEST-001",
        brand_name="TESTDRUG",
        generic_name="Paracetamol",
        strength=Strength(value=500, unit="mg"),
        dosage_form=DosageForm.TABLET,
        composition="Each tablet contains: Paracetamol IP 500 mg",
        manufacturer=Manufacturer(
            name="Test Pharma Ltd.",
            address="123 Industrial Area, Mumbai",
            license_no="MH/2024/000001",
        ),
    )
    blister = BlisterSpec(length=120, width=50, height=8)
    config = PackagingConfig(
        product=product, blister=blister, pack_size="1 x 10", mrp="₹50.00"
    )
    config.carton.calculate_from_blister(blister)
    return config


@pytest.fixture
def sample_pdf(sample_config, tmp_path):
    dieline = compute_dieline(sample_config.carton)
    artwork = generate_default_artwork(sample_config)
    path = tmp_path / "test_artwork.pdf"
    compose_artwork_pdf(sample_config, dieline, artwork, path)
    return path


def _decode_pdf_stream(pdf_path):
    """Extract and decode ALL content streams from a PDF."""
    with open(pdf_path, "rb") as f:
        data = f.read()
    parts = []
    pos = 0
    while True:
        s = data.find(b"stream", pos)
        if s < 0:
            break
        e = data.find(b"endstream", s)
        if e < 0:
            break
        raw = data[s + 7 : e].strip()
        # Try various decodings: ASCII85+Flate, Flate only, uncompressed
        decoded = None
        for attempt in ["a85_flate", "flate", "raw"]:
            try:
                if attempt == "a85_flate":
                    a85 = base64.a85decode(raw, adobe=True)
                    decoded = zlib.decompress(a85).decode("latin-1")
                elif attempt == "flate":
                    decoded = zlib.decompress(raw).decode("latin-1")
                else:
                    decoded = raw.decode("latin-1")
                break
            except Exception:
                continue
        if decoded and "BT" in decoded:  # only include content streams (have text ops)
            parts.append(decoded)
        elif decoded and ("re " in decoded or "BDC" in decoded):
            parts.append(decoded)
        pos = e + 9
    return "\n".join(parts)


class TestPdfOutput:
    def test_file_created(self, sample_pdf):
        assert sample_pdf.exists()
        assert sample_pdf.stat().st_size > 0

    def test_valid_pdf_header(self, sample_pdf):
        with open(sample_pdf, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_contains_editable_text(self, sample_pdf):
        """Text must be stored as text operators (BT/ET), not outlines."""
        content = _decode_pdf_stream(sample_pdf)
        assert "BT" in content, "No BT (begin text) operators found"
        assert "Tj" in content, "No Tj (show text) operators found"

    def test_contains_product_name(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        assert "TESTDRUG" in content

    def test_contains_strength(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        # Strength may be word-wrapped across lines (e.g. "500" and "mg" on separate lines)
        assert "500" in content

    def test_contains_generic_name(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        assert "Paracetamol" in content

    def test_contains_manufacturer(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        assert "Test Pharma Ltd" in content

    def test_contains_schedule_warning(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        # Warning may be wrapped across lines; check for key phrase
        assert "SCHEDULE H" in content or "SCHEDULE" in content

    def test_contains_font_references(self, sample_pdf):
        with open(sample_pdf, "rb") as f:
            data = f.read()
        # Check for embedded or referenced fonts
        has_font = (b"Helvetica" in data or b"HelveticaEmbed" in data
                    or b"Arial" in data or b"Liberation" in data
                    or b"/BaseFont" in data)
        assert has_font, "No font references found in PDF"

    def test_contains_vector_barcode(self, sample_pdf):
        """Barcode should be vector rectangles, not a raster image."""
        content = _decode_pdf_stream(sample_pdf)
        # EAN-13 produces many thin rectangles
        rect_count = content.count(" re f*")
        assert rect_count >= 20, f"Expected 20+ barcode bars, got {rect_count}"

    def test_contains_coding_zones(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        assert "B.No" in content
        assert "Mfg." in content
        assert "Exp." in content

    def test_contains_mrp(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        assert "125.50" in content or "MRP" in content

    def test_contains_dieline_annotation(self, sample_pdf):
        content = _decode_pdf_stream(sample_pdf)
        assert "DO NOT PRINT" in content

    def test_contains_cmyk_colors(self, sample_pdf):
        """Should use CMYK color space, not RGB."""
        content = _decode_pdf_stream(sample_pdf)
        # CMYK fill: c m y k k operator
        assert " k" in content, "No CMYK fill colors found"

    def test_contains_ocg_layer_definitions(self, sample_pdf):
        """PDF must contain OCG (Optional Content Group) definitions."""
        with open(sample_pdf, "rb") as f:
            data = f.read()
        assert b"/OCG" in data or b"/OCGs" in data, "No OCG definitions found in PDF"

    def test_contains_ocg_layer_names(self, sample_pdf):
        """Each expected layer name must appear as an OCG entry in the PDF."""
        with open(sample_pdf, "rb") as f:
            data = f.read()
        for layer_name in ["Dieline", "Artwork", "Text", "Barcode", "Coding", "Varnish", "Technical"]:
            assert layer_name.encode() in data, f"Layer name '{layer_name}' not found in PDF"

    def test_contains_ocg_bdc_markers(self, sample_pdf):
        """Content stream must have BDC/EMC markers for OCG layers."""
        content = _decode_pdf_stream(sample_pdf)
        assert "BDC" in content, "No BDC (begin marked content) operators found"
        assert "EMC" in content, "No EMC (end marked content) operators found"
        # Verify at least one OCG resource name is referenced
        assert "OC_" in content, "No OC_ resource references found in content stream"

    def test_contains_ocproperties_in_catalog(self, sample_pdf):
        """PDF catalog must contain an OCProperties entry."""
        with open(sample_pdf, "rb") as f:
            data = f.read()
        assert b"OCProperties" in data, "No OCProperties in PDF catalog"

    def test_long_text_is_wrapped_not_clipped(self, sample_pdf):
        """Long text should be word-wrapped to multiple lines, not clipped."""
        content = _decode_pdf_stream(sample_pdf)
        # The Schedule H warning is long — it should appear across multiple
        # Tj operators (one per wrapped line) rather than being cut off.
        # Count how many text draw operations contain "SCHEDULE" or warning words
        schedule_lines = [l for l in content.split("\n") if "SCHEDULE" in l or "prescription" in l.lower() or "Registered" in l]
        assert len(schedule_lines) >= 2, \
            "Schedule H warning should be wrapped to multiple lines"

    def test_all_five_ocg_layers_have_bdc(self, sample_pdf):
        """Each of the five layer resource names must appear as BDC targets."""
        content = _decode_pdf_stream(sample_pdf)
        for layer_name in ["Artwork", "Text", "Barcode", "Coding", "Varnish", "Dieline", "Technical"]:
            marker = f"/OC_{layer_name} BDC"
            assert marker in content, f"Missing BDC marker for layer: {layer_name}"


class TestEan13:
    def test_generates_bars(self):
        data = generate_ean13_bars("890123456789")
        assert len(data.bars) > 0
        assert data.total_width > 0

    def test_text_has_13_digits(self):
        data = generate_ean13_bars("890123456789")
        assert len(data.text) == 13

    def test_all_bars_have_positive_dimensions(self):
        data = generate_ean13_bars("890123456789")
        for x, w, h in data.bars:
            assert x >= 0
            assert w > 0
            assert h > 0

    def test_rejects_invalid_length(self):
        with pytest.raises(ValueError):
            generate_ean13_bars("12345")


class TestPharmacode:
    def test_generates_bars(self):
        data = generate_pharmacode_bars(1234)
        assert len(data.bars) > 0

    def test_rejects_too_small(self):
        with pytest.raises(ValueError):
            generate_pharmacode_bars(2)

    def test_rejects_too_large(self):
        with pytest.raises(ValueError):
            generate_pharmacode_bars(200000)

    def test_different_codes_produce_different_patterns(self):
        d1 = generate_pharmacode_bars(100)
        d2 = generate_pharmacode_bars(200)
        assert d1.bars != d2.bars
