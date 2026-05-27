// ── AI provider model catalogue (fetched from /api/settings/providers) ────────
let PROVIDER_MODELS = {};

function buildProviderModelSelect(selectEl, provider, { withDefault = false, selectedValue = '' } = {}) {
  const models = PROVIDER_MODELS[provider] || [];
  selectEl.replaceChildren();
  if (withDefault) {
    const o = document.createElement('option'); o.value = ''; o.textContent = 'Default'; selectEl.appendChild(o);
  }
  models.forEach(({ id, label }) => {
    const o = document.createElement('option'); o.value = id; o.textContent = label;
    if (id === selectedValue) o.selected = true;
    selectEl.appendChild(o);
  });
  if (!withDefault && !selectedValue && models.length) selectEl.value = models[0].id;
}

// ── DOM helper ────────────────────────────────────────────────────────────────
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) {
    Object.entries(props).forEach(([k, v]) => {
      if (v == null) return;
      if (k === 'cls')     { el.className = v; }
      else if (k === 'style')   { el.style.cssText = v; }
      else if (k === 'text')    { el.textContent = v; }
      else if (k === 'onclick') { el.addEventListener('click', v); }
      else                      { el.setAttribute(k, v); }
    });
  }
  children.flat().forEach(c => {
    if (c == null) return;
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  });
  return el;
}

function icon(cls) {
  const i = document.createElement('i');
  i.className = cls;
  return i;
}

// ── State ─────────────────────────────────────────────────────────────────────
const App = {
  series: [],
  total: 0,
  page: 1,
  limit: 15,
  activeStatuses: new Set(['new', 'draft', 'approved']),
  collections: [],
  activeCollection: null,
  currentSeriesId: null,
  currentSeries: null,
  unsortedSeriesId: null,
  search: '',
  currentView: 'editor',
};

// Maps display-status names → DB status values they represent.
// "draft" covers approved; "active" covers partial_posted.
const STATUS_DISPLAY_GROUPS = {
  new:    ['new'],
  draft:  ['draft', 'approved'],
  active: ['active', 'partial_posted'],
  done:   ['done', 'posted'],
  skip:   ['skip'],
};

function statusDisplay(dbStatus) {
  for (const [display, dbValues] of Object.entries(STATUS_DISPLAY_GROUPS)) {
    if (dbValues.includes(dbStatus)) return display;
  }
  return dbStatus;
}

function activeDbStatuses() {
  const active = [...document.querySelectorAll('.aap-chip[data-status-group].is-active')]
    .map(el => el.dataset.statusGroup);
  return active.flatMap(g => STATUS_DISPLAY_GROUPS[g] || [g]);
}

// ── API ───────────────────────────────────────────────────────────────────────
async function apiFetch(method, path, body) {
  const opts = { method };
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body != null) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    const detail = err.detail;
    const msg = Array.isArray(detail)
      ? detail.map(d => d.msg || JSON.stringify(d)).join('; ')
      : (typeof detail === 'object' && detail !== null
          ? (detail.message || resp.statusText)
          : (detail || resp.statusText));
    const e = new Error(msg);
    e.status = resp.status;
    e.body = err;
    throw e;
  }
  return resp.json();
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type) {
  const cls = { success: 'text-bg-success', danger: 'text-bg-danger' }[type] || 'text-bg-secondary';
  const wrap = h('div', { cls: 'toast ' + cls, role: 'alert' });
  const inner = h('div', { cls: 'd-flex' });
  const body = h('div', { cls: 'toast-body', text: msg });
  const close = h('button', { cls: 'btn-close btn-close-white me-2 m-auto', type: 'button' });
  close.setAttribute('data-bs-dismiss', 'toast');
  inner.append(body, close);
  wrap.appendChild(inner);
  document.getElementById('toastContainer').appendChild(wrap);
  const t = new bootstrap.Toast(wrap, type === 'danger' ? { autohide: false } : { delay: 3500 });
  t.show();
  wrap.addEventListener('hidden.bs.toast', () => wrap.remove());
}

// ── Error Service ─────────────────────────────────────────────────────────────
const ErrorService = (() => {
  const _log = [];
  const MAX = 20;
  const _listeners = new Set();
  const _cleared = new Set();

  function record(context, message) {
    _cleared.delete(context);
    const msg = message || 'Unknown error';
    _log.unshift({ ts: new Date(), context, message: msg });
    if (_log.length > MAX) _log.pop();
    showToast(msg, 'danger');
    _listeners.forEach(fn => fn());
  }

  function clear(context) {
    _cleared.add(context);
    _listeners.forEach(fn => fn());
  }

  function isCleared(context) { return _cleared.has(context); }
  function getAll() { return [..._log]; }
  function subscribe(fn) { _listeners.add(fn); return () => _listeners.delete(fn); }

  return { record, clear, isCleared, getAll, subscribe };
})();

// ── Confirm ───────────────────────────────────────────────────────────────────
function showConfirm(message, onOk) {
  document.getElementById('confirmBody').textContent = message;
  const old = document.getElementById('confirmOkBtn');
  const btn = old.cloneNode(true);
  old.replaceWith(btn);
  btn.id = 'confirmOkBtn';
  btn.addEventListener('click', onOk);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('confirmModal')).show();
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function formatDate(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr.endsWith('Z') ? isoStr : isoStr + 'Z');
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) + ' ' +
         d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

