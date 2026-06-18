// Join a path onto the configured site base (import.meta.env.BASE_URL),
// collapsing any resulting double slashes. Centralized so every caller uses the
// same, robust normalization rather than ad-hoc `.replace('//', '/')` variants
// (which only replace the first occurrence).
const base = import.meta.env.BASE_URL;

export function assetPath(path = ''): string {
  return `${base}/${path}`.replace(/\/{2,}/g, '/');
}

// Convenience for the site root, e.g. the hero logo / "back" links.
export const home = assetPath();
