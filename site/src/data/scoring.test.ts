import { describe, expect, it } from 'vitest';
import { DEFAULT_SCORING, pointsFor, type BandsMethod, type LinearMethod } from './scoring';

// The 2026 edition: closer guess earns more points, first covering band wins.
const boxOfficeBands = DEFAULT_SCORING.boxOffice as BandsMethod;
const metacriticBands = DEFAULT_SCORING.metacritic as BandsMethod;

// The 2025 edition: golf-style, one point per $1M (box office) / per point (meta).
const boxOfficeLinear: LinearMethod = { type: 'linear', per: 1, unit: 1_000_000, round: 'nearest' };
const metacriticLinear: LinearMethod = { type: 'linear', per: 1, unit: 1, round: 'nearest' };

describe('pointsFor — bands', () => {
  it('awards the top band for an exact guess', () => {
    expect(pointsFor(boxOfficeBands, 100_000_000, 100_000_000)).toBe(20);
  });

  it('includes the band boundary (miss == within)', () => {
    expect(pointsFor(boxOfficeBands, 100_500_000, 100_000_000)).toBe(20);
    expect(pointsFor(boxOfficeBands, 105_000_000, 100_000_000)).toBe(10);
  });

  it('drops to the next band just past a boundary', () => {
    expect(pointsFor(boxOfficeBands, 100_500_001, 100_000_000)).toBe(10);
    expect(pointsFor(boxOfficeBands, 105_000_001, 100_000_000)).toBe(5);
    expect(pointsFor(boxOfficeBands, 110_000_001, 100_000_000)).toBe(1);
  });

  it('scores zero when the miss exceeds every band', () => {
    expect(pointsFor(boxOfficeBands, 151_000_000, 100_000_000)).toBe(0);
  });

  it('is symmetric: over- and under-guessing by the same amount tie', () => {
    expect(pointsFor(boxOfficeBands, 106_000_000, 100_000_000)).toBe(
      pointsFor(boxOfficeBands, 94_000_000, 100_000_000),
    );
  });

  it('handles a zero-width band (Metacritic exact-only top tier)', () => {
    expect(pointsFor(metacriticBands, 70, 70)).toBe(5); // exact
    expect(pointsFor(metacriticBands, 71, 70)).toBe(1); // within 5
    expect(pointsFor(metacriticBands, 76, 70)).toBe(0); // beyond
  });
});

describe('pointsFor — linear', () => {
  it('charges one point per unit of error (nearest)', () => {
    expect(pointsFor(boxOfficeLinear, 12_000_000, 10_000_000)).toBe(2);
    expect(pointsFor(metacriticLinear, 60, 53)).toBe(7);
  });

  it('rounds to nearest by default', () => {
    expect(pointsFor(boxOfficeLinear, 12_400_000, 10_000_000)).toBe(2); // 2.4 -> 2
    expect(pointsFor(boxOfficeLinear, 12_600_000, 10_000_000)).toBe(3); // 2.6 -> 3
  });

  it('floors when round is "down"', () => {
    const method: LinearMethod = { ...boxOfficeLinear, round: 'down' };
    expect(pointsFor(method, 12_900_000, 10_000_000)).toBe(2); // 2.9 -> 2
  });

  it('keeps fractional points when round is "none"', () => {
    const method: LinearMethod = { ...boxOfficeLinear, round: 'none' };
    expect(pointsFor(method, 12_500_000, 10_000_000)).toBe(2.5);
  });

  it('scales by the per-unit penalty', () => {
    const method: LinearMethod = { type: 'linear', per: 3, unit: 1_000_000, round: 'nearest' };
    expect(pointsFor(method, 14_000_000, 10_000_000)).toBe(12); // 4 units * 3
  });

  it('is symmetric and zero for an exact guess', () => {
    expect(pointsFor(boxOfficeLinear, 10_000_000, 10_000_000)).toBe(0);
    expect(pointsFor(boxOfficeLinear, 13_000_000, 10_000_000)).toBe(pointsFor(boxOfficeLinear, 7_000_000, 10_000_000));
  });
});
