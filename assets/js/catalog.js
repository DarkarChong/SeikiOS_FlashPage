// SEIKIOS catalog — loads _games.json, renders the grid, and wires up the
// sidebar filter / search / order controls. Vanilla JS, no dependencies.

const FILTER_LABELS = {
  all: 'All Games',
  inkagames: 'Saw Games',
};

const state = { filter: 'all', query: '', order: 'name' };
let GAMES = [];

async function loadCatalog() {
  const base = document.querySelector('base')?.href || location.href.replace(/\/[^/]*$/, '/');
  const res = await fetch(base + '_games.json');
  GAMES = await res.json();

  buildCollage(GAMES);
  wireControls();
  render();
}

// ── Background character collage (repeat thumbnails to fill the gutters) ──
function buildCollage(games) {
  const el = document.getElementById('bg-collage');
  if (!el) return;
  const thumbs = games.map(g => g.thumbnail).filter(Boolean);
  if (!thumbs.length) return;
  const TILES = 60;
  el.innerHTML = Array.from({ length: TILES }, (_, i) => {
    const src = thumbs[i % thumbs.length];
    return `<img src="${src}" alt="" loading="lazy" aria-hidden="true">`;
  }).join('');
}

// ── Controls ──
function wireControls() {
  document.querySelectorAll('.nav-item[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      state.filter = btn.dataset.filter;
      document.querySelectorAll('.nav-item[data-filter]').forEach(b =>
        b.classList.toggle('active', b === btn));
      const title = document.getElementById('page-title-text');
      if (title) title.textContent = FILTER_LABELS[state.filter] || 'Games';
      render();
    });
  });

  const search = document.getElementById('search');
  if (search) search.addEventListener('input', e => {
    state.query = e.target.value.trim().toLowerCase();
    render();
  });

  const order = document.getElementById('order');
  if (order) order.addEventListener('change', e => {
    state.order = e.target.value;
    render();
  });
}

// ── Filter + sort ──
function visibleGames() {
  let list = GAMES.slice();

  if (state.filter !== 'all') {
    list = list.filter(g => (g.category || '') === state.filter);
  }
  if (state.query) {
    list = list.filter(g => g.title.toLowerCase().includes(state.query));
  }

  const byName = (a, b) => a.title.localeCompare(b.title);
  const byYear = (a, b) => (a.year || 0) - (b.year || 0);
  switch (state.order) {
    case 'name-desc': list.sort((a, b) => byName(b, a)); break;
    case 'year':      list.sort(byYear); break;
    case 'year-desc': list.sort((a, b) => byYear(b, a)); break;
    default:          list.sort(byName);
  }
  return list;
}

// ── Render ──
function render() {
  const grid = document.getElementById('game-grid');
  const empty = document.getElementById('empty-state');
  const counter = document.getElementById('game-count');
  const list = visibleGames();

  if (counter) counter.textContent = list.length;
  if (empty) empty.hidden = list.length > 0;

  grid.innerHTML = list.map(g => `
    <a class="card" href="games/${g.id}/">
      ${g.thumbnail
        ? `<img class="card-thumb" src="${g.thumbnail}" alt="${g.title}" loading="lazy">`
        : `<div class="card-thumb-placeholder">▶</div>`}
      <div class="card-body">
        <div class="card-title">${g.title}</div>
        <div class="card-meta">
          ${g.status === 'patched'
            ? `<span class="badge badge-patched">✓ Patched</span>`
            : `<span class="badge badge-wip">WIP</span>`}
          ${g.year ? `<span class="card-year">${g.year}</span>` : ''}
        </div>
      </div>
    </a>
  `).join('');
}

loadCatalog();
