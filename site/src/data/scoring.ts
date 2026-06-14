// Pure scoring logic, kept free of data-loading side effects so it can be unit
// tested in isolation. `games.ts` re-exports these for existing importers.

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

// Points a single guess earns: how far `pred` lands from `actual` under `method`.
export function pointsFor(method: ScoreMethod, pred: number, actual: number): number {
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
