import { describe, expect, it } from 'vitest';
import type { MovieRow } from '../data/games';
import { advantage, diffChip } from './format';

// diffChip only reads `scored` and `diff`, so a minimal stub stands in for a row.
function row(diff: number, scored = true): MovieRow {
  return { diff, scored } as MovieRow;
}

describe('advantage — winner direction (objective-aware)', () => {
  it('credits the higher score when high wins', () => {
    expect(advantage(8, 5, false)).toBe(3); // Sean ahead
    expect(advantage(5, 8, false)).toBe(-3); // Amanda ahead
  });

  it('credits the lower score when low wins (golf)', () => {
    expect(advantage(5, 8, true)).toBe(3); // Sean ahead despite fewer points
    expect(advantage(8, 5, true)).toBe(-3); // Amanda ahead
  });

  it('is zero on a tie regardless of objective', () => {
    // Sign of zero is irrelevant: downstream only checks === 0 / > 0 / < 0.
    expect(advantage(6, 6, false) === 0).toBe(true);
    expect(advantage(6, 6, true) === 0).toBe(true);
  });
});

describe('diffChip — plain Sean−Amanda gap (objective-independent)', () => {
  it('credits the host with more points', () => {
    expect(diffChip(row(3))).toEqual({ text: '+3 Sean', cls: 'sean' });
    expect(diffChip(row(-4))).toEqual({ text: '+4 Amanda', cls: 'amanda' });
  });

  it('does not flip for golf-style editions', () => {
    // Same diff, whether or not lowest wins: the chip reports points, not standing.
    expect(diffChip(row(2))).toEqual({ text: '+2 Sean', cls: 'sean' });
  });

  it('shows a tie when totals match', () => {
    expect(diffChip(row(0))).toEqual({ text: 'Tie', cls: 'tie' });
  });

  it('shows TBD before a movie is scored', () => {
    expect(diffChip(row(5, false))).toEqual({ text: 'TBD', cls: 'tbd' });
  });
});
