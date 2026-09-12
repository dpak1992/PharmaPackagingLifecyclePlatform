from enum import Enum


class DosageForm(str, Enum):
    TABLET = "tablet"
    CAPSULE = "capsule"
    FILM_COATED_TABLET = "film_coated_tablet"
    CHEWABLE_TABLET = "chewable_tablet"


class CartonConstruction(str, Enum):
    """ECMA standard carton construction codes."""
    ECMA_A20_20 = "ECMA_A20_20"  # Reverse tuck-end (most common pharma)
    ECMA_A20_04 = "ECMA_A20_04"  # Straight tuck-end
    ECMA_A55_03 = "ECMA_A55_03"  # Crash-lock bottom with tuck top


class BoardGrade(str, Enum):
    GC1 = "GC1"  # Coated one side, virgin fiber
    SBS = "SBS"  # Solid bleached sulfate
    FBB = "FBB"  # Folding boxboard


class PanelType(str, Enum):
    FRONT = "front"
    BACK = "back"
    SIDE_LEFT = "side_left"
    SIDE_RIGHT = "side_right"
    TOP_TUCK = "top_tuck"
    BOTTOM_TUCK = "bottom_tuck"
    TOP_DUST = "top_dust"
    BOTTOM_DUST = "bottom_dust"
    GLUE_TAB = "glue_tab"


class PanelPosition(str, Enum):
    """Position of panel in the flat dieline layout (left to right)."""
    GLUE_TAB = "glue_tab"
    PANEL_1 = "panel_1"  # Width panel (front)
    PANEL_2 = "panel_2"  # Length panel (side right)
    PANEL_3 = "panel_3"  # Width panel (back)
    PANEL_4 = "panel_4"  # Length panel (side left)


class BarcodeType(str, Enum):
    EAN_13 = "EAN-13"
    PHARMACODE = "pharmacode"
    DATA_MATRIX = "DataMatrix"
    CODE_128 = "Code128"


class ArtworkStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class LayerName(str, Enum):
    """Standard layer names for packaging artwork."""
    DIELINE = "Dieline"
    ARTWORK = "Artwork"
    TEXT = "Text"
    BARCODE = "Barcode"
    VARNISH = "Varnish"
    FOIL = "Foil"
    BRAILLE = "Braille"
    CODING = "Coding"
    TECHNICAL = "Technical"