// ── Series list ───────────────────────────────────────────────────────────────
let _sentinel = null;
let _observer = null;

function _updateSentinel(active) {
  if (!_sentinel) {
    _sentinel = h('div', { id: 'scrollSentinel', style: 'height:1px' });
    const sidebar = document.getElementById('seriesListPanel');
    sidebar.insertBefore(_sentinel, document.getElementById('loadMoreBtn'));
    _observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && App.series.length < App.total) {
        loadMoreSeries();
      }
    }, { threshold: 0.1 });
  }
  if (active) _observer.observe(_sentinel);
  else _observer.unobserve(_sentinel);
}

function _trimDomIfNeeded(container) {
  const items = container.querySelectorAll('[data-id]');
  if (items.length <= 100) return;
  for (let i = 0; i < 50; i++) items[i].remove();
  if (!document.getElementById('seriesTrimNotice')) {
    const notice = h('div', {
      id: 'seriesTrimNotice',
      cls: 'text-muted small text-center py-1 border-bottom',
      text: '↑ Scroll to top to reload from beginning',
    });
    container.prepend(notice);
  }
}

async function loadSeries(reset) {
  if (reset) {
    App.page = 1; App.series = [];
    document.getElementById('seriesItems').replaceChildren();
    document.getElementById('seriesTrimNotice')?.remove();
    if (_sentinel) _observer.unobserve(_sentinel);
  }
  document.getElementById('seriesListLoading').classList.remove('d-none');
  try {
    const statuses = [...App.activeStatuses].join(',') || 'new';
    const q = new URLSearchParams({ page: App.page, limit: App.limit, status: statuses });
    if (App.search) q.set('search', App.search);
    if (App.activeCollection) q.set('collection_id', App.activeCollection);
    const data = await apiFetch('GET', '/api/series?' + q);
    App.series.push(...data.items);
    App.total = data.total;
    const countEl = document.getElementById('seriesCount');
    if (countEl) countEl.textContent = App.total + ' series';
    const container = document.getElementById('seriesItems');
    const visible = data.items.filter(s => (s.name || s.title) !== 'Unsorted' && s.id !== App.unsortedSeriesId);
    visible.forEach(s => container.appendChild(buildSeriesItem(s)));
    const hasMore = App.series.length < App.total;
    document.getElementById('loadMoreBtn').classList.toggle('d-none', !hasMore);
    _updateSentinel(hasMore);
    if (!reset) _trimDomIfNeeded(container);
    if (reset && !App.currentSeriesId && App.currentView === 'editor') {
      showView('list', { push: false });
    }
  } catch (e) {
    showToast(e.message, 'danger');
  } finally {
    document.getElementById('seriesListLoading').classList.add('d-none');
  }
}

async function loadMoreSeries() {
  App.page++;
  await loadSeries(false);
}

function buildSeriesItem(s) {
  const displayStatus = statusDisplay(s.status);
  const dotVar = `var(--aap-dot-${displayStatus})`;
  const name = s.name || s.title || s.original_folder_name || String(s.id).slice(0, 8);
  const isSlug = !(s.name || s.title);

  const thumb = s.cover_url
    ? h('img', {
        cls: 'aap-series-row__thumb-inner',
        src: s.cover_url,
        style: 'object-fit:cover',
        loading: 'lazy',
      })
    : h('div', { cls: 'aap-series-row__thumb-inner' });

  const postedCount = s.posted_count ?? 0;
  const imageCount  = s.image_count  ?? 0;

  const countsChildren = [h('span', {}, String(imageCount) + ' img')];
  if (postedCount > 0) {
    const pct = imageCount > 0 ? Math.round((postedCount / imageCount) * 100) : 0;
    countsChildren.push(
      h('span', { cls: 'aap-bar-mini' },
        h('div', { cls: 'aap-bar-mini__fill', style: `width:${pct}%` })
      ),
      h('span', {}, `${postedCount}/${imageCount}`)
    );
  } else {
    countsChildren.push(h('span', { cls: 'aap-mute' }, 'no posts yet'));
  }

  const metaChildren = [
    h('span', {
      cls: 'aap-status-pill',
      style: `--pill-color:${dotVar}`,
      text: displayStatus,
    }),
  ];
  if (s.collection_name) {
    const label = s.collection_name.length > 22
      ? s.collection_name.slice(0, 21) + '…'
      : s.collection_name;
    metaChildren.push(h('span', { cls: 'aap-collection-tag', text: '↪ ' + label }));
  }

  return h('article', {
    cls: 'aap-series-row',
    id: 'si-' + s.id,
    'data-id': s.id,
    style: `--stripe-color:${dotVar};--pill-color:${dotVar}`,
    onclick: () => selectSeries(s.id),
  },
    h('div', { cls: 'aap-series-row__stripe' }),
    h('div', { cls: 'aap-series-row__thumb' }, thumb),
    h('div', { cls: 'aap-series-row__body' },
      h('div', { cls: 'aap-series-row__meta' }, ...metaChildren),
      h('div', {
        cls: 'aap-series-row__title' + (isSlug ? ' is-slug' : ''),
        text: name,
      }),
      h('div', { cls: 'aap-series-row__counts' }, ...countsChildren)
    ),
    h('div', { cls: 'aap-series-row__actions' },
      h('button', {
        cls: 'aap-icon-btn',
        title: 'Open',
        onclick: (e) => { e.stopPropagation(); selectSeries(s.id); },
      }, '→')
    )
  );
}

