"""Integration tests for the ingestion pipeline."""

import csv
from pathlib import Path

import polars as pl

from fcmr_core.ingestion.pipeline import ingest_csv, read_parquet


def _write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class TestIngestionPipeline:
    def test_basic_ingest(self, tmp_path):
        csv_path = tmp_path / "test.csv"
        _write_csv(
            [
                {
                    "customer_id": "C001",
                    "full_name": "Test User",
                    "pan": "ABCPF1234A",
                    "pincode": "110001",
                },
                {
                    "customer_id": "C002",
                    "full_name": "Another User",
                    "pan": "XYZPG5678B",
                    "pincode": "400001",
                },
            ],
            csv_path,
        )

        result = ingest_csv(csv_path, "customer_master", "test-ingest-01")
        assert result.total_rows == 2
        assert result.accepted_rows == 2
        assert result.rejected_rows == 0
        assert result.parquet_path.exists()

    def test_column_mapping_aliases(self, tmp_path):
        # Use messy real-world header names (aliases) instead of canonical ones
        csv_path = tmp_path / "messy.csv"
        _write_csv(
            [
                {
                    "cust_id": "C001",
                    "borrower_name": "Test User",
                    "pan_no": "ABCPF1234A",
                    "pin_code": "110001",
                },
            ],
            csv_path,
        )

        result = ingest_csv(csv_path, "customer_master", "test-ingest-02")
        assert result.accepted_rows == 1

        df = read_parquet(result.parquet_path).collect()
        # Canonical column names should appear after mapping
        assert "customer_id" in df.columns
        assert "full_name" in df.columns

    def test_unknown_report_type_passes_through(self, tmp_path):
        csv_path = tmp_path / "unknown.csv"
        _write_csv([{"col_a": "v1", "col_b": "v2"}], csv_path)

        result = ingest_csv(csv_path, "unknown_type", "test-ingest-03")
        assert result.accepted_rows == 1

    def test_missing_required_columns_reported(self, tmp_path):
        # customer_master requires customer_id; omit it
        csv_path = tmp_path / "missing.csv"
        _write_csv([{"full_name": "No ID Here", "pan": "ABCPF1234A"}], csv_path)

        result = ingest_csv(csv_path, "customer_master", "test-ingest-04")
        assert "customer_id" in result.missing_required

    def test_parquet_is_readable_by_polars(self, tmp_path):
        csv_path = tmp_path / "readable.csv"
        _write_csv(
            [{"customer_id": f"C{i:03d}", "full_name": f"User {i}"} for i in range(10)], csv_path
        )

        result = ingest_csv(csv_path, "customer_master", "test-ingest-05")
        lf = read_parquet(result.parquet_path)
        assert isinstance(lf, pl.LazyFrame)
        df = lf.collect()
        assert len(df) == 10
