"""Duplicate detection rules using DuckDB for cross-row self-joins.

Checks (all deterministic, no fuzzy matching):
  1. Shared PAN across different customer_ids
  2. Shared Aadhaar hash across different customer_ids (full Aadhaar never stored)
  3. Shared mobile number across different customer_ids
  4. Shared bank account number across different customer_ids
  5. Exact name+DOB match (normalised: upper, whitespace-stripped) across different customer_ids
"""

from __future__ import annotations

import hashlib

import duckdb
import polars as pl

from fcmr_core.config import settings
from fcmr_core.rules.registry import register


def _col_or_empty(df: pl.DataFrame, col: str) -> pl.Series:
    if col in df.columns:
        return df[col].fill_null("").cast(pl.Utf8)
    return pl.Series(col, [""] * len(df), dtype=pl.Utf8)


def _annotate(df: pl.DataFrame, rule_id: str, statuses: list[str], codes: list[str], descs: list[str]) -> pl.DataFrame:
    return df.with_columns([
        pl.Series(f"_exc_{rule_id}_status", statuses, dtype=pl.Utf8),
        pl.Series(f"_exc_{rule_id}_code", codes, dtype=pl.Utf8),
        pl.Series(f"_exc_{rule_id}_desc", descs, dtype=pl.Utf8),
    ])


def _hash_aadhaar(raw: str) -> str:
    """One-way hash of Aadhaar for dedup; salt prevents rainbow-table attacks."""
    val = (raw or "").strip().replace(" ", "").replace("-", "")
    if not val or len(val) != 12:
        return ""
    salted = settings.aadhaar_hash_salt + val
    return hashlib.sha256(salted.encode()).hexdigest()


def _find_duplicates_duckdb(df: pl.DataFrame, key_col: str, id_col: str) -> dict[str, list[str]]:
    """Return {key_value: [cust_id1, cust_id2, ...]} for keys appearing > once.

    Casts both columns to VARCHAR so the query works even when DuckDB auto-typed
    a column as INT64 (e.g. a purely numeric customer_id like UCID).
    """
    with duckdb.connect() as con:
        con.register("tbl", df.to_arrow())
        rows = con.execute(f"""
            SELECT a.{key_col}::VARCHAR, a.{id_col}::VARCHAR
            FROM tbl a
            WHERE a.{key_col} IS NOT NULL AND a.{key_col}::VARCHAR <> ''
              AND EXISTS (
                  SELECT 1 FROM tbl b
                  WHERE b.{key_col}::VARCHAR = a.{key_col}::VARCHAR
                    AND b.{id_col}::VARCHAR <> a.{id_col}::VARCHAR
                    AND b.{id_col} IS NOT NULL AND b.{id_col}::VARCHAR <> ''
              )
            ORDER BY a.{key_col}::VARCHAR
        """).fetchall()
    result: dict[str, list[str]] = {}
    for key, cid in rows:
        result.setdefault(str(key), []).append(str(cid))
    return result


@register("pan_duplicate", "Shared PAN across different customer IDs")
def rule_pan_duplicate(df: pl.DataFrame) -> pl.DataFrame:
    # Normalise PAN before dedup
    work = df.with_columns(
        pl.col("pan").fill_null("").str.strip_chars().str.to_uppercase().alias("_pan_norm")
        if "pan" in df.columns
        else pl.lit("").alias("_pan_norm")
    )
    cid_col = "customer_id" if "customer_id" in df.columns else "_row_num"
    dupes = _find_duplicates_duckdb(work.select(["_pan_norm", cid_col]), "_pan_norm", cid_col)

    cids = _col_or_empty(df, "customer_id")
    pans = work["_pan_norm"]
    statuses, codes, descs = [], [], []
    for cid, pan in zip(cids, pans):
        pan = (pan or "").strip()
        if pan and pan in dupes:
            others = [c for c in dupes[pan] if c != cid]
            statuses.append("ERROR"); codes.append("PAN_DUPLICATE")
            descs.append(f"PAN '{pan}' is shared with customer(s): {', '.join(others[:5])}")
        else:
            statuses.append("OK"); codes.append(""); descs.append("")
    return _annotate(df, "pan_duplicate", statuses, codes, descs)


