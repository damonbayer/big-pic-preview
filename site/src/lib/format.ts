// Pure formatting and scoring-display helpers for the scoreboard. Kept free of
// component state so they can be unit-tested in isolation; the objective-aware
// ones (advantage, heat) take the game's direction as an argument rather than
// closing over it.
import type { MovieRow, ScoreMethod } from '../data/games';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function fmtDate(iso: string | null): string {
  if (!iso) return 'TBD';
  const [, m, d] = iso.split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}`;
}

export function fmtBO(v: number | null): string {
  if (v === null) return '—';
  const millions = v / 1e6;
  const text = millions >= 100 ? Math.round(millions).toString() : millions.toFixed(1).replace(/\.0$/, '');
  return `$${text}M`;
}

export function fmtMeta(v: number | null): string {
  return v === null ? '—' : String(v);
}

// Render a box-office scoring threshold (in dollars) for the rules panel.
export function fmtThreshold(v: number): string {
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1).replace(/\.0$/, '')}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${v}`;
}

export function pluralPts(pts: number): string {
  return `${pts} ${pts === 1 ? 'pt' : 'pts'}`;
}

// One "<label> → <pts>" line per rule, for the "How the scoring works" panel.
// `kind` controls how the box-office vs Metacritic units read.
export function ruleLines(method: ScoreMethod, kind: 'bo' | 'meta'): { label: string; pts: string }[] {
  if (method.type === 'bands') {
    return method.bands.map((band) => ({
      label:
        kind === 'bo' ? `Within ${fmtThreshold(band.within)}` : band.within === 0 ? 'Exact' : `Within ${band.within}`,
      pts: pluralPts(band.pts),
    }));
  }
  const unitLabel = kind === 'bo' ? fmtThreshold(method.unit) : method.unit === 1 ? 'point' : `${method.unit} points`;
  return [{ label: `Every ${unitLabel} off`, pts: pluralPts(method.per) }];
}

export function ptsTitle(line: { boPts: number; metaPts: number }, scored: boolean): string | undefined {
  return scored ? `Box office: ${line.boPts} pts · Metacritic: ${line.metaPts} pts` : undefined;
}

// More precise than fmtBO so a $1.04M miss doesn't read as "$1M".
export function fmtBODiff(v: number): string {
  const millions = v / 1e6;
  const text =
    millions >= 100
      ? Math.round(millions).toString()
      : millions >= 10
        ? millions.toFixed(1).replace(/\.0$/, '')
        : millions.toFixed(2).replace(/0$/, '').replace(/\.0$/, '');
  return `$${text}M`;
}

export function metaGuessTitle(pred: number, actual: number | null, pts: number): string | undefined {
  if (actual === null) return undefined;
  const off = Math.abs(pred - actual);
  return `Guessed ${pred}, actual ${actual} — ${off === 0 ? 'exact' : `off by ${off}`} → ${pluralPts(pts)}`;
}

export function boGuessTitle(pred: number, actual: number | null, pts: number): string | undefined {
  if (actual === null) return undefined;
  const off = Math.abs(pred - actual);
  return `Guessed ${fmtBO(pred)}, actual ${fmtBO(actual)} — off by ${fmtBODiff(off)} → ${pluralPts(pts)}`;
}

// Sean's advantage over Amanda: positive means Sean is ahead, in whichever
// direction this game's objective rewards. Golf-style editions (lowest total
// wins) flip the sign.
export function advantage(seanPts: number, amandaPts: number, lowerWins: boolean): number {
  const lead = seanPts - amandaPts;
  return lowerWins ? -lead : lead;
}

// The differential is a plain Sean−Amanda point gap, independent of objective:
// it credits whoever holds more points. In golf-style (lowest wins) editions
// that's the trailing host, which reads fine once you know lowest wins — and is
// far less confusing than flipping the sign. Who's actually ahead is conveyed by
// the winner highlight (see `advantage`), not this chip.
export function diffChip(m: MovieRow): { text: string; cls: string } {
  if (!m.scored) return { text: 'TBD', cls: 'tbd' };
  const gap = Math.abs(m.diff);
  if (m.diff > 0) return { text: `+${gap} Sean`, cls: 'sean' };
  if (m.diff < 0) return { text: `+${gap} Amanda`, cls: 'amanda' };
  return { text: 'Tie', cls: 'tie' };
}

// data-pts value for a guess cell; undefined (no attribute) when the actual
// isn't in yet or the shading is disabled. Guess-cell shading reads "more
// points = better guess", which only holds when the objective is to maximize.
export function heat(pts: number, actual: number | null, showHeat: boolean): number | undefined {
  return showHeat && actual !== null ? pts : undefined;
}
