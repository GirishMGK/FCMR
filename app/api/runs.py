"""Run (analytics execution) endpoints."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from fcmr_core.catalog import store
from fcmr_core.config import settings
from fcmr_core.ingestion.pipeline import read_parquet
from fcmr_core.reporting.builder import build_exception_csvs
from fcmr_core.rules.registry import run_pipeline

router = APIRouter()
_templates_dir = Path(__file__).parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@router.post("/uploads/{upload_id}/run")
async def start_run(upload_id: str, background_tasks: BackgroundTasks):
    upload = store.get_upload(upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if upload["status"] != "ready":
        raise HTTPException(status_code=400, detail="Upload is not ready")

    parquet_path = Path(upload["parquet_path"])
    if not parquet_path.exists():
        raise HTTPException(status_code=500, detail="Parquet file not found on disk")

    run_id = store.create_run(upload_id)
    store.update_run(run_id, status="running", started_at=_now())

    # Run in a background thread so the browser gets an immediate response.
    # FastAPI BackgroundTasks run after the response is sent but in the same
    # process thread pool — sufficient for CPU-bound work without a job queue.
    background_tasks.add_task(_run_analytics, run_id, parquet_path)

    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


def _run_analytics(run_id: str, parquet_path: Path) -> None:
    """Execute the full analytics pipeline and update the catalog when done."""
    try:
        df = read_parquet(parquet_path).collect()
        annotated = run_pipeline(df)
        out_dir = settings.outputs_dir / run_id
        wide_path, long_path = build_exception_csvs(annotated, run_id, out_dir)
        store.update_run(
            run_id,
            status="completed",
            finished_at=_now(),
            wide_csv=str(wide_path),
            long_csv=str(long_path),
        )
    except Exception as exc:
        store.update_run(run_id, status="failed", finished_at=_now(), error=str(exc))


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    summary = None
    if run["status"] == "completed" and run["wide_csv"]:
        wide_path = Path(run["wide_csv"])
        if wide_path.exists():
            wide_df = pl.read_csv(
                str(wide_path),
                columns=["overall_status"],
                infer_schema_length=0,
            )
            counts = (
                wide_df["overall_status"]
                .value_counts()
                .sort("overall_status")
            )
            summary = {
                "total": len(wide_df),
                "status_counts": {r["overall_status"]: r["count"] for r in counts.iter_rows(named=True)},
                "top_codes": list(_top_exception_codes(run["long_csv"])),
            }

    return templates.TemplateResponse(
        request=request, name="run_detail.html",
        context={"run": run, "summary": summary},
    )


def _top_exception_codes(long_csv_path: str | None, n: int = 10):
    if not long_csv_path:
        return []
    p = Path(long_csv_path)
    if not p.exists():
        return []
    df = pl.read_csv(str(p))
    if df.is_empty() or "exception_code" not in df.columns:
        return []
    return (
        df["exception_code"]
        .value_counts()
        .sort("count", descending=True)
        .head(n)
        .iter_rows(named=True)
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
