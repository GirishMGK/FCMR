"""Exception CSV builders.

Two outputs per run:

  wide CSV  — one row per input record; appends:
                overall_status, exception_count, exception_codes, exception_descriptions
                (codes and descriptions are pipe-joined for multi-exception rows)

  long CSV  — one row per (record, exception); columns:
                _row_num, customer_id, rule_id, status, exception_code, exception_description
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl


_EXC_STATUS_RE = re.compile(r"^_exc_(.+)_status$")

# Severity order for overall_status rollup
_SEVERITY = {"OK": 0, "WARN": 1, "ERROR": 2}


def build_exception_csvs(
    annotated: pl.DataFrame,
    run_id: str,
    outputs_dir: Path,
) -> tuple[Path, Path]:
    """Write wide and long exception CSVs.  Returns (wide_path, long_path)."""
    outputs_dir.mkdir(parents=True, exist_ok=True)
    wide_path = outputs_dir / f"{run_id}_wide.csv"
    long_path = outputs_dir / f"{run_id}_long.csv"

    # Collect rule IDs from the annotated frame
    rule_ids = [
        _EXC_STATUS_RE.match(c).group(1)  # type: ignore[union-attr]
        for c in annotated.columns
        if _EXC_STATUS_RE.match(c)
    ]

    # ---- Wide CSV --------------------------------------------------------
    overall_statuses: list[str] = []
    exc_counts: list[int] = []
    exc_codes_list: list[str] = []
    exc_descs_list: list[str] = []

    for i in range(len(annotated)):
        worst = "OK"
        codes: list[str] = []
        descs: list[str] = []
        for rid in rule_ids:
            status = annotated[f"_exc_{rid}_status"][i] or "OK"
            code = annotated[f"_exc_{rid}_code"][i] or ""
            desc = annotated[f"_exc_{rid}_desc"][i] or ""
            if _SEVERITY.get(status, 0) > _SEVERITY.get(worst, 0):
                worst = status
            if code:
                codes.append(code)
            if desc:
                descs.append(desc)
        overall_statuses.append(worst)
        exc_counts.append(len(codes))
        exc_codes_list.append("|".join(codes))
        exc_descs_list.append("|".join(descs))

    # Drop internal annotation columns before writing
    exc_cols = [c for c in annotated.columns if c.startswith("_exc_")]
    base_df = annotated.drop(exc_cols)

    wide_df = base_df.with_columns([
        pl.Series("overall_status", overall_statuses, dtype=pl.Utf8),
        pl.Series("exception_count", exc_counts, dtype=pl.Int32),
        pl.Series("exception_codes", exc_codes_list, dtype=pl.Utf8),
        pl.Series("exception_descriptions", exc_descs_list, dtype=pl.Utf8),
    ])
    wide_df.write_csv(str(wide_path))

    # ---- Long CSV --------------------------------------------------------
    long_rows: list[dict] = []
    row_num_col = annotated["_row_num"] if "_row_num" in annotated.columns else pl.Series([None] * len(annotated))
    cid_col = annotated["customer_id"] if "customer_id" in annotated.columns else pl.Series([""] * len(annotated))

    for i in range(len(annotated)):
        for rid in rule_ids:
            status = annotated[f"_exc_{rid}_status"][i] or "OK"
            code = annotated[f"_exc_{rid}_code"][i] or ""
            desc = annotated[f"_exc_{rid}_desc"][i] or ""
            if status != "OK":
                long_rows.append({
                    "_row_num": row_num_col[i],
                    "customer_id": cid_col[i],
                    "rule_id": rid,
                    "status": status,
                    "exception_code": code,
                    "exception_description": desc,
                })

    long_df = pl.DataFrame(long_rows) if long_rows else pl.DataFrame({
        "_row_num": pl.Series([], dtype=pl.Int64),
        "customer_id": pl.Series([], dtype=pl.Utf8),
        "rule_id": pl.Series([], dtype=pl.Utf8),
        "status": pl.Series([], dtype=pl.Utf8),
        "exception_code": pl.Series([], dtype=pl.Utf8),
        "exception_description": pl.Series([], dtype=pl.Utf8),
    })
    long_df.write_csv(str(long_path))

    return wide_path, long_path
