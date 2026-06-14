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
const linkBo = document.getElementById('card-link-bo') as HTMLAnchorElement;
const linkMc = document.getElementById('card-link-mc') as HTMLAnchorElement;
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
  setLink(linkBo, links.boxOffice);
  setLink(linkMc, links.metacritic);
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

// ----- column sorting -----
const tbody = document.querySelector('tbody')!;
// The server renders rows sorted by release date ascending.
let sortCol: number | null = 1;
let sortDir: 'asc' | 'desc' = 'asc';

function sortKey(row: HTMLTableRowElement, col: number): string {
  const cell = row.cells[col];
  return cell.dataset.sort ?? cell.textContent!.trim();
}

for (const btn of document.querySelectorAll<HTMLButtonElement>('.sort-btn')) {
  btn.addEventListener('click', () => {
    const col = Number(btn.dataset.col);
    // Text-ish columns sort ascending first, numeric ones biggest-first.
    const firstDir = col <= 1 ? 'asc' : 'desc';
    sortDir = sortCol === col ? (sortDir === 'asc' ? 'desc' : 'asc') : firstDir;
    sortCol = col;

    const mult = sortDir === 'asc' ? 1 : -1;
    const rows = [...tbody.rows];
    rows.sort((a, b) => {
      const ka = sortKey(a, col);
      const kb = sortKey(b, col);
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
