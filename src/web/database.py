"""SQLAlchemy database models and setup for the pharma packaging platform.

Uses SQLite for local development. Connection string can be changed to
PostgreSQL when deploying to production.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, Column, String, Text, Float, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

# Database file location
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "pharma_packaging.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def new_uuid() -> str:
    return uuid.uuid4().hex


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(32), primary_key=True, default=new_uuid)
    name = Column(String(255), nullable=False)
    address = Column(Text, default="")
    license_no = Column(String(100), default="")
    logo_path = Column(String(500), nullable=True)
    brand_color_hex = Column(String(7), default="#1a56db")
    is_manufacturer = Column(Boolean, default=True)
    manufacturer_name = Column(String(255), nullable=True)
    manufacturer_address = Column(Text, nullable=True)
    manufacturer_license_no = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")

    @property
    def display_manufacturer_name(self) -> str:
        if self.is_manufacturer:
            return self.name
        return self.manufacturer_name or self.name

    @property
    def display_manufacturer_address(self) -> str:
        if self.is_manufacturer:
            return self.address
        return self.manufacturer_address or self.address

    @property
    def display_manufacturer_license(self) -> str:
        if self.is_manufacturer:
            return self.license_no
        return self.manufacturer_license_no or self.license_no


class Product(Base):
    __tablename__ = "products"

    id = Column(String(32), primary_key=True, default=new_uuid)
    org_id = Column(String(32), ForeignKey("organizations.id"), nullable=False)
    brand_name = Column(String(255), nullable=False)
    brand_name_hindi = Column(String(255), nullable=True)
    generic_name = Column(String(255), nullable=False)
    strength_value = Column(Float, nullable=False)
    strength_unit = Column(String(10), default="mg")
    dosage_form = Column(String(50), default="tablet")
    composition = Column(Text, default="")
    schedule_type = Column(String(5), nullable=True)  # "H", "H1", "X", or None
    storage_conditions = Column(String(500), default="Store below 25°C. Protect from light and moisture.")
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="products")
    projects = relationship("PackagingProject", back_populates="product", cascade="all, delete-orphan")

    @property
    def strength_display(self) -> str:
        v = int(self.strength_value) if self.strength_value == int(self.strength_value) else self.strength_value
        return f"{v} {self.strength_unit}"

    @property
    def schedule_warning(self) -> str:
        if self.schedule_type == "H":
            return ("SCHEDULE H DRUG - Warning: To be sold by retail on the "
                    "prescription of a Registered Medical Practitioner only.")
        if self.schedule_type == "H1":
            return ("SCHEDULE H1 DRUG - Warning: It is dangerous to take this "
                    "preparation except under medical supervision.")
        if self.schedule_type == "X":
            return ("SCHEDULE X DRUG - Warning: To be sold by retail on the "
                    "prescription of a Registered Medical Practitioner only.")
        return ""


class PackagingProject(Base):
    __tablename__ = "packaging_projects"

    id = Column(String(32), primary_key=True, default=new_uuid)
    product_id = Column(String(32), ForeignKey("products.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="draft")  # draft, generated, approved
    pack_size = Column(String(50), default="1 x 10")
    blisters_per_carton = Column(Integer, default=1)
    mrp = Column(String(50), nullable=True)
    blister_length = Column(Float, default=120.0)
    blister_width = Column(Float, default=50.0)
    blister_height = Column(Float, default=8.0)
    board_caliper = Column(Float, default=0.40)
    clearance = Column(Float, default=2.0)
    leaflet_allowance = Column(Float, default=5.0)
    output_dir = Column(String(500), nullable=True)
    validation_json = Column(Text, nullable=True)
    carton_internal_l = Column(Float, nullable=True)
    carton_internal_w = Column(Float, nullable=True)
    carton_internal_d = Column(Float, nullable=True)
    dieline_total_w = Column(Float, nullable=True)
    dieline_total_h = Column(Float, nullable=True)
    panel_count = Column(Integer, nullable=True)
    text_count = Column(Integer, nullable=True)
    barcode_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="projects")

    @property
    def organization(self):
        return self.product.organization if self.product else None


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise
