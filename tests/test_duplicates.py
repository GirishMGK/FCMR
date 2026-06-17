"""Unit tests for duplicate detection rules."""

import polars as pl
import pytest

from fcmr_core.rules.duplicates import (
    rule_pan_duplicate,
    rule_mobile_duplicate,
    rule_bank_account_duplicate,
    rule_name_dob_duplicate,
)


def _status(df: pl.DataFrame, rule_id: str, row: int = 0) -> str:
    return df[f"_exc_{rule_id}_status"][row]


def _code(df: pl.DataFrame, rule_id: str, row: int = 0) -> str:
    return df[f"_exc_{rule_id}_code"][row]


class TestPanDuplicate:
    def _make_df(self, pans: list[str], cids: list[str]) -> pl.DataFrame:
        return pl.DataFrame({"customer_id": cids, "pan": pans})

    def test_no_duplicate(self):
        df = rule_pan_duplicate(self._make_df(["ABCPF1234A", "XYZPG5678B"], ["C001", "C002"]))
        assert _status(df, "pan_duplicate", 0) == "OK"
        assert _status(df, "pan_duplicate", 1) == "OK"

    def test_shared_pan_flagged(self):
        df = rule_pan_duplicate(self._make_df(["ABCPF1234A", "ABCPF1234A"], ["C001", "C002"]))
        assert _code(df, "pan_duplicate", 0) == "PAN_DUPLICATE"
        assert _code(df, "pan_duplicate", 1) == "PAN_DUPLICATE"

    def test_three_way_duplicate(self):
        df = rule_pan_duplicate(self._make_df(
            ["ABCPF1234A", "ABCPF1234A", "ABCPF1234A"],
            ["C001", "C002", "C003"],
        ))
        for i in range(3):
            assert _code(df, "pan_duplicate", i) == "PAN_DUPLICATE"

    def test_empty_pan_not_flagged(self):
        df = rule_pan_duplicate(self._make_df(["", ""], ["C001", "C002"]))
        assert _status(df, "pan_duplicate", 0) == "OK"


class TestMobileDuplicate:
    def _make_df(self, mobiles: list[str], cids: list[str]) -> pl.DataFrame:
        return pl.DataFrame({"customer_id": cids, "mobile": mobiles})

    def test_no_duplicate(self):
        df = rule_mobile_duplicate(self._make_df(["9876543210", "8001234567"], ["C001", "C002"]))
        assert _status(df, "mobile_duplicate", 0) == "OK"

    def test_shared_mobile_flagged(self):
        df = rule_mobile_duplicate(self._make_df(["9876543210", "9876543210"], ["C001", "C002"]))
        assert _code(df, "mobile_duplicate", 0) == "MOBILE_DUPLICATE"
        assert _code(df, "mobile_duplicate", 1) == "MOBILE_DUPLICATE"


class TestBankAccountDuplicate:
    def _make_df(self, accounts: list[str], cids: list[str]) -> pl.DataFrame:
        return pl.DataFrame({"customer_id": cids, "bank_account": accounts})

    def test_shared_account_flagged(self):
        df = rule_bank_account_duplicate(
            self._make_df(["123456789012", "123456789012"], ["C001", "C002"])
        )
        assert _code(df, "bank_account_duplicate", 0) == "BANK_ACCOUNT_DUPLICATE"

    def test_unique_accounts_ok(self):
        df = rule_bank_account_duplicate(
            self._make_df(["111111111111", "222222222222"], ["C001", "C002"])
        )
        assert _status(df, "bank_account_duplicate", 0) == "OK"


class TestNameDobDuplicate:
    def _make_df(self, names: list[str], dobs: list[str], cids: list[str]) -> pl.DataFrame:
        return pl.DataFrame({"customer_id": cids, "full_name": names, "dob": dobs})

    def test_exact_name_dob_match(self):
        df = rule_name_dob_duplicate(
            self._make_df(
                ["Rahul Sharma", "Rahul Sharma"],
                ["1990-01-01", "1990-01-01"],
                ["C001", "C002"],
            )
        )
        assert _code(df, "name_dob_duplicate", 0) == "NAME_DOB_DUPLICATE"

    def test_same_name_different_dob_is_ok(self):
        df = rule_name_dob_duplicate(
            self._make_df(
                ["Rahul Sharma", "Rahul Sharma"],
                ["1990-01-01", "1991-02-02"],
                ["C001", "C002"],
            )
        )
        assert _status(df, "name_dob_duplicate", 0) == "OK"

    def test_case_insensitive_match(self):
        df = rule_name_dob_duplicate(
            self._make_df(
                ["rahul sharma", "RAHUL SHARMA"],
                ["1990-01-01", "1990-01-01"],
                ["C001", "C002"],
            )
        )
        assert _code(df, "name_dob_duplicate", 0) == "NAME_DOB_DUPLICATE"
