# big_pic_summer_movie_preview

Tracking Sean and Amanda's predictions from The Big Picture's Summer Movie Preview.

**Scoreboard site:** https://damonbayer.github.io/big_pic_summer_movie_preview/

## Data files

- `summer_movie_preview_predictions.csv`: tidy host predictions transcribed from the source images.
- `movies.csv`: movie lookup IDs generated from Wikidata.
- `current_movie_results.csv`: latest fetched domestic box office and Metacritic scores.
- `scores.csv`: predictions joined with actuals plus per-host points (regenerate with `uv run scripts/score.py`).
- `tmdb_details.json`: movie metadata (release dates, posters, synopses) from TMDB.

## Refresh movie IDs

```sh
uv run scripts/fetch_movie_ids.py
```

The script reads `summer_movie_preview_predictions.csv`, queries Wikidata for TMDB,
IMDb/Box Office Mojo, and Metacritic IDs, and rewrites `movies.csv`.

## Refresh current results

```sh
uv run scripts/fetch_current_results.py
```

The script reads `movies.csv`, fetches Box Office Mojo title pages and Metacritic
movie pages, and rewrites `current_movie_results.csv`. Empty result fields are
paired with an error column explaining whether the source page, score, or ID was
missing.

## Refresh TMDB details

```sh
uv run scripts/fetch_tmdb_details.py
```

The script reads `movies.csv`, fetches details from TMDB (set `TMDB_API_KEY` to
override the default key), and rewrites `tmdb_details.json`.

## Scoreboard site

The site in `site/` is built with [Astro](https://astro.build) and reads
`scores.csv` and `tmdb_details.json` at build time. A GitHub Actions workflow
(`.github/workflows/deploy.yml`) builds and deploys it to GitHub Pages on every
push to `main`. To update the published scores: re-run the fetch scripts and
`uv run scripts/score.py`, then commit and push.

```sh
cd site
npm install
npm run dev    # local dev server
npm run build  # production build
```
