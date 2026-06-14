from __future__ import annotations

import csv
import html
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from bs4 import BeautifulSoup

from games import ROOT, parse_game_selection

REQUEST_DELAY_SECONDS = 0.25

# A 404 from Box Office Mojo / Metacritic is retried up to MAX_404_ATTEMPTS times
# total; if every attempt still 404s, the run fails (PersistentNotFoundError) so
# the scheduled GitHub Action surfaces the broken page instead of silently
# recording it as a missing result.
MAX_404_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2.0

USER_AGENT = (
    "Mozilla/5.0 (compatible; big_pic_summer_movie_preview/0.1; local data script)"
)


@dataclass(frozen=True)
class FetchResult:
    value: int | None
    error: str


class PersistentNotFoundError(RuntimeError):
    """A page returned HTTP 404 on every attempt; the whole run should fail."""


def fetch_text(url: str) -> str:
    """Fetch ``url`` as text, retrying transient 404s.

    Box Office Mojo and Metacritic occasionally serve a spurious 404. Retry up to
    MAX_404_ATTEMPTS times; a 404 that survives every attempt raises
    PersistentNotFoundError so the run (and the scheduled GitHub Action) fails
    loudly rather than silently recording the page as missing. Non-404 errors are
    raised immediately for the caller to record as before.
    """
    for attempt in range(1, MAX_404_ATTEMPTS + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            if attempt == MAX_404_ATTEMPTS:
                raise PersistentNotFoundError(
                    f"{url} returned HTTP 404 after {MAX_404_ATTEMPTS} attempts"
                ) from error
            print(
                f"  HTTP 404 on {url} (attempt {attempt}/{MAX_404_ATTEMPTS}); "
                f"retrying in {RETRY_DELAY_SECONDS:g}s"
            )
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError("unreachable")  # pragma: no cover


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


def fetch_domestic_box_office(box_office_mojo_id: str) -> FetchResult:
    if not box_office_mojo_id:
        return FetchResult(None, "missing Box Office Mojo ID")

    url = f"https://www.boxofficemojo.com/title/{box_office_mojo_id}/"
    try:
        page = fetch_text(url)
        value = parse_domestic_box_office(page)
    except urllib.error.HTTPError as error:
        return FetchResult(None, f"HTTP {error.code}")
    except urllib.error.URLError as error:
        return FetchResult(None, str(error.reason))
    except TimeoutError:
        return FetchResult(None, "timeout")

    if value is None:
        return FetchResult(None, "domestic gross not found")
    return FetchResult(value, "")


def fetch_metacritic_score(metacritic_id: str) -> FetchResult:
    if not metacritic_id:
        return FetchResult(None, "missing Metacritic ID")

    url = f"https://www.metacritic.com/{metacritic_id.strip('/')}/"
    try:
        page = fetch_text(url)
        value = parse_metacritic_score(page)
    except urllib.error.HTTPError as error:
        return FetchResult(None, f"HTTP {error.code}")
    except urllib.error.URLError as error:
        return FetchResult(None, str(error.reason))
    except TimeoutError:
        return FetchResult(None, "timeout")

    if value is None:
        return FetchResult(None, "Metascore not found")
    return FetchResult(value, "")


def write_results(rows: list[dict[str, str | int | None]], output_csv: Path) -> None:
    fieldnames = [
        "title",
        "box_office",
        "metacritic",
        "box_office_error",
        "metacritic_error",
    ]
    with output_csv.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def refresh_game(movies_csv: Path, output_csv: Path) -> None:
    movies = pl.read_csv(movies_csv).to_dicts()
    rows = []

    for index, movie in enumerate(movies, start=1):
        title = str(movie["title"])
        box_office = fetch_domestic_box_office(
            str(movie.get("box_office_mojo_id") or "")
        )
        time.sleep(REQUEST_DELAY_SECONDS)
        metacritic = fetch_metacritic_score(str(movie.get("metacritic_id") or ""))
        time.sleep(REQUEST_DELAY_SECONDS)

        rows.append(
            {
                "title": title,
                "box_office": box_office.value,
                "metacritic": metacritic.value,
                "box_office_error": box_office.error,
                "metacritic_error": metacritic.error,
            }
        )
        print(f"{index:02d}/{len(movies)} {title}")

    write_results(rows, output_csv)
    box_count = sum(row["box_office"] is not None for row in rows)
    metacritic_count = sum(row["metacritic"] is not None for row in rows)
    print(f"Wrote {output_csv.relative_to(ROOT)} with {len(rows)} titles.")
    print(f"Found domestic box office for {box_count} titles.")
    print(f"Found Metacritic scores for {metacritic_count} titles.")


def main() -> None:
    games = parse_game_selection("Fetch box office and Metacritic results.")
    if not games:
        print("No games selected; nothing to refresh.")
        return
    for game in games:
        print(f"== {game.id} ==")
        refresh_game(game.movies_csv, game.results_csv)


if __name__ == "__main__":
    try:
        main()
    except PersistentNotFoundError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
