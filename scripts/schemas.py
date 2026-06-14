"""Canonical schemas for the per-game CSVs.

Every edition under games/<id>/ carries the same three tables — movies.csv,
predictions.csv, and results.csv — each with a fixed set of columns. Defining
their shape once here makes this the single source of truth: the fetch scripts
read and write through ``read_csv`` / ``write_csv`` so column order and dtypes
stay consistent across the project.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

# External identifiers stay strings: leading characters and exact formatting
# matter (tt…, movie/…, Q…) and they're never used arithmetically.
MOVIES_SCHEMA: dict[str, pl.DataType] = {
    "title": pl.String(),
    "wikidata_id": pl.String(),
    "tmdb_id": pl.String(),
    "box_office_mojo_id": pl.String(),
    "metacritic_id": pl.String(),
    "letterboxd_id": pl.String(),
}

PREDICTIONS_SCHEMA: dict[str, pl.DataType] = {
    "title": pl.String(),
    "host": pl.String(),
    "box_office_pred_millions": pl.Int64(),
    "metacritic_pred": pl.Int64(),
}

# box_office / metacritic are blank until results.csv is filled in, so both are
# nullable; the *_error columns explain any blanks.
RESULTS_SCHEMA: dict[str, pl.DataType] = {
    "title": pl.String(),
    "box_office": pl.Int64(),
    "metacritic": pl.Int64(),
    "box_office_error": pl.String(),
    "metacritic_error": pl.String(),
}


def conform(frame: pl.DataFrame, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Return ``frame`` with exactly ``schema``'s columns, in order and dtype.

    Columns absent from ``frame`` are added as nulls; extras are dropped.
    """
    # A column-less frame (e.g. built from an empty row list) has no height for
    # a null literal to broadcast against, so return an empty, typed frame.
    if frame.width == 0:
        return pl.DataFrame(schema=schema)
    return frame.select(
        (pl.col(name) if name in frame.columns else pl.lit(None))
        .cast(dtype)
        .alias(name)
        for name, dtype in schema.items()
    )


def read_csv(path: Path, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Read a per-game CSV conformed to ``schema``."""
    return conform(pl.read_csv(path, schema_overrides=schema), schema)


def write_csv(frame: pl.DataFrame, path: Path, schema: dict[str, pl.DataType]) -> None:
    """Write ``frame`` to ``path`` conformed to ``schema``."""
    conform(frame, schema).write_csv(path)
