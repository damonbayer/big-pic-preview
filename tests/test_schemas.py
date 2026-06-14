from __future__ import annotations

import polars as pl
import pytest
from schemas import (
    MOVIES_SCHEMA,
    PREDICTIONS_SCHEMA,
    RESULTS_SCHEMA,
    conform,
    read_csv,
    write_csv,
)

from games import ROOT

CSV_FILES = [
    (path, schema)
    for kind, schema in (
        ("movies", MOVIES_SCHEMA),
        ("predictions", PREDICTIONS_SCHEMA),
        ("results", RESULTS_SCHEMA),
    )
    for path in sorted((ROOT / "games").glob(f"*/{kind}.csv"))
]
CSV_IDS = [f"{p.parent.name}/{p.name}" for p, _ in CSV_FILES]


@pytest.mark.parametrize("path,schema", CSV_FILES, ids=CSV_IDS)
def test_roundtrip_is_byte_identical(path, schema, tmp_path):
    """Every committed CSV survives read -> write unchanged."""
    out = tmp_path / path.name
    write_csv(read_csv(path, schema), out, schema)
    assert out.read_text() == path.read_text()


def test_conform_orders_columns_and_drops_extras():
    df = pl.DataFrame(
        {
            "extra": [1],
            "metacritic_pred": [60],
            "title": ["A"],
            "host": ["x"],
            "box_office_pred_millions": [100],
        }
    )
    assert conform(df, PREDICTIONS_SCHEMA).columns == list(PREDICTIONS_SCHEMA)


def test_conform_fills_missing_columns_with_null():
    """A seed frame with only `title` still yields the full schema."""
    out = conform(pl.DataFrame({"title": ["A", "B"]}), MOVIES_SCHEMA)
    assert out.columns == list(MOVIES_SCHEMA)
    assert out["wikidata_id"].null_count() == 2


def test_conform_empty_frame_has_zero_rows():
    out = conform(pl.DataFrame([]), MOVIES_SCHEMA)
    assert out.shape == (0, len(MOVIES_SCHEMA))
    assert out.columns == list(MOVIES_SCHEMA)


def test_read_csv_applies_nullable_int_dtypes(tmp_path):
    path = tmp_path / "results.csv"
    path.write_text(
        "title,box_office,metacritic,box_office_error,metacritic_error\n"
        "A,100,60,,\n"
        "B,,,err,err\n"
    )
    df = read_csv(path, RESULTS_SCHEMA)
    assert df.schema["box_office"] == pl.Int64
    assert df["box_office"].to_list() == [100, None]


def test_write_csv_empty_rows_writes_header_only(tmp_path):
    path = tmp_path / "movies.csv"
    write_csv(pl.DataFrame([]), path, MOVIES_SCHEMA)
    assert path.read_text() == ",".join(MOVIES_SCHEMA) + "\n"
