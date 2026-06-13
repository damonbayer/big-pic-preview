import predictionsCsv from '../../../predictions.csv?raw';
import resultsCsv from '../../../current_movie_results.csv?raw';
import moviesCsv from '../../../movies.csv?raw';
import tmdbDetails from '../../../tmdb_details.json';

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

const tmdb = tmdbDetails as Record<string, TmdbInfo>;

// --- scoring rules ---

function boxOfficePts(pred: number, actual: number): number {
  const off = Math.abs(pred - actual);
  if (off <= 500_000) return 20;
  if (off <= 5_000_000) return 10;
  if (off <= 10_000_000) return 5;
  if (off <= 50_000_000) return 1;
  return 0;
}

function metacriticPts(pred: number, actual: number): number {
  const off = Math.abs(pred - actual);
  if (off === 0) return 5;
  if (off <= 5) return 1;
  return 0;
}

// --- load actuals: title -> { box_office, metacritic } ---

const actuals = new Map<string, { bo: number | null; meta: number | null }>();

for (const line of resultsCsv.trim().split('\n').slice(1)) {
  // title,box_office,metacritic,box_office_url,metacritic_url,...
  const cols = line.split(',');
  actuals.set(cols[0], {
    bo: cols[1] === '' ? null : Number(cols[1]),
    meta: cols[2] === '' ? null : Number(cols[2]),
  });
}

// --- load source links from movies.csv IDs ---

const NO_LINKS: MovieLinks = {
  tmdb: null,
  boxOffice: null,
  metacritic: null,
  letterboxd: null,
};
const links = new Map<string, MovieLinks>();

for (const line of moviesCsv.trim().split('\n').slice(1)) {
  // title,wikidata_id,tmdb_id,box_office_mojo_id,metacritic_id,letterboxd_id
  const [title, , tmdbId, bomId, metaId, letterboxdId] = line.split(',');
  links.set(title, {
    tmdb: tmdbId ? `https://www.themoviedb.org/movie/${tmdbId}` : null,
    boxOffice: bomId ? `https://www.boxofficemojo.com/title/${bomId}/` : null,
    // metacritic_id sometimes carries stray slashes (e.g. "movie/power-ballad/").
    metacritic: metaId ? `https://www.metacritic.com/${metaId.replace(/^\/+|\/+$/g, '')}/` : null,
    letterboxd: letterboxdId ? `https://letterboxd.com/film/${letterboxdId.replace(/^\/+|\/+$/g, '')}/` : null,
  });
}

// --- load predictions: title+host -> guesses ---

interface Pred {
  boPred: number;
  metaPred: number;
}

const byTitle = new Map<string, Partial<Record<'sean' | 'amanda', Pred>>>();

for (const line of predictionsCsv.trim().split('\n').slice(1)) {
  // title,host,box_office_pred_millions,metacritic_pred
  const cols = line.split(',');
  const title = cols[0];
  const host = cols[1] as 'sean' | 'amanda';
  const entry = byTitle.get(title) ?? {};
  entry[host] = {
    boPred: Number(cols[2]) * 1_000_000,
    metaPred: Number(cols[3]),
  };
  byTitle.set(title, entry);
}

// --- score every guess ---

export const movies: MovieRow[] = [...byTitle.entries()].map(([title, hosts]) => {
  const info = tmdb[title] ?? null;
  const { bo = null, meta = null } = actuals.get(title) ?? {};
  const score = (pred: Pred): HostLine => {
    const boPts = bo === null ? 0 : boxOfficePts(pred.boPred, bo);
    const metaPts = meta === null ? 0 : metacriticPts(pred.metaPred, meta);
    return { ...pred, boPts, metaPts, totalPts: boPts + metaPts };
  };
  const sean = score(hosts.sean!);
  const amanda = score(hosts.amanda!);
  return {
    title,
    releaseDate: info?.release_date ?? null,
    tmdb: info,
    links: links.get(title) ?? NO_LINKS,
    actualBO: bo,
    actualMeta: meta,
    sean,
    amanda,
    diff: sean.totalPts - amanda.totalPts,
    // A film only counts once both results are in: a Metacritic score alone
    // (reviews land before release) isn't enough, and neither is box office
    // without a Metacritic score.
    scored: bo !== null && meta !== null,
  };
});

movies.sort((a, b) => {
  if (a.releaseDate === b.releaseDate) return a.title.localeCompare(b.title);
  if (a.releaseDate === null) return 1;
  if (b.releaseDate === null) return -1;
  return a.releaseDate < b.releaseDate ? -1 : 1;
});

export const totals = {
  sean: movies.reduce((sum, m) => sum + (m.scored ? m.sean.totalPts : 0), 0),
  amanda: movies.reduce((sum, m) => sum + (m.scored ? m.amanda.totalPts : 0), 0),
  scoredCount: movies.filter((m) => m.scored).length,
  movieCount: movies.length,
};