@register("aadhaar_duplicate", "Shared Aadhaar (hash-based) across different customer IDs")
def rule_aadhaar_duplicate(df: pl.DataFrame) -> pl.DataFrame:
    aadh_series = _col_or_empty(df, "aadhaar")
    cids = _col_or_empty(df, "customer_id")

    # Build a work frame with hashed Aadhaar — never use raw value for dedup store
    hashes = [_hash_aadhaar(a) for a in aadh_series]
    work = pl.DataFrame({
        "customer_id": cids,
        "_aadhaar_hash": hashes,
    })
    dupes = _find_duplicates_duckdb(work, "_aadhaar_hash", "customer_id")

    statuses, codes, descs = [], [], []
    for cid, h in zip(cids, hashes):
        if h and h in dupes:
            others = [c for c in dupes[h] if c != cid]
            statuses.append("ERROR"); codes.append("AADHAAR_DUPLICATE")
            descs.append(f"Aadhaar (masked) is shared with customer(s): {', '.join(others[:5])}")
        else:
            statuses.append("OK"); codes.append(""); descs.append("")
    return _annotate(df, "aadhaar_duplicate", statuses, codes, descs)


@register("mobile_duplicate", "Shared mobile number across different customer IDs")
def rule_mobile_duplicate(df: pl.DataFrame) -> pl.DataFrame:
    mobiles = _col_or_empty(df, "mobile")
    cids = _col_or_empty(df, "customer_id")
    norm_mobiles = pl.Series([m.strip().replace(" ", "").replace("-", "") for m in mobiles])

    work = pl.DataFrame({"customer_id": cids, "_mobile_norm": norm_mobiles})
    dupes = _find_duplicates_duckdb(work, "_mobile_norm", "customer_id")

    statuses, codes, descs = [], [], []
    for cid, mob in zip(cids, norm_mobiles):
        if mob and mob in dupes:
            others = [c for c in dupes[mob] if c != cid]
            statuses.append("ERROR"); codes.append("MOBILE_DUPLICATE")
            descs.append(f"Mobile '{mob}' is shared with customer(s): {', '.join(others[:5])}")
        else:
            statuses.append("OK"); codes.append(""); descs.append("")
    return _annotate(df, "mobile_duplicate", statuses, codes, descs)


@register("bank_account_duplicate", "Shared bank account number across different customer IDs")
def rule_bank_account_duplicate(df: pl.DataFrame) -> pl.DataFrame:
    accts = _col_or_empty(df, "bank_account")
    cids = _col_or_empty(df, "customer_id")
    work = pl.DataFrame({"customer_id": cids, "_acct": accts})
    dupes = _find_duplicates_duckdb(work, "_acct", "customer_id")

    statuses, codes, descs = [], [], []
    for cid, acct in zip(cids, accts):
        acct = (acct or "").strip()
        if acct and acct in dupes:
            others = [c for c in dupes[acct] if c != cid]
            statuses.append("ERROR"); codes.append("BANK_ACCOUNT_DUPLICATE")
            descs.append(f"Bank account '{acct}' is shared with customer(s): {', '.join(others[:5])}")
        else:
            statuses.append("OK"); codes.append(""); descs.append("")
    return _annotate(df, "bank_account_duplicate", statuses, codes, descs)


@register("name_dob_duplicate", "Exact name+DOB duplicate (normalised) across different customer IDs")
def rule_name_dob_duplicate(df: pl.DataFrame) -> pl.DataFrame:
    names = _col_or_empty(df, "full_name")
    dobs = _col_or_empty(df, "dob")
    cids = _col_or_empty(df, "customer_id")

    keys = [
        (n.strip().upper() + "|" + d.strip()) if (n.strip() and d.strip()) else ""
        for n, d in zip(names, dobs)
    ]
    work = pl.DataFrame({"customer_id": cids, "_name_dob": keys})
    dupes = _find_duplicates_duckdb(work, "_name_dob", "customer_id")

    statuses, codes, descs = [], [], []
    for cid, key in zip(cids, keys):
        if key and key in dupes:
            others = [c for c in dupes[key] if c != cid]
            name, dob = key.split("|", 1)
            statuses.append("ERROR"); codes.append("NAME_DOB_DUPLICATE")
            descs.append(
                f"Name+DOB combination '{name} / {dob}' matches customer(s): {', '.join(others[:5])}"
            )
        else:
            statuses.append("OK"); codes.append(""); descs.append("")
    return _annotate(df, "name_dob_duplicate", statuses, codes, descs)
