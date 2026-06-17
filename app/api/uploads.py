"""Upload and ingest endpoints + main dashboard UI."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from fcmr_core.catalog import store
from fcmr_core.config import settings
from fcmr_core.ingestion.pipeline import ingest_csv
from fcmr_core.schemas.loader import available_report_types

router = APIRouter()
_templates_dir = Path(__file__).parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    uploads = store.list_uploads()
    report_types = available_report_types()
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"uploads": uploads, "report_types": report_types},
    )


@router.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request):
    report_types = available_report_types()
    return templates.TemplateResponse(
        request=request, name="upload.html",
        context={"report_types": report_types},
    )


@router.post("/upload")
async def do_upload(
    request: Request,
    report_type: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    # Size guard
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 2 GB upload limit.")

    upload_id = store.create_upload(report_type, file.filename)
    dest_dir = settings.uploads_dir / upload_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    csv_path = dest_dir / file.filename

    csv_path.write_bytes(content)

    # Ingest synchronously (streaming; safe for 5M rows)
    try:
        result = ingest_csv(csv_path, report_type, upload_id)
        store.update_upload(upload_id, parquet_path=result.parquet_path, row_count=result.total_rows)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

    return RedirectResponse(url=f"/uploads/{upload_id}", status_code=303)


@router.get("/uploads/{upload_id}", response_class=HTMLResponse)
async def upload_detail(request: Request, upload_id: str):
    uploads_list = store.list_uploads()
    upload = next((u for u in uploads_list if u["upload_id"] == upload_id), None)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    runs = store.list_runs(upload_id)
    return templates.TemplateResponse(
        request=request, name="upload_detail.html",
        context={"upload": upload, "runs": runs},
    )
