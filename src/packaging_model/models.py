"""Packaging object model — the structured representation of pharmaceutical packaging.

All dimensions are in millimeters unless otherwise specified.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from packaging_model.enums import (
    DosageForm,
    CartonConstruction,
    BoardGrade,
    PanelType,
    BarcodeType,
    ArtworkStatus,
    LayerName,
)


class Strength(BaseModel):
    value: float
    unit: str = "mg"

    def __str__(self) -> str:
        if self.value == int(self.value):
            return f"{int(self.value)} {self.unit}"
        return f"{self.value} {self.unit}"


class Manufacturer(BaseModel):
    name: str
    address: str
    license_no: str


class Product(BaseModel):
    id: str
    brand_name: str
    brand_name_hindi: Optional[str] = None  # e.g. "वेन्टीमॉक्स-250"
    generic_name: str
    strength: Strength
    dosage_form: DosageForm
    composition: str  # e.g. "Each tablet contains Azithromycin IP 500 mg"
    manufacturer: Manufacturer
    marketer: Optional[Manufacturer] = None  # if marketed by a different company
    schedule_warning: str = (
        "SCHEDULE H DRUG - Warning: To be sold by retail on the "
        "prescription of a Registered Medical Practitioner only."
    )
    storage_conditions: str = "Store below 25°C. Protect from light and moisture."


class BlisterSpec(BaseModel):
    """Primary packaging specification for a blister pack."""
    configuration: str = "1x10"  # rows × cavities
    length: float  # mm — overall blister length
    width: float   # mm — overall blister width
    height: float  # mm — max blister thickness including formed cavities
    material_base: str = "PVC 250μm"
    material_lidding: str = "Aluminium 20μm"


class BoardSpec(BaseModel):
    grade: BoardGrade = BoardGrade.GC1
    caliper: float = 0.40  # mm (400 microns)
    weight_gsm: int = 300


class CartonSpec(BaseModel):
    """Calculated carton dimensions."""
    construction: CartonConstruction = CartonConstruction.ECMA_A20_20
    board: BoardSpec = Field(default_factory=BoardSpec)
    clearance: float = 2.0  # mm per side
    leaflet_allowance: float = 5.0  # mm added to depth for folded leaflet
    blisters_per_carton: int = 1  # number of blister strips stacked in the carton

    # Internal dimensions (calculated from blister + clearances)
    internal_length: float = 0.0
    internal_width: float = 0.0
    internal_depth: float = 0.0

    def calculate_from_blister(self, blister: BlisterSpec) -> None:
        self.internal_length = blister.length + 2 * self.clearance
        self.internal_width = blister.width + 2 * self.clearance
        self.internal_depth = (
            blister.height * self.blisters_per_carton
            + self.leaflet_allowance
            + self.clearance
        )


class Panel(BaseModel):
    """A single panel in the flat dieline layout."""
    panel_type: PanelType
    x: float  # mm from left edge of flat layout
    y: float  # mm from bottom edge
    width: float  # mm — horizontal extent in flat layout
    height: float  # mm — vertical extent in flat layout


class DielineSpec(BaseModel):
    """Complete dieline specification with all panels and geometry."""
    version: str = "1.0"
    construction: CartonConstruction = CartonConstruction.ECMA_A20_20
    panels: List[Panel] = Field(default_factory=list)
    total_width: float = 0.0  # mm — total flat layout width
    total_height: float = 0.0  # mm — total flat layout height
    glue_tab_width: float = 15.0  # mm
    tuck_flap_depth: float = 0.0  # mm
    dust_flap_depth: float = 0.0  # mm


class SpotColor(BaseModel):
    name: str  # e.g. "Pantone 2945 C"
    cyan: float = 0.0
    magenta: float = 0.0
    yellow: float = 0.0
    black: float = 0.0


class TextElement(BaseModel):
    id: str
    content: str
    source_field: str  # e.g. "product.brand_name"
    panel_type: PanelType
    x: float  # mm offset within panel
    y: float  # mm offset within panel
    font_family: str = "Helvetica"
    font_size: float = 10.0  # points
    font_bold: bool = False
    color_name: Optional[str] = None  # spot color name, or None for process black
    rotation: float = 0.0  # degrees counter-clockwise (90 = vertical, bottom-to-top)


class BarcodeElement(BaseModel):
    id: str
    barcode_type: BarcodeType
    data: str  # encoded data
    panel_type: PanelType
    x: float
    y: float
    width: float = 37.29  # mm (EAN-13 nominal)
    height: float = 25.93  # mm


class CodingZone(BaseModel):
    id: str
    purpose: str  # "MRP", "batch", "date"
    panel_type: PanelType
    x: float
    y: float
    width: float
    height: float


class ArtworkSpec(BaseModel):
    id: str
    version: str = "1.0"
    status: ArtworkStatus = ArtworkStatus.DRAFT
    text_elements: List[TextElement] = Field(default_factory=list)
    barcodes: List[BarcodeElement] = Field(default_factory=list)
    coding_zones: List[CodingZone] = Field(default_factory=list)
    spot_colors: List[SpotColor] = Field(default_factory=list)
    layers: List[LayerName] = Field(
        default_factory=lambda: [
            LayerName.DIELINE,
            LayerName.ARTWORK,
            LayerName.TEXT,
            LayerName.BARCODE,
        ]
    )


class PackagingConfig(BaseModel):
    """Top-level packaging configuration tying everything together."""
    product: Product
    blister: BlisterSpec
    carton: CartonSpec = Field(default_factory=CartonSpec)
    dieline: Optional[DielineSpec] = None
    artwork: Optional[ArtworkSpec] = None
    pack_size: str = "1 x 10"
    mrp: Optional[str] = None  # e.g. "₹125.50"
    brand_color_hex: str = "#1a56db"  # organization's brand color
