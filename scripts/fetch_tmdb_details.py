"""Fetch TMDB details for every movie in a game's movies.csv.

Writes games/<id>/tmdb_details.json keyed by each movie's canonical TMDB title.
Defaults to the live games; pass game ids or --all to refresh finished editions
too. Reads the API key from the TMDB_API_KEY environment variable or a git-ignored
.env file at the repo root (TMDB_API_KEY=...).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import polars as pl
import tmdbsimple as tmdb
from dotenv import load_dotenv
from schemas import (
    MOVIES_SCHEMA,
    PREDICTIONS_SCHEMA,
    RESULTS_SCHEMA,
    read_csv,
    write_csv,
)

from games import ROOT, parse_game_selection

REQUEST_DELAY_SECONDS = 0.25
POSTER_BASE = "https://image.tmdb.org/t/p/w342"


def load_api_key() -> str:
    # An exported env var wins; otherwise fall back to the git-ignored .env.
    load_dotenv(ROOT / ".env")
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        sys.exit("TMDB_API_KEY is not set (export it or add it to .env)")
    return key


def fetch(tmdb_id: str) -> dict:
    movie = tmdb.Movies(int(tmdb_id))
    info = movie.info(append_to_response="credits")
    directors = [
        c["name"]
        for c in info.get("credits", {}).get("crew", [])
        if c.get("job") == "Director"
    ]
    cast = [c["name"] for c in info.get("credits", {}).get("cast", [])[:4]]
    return {
        "tmdb_id": info["id"],
        "tmdb_title": info.get("title"),
        "release_date": info.get("release_date") or None,
        "overview": info.get("overview") or None,
        "tagline": info.get("tagline") or None,
        "runtime": info.get("runtime") or None,
        "genres": [g["name"] for g in info.get("genres", [])],
        "poster_url": POSTER_BASE + info["poster_path"]
        if info.get("poster_path")
        else None,
        "directors": directors,
        "cast": cast,
    }


def rename_titles(path: Path, schema: dict, renames: dict[str, str]) -> int:
    """Apply a title -> canonical-title map to a CSV with the given schema."""
    if not path.exists():
        return 0
    df = read_csv(path, schema)
    renamed = df.with_columns(pl.col("title").replace(renames))
    changed = int((df["title"] != renamed["title"]).sum())
    write_csv(renamed, path, schema)
    return changed


def refresh_game(
    movies_csv: Path, predictions_csv: Path, results_csv: Path, out: Path
) -> None:
    details: dict[str, dict] = {}
    renames: dict[str, str] = {}
    expected = 0
    failed = 0
    for row in read_csv(movies_csv, MOVIES_SCHEMA).to_dicts():
        title = row["title"]
        if not row.get("tmdb_id"):
            print(f"skip {title}: no tmdb_id")
            continue
        expected += 1
        try:
            info = fetch(row["tmdb_id"])
        except Exception as exc:
            print(f"FAILED {title}: {exc}")
            failed += 1
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        # The canonical name from TMDB becomes the title every file keys on.
        canonical = info.get("tmdb_title") or title
        details[canonical] = info
        renames[title] = canonical
        note = f" -> {canonical}" if canonical != title else ""
        print(f"ok {title}{note}")
        time.sleep(REQUEST_DELAY_SECONDS)

    # Don't overwrite a good file with nothing: if every movie that should have
    # fetched failed (bad key, TMDB outage), fail loudly instead of wiping data.
    if expected and failed == expected:
        raise RuntimeError(
            f"all {expected} TMDB fetches failed; leaving {out.relative_to(ROOT)} untouched"
        )

    out.write_text(json.dumps(details, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)} ({len(details)} movies)")

    movies_renamed = rename_titles(movies_csv, MOVIES_SCHEMA, renames)
    preds_renamed = rename_titles(predictions_csv, PREDICTIONS_SCHEMA, renames)
    results_renamed = rename_titles(results_csv, RESULTS_SCHEMA, renames)
    print(
        f"renamed {movies_renamed} title(s) in {movies_csv.name}, "
        f"{preds_renamed} row(s) in {predictions_csv.name}, "
        f"{results_renamed} row(s) in {results_csv.name}"
    )


def main() -> None:
    games = parse_game_selection("Fetch TMDB details and canonical titles.")
    if not games:
        print("No games selected; nothing to fetch.")
        return
    tmdb.API_KEY = load_api_key()
    for game in games:
        print(f"== {game.id} ==")
        refresh_game(
            game.movies_csv, game.predictions_csv, game.results_csv, game.tmdb_json
        )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
