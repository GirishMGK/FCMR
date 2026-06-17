"""Run (analytics execution) endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from fastapi import APIRouter, HTTPException, Request
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
async def start_run(upload_id: str):
    uploads = store.list_uploads()
    upload = next((u for u in uploads if u["upload_id"] == upload_id), None)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    if upload["status"] != "ready":
        raise HTTPException(status_code=400, detail="Upload is not ready (ingestion may have failed)")

    parquet_path = Path(upload["parquet_path"])
    if not parquet_path.exists():
        raise HTTPException(status_code=500, detail="Parquet file not found on disk")

    run_id = store.create_run(upload_id)
    store.update_run(run_id, status="running", started_at=_now())

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
        raise HTTPException(status_code=500, detail=f"Run failed: {exc}") from exc

    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    summary = None
    if run["status"] == "completed" and run["wide_csv"]:
        wide_path = Path(run["wide_csv"])
        if wide_path.exists():
            wide_df = pl.read_csv(str(wide_path))
            counts = (
                wide_df["overall_status"]
                .value_counts()
                .sort("overall_status")
            )
            summary = {
                "total": len(wide_df),
                "status_counts": {r["overall_status"]: r["count"] for r in counts.iter_rows(named=True)},
                "top_codes": _top_exception_codes(run["long_csv"]),
            }

    return templates.TemplateResponse(
        request=request, name="run_detail.html",
        context={"run": run, "summary": summary},
    )


def _top_exception_codes(long_csv_path: str | None, n: int = 10) -> list[dict]:
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
