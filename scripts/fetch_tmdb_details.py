"""Fetch TMDB details for every movie in each live game's movies.csv.

Writes games/<id>/tmdb_details.json keyed by the title used in the prediction
CSVs. Only live games are refreshed; finished editions stay frozen. Reads the
API key from the TMDB_API_KEY environment variable or a git-ignored .env file at
the repo root (TMDB_API_KEY=...).
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import tmdbsimple as tmdb

from games import ROOT, live_games


def load_api_key() -> str:
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                name, _, value = line.partition("=")
                if name.strip() == "TMDB_API_KEY":
                    key = value.strip()
    if not key:
        sys.exit("TMDB_API_KEY is not set (export it or add it to .env)")
    return key


tmdb.API_KEY = load_api_key()
POSTER_BASE = "https://image.tmdb.org/t/p/w342"


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


def refresh_game(movies_csv: Path, out: Path) -> None:
    details: dict[str, dict] = {}
    with open(movies_csv, newline="") as f:
        for row in csv.DictReader(f):
            title = row["title"]
            if not row.get("tmdb_id"):
                print(f"skip {title}: no tmdb_id")
                continue
            try:
                details[title] = fetch(row["tmdb_id"])
            except Exception as exc:
                print(f"FAILED {title}: {exc}")
            else:
                print(f"ok {title}")
            time.sleep(0.25)

    out.write_text(json.dumps(details, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)} ({len(details)} movies)")


def main() -> None:
    games = live_games()
    if not games:
        print("No live games in the manifest; nothing to fetch.")
        return
    for game in games:
        print(f"== {game.id} ==")
        refresh_game(game.movies_csv, game.tmdb_json)


if __name__ == "__main__":
    main()
