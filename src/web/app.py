"""FastAPI web application for the Pharma Packaging Lifecycle Platform."""

import tempfile
import uuid
from pathlib import Path

from typing import Dict, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from packaging_model import (
    BlisterSpec,
    BoardSpec,
    CartonSpec,
    Manufacturer,
    PackagingConfig,
    Product,
    Strength,
)
from packaging_model.enums import DosageForm
from dieline_engine.geometry import compute_dieline
from dieline_engine.dxf_export import export_dxf
from artwork_engine.text_layout import generate_default_artwork
from artwork_engine.pdf_composer import compose_artwork_pdf
from validation_engine import check_completeness, validate_barcodes

app = FastAPI(title="Pharma Packaging Lifecycle Platform")

_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

# In-memory job store: job_id -> temp directory path
_jobs: Dict[str, str] = {}


@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request, error: Optional[str] = None):
    """Render the product specification form."""
    return templates.TemplateResponse(
        "form.html",
        {
            "request": request,
            "dosage_forms": list(DosageForm),
            "error": error,
        },
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    request: Request,
    brand_name: str = Form(...),
    generic_name: str = Form(...),
    strength: float = Form(...),
    strength_unit: str = Form("mg"),
    dosage_form: str = Form("tablet"),
    composition: str = Form(...),
    schedule_h: Optional[str] = Form(None),
    mfg_name: str = Form(...),
    mfg_address: str = Form(...),
    license_no: str = Form(...),
    pack_size: str = Form("1 x 10"),
    mrp: str = Form(""),
    blister_length: float = Form(120.0),
    blister_width: float = Form(50.0),
    blister_height: float = Form(8.0),
    board_caliper: float = Form(0.40),
    clearance: float = Form(2.0),
    leaflet_allowance: float = Form(5.0),
):
    """Process the form, generate dieline + artwork, and render results."""
    try:
        # Build MRP string
        mrp_str = None
        if mrp and mrp.strip():
            raw = mrp.strip().lstrip("Rs.").lstrip("Rs").lstrip("\u20b9").strip()
            mrp_str = f"\u20b9{raw}"

        # Schedule H warning
        schedule_warning = (
            "SCHEDULE H DRUG - Warning: To be sold by retail on the "
            "prescription of a Registered Medical Practitioner only."
        ) if schedule_h else ""

        product = Product(
            id=f"{brand_name.upper().replace(' ', '-')}-{int(strength)}",
            brand_name=brand_name,
            generic_name=generic_name,
            strength=Strength(value=strength, unit=strength_unit),
            dosage_form=DosageForm(dosage_form),
            composition=composition,
            manufacturer=Manufacturer(
                name=mfg_name,
                address=mfg_address,
                license_no=license_no,
            ),
            schedule_warning=schedule_warning,
        )

        blister = BlisterSpec(
            length=blister_length,
            width=blister_width,
            height=blister_height,
        )

        carton = CartonSpec(
            board=BoardSpec(caliper=board_caliper),
            clearance=clearance,
            leaflet_allowance=leaflet_allowance,
        )

        config = PackagingConfig(
            product=product,
            blister=blister,
            carton=carton,
            pack_size=pack_size,
            mrp=mrp_str,
        )
        config.carton.calculate_from_blister(blister)

        # Generate dieline and artwork
        dieline = compute_dieline(config.carton)
        artwork = generate_default_artwork(config)

        # Write outputs to a temp directory
        tmp_dir = tempfile.mkdtemp(prefix="pharma_pkg_")
        dxf_path = Path(tmp_dir) / "dieline.dxf"
        pdf_path = Path(tmp_dir) / "artwork.pdf"
        json_path = Path(tmp_dir) / "config.json"

        export_dxf(dieline, config.carton, str(dxf_path))
        compose_artwork_pdf(config, dieline, artwork, str(pdf_path))

        with open(json_path, "w") as f:
            f.write(config.model_dump_json(indent=2))

        # Run validation
        completeness_results = check_completeness(config, artwork)
        barcode_results = validate_barcodes(artwork)
        all_validations = completeness_results + barcode_results

        # Separate by status
        validation_pass = [v for v in all_validations if v.status.value == "pass"]
        validation_fail = [v for v in all_validations if v.status.value == "fail"]
        validation_warn = [v for v in all_validations if v.status.value == "warning"]

        # Store job
        job_id = uuid.uuid4().hex
        _jobs[job_id] = tmp_dir

        # Prepare spot color for 3D preview
        brand_cmyk = None
        if artwork.spot_colors:
            sc = artwork.spot_colors[0]
            brand_cmyk = {
                "c": sc.cyan, "m": sc.magenta,
                "y": sc.yellow, "k": sc.black,
            }

        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "job_id": job_id,
                "carton_l": config.carton.internal_length,
                "carton_w": config.carton.internal_width,
                "carton_d": config.carton.internal_depth,
                "dieline_w": dieline.total_width,
                "dieline_h": dieline.total_height,
                "panel_count": len(dieline.panels),
                "text_count": len(artwork.text_elements),
                "barcode_count": len(artwork.barcodes),
                "brand_name": config.product.brand_name,
                "strength_str": str(config.product.strength),
                "generic_name": config.product.generic_name,
                "brand_cmyk": brand_cmyk,
                "validation_pass": validation_pass,
                "validation_fail": validation_fail,
                "validation_warn": validation_warn,
                "validation_total": len(all_validations),
            },
        )

    except Exception as exc:
        return templates.TemplateResponse(
            "form.html",
            {
                "request": request,
                "dosage_forms": list(DosageForm),
                "error": f"Generation failed: {exc}",
            },
            status_code=422,
        )


@app.get("/download/{job_id}/{filetype}")
async def download(job_id: str, filetype: str):
    """Serve a generated file for download."""
    tmp_dir = _jobs.get(job_id)
    if not tmp_dir:
        return HTMLResponse("Job not found. Please generate packaging first.", status_code=404)

    file_map = {
        "dxf": ("dieline.dxf", "application/dxf", "dieline.dxf"),
        "pdf": ("artwork.pdf", "application/pdf", "artwork.pdf"),
        "json": ("config.json", "application/json", "config.json"),
    }

    entry = file_map.get(filetype)
    if not entry:
        return HTMLResponse("Invalid file type.", status_code=400)

    filename, media_type, download_name = entry
    file_path = Path(tmp_dir) / filename

    if not file_path.exists():
        return HTMLResponse("File not found.", status_code=404)

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=download_name,
    )


@app.get("/preview/{job_id}")
async def preview(job_id: str):
    """Serve the PDF for inline preview."""
    tmp_dir = _jobs.get(job_id)
    if not tmp_dir:
        return HTMLResponse("Job not found.", status_code=404)

    pdf_path = Path(tmp_dir) / "artwork.pdf"
    if not pdf_path.exists():
        return HTMLResponse("PDF not found.", status_code=404)

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
    )
