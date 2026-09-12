# Multi-Tenant Onboarding & Project Workflow — Design Spec

**Date:** 2026-09-12
**Status:** Approved

## Overview

Transform the pharma packaging platform from a single-form demo into a
multi-tenant application with company onboarding, product catalogs, and
project-based packaging design workflow. No authentication for now.

## Data Model

### Organization
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| name | str | "Univentis Medicare Ltd." |
| address | text | |
| license_no | str | |
| logo_path | str (nullable) | relative path to uploaded logo |
| brand_color_hex | str | "#e87722" |
| is_manufacturer | bool | true if they manufacture in-house |
| manufacturer_name | str (nullable) | if contract manufactured |
| manufacturer_address | text (nullable) | |
| manufacturer_license_no | str (nullable) | |
| created_at | datetime | |

### Product
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| org_id | UUID (FK → Organization) | |
| brand_name | str | "Ventimox" |
| brand_name_hindi | str (nullable) | |
| generic_name | str | "Amoxycillin Trihydrate" |
| strength_value | float | 250 |
| strength_unit | str | "mg" |
| dosage_form | str | "capsule" |
| composition | text | |
| schedule_type | str (nullable) | "H", "H1", "X", or null |
| storage_conditions | str | |
| created_at | datetime | |

### PackagingProject
| Field | Type | Notes |
|-------|------|-------|
| id | UUID (PK) | |
| product_id | UUID (FK → Product) | |
| name | str | "Ventimox-250 10x3x10 Carton" |
| status | str | "draft", "generated", "approved" |
| pack_size | str | "10x3x10" |
| blisters_per_carton | int | 3 |
| mrp | str (nullable) | |
| blister_length | float | mm |
| blister_width | float | mm |
| blister_height | float | mm |
| board_caliper | float | mm |
| clearance | float | mm |
| leaflet_allowance | float | mm |
| output_dir | str (nullable) | path to generated files |
| validation_json | text (nullable) | JSON string of validation results |
| carton_internal_l | float (nullable) | calculated, stored for display |
| carton_internal_w | float (nullable) | |
| carton_internal_d | float (nullable) | |
| created_at | datetime | |
| updated_at | datetime | |

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | / | Landing — list orgs or "Get Started" |
| GET | /onboard | Organization setup form |
| POST | /onboard | Save org → redirect to dashboard |
| GET | /org/{org_id} | Dashboard — products + recent projects |
| GET | /org/{org_id}/edit | Edit org form |
| POST | /org/{org_id}/edit | Save org changes |
| GET | /org/{org_id}/product/new | New product form |
| POST | /org/{org_id}/product/new | Save product |
| GET | /org/{org_id}/product/{pid}/edit | Edit product form |
| POST | /org/{org_id}/product/{pid}/edit | Save product changes |
| GET | /org/{org_id}/product/{pid}/project/new | Project form (blister/carton params) |
| POST | /org/{org_id}/product/{pid}/project/new | Generate packaging → redirect to results |
| GET | /org/{org_id}/project/{proj_id} | Results page (3D, PDF, validation) |
| GET | /download/{proj_id}/{filetype} | Download DXF/PDF/JSON |
| GET | /preview/{proj_id} | PDF inline preview |
| GET | /logo/{org_id} | Serve uploaded logo |

## User Flow

1. Landing page → "Get Started" button (if no orgs) or org cards
2. Onboarding form → company name, address, license, logo upload, brand color, manufacturer details
3. Dashboard → "Add Product" button + product cards + recent project list
4. Product form → brand, generic, strength, dosage, composition, schedule, storage
5. Project form → select blister dims, carton params, MRP → "Generate"
6. Results page → 3D preview, validation, downloads (same as current but persistent)

## File Structure

```
src/web/
├── app.py              — FastAPI routes (rewritten)
├── database.py         — SQLAlchemy models + engine (SQLite)
├── templates/
│   ├── base.html       — shared layout (nav with org name/logo)
│   ├── landing.html    — org list or get started
│   ├── onboard.html    — org setup form
│   ├── dashboard.html  — products + projects
│   ├── product_form.html
│   ├── project_form.html
│   └── result.html     — updated to load from project
└── static/
    └── uploads/        — logo files
data/
└── projects/           — generated output files (persistent)
```

## File Storage

- Logos: `src/web/static/uploads/{org_id}/logo.{ext}`
- Project outputs: `data/projects/{project_id}/dieline.dxf`, `artwork.pdf`, `config.json`
- SQLite database: `data/pharma_packaging.db`

## Dependencies

Add `sqlalchemy>=2.0` to pyproject.toml `[project.optional-dependencies] web`.

## What Stays Unchanged

- src/packaging_model/ — all Pydantic models
- src/dieline_engine/ — dieline generation
- src/artwork_engine/ — PDF composition
- src/validation_engine/ — validation checks
- tests/ — all 78 existing tests
- 3D viewer JS, PDF preview, download logic (moved into new routes)

## Implementation Order

1. database.py — SQLAlchemy models + setup
2. base.html — shared template layout
3. landing.html + onboard.html + onboard routes
4. dashboard.html + org routes
5. product_form.html + product routes
6. project_form.html + project routes (migrate current generate logic)
7. result.html updates (load from DB instead of temp dict)
8. Logo upload + serving
9. Wire existing engines into project generation
