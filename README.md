# big-pic-preview

Tracking Sean and Amanda's predictions from The Big Picture's Summer Movie Preview.

**Scoreboard site:** https://damonbayer.github.io/big-pic-preview/

## Data files

- `predictions.csv`: tidy host predictions transcribed from the source images.
- `movies.csv`: movie lookup IDs generated from Wikidata.
- `current_movie_results.csv`: latest fetched domestic box office and Metacritic scores.
- `tmdb_details.json`: movie metadata (release dates, posters, synopses) from TMDB.

## Refresh movie IDs

```sh
uv run scripts/fetch_movie_ids.py
```

The script reads `movies.csv`, queries Wikidata for TMDB,
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

The script reads `movies.csv`, fetches details from TMDB, and rewrites
`tmdb_details.json`. The API key comes from the `TMDB_API_KEY` environment
variable or a git-ignored `.env` file at the repo root.

## Scoreboard site

The site in `site/` is built with [Astro](https://astro.build). At build time
it reads `predictions.csv`, `current_movie_results.csv`,
and `tmdb_details.json`, and computes all points, totals, and differentials —
the scoring rules live in `site/src/data/scoreboard.ts`. A GitHub Actions workflow
(`.github/workflows/deploy.yml`) builds and deploys it to GitHub Pages on every
push to `main`. To update the published scores: run the fetch scripts above,
then commit and push — scoring happens in the site build, so there is no
derived scores file to regenerate.

```sh
cd site
npm install
npm run dev    # local dev server
npm run build  # production build
```
