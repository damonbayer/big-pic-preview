# big-pic-preview

Tracking Sean and Amanda's predictions from The Big Picture's Movie Preview
boom-or-bust game, across editions.

**Scoreboard site:** https://bigpicpreview.com

## Games

Each edition of the game (e.g. Summer 2026) is a "game" with its own data, living
in `games/<id>/`. The list of games — in chronological order, each flagged `live`
or not — is the manifest at `games/games.json`. It is the single source of truth
read by both the Python scripts and the site.

```
games/
  games.json                 # manifest: id, season, year, title, live, episodes, scoring
  2026-summer/
    predictions.csv          # tidy host predictions transcribed from the source images
    movies.csv               # movie lookup IDs generated from Wikidata
    results.csv              # latest fetched domestic box office and Metacritic scores
    tmdb_details.json        # movie metadata (release dates, posters, synopses) from TMDB
  2025-summer/
    ...
```

### Adding a game

1. Create `games/<id>/` with `predictions.csv`, `movies.csv` (the
   `title` column is enough to start), an empty `results.csv`
   header row, and `tmdb_details.json` (`{}`).
2. Add an entry to `games/games.json` in chronological order. Set `live: true`
   while the game is running. Optionally override `scoring` (it always pairs box
   office with Metacritic, but the thresholds can change); omitting it uses the
   defaults in `site/src/data/games.ts`.
3. Run the fetch scripts (they only touch live games) to fill in IDs, results,
   and TMDB details.

`live` controls behavior: the update scripts only refresh live games, and the
site shows "in the lead" / "updated daily" for live games versus "winner" /
"all movies scored" for finished ones.

## Refresh movie IDs

```sh
uv run scripts/fetch_movie_ids.py
```

For each live game, reads `games/<id>/movies.csv`, queries Wikidata for TMDB,
IMDb/Box Office Mojo, and Metacritic IDs, and rewrites that file.

## Refresh current results

```sh
uv run scripts/fetch_current_results.py
```

For each live game, reads `games/<id>/movies.csv`, fetches Box Office Mojo title
pages and Metacritic movie pages, and rewrites `games/<id>/results.csv`.
Empty result fields are paired with an error column explaining whether the source
page, score, or ID was missing.

## Refresh TMDB details

```sh
uv run scripts/fetch_tmdb_details.py
```

For each live game, reads `games/<id>/movies.csv`, fetches details from TMDB, and
rewrites `games/<id>/tmdb_details.json`. The API key comes from the `TMDB_API_KEY`
environment variable or a git-ignored `.env` file at the repo root.

## Scoreboard site

The site in `site/` is built with [Astro](https://astro.build). At build time it
reads the manifest and every game's data files, and computes all points, totals,
and differentials — the scoring rules live in `site/src/data/games.ts`. The
homepage renders the current (live) edition; each game also has its own page at
`/games/<id>/`. A GitHub Actions workflow (`.github/workflows/deploy.yml`) builds
and deploys it to GitHub Pages on every push to `main`. To update the published
scores: run the fetch scripts above, then commit and push — scoring happens in
the site build, so there is no derived scores file to regenerate.

```sh
cd site
npm install
npm run dev    # local dev server
npm run build  # production build
```
