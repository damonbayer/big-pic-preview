const data = JSON.parse(document.getElementById('movie-data')!.textContent!);
const card = document.getElementById('movie-card')!;
const poster = document.getElementById('card-poster') as HTMLImageElement;
const titleEl = document.getElementById('card-title')!;
const metaEl = document.getElementById('card-meta')!;
const taglineEl = document.getElementById('card-tagline')!;
const overviewEl = document.getElementById('card-overview')!;
const creditsEl = document.getElementById('card-credits')!;
const linksEl = document.getElementById('card-links')!;
const linkTmdb = document.getElementById('card-link-tmdb') as HTMLAnchorElement;
const linkImdb = document.getElementById('card-link-imdb') as HTMLAnchorElement;
const linkLetterboxd = document.getElementById('card-link-letterboxd') as HTMLAnchorElement;

let pinned: string | null = null;

function setLink(a: HTMLAnchorElement, url: string | null | undefined) {
  if (url) {
    a.href = url;
    a.hidden = false;
  } else {
    a.removeAttribute('href');
    a.hidden = true;
  }
}

function fill(title: string) {
  const d = data[title];
  if (!d) return false;
  titleEl.textContent = title;
  const bits = [d.date];
  if (d.runtime) bits.push(`${d.runtime} min`);
  if (d.genres?.length) bits.push(d.genres.join(' / '));
  metaEl.textContent = bits.join(' · ');
  taglineEl.textContent = d.tagline ?? '';
  taglineEl.hidden = !d.tagline;
  overviewEl.textContent = d.overview ?? 'No synopsis yet.';
  const credits = [];
  if (d.directors?.length) credits.push(`Directed by ${d.directors.join(', ')}`);
  if (d.cast?.length) credits.push(`Starring ${d.cast.join(', ')}`);
  creditsEl.textContent = credits.join(' · ');
  creditsEl.hidden = credits.length === 0;
  const links = d.links ?? {};
  setLink(linkTmdb, links.tmdb);
  setLink(linkImdb, links.imdb);
  setLink(linkLetterboxd, links.letterboxd);
  if (d.poster) {
    poster.src = d.poster;
    poster.hidden = false;
  } else {
    poster.removeAttribute('src');
    poster.hidden = true;
  }
  return true;
}

function place(anchor: Element) {
  const r = anchor.getBoundingClientRect();
  card.hidden = false;
  const cw = card.offsetWidth;
  const ch = card.offsetHeight;
  let x = r.right + 14;
  if (x + cw > window.innerWidth - 8) x = Math.max(8, window.innerWidth - cw - 8);
  let y = r.top - 8;
  if (y + ch > window.innerHeight - 8) y = Math.max(8, window.innerHeight - ch - 8);
  card.style.left = `${x}px`;
  card.style.top = `${y}px`;
}

function show(btn: Element) {
  const title = (btn as HTMLElement).dataset.title!;
  if (fill(title)) place(btn);
}

function hide() {
  if (!pinned) card.hidden = true;
}

// Pinning enables pointer events so the source links can be clicked;
// hover-only cards stay click-through so they don't block the table.
function closeCard() {
  pinned = null;
  card.hidden = true;
  card.style.pointerEvents = '';
}

for (const btn of document.querySelectorAll<HTMLElement>('.movie-btn')) {
  btn.addEventListener('mouseenter', () => {
    if (!pinned) show(btn);
  });
  btn.addEventListener('mouseleave', hide);
  btn.addEventListener('focus', () => {
    if (!pinned) show(btn);
  });
  btn.addEventListener('blur', hide);
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const title = btn.dataset.title!;
    if (pinned === title) {
      closeCard();
    } else {
      pinned = title;
      show(btn);
      card.style.pointerEvents = 'auto';
    }
  });
}

// Clicking a source link shouldn't dismiss the pinned card.
linksEl.addEventListener('click', (e) => e.stopPropagation());

document.addEventListener('click', closeCard);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeCard();
});
window.addEventListener(
  'scroll',
  () => {
    if (!pinned) card.hidden = true;
  },
  { passive: true },
);

// ----- leader badge wiggle -----
// The "Winner" / "In the lead" badge does a little shimmy on load and whenever
// the leading card is clicked. Re-adding the class after a forced reflow
// restarts the one-shot CSS animation.
const badge = document.querySelector<HTMLElement>('.score-card.leading .badge');
if (badge) {
  const wiggle = () => {
    badge.classList.remove('wiggle');
    void badge.offsetWidth;
    badge.classList.add('wiggle');
  };
  wiggle();
  badge.closest('.score-card')?.addEventListener('click', wiggle);
}

