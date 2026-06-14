from __future__ import annotations

import csv
import io
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl

from games import live_games

FIELDNAMES = [
    "title",
    "wikidata_id",
    "tmdb_id",
    "box_office_mojo_id",
    "metacritic_id",
    "letterboxd_id",
]

# Maps the movies.csv ID column to the SPARQL variable that carries its value.
ID_COLUMNS = {
    "tmdb_id": "tmdb",
    "box_office_mojo_id": "imdb",
    "metacritic_id": "metacritic",
    "letterboxd_id": "letterboxd",
}

QID_PATTERN = re.compile(r"^Q\d+$")


def lookup_term(row: dict[str, str]) -> str:
    """The Wikidata item (Q-id) to look up, falling back to the title label."""
    return (row.get("wikidata_id") or "").strip() or row["title"]


def missing_columns(row: dict[str, str]) -> list[str]:
    return [column for column in ID_COLUMNS if not (row.get(column) or "").strip()]


def sparql_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"@en'


def build_query(term_by_title: dict[str, str]) -> str:
    label_pairs = []
    item_pairs = []
    for title, name in term_by_title.items():
        if QID_PATTERN.match(name):
            item_pairs.append(f"({sparql_literal(title)} wd:{name})")
        else:
            label_pairs.append(f"({sparql_literal(title)} {sparql_literal(name)})")

    blocks = []
    if label_pairs:
        values = "\n    ".join(label_pairs)
        blocks.append(
            f"""  {{
    VALUES (?sourceTitle ?label) {{
    {values}
    }}
    ?item wdt:P31/wdt:P279* wd:Q11424.
    {{ ?item rdfs:label ?label. }} UNION {{ ?item skos:altLabel ?label. }}
  }}"""
        )
    if item_pairs:
        values = "\n    ".join(item_pairs)
        blocks.append(
            f"""  {{
    VALUES (?sourceTitle ?item) {{
    {values}
    }}
  }}"""
        )

    union = "\n  UNION\n".join(blocks)
    return f"""
SELECT ?sourceTitle ?item ?itemLabel ?imdb ?tmdb ?metacritic ?letterboxd ?date WHERE {{
{union}
  OPTIONAL {{ ?item wdt:P345 ?imdb }}
  OPTIONAL {{ ?item wdt:P4947 ?tmdb }}
  OPTIONAL {{ ?item wdt:P1712 ?metacritic }}
  OPTIONAL {{ ?item wdt:P6127 ?letterboxd }}
  OPTIONAL {{ ?item wdt:P577 ?date }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
""".strip()


def query_wikidata(term_by_title: dict[str, str]) -> pl.DataFrame:
    if not term_by_title:
        return empty_candidates()

    query = build_query(term_by_title)
    data = urllib.parse.urlencode({"query": query, "format": "csv"}).encode()
    request = urllib.request.Request(
        "https://query.wikidata.org/sparql?format=csv",
        data=data,
        headers={
            "Accept": "text/csv",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "big_pic_summer_movie_preview/0.1 (local reproducible data script)",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()

    body = body.strip()
    if not body:
        return empty_candidates()
    if body.startswith(b"<?xml"):
        return parse_sparql_xml(body)
    return pl.read_csv(io.BytesIO(body))


def parse_sparql_xml(body: bytes) -> pl.DataFrame:
    namespace = {"sparql": "http://www.w3.org/2005/sparql-results#"}
    fields = [
        "sourceTitle",
        "item",
        "itemLabel",
        "imdb",
        "tmdb",
        "metacritic",
        "letterboxd",
        "date",
    ]
    root = ET.fromstring(body)
    rows = []
    for result in root.findall(".//sparql:result", namespace):
        row = {field: "" for field in fields}
        for binding in result.findall("sparql:binding", namespace):
            name = binding.attrib["name"]
            child = next(iter(binding))
            row[name] = child.text or ""
        rows.append(row)
    return (
        pl.DataFrame(rows, schema=empty_candidates().schema)
        if rows
        else empty_candidates()
    )


def empty_candidates() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "sourceTitle": pl.String,
            "item": pl.String,
            "itemLabel": pl.String,
            "imdb": pl.String,
            "tmdb": pl.String,
            "metacritic": pl.String,
            "letterboxd": pl.String,
            "date": pl.String,
        }
    )


def year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"^(\d{4})", value)
    return int(match.group(1)) if match else None


def candidate_score(
    row: dict[str, object], target_years: set[int]
) -> tuple[int, int, int, str]:
    date_year = year_from_date(row.get("date"))
    has_target_year = date_year in target_years
    has_no_date = date_year is None
    has_any_id = any(
        row.get(column) for column in ("imdb", "tmdb", "metacritic", "letterboxd")
    )

    # Avoid assigning older same-title films to this edition's preview slate.
    if date_year is not None and date_year not in target_years:
        return (-1, 0, 0, "")

    return (
        int(has_target_year),
        int(has_any_id),
        int(has_no_date),
        str(row.get("item") or ""),
    )


def select_best_candidates(
    candidates: pl.DataFrame, titles: list[str], target_years: set[int]
) -> dict[str, dict[str, str]]:
    if candidates.is_empty():
        return {}

    selected = {}
    for title in titles:
        title_rows = candidates.filter(pl.col("sourceTitle") == title).to_dicts()
        if not title_rows:
            continue
        best = max(title_rows, key=lambda row: candidate_score(row, target_years))
        if candidate_score(best, target_years)[0] < 0:
            continue
        selected[title] = {
            "tmdb_id": str(best.get("tmdb") or ""),
            "box_office_mojo_id": str(best.get("imdb") or ""),
            "metacritic_id": str(best.get("metacritic") or ""),
            "letterboxd_id": str(best.get("letterboxd") or ""),
        }
    return selected


def read_movies(movies_csv: Path) -> list[dict[str, str]]:
    with movies_csv.open(newline="") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        row.setdefault("wikidata_id", "")
    return rows


def write_movies(rows: list[dict[str, str]], movies_csv: Path) -> None:
    with movies_csv.open("w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=FIELDNAMES, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def fill_game(movies_csv: Path, target_years: set[int]) -> None:
    rows = read_movies(movies_csv)

    term_by_title = {
        row["title"]: lookup_term(row) for row in rows if missing_columns(row)
    }
    if not term_by_title:
        print("All movies already have every link; nothing to fetch.")
        return

    candidates = query_wikidata(term_by_title)
    selected = select_best_candidates(candidates, list(term_by_title), target_years)

    filled = 0
    for row in rows:
        ids = selected.get(row["title"])
        if not ids:
            continue
        for column in missing_columns(row):
            value = ids.get(column, "")
            if value:
                row[column] = value
                filled += 1

    write_movies(rows, movies_csv)
    print(
        f"Checked {len(term_by_title)} movies with missing links; filled {filled} link(s)."
    )


def main() -> None:
    games = live_games()
    if not games:
        print("No live games in the manifest; nothing to fetch.")
        return
    for game in games:
        # Films in an edition's slate cluster around its year, but some slip a
        # year. Allow a ±1 window to disambiguate same-title Wikidata items.
        target_years = {game.year - 1, game.year, game.year + 1}
        print(f"== {game.id} ==")
        fill_game(game.movies_csv, target_years)


if __name__ == "__main__":
    main()
