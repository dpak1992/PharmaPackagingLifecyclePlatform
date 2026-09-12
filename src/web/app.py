"""FastAPI web application for the Pharma Packaging Lifecycle Platform.

Multi-tenant application with organization onboarding, product catalog,
and project-based packaging generation workflow.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, Form, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from packaging_model import (
    BlisterSpec, BoardSpec, CartonSpec, Manufacturer,
    PackagingConfig, Product, Strength,
)
from packaging_model.enums import DosageForm
from dieline_engine.geometry import compute_dieline
from dieline_engine.dxf_export import export_dxf
from artwork_engine.text_layout import generate_default_artwork, _DOSAGE_FORM_LABELS
from artwork_engine.pdf_composer import compose_artwork_pdf
from validation_engine import check_completeness, validate_barcodes

from web.database import (
    init_db, get_db, Organization, Product as DBProduct, PackagingProject,
)

# Initialize database
init_db()

app = FastAPI(title="Pharma Packaging Lifecycle Platform")

_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

# Static files for logos
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Project output directory
PROJECT_OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "projects"
PROJECT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─── Landing ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    db = get_db()
    try:
        orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()
        return templates.TemplateResponse("landing.html", {
            "request": request, "organizations": orgs,
        })
    finally:
        db.close()


# ─── Onboarding ────────────────────────────────────────────────────────

@app.get("/onboard", response_class=HTMLResponse)
async def onboard_form(request: Request):
    return templates.TemplateResponse("onboard.html", {
        "request": request, "org": None,
    })


@app.post("/onboard")
async def onboard_save(
    request: Request,
    name: str = Form(...),
    address: str = Form(""),
    license_no: str = Form(""),
    brand_color_hex: str = Form("#1a56db"),
    is_manufacturer: Optional[str] = Form(None),
    manufacturer_name: str = Form(""),
    manufacturer_address: str = Form(""),
    manufacturer_license_no: str = Form(""),
    logo: Optional[UploadFile] = File(None),
):
    db = get_db()
    try:
        org = Organization(
            name=name, address=address, license_no=license_no,
            brand_color_hex=brand_color_hex,
            is_manufacturer=bool(is_manufacturer),
            manufacturer_name=manufacturer_name or None,
            manufacturer_address=manufacturer_address or None,
            manufacturer_license_no=manufacturer_license_no or None,
        )
        db.add(org)
        db.flush()  # get the ID

        # Handle logo upload
        if logo and logo.filename:
            logo_dir = _static_dir / "uploads" / org.id
            logo_dir.mkdir(parents=True, exist_ok=True)
            ext = Path(logo.filename).suffix or ".png"
            logo_path = logo_dir / f"logo{ext}"
            with open(logo_path, "wb") as f:
                content = await logo.read()
                f.write(content)
            org.logo_path = f"uploads/{org.id}/logo{ext}"

        db.commit()
        return RedirectResponse(f"/org/{org.id}", status_code=303)
    except Exception as exc:
        db.rollback()
        return templates.TemplateResponse("onboard.html", {
            "request": request, "org": None, "error": str(exc),
        }, status_code=422)
    finally:
        db.close()


# ─── Organization ──────────────────────────────────────────────────────

@app.get("/org/{org_id}", response_class=HTMLResponse)
async def dashboard(request: Request, org_id: str):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if not org:
            return RedirectResponse("/", status_code=303)
        # Get all projects across all products, most recent first
        projects = (db.query(PackagingProject)
                    .join(DBProduct)
                    .filter(DBProduct.org_id == org_id)
                    .order_by(PackagingProject.created_at.desc())
                    .limit(20).all())
        return templates.TemplateResponse("dashboard.html", {
            "request": request, "org": org, "projects": projects,
        })
    finally:
        db.close()


@app.get("/org/{org_id}/edit", response_class=HTMLResponse)
async def org_edit_form(request: Request, org_id: str):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if not org:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("onboard.html", {
            "request": request, "org": org,
        })
    finally:
        db.close()


@app.post("/org/{org_id}/edit")
async def org_edit_save(
    request: Request, org_id: str,
    name: str = Form(...),
    address: str = Form(""),
    license_no: str = Form(""),
    brand_color_hex: str = Form("#1a56db"),
    is_manufacturer: Optional[str] = Form(None),
    manufacturer_name: str = Form(""),
    manufacturer_address: str = Form(""),
    manufacturer_license_no: str = Form(""),
    logo: Optional[UploadFile] = File(None),
):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if not org:
            return RedirectResponse("/", status_code=303)

        org.name = name
        org.address = address
        org.license_no = license_no
        org.brand_color_hex = brand_color_hex
        org.is_manufacturer = bool(is_manufacturer)
        org.manufacturer_name = manufacturer_name or None
        org.manufacturer_address = manufacturer_address or None
        org.manufacturer_license_no = manufacturer_license_no or None

        if logo and logo.filename:
            logo_dir = _static_dir / "uploads" / org.id
            logo_dir.mkdir(parents=True, exist_ok=True)
            ext = Path(logo.filename).suffix or ".png"
            logo_path = logo_dir / f"logo{ext}"
            with open(logo_path, "wb") as f:
                content = await logo.read()
                f.write(content)
            org.logo_path = f"uploads/{org.id}/logo{ext}"

        db.commit()
        return RedirectResponse(f"/org/{org.id}", status_code=303)
    except Exception as exc:
        db.rollback()
        return templates.TemplateResponse("onboard.html", {
            "request": request, "org": org, "error": str(exc),
        }, status_code=422)
    finally:
        db.close()


@app.get("/logo/{org_id}")
async def serve_logo(org_id: str):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if not org or not org.logo_path:
            return HTMLResponse("No logo", status_code=404)
        logo_file = _static_dir / org.logo_path
        if not logo_file.exists():
            return HTMLResponse("Logo file not found", status_code=404)
        return FileResponse(str(logo_file))
    finally:
        db.close()


# ─── Products ──────────────────────────────────────────────────────────

@app.get("/org/{org_id}/product/new", response_class=HTMLResponse)
async def product_new_form(request: Request, org_id: str):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        if not org:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("product_form.html", {
            "request": request, "org": org, "product": None,
            "dosage_forms": list(DosageForm),
        })
    finally:
        db.close()


@app.post("/org/{org_id}/product/new")
async def product_new_save(
    request: Request, org_id: str,
    brand_name: str = Form(...),
    brand_name_hindi: str = Form(""),
    generic_name: str = Form(...),
    strength_value: float = Form(...),
    strength_unit: str = Form("mg"),
    dosage_form: str = Form("tablet"),
    composition: str = Form(...),
    schedule_type: str = Form(""),
    storage_conditions: str = Form("Store below 25°C. Protect from light and moisture."),
):
    db = get_db()
    try:
        product = DBProduct(
            org_id=org_id,
            brand_name=brand_name,
            brand_name_hindi=brand_name_hindi or None,
            generic_name=generic_name,
            strength_value=strength_value,
            strength_unit=strength_unit,
            dosage_form=dosage_form,
            composition=composition,
            schedule_type=schedule_type or None,
            storage_conditions=storage_conditions,
        )
        db.add(product)
        db.commit()
        return RedirectResponse(f"/org/{org_id}", status_code=303)
    except Exception as exc:
        db.rollback()
        org = db.query(Organization).filter_by(id=org_id).first()
        return templates.TemplateResponse("product_form.html", {
            "request": request, "org": org, "product": None,
            "dosage_forms": list(DosageForm), "error": str(exc),
        }, status_code=422)
    finally:
        db.close()


@app.get("/org/{org_id}/product/{product_id}/edit", response_class=HTMLResponse)
async def product_edit_form(request: Request, org_id: str, product_id: str):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        product = db.query(DBProduct).filter_by(id=product_id, org_id=org_id).first()
        if not org or not product:
            return RedirectResponse(f"/org/{org_id}", status_code=303)
        return templates.TemplateResponse("product_form.html", {
            "request": request, "org": org, "product": product,
            "dosage_forms": list(DosageForm),
        })
    finally:
        db.close()


@app.post("/org/{org_id}/product/{product_id}/edit")
async def product_edit_save(
    request: Request, org_id: str, product_id: str,
    brand_name: str = Form(...),
    brand_name_hindi: str = Form(""),
    generic_name: str = Form(...),
    strength_value: float = Form(...),
    strength_unit: str = Form("mg"),
    dosage_form: str = Form("tablet"),
    composition: str = Form(...),
    schedule_type: str = Form(""),
    storage_conditions: str = Form("Store below 25°C. Protect from light and moisture."),
):
    db = get_db()
    try:
        product = db.query(DBProduct).filter_by(id=product_id, org_id=org_id).first()
        if not product:
            return RedirectResponse(f"/org/{org_id}", status_code=303)
        product.brand_name = brand_name
        product.brand_name_hindi = brand_name_hindi or None
        product.generic_name = generic_name
        product.strength_value = strength_value
        product.strength_unit = strength_unit
        product.dosage_form = dosage_form
        product.composition = composition
        product.schedule_type = schedule_type or None
        product.storage_conditions = storage_conditions
        db.commit()
        return RedirectResponse(f"/org/{org_id}", status_code=303)
    finally:
        db.close()


# ─── Packaging Projects ───────────────────────────────────────────────

@app.get("/org/{org_id}/product/{product_id}/project/new", response_class=HTMLResponse)
async def project_new_form(request: Request, org_id: str, product_id: str):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        product = db.query(DBProduct).filter_by(id=product_id, org_id=org_id).first()
        if not org or not product:
            return RedirectResponse(f"/org/{org_id}", status_code=303)
        return templates.TemplateResponse("project_form.html", {
            "request": request, "org": org, "product": product,
        })
    finally:
        db.close()


def _build_packaging_config(org: Organization, product: DBProduct, proj: PackagingProject) -> PackagingConfig:
    """Build a PackagingConfig from database objects."""
    # Determine manufacturer and marketer
    mfg = Manufacturer(
        name=org.display_manufacturer_name,
        address=org.display_manufacturer_address,
        license_no=org.display_manufacturer_license,
    )
    marketer = None
    if not org.is_manufacturer:
        # Org is the marketer, manufacturer is separate
        marketer = Manufacturer(name=org.name, address=org.address, license_no=org.license_no)

    # MRP
    mrp_str = None
    if proj.mrp and proj.mrp.strip():
        raw = proj.mrp.strip().lstrip("Rs.").lstrip("Rs").lstrip("\u20b9").strip()
        mrp_str = f"\u20b9{raw}"

    p = Product(
        id=f"{product.brand_name.upper()}-{int(product.strength_value)}",
        brand_name=product.brand_name,
        brand_name_hindi=product.brand_name_hindi,
        generic_name=product.generic_name,
        strength=Strength(value=product.strength_value, unit=product.strength_unit),
        dosage_form=DosageForm(product.dosage_form),
        composition=product.composition,
        manufacturer=mfg,
        marketer=marketer,
        schedule_warning=product.schedule_warning,
        storage_conditions=product.storage_conditions,
    )

    blister = BlisterSpec(
        length=proj.blister_length, width=proj.blister_width, height=proj.blister_height,
    )
    carton = CartonSpec(
        board=BoardSpec(caliper=proj.board_caliper),
        clearance=proj.clearance,
        leaflet_allowance=proj.leaflet_allowance,
        blisters_per_carton=proj.blisters_per_carton,
    )

    config = PackagingConfig(
        product=p, blister=blister, carton=carton,
        pack_size=proj.pack_size, mrp=mrp_str,
        brand_color_hex=org.brand_color_hex,
    )
    config.carton.calculate_from_blister(blister)
    return config


@app.post("/org/{org_id}/product/{product_id}/project/new")
async def project_generate(
    request: Request, org_id: str, product_id: str,
    name: str = Form(...),
    pack_size: str = Form("10x3x10"),
    blisters_per_carton: int = Form(3),
    mrp: str = Form(""),
    blister_length: float = Form(189.0),
    blister_width: float = Form(53.0),
    blister_height: float = Form(8.4),
    board_caliper: float = Form(0.40),
    clearance: float = Form(2.0),
    leaflet_allowance: float = Form(5.0),
):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        product = db.query(DBProduct).filter_by(id=product_id, org_id=org_id).first()
        if not org or not product:
            return RedirectResponse(f"/org/{org_id}", status_code=303)

        # Create project record
        proj = PackagingProject(
            product_id=product_id, name=name, status="draft",
            pack_size=pack_size, blisters_per_carton=blisters_per_carton,
            mrp=mrp or None,
            blister_length=blister_length, blister_width=blister_width,
            blister_height=blister_height,
            board_caliper=board_caliper, clearance=clearance,
            leaflet_allowance=leaflet_allowance,
        )
        db.add(proj)
        db.flush()

        # Build packaging config from DB objects
        config = _build_packaging_config(org, product, proj)

        # Generate
        dieline = compute_dieline(config.carton)
        artwork = generate_default_artwork(config)

        # Save output files
        out_dir = PROJECT_OUTPUT_DIR / proj.id
        out_dir.mkdir(parents=True, exist_ok=True)

        export_dxf(dieline, config.carton, str(out_dir / "dieline.dxf"))
        compose_artwork_pdf(config, dieline, artwork, str(out_dir / "artwork.pdf"))
        with open(out_dir / "config.json", "w") as f:
            f.write(config.model_dump_json(indent=2))

        # Run validation
        completeness_results = check_completeness(config, artwork)
        barcode_results = validate_barcodes(artwork)
        all_validations = completeness_results + barcode_results

        # Update project record
        proj.status = "generated"
        proj.output_dir = str(out_dir)
        proj.carton_internal_l = config.carton.internal_length
        proj.carton_internal_w = config.carton.internal_width
        proj.carton_internal_d = config.carton.internal_depth
        proj.dieline_total_w = dieline.total_width
        proj.dieline_total_h = dieline.total_height
        proj.panel_count = len(dieline.panels)
        proj.text_count = len(artwork.text_elements)
        proj.barcode_count = len(artwork.barcodes)
        proj.validation_json = json.dumps([v.model_dump() for v in all_validations])

        db.commit()
        return RedirectResponse(f"/org/{org_id}/project/{proj.id}", status_code=303)

    except Exception as exc:
        db.rollback()
        org = db.query(Organization).filter_by(id=org_id).first()
        product = db.query(DBProduct).filter_by(id=product_id, org_id=org_id).first()
        return templates.TemplateResponse("project_form.html", {
            "request": request, "org": org, "product": product,
            "error": f"Generation failed: {exc}",
        }, status_code=422)
    finally:
        db.close()


# ─── Project Results ───────────────────────────────────────────────────

@app.get("/org/{org_id}/project/{project_id}", response_class=HTMLResponse)
async def project_results(request: Request, org_id: str, project_id: str):
    db = get_db()
    try:
        org = db.query(Organization).filter_by(id=org_id).first()
        proj = db.query(PackagingProject).filter_by(id=project_id).first()
        if not org or not proj:
            return RedirectResponse(f"/org/{org_id}", status_code=303)

        product = proj.product

        # Parse validation results
        validation_pass, validation_fail, validation_warn = [], [], []
        if proj.validation_json:
            from validation_engine.models import ValidationResult
            all_v = [ValidationResult(**v) for v in json.loads(proj.validation_json)]
            validation_pass = [v for v in all_v if v.status.value == "pass"]
            validation_fail = [v for v in all_v if v.status.value == "fail"]
            validation_warn = [v for v in all_v if v.status.value == "warning"]

        # Brand color for 3D preview
        brand_cmyk = None
        # Convert hex to approximate CMYK for 3D preview
        hex_color = org.brand_color_hex.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16)/255, int(hex_color[2:4], 16)/255, int(hex_color[4:6], 16)/255
            k = 1 - max(r, g, b)
            if k < 1:
                c_val = (1 - r - k) / (1 - k) * 100
                m_val = (1 - g - k) / (1 - k) * 100
                y_val = (1 - b - k) / (1 - k) * 100
            else:
                c_val = m_val = y_val = 0
            brand_cmyk = {"c": c_val, "m": m_val, "y": y_val, "k": k * 100}

        dosage_label = _DOSAGE_FORM_LABELS.get(DosageForm(product.dosage_form), "Tablets IP")

        return templates.TemplateResponse("result.html", {
            "request": request,
            "org": org,
            "project": proj,
            "job_id": proj.id,
            "carton_l": proj.carton_internal_l,
            "carton_w": proj.carton_internal_w,
            "carton_d": proj.carton_internal_d,
            "dieline_w": proj.dieline_total_w,
            "dieline_h": proj.dieline_total_h,
            "panel_count": proj.panel_count,
            "text_count": proj.text_count,
            "barcode_count": proj.barcode_count,
            "brand_name": product.brand_name,
            "brand_name_hindi": product.brand_name_hindi or "",
            "strength_str": product.strength_display,
            "strength_val": int(product.strength_value),
            "generic_name": product.generic_name,
            "dosage_label": dosage_label,
            "pack_size": proj.pack_size,
            "composition": product.composition.replace("\n", " ").replace("'", "\\'"),
            "storage": product.storage_conditions.replace("'", "\\'"),
            "mfg_name": org.display_manufacturer_name.replace("'", "\\'"),
            "mfg_address": org.display_manufacturer_address.replace("\n", ", ").replace("'", "\\'"),
            "mfg_license": org.display_manufacturer_license,
            "marketer_name": (org.name if not org.is_manufacturer else "").replace("'", "\\'"),
            "marketer_address": (org.address if not org.is_manufacturer else "").replace("\n", ", ").replace("'", "\\'"),
            "has_schedule_h": bool(product.schedule_type),
            "brand_cmyk": brand_cmyk,
            "validation_pass": validation_pass,
            "validation_fail": validation_fail,
            "validation_warn": validation_warn,
            "validation_total": len(validation_pass) + len(validation_fail) + len(validation_warn),
        })
    finally:
        db.close()


# ─── File Downloads ────────────────────────────────────────────────────

@app.get("/download/{project_id}/{filetype}")
async def download(project_id: str, filetype: str):
    db = get_db()
    try:
        proj = db.query(PackagingProject).filter_by(id=project_id).first()
        if not proj or not proj.output_dir:
            return HTMLResponse("Project not found.", status_code=404)

        file_map = {
            "dxf": ("dieline.dxf", "application/dxf"),
            "pdf": ("artwork.pdf", "application/pdf"),
            "json": ("config.json", "application/json"),
        }
        entry = file_map.get(filetype)
        if not entry:
            return HTMLResponse("Invalid file type.", status_code=400)

        filename, media_type = entry
        file_path = Path(proj.output_dir) / filename
        if not file_path.exists():
            return HTMLResponse("File not found.", status_code=404)

        return FileResponse(str(file_path), media_type=media_type, filename=filename)
    finally:
        db.close()


@app.get("/preview/{project_id}")
async def preview(project_id: str):
    db = get_db()
    try:
        proj = db.query(PackagingProject).filter_by(id=project_id).first()
        if not proj or not proj.output_dir:
            return HTMLResponse("Project not found.", status_code=404)
        pdf_path = Path(proj.output_dir) / "artwork.pdf"
        if not pdf_path.exists():
            return HTMLResponse("PDF not found.", status_code=404)
        return FileResponse(str(pdf_path), media_type="application/pdf")
    finally:
        db.close()
