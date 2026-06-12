import scoresCsv from '../../../scores.csv?raw';
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

export interface MovieRow {
  title: string;
  releaseDate: string | null;
  tmdb: TmdbInfo | null;
  actualBO: number | null;
  actualMeta: number | null;
  sean: HostLine;
  amanda: HostLine;
  diff: number;
  scored: boolean;
}

const tmdb = tmdbDetails as Record<string, TmdbInfo>;

function num(value: string): number | null {
  return value === '' ? null : Number(value);
}

interface RawLine {
  boPred: number;
  metaPred: number;
  actualBO: number | null;
  actualMeta: number | null;
  boPts: number;
  metaPts: number;
  totalPts: number;
}

const byTitle = new Map<string, Partial<Record<'sean' | 'amanda', RawLine>>>();

for (const line of scoresCsv.trim().split('\n').slice(1)) {
  const cols = line.split(',');
  // title,host,box_office_pred,metacritic_pred,box_office,metacritic,
  // box_office_diff,metacritic_diff,box_office_pts,metacritic_pts,total_pts
  const title = cols[0];
  const host = cols[1] as 'sean' | 'amanda';
  const entry = byTitle.get(title) ?? {};
  entry[host] = {
    boPred: Number(cols[2]),
    metaPred: Number(cols[3]),
    actualBO: num(cols[4]),
    actualMeta: num(cols[5]),
    boPts: Number(cols[8]),
    metaPts: Number(cols[9]),
    totalPts: Number(cols[10]),
  };
  byTitle.set(title, entry);
}

export const movies: MovieRow[] = [...byTitle.entries()].map(([title, hosts]) => {
  const sean = hosts.sean!;
  const amanda = hosts.amanda!;
  const info = tmdb[title] ?? null;
  const pick = (raw: RawLine): HostLine => ({
    boPred: raw.boPred,
    metaPred: raw.metaPred,
    boPts: raw.boPts,
    metaPts: raw.metaPts,
    totalPts: raw.totalPts,
  });
  return {
    title,
    releaseDate: info?.release_date ?? null,
    tmdb: info,
    actualBO: sean.actualBO,
    actualMeta: sean.actualMeta,
    sean: pick(sean),
    amanda: pick(amanda),
    diff: sean.totalPts - amanda.totalPts,
    // A film only counts once both results are in: a Metacritic score alone
    // (reviews land before release) isn't enough, and neither is box office
    // without a Metacritic score.
    scored: sean.actualBO !== null && sean.actualMeta !== null,
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
