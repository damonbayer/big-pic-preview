import Papa from 'papaparse';
import manifest from '../../../games/games.json';

// Per-game data lives in games/<id>/. Vite's import.meta.glob pulls every
// game's files in at build time; the game id is the directory segment.
const predictionFiles = import.meta.glob('../../../games/*/predictions.csv', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;
const resultFiles = import.meta.glob('../../../games/*/results.csv', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;
const movieFiles = import.meta.glob('../../../games/*/movies.csv', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;
const tmdbFiles = import.meta.glob('../../../games/*/tmdb_details.json', {
  import: 'default',
  eager: true,
}) as Record<string, Record<string, TmdbInfo>>;

function gameIdFromPath(path: string): string {
  return path.match(/\/games\/([^/]+)\//)![1];
}

// Re-key a globbed `path -> value` map by game id.
function byGameId<T>(files: Record<string, T>): Record<string, T> {
  return Object.fromEntries(Object.entries(files).map(([path, value]) => [gameIdFromPath(path), value]));
}

const predictionsById = byGameId(predictionFiles);
const resultsById = byGameId(resultFiles);
const moviesById = byGameId(movieFiles);
const tmdbById = byGameId(tmdbFiles);

// Parse a CSV into records keyed by its header row, so callers join on column
// names rather than fragile positional indices. PapaParse handles the quoting
// the Python fetch scripts emit — a title like "Sorry, Baby" stays one field
// instead of shifting every column and mis-mapping results to the wrong movie.
function parseCsvRecords(text: string): Record<string, string>[] {
  const parsed = Papa.parse<Record<string, string>>(text.trim(), {
    header: true,
    skipEmptyLines: true,
  });
  return parsed.data;
}

// --- types ---

export interface Episode {
  label: string;
  url: string;
}

// Scoring always pairs box office with Metacritic, but the method differs
// between editions. 2026 awards banded points (closer guess → more points, most
// points wins); 2025 is golf-style, charging a point per unit you miss by, and
// the lowest total wins. `objective` says which direction wins.
export interface ScoreBand {
  within: number;
  pts: number;
}

// Tiered tolerance bands; the first band whose tolerance covers the miss wins.
export interface BandsMethod {
  type: 'bands';
  bands: ScoreBand[];
}

// A flat penalty of `per` points for every `unit` of error (rounded per
// `round`, default nearest). `unit` is in the actual's native scale — dollars
// for box office, Metacritic points for Metacritic.
export interface LinearMethod {
  type: 'linear';
  per: number;
  unit: number;
  round?: 'nearest' | 'down' | 'none';
}

export type ScoreMethod = BandsMethod | LinearMethod;

export interface ScoringRules {
  objective: 'high' | 'low';
  boxOffice: ScoreMethod;
  metacritic: ScoreMethod;
}

export interface GameMeta {
  id: string;
  season: string;
  year: number;
  title: string;
  live: boolean;
  episodes: Episode[];
  scoring: ScoringRules;
}

export interface TmdbInfo {
  tmdb_id: number;
  tmdb_title: string | null;
  release_date: string | null;
  overview: string | null;
  tagline: string | null;
  runtime: number | null;
  genres: string[];
  poster_url: string | null;
  directors: string[];
  cast: string[];
}

export interface HostLine {
  boPred: number;
  metaPred: number;
  boPts: number;
  metaPts: number;
  totalPts: number;
}

export interface MovieLinks {
  tmdb: string | null;
  boxOffice: string | null;
  metacritic: string | null;
  letterboxd: string | null;
}

export interface MovieRow {
  title: string;
  releaseDate: string | null;
  tmdb: TmdbInfo | null;
  links: MovieLinks;
  actualBO: number | null;
  actualMeta: number | null;
  sean: HostLine;
  amanda: HostLine;
  diff: number;
  scored: boolean;
}

export interface Totals {
  sean: number;
  amanda: number;
  scoredCount: number;
  movieCount: number;
}

export interface GameData {
  meta: GameMeta;
  movies: MovieRow[];
  totals: Totals;
}

// A game omitting `scoring` in the manifest falls back to these (the 2026 bands).
export const DEFAULT_SCORING: ScoringRules = {
  objective: 'high',
  boxOffice: {
    type: 'bands',
    bands: [
      { within: 500_000, pts: 20 },
      { within: 5_000_000, pts: 10 },
      { within: 10_000_000, pts: 5 },
      { within: 50_000_000, pts: 1 },
    ],
  },
  metacritic: {
    type: 'bands',
    bands: [
      { within: 0, pts: 5 },
      { within: 5, pts: 1 },
    ],
  },
};

function pointsFor(method: ScoreMethod, pred: number, actual: number): number {
  const off = Math.abs(pred - actual);
  if (method.type === 'bands') {
    // Bands are checked nearest-first; the first tolerance that covers the miss wins.
    for (const band of method.bands) {
      if (off <= band.within) return band.pts;
    }
    return 0;
  }
  const units = off / method.unit;
  const quantized = method.round === 'down' ? Math.floor(units) : method.round === 'none' ? units : Math.round(units);
  return quantized * method.per;
}

const NO_LINKS: MovieLinks = {
  tmdb: null,
  boxOffice: null,
  metacritic: null,
  letterboxd: null,
};

interface Pred {
  boPred: number;
  metaPred: number;
}

function computeGame(meta: GameMeta): GameData {
  const predictionsCsv = predictionsById[meta.id] ?? '';
  const resultsCsv = resultsById[meta.id] ?? '';
  const moviesCsv = moviesById[meta.id] ?? '';
  const tmdb = tmdbById[meta.id] ?? {};

  // --- load actuals: title -> { box_office, metacritic } ---
  // columns: title,box_office,metacritic,box_office_error,metacritic_error
  const actuals = new Map<string, { bo: number | null; meta: number | null }>();
  for (const row of parseCsvRecords(resultsCsv)) {
    actuals.set(row.title, {
      bo: row.box_office === '' ? null : Number(row.box_office),
      meta: row.metacritic === '' ? null : Number(row.metacritic),
    });
  }

  // --- load source links from movies.csv IDs ---
  const links = new Map<string, MovieLinks>();
  for (const row of parseCsvRecords(moviesCsv)) {
    const { tmdb_id: tmdbId, box_office_mojo_id: bomId, metacritic_id: metaId, letterboxd_id: letterboxdId } = row;
    links.set(row.title, {
      tmdb: tmdbId ? `https://www.themoviedb.org/movie/${tmdbId}` : null,
      boxOffice: bomId ? `https://www.boxofficemojo.com/title/${bomId}/` : null,
      // metacritic_id sometimes carries stray slashes (e.g. "movie/power-ballad/").
      metacritic: metaId ? `https://www.metacritic.com/${metaId.replace(/^\/+|\/+$/g, '')}/` : null,
      letterboxd: letterboxdId ? `https://letterboxd.com/film/${letterboxdId.replace(/^\/+|\/+$/g, '')}/` : null,
    });
  }

  // --- load predictions: title+host -> guesses ---
  const byTitle = new Map<string, Partial<Record<'sean' | 'amanda', Pred>>>();
  for (const row of parseCsvRecords(predictionsCsv)) {
    const host = row.host;
    // Fail loudly on a transcription typo rather than silently dropping the row.
    if (host !== 'sean' && host !== 'amanda') {
      throw new Error(`${meta.id}: unexpected host "${host}" for "${row.title}" (expected "sean" or "amanda")`);
    }
    const entry = byTitle.get(row.title) ?? {};
    entry[host] = {
      boPred: Number(row.box_office_pred_millions) * 1_000_000,
      metaPred: Number(row.metacritic_pred),
    };
    byTitle.set(row.title, entry);
  }

  // --- score every guess ---
  const movies: MovieRow[] = [...byTitle.entries()].map(([title, hosts]) => {
    const info = tmdb[title] ?? null;
    const { bo = null, meta: metaActual = null } = actuals.get(title) ?? {};
    const score = (pred: Pred): HostLine => {
      const boPts = bo === null ? 0 : pointsFor(meta.scoring.boxOffice, pred.boPred, bo);
      const metaPts = metaActual === null ? 0 : pointsFor(meta.scoring.metacritic, pred.metaPred, metaActual);
      return { ...pred, boPts, metaPts, totalPts: boPts + metaPts };
    };
    if (!hosts.sean || !hosts.amanda) {
      throw new Error(`${meta.id}: "${title}" is missing a prediction for ${hosts.sean ? 'amanda' : 'sean'}`);
    }
    const sean = score(hosts.sean);
    const amanda = score(hosts.amanda);
    return {
      title,
      releaseDate: info?.release_date ?? null,
      tmdb: info,
      links: links.get(title) ?? NO_LINKS,
      actualBO: bo,
      actualMeta: metaActual,
      sean,
      amanda,
      diff: sean.totalPts - amanda.totalPts,
      // A film only counts once both results are in: a Metacritic score alone
      // (reviews land before release) isn't enough, and neither is box office
      // without a Metacritic score.
      scored: bo !== null && metaActual !== null,
    };
  });

  movies.sort((a, b) => {
    if (a.releaseDate === b.releaseDate) return a.title.localeCompare(b.title);
    if (a.releaseDate === null) return 1;
    if (b.releaseDate === null) return -1;
    return a.releaseDate < b.releaseDate ? -1 : 1;
  });

  const totals: Totals = {
    sean: movies.reduce((sum, m) => sum + (m.scored ? m.sean.totalPts : 0), 0),
    amanda: movies.reduce((sum, m) => sum + (m.scored ? m.amanda.totalPts : 0), 0),
    scoredCount: movies.filter((m) => m.scored).length,
    movieCount: movies.length,
  };

  return { meta, movies, totals };
}

// Manifest order is chronological (oldest first).
export const games: GameData[] = manifest.games.map((g) =>
  computeGame({
    id: g.id,
    season: g.season,
    year: g.year,
    title: g.title,
    live: g.live,
    episodes: g.episodes ?? [],
    // JSON widens the discriminant strings (e.g. "bands") to `string`, so the
    // structural shape can't satisfy the union directly — cast it.
    scoring: (g.scoring as ScoringRules | undefined) ?? DEFAULT_SCORING,
  }),
);

// The homepage shows the active edition: the most recent live game, or the most
// recent game overall if none is currently live.
export const currentGame: GameData = [...games].reverse().find((g) => g.meta.live) ?? games[games.length - 1];

export function getGame(id: string): GameData | undefined {
  return games.find((g) => g.meta.id === id);
}