function updateSeriesItem(s) {
  const old = document.getElementById('si-' + s.id);
  if (!old) return;
  // SeriesDetail lacks cover_url / image_count — derive them from images[] when present
  const item = ('cover_url' in s) ? s : {
    ...s,
    cover_url: s.images?.find(i => !i.deleted_at)?.public_url ?? null,
    image_count: s.images?.filter(i => !i.deleted_at).length ?? 0,
    collection_name: s.collection?.name ?? null,
    collection_name_ru: s.collection?.name_ru ?? null,
  };
  old.replaceWith(buildSeriesItem(item));
}

async function selectSeries(id, { push = true } = {}) {
  App.currentSeriesId = id;
  document.querySelectorAll('.aap-series-row').forEach(el => {
    el.classList.toggle('is-active', el.dataset.id === String(id));
  });
  showView('editor', { push: false });
  await loadSeriesDetail(id);
  if (push) _pushState();
}

let _loadDetailToken = 0;

async function loadSeriesDetail(id, { silent = false } = {}) {
  const token = ++_loadDetailToken;
  const panel = document.getElementById('editorPanel');
  if (!silent) {
    panel.replaceChildren(h('div', { cls: 'text-center p-5' }, h('div', { cls: 'spinner-border text-secondary' })));
  }
  try {
    const s = await apiFetch('GET', '/api/series/' + id);
    if (token !== _loadDetailToken) return;
    App.currentSeries = s;
    renderEditor(s);
  } catch (e) {
    if (token !== _loadDetailToken) return;
    panel.replaceChildren(h('div', { cls: 'alert alert-danger', text: e.message }));
  }
}

async function selectUnsorted() {
  try {
    const s = await apiFetch('GET', '/api/series/unsorted');
    App.unsortedSeriesId = s.id;
    if (!App.series.find(x => x.id === s.id)) App.series.unshift(s);
    await selectSeries(s.id);
  } catch (e) { showToast(e.message, 'danger'); }
}