// ----- progress emoji dance -----
// The emoji dances on load; later dances are user-triggered.
for (const emoji of document.querySelectorAll<HTMLElement>('.progress .emoji')) {
  const dance = () => {
    emoji.classList.remove('dance-now');
    void emoji.offsetWidth;
    emoji.classList.add('dance-now');
  };
  dance();
  emoji.addEventListener('click', dance);
  emoji.addEventListener('animationend', (event) => {
    if (event.animationName === 'emoji-dance-now') emoji.classList.remove('dance-now');
  });
}

// ----- localize the "scores last updated" stamp -----
// The page ships a UTC fallback (for no-JS readers and the first paint); rewrite
// it here in the visitor's own locale and time zone so the time reads on their
// clock. `toLocaleString(undefined, …)` defaults to both.
for (const el of document.querySelectorAll<HTMLTimeElement>('time[data-local-time]')) {
  const iso = el.getAttribute('datetime');
  if (!iso) continue;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) continue;
  el.textContent = d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  });
  el.title = d.toLocaleString(undefined, { dateStyle: 'full', timeStyle: 'long' });
}

// ----- horizontal scroll shadows -----
// Toggle the right table-edge shadow so the off-screen Points/Differential
// columns are discoverable on narrow viewports.
const scroller = document.querySelector<HTMLElement>('.table-scroll');
if (scroller) {
  const updateShadows = () => {
    const max = scroller.scrollWidth - scroller.clientWidth;
    scroller.classList.toggle('can-scroll-right', scroller.scrollLeft < max - 1);
  };
  updateShadows();
  scroller.addEventListener('scroll', updateShadows, { passive: true });
  window.addEventListener('resize', updateShadows, { passive: true });
}

// ----- column sorting -----
const tbody = document.querySelector('tbody')!;
type SortKey =
  | 'movieTitle'
  | 'releaseDate'
  | 'seanMeta'
  | 'amandaMeta'
  | 'actualMeta'
  | 'seanBoxOffice'
  | 'amandaBoxOffice'
  | 'actualBoxOffice'
  | 'seanPoints'
  | 'amandaPoints'
  | 'diff';

const SORT_DATASET_KEYS: Record<SortKey, string> = {
  movieTitle: 'sortMovieTitle',
  releaseDate: 'sortReleaseDate',
  seanMeta: 'sortSeanMeta',
  amandaMeta: 'sortAmandaMeta',
  actualMeta: 'sortActualMeta',
  seanBoxOffice: 'sortSeanBoxOffice',
  amandaBoxOffice: 'sortAmandaBoxOffice',
  actualBoxOffice: 'sortActualBoxOffice',
  seanPoints: 'sortSeanPoints',
  amandaPoints: 'sortAmandaPoints',
  diff: 'sortDiff',
};
const ASC_FIRST_SORT_KEYS = new Set<SortKey>(['movieTitle', 'releaseDate']);

function isSortKey(key: string | undefined): key is SortKey {
  return key !== undefined && key in SORT_DATASET_KEYS;
}

// The server renders rows sorted by release date ascending.
let activeSortKey: SortKey | null = 'releaseDate';
let sortDir: 'asc' | 'desc' = 'asc';

function sortValue(row: HTMLTableRowElement, key: SortKey): string {
  return row.dataset[SORT_DATASET_KEYS[key]] ?? '';
}

for (const btn of document.querySelectorAll<HTMLButtonElement>('.sort-btn')) {
  btn.addEventListener('click', () => {
    const key = btn.dataset.sortKey;
    if (!isSortKey(key)) {
      throw new Error(`Sort button has an unknown data-sort-key: ${key ?? '(missing)'}`);
    }
    // Text-ish columns sort ascending first, numeric ones biggest-first.
    const firstDir = ASC_FIRST_SORT_KEYS.has(key) ? 'asc' : 'desc';
    sortDir = activeSortKey === key ? (sortDir === 'asc' ? 'desc' : 'asc') : firstDir;
    activeSortKey = key;

    const mult = sortDir === 'asc' ? 1 : -1;
    const rows = [...tbody.rows];
    rows.sort((a, b) => {
      const ka = sortValue(a, key);
      const kb = sortValue(b, key);
      if (ka === '' || kb === '') return (ka === '' ? 1 : 0) - (kb === '' ? 1 : 0);
      const na = Number(ka);
      const nb = Number(kb);
      if (!Number.isNaN(na) && !Number.isNaN(nb)) return (na - nb) * mult;
      return ka.localeCompare(kb) * mult;
    });
    for (const row of rows) tbody.appendChild(row);

    for (const th of document.querySelectorAll('th[aria-sort]')) th.removeAttribute('aria-sort');
    btn.closest('th')!.setAttribute('aria-sort', sortDir === 'asc' ? 'ascending' : 'descending');
  });
}
