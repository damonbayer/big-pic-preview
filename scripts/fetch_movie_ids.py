from __future__ import annotations

import csv
import io
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS_CSV = ROOT / "summer_movie_preview_predictions.csv"
OUTPUT_CSV = ROOT / "movies.csv"

TARGET_YEARS = {2025, 2026, 2027}

ALIASES = {
    "I Love Boosters": ["I Love Boosters!"],
    "Star Wars: The Mandalorian and Grogu": ["The Mandalorian and Grogu"],
    "The Breadwinner": ["The Breadwinner (2026 film)"],
    "Supergirl": ["Supergirl: Woman of Tomorrow"],
    "Moana": ["Moana (2026 film)"],
    "PAW Patrol: The Dino Movie": ["Paw Patrol: The Dino Movie"],
}

WIKIDATA_ITEM_OVERRIDES = {
    "The End of Oak Street": "Q124804916",
}


def sparql_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"@en'


def build_query(titles: list[str]) -> str:
    pairs = []
    manual_pairs = []
    for title in titles:
        matched_titles = [title, *ALIASES.get(title, [])]
        for matched_title in dict.fromkeys(matched_titles):
            pairs.append(f"({sparql_literal(title)} {sparql_literal(matched_title)})")
        if wikidata_item := WIKIDATA_ITEM_OVERRIDES.get(title):
            manual_pairs.append(
                f"({sparql_literal(title)} {sparql_literal(title)} wd:{wikidata_item})"
            )

    values = "\n    ".join(pairs)
    manual_union = ""
    if manual_pairs:
        manual_values = "\n    ".join(manual_pairs)
        manual_union = f"""
  UNION {{
    VALUES (?sourceTitle ?matched ?item) {{
    {manual_values}
    }}
  }}
"""
    return f"""
SELECT ?sourceTitle ?matched ?item ?itemLabel ?imdb ?tmdb ?metacritic ?date WHERE {{
  {{
    VALUES (?sourceTitle ?matched) {{
    {values}
    }}
    ?item wdt:P31/wdt:P279* wd:Q11424.
    {{ ?item rdfs:label ?matched. }} UNION {{ ?item skos:altLabel ?matched. }}
  }}
{manual_union}
  OPTIONAL {{ ?item wdt:P345 ?imdb }}
  OPTIONAL {{ ?item wdt:P4947 ?tmdb }}
  OPTIONAL {{ ?item wdt:P1712 ?metacritic }}
  OPTIONAL {{ ?item wdt:P577 ?date }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
""".strip()


def query_wikidata(titles: list[str]) -> pl.DataFrame:
    query = build_query(titles)
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
    fields = ["sourceTitle", "matched", "item", "itemLabel", "imdb", "tmdb", "metacritic", "date"]
    root = ET.fromstring(body)
    rows = []
    for result in root.findall(".//sparql:result", namespace):
        row = {field: "" for field in fields}
        for binding in result.findall("sparql:binding", namespace):
            name = binding.attrib["name"]
            child = list(binding)[0]
            row[name] = child.text or ""
        rows.append(row)
    return pl.DataFrame(rows, schema=empty_candidates().schema) if rows else empty_candidates()


def empty_candidates() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "sourceTitle": pl.String,
            "matched": pl.String,
            "item": pl.String,
            "itemLabel": pl.String,
            "imdb": pl.String,
            "tmdb": pl.String,
            "metacritic": pl.String,
            "date": pl.String,
        }
    )


def year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    match = re.match(r"^(\d{4})", value)
    return int(match.group(1)) if match else None


def candidate_score(row: dict[str, object]) -> tuple[int, int, int, int, str]:
    date_year = year_from_date(row.get("date"))
    has_target_year = date_year in TARGET_YEARS
    has_no_date = date_year is None
    has_any_id = any(row.get(column) for column in ("imdb", "tmdb", "metacritic"))
    matched_source = row.get("matched") == row.get("sourceTitle")

    # Avoid assigning older same-title films to the 2026 preview slate.
    if date_year is not None and date_year not in TARGET_YEARS:
        return (-1, 0, 0, 0, "")

    return (
        int(has_target_year),
        int(has_any_id),
        int(matched_source),
        int(has_no_date),
        str(row.get("item") or ""),
    )


def select_best_candidates(candidates: pl.DataFrame, titles: list[str]) -> dict[str, dict[str, str]]:
    if candidates.is_empty():
        return {}

    selected = {}
    for title in titles:
        title_rows = candidates.filter(pl.col("sourceTitle") == title).to_dicts()
        if not title_rows:
            continue
        best = max(title_rows, key=candidate_score)
        if candidate_score(best)[0] < 0:
            continue
        selected[title] = {
            "tmdb_id": str(best.get("tmdb") or ""),
            "box_office_mojo_id": str(best.get("imdb") or ""),
            "metacritic_id": str(best.get("metacritic") or ""),
        }
    return selected


def write_movies_csv(titles: list[str], selected: dict[str, dict[str, str]]) -> None:
    with OUTPUT_CSV.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["title", "tmdb_id", "box_office_mojo_id", "metacritic_id"],
        )
        writer.writeheader()
        for title in titles:
            ids = selected.get(title, {})
            writer.writerow(
                {
                    "title": title,
                    "tmdb_id": ids.get("tmdb_id", ""),
                    "box_office_mojo_id": ids.get("box_office_mojo_id", ""),
                    "metacritic_id": ids.get("metacritic_id", ""),
                }
            )


def main() -> None:
    predictions = pl.read_csv(PREDICTIONS_CSV)
    titles = predictions.select("title").unique(maintain_order=True).get_column("title").to_list()
    candidates = query_wikidata(titles)
    selected = select_best_candidates(candidates, titles)
    write_movies_csv(titles, selected)
    print(f"Wrote {OUTPUT_CSV.relative_to(ROOT)} with {len(titles)} titles.")
    print(f"Matched at least one ID for {len(selected)} titles.")


if __name__ == "__main__":
    main()
