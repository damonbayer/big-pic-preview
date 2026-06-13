from __future__ import annotations

import csv
import html
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MOVIES_CSV = ROOT / "movies.csv"
OUTPUT_CSV = ROOT / "current_movie_results.csv"

REQUEST_DELAY_SECONDS = 0.25
USER_AGENT = (
    "Mozilla/5.0 (compatible; big_pic_summer_movie_preview/0.1; local data script)"
)


@dataclass(frozen=True)
class FetchResult:
    value: int | None
    error: str


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8", errors="replace")


def money_to_int(value: str) -> int:
    return int(value.replace("$", "").replace(",", ""))


def parse_domestic_box_office(page: str) -> int | None:
    soup = BeautifulSoup(page, "html.parser")
    for label in soup.find_all(string=re.compile(r"Domestic\s*\(")):
        section = label.find_parent("div")
        if not section:
            continue
        money = section.select_one(".money")
        if money:
            return money_to_int(money.get_text(strip=True))

    # Fallback for minor markup changes: use the first money value after the Domestic label.
    normalized = html.unescape(page)
    domestic_index = normalized.find("Domestic (")
    if domestic_index == -1:
        return None
    nearby = normalized[domestic_index : domestic_index + 2_000]
    match = re.search(r"\$[\d,]+", nearby)
    return money_to_int(match.group(0)) if match else None


def parse_metacritic_score(page: str) -> int | None:
    normalized = html.unescape(page)
    match = re.search(
        r'"name"\s*:\s*"Metascore".{0,1200}?"ratingValue"\s*:\s*"?(\d{1,3})"?',
        normalized,
        flags=re.DOTALL,
    )
    if match:
        return int(match.group(1))

    # Fallback for rendered score snippets.
    match = re.search(
        r"Metascore.{0,300}?c-siteReviewScore[^>]*>\s*<span[^>]*>(\d{1,3})</span>",
        normalized,
        flags=re.DOTALL,
    )
    return int(match.group(1)) if match else None


def fetch_domestic_box_office(box_office_mojo_id: str) -> tuple[str, FetchResult]:
    if not box_office_mojo_id:
        return "", FetchResult(None, "missing Box Office Mojo ID")

    url = f"https://www.boxofficemojo.com/title/{box_office_mojo_id}/"
    try:
        page = fetch_text(url)
        value = parse_domestic_box_office(page)
    except urllib.error.HTTPError as error:
        return url, FetchResult(None, f"HTTP {error.code}")
    except urllib.error.URLError as error:
        return url, FetchResult(None, str(error.reason))
    except TimeoutError:
        return url, FetchResult(None, "timeout")

    if value is None:
        return url, FetchResult(None, "domestic gross not found")
    return url, FetchResult(value, "")


def fetch_metacritic_score(metacritic_id: str) -> tuple[str, FetchResult]:
    if not metacritic_id:
        return "", FetchResult(None, "missing Metacritic ID")

    url = f"https://www.metacritic.com/{metacritic_id.strip('/')}/"
    try:
        page = fetch_text(url)
        value = parse_metacritic_score(page)
    except urllib.error.HTTPError as error:
        return url, FetchResult(None, f"HTTP {error.code}")
    except urllib.error.URLError as error:
        return url, FetchResult(None, str(error.reason))
    except TimeoutError:
        return url, FetchResult(None, "timeout")

    if value is None:
        return url, FetchResult(None, "Metascore not found")
    return url, FetchResult(value, "")


def write_results(rows: list[dict[str, str | int | None]]) -> None:
    fieldnames = [
        "title",
        "box_office",
        "metacritic",
        "box_office_url",
        "metacritic_url",
        "box_office_error",
        "metacritic_error",
        "fetched_at",
    ]
    with OUTPUT_CSV.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    movies = pl.read_csv(MOVIES_CSV).to_dicts()
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    rows = []

    for index, movie in enumerate(movies, start=1):
        title = str(movie["title"])
        box_url, box_office = fetch_domestic_box_office(
            str(movie.get("box_office_mojo_id") or "")
        )
        time.sleep(REQUEST_DELAY_SECONDS)
        metacritic_url, metacritic = fetch_metacritic_score(
            str(movie.get("metacritic_id") or "")
        )
        time.sleep(REQUEST_DELAY_SECONDS)

        rows.append(
            {
                "title": title,
                "box_office": box_office.value,
                "metacritic": metacritic.value,
                "box_office_url": box_url,
                "metacritic_url": metacritic_url,
                "box_office_error": box_office.error,
                "metacritic_error": metacritic.error,
                "fetched_at": fetched_at,
            }
        )
        print(f"{index:02d}/{len(movies)} {title}")

    write_results(rows)
    box_count = sum(row["box_office"] is not None for row in rows)
    metacritic_count = sum(row["metacritic"] is not None for row in rows)
    print(f"Wrote {OUTPUT_CSV.relative_to(ROOT)} with {len(rows)} titles.")
    print(f"Found domestic box office for {box_count} titles.")
    print(f"Found Metacritic scores for {metacritic_count} titles.")


if __name__ == "__main__":
    main()