async function createSeries() {
  try {
    const s = await apiFetch('POST', '/api/series', { name: '', title: '' });
    document.getElementById('seriesItems').prepend(buildSeriesItem(s));
    App.series.unshift(s);
    await selectSeries(s.id);
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

// ── Filter ────────────────────────────────────────────────────────────────────
function onChipToggle(chip) {
  chip.classList.toggle('is-active');
  App.activeStatuses = new Set(activeDbStatuses());
  loadSeries(true);
  _pushState();
}

function onFilterChange() {
  App.activeStatuses = new Set(activeDbStatuses());
  loadSeries(true);
  _pushState();
}

let _searchDebounce = null;
function onSearchChange(val) {
  clearTimeout(_searchDebounce);
  _searchDebounce = setTimeout(() => {
    App.search = val.trim();
    loadSeries(true);
    _pushState();
  }, 300);
}

// ── View switching ────────────────────────────────────────────────────────────
function showView(view, { push = true } = {}) {
  App.currentView = view;
  const listPanel   = document.getElementById('seriesListPanel');
  const editor      = document.getElementById('editorPanel');
  const queue       = document.getElementById('queuePanel');
  const trash       = document.getElementById('trashPanel');
  const collections = document.getElementById('collectionsPanel');
  const stats       = document.getElementById('statsPanel');

  [listPanel, editor, queue, trash, collections, stats].forEach(p => p && p.classList.add('d-none'));

  if (view === 'list') {
    listPanel.classList.remove('d-none');
  } else if (view === 'editor') {
    editor.classList.remove('d-none');
  } else if (view === 'queue') {
    queue.classList.remove('d-none');
    refreshQueue();
  } else if (view === 'trash') {
    trash.classList.remove('d-none');
    refreshTrash();
  } else if (view === 'collections') {
    collections && collections.classList.remove('d-none');
    refreshCollections();
  } else if (view === 'stats') {
    stats && stats.classList.remove('d-none');
    if (typeof refreshStats === 'function') refreshStats();
  }

  document.getElementById('navCollections')?.classList.toggle('is-active', view === 'collections');
  document.getElementById('navQueue')?.classList.toggle('is-active', view === 'queue');
  document.getElementById('navTrash')?.classList.toggle('is-active', view === 'trash');
  document.getElementById('navStats')?.classList.toggle('is-active', view === 'stats');

  if (push) _pushState();
}

// ── Queue ─────────────────────────────────────────────────────────────────────
function _platformIcon(platform) {
  const cls = { instagram: 'bi bi-instagram', telegram: 'bi bi-telegram', pinterest: 'bi bi-pinterest' }[platform] || 'bi bi-circle';
  return icon(cls);
}

let _activeQueueEditRow = null;

function _openQueueEdit(postId, scheduledAt, dataRow) {
  // Close any already-open edit row or post-edit form
  if (_activeQueueEditRow) { _activeQueueEditRow.remove(); _activeQueueEditRow = null; }
  document.querySelectorAll('[id^="queue-post-edit-"]').forEach(el => el.remove());

  // Convert UTC ISO string to datetime-local value (YYYY-MM-DDTHH:MM, UTC)
  function _toLocal(iso) {
    if (!iso) return '';
    const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
    const p = n => String(n).padStart(2, '0');
    return d.getUTCFullYear() + '-' + p(d.getUTCMonth() + 1) + '-' + p(d.getUTCDate()) + 'T' + p(d.getUTCHours()) + ':' + p(d.getUTCMinutes());
  }

  const dtInput = Object.assign(document.createElement('input'), {
    type: 'datetime-local', value: _toLocal(scheduledAt),
    className: 'form-control aap-input aap-input--mono', style: 'width:220px',
  });
  const saveBtn   = h('button', { cls: 'btn aap-btn aap-btn--sm aap-btn-primary', text: 'Save',   type: 'button' });
  const cancelBtn = h('button', { cls: 'btn aap-btn aap-btn--sm',                 text: 'Cancel', type: 'button' });
  const label     = h('div', { cls: 'aap-queue-edit-row__label', text: 'Reschedule · UTC' });
  const editRow   = h('div', { cls: 'aap-queue-edit-row' },
    h('div', {}, label, dtInput),
    saveBtn, cancelBtn);

  _activeQueueEditRow = editRow;
  dataRow.after(editRow);
  dtInput.focus();

  cancelBtn.addEventListener('click', () => {
    editRow.remove();
    if (_activeQueueEditRow === editRow) _activeQueueEditRow = null;
  });
  saveBtn.addEventListener('click', async () => {
    if (!dtInput.value) return;
    saveBtn.disabled = true;
    saveBtn.textContent = '…';
    try {
      await apiFetch('POST', '/api/posts/' + postId + '/schedule', { datetime_utc: dtInput.value + ':00Z' });
      showToast('Rescheduled', 'success');
      _activeQueueEditRow = null;
      await refreshQueue();
    } catch (e) {
      showToast(e.message, 'danger');
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save';
    }
  });
}

async function _openQueueEditPost(postId, seriesId, dataRow) {
  // Toggle: click again to close
  const formId = 'queue-post-edit-' + postId;
  const existing = document.getElementById(formId);
  if (existing) { existing.remove(); return; }
  // Close any open reschedule row
  if (_activeQueueEditRow) { _activeQueueEditRow.remove(); _activeQueueEditRow = null; }
  try {
    const [post, series] = await Promise.all([
      apiFetch('GET', '/api/posts/' + postId),
      apiFetch('GET', '/api/series/' + seriesId),
    ]);
    const imgMap = {};
    (series.images || []).forEach(i => { if (!i.deleted_at) imgMap[i.id] = i.public_url; });
    const form = buildEditPostForm(
      post, imgMap, series,
      () => document.getElementById(formId)?.remove(),
      () => refreshQueue(),
    );
    form.id = formId;
    dataRow.after(form);
  } catch (e) { showToast(e.message, 'danger'); }
}

async function refreshQueue() {
  const el = document.getElementById('queueContent');
  el.replaceChildren(h('div', { cls: 'text-center' }, h('div', { cls: 'spinner-border spinner-border-sm' })));
  try {
    const items = await apiFetch('GET', '/api/queue');
    const kicker = document.getElementById('queueKicker');
    if (kicker) kicker.textContent = items.length + ' post' + (items.length !== 1 ? 's' : '') + ' scheduled';
    if (!items.length) {
      el.replaceChildren(h('p', { cls: 'aap-panel-head__meta text-center', style: 'padding:2rem 0', text: 'No scheduled posts.' }));
      return;
    }
    const table = h('div', { cls: 'aap-table', style: '--cols: 180px 1fr 160px 120px 130px' });
    table.appendChild(h('div', { cls: 'aap-table__head' },
      h('span', { text: 'Series' }),
      h('span', { text: 'Title' }),
      h('span', { text: 'Datetime · UTC' }),
      h('span', { text: 'Platform' }),
      h('span', { text: 'Actions' })));
    items.forEach(item => {
      const platformPill = h('span', { cls: 'aap-platform-pill' },
        _platformIcon(item.platform),
        document.createTextNode(' ' + item.platform));
      const thumbEl = item.cover_url
        ? Object.assign(document.createElement('img'), {
            src: item.cover_url, className: 'aap-mini-thumb aap-mini-thumb--sm',
            style: 'object-fit:cover',
          })
        : h('span', { cls: 'aap-mini-thumb aap-mini-thumb--sm', style: '--thumb-color: hsl(210 30% 50%)' });
      const seriesCell = h('div', { cls: 'aap-queue-series' },
        thumbEl,
        h('button', { cls: 'aap-queue-series__name aap-queue-series__name--link', text: item.series_name || item.series_id.slice(0, 8), onclick: () => selectSeries(item.series_id) }));
      const dataRow = h('div', { cls: 'aap-table__row' },
        seriesCell,
        h('span', { cls: 'aap-queue-title', text: item.title }),
        h('span', { cls: 'aap-queue-when', text: formatDate(item.scheduled_at) }),
        platformPill,
        h('div', { cls: 'd-flex align-items-center gap-1' },
          (() => { const b = h('button', { cls: 'aap-icon-btn', title: 'Edit post', 'aria-label': 'Edit post' }, icon('bi bi-pencil')); b.addEventListener('click', () => _openQueueEditPost(item.post_id, item.series_id, dataRow)); return b; })(),
          (() => { const b = h('button', { cls: 'aap-icon-btn', title: 'Reschedule', 'aria-label': 'Reschedule' }, icon('bi bi-calendar-plus')); b.addEventListener('click', () => _openQueueEdit(item.post_id, item.scheduled_at, dataRow)); return b; })(),
          h('button', { cls: 'btn aap-btn aap-btn--sm aap-btn-danger', text: 'Cancel', onclick: () => cancelPostScheduleItem(item.post_id) })));
      table.appendChild(dataRow);
    });
    el.replaceChildren(table);
  } catch (e) {
    el.replaceChildren(h('p', { cls: 'text-danger', text: e.message }));
  }
}

async function cancelPostScheduleItem(postId) {
  showConfirm('Cancel this scheduled post?', async () => {
    try {
      await apiFetch('DELETE', '/api/posts/' + postId + '/schedule');
      showToast('Schedule cancelled', 'success');
      await refreshQueue();
    } catch (e) { showToast(e.message, 'danger'); }
  });
}

// ── Collections ───────────────────────────────────────────────────────────────
async function refreshCollections() {
  const el = document.getElementById('collectionsContent');
  if (!el) return;
  el.replaceChildren(h('div', { cls: 'text-center' }, h('div', { cls: 'spinner-border spinner-border-sm' })));
  try {
    App.collections = await apiFetch('GET', '/api/collections');
    _populateCollectionFilter();
    const kicker = document.getElementById('collectionsKicker');
    if (kicker) {
      const total = App.collections.reduce((s, c) => s + (c.series_total || 0), 0);
      kicker.textContent = App.collections.length + ' collection' + (App.collections.length !== 1 ? 's' : '')
        + (total ? ' · ' + total + ' series' : '');
    }
    if (!App.collections.length) {
      el.replaceChildren(h('p', { cls: 'aap-panel-head__meta text-center', style: 'padding:2rem 0', text: 'No collections yet.' }));
      return;
    }
    const list = h('div', { cls: 'd-flex flex-column gap-2' });
    App.collections.forEach(c => list.appendChild(_buildCollectionItem(c)));
    el.replaceChildren(list);
  } catch (e) {
    el.replaceChildren(h('p', { cls: 'text-danger', text: e.message }));
  }
}

function _populateCollectionFilter() {
  const btn  = document.getElementById('collectionFilterBtn');
  const menu = document.getElementById('collectionFilterMenu');
  if (!btn || !menu) return;

  menu.replaceChildren();

  const allLink = h('a', { cls: 'dropdown-item small' + (App.activeCollection ? '' : ' active'), href: '#', text: 'All collections' });
  allLink.addEventListener('click', e => {
    e.preventDefault();
    onCollectionFilterChange('');
    btn.textContent = 'All collections';
    menu.classList.remove('show');
  });
  menu.appendChild(h('li', null, allLink));

  (App.collections || []).forEach(c => {
    const link = h('a', { cls: 'dropdown-item small py-1' + (App.activeCollection === c.id ? ' active' : ''), href: '#', style: 'line-height:1.3' });
    link.appendChild(document.createTextNode(c.name));
    if (c.name_ru) link.appendChild(h('span', { cls: 'text-muted d-block', style: 'font-size:11px', text: c.name_ru }));
    link.addEventListener('click', e => {
      e.preventDefault();
      onCollectionFilterChange(c.id);
      btn.textContent = c.name;
      menu.classList.remove('show');
    });
    menu.appendChild(h('li', null, link));
  });

  // Update button label to reflect current active collection
  const active = (App.collections || []).find(c => c.id === App.activeCollection);
  btn.textContent = active ? active.name : 'All collections';
}

function onCollectionFilterChange(val) {
  App.activeCollection = val || null;
  loadSeries(true);
  _pushState();
}

function _buildCollectionItem(c) {
  const countParts = [];
  if (c.series_total > 0) {
    const byStatus = c.series_by_status || {};
    const statusParts = Object.entries(byStatus)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([s, n]) => n + ' ' + s);
    countParts.push(c.series_total + ' series' + (statusParts.length ? ': ' + statusParts.join(' · ') : ''));
  } else {
    countParts.push('0 series');
  }
  const countText = countParts[0];

  const filterBtn = h('button', { cls: 'aap-icon-btn--row', title: 'Filter series by this collection', 'aria-label': 'Filter series by this collection', style: '--btn-color: var(--aap-accent)' });
  filterBtn.appendChild(icon('bi bi-funnel'));
  filterBtn.addEventListener('click', () => {
    App.activeCollection = c.id;
    _populateCollectionFilter();
    showView('list');
    loadSeries(true);
  });

  const delBtn = h('button', { cls: 'aap-icon-btn--row', title: 'Delete collection', style: '--btn-color: var(--aap-danger)' });
  delBtn.appendChild(icon('bi bi-trash'));
  delBtn.addEventListener('click', () => showConfirm('Delete collection "' + c.name + '"? Series will be unassigned.', async () => {
    try {
      await apiFetch('DELETE', '/api/collections/' + c.id);
      showToast('Deleted', 'success');
      if (App.activeCollection === c.id) { App.activeCollection = null; loadSeries(true); }
      await refreshCollections();
    } catch (e) { showToast(e.message, 'danger'); }
  }));

  const row = h('article', { cls: 'aap-collection-row' });

  function renderView() {
    row.classList.remove('is-editing');
    const editBtn = h('button', { cls: 'aap-icon-btn--row', title: 'Edit' });
    editBtn.appendChild(icon('bi bi-pencil'));
    editBtn.addEventListener('click', renderEdit);
    row.replaceChildren(
      h('div', null,
        h('div', { cls: 'aap-collection-row__name-en', text: c.name }),
        c.name_ru ? h('div', { cls: 'aap-collection-row__name-ru', text: c.name_ru }) : null),
      h('div', { cls: 'aap-collection-row__counts', text: countText }),
      h('div'),
      h('div', { cls: 'aap-collection-row__actions' }, filterBtn, editBtn, delBtn));
  }

  function renderEdit() {
    row.classList.add('is-editing');
    const nameInput = h('input', { type: 'text', cls: 'form-control aap-input', 'aria-label': 'Name (EN)' });
    nameInput.value = c.name;
    const nameRuInput = h('input', { type: 'text', cls: 'form-control aap-input', 'aria-label': 'Name (RU)' });
    nameRuInput.value = c.name_ru || '';
    const saveBtn = h('button', { cls: 'btn aap-btn aap-btn-primary', type: 'button', style: 'padding:6px 12px;font-size:12px' });
    saveBtn.textContent = 'Save';
    saveBtn.addEventListener('click', async () => {
      try {
        await apiFetch('PATCH', '/api/collections/' + c.id, { name: nameInput.value.trim(), name_ru: nameRuInput.value.trim() || null });
        showToast('Saved', 'success');
        await refreshCollections();
      } catch (e) { showToast(e.message, 'danger'); }
    });
    const cancelBtn = h('button', { cls: 'aap-icon-btn--row', title: 'Cancel' });
    cancelBtn.appendChild(icon('bi bi-x-lg'));
    cancelBtn.addEventListener('click', renderView);
    row.replaceChildren(
      nameInput, nameRuInput, saveBtn,
      h('div', { cls: 'aap-collection-row__edit-meta', text: countText }),
      h('div', { cls: 'aap-collection-row__actions' }, filterBtn, cancelBtn, delBtn));
  }

  renderView();
  return row;
}

async function createCollection() {
  const input = document.getElementById('newCollectionName');
  const inputRu = document.getElementById('newCollectionNameRu');
  if (!input) return;
  const name = input.value.trim();
  if (!name) { showToast('Enter a collection name', 'danger'); return; }
  const name_ru = inputRu?.value.trim() || null;
  try {
    await apiFetch('POST', '/api/collections', { name, name_ru });
    input.value = '';
    if (inputRu) inputRu.value = '';
    showToast('Collection created', 'success');
    await refreshCollections();
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Trash ─────────────────────────────────────────────────────────────────────
function _disableWithSpinner(btn) {
  btn.disabled = true;
  btn.replaceChildren(h('span', { cls: 'spinner-border spinner-border-sm' }));
}

async function refreshTrash() {
  const content = document.getElementById('trashContent');
  const emptyBtn = document.getElementById('emptyTrashBtn');
  content.replaceChildren(h('div', { cls: 'text-muted text-center py-4', text: 'Loading…' }));
  try {
    const data = await apiFetch('GET', '/api/trash');
    const isEmpty = !data.series.length && !data.images.length;
    emptyBtn.classList.toggle('d-none', isEmpty);
    emptyBtn.onclick = () => showConfirm('Permanently delete everything in Trash?', async () => {
      const progressContainer = document.getElementById('trashProgressContainer');
      const progressBar = document.getElementById('trashProgressBar');
      const progressLabel = document.getElementById('trashProgressLabel');
      const progressCount = document.getElementById('trashProgressCount');
      const items = [
        ...data.series.map(s => ({ type: 'series', id: s.id, label: s.title || s.original_folder_name || s.id.slice(0, 8) })),
        ...data.images.map(i => ({ type: 'images', id: i.id, label: i.original_filename })),
      ];
      const total = items.length;
      _disableWithSpinner(emptyBtn);
      progressBar.style.width = '0%';
      progressContainer.classList.remove('d-none');
      let done = 0, failed = 0;
      for (const item of items) {
        progressLabel.textContent = item.label;
        progressCount.textContent = (done + 1) + ' / ' + total;
        try {
          await apiFetch('DELETE', '/api/trash/' + item.type + '/' + item.id);
        } catch (_) { failed++; }
        done++;
        const pct = Math.round(done / total * 100);
        progressBar.style.width = pct + '%';
        progressBar.setAttribute('aria-valuenow', pct);
      }
      progressContainer.classList.add('d-none');
      if (failed) showToast(failed + ' item(s) failed to delete', 'danger');
      else showToast('Trash emptied', 'success');
      refreshTrash();
    });
    const kicker = document.getElementById('trashKicker');
    if (kicker) {
      const parts = [];
      if (data.images.length) parts.push(data.images.length + ' image' + (data.images.length !== 1 ? 's' : ''));
      if (data.series.length) parts.push(data.series.length + ' series');
      parts.push('auto-purged after 30 days');
      kicker.textContent = parts.join(' · ');
    }
    if (isEmpty) {
      content.replaceChildren(h('p', { cls: 'text-muted text-center py-4', text: 'Trash is empty' }));
      return;
    }
    const nodes = [];
    if (data.images.length) {
      nodes.push(h('h2', { cls: 'aap-section-label', text: 'Deleted images · ' + data.images.length }));
      data.images.forEach(i => nodes.push(_buildTrashImageItem(i)));
    }
    if (data.series.length) {
      nodes.push(h('h2', { cls: 'aap-section-label' + (data.images.length ? ' mt-4' : ''), text: 'Deleted series · ' + data.series.length }));
      data.series.forEach(s => nodes.push(_buildTrashSeriesItem(s)));
    }
    content.replaceChildren(...nodes);
  } catch (e) {
    content.replaceChildren(h('p', { cls: 'text-danger', text: e.message }));
  }
}

function _buildTrashSeriesItem(s) {
  const restoreBtn = h('button', { cls: 'btn aap-btn aap-btn--sm aap-btn-success' });
  restoreBtn.appendChild(icon('bi bi-arrow-counterclockwise'));
  restoreBtn.appendChild(document.createTextNode(' Restore'));
  restoreBtn.addEventListener('click', async () => {
    _disableWithSpinner(restoreBtn);
    try {
      await apiFetch('POST', '/api/trash/series/' + s.id + '/restore');
      showToast('Series restored', 'success');
      loadSeries(true);
    } catch (e) { showToast(e.message, 'danger'); }
    refreshTrash();
  });
  const delBtn = h('button', { cls: 'btn aap-btn aap-btn--sm aap-btn-danger' });
  delBtn.appendChild(icon('bi bi-trash'));
  delBtn.appendChild(document.createTextNode(' Delete'));
  delBtn.addEventListener('click', () => showConfirm(
    'Permanently delete this series and all its images?',
    async () => {
      _disableWithSpinner(delBtn);
      try {
        await apiFetch('DELETE', '/api/trash/series/' + s.id);
        showToast('Permanently deleted', 'success');
      } catch (e) { showToast(e.message, 'danger'); }
      refreshTrash();
    }
  ));
  const title = s.title || s.original_folder_name || s.id.slice(0, 8);
  const thumb = s.cover_url
    ? Object.assign(document.createElement('img'), {
        src: s.cover_url, className: 'aap-mini-thumb',
        style: 'object-fit:cover',
      })
    : h('span', { cls: 'aap-mini-thumb' });
  return h('article', { cls: 'aap-trash-row' },
    thumb,
    h('div', { cls: 'min-w-0' },
      h('div', { cls: 'aap-trash-row__title', text: title }),
      h('div', { cls: 'aap-trash-row__meta', text: s.image_count + ' images · deleted ' + _timeAgo(s.deleted_at) })),
    h('div', { cls: 'aap-trash-row__actions' }, restoreBtn, delBtn));
}

function _buildTrashImageItem(i) {
  const restoreBtn = h('button', { cls: 'btn aap-btn aap-btn--sm aap-btn-success' });
  restoreBtn.appendChild(icon('bi bi-arrow-counterclockwise'));
  restoreBtn.appendChild(document.createTextNode(' Restore'));
  restoreBtn.addEventListener('click', async () => {
    _disableWithSpinner(restoreBtn);
    try {
      await apiFetch('POST', '/api/trash/images/' + i.id + '/restore');
      showToast('Image restored', 'success');
      if (App.currentSeriesId === i.series_id) loadSeriesDetail(i.series_id);
    } catch (e) { showToast(e.message, 'danger'); }
    refreshTrash();
  });
  const delBtn = h('button', { cls: 'btn aap-btn aap-btn--sm aap-btn-danger' });
  delBtn.appendChild(icon('bi bi-trash'));
  delBtn.appendChild(document.createTextNode(' Delete'));
  delBtn.addEventListener('click', () => showConfirm('Permanently delete this image?', async () => {
    _disableWithSpinner(delBtn);
    try {
      await apiFetch('DELETE', '/api/trash/images/' + i.id);
      showToast('Permanently deleted', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
    refreshTrash();
  }));
  const thumb = Object.assign(document.createElement('img'), {
    src: i.public_url, className: 'aap-mini-thumb',
    style: 'object-fit:cover',
  });
  return h('article', { cls: 'aap-trash-row' },
    thumb,
    h('div', { cls: 'min-w-0' },
      h('div', { cls: 'aap-trash-row__title', text: i.original_filename }),
      h('div', { cls: 'aap-trash-row__meta' },
        document.createTextNode('from '),
        h('span', { cls: 'aap-mono', text: i.series_title }),
        document.createTextNode(' · deleted ' + _timeAgo(i.deleted_at)))),
    h('div', { cls: 'aap-trash-row__actions' }, restoreBtn, delBtn));
}
function _timeAgo(iso) {
  const secs = Math.floor((Date.now() - new Date(iso + 'Z')) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return Math.floor(secs / 60) + 'm ago';
  if (secs < 86400) return Math.floor(secs / 3600) + 'h ago';
  return Math.floor(secs / 86400) + 'd ago';
}

// ── Draft helpers ─────────────────────────────────────────────────────────────
function getDraftEdits() {
  return {
    title:   document.getElementById('editorTitle')?.value,
    desc_en: document.getElementById('f_desc_en')?.value,
    desc_ru: document.getElementById('f_desc_ru')?.value,
    tags_ig: document.getElementById('f_tags_ig')?.value,
    tags_tg: document.getElementById('f_tags_tg')?.value,
  };
}

// ── URL state ─────────────────────────────────────────────────────────────────
const _DEFAULT_STATUSES = 'approved,draft,new';

function _seriesUrlLabel() {
  const s = App.currentSeries;
  return (s && (s.name || s.title)) || null;
}

function _pushState() {
  const statusStr = [...App.activeStatuses].sort().join(',');
  const label = _seriesUrlLabel();
  const p = new URLSearchParams();
  if (App.currentView && App.currentView !== 'editor') p.set('view', App.currentView);
  if (App.currentSeriesId) p.set('series', label || App.currentSeriesId);
  if (statusStr !== _DEFAULT_STATUSES) p.set('status', statusStr);
  if (App.search) p.set('q', App.search);
  if (App.activeCollection) {
    const _ac = (App.collections || []).find(c => c.id === App.activeCollection);
    p.set('collection', _ac ? _ac.name : App.activeCollection);
  }
  if (App.limit !== 15) p.set('limit', String(App.limit));
  const url = p.toString() ? '?' + p.toString() : location.pathname;
  history.pushState({
    view: App.currentView, series: App.currentSeriesId,
    status: statusStr, q: App.search,
    collection: App.activeCollection, limit: App.limit,
  }, '', url);
}

async function _resolveCollectionParam(param) {
  if (!param) return null;
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(param)) return param;
  const norm = param.toLowerCase();
  let found = (App.collections || []).find(c => (c.name || '').toLowerCase() === norm);
  if (found) return found.id;
  try {
    const data = await apiFetch('GET', '/api/collections');
    App.collections = data;
    _populateCollectionFilter();
    found = data.find(c => (c.name || '').toLowerCase() === norm);
    return found?.id || null;
  } catch { return null; }
}

async function _resolveSeriesParam(param) {
  if (!param) return null;
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(param)) return param;
  const norm = param.toLowerCase();
  const inPage = App.series.find(s => (s.name || s.title || '').toLowerCase() === norm);
  if (inPage) return inPage.id;
  try {
    const data = await apiFetch('GET', '/api/series?search=' + encodeURIComponent(param) + '&limit=5&status=new,draft,approved,posted,skip');
    const match = (data.items || []).find(s => (s.name || s.title || '').toLowerCase() === norm);
    return match?.id || null;
  } catch { return null; }
}

function _syncFiltersFromState(status, q, collection, limit) {
  if (status) App.activeStatuses = new Set(status.split(','));
  App.search = q || '';
  App.activeCollection = collection || null;
  App.limit = limit || 15;
  document.querySelectorAll('.aap-chip[data-status-group]').forEach(chip => {
    const dbVals = STATUS_DISPLAY_GROUPS[chip.dataset.statusGroup] || [];
    const active = dbVals.some(v => App.activeStatuses.has(v));
    chip.classList.toggle('is-active', active);
  });
  document.getElementById('limitSel').value = String(App.limit);
  const searchEl = document.getElementById('seriesSearch');
  if (searchEl) searchEl.value = App.search;
  if (App.collections.length) _populateCollectionFilter();
}

async function _restoreFromUrl() {
  const p = new URLSearchParams(location.search);
  const view = p.get('view') || 'editor';
  const seriesParam = p.get('series') || null;
  const _collId = await _resolveCollectionParam(p.get('collection'));
  _syncFiltersFromState(p.get('status'), p.get('q'), _collId, parseInt(p.get('limit')) || null);

  showView(view, { push: false });
  await loadSeries(true);
  if (seriesParam && view === 'editor') {
    const seriesId = await _resolveSeriesParam(seriesParam);
    if (seriesId) await selectSeries(seriesId, { push: false });
  }

  _pushState();
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  localStorage.setItem('aap-theme', next);
  document.documentElement.setAttribute('data-theme', next);
  document.documentElement.setAttribute('data-bs-theme', next);
  const icon = document.getElementById('aap-theme-icon');
  if (icon) icon.textContent = next === 'dark' ? '☀' : '☾';
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  localStorage.setItem('aap-theme', next);
  document.documentElement.setAttribute('data-theme', next);
  document.documentElement.setAttribute('data-bs-theme', next);
  const icon = document.getElementById('aap-theme-icon');
  if (icon) icon.textContent = next === 'dark' ? '☀' : '☾';
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  apiFetch('GET', '/api/settings/providers').then(d => { PROVIDER_MODELS = d; }).catch(() => {});
  apiFetch('GET', '/api/collections').then(data => { App.collections = data; _populateCollectionFilter(); }).catch(() => {});
  initLightbox();

  const collFilterBtn  = document.getElementById('collectionFilterBtn');
  const collFilterMenu = document.getElementById('collectionFilterMenu');
  collFilterBtn.addEventListener('click', e => {
    e.stopPropagation();
    const open = collFilterMenu.classList.contains('show');
    if (!open) {
      const r = collFilterBtn.getBoundingClientRect();
      collFilterMenu.style.position = 'fixed';
      collFilterMenu.style.top  = r.bottom + 'px';
      collFilterMenu.style.left = r.left + 'px';
      collFilterMenu.style.right = 'auto';
    }
    collFilterMenu.classList.toggle('show');
  });
  document.addEventListener('click', () => collFilterMenu.classList.remove('show'));

  document.getElementById('limitSel').addEventListener('change', function () {
    App.limit = +this.value;
    loadSeries(true);
    _pushState();
  });

  window.addEventListener('popstate', async (e) => {
    const s = e.state;
    if (!s) return;
    _syncFiltersFromState(s.status, s.q, s.collection, s.limit);
    showView(s.view || 'editor', { push: false });
    await loadSeries(true);
    if (s.series && (s.view === 'editor' || !s.view)) await selectSeries(s.series, { push: false });
  });

  setInterval(() => {
    if (!App.currentSeriesId) return;
    const d = getDraftEdits();
    if (d.desc_en || d.desc_ru || d.title)
      localStorage.setItem('draft_' + App.currentSeriesId, JSON.stringify(d));
  }, 30000);

  await _restoreFromUrl();
});
