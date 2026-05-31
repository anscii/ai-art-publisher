// ── Sending poller ────────────────────────────────────────────────────────────
// Polls loadSeriesDetail every 3 s while any post has status="sending".
// Clears itself when all posts settle (posted/failed) or user navigates away.
let _sendingPollerId = null;
function _startSendingPoller(seriesId, { watchedPostIds = new Set() } = {}) {
  if (_sendingPollerId) clearInterval(_sendingPollerId);
  const notified = new Set();
  // Snapshot settled items so only new transitions toast.
  // watchedPostIds are never pre-populated — they're the posts we just kicked off
  // and must toast even if the background task completes before the first poll.
  (App.currentSeries?.posts || []).filter(p => !p.deleted_at).forEach(p => {
    if (p.status !== 'sending' && !watchedPostIds.has(p.id)) notified.add(p.id);
    if (p.story_status && p.story_status !== 'publishing') notified.add('story:' + p.id);
  });
  _sendingPollerId = setInterval(async () => {
    if (App.currentSeriesId !== seriesId) {
      clearInterval(_sendingPollerId); _sendingPollerId = null; return;
    }
    await loadSeriesDetail(seriesId, { silent: true });
    const posts = (App.currentSeries?.posts || []).filter(p => !p.deleted_at);
    const hasActivity = posts.some(p => p.status === 'sending' || p.story_status === 'publishing');
    if (!hasActivity) {
      posts
        .filter(p => !notified.has(p.id) && (p.status === 'posted' || p.status === 'failed'))
        .forEach(p => {
          notified.add(p.id);
          showToast(
            p.status === 'posted'
              ? 'Posted to ' + p.platform
              : 'Failed: ' + (p.error_message || p.platform),
            p.status === 'posted' ? 'success' : 'danger'
          );
        });
      posts
        .filter(p => !notified.has('story:' + p.id) && p.story_status && p.story_status !== 'publishing')
        .forEach(p => {
          notified.add('story:' + p.id);
          const n = p.story_frame_count ?? '';
          const frames = n ? ' (' + n + ' frame' + (n === 1 ? '' : 's') + ')' : '';
          const platforms = 'Instagram' + (p.story_facebook_posted ? ' + Facebook' : '');
          showToast(
            p.story_status === 'posted'
              ? 'Story published to ' + platforms + frames
              : 'Story failed: ' + (p.story_error_message || 'unknown error'),
            p.story_status === 'posted' ? 'success' : 'danger'
          );
        });
      clearInterval(_sendingPollerId); _sendingPollerId = null;
    }
  }, 3000);
}

// ── Textarea auto-grow ────────────────────────────────────────────────────────
function _autoGrow(el) {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}
function _autoGrowDescTextareas() {
  _autoGrow(document.getElementById('f_desc_en'));
  _autoGrow(document.getElementById('f_desc_ru'));
}

// ── Generate card error UI ────────────────────────────────────────────────────
function _updateGenErrorUI() {
  const errorDiv  = document.getElementById('genError');
  const logBadge  = document.getElementById('genErrorBadge');
  const logList   = document.getElementById('genErrorList');
  const all       = ErrorService.getAll();
  const latestGen = all.find(e => e.context === 'generate');

  if (errorDiv) {
    const show = latestGen && !ErrorService.isCleared('generate');
    errorDiv.classList.toggle('d-none', !show);
    if (show) errorDiv.textContent = latestGen.message;
  }
  if (logBadge) {
    logBadge.classList.toggle('d-none', all.length === 0);
    if (all.length > 0) logBadge.textContent = `⚠ ${all.length}`;
  }
  if (logList) {
    logList.replaceChildren(...all.map(e => {
      const time = e.ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const li = h('li', { cls: 'list-group-item list-group-item-danger small py-1 px-2' });
      li.appendChild(h('span', { cls: 'fw-bold me-2', text: time }));
      li.appendChild(h('span', { cls: 'badge bg-secondary me-1', text: e.context }));
      li.appendChild(document.createTextNode(e.message));
      return li;
    }));
  }
}
ErrorService.subscribe(_updateGenErrorUI);

// ── Selection state ───────────────────────────────────────────────────────────
let _selectedImages = new Set();

// Single document-level listener for closing the collection picker panel.
// Stored here so it is added once and never accumulates.
let _activeCollPickerHide = null;
let _pinterestBoardsCache = null;
document.addEventListener('click', () => { if (_activeCollPickerHide) _activeCollPickerHide(); });

function _debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

function _updateSaveDescBtn() {
  const btn = document.getElementById('saveDescBtn');
  if (!btn || !App.currentSeries) return;
  const s = App.currentSeries;
  const dirty =
    (document.getElementById('editorTitle')?.value?.trim() ?? '') !== (s.name ?? '') ||
    (document.getElementById('f_pub_title')?.value?.trim() ?? '') !== (s.title ?? '') ||
    (document.getElementById('f_pub_title_ru')?.value?.trim() ?? '') !== (s.title_ru ?? '') ||
    (document.getElementById('f_desc_en')?.value ?? '') !== (s.description_en ?? '') ||
    (document.getElementById('f_desc_ru')?.value ?? '') !== (s.description_ru ?? '') ||
    (document.getElementById('f_tags_ig')?.value?.trim() ?? '') !== (s.tags_instagram ?? []).join(' ') ||
    (document.getElementById('f_tags_tg')?.value?.trim() ?? '') !== (s.tags_telegram ?? []).join(' ') ||
    (App.activeVariantId != null && App.activeVariantId !== (s.chosen_variant_id ?? null));
  btn.classList.toggle('btn-primary', dirty);
  btn.classList.toggle('btn-outline-primary', !dirty);
}


function _updateSaveDescBtn() {
  const btn = document.getElementById('saveDescBtn');
  if (!btn || !App.currentSeries) return;
  const s = App.currentSeries;
  const dirty =
    (document.getElementById('editorTitle')?.value?.trim() ?? '') !== (s.name ?? '') ||
    (document.getElementById('f_pub_title')?.value?.trim() ?? '') !== (s.title ?? '') ||
    (document.getElementById('f_pub_title_ru')?.value?.trim() ?? '') !== (s.title_ru ?? '') ||
    (document.getElementById('f_desc_en')?.value ?? '') !== (s.description_en ?? '') ||
    (document.getElementById('f_desc_ru')?.value ?? '') !== (s.description_ru ?? '') ||
    (document.getElementById('f_tags_ig')?.value?.trim() ?? '') !== (s.tags_instagram ?? []).join(' ') ||
    (document.getElementById('f_tags_tg')?.value?.trim() ?? '') !== (s.tags_telegram ?? []).join(' ') ||
    (App.activeVariantId != null && App.activeVariantId !== (s.chosen_variant_id ?? null));
  btn.classList.toggle('btn-primary', dirty);
  btn.classList.toggle('btn-outline-primary', !dirty);
}


// ── Editor entry point ────────────────────────────────────────────────────────
function renderEditor(series) {
  _selectedImages = new Set(series.images.filter(i => i.status === 'queued').map(i => i.id));
  App.activeVariantId = series.chosen_variant_id || null;

  const slug = series.original_folder_name || String(series.id).slice(0, 12);
  const displayStatus = statusDisplay(series.status);
  const dotVar = 'var(--aap-dot-' + displayStatus + ')';

  const topbar = h('header', { cls: 'aap-editor-topbar' },
    h('button', {
      cls: 'aap-icon-btn',
      type: 'button',
      title: 'Back to list',
      onclick: () => showView('list'),
    }, '←'),
    h('div', { cls: 'aap-editor-topbar__slug', text: slug }),
    h('div', { style: 'flex:1' }),
    h('span', { cls: 'aap-save-indicator' },
      h('span', { cls: 'aap-dot aap-dot--' + displayStatus }),
      document.createTextNode(' auto-saved')
    )
  );

  const titleInput = h('input', {
    type: 'text',
    cls: 'aap-title',
    id: 'editorTitle',
    placeholder: 'Series title…',
    'aria-label': 'Series title',
  });
  titleInput.value = series.name || series.title || '';
  titleInput.addEventListener('blur', () => saveTitle(series.id));
  titleInput.addEventListener('input', _updateSaveDescBtn);

  const collPicker = buildCollectionPicker(series);
  const imageCount = (series.images || []).filter(i => !i.deleted_at).length;
  const selCount = _selectedImages.size;
  const countMeta = h('span', {
    cls: 'aap-mono',
    style: 'font-size:11px;color:var(--aap-ink-mute)',
    text: '· ' + imageCount + ' images' + (selCount > 0 ? ' · ' + selCount + ' selected' : ''),
  });

  const titleBlock = h('section', { cls: 'aap-title-block' },
    h('div', { cls: 'aap-title-block__meta' },
      h('span', { cls: 'aap-dot aap-dot--' + displayStatus, style: 'width:8px;height:8px' }),
      h('span', {
        cls: 'aap-status-label',
        style: '--status-color:' + dotVar,
        text: displayStatus,
      }),
      collPicker,
      countMeta
    ),
    titleInput
  );

  document.getElementById('editorPanel').replaceChildren(
    topbar,
    titleBlock,
    buildStatusBar(series),
    buildImagesSection(series),
    buildActionBar(series.id),
    buildGenerateCard(series.id),
    buildDescriptionsCard(series),
    buildPostsCard(series),
  );

  initImageSortable(series.id);
  if (series.chosen_variant_id) {
    const chosen = (series.ai_variants || []).find(v => v.id === series.chosen_variant_id);
    const hintEl = document.getElementById('genHint');
    if (chosen && hintEl) hintEl.value = chosen.hint || '';
  }
  restoreDraft(series.id);
  _updateSaveDescBtn();
  _autoGrowDescTextareas();
}

async function saveTitle(seriesId) {
  const val = document.getElementById('editorTitle')?.value?.trim() ?? '';
  if (val === (App.currentSeries?.name ?? '')) return;
  try {
    const updated = await apiFetch('PUT', '/api/series/' + seriesId, { name: val });
    App.currentSeries = updated;
    updateSeriesItem(updated);
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Images section ───────────────────────────────────────────────────────────
function _selGridCols() {
  return window.matchMedia('(max-width: 600px)').matches ? 3 : 8;
}

function buildImagesSection(series) {
  const images = (series.images || []).filter(i => !i.deleted_at);
  const selected   = images.filter(i => _selectedImages.has(i.id));
  const unselected = images
    .filter(i => !_selectedImages.has(i.id))
    .sort((a, b) => (a.status === 'skip' ? 1 : 0) - (b.status === 'skip' ? 1 : 0));

  const selGrid = h('div', { cls: 'aap-thumb-grid', id: 'selectedTray' });
  selected.forEach((img, idx) =>
    selGrid.appendChild(buildThumb(img, series.id, idx + 1)));
  const cols = _selGridCols();
  const rem = selected.length % cols;
  const slots = rem > 0 ? cols - rem : cols;
  for (let i = 0; i < slots; i++) {
    selGrid.appendChild(h('div', { cls: 'aap-thumb-slot' }, '+'));
  }

  const libGrid = h('div', { cls: 'aap-thumb-grid mt-3', id: 'libraryGrid' });
  unselected.forEach((img, idx) =>
    libGrid.appendChild(buildThumb(img, series.id, selected.length + idx + 1)));

  const addBtn = h('button', { cls: 'btn aap-btn', style: 'font-size:12px' },
    icon('bi bi-plus me-1'), document.createTextNode('Add images'));
  addBtn.addEventListener('click', () => addImages(series.id));

  const selAllBtn = h('button', { cls: 'btn aap-btn', title: 'Select all', 'aria-label': 'Select all' },
    icon('bi bi-check2-all me-1'), document.createTextNode('All'));
  selAllBtn.addEventListener('click', () => _selectAll(series.id));

  const deselBtn = h('button', { cls: 'btn aap-btn', title: 'Deselect all', 'aria-label': 'Deselect all' },
    icon('bi bi-x-circle me-1'), document.createTextNode('None'));
  deselBtn.addEventListener('click', () => _deselectAll(series.id));

  return h('section', { cls: 'px-4 pt-4 pb-2' },
    h('div', { cls: 'aap-panel-head' },
      h('span', { cls: 'aap-panel-head__label aap-panel-head__label--accent',
        text: '\u2191 In this post \u00b7 story order' }),
      h('span', { cls: 'aap-panel-head__meta', text: 'drag to reorder' })
    ),
    h('div', { cls: 'aap-selected-tray mt-2' }, selGrid),
    h('div', { cls: 'aap-panel-head mt-4' },
      h('span', { cls: 'aap-panel-head__label aap-panel-head__label--mute',
        id: 'imagesCardLabel',
        text: 'Library \u00b7 ' + unselected.length + ' unselected' }),
      h('span', { cls: 'aap-panel-head__rule' }),
      h('div', { cls: 'd-flex gap-2' }, selAllBtn, deselBtn, addBtn)
    ),
    libGrid
  );
}

function _refreshImagesHeader(total) {
  const el = document.getElementById('imagesCardLabel');
  if (!el) return;
  el.textContent = 'Library \u00b7 ' + (total - _selectedImages.size) + ' unselected';
}

function buildThumb(img, seriesId, orderNum) {
  const isSelected = _selectedImages.has(img.id);
  const isPosted   = img.status === 'posted';
  const isSkipped  = img.status === 'skip';
  const hue = [...img.id].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;

  let cls = 'aap-thumb';
  if (isSelected) cls += ' is-selected';
  if (isPosted)   cls += ' is-posted';
  if (isSkipped)  cls += ' is-skipped';

  const thumb = h('div', {
    cls,
    'data-image-id': img.id,
    'data-image-status': img.status,
    style: '--thumb-color: hsl(' + hue + ' 35% 40%)',
  });
  thumb.style.position = 'relative';

  if (img.public_url) {
    const imgEl = document.createElement('img');
    imgEl.setAttribute('src', img.public_url);
    imgEl.style.cssText = 'width:100%;height:100%;object-fit:cover;position:absolute;inset:0;border-radius:inherit;cursor:zoom-in';
    imgEl.loading = 'lazy';
    imgEl.setAttribute('draggable', 'false');
    imgEl.addEventListener('click', e => {
      e.stopPropagation();
      const allImgs = _getAllThumbImages();
      openLightbox(allImgs, allImgs.findIndex(im => im.id === img.id));
    });
    thumb.appendChild(imgEl);
  }

  if (orderNum != null) {
    thumb.appendChild(h('span', { cls: 'aap-thumb__order' },
      String(orderNum).padStart(2, '0')));
  }
  if (isPosted) {
    thumb.appendChild(h('span', { cls: 'aap-thumb__posted-tag', text: 'POSTED' }));
  }
  if (isSkipped) {
    thumb.appendChild(h('span', { cls: 'aap-thumb__overlay-label', text: 'SKIPPED' }));
  }
  thumb.appendChild(h('span', { cls: 'aap-thumb__drag', text: '\u22ee\u22ee' }));

  const statusBtn = h('button', {
    cls: 'btn btn-xs position-absolute top-0 start-0 m-1 p-0 border-0 bg-transparent',
    style: 'line-height:1;width:22px;height:22px;z-index:2',
    'data-select-btn': img.id,
    'aria-label': isSelected ? 'Deselect image' : 'Select image',
    'aria-pressed': String(isSelected),
  });
  statusBtn.appendChild(icon(_selectIcon(img.id, img.status)));
  statusBtn.addEventListener('click', e => {
    e.stopPropagation();
    _toggleSelection(img.id, img.status, seriesId);
  });
  thumb.appendChild(statusBtn);

  const menuBtn = h('button', {
    cls: 'btn btn-xs btn-dark opacity-75 position-absolute top-0 end-0 m-1',
    'aria-label': 'Image options',
  });
  menuBtn.appendChild(document.createTextNode('\u22ef'));
  menuBtn.setAttribute('data-bs-toggle', 'dropdown');
  menuBtn.addEventListener('click', e => e.stopPropagation());
  const dropItems = document.createElement('ul');
  dropItems.className = 'dropdown-menu dropdown-menu-end';
  const hdr2 = document.createElement('li');
  hdr2.appendChild(h('h6', { cls: 'dropdown-header', text: 'Move to' }));
  dropItems.appendChild(hdr2);
  buildMoveToItems(img.id, seriesId, false).forEach(li => dropItems.appendChild(li));
  const divLi = document.createElement('li');
  divLi.appendChild(h('hr', { cls: 'dropdown-divider' }));
  dropItems.appendChild(divLi);
  const delLi = document.createElement('li');
  const delA = h('a', { cls: 'dropdown-item small text-danger', href: '#' });
  delA.appendChild(icon('bi bi-trash me-1'));
  delA.appendChild(document.createTextNode('Delete'));
  delA.addEventListener('click', e => { e.preventDefault(); deleteImage(img.id); });
  delLi.appendChild(delA);
  dropItems.appendChild(delLi);
  thumb.appendChild(h('div', { cls: 'position-absolute top-0 end-0' },
    h('div', { cls: 'dropdown' }, menuBtn, dropItems)));

  return thumb;
}

function _getAllThumbImages() {
  const sel = [...document.querySelectorAll('#selectedTray [data-image-id]')];
  const lib = [...document.querySelectorAll('#libraryGrid [data-image-id]')];
  const imgById = Object.fromEntries(
    (App.currentSeries?.images ?? []).map(i => [i.id, i])
  );
  return [...sel, ...lib].map(el => imgById[el.dataset.imageId]).filter(Boolean);
}

function _selectIcon(imgId, status) {
  if (_selectedImages.has(imgId)) return 'bi bi-check-circle-fill text-primary fs-5';
  if (status === 'posted') return 'bi bi-check-circle-fill text-success fs-5';
  return 'bi bi-circle text-white fs-5';
}

function _toggleSelection(imgId, imgStatus, seriesId) {
  const isNowSelected = !_selectedImages.has(imgId);
  if (isNowSelected) _selectedImages.add(imgId); else _selectedImages.delete(imgId);
  const btn = document.querySelector('[data-select-btn="' + imgId + '"]');
  if (btn) {
    btn.replaceChildren(icon(_selectIcon(imgId, imgStatus)));
    btn.setAttribute('aria-pressed', String(isNowSelected));
    btn.setAttribute('aria-label', isNowSelected ? 'Deselect image' : 'Select image');
  }
  const thumb = document.querySelector('[data-image-id="' + imgId + '"]');
  if (thumb) thumb.classList.toggle('is-selected', isNowSelected);
  _resortStrip();
  const total = App.currentSeries?.images?.length ?? 0;
  _refreshImagesHeader(total);
  _refreshActionBar(seriesId);
  _lightboxSyncSelectBtn(imgId);
}

function _resortStrip() {
  const selGrid = document.getElementById('selectedTray');
  const libGrid = document.getElementById('libraryGrid');
  if (!selGrid || !libGrid) return;

  selGrid.querySelectorAll('.aap-thumb-slot').forEach(s => s.remove());
  const allThumbs = [
    ...selGrid.querySelectorAll('[data-image-id]'),
    ...libGrid.querySelectorAll('[data-image-id]'),
  ];
  if (!allThumbs.length) return;

  let selIdx = 1;
  allThumbs.forEach(el => {
    const id = el.dataset.imageId;
    if (_selectedImages.has(id)) {
      const badge = el.querySelector('.aap-thumb__order');
      if (badge) badge.textContent = String(selIdx).padStart(2, '0');
      selIdx++;
      el.classList.add('is-selected');
      selGrid.appendChild(el);
    } else {
      el.classList.remove('is-selected');
      libGrid.appendChild(el);
    }
  });

  const cols = _selGridCols();
  const cnt = selGrid.querySelectorAll('[data-image-id]').length;
  const rem = cnt % cols;
  const slotsNeeded = rem > 0 ? cols - rem : cols;
  for (let i = 0; i < slotsNeeded; i++) {
    selGrid.appendChild(h('div', { cls: 'aap-thumb-slot' }, '+'));
  }
}

function _syncSelectionUI(seriesId) {
  [
    ...document.querySelectorAll('#selectedTray [data-image-id]'),
    ...document.querySelectorAll('#libraryGrid [data-image-id]'),
  ].forEach(thumb => {
    const id = thumb.dataset.imageId, st = thumb.dataset.imageStatus || 'pending';
    thumb.classList.toggle('is-selected', _selectedImages.has(id));
    const btn = thumb.querySelector('[data-select-btn]');
    if (btn) btn.replaceChildren(icon(_selectIcon(id, st)));
  });
  _resortStrip();
  _refreshImagesHeader((App.currentSeries?.images ?? []).length);
  _refreshActionBar(seriesId);
}

function _selectAll(seriesId) {
  (App.currentSeries?.images ?? []).forEach(img => { if (!img.deleted_at) _selectedImages.add(img.id); });
  _syncSelectionUI(seriesId);
}

function _deselectAll(seriesId) {
  _selectedImages.clear();
  _syncSelectionUI(seriesId);
}

function _invertSelection(seriesId) {
  (App.currentSeries?.images ?? []).forEach(img => {
    if (img.deleted_at) return;
    if (_selectedImages.has(img.id)) _selectedImages.delete(img.id); else _selectedImages.add(img.id);
  });
  _syncSelectionUI(seriesId);
}

// ── Move to picker ────────────────────────────────────────────────────────────
// Returns <li> elements for the "Move to" section.
// bulk=false → moves just imageId; bulk=true → moves all _selectedImages
function buildMoveToItems(imageId, seriesId, bulk, afterMove = null) {
  const items = [];

  const mkItem = (label, iconCls, onClick) => {
    const li = document.createElement('li');
    const a = h('a', { cls: 'dropdown-item small', href: '#' });
    if (iconCls) a.appendChild(icon(iconCls + ' me-1'));
    a.appendChild(document.createTextNode(label));
    a.addEventListener('click', e => { e.preventDefault(); onClick(); });
    li.appendChild(a);
    return li;
  };

  // Unsorted — always pinned first
  items.push(mkItem('Unsorted', 'bi bi-folder', async () => {
    try {
      const s = await _getOrCacheUnsorted();
      const ids = bulk ? [..._selectedImages] : [imageId];
      if (await moveImages(ids, s.id, seriesId)) {
        if (afterMove) afterMove();
      }
    } catch (e) { showToast(e.message, 'danger'); }
  }));

  const activeStatuses = ['new', 'draft', 'approved'];
  const _isUnsorted = s => (s.name || s.title) === 'Unsorted' || (App.unsortedSeriesId && s.id === App.unsortedSeriesId);
  const active = App.series.filter(s => s.id !== seriesId && !_isUnsorted(s) && activeStatuses.includes(s.status));

  // Always show search/create input; ≤10 series → filter client-side, >10 → fetch API
  const li = document.createElement('li');
  li.className = 'px-2 py-1';
  const input = h('input', { type: 'text', cls: 'form-control form-control-sm', placeholder: 'Search or create series…' });
  input.setAttribute('autocomplete', 'off');
  const results = h('ul', { cls: 'list-unstyled mb-0 mt-1', style: 'max-height:160px;overflow-y:auto' });

  const renderRow = (s) => {
    const name = s.name || s.title || s.original_folder_name || s.id.slice(0, 8);
    const row = h('li', null, h('a', { cls: 'dropdown-item small', href: '#', text: name }));
    row.firstChild.addEventListener('click', async e => {
      e.preventDefault();
      const ids = bulk ? [..._selectedImages] : [imageId];
      if (await moveImages(ids, s.id, seriesId)) {
        if (afterMove) afterMove();
      }
    });
    return row;
  };

  const appendCreate = (query) => {
    const createRow = h('li', null, h('a', { cls: 'dropdown-item small text-primary', href: '#' }));
    createRow.firstChild.appendChild(icon('bi bi-plus me-1'));
    createRow.firstChild.appendChild(document.createTextNode('Create "' + query + '"'));
    createRow.firstChild.addEventListener('click', async e => {
      e.preventDefault();
      // Capture selection immediately — before any async call that might change state
      const ids = bulk ? [..._selectedImages] : [imageId];
      try {
        const newSeries = await apiFetch('POST', '/api/series', { name: query, title: query });
        App.series.push(newSeries);
        await Promise.all(ids.map(id => apiFetch('PUT', '/api/images/' + id + '/move', { target_series_id: newSeries.id })));
        _selectedImages.clear();
        // Update source series in sidebar, then open the new series
        const sourceUpdated = await apiFetch('GET', '/api/series/' + seriesId);
        updateSeriesItem(sourceUpdated);
        document.getElementById('seriesItems')?.prepend(buildSeriesItem(newSeries));
        await selectSeries(newSeries.id);
        updateSeriesItem(App.currentSeries);
        showToast(ids.length > 1 ? ids.length + ' images moved' : 'Image moved', 'success');
        if (afterMove) afterMove();
      } catch (err) { showToast(err.message, 'danger'); }
    });
    results.appendChild(createRow);
  };

  const renderResults = async (query) => {
    results.replaceChildren();
    if (App.total <= 10) {
      // client-side filter
      const filtered = query
        ? active.filter(s => (s.title || s.original_folder_name || '').toLowerCase().includes(query.toLowerCase()))
        : active;
      filtered.forEach(s => results.appendChild(renderRow(s)));
      if (query) {
        const exactMatch = active.some(s => (s.title || '').toLowerCase() === query.toLowerCase());
        if (!exactMatch) appendCreate(query);
      }
    } else {
      if (!query) return;
      try {
        const statusParam = activeStatuses.join(',');
        const data = await apiFetch('GET', '/api/series?search=' + encodeURIComponent(query) + '&status=' + statusParam + '&limit=10');
        const filtered = data.items.filter(s => s.id !== seriesId && !_isUnsorted(s));
        filtered.forEach(s => results.appendChild(renderRow(s)));
        const exactMatch = filtered.some(s => (s.name || s.title || '').toLowerCase() === query.toLowerCase());
        if (!exactMatch) appendCreate(query);
      } catch (e) { showToast(e.message, 'danger'); }
    }
  };

  // show all active series immediately (≤10 mode only)
  if (App.total <= 10) renderResults('');

  const debouncedSearch = _debounce(renderResults, 280);
  input.addEventListener('input', e => debouncedSearch(e.target.value.trim()));
  input.addEventListener('click', e => e.stopPropagation());
  li.appendChild(input);
  li.appendChild(results);
  items.push(li);

  return items;
}

async function _getOrCacheUnsorted() {
  if (!App.unsortedSeriesId) {
    const s = await apiFetch('GET', '/api/series/unsorted');
    App.unsortedSeriesId = s.id;
    return s;
  }
  return { id: App.unsortedSeriesId };
}

// ── Action bar ────────────────────────────────────────────────────────────────
function buildActionBar(seriesId) {
  const bar = h('div', { id: 'imageActionBar', cls: 'aap-action-bar mx-4' });
  if (_selectedImages.size === 0) { bar.style.display = 'none'; return bar; }

  bar.appendChild(h('span', { cls: 'aap-action-bar__count' },
    h('strong', {}, String(_selectedImages.size)),
    document.createTextNode(' selected')
  ));
  bar.appendChild(h('span', { cls: 'aap-divider-v' }));

  const moveBtn = h('button', { cls: 'btn aap-btn' },
    icon('bi bi-box-arrow-right me-1'), document.createTextNode('\u2197 Move to\u2026'));
  moveBtn.setAttribute('data-bs-toggle', 'dropdown');
  const moveDrop = document.createElement('ul');
  moveDrop.className = 'dropdown-menu';
  buildMoveToItems(null, seriesId, true).forEach(li => moveDrop.appendChild(li));
  bar.appendChild(h('div', { cls: 'dropdown' }, moveBtn, moveDrop));

  const statusMap = new Map((App.currentSeries?.images ?? []).map(i => [i.id, i.status]));
  const toSkip         = [..._selectedImages].filter(id => { const s = statusMap.get(id); return s && s !== 'skip' && s !== 'posted'; });
  const toUnskip       = [..._selectedImages].filter(id => statusMap.get(id) === 'skip');
  const toMarkPosted   = [..._selectedImages].filter(id => { const s = statusMap.get(id); return s && s !== 'skip' && s !== 'posted'; });
  const toUnmarkPosted = [..._selectedImages].filter(id => statusMap.get(id) === 'posted');

  const _mkAction = (label, ids, newStatus) => {
    const btn = h('button', { cls: 'btn aap-btn', text: label });
    btn.addEventListener('click', async () => {
      try {
        await Promise.all(ids.map(id => apiFetch('PATCH', '/api/images/' + id + '/status', { status: newStatus })));
        const updated = await apiFetch('GET', '/api/series/' + seriesId);
        App.currentSeries = updated;
        renderEditor(updated);
      } catch (e) { showToast(e.message, 'danger'); }
    });
    return btn;
  };

  if (toSkip.length > 0)         bar.appendChild(_mkAction('\u25cc Skip',         toSkip,         'skip'));
  if (toUnskip.length > 0)       bar.appendChild(_mkAction('\u21ba Unskip',       toUnskip,       'pending'));
  if (toMarkPosted.length > 0)   bar.appendChild(_mkAction('\u2713 Mark posted',  toMarkPosted,   'posted'));
  if (toUnmarkPosted.length > 0) bar.appendChild(_mkAction('\u21ba Unmark posted',toUnmarkPosted, 'pending'));

  const delBtn = h('button', { cls: 'btn aap-btn aap-btn-danger', text: '\u00d7 Delete' });
  delBtn.addEventListener('click', () => {
    showConfirm('Delete ' + _selectedImages.size + ' image(s)?', async () => {
      try {
        await Promise.all([..._selectedImages].map(id => apiFetch('DELETE', '/api/images/' + id)));
        const updated = await apiFetch('GET', '/api/series/' + seriesId);
        App.currentSeries = updated;
        renderEditor(updated);
        showToast('Moved to Trash', 'success');
      } catch (e) { showToast(e.message, 'danger'); }
    });
  });
  bar.appendChild(delBtn);
  bar.appendChild(h('div', { style: 'flex:1' }));

  const saveBtn = h('button', { cls: 'btn aap-btn aap-btn-primary', text: '\u21b3 Save' });
  saveBtn.addEventListener('click', async () => {
    try {
      const updated = await apiFetch('PUT', '/api/series/' + seriesId + '/queue', { image_ids: [..._selectedImages] });
      App.currentSeries = updated;
      updateSeriesItem(updated);
      showToast('Queue saved', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
  });
  bar.appendChild(saveBtn);
  return bar;
}

function _refreshActionBar(seriesId) {
  const old = document.getElementById('imageActionBar');
  if (!old) return;
  old.replaceWith(buildActionBar(seriesId));
}

let _sortable = null;
let _sortableLib = null;
let _lightboxImages = [];
let _lightboxIdx    = 0;
let _lightboxOpen   = false;

function initImageSortable(seriesId) {
  const grid = document.getElementById('selectedTray');
  const lib  = document.getElementById('libraryGrid');
  if (!grid) return;
  if (_sortable)    { _sortable.destroy();    _sortable    = null; }
  if (_sortableLib) { _sortableLib.destroy(); _sortableLib = null; }
  const touch = window.matchMedia('(pointer: coarse)').matches;
  const opts = (container) => ({
    animation: 150,
    ghostClass: 'sortable-ghost',
    filter: '.aap-thumb-slot',
    forceFallback: true,
    fallbackTolerance: 4,
    group: 'images',
    ...(touch ? { delay: 300, touchStartThreshold: 8 } : {}),
    onEnd: async (evt) => {
      if (evt.from !== evt.to) {
        const imgId = evt.item.dataset.imageId;
        if (imgId) {
          if (evt.to === grid) _selectedImages.add(imgId);
          else _selectedImages.delete(imgId);
          _syncSelectionUI(seriesId);
        }
      }
      const selIds = [...grid.querySelectorAll('[data-image-id]')].map(el => el.dataset.imageId);
      const libIds = lib ? [...lib.querySelectorAll('[data-image-id]')].map(el => el.dataset.imageId) : [];
      try {
        await apiFetch('PUT', '/api/series/' + seriesId + '/images/reorder', { image_ids: [...selIds, ...libIds] });
      } catch (e) { showToast('Reorder failed: ' + e.message, 'danger'); }
    },
  });
  _sortable = Sortable.create(grid, opts(grid));
  if (lib) _sortableLib = Sortable.create(lib, opts(lib));
  if (touch) {
    grid.addEventListener('contextmenu', e => e.preventDefault());
    if (lib) lib.addEventListener('contextmenu', e => e.preventDefault());
  }
}

function initLightbox() {
  document.addEventListener('keydown', e => {
    if (!_lightboxOpen) return;
    if (e.key === 'ArrowLeft')  lightboxNav(-1);
    if (e.key === 'ArrowRight') lightboxNav(+1);
  });
  document.getElementById('lightboxModal')
    .addEventListener('hidden.bs.modal', () => { _lightboxOpen = false; });
  document.getElementById('lightboxPrev').addEventListener('click', () => lightboxNav(-1));
  document.getElementById('lightboxNext').addEventListener('click', () => lightboxNav(+1));

  let _touchStartX = 0;
  const modal = document.getElementById('lightboxModal');
  modal.addEventListener('touchstart', e => { _touchStartX = e.changedTouches[0].clientX; }, { passive: true });
  modal.addEventListener('touchend', e => {
    if (!_lightboxOpen) return;
    const dx = e.changedTouches[0].clientX - _touchStartX;
    if (Math.abs(dx) > 50) lightboxNav(dx < 0 ? +1 : -1);
  }, { passive: true });

  async function _lightboxPatch(newStatus) {
    const img = _lightboxImages[_lightboxIdx];
    try {
      const updated = await apiFetch('PATCH', '/api/images/' + img.id + '/status', { status: newStatus });
      _lightboxImages[_lightboxIdx] = { ...img, status: newStatus };
      const savedSelection = new Set(_selectedImages);
      if (newStatus === 'skip' || newStatus === 'posted') savedSelection.delete(img.id);
      App.currentSeries = updated;
      renderEditor(updated);
      _selectedImages = savedSelection;
      _lightboxRender();
    } catch (err) { showToast(err.message, 'danger'); }
  }

  document.getElementById('lightboxQueueBtn').addEventListener('click', () => {
    const img = _lightboxImages[_lightboxIdx];
    if (img.status === 'posted') return;
    _toggleSelection(img.id, img.status, App.currentSeriesId);
    _lightboxRender();
  });
  document.getElementById('lightboxSkipBtn').addEventListener('click', () => {
    const img = _lightboxImages[_lightboxIdx];
    _lightboxPatch(img.status === 'skip' ? 'pending' : 'skip');
  });
  document.getElementById('lightboxMarkPostedBtn').addEventListener('click', () => {
    const img = _lightboxImages[_lightboxIdx];
    if (img.status !== 'posted') _lightboxPatch('posted');
  });
  document.getElementById('lightboxDeleteBtn').addEventListener('click', async () => {
    const img = _lightboxImages[_lightboxIdx];
    try {
      const updated = await apiFetch('DELETE', '/api/images/' + img.id);
      _lightboxImages.splice(_lightboxIdx, 1);
      if (!_lightboxImages.length) {
        bootstrap.Modal.getOrCreateInstance(document.getElementById('lightboxModal')).hide();
      } else {
        _lightboxIdx = Math.min(_lightboxIdx, _lightboxImages.length - 1);
        _lightboxRender();
      }
      App.currentSeries = updated;
      renderEditor(updated);
      showToast('Moved to Trash', 'success');
    } catch (err) { showToast(err.message, 'danger'); }
  });
  document.getElementById('lightboxFilmstrip').addEventListener('click', e => {
    const thumb = e.target.closest('[data-filmstrip-idx]');
    if (!thumb) return;
    _lightboxIdx = parseInt(thumb.dataset.filmstripIdx, 10);
    _lightboxRender();
  });
}

function openLightbox(images, startIdx) {
  _lightboxImages = images;
  _lightboxIdx    = startIdx;
  _lightboxOpen   = true;
  _lightboxRender();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('lightboxModal')).show();
}

function _lightboxRender() {
  const img = _lightboxImages[_lightboxIdx];

  document.getElementById('lightboxImg').setAttribute('src', img.public_url);
  document.getElementById('lightboxImg').setAttribute('alt', 'Image ' + (_lightboxIdx + 1));

  const counter = document.getElementById('lightboxCounter');
  const muteSpan = h('span', { cls: 'aap-mute' }, '/ ' + _lightboxImages.length);
  counter.replaceChildren(
    document.createTextNode((_lightboxIdx + 1) + ' '),
    muteSpan
  );

  const single = _lightboxImages.length <= 1;
  document.getElementById('lightboxPrev').classList.toggle('invisible', single);
  document.getElementById('lightboxNext').classList.toggle('invisible', single);

  const selBadge = document.getElementById('lightboxSelectedBadge');
  if (selBadge) selBadge.classList.toggle('d-none', !_selectedImages.has(img.id));

  const label = document.getElementById('lightboxActionsLabel');
  if (label) label.textContent = 'image ' + String(_lightboxIdx + 1).padStart(2, '0');

  const qBtn = document.getElementById('lightboxQueueBtn');
  const isSelected = _selectedImages.has(img.id);
  qBtn.textContent = isSelected ? '✓ Deselect' : '+ Select';
  qBtn.classList.toggle('aap-btn-selected', isSelected);
  qBtn.setAttribute('aria-label', isSelected ? 'Deselect image' : 'Select image');
  qBtn.disabled = img.status === 'posted';

  const sBtn = document.getElementById('lightboxSkipBtn');
  const isSkip = img.status === 'skip';
  sBtn.textContent = isSkip ? '↺ Unskip' : '◌ Skip';
  sBtn.setAttribute('aria-label', isSkip ? 'Unskip image' : 'Skip image');

  const mpBtn = document.getElementById('lightboxMarkPostedBtn');
  if (mpBtn) mpBtn.classList.toggle('d-none', img.status === 'posted');

  const moveMenu = document.getElementById('lightboxMoveMenu');
  if (moveMenu) {
    const currentSeriesId = App.currentSeriesId;
    moveMenu.replaceChildren();
    buildMoveToItems(img.id, currentSeriesId, false, () => {
      _lightboxImages.splice(_lightboxIdx, 1);
      if (!_lightboxImages.length || App.currentSeriesId !== currentSeriesId) {
        bootstrap.Modal.getOrCreateInstance(document.getElementById('lightboxModal')).hide();
      } else {
        _lightboxIdx = Math.min(_lightboxIdx, _lightboxImages.length - 1);
        _lightboxRender();
      }
    }).forEach(li => moveMenu.appendChild(li));
  }

  // Filmstrip
  const strip = document.getElementById('lightboxFilmstrip');
  if (strip) {
    strip.replaceChildren(
      ..._lightboxImages.map((im, i) => {
        const hue = [...im.id].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
        const btn = h('button', {
          cls: 'aap-filmstrip__thumb' + (i === _lightboxIdx ? ' is-current' : ''),
          type: 'button',
          style: '--thumb-color: hsl(' + hue + ' 35% 40%)',
          'data-filmstrip-idx': String(i),
        },
          h('span', { cls: 'aap-filmstrip__thumb-num' },
            String(i + 1).padStart(2, '0'))
        );
        if (im.public_url) {
          const fImg = document.createElement('img');
          fImg.src = im.public_url;
          fImg.style.cssText = 'width:100%;height:100%;object-fit:cover;position:absolute;inset:0';
          btn.style.position = 'relative';
          btn.insertBefore(fImg, btn.firstChild);
        }
        return btn;
      })
    );
  }
}

function lightboxNav(delta) {
  _lightboxIdx = (_lightboxIdx + delta + _lightboxImages.length) % _lightboxImages.length;
  _lightboxRender();
}

function _lightboxSyncSelectBtn(imgId) {
  if (!_lightboxOpen) return;
  const current = _lightboxImages[_lightboxIdx];
  if (current && current.id === imgId) _lightboxRender();
}

async function addImages(seriesId) {
  const input = document.createElement('input');
  input.type = 'file'; input.multiple = true; input.accept = 'image/*';
  input.addEventListener('change', async () => {
    if (!input.files.length) return;
    const fd = new FormData();
    for (const f of input.files) fd.append('files', f);
    try {
      const resp = await fetch('/api/series/' + seriesId + '/images', { method: 'POST', body: fd });
      if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail); }
      await loadSeriesDetail(seriesId);
      updateSeriesItem(App.currentSeries);
      showToast('Images uploaded', 'success');
    } catch (e) { showToast(e.message, 'danger'); }
  });
  input.click();
}

async function moveImages(imageIds, targetId, currentId) {
  try {
    await Promise.all(imageIds.map(id => apiFetch('PUT', '/api/images/' + id + '/move', { target_series_id: targetId })));
    _selectedImages.clear();
    await loadSeriesDetail(currentId);
    const t = await apiFetch('GET', '/api/series/' + targetId);
    updateSeriesItem(t);
    showToast(imageIds.length > 1 ? imageIds.length + ' images moved' : 'Image moved', 'success');
    return true;
  } catch (e) { showToast(e.message, 'danger'); }
}

async function deleteImage(imageId) {
  try {
    const updated = await apiFetch('DELETE', '/api/images/' + imageId);
    App.currentSeries = updated;
    renderEditor(updated);
    showToast('Moved to Trash', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

async function deleteVariant(variantId, cascade = false) {
  const path = '/api/ai_variants/' + variantId + (cascade ? '?cascade=true' : '');
  try {
    const updated = await apiFetch('DELETE', path);
    App.currentSeries = updated;
    renderEditor(updated);
    showToast('Variant deleted', 'success');
  } catch (e) {
    if (e.status === 409 && e.body?.detail?.cascade_required) {
      const n = e.body.detail.dependent_count;
      showConfirm(
        'This draft has ' + n + ' dependent full variant' + (n === 1 ? '' : 's') +
        ' that will also be deleted. Proceed?',
        () => deleteVariant(variantId, true),
      );
    } else {
      showToast(e.message, 'danger');
    }
  }
}

// ── Descriptions card ─────────────────────────────────────────────────────────
function buildDescriptionsCard(series) {
  const variants = series.ai_variants || [];

  const variantRow = h('div', { cls: 'aap-variant-row' });
  if (!variants.length) {
    variantRow.appendChild(h('span', { cls: 'aap-panel-head__meta', text: 'No AI variants yet.' }));
  } else {
    variants.forEach((v, i) => {
      const isChosen  = v.id === series.chosen_variant_id;
      const isPartial = !v.title;
      const pill = h('button', {
        cls: 'aap-variant' + (isChosen ? ' is-active' : ''),
        type: 'button',
        'data-variant-idx': String(i),
        onclick: () => applyVariant(i),
      },
        h('span', { cls: 'aap-variant__label', text: 'V' + (variants.length - i) }),
        h('span', { cls: 'aap-variant__model',
          text: (isPartial ? '(draft) ' : '') + (v.model || '') }),
        h('span', { cls: 'aap-variant__x', text: '\u00d7' })
      );
      pill.querySelector('.aap-variant__x').setAttribute('title', 'Delete variant');
      if (v.used_in_posts) {
        pill.querySelector('.aap-variant__x').style.display = 'none';
      } else {
        pill.querySelector('.aap-variant__x').addEventListener('click', e => {
          e.stopPropagation();
          deleteVariant(v.id);
        });
      }
      variantRow.appendChild(pill);
    });
  }
  const descEn    = h('textarea', { cls: 'aap-lang-textarea', id: 'f_desc_en', rows: '5', 'aria-label': 'EN Instagram description' });
  descEn.value    = series.description_en || '';
  descEn.addEventListener('input', () => _autoGrow(descEn));
  const descRu    = h('textarea', { cls: 'aap-lang-textarea', id: 'f_desc_ru', rows: '5', 'aria-label': 'RU description' });
  descRu.value    = series.description_ru || '';
  descRu.addEventListener('input', () => _autoGrow(descRu));
  const tagsIg    = h('input', { type: 'text', cls: 'aap-tag-input', id: 'f_tags_ig', 'aria-label': 'EN Instagram tags' });
  tagsIg.value    = (series.tags_instagram || []).join(' ');
  const tagsTg    = h('input', { type: 'text', cls: 'aap-tag-input', id: 'f_tags_tg', 'aria-label': 'TG tags' });
  tagsTg.value    = (series.tags_telegram || []).join(' ');
  const pubTitle  = h('input', { type: 'text', cls: 'aap-lang-card__title', id: 'f_pub_title', placeholder: 'Publication title EN', 'aria-label': 'EN title' });
  pubTitle.value  = series.title || '';
  const pubTitleRu = h('input', { type: 'text', cls: 'aap-lang-card__title', id: 'f_pub_title_ru', placeholder: 'Publication title RU', 'aria-label': 'RU title' });
  pubTitleRu.value = series.title_ru || '';

  const _cv  = series.chosen_variant_id
    ? (series.ai_variants || []).find(v => v.id === series.chosen_variant_id)
    : null;
  const _arch = _cv?.archive_metadata || {};

  const igSeo    = h('input', { type: 'text', cls: 'form-control aap-input', id: 'f_instagram_seo' });
  igSeo.value    = _cv?.instagram_seo || '';
  const pinTitle = h('input', { type: 'text', cls: 'form-control aap-input', id: 'f_pin_title' });
  pinTitle.value = _cv?.pinterest_title || '';
  const pinDesc  = h('textarea', { cls: 'form-control aap-input', id: 'f_pin_desc', rows: '2' });
  pinDesc.value  = _cv?.pinterest_description || '';
  const pinBoard = h('input', { type: 'text', cls: 'form-control aap-input', id: 'f_pin_board' });
  pinBoard.value = _cv?.pinterest_board || '';
  const archWorld  = h('input', { type: 'text', cls: 'form-control aap-input', id: 'f_arch_world',  placeholder: 'comma-separated' });
  archWorld.value  = (_arch.world_keywords  || []).join(', ');
  const archVisual = h('input', { type: 'text', cls: 'form-control aap-input', id: 'f_arch_visual', placeholder: 'comma-separated' });
  archVisual.value = (_arch.visual_keywords || []).join(', ');
  const archMood   = h('input', { type: 'text', cls: 'form-control aap-input', id: 'f_arch_mood',   placeholder: 'comma-separated' });
  archMood.value   = (_arch.mood_keywords   || []).join(', ');

  const boardChips = h('div', { cls: 'mt-1 d-flex flex-wrap gap-1' });
  const _fillBoards = boards => boards.forEach(name => {
    const chip = h('button', { type: 'button', cls: 'aap-chip',
      style: 'padding:3px 8px;font-size:11px', text: name });
    chip.addEventListener('click', () => { pinBoard.value = name; });
    boardChips.appendChild(chip);
  });
  if (_pinterestBoardsCache) {
    _fillBoards(_pinterestBoardsCache);
  } else {
    apiFetch('GET', '/api/settings/pinterest/boards').then(d => {
      _pinterestBoardsCache = d.boards || [];
      _fillBoards(_pinterestBoardsCache);
    }).catch(() => {});
  }

  const saveBtn = h('button', { cls: 'btn aap-btn aap-btn-primary', id: 'saveDescBtn' },
    icon('bi bi-floppy me-1'), document.createTextNode('Save'));
  saveBtn.addEventListener('click', () => saveDescription(series.id));

  const resetBtn = h('button', { cls: 'btn aap-btn ms-2' },
    icon('bi bi-arrow-counterclockwise me-1'), document.createTextNode('Reset'));
  resetBtn.addEventListener('click', resetToSaved);

  const chosenIdx = _cv ? variants.indexOf(_cv) : -1;
  const variantCount = variants.length + ' variants'
    + (chosenIdx >= 0 ? ' \u00b7 V' + (variants.length - chosenIdx) + ' active' : '');

  const section = h('section', { cls: 'px-4 pb-4', id: 'descBody-' + series.id },
    h('div', { cls: 'aap-panel-head' },
      h('span', { cls: 'aap-panel-head__label', text: 'Descriptions' }),
      h('span', { cls: 'aap-panel-head__rule' }),
      h('span', { cls: 'aap-panel-head__meta', text: variantCount })
    ),
    variantRow,
    h('div', { cls: 'row g-3 mt-2' },
      h('div', { cls: 'col-md-6' },
        h('div', { cls: 'aap-card aap-lang-card' },
          h('div', { cls: 'd-flex align-items-center gap-2 mb-3' },
            h('span', { cls: 'aap-lang-badge', text: 'EN' }),
            h('span', { cls: 'aap-panel-head__meta', text: 'publication' })
          ),
          pubTitle,
          h('label', { cls: 'aap-field-label', text: 'Instagram & FB' }), descEn,
          h('label', { cls: 'aap-field-label mt-3', text: 'Tags' }), tagsIg
        )
      ),
      h('div', { cls: 'col-md-6' },
        h('div', { cls: 'aap-card aap-lang-card' },
          h('div', { cls: 'd-flex align-items-center gap-2 mb-3' },
            h('span', { cls: 'aap-lang-badge', text: 'RU' }),
            h('span', { cls: 'aap-panel-head__meta', text: 'publication' })
          ),
          pubTitleRu,
          h('label', { cls: 'aap-field-label', text: 'Telegram' }), descRu,
          h('label', { cls: 'aap-field-label mt-3', text: 'Tags' }), tagsTg
        )
      )
    ),
    h('div', { cls: 'aap-card mt-3' },
      h('div', { cls: 'd-flex align-items-center gap-2 mb-3' },
        h('span', { cls: 'aap-pin-mark', text: 'P' }),
        h('span', { cls: 'aap-composer__title', text: 'Pinterest' })
      ),
      h('div', { cls: 'row g-3 mb-3' },
        h('div', { cls: 'col-md-6' },
          h('label', { cls: 'aap-field-label', text: 'Title' }), pinTitle),
        h('div', { cls: 'col-md-6' },
          h('label', { cls: 'aap-field-label', text: 'Board' }), pinBoard, boardChips)
      ),
      h('label', { cls: 'aap-field-label', text: 'Description' }), pinDesc
    ),
    h('div', { cls: 'aap-card mt-3' },
      h('div', { cls: 'd-flex align-items-center gap-2 mb-3' },
        h('span', { style: 'color:var(--aap-accent);font-size:12px', text: '\u25be' }),
        h('span', { cls: 'aap-composer__title', text: 'Semantic layer' }),
        h('span', { cls: 'aap-auto-badge', text: 'auto' })
      ),
      h('div', { cls: 'row g-3' },
        h('div', { cls: 'col-md-6' },
          h('label', { cls: 'aap-field-label', text: 'Instagram discovery' }), igSeo),
        h('div', { cls: 'col-md-6' },
          h('label', { cls: 'aap-field-label', text: 'World keywords' }), archWorld),
        h('div', { cls: 'col-md-6' },
          h('label', { cls: 'aap-field-label', text: 'Visual keywords' }), archVisual),
        h('div', { cls: 'col-md-6' },
          h('label', { cls: 'aap-field-label', text: 'Mood keywords' }), archMood)
      )
    ),
    h('div', { cls: 'mt-3' }, saveBtn, resetBtn)
  );

  section.addEventListener('input', _debounce(_updateSaveDescBtn, 150));
  return section;
}

function resetToSaved() {
  const s = App.currentSeries;
  if (!s) return;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  set('f_pub_title',    s.title);
  set('f_pub_title_ru', s.title_ru);
  set('f_desc_en',      s.description_en);
  set('f_desc_ru',      s.description_ru);
  set('f_tags_ig',      (s.tags_instagram || []).join(' '));
  set('f_tags_tg',      (s.tags_telegram  || []).join(' '));
  const chosenV = s.chosen_variant_id
    ? (s.ai_variants || []).find(v => v.id === s.chosen_variant_id)
    : null;
  const arch = chosenV?.archive_metadata || {};
  set('f_instagram_seo', chosenV?.instagram_seo || '');
  set('f_pin_title',     chosenV?.pinterest_title || '');
  set('f_pin_desc',      chosenV?.pinterest_description || '');
  set('f_pin_board',     chosenV?.pinterest_board || '');
  set('f_arch_world',  (arch.world_keywords  || []).join(', '));
  set('f_arch_visual', (arch.visual_keywords || []).join(', '));
  set('f_arch_mood',   (arch.mood_keywords   || []).join(', '));
  App.activeVariantId = s.chosen_variant_id || null;
  _updateSaveDescBtn();
  document.querySelectorAll('[data-variant-idx]').forEach((btn, i) => {
    const isChosen = (s.ai_variants || [])[i]?.id === s.chosen_variant_id;
    btn.classList.toggle('is-active', isChosen);
  });
  _autoGrowDescTextareas();
}

function applyVariant(idx) {
  const v = App.currentSeries?.ai_variants?.[idx];
  if (!v) return;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  const isPartial = !v.title;
  if (isPartial) {
    set('f_desc_en', v.description_en);
    set('f_desc_ru', v.description_ru);
    set('f_pub_title', '');
    set('f_pub_title_ru', '');
    set('f_tags_ig', '');
    set('f_tags_tg', '');
    set('f_instagram_seo', '');
    set('f_pin_title', '');
    set('f_pin_desc', '');
    set('f_pin_board', '');
    set('f_arch_world', '');
    set('f_arch_visual', '');
    set('f_arch_mood', '');
    const hintEl = document.getElementById('genHint'); if (hintEl) hintEl.value = v.hint || '';
  } else {
    set('f_desc_en', v.description_en);
    set('f_desc_ru', v.description_ru);
    set('f_tags_ig', (v.tags_instagram || []).join(' '));
    set('f_tags_tg', (v.tags_telegram  || []).join(' '));
    if (v.title) { const t = document.getElementById('f_pub_title'); if (t) t.value = v.title; }
    if (v.title_ru) { const t = document.getElementById('f_pub_title_ru'); if (t) t.value = v.title_ru; }
    const hintEl = document.getElementById('genHint'); if (hintEl) hintEl.value = v.hint || '';
    set('f_instagram_seo', v.instagram_seo || '');
    set('f_pin_title', v.pinterest_title || '');
    set('f_pin_desc', v.pinterest_description || '');
    set('f_pin_board', v.pinterest_board || '');
    const arch = v.archive_metadata || {};
    set('f_arch_world', (arch.world_keywords || []).join(', '));
    set('f_arch_visual', (arch.visual_keywords || []).join(', '));
    set('f_arch_mood', (arch.mood_keywords || []).join(', '));
  }
  App.activeVariantId = v.id;
  _updateSaveDescBtn();
  document.querySelectorAll('[data-variant-idx]').forEach((btn, i) => {
    btn.classList.toggle('is-active', i === idx);
  });
  _autoGrowDescTextareas();
}

async function saveDescription(seriesId) {
  const tagsIg = (document.getElementById('f_tags_ig')?.value || '').split(/\s+/).filter(Boolean);
  const tagsTg = (document.getElementById('f_tags_tg')?.value || '').split(/\s+/).filter(Boolean);
  try {
    const body = {
      name:           document.getElementById('editorTitle')?.value?.trim() || '',
      title:          document.getElementById('f_pub_title')?.value?.trim() || '',
      title_ru:       document.getElementById('f_pub_title_ru')?.value?.trim() || '',
      description_en: document.getElementById('f_desc_en')?.value || '',
      description_ru: document.getElementById('f_desc_ru')?.value || '',
      tags_instagram: tagsIg,
      tags_telegram:  tagsTg,
    };
    if (App.activeVariantId) body.chosen_variant_id = App.activeVariantId;
    const updated = await apiFetch('PUT', '/api/series/' + seriesId, body);
    App.currentSeries = updated;
    updateSeriesItem(updated);
    const t = document.getElementById('editorTitle');
    if (t) t.value = updated.name || updated.title || '';
    localStorage.removeItem('draft_' + seriesId);
    showToast('Saved', 'success');
    _updateSaveDescBtn();
    if (App.activeVariantId) {
      const splitTrim = s => s.split(',').map(x => x.trim()).filter(Boolean);
      await apiFetch('PATCH', '/api/ai_variants/' + App.activeVariantId, {
        instagram_seo: document.getElementById('f_instagram_seo')?.value || '',
        pinterest_title: document.getElementById('f_pin_title')?.value || '',
        pinterest_description: document.getElementById('f_pin_desc')?.value || '',
        pinterest_board: document.getElementById('f_pin_board')?.value || '',
        archive_metadata: {
          world_keywords: splitTrim(document.getElementById('f_arch_world')?.value || ''),
          visual_keywords: splitTrim(document.getElementById('f_arch_visual')?.value || ''),
          mood_keywords: splitTrim(document.getElementById('f_arch_mood')?.value || ''),
        },
      });
    }
  } catch (e) { showToast(e.message, 'danger'); }
}

function _restoreSelectionAfterRender(savedSel, seriesId) {
  _selectedImages = savedSel;
  [
    ...document.querySelectorAll('#selectedTray [data-image-id]'),
    ...document.querySelectorAll('#libraryGrid [data-image-id]'),
  ].forEach(thumb => {
    const id = thumb.dataset.imageId, st = thumb.dataset.imageStatus;
    thumb.classList.toggle('is-selected', savedSel.has(id));
    const btn = thumb.querySelector('[data-select-btn]');
    if (btn) btn.replaceChildren(icon(_selectIcon(id, st)));
  });
  _resortStrip();
  _refreshActionBar(seriesId);
  _refreshImagesHeader((App.currentSeries?.images ?? []).length);
}

// ── Generate card ─────────────────────────────────────────────────────────────
function buildGenerateCard(seriesId) {
  const hintInput = h('input', {
    type: 'text', cls: 'form-control aap-input', id: 'genHint',
    placeholder: 'e.g. astronaut on lost space station sees a Hand. Outside.',
  });

  const provSel = document.createElement('select');
  provSel.className = 'form-select aap-input'; provSel.id = 'genProvider';
  [['', 'Default'], ['anthropic', 'Anthropic'], ['openai', 'OpenAI'],
   ['google', 'Google'], ['deepseek', 'DeepSeek'], ['openrouter', 'OpenRouter']
  ].forEach(([val, lbl]) => {
    const o = document.createElement('option'); o.value = val; o.textContent = lbl;
    provSel.appendChild(o);
  });
  if (App.generateProvider != null) provSel.value = App.generateProvider;

  const modelSel = document.createElement('select');
  modelSel.className = 'form-select aap-input'; modelSel.id = 'genModel';
  buildProviderModelSelect(modelSel, provSel.value, { withDefault: true });
  if (App.generateModel) modelSel.value = App.generateModel;

  provSel.addEventListener('change', () => {
    App.generateProvider = provSel.value;
    buildProviderModelSelect(modelSel, provSel.value, { withDefault: true });
  });
  modelSel.addEventListener('change', () => { App.generateModel = modelSel.value; });

  const numVariantsInput = h('input', {
    type: 'number', cls: 'form-control aap-input', id: 'genNumVariants',
    min: '1', max: '5',
    value: String(App.generateNumVariants || 1),
    style: 'width:60px',
  });
  numVariantsInput.addEventListener('change', () => {
    App.generateNumVariants = parseInt(numVariantsInput.value, 10) || 1;
  });

  const langEn = h('button', { type: 'button', cls: 'is-active', id: 'genLangEn', 'data-lang': 'EN', text: 'EN' });
  const langRu = h('button', { type: 'button', id: 'genLangRu', 'data-lang': 'RU', text: 'RU' });
  const _setLang = lang => {
    App.generateLanguage = lang;
    langEn.classList.toggle('is-active', lang === 'en');
    langRu.classList.toggle('is-active', lang === 'ru');
  };
  langEn.addEventListener('click', () => _setLang('en'));
  langRu.addEventListener('click', () => _setLang('ru'));
  if (!App.generateLanguage) App.generateLanguage = 'en';
  _setLang(App.generateLanguage);

  const imgCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'genIncludeImages' });

  const genBtn = h('button', { cls: 'btn aap-btn aap-btn-primary w-100', id: 'generateBtn' },
    document.createTextNode('\u2736 Generate '),
    numVariantsInput,
    document.createTextNode(' drafts')
  );
  genBtn.addEventListener('click', () => generateDrafts(seriesId));

  const genFullBtn = h('button', { cls: 'btn aap-btn w-100', id: 'generateFullBtn', text: 'Generate full \u2192' });
  genFullBtn.addEventListener('click', () => generateFull(seriesId));

  const errorBadge = h('a', { cls: 'ms-auto small text-warning d-none', id: 'genErrorBadge', style: 'cursor:pointer' });
  errorBadge.setAttribute('data-bs-toggle', 'collapse');
  errorBadge.setAttribute('href', '#genErrorLog');
  const errorList = h('ul', { cls: 'list-group list-group-flush', id: 'genErrorList' });
  const errorLog  = h('div', { cls: 'collapse', id: 'genErrorLog' }, errorList);
  const errorDiv  = h('div', { cls: 'alert alert-danger small py-1 px-2 mt-2 mb-0 d-none', id: 'genError' });

  return h('section', { cls: 'px-4 pb-4' },
    h('div', { cls: 'aap-card aap-card--gen' },
      h('div', { cls: 'aap-panel-head' },
        h('span', { cls: 'aap-panel-head__label aap-panel-head__label--accent', text: '\u2736 Generate' }),
        h('span', { cls: 'aap-panel-head__rule' }),
        errorBadge
      ),
      h('div', null,
        h('label', { cls: 'aap-field-label', text: 'Hint' }),
        h('div', { cls: 'aap-hint-input' },
          h('span', { cls: 'aap-hint-input__prompt', text: '\u203a' }),
          hintInput
        )
      ),
      h('div', { cls: 'row g-2 mt-3' },
        h('div', { cls: 'col' },
          h('label', { cls: 'aap-field-label', text: 'Provider' }), provSel),
        h('div', { cls: 'col' },
          h('label', { cls: 'aap-field-label', text: 'Model' }), modelSel),
        h('div', { cls: 'col-auto', style: 'width:110px' },
          h('label', { cls: 'aap-field-label', text: 'Language' }),
          h('div', { cls: 'aap-seg' }, langEn, langRu)
        )
      ),
      h('div', { cls: 'aap-rail' },
        h('div', { cls: 'aap-step aap-step--active' },
          h('div', { cls: 'aap-step__head' },
            h('span', { cls: 'aap-step__num', text: '1' }),
            h('span', { cls: 'aap-step__title', text: 'Draft descriptions' })
          ),
          h('p', { cls: 'aap-step__body', text: 'Produces EN drafts to choose from.' }),
          genBtn,
          h('label', {
            cls: 'd-flex align-items-center gap-2 mt-2',
            style: 'font-size:11px;color:var(--aap-ink-soft)',
          }, imgCheck, document.createTextNode(' include images as context'))
        ),
        h('div', { cls: 'aap-rail__arrow', text: '\u2192' }),
        h('div', { cls: 'aap-step' },
          h('div', { cls: 'aap-step__head' },
            h('span', { cls: 'aap-step__num aap-step__num--outline', text: '2' }),
            h('span', { cls: 'aap-step__title', text: 'Fill the rest' })
          ),
          h('p', { cls: 'aap-step__body',
            text: 'From chosen draft: translate, write TG & Pinterest, derive tags + semantics.' }),
          genFullBtn
        )
      ),
      errorDiv, errorLog
    )
  );
}

async function generateDrafts(seriesId) {
  const btn = document.getElementById('generateBtn');
  const provider = document.getElementById('genProvider')?.value || null;
  const model    = document.getElementById('genModel')?.value.trim() || null;
  const hint          = document.getElementById('genHint')?.value.trim() || null;
  const includeImages = document.getElementById('genIncludeImages')?.checked ?? false;
  const language = App.generateLanguage || 'en';
  const numVariants = parseInt(document.getElementById('genNumVariants')?.value || '1', 10) || 1;
  if (btn) {
    btn.disabled = true;
    btn.replaceChildren(h('span', { cls: 'spinner-border spinner-border-sm me-1' }), document.createTextNode('Generating…'));
  }
  let selectedImageIds = null;
  if (includeImages && _selectedImages.size > 0) {
    const orderedThumbIds = [
      ...document.querySelectorAll('#selectedTray [data-image-id]'),
      ...document.querySelectorAll('#libraryGrid [data-image-id]'),
    ].map(el => el.dataset.imageId);
    selectedImageIds = orderedThumbIds.length > 0
      ? orderedThumbIds.filter(id => _selectedImages.has(id)).slice(0, 3)
      : [..._selectedImages].slice(0, 3);
  }
  try {
    const newVariants = await apiFetch('POST', '/api/series/' + seriesId + '/generate', {
      provider: provider || null, model: model || null, hint: hint || null,
      include_images: includeImages, selected_image_ids: selectedImageIds, language, num_variants: numVariants,
    });
    const savedSelection = new Set(_selectedImages);
    await loadSeriesDetail(seriesId);
    // Variants sorted newest-first — new drafts are always at index 0
    if ((App.currentSeries?.ai_variants || []).length > 0) applyVariant(0);
    _restoreSelectionAfterRender(savedSelection, seriesId);
    const cost = newVariants[0]?.cost_usd;
    const costLabel = cost > 0 ? ` · $${cost.toFixed(4)}` : '';
    ErrorService.clear('generate');
    showToast(`Generated ${newVariants.length} drafts${costLabel}`, 'success');
  } catch (e) {
    ErrorService.record('generate', e.message);
    if (btn) {
      btn.disabled = false;
      btn.replaceChildren(icon('bi bi-robot me-1'), document.createTextNode('Generate Drafts'));
    }
  }
}

async function generateFull(seriesId) {
  const language = App.generateLanguage || 'en';
  const fieldId = language === 'ru' ? 'f_desc_ru' : 'f_desc_en';
  const description = document.getElementById(fieldId)?.value?.trim() || '';
  if (!description) {
    showToast(`Enter a ${language === 'ru' ? 'Russian' : 'English'} description first`, 'warning');
    return;
  }
  const btn = document.getElementById('generateFullBtn');
  if (btn) {
    btn.disabled = true;
    btn.replaceChildren(h('span', { cls: 'spinner-border spinner-border-sm me-1' }), document.createTextNode('Expanding…'));
  }
  const provider = document.getElementById('genProvider')?.value || null;
  const model = document.getElementById('genModel')?.value?.trim() || null;
  const hint = document.getElementById('genHint')?.value?.trim() || null;
  try {
    const updated = await apiFetch('POST', '/api/series/' + seriesId + '/generate-full', {
      description, language,
      variant_id: App.activeVariantId || null,
      provider: provider || null, model: model || null, hint: hint || null,
    });
    App.currentSeries = updated;
    const variants = updated.ai_variants || [];
    const targetId = App.activeVariantId;
    const idx = targetId ? variants.findIndex(v => v.id === targetId) : variants.length - 1;
    renderEditor(updated);
    if (idx >= 0) applyVariant(idx);
    const cost = variants[idx >= 0 ? idx : variants.length - 1]?.cost_usd;
    const costLabel = cost > 0 ? ` · $${cost.toFixed(4)}` : '';
    ErrorService.clear('generate');
    showToast(`Full content generated${costLabel}`, 'success');
  } catch (e) {
    ErrorService.record('generate', e.message);
    if (btn) {
      btn.disabled = false;
      btn.replaceChildren(icon('bi bi-stars me-1'), document.createTextNode('Generate Full'));
    }
  }
}

// ── Actions card ──────────────────────────────────────────────────────────────
function buildStatusBar(series) {
  const displayStatus = statusDisplay(series.status);
  const STATUS_SEG = [
    { display: 'new',    dbWrite: 'new',    dotCls: 'aap-dot--new' },
    { display: 'draft',  dbWrite: 'draft',  dotCls: 'aap-dot--draft' },
    { display: 'active', dbWrite: 'active', dotCls: 'aap-dot--active' },
    { display: 'done',   dbWrite: 'done',   dotCls: 'aap-dot--done' },
  ];

  const seg = h('div', { cls: 'aap-status-seg', id: 'aap-status-seg' });
  STATUS_SEG.forEach(({ display, dbWrite, dotCls }) => {
    const isActive = display === displayStatus;
    const btn = h('button', {
      type: 'button',
      cls: isActive ? 'is-active' : '',
      'data-status': dbWrite,
    },
      h('span', { cls: 'aap-dot ' + dotCls }),
      document.createTextNode(' ' + display.charAt(0).toUpperCase() + display.slice(1))
    );
    if (isActive) btn.style.setProperty('--seg-color', 'var(--aap-dot-' + display + ')');
    btn.addEventListener('click', () => {
      seg.querySelectorAll('button').forEach(b => {
        b.classList.remove('is-active');
        b.style.removeProperty('--seg-color');
      });
      btn.classList.add('is-active');
      btn.style.setProperty('--seg-color', 'var(--aap-dot-' + display + ')');
      saveStatus(series.id);
    });
    seg.appendChild(btn);
  });

  const deleteSeriesBtn = h('button', {
    cls: 'aap-icon-btn aap-icon-btn--danger',
    title: 'Delete series',
    'aria-label': 'Delete series',
  }, h('i', { cls: 'bi bi-trash3' }));
  deleteSeriesBtn.addEventListener('click', () => deleteSeries(series.id));

  return h('div', { cls: 'aap-editor-action-row' },
    seg,
    h('div', { style: 'flex:1' }),
    deleteSeriesBtn
  );
}

async function saveStatus(seriesId) {
  const status = document.querySelector('#aap-status-seg button.is-active')?.dataset.status;
  if (!status) return;
  try {
    const updated = await apiFetch('PUT', '/api/series/' + seriesId, { status });
    App.currentSeries = updated;
    updateSeriesItem(updated);
    showToast('Status saved', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

async function deleteSeries(seriesId) {
  try {
    await apiFetch('DELETE', '/api/series/' + seriesId);
    App.series = App.series.filter(s => s.id !== seriesId);
    App.currentSeriesId = null;
    App.currentSeries = null;
    document.getElementById('si-' + seriesId)?.remove();
    showView('list');
    showToast('Moved to Trash', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Collection picker ─────────────────────────────────────────────────────────
function buildCollectionPicker(series) {
  let currentCollection = series.collection || null;
  let currentNumber = series.collection_number || null;
  let currentIndex = series.collection_index || null;

  const wrap = h('div', { id: 'collectionPickerWrap', cls: 'd-flex align-items-center gap-1 mb-2 position-relative', style: 'z-index:1050' });

  // ── Toggle button ──────────────────────────────────────────────────────────
  const toggleBtn = h('button', {
    type: 'button',
    cls: 'btn btn-sm btn-outline-secondary d-flex align-items-center gap-1',
  });
  const _updateBtn = () => {
    toggleBtn.replaceChildren(icon('bi bi-collection'));
    if (currentCollection) {
      toggleBtn.appendChild(h('span', { cls: 'badge bg-purple ms-1 lh-sm d-flex flex-column align-items-start' },
        document.createTextNode(currentCollection.name),
        currentCollection.name_ru
          ? h('span', { style: 'font-size:10px;opacity:0.85', text: currentCollection.name_ru })
          : null,
      ));
    } else {
      toggleBtn.appendChild(document.createTextNode(' Collection…'));
    }
  };
  _updateBtn();

  // ── Dropdown panel (search + list) ────────────────────────────────────────
  const panel = h('div', {
    cls: 'position-absolute bg-body border rounded shadow-sm p-2',
    style: 'z-index:100;min-width:240px;display:none;top:100%;left:0',
  });

  const searchInput = h('input', {
    type: 'text', cls: 'form-control form-control-sm mb-1',
    placeholder: 'Search or create…',
  });
  searchInput.setAttribute('autocomplete', 'off');

  const listEl = h('ul', { cls: 'list-unstyled mb-0', style: 'max-height:200px;overflow-y:auto' });

  panel.appendChild(searchInput);
  panel.appendChild(listEl);

  const _hidePanel = () => { panel.style.display = 'none'; searchInput.value = ''; _activeCollPickerHide = null; };
  const _showPanel = () => { panel.style.display = 'block'; searchInput.focus(); _renderList(''); };

  // ── Number input ──────────────────────────────────────────────────────────
  let numWrap = null;
  const _setNumberInput = (show, numberVal, indexVal) => {
    if (numWrap) { numWrap.remove(); numWrap = null; }
    if (!show) return;
    const numInput = h('input', {
      type: 'text', cls: 'form-control form-control-sm',
      id: 'collectionNumberInput', placeholder: '#number',
      style: 'width:80px',
    });
    numInput.value = numberVal || '';
    numInput.addEventListener('blur', async () => {
      const val = numInput.value.trim();
      if (val === (currentNumber || '')) return;
      try {
        const updated = await apiFetch('PUT', '/api/series/' + series.id, { collection_number: val || null });
        App.currentSeries = updated;
        currentNumber = updated.collection_number;
      } catch (e) { showToast(e.message, 'danger'); numInput.value = currentNumber || ''; }
    });
    const idxHint = indexVal != null
      ? h('span', { cls: 'text-muted small', text: '(' + indexVal + ')' })
      : null;
    numWrap = h('span', { cls: 'd-flex align-items-center gap-1' }, numInput, idxHint);
    wrap.appendChild(numWrap);
  };

  // ── Assign / unassign ─────────────────────────────────────────────────────
  const _assign = async (collectionId, collectionName, collectionNameRu) => {
    _hidePanel();
    currentCollection = { id: collectionId, name: collectionName, name_ru: collectionNameRu || null };
    _updateBtn();
    try {
      const updated = await apiFetch('PUT', '/api/series/' + series.id, { collection_id: collectionId });
      App.currentSeries = updated;
      currentNumber = updated.collection_number;
      currentIndex = updated.collection_index;
      updateSeriesItem(updated);
      _setNumberInput(true, currentNumber, currentIndex);
    } catch (e) {
      showToast(e.message, 'danger');
      currentCollection = series.collection || null;
      _updateBtn();
    }
  };

  const _unassign = async () => {
    _hidePanel();
    currentCollection = null;
    _updateBtn();
    _setNumberInput(false);
    try {
      const updated = await apiFetch('PUT', '/api/series/' + series.id, { collection_id: null });
      App.currentSeries = updated;
      currentNumber = null;
      currentIndex = null;
      updateSeriesItem(updated);
    } catch (e) {
      showToast(e.message, 'danger');
      currentCollection = series.collection || null;
      _updateBtn();
      _setNumberInput(true, currentNumber, currentIndex);
    }
  };

  // ── List rendering ────────────────────────────────────────────────────────
  const _renderList = (query) => {
    listEl.replaceChildren();
    const all = App.collections || [];
    const q = query.toLowerCase();
    const filtered = q
      ? all.filter(c => c.name.toLowerCase().includes(q) || (c.name_ru || '').toLowerCase().includes(q))
      : all;

    filtered.forEach(c => {
      const link = h('a', { cls: 'dropdown-item small py-1', href: '#', style: 'line-height:1.3' });
      link.appendChild(document.createTextNode(c.name));
      if (c.name_ru) link.appendChild(h('span', { cls: 'text-muted d-block', style: 'font-size:11px', text: c.name_ru }));
      link.addEventListener('click', e => { e.preventDefault(); _assign(c.id, c.name, c.name_ru); });
      listEl.appendChild(h('li', null, link));
    });

    if (query && !filtered.some(c => c.name.toLowerCase() === query.toLowerCase())) {
      const createLink = h('a', { cls: 'dropdown-item small text-primary', href: '#' });
      createLink.appendChild(icon('bi bi-plus me-1'));
      createLink.appendChild(document.createTextNode('Create "' + query + '"'));
      createLink.addEventListener('click', async e => {
        e.preventDefault();
        try {
          const c = await apiFetch('POST', '/api/collections', { name: query });
          App.collections = [...(App.collections || []), c];
          await _assign(c.id, c.name, c.name_ru);
        } catch (err) { showToast(err.message, 'danger'); }
      });
      listEl.appendChild(h('li', null, createLink));
    }

    if (currentCollection) {
      listEl.appendChild(h('li', null,
        h('a', { cls: 'dropdown-item small text-muted', href: '#', text: '— Remove collection',
          onclick: e => { e.preventDefault(); _unassign(); } })));
    }
  };

  searchInput.addEventListener('input', e => _renderList(e.target.value.trim()));
  searchInput.addEventListener('keydown', e => { if (e.key === 'Escape') _hidePanel(); });

  // ── Toggle ────────────────────────────────────────────────────────────────
  toggleBtn.addEventListener('click', e => {
    e.stopPropagation();
    if (panel.style.display === 'none') {
      _activeCollPickerHide = _hidePanel;
      _showPanel();
    } else {
      _hidePanel();
    }
  });

  wrap.appendChild(toggleBtn);
  wrap.appendChild(panel);
  _setNumberInput(!!currentCollection, currentNumber, currentIndex);
  return wrap;
}

// ── Shared image selector (used by create and edit post forms) ────────────────
function _buildImageSelector(allImages, initialSelected, imgMap) {
  const selected = new Set(initialSelected);
  const grid = h('div', { cls: 'd-flex gap-1 flex-wrap mb-2' });
  allImages.forEach(img => {
    const on = selected.has(img.id);
    const imgEl = document.createElement('img');
    imgEl.setAttribute('src', imgMap[img.id] || img.public_url || '');
    imgEl.style.cssText = 'width:52px;height:46px;object-fit:cover;border-radius:3px;cursor:pointer;opacity:' + (on ? '1' : '0.35');
    const tick = h('div', { cls: 'position-absolute top-0 end-0', style: 'font-size:12px;line-height:1;background:rgba(0,0,0,.5);border-radius:2px;padding:1px 3px;color:#fff;display:' + (on ? '' : 'none') });
    tick.textContent = '✓';
    const wrap = h('div', { cls: 'position-relative', style: 'display:inline-block' });
    wrap.appendChild(imgEl); wrap.appendChild(tick);
    wrap.addEventListener('click', () => {
      if (selected.has(img.id)) { selected.delete(img.id); imgEl.style.opacity = '0.35'; tick.style.display = 'none'; }
      else { selected.add(img.id); imgEl.style.opacity = '1'; tick.style.display = ''; }
    });
    grid.appendChild(wrap);
  });
  return { grid, selected };
}

// ── Posts card ────────────────────────────────────────────────────────────────
const POST_PLATFORM_ICON = { telegram: 'bi bi-telegram', instagram: 'bi bi-instagram', facebook: 'bi bi-facebook', pinterest: 'bi bi-pinterest' };
const POST_STATUS_COLOR  = { draft: 'bg-secondary', scheduled: 'bg-purple', sending: 'bg-warning text-dark', posted: 'bg-success', failed: 'bg-danger' };

function buildPostsCard(series) {
  const imgMap = {};
  series.images.forEach(i => { if (!i.deleted_at) imgMap[i.id] = i.public_url; });
  const activePosts = (series.posts || []).filter(p => !p.deleted_at);
  const scheduled   = activePosts.filter(p => p.status === 'scheduled').length;
  const published   = activePosts.filter(p => p.status === 'posted').length;

  const newPostBtn = h('button', { cls: 'btn aap-btn' },
    icon('bi bi-plus me-1'), document.createTextNode('New post'));
  const formWrap = h('div', { cls: 'd-none' });
  newPostBtn.addEventListener('click', () => {
    if (formWrap.classList.contains('d-none')) {
      const cur = App.currentSeries;
      const curImgMap = {};
      cur.images.forEach(i => { if (!i.deleted_at) curImgMap[i.id] = i.public_url; });
      formWrap.replaceChildren(buildCreatePostForm(cur, curImgMap, () => formWrap.classList.add('d-none')));
      formWrap.classList.remove('d-none');
    } else {
      formWrap.classList.add('d-none');
    }
  });

  const postList = h('div', { cls: 'd-flex flex-column gap-2' });
  if (!activePosts.length) {
    postList.appendChild(h('p', { cls: 'aap-mute', style: 'font-size:13px;padding:0 0 8px',
      text: 'No posts yet.' }));
  } else {
    activePosts.forEach(p => postList.appendChild(buildPostRow(p, imgMap, series)));
  }

  return h('section', { cls: 'px-4 py-4' },
    h('div', { cls: 'aap-panel-head' },
      h('span', { cls: 'aap-panel-head__label', text: 'Posts' }),
      h('span', { cls: 'aap-panel-head__rule' }),
      h('span', { cls: 'aap-panel-head__meta',
        text: scheduled + ' scheduled \u00b7 ' + published + ' published' }),
      newPostBtn
    ),
    formWrap,
    postList
  );
}

const STATUS_ICON_MAP = {
  draft:     { cls: 'bi bi-pencil',           color: 'var(--aap-ink-mute)' },
  scheduled: { cls: 'bi bi-calendar-check',   color: 'var(--aap-dot-active)' },
  posted:    { cls: 'bi bi-check-lg',          color: 'var(--aap-dot-done)' },
  failed:    { cls: 'bi bi-exclamation-circle',color: 'var(--aap-danger)' },
};
const STORY_STATUS_ICON = {
  draft:      { cls: 'bi bi-clock',              color: 'var(--aap-ink-mute)' },
  rendered:   { cls: 'bi bi-image',              color: 'var(--aap-dot-active)' },
  publishing: { cls: 'bi bi-arrow-repeat',       color: 'var(--aap-dot-active)' },
  posted:     { cls: 'bi bi-check-lg',           color: 'var(--aap-dot-done)' },
  failed:     { cls: 'bi bi-exclamation-circle', color: 'var(--aap-danger)' },
};

function buildPostRow(post, imgMap, series) {
  const PLAT_ICON = {
    telegram:  'bi bi-telegram',
    instagram: 'bi bi-instagram',
    facebook:  'bi bi-facebook',
    pinterest: 'bi bi-pinterest',
  };
  const STATUS_COLOR_MAP = {
    draft:     'var(--aap-ink-mute)',
    scheduled: 'var(--aap-dot-active)',
    sending:   'var(--aap-dot-active)',
    posted:    'var(--aap-dot-done)',
    failed:    'var(--aap-danger)',
  };

  const hue = [...post.id].reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
  const thumbDiv = h('div', {
    cls: 'aap-post-row__thumb',
    style: '--thumb-color: hsl(' + hue + ' 40% 40%)',
  });
  if (post.image_ids?.length && imgMap[post.image_ids[0]]) {
    const img2 = document.createElement('img');
    img2.src = imgMap[post.image_ids[0]];
    img2.style.cssText = 'width:100%;height:100%;object-fit:cover';
    thumbDiv.appendChild(img2);
  }

  const platIconCls = PLAT_ICON[post.platform] || 'bi bi-send';
  const platEl = h('div', { cls: 'aap-post-row__channels' },
    icon(platIconCls + ' me-1'));
  const timeEl = post.posted_at
    ? h('span', { cls: 'aap-post-row__when', text: formatDate(post.posted_at) })
    : post.scheduled_at
      ? h('span', { cls: 'aap-post-row__when',
          style: 'color:var(--aap-dot-active)', text: formatDate(post.scheduled_at) })
      : null;
  if (timeEl) platEl.appendChild(timeEl);

  const si = STATUS_ICON_MAP[post.status];
  const statusEl = h('span', {
    cls: 'aap-post-row__status',
    style: '--status-color: ' + (STATUS_COLOR_MAP[post.status] || 'var(--aap-ink-mute)'),
    title: post.status,
  },
    post.status === 'sending'
      ? h('span', { cls: 'spinner-border spinner-border-sm', 'aria-hidden': 'true' })
      : si ? h('i', { cls: si.cls, style: 'color:' + si.color + ';font-size:14px' })
           : h('span', { cls: 'aap-dot' })
  );

  const actions = h('div', { cls: 'aap-post-row__actions' });

  const viewBtn = h('button', { cls: 'aap-icon-btn', title: 'View post content', 'aria-label': 'View post content' },
    icon('bi bi-eye'));
  viewBtn.addEventListener('click', () => showPostContent(post, imgMap, series));
  actions.appendChild(viewBtn);

  if (post.status !== 'posted' && post.status !== 'sending') {
    const postNowBtn = h('button', { cls: 'aap-icon-btn', title: 'Post now', 'aria-label': 'Post now' },
      icon('bi bi-send'));
    postNowBtn.addEventListener('click', () => postNow(post.id));
    actions.appendChild(postNowBtn);
  }

  if (post.status === 'draft' || post.status === 'failed') {
    const schedBtn = h('button', { cls: 'aap-icon-btn', title: 'Schedule', 'aria-label': 'Schedule' },
      icon('bi bi-calendar-plus'));
    schedBtn.addEventListener('click', () => {
      const pickerId = 'sched-picker-' + post.id;
      const existing = document.getElementById(pickerId);
      if (existing) { existing.remove(); return; }
      const dtInput = h('input', { type: 'datetime-local', cls: 'form-control aap-input', style: 'width:200px' });
      const base = post.scheduled_at
        ? new Date(post.scheduled_at.endsWith('Z') ? post.scheduled_at : post.scheduled_at + 'Z')
        : new Date(Date.now() + 3600000);
      dtInput.value = base.toISOString().slice(0, 16);
      const okBtn = h('button', { cls: 'btn aap-btn aap-btn-primary', text: 'Schedule' });
      okBtn.addEventListener('click', async () => {
        if (!dtInput.value) return;
        await schedulePost(post.id, new Date(dtInput.value).toISOString());
        picker.remove();
      });
      const cancelBtn = h('button', { cls: 'btn aap-btn', text: 'Cancel' });
      cancelBtn.addEventListener('click', () => picker.remove());
      const picker = h('div', { id: pickerId, cls: 'aap-card mt-2 d-flex align-items-center gap-2 flex-wrap' },
        dtInput, okBtn, cancelBtn);
      rowWrap.after(picker);
    });
    actions.appendChild(schedBtn);
  }

  if (post.status === 'scheduled') {
    const cancelBtn = h('button', { cls: 'aap-icon-btn', title: 'Cancel schedule', 'aria-label': 'Cancel schedule' },
      icon('bi bi-x-circle'));
    cancelBtn.addEventListener('click', () => cancelPostSchedule(post.id));
    actions.appendChild(cancelBtn);
  }

  if (post.status !== 'posted') {
    const editBtn = h('button', { cls: 'aap-icon-btn', title: 'Edit', 'aria-label': 'Edit post' },
      icon('bi bi-pencil'));
    editBtn.addEventListener('click', () => {
      const existing = document.getElementById('edit-form-' + post.id);
      if (existing) { existing.remove(); return; }
      const form = buildEditPostForm(post, imgMap, series,
        () => document.getElementById('edit-form-' + post.id)?.remove());
      form.id = 'edit-form-' + post.id;
      rowWrap.after(form);
    });
    actions.appendChild(editBtn);

    const delBtn = h('button', { cls: 'aap-icon-btn', title: 'Delete', 'aria-label': 'Delete post' },
      icon('bi bi-trash'));
    delBtn.addEventListener('click', () => deletePost(post.id));
    actions.appendChild(delBtn);
  }

  if (post.platform === 'instagram') {
    const storyChildren = [icon('bi bi-film')];
    if (post.story_status) {
      const si = STORY_STATUS_ICON[post.story_status];
      if (si) storyChildren.push(h('i', { cls: si.cls, style: 'font-size:9px;color:' + si.color }));
    }
    const storyBtn = h('button', {
      cls: 'aap-icon-btn',
      style: 'flex-direction:column;gap:1px;height:auto;padding:4px 6px;min-width:28px',
      title: post.story_id ? 'Story: ' + post.story_status : 'Create Story',
      'aria-label': 'Story',
      'data-story-btn': post.id,
    }, ...storyChildren);
    storyBtn.addEventListener('click', () => _openStoryModal(post, imgMap, series));
    actions.appendChild(storyBtn);
  }

  const rowWrap = h('article', {
    cls: 'aap-post-row',
    'data-post-row': post.id,
    'data-post-status': post.status,
  },
    thumbDiv,
    h('div', { cls: 'aap-post-row__info' },
      h('div', { cls: 'aap-post-row__title', text: post.title || '(no title)' }),
      platEl
    ),
    statusEl,
    actions
  );
  return rowWrap;
}

function buildEditPostForm(post, imgMap, series, onClose, onSave) {
  const allImages = series.images.filter(i => !i.deleted_at);
  const { grid: imgGrid, selected: _sel } = _buildImageSelector(allImages, post.image_ids || [], imgMap);

  const isTelegram = post.platform === 'telegram';

  // Shared description/tags inputs (placed in language-matched block)
  const descInput = h('textarea', { cls: 'form-control form-control-sm mb-1', rows: '3', placeholder: 'Description' });
  descInput.value = post.description || '';
  const tagsInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', placeholder: 'Tags' });
  tagsInput.value = (post.tags || []).join(' ');

  // EN block
  const titleInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', placeholder: 'Title (EN)' });
  titleInput.value = post.title || '';
  const collLineInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', placeholder: '◈ Collection line (leave blank to hide)' });
  collLineInput.value = post.collection_line || '';
  const enBlockChildren = [
    h('div', { cls: 'small fw-semibold mb-1 text-secondary', text: 'EN' }),
    titleInput,
  ];
  if (!isTelegram) { enBlockChildren.push(descInput, tagsInput); }
  enBlockChildren.push(collLineInput);
  const enBlock = h('div', { cls: 'border rounded p-2 mb-2' }, ...enBlockChildren);

  // RU block
  const titleRuInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', placeholder: 'Title (RU)' });
  titleRuInput.value = post.title_ru || '';
  const collLineRuInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', placeholder: '◈ Collection line RU (leave blank to hide)' });
  collLineRuInput.value = post.collection_line_ru || '';
  const ruBlockChildren = [
    h('div', { cls: 'small fw-semibold mb-1 text-secondary', text: 'RU' }),
    titleRuInput,
  ];
  if (isTelegram) { ruBlockChildren.push(descInput, tagsInput); }
  ruBlockChildren.push(collLineRuInput);
  const ruBlock = h('div', { cls: 'border rounded p-2 mb-2' }, ...ruBlockChildren);

  const saveBtn = h('button', { cls: 'btn btn-sm btn-primary me-1' });
  saveBtn.appendChild(icon('bi bi-floppy me-1'));
  saveBtn.appendChild(document.createTextNode('Save'));
  saveBtn.addEventListener('click', async () => {
    if (!_sel.size) { showToast('Select at least one image', 'danger'); return; }
    const imageIds = allImages.filter(i => _sel.has(i.id)).map(i => i.id);
    try {
      saveBtn.disabled = true;
      await apiFetch('PATCH', '/api/posts/' + post.id, {
        title: titleInput.value.trim(),
        title_ru: titleRuInput.value.trim(),
        description: descInput.value,
        tags: tagsInput.value.split(/\s+/).filter(Boolean),
        collection_line: collLineInput.value.trim() || null,
        collection_line_ru: collLineRuInput.value.trim() || null,
        image_ids: imageIds,
      });
      showToast('Post updated', 'success');
      onClose();
      if (onSave) { await onSave(); } else { await loadSeriesDetail(series.id); }
    } catch (e) { showToast(e.message, 'danger'); saveBtn.disabled = false; }
  });

  const cancelBtn = h('button', { cls: 'btn btn-sm btn-outline-secondary', text: 'Cancel', onclick: onClose });

  return h('div', { cls: 'border rounded p-2 mb-1 bg-body-tertiary' },
    h('div', { cls: 'small text-muted mb-1 fw-medium', text: 'Images' }), imgGrid,
    enBlock, ruBlock,
    h('div', null, saveBtn, cancelBtn));
}

function buildCreatePostForm(series, imgMap, onClose) {
  const allImages = series.images.filter(i => !i.deleted_at);
  // Seed from current strip selection; empty if nothing selected (user must pick explicitly)
  const initialSel = _selectedImages.size > 0
    ? allImages.filter(i => _selectedImages.has(i.id)).map(i => i.id)
    : [];
  const { grid: imgGrid, selected: _selectedPostImages } = _buildImageSelector(allImages, initialSel, imgMap);

  // Platform checkboxes
  const tgCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'pf_tg' });
  tgCheck.checked = true;
  const igCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'pf_ig' });
  igCheck.checked = true;
  const ptCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'pf_pt' });
  ptCheck.checked = false;

  const platformRow = h('div', { cls: 'd-flex gap-3 mb-2 align-items-center' },
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, tgCheck, document.createTextNode(' Telegram')),
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, igCheck, document.createTextNode(' Instagram & FB')),
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, ptCheck, document.createTextNode(' Pinterest')));

  // EN content fields
  const titleInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', id: 'pf_title', placeholder: 'Title (EN)' });
  titleInput.value = series.title || '';
  const descOtherInput = h('textarea', { cls: 'form-control form-control-sm mb-1', id: 'pf_desc_other', rows: '3', placeholder: 'Description (Instagram & FB)' });
  descOtherInput.value = series.description_en || '';
  const tagsOtherInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', id: 'pf_tags_other', placeholder: 'Tags (Instagram & FB)' });
  tagsOtherInput.value = (series.tags_instagram || []).join(' ');
  const collLineInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', id: 'pf_coll_line', placeholder: '◈ Collection line (leave blank to hide)' });
  if (series.collection) {
    const num = (series.collection_number || '').trim();
    collLineInput.value = num ? `◈ ${series.collection.name} — ${num}` : `◈ ${series.collection.name}`;
  }

  // RU content fields
  const titleRuInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', id: 'pf_title_ru', placeholder: 'Title (RU)' });
  titleRuInput.value = series.title_ru || series.title || '';
  const descTgInput = h('textarea', { cls: 'form-control form-control-sm mb-1', id: 'pf_desc_tg', rows: '3', placeholder: 'Description (Telegram)' });
  descTgInput.value = series.description_ru || '';
  const tagsTgInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', id: 'pf_tags_tg', placeholder: 'Tags (Telegram)' });
  tagsTgInput.value = (series.tags_telegram || []).join(' ');
  const collLineRuInput = h('input', { type: 'text', cls: 'form-control form-control-sm mb-1', id: 'pf_coll_line_ru', placeholder: '◈ Collection line RU (leave blank to hide)' });
  if (series.collection) {
    const num = (series.collection_number || '').trim();
    const nameRu = series.collection.name_ru || series.collection.name;
    collLineRuInput.value = num ? `◈ ${nameRu} — ${num}` : `◈ ${nameRu}`;
  }

  const schedInput = h('input', { type: 'datetime-local', cls: 'form-control form-control-sm mb-2', id: 'pf_sched' });

  // ── Shared payload builder ────────────────────────────────────────────────
  function _buildCreatePayload() {
    const platforms = [];
    if (tgCheck.checked) platforms.push('telegram');
    if (igCheck.checked) platforms.push('instagram');
    if (ptCheck.checked) platforms.push('pinterest');
    if (!platforms.length) { showToast('Select at least one platform', 'danger'); return null; }
    if (!_selectedPostImages.size) { showToast('Select at least one image', 'danger'); return null; }
    const imageIds = allImages.filter(i => _selectedPostImages.has(i.id)).map(i => i.id);
    return {
      platforms,
      title: titleInput.value.trim(),
      title_ru: titleRuInput.value.trim(),
      description_telegram: descTgInput.value,
      description_other: descOtherInput.value,
      tags_telegram: tagsTgInput.value.split(/\s+/).filter(Boolean),
      tags_other: tagsOtherInput.value.split(/\s+/).filter(Boolean),
      collection_line: collLineInput.value.trim() || null,
      collection_line_ru: collLineRuInput.value.trim() || null,
      image_ids: imageIds,
      scheduled_at: schedInput.value ? new Date(schedInput.value).toISOString() : null,
    };
  }

  // ── Save post(s) ──────────────────────────────────────────────────────────
  const saveBtn = h('button', { cls: 'btn btn-sm btn-primary me-1' });
  saveBtn.appendChild(icon('bi bi-save me-1'));
  saveBtn.appendChild(document.createTextNode('Save post(s)'));
  saveBtn.addEventListener('click', async () => {
    const payload = _buildCreatePayload();
    if (!payload) return;
    saveBtn.disabled = true;
    try {
      const posts = await apiFetch('POST', '/api/series/' + series.id + '/posts', payload);
      showToast(posts.length + ' post(s) created', 'success');
      onClose();
      await loadSeriesDetail(series.id);
    } catch (e) {
      showToast(e.message, 'danger');
      saveBtn.disabled = false;
    }
  });

  // ── Save & send ───────────────────────────────────────────────────────────
  const saveAndSendBtn = h('button', { cls: 'btn btn-sm btn-success me-1' });
  saveAndSendBtn.appendChild(icon('bi bi-send-fill me-1'));
  saveAndSendBtn.appendChild(document.createTextNode('Save & send'));
  saveAndSendBtn.addEventListener('click', async () => {
    const payload = _buildCreatePayload();
    if (!payload) return;
    saveAndSendBtn.disabled = true;
    try {
      const posts = await apiFetch('POST', '/api/series/' + series.id + '/posts', payload);
      // Fire posting for each platform — returns immediately (background task handles actual send).
      await Promise.all(posts.map(p =>
        apiFetch('POST', '/api/posts/' + p.id + '/post').catch(() => {})
      ));
      showToast(posts.length + ' post(s) sending…', 'info');
      onClose();
      await loadSeriesDetail(series.id);
      _startSendingPoller(series.id, { watchedPostIds: new Set(posts.map(p => p.id)) });
    } catch (e) {
      showToast(e.message, 'danger');
      saveAndSendBtn.disabled = false;
    }
  });

  const cancelBtn = h('button', { cls: 'btn btn-sm btn-outline-secondary', text: 'Cancel', onclick: onClose });

  const enBlock = h('div', { cls: 'border rounded p-2 mb-2' },
    h('div', { cls: 'small fw-semibold mb-1 text-secondary', text: 'EN' }),
    titleInput, descOtherInput, tagsOtherInput, collLineInput);

  const ruBlock = h('div', { cls: 'border rounded p-2 mb-2' },
    h('div', { cls: 'small fw-semibold mb-1 text-secondary', text: 'RU' }),
    titleRuInput, descTgInput, tagsTgInput, collLineRuInput);

  return h('div', { cls: 'border rounded p-2 mb-2 bg-body-tertiary' },
    h('div', { cls: 'small text-muted mb-1 fw-medium', text: 'Select images' }), imgGrid,
    h('div', { cls: 'small text-muted mb-1 fw-medium', text: 'Platforms' }), platformRow,
    enBlock, ruBlock,
    h('div', { cls: 'small text-muted mb-1 fw-medium', text: 'Schedule (optional)' }),
    schedInput,
    h('div', null, saveBtn, saveAndSendBtn, cancelBtn));
}

// ── Draft restore ─────────────────────────────────────────────────────────────
function restoreDraft(seriesId) {
  const raw = localStorage.getItem('draft_' + seriesId);
  if (!raw) return;
  try {
    const d = JSON.parse(raw);
    if (!App.currentSeries?.description_en && d.desc_en) {
      const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
      set('editorTitle', d.title); set('f_desc_en', d.desc_en); set('f_desc_ru', d.desc_ru);
      set('f_tags_ig', d.tags_ig); set('f_tags_tg', d.tags_tg);
    }
  } catch (_) {}
}

function _buildPostCaption(post) {
  const tags = (post.tags || []).join(' ');
  let parts;
  if (post.platform === 'telegram') {
    const title = post.title_ru || post.title;
    const collLine = post.collection_line_ru || post.collection_line;
    parts = [title, collLine, post.description, tags];
  } else {
    const archiveFooter = post.seo ? '—\nFiled under:\n' + post.seo : null;
    parts = [post.title, post.collection_line, post.description, archiveFooter, tags];
  }
  return parts.filter(Boolean).join('\n\n');
}

function showPostContent(post, imgMap, series) {
  const platIcon = POST_PLATFORM_ICON[post.platform] || 'bi bi-globe';
  document.getElementById('postViewPlatform').replaceChildren(
    h('span', { cls: 'd-flex align-items-center gap-1' },
      icon(platIcon + ' me-1'),
      h('span', { cls: 'fw-semibold text-capitalize', text: post.platform })
    )
  );

  const statusColor = POST_STATUS_COLOR[post.status] || 'bg-secondary';
  document.getElementById('postViewStatus').replaceChildren(
    h('span', { cls: 'badge ' + statusColor, text: post.status })
  );

  const timeEl = document.getElementById('postViewTime');
  if (post.posted_at) {
    timeEl.textContent = formatDate(post.posted_at);
  } else if (post.scheduled_at) {
    timeEl.textContent = 'Scheduled: ' + formatDate(post.scheduled_at);
  } else {
    timeEl.textContent = '';
  }

  const sections = [];

  // Images — look up full image objects so openLightbox gets public_url + id
  const postImages = (post.image_ids || [])
    .map(id => (series.images || []).find(img => img.id === id))
    .filter(Boolean);
  if (postImages.length) {
    sections.push(
      h('div', { cls: 'd-flex flex-wrap gap-2 mb-3' },
        ...postImages.map((img, i) =>
          h('img', {
            src: img.public_url,
            style: 'height:120px;width:120px;object-fit:cover;border-radius:6px;cursor:pointer',
            onclick: () => openLightbox(postImages, i)
          })
        )
      )
    );
  }

  // Full assembled caption as it appears on the platform
  const caption = _buildPostCaption(post);
  if (caption) {
    sections.push(
      h('pre', {
        style: 'white-space:pre-wrap;font-family:inherit;font-size:.9rem;' +
               'background:var(--bs-body-bg);border:1px solid var(--bs-border-color);' +
               'border-radius:6px;padding:.75rem;margin:0',
        text: caption
      })
    );
  }

  // Platform link (below caption).
  // Pinterest uses external_post_id (comma-separated pin IDs) since each pin gets
  // its own URL. All other platforms use post_url (the canonical permalink saved at
  // post time — correct for Instagram and Telegram). Fallback to a constructed
  // Facebook URL when post_url is absent (legacy posts pre-permalink storage).
  if (post.platform === 'pinterest' && post.external_post_id) {
    const pinIds = post.external_post_id.split(',').map(s => s.trim()).filter(Boolean);
    sections.push(h('div', { cls: 'd-flex flex-wrap gap-2 mt-2' },
      ...pinIds.map((pid, i) =>
        h('a', {
          href: 'https://www.pinterest.com/pin/' + pid + '/',
          target: '_blank',
          cls: 'btn btn-sm btn-outline-secondary'
        }, icon('bi bi-box-arrow-up-right me-1'), 'Pin ' + (i + 1))
      )
    ));
  } else if (post.post_url) {
    sections.push(h('div', { cls: 'mt-2' },
      h('a', { href: post.post_url, target: '_blank', cls: 'btn btn-sm btn-outline-secondary' },
        icon('bi bi-box-arrow-up-right me-1'), 'View on ' + post.platform)
    ));
  } else if (post.platform === 'facebook' && post.external_post_id) {
    sections.push(h('div', { cls: 'mt-2' },
      h('a', {
        href: 'https://www.facebook.com/' + post.external_post_id,
        target: '_blank',
        cls: 'btn btn-sm btn-outline-secondary'
      }, icon('bi bi-box-arrow-up-right me-1'), 'View on facebook')
    ));
  }

  if (post.error_message) {
    sections.push(h('div', { cls: 'alert alert-danger mt-2 py-2 small', text: post.error_message }));
  }

  document.getElementById('postViewBody').replaceChildren(...sections);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('postViewModal')).show();
}


// ── Stories ────────────────────────────────────────────────────────────────

const _TEXT_COLORS = [
  { hex: '#ffffff', label: 'White' },
  { hex: '#0e0e10', label: 'Ink' },
  { hex: '#f5e6d3', label: 'Cream' },
  { hex: '#b8501f', label: 'Accent' },
  { hex: '#9ab2c7', label: 'Steel' },
];

let _storyCtx = null;
let _allTextMode = false;
const _dirtyFrameIds = new Set();

function _markFrameDirty(frameId) {
  _dirtyFrameIds.add(frameId);
  const pill = document.querySelector('[data-unsaved-pill]');
  if (pill) pill.hidden = false;
}

function _openStoryModal(post, imgMap, series) {
  _dirtyFrameIds.clear();
  _allTextMode = false;
  const modalEl = document.getElementById('storyEditorModal');
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  document.getElementById('storyEditorTitle').textContent = post.title || 'Story';
  const body = document.getElementById('storyEditorBody');
  body.replaceChildren();
  _loadStoryModal(body, post, imgMap, series);
  // Save unsaved changes to localStorage on close (only sent to server on render)
  modalEl.addEventListener('hide.bs.modal', () => { if (_storyCtx) _saveDraftToLS(_storyCtx.story); }, { once: true });
  modal.show();
}

async function _flushDirtyFrames() {
  if (!_storyCtx || !_dirtyFrameIds.size) return;
  const { story } = _storyCtx;
  const ids = [..._dirtyFrameIds];
  _dirtyFrameIds.clear();
  for (const frameId of ids) {
    const frame = story.frames.find(f => f.id === frameId);
    if (!frame) continue;
    try {
      await apiFetch('PATCH', '/api/story-frames/' + frameId, {
        text: frame.text,
        title: frame.title,
        background_mode: frame.background_mode,
        text_color: frame.text_color,
        text_align: frame.text_align,
        title_position: frame.title_position,
        text_halign: frame.text_halign,
        font_size: frame.font_size,
        is_enabled: frame.is_enabled,
      });
    } catch (e) {
      showToast('Frame save failed: ' + e.message, 'danger');
    }
  }
}

function _lsKey(storyId) { return 'se_draft_' + storyId; }

function _saveDraftToLS(story) {
  if (!_dirtyFrameIds.size) { localStorage.removeItem(_lsKey(story.id)); return; }
  const draft = {};
  for (const fid of _dirtyFrameIds) {
    const f = story.frames.find(fr => fr.id === fid);
    if (f) draft[fid] = { text: f.text, title: f.title, background_mode: f.background_mode, text_color: f.text_color, text_align: f.text_align, title_position: f.title_position, text_halign: f.text_halign, font_size: f.font_size, is_enabled: f.is_enabled };
  }
  localStorage.setItem(_lsKey(story.id), JSON.stringify(draft));
}

function _loadDraftFromLS(story) {
  const raw = localStorage.getItem(_lsKey(story.id));
  if (!raw) return;
  try {
    const draft = JSON.parse(raw);
    for (const [fid, data] of Object.entries(draft)) {
      const f = story.frames.find(fr => fr.id === fid);
      if (!f) continue;
      Object.assign(f, data);
      _markFrameDirty(fid);
    }
  } catch (e) { /* ignore corrupt draft */ }
}

function _clearDraftFromLS(storyId) { localStorage.removeItem(_lsKey(storyId)); }

async function _loadStoryModal(body, post, imgMap, series) {
  if (post.story_id) {
    try {
      const story = await apiFetch('GET', '/api/stories/' + post.story_id);
      _storyCtx = { post, imgMap, story, frameIdx: 0 };
      _loadDraftFromLS(story);
      _renderStoryEditorV2(body);
    } catch (e) { showToast(e.message, 'danger'); }
  } else {
    _renderStoryPickerV2(body, post, imgMap, series);
  }
}

function _renderStoryPickerV2(body, post, imgMap, series) {
  const allImages = (post.image_ids || []).map((id, idx) => ({ id, url: imgMap[id], idx }));

  const checkboxes = allImages.map(({ id, url, idx }) => {
    const cb = h('input', { type: 'checkbox', cls: 'form-check-input', 'data-story-image-checkbox': id });
    if (idx < 4) cb.checked = true;
    const thumb = url
      ? h('img', { src: url, style: 'width:36px;height:36px;object-fit:cover;border-radius:3px;flex-shrink:0' })
      : h('span', { style: 'width:36px;height:36px;display:inline-block;background:var(--aap-panel-hi);border-radius:3px;flex-shrink:0' });
    const label = h('label', { cls: 'form-check-label d-flex align-items-center gap-2 mb-2', style: 'cursor:pointer' },
      cb, thumb, document.createTextNode('Image ' + (idx + 1)));
    return { cb, label, id };
  });

  const genBtn = h('button', {
    cls: 'va__btn va__btn--primary mt-2',
    text: 'Generate Story Draft',
    'data-story-generate-btn': post.id,
  });

  genBtn.addEventListener('click', async () => {
    const imageIds = checkboxes.filter(({ cb }) => cb.checked).map(({ id }) => id);
    if (!imageIds.length) { showToast('Select at least one image', 'warning'); return; }
    genBtn.disabled = true;
    genBtn.textContent = 'Generating…';
    try {
      const story = await apiFetch('POST', '/api/posts/' + post.id + '/stories', { image_ids: imageIds });
      post.story_id = story.id;
      const btn = document.querySelector('[data-story-btn="' + post.id + '"]');
      if (btn) btn.title = 'Story';
      _storyCtx = { post, imgMap, story, frameIdx: 0 };
      _renderStoryEditorV2(body);
    } catch (e) {
      showToast(e.message, 'danger');
      genBtn.disabled = false;
      genBtn.textContent = 'Generate Story Draft';
    }
  });

  body.replaceChildren(
    h('div', { cls: 'se-va', 'data-story-panel': post.id },
      h('div', { cls: 'fw-semibold small mb-1' }, 'Choose images (first 4 selected):'),
      h('div', {}, ...checkboxes.map(({ label }) => label)),
      genBtn
    )
  );
}

function _splitLastLine(text) {
  const lines = (text || '').split('\n');
  if (lines.length > 1) return [lines.slice(0, -1).join('\n'), lines[lines.length - 1]];
  const m = text.match(/^(.*[.!?…])\s+(.+)$/s);
  if (m) return [m[1], m[2]];
  return [text, ''];
}

function _splitFirstLine(text) {
  const lines = (text || '').split('\n');
  if (lines.length > 1) return [lines[0], lines.slice(1).join('\n')];
  const m = text.match(/^(.+?[.!?…])\s+(.+)$/s);
  if (m) return [m[1], m[2]];
  return [text, ''];
}

function _parseAndDistribute(value, frames) {
  const textFrames = frames.filter(f => f.frame_type === 'text');
  const sections = value.split(/^─+\s*frame\s+\d+\s*─+\s*$/m);
  sections.forEach((section, i) => {
    if (i >= textFrames.length) return;
    const f = textFrames[i];
    f.text = section.trim();
    f.rendered_url = null;
    _markFrameDirty(f.id);
  });
}

function _buildTextDragHandle(upperFrame, lowerFrame, upperTa, lowerTa) {
  const handle = h('div', { cls: 'va__drag-handle' },
    h('span', { cls: 'va__drag-handle__icon' }, '⠿')
  );
  const THRESHOLD = 28;
  let startY = 0;

  function onMove(currentY) {
    const dy = currentY - startY;
    const fit = () => [upperTa, lowerTa].forEach(ta => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; });
    if (dy > THRESHOLD) {
      // drag down → separator moves down → upper grows: first line of lower → end of upper
      const [taken, rest] = _splitFirstLine(lowerFrame.text || '');
      if (!taken) return;
      lowerFrame.text = rest; lowerFrame.rendered_url = null; _markFrameDirty(lowerFrame.id);
      upperFrame.text = (upperFrame.text ? upperFrame.text + '\n' : '') + taken;
      upperFrame.rendered_url = null; _markFrameDirty(upperFrame.id);
      upperTa.value = upperFrame.text; lowerTa.value = lowerFrame.text;
      fit(); startY = currentY;
    } else if (dy < -THRESHOLD) {
      // drag up → separator moves up → lower grows: last line of upper → start of lower
      const [rest, taken] = _splitLastLine(upperFrame.text || '');
      if (!taken) return;
      upperFrame.text = rest; upperFrame.rendered_url = null; _markFrameDirty(upperFrame.id);
      lowerFrame.text = taken + (lowerFrame.text ? '\n' + lowerFrame.text : '');
      lowerFrame.rendered_url = null; _markFrameDirty(lowerFrame.id);
      upperTa.value = upperFrame.text; lowerTa.value = lowerFrame.text;
      fit(); startY = currentY;
    }
  }

  handle.addEventListener('touchstart', e => { startY = e.touches[0].clientY; }, { passive: true });
  handle.addEventListener('touchmove', e => { onMove(e.touches[0].clientY); }, { passive: true });

  handle.addEventListener('mousedown', e => {
    startY = e.clientY;
    e.preventDefault();
    const onMouseMove = e => onMove(e.clientY);
    const onMouseUp = () => { document.removeEventListener('mousemove', onMouseMove); document.removeEventListener('mouseup', onMouseUp); };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  });

  return handle;
}

function _renderStoryEditorV2(body) {
  const { story, imgMap, post } = _storyCtx;
  const frameIdx = _storyCtx.frameIdx;
  const frames = story.frames;
  const frame = frames[frameIdx];

  const pill = h('span', {
    cls: 'se-va__pill' + (story.status === 'draft' ? ' se-va__pill--ghost' : ''),
    text: story.status.toUpperCase(),
  });

  const regenBtn = h('button', { cls: 'se-va__regen', text: 'Regenerate' });
  regenBtn.addEventListener('click', () => {
    _storyCtx = null;
    post.story_id = null;
    _renderStoryPickerV2(body, post, imgMap, null);
  });

  const allTextBtn = h('button', {
    cls: 'se-va__regen',
    text: _allTextMode ? '← Preview' : 'Edit all text',
    style: _allTextMode ? 'border-color:var(--aap-accent);color:var(--aap-accent)' : '',
    title: 'View and redistribute all frame text in one editor',
  });
  allTextBtn.addEventListener('click', () => { _allTextMode = !_allTextMode; _renderStoryEditorV2(body); });

  const resetBtn = h('button', {
    cls: 'se-va__regen',
    text: 'Reset',
    title: 'Discard unsaved changes and revert to last saved state',
  });
  resetBtn.addEventListener('click', async () => {
    _dirtyFrameIds.clear();
    _clearDraftFromLS(story.id);
    try {
      const fresh = await apiFetch('GET', '/api/stories/' + story.id);
      _storyCtx.story = fresh;
      _allTextMode = false;
      _renderStoryEditorV2(body);
    } catch (e) { showToast(e.message, 'danger'); }
  });

  const unsavedPill = h('span', { cls: 'se-va__unsaved', 'data-unsaved-pill': '', hidden: _dirtyFrameIds.size === 0 }, 'unsaved');
  const pillGroup = h('div', { style: 'display:flex;flex-direction:column;gap:3px' }, pill, unsavedPill);
  const topbar = h('div', { cls: 'se-va__topbar' }, pillGroup, h('span', { cls: 'se-va__rule' }), allTextBtn, resetBtn, regenBtn);

  // ── Option C: stacked text canvas with drag handles ────────────────────────
  if (_allTextMode) {
    const textFrames = frames.filter(f => f.frame_type === 'text');

    const _fitTa = ta => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; };

    // Build textareas first so handles can reference adjacent ones
    const items = textFrames.map(f => {
      const ta = h('textarea', { cls: 'va__textarea va__all-text__area' });
      ta.value = f.text || '';
      ta.addEventListener('input', () => { f.text = ta.value; f.rendered_url = null; _markFrameDirty(f.id); _fitTa(ta); });
      return { f, ta };
    });

    const canvas = h('div', { cls: 'va__all-text' });
    items.forEach(({ f, ta }, i) => {
      const frameNum = frames.indexOf(f) + 1;
      canvas.appendChild(h('div', { cls: 'va__all-text__label' }, `Frame ${frameNum}`));
      canvas.appendChild(ta);
      if (i < items.length - 1) {
        canvas.appendChild(_buildTextDragHandle(f, items[i + 1].f, ta, items[i + 1].ta));
      }
    });

    const renderBtnAll = h('button', { cls: 'va__btn va__btn--primary', text: 'Render Preview', 'data-story-render-btn': story.id });
    renderBtnAll.addEventListener('click', async () => {
      renderBtnAll.disabled = true; renderBtnAll.textContent = 'Saving…';
      try {
        await _flushDirtyFrames();
        _clearDraftFromLS(story.id);
        renderBtnAll.textContent = 'Rendering…';
        const updated = await apiFetch('POST', '/api/stories/' + story.id + '/render');
        _storyCtx.story = updated;
        _allTextMode = false;
        _renderStoryEditorV2(body);
        showToast('Rendered ' + updated.frames.filter(f => f.is_enabled).length + ' frames', 'success');
      } catch (e) { showToast(e.message, 'danger'); renderBtnAll.disabled = false; renderBtnAll.textContent = 'Render Preview'; }
    });

    body.replaceChildren(h('div', { cls: 'se-va', 'data-story-panel': post.id },
      topbar, canvas, h('div', { cls: 'va__foot' }, renderBtnAll)
    ));
    // Fit all textareas to content after DOM insertion
    items.forEach(({ ta }) => _fitTa(ta));
    return;
  }
  // ────────────────────────────────────────────────────────────────────────────

  const prevBtn = h('button', { cls: 'se-head__nav', 'aria-label': 'Previous' }, '‹');
  const nextBtn = h('button', { cls: 'se-head__nav', 'aria-label': 'Next' }, '›');
  prevBtn.disabled = frameIdx === 0;
  nextBtn.disabled = frameIdx === frames.length - 1;
  prevBtn.addEventListener('click', () => { _storyCtx.frameIdx = frameIdx - 1; _renderStoryEditorV2(body); });
  nextBtn.addEventListener('click', () => { _storyCtx.frameIdx = frameIdx + 1; _renderStoryEditorV2(body); });

  const numStr = String(frameIdx + 1).padStart(2, '0');
  const totalStr = String(frames.length).padStart(2, '0');
  const kindLabel = frame.frame_type === 'image' ? (frame.title ? 'cover slide' : 'image slide') : 'text slide';

  const head = h('div', { cls: 'se-head' },
    prevBtn,
    h('div', { cls: 'se-head__mid' },
      h('span', { cls: 'se-head__count' },
        document.createTextNode(numStr + ' '),
        h('strong', {}, '/ ' + totalStr)
      ),
      h('span', { cls: 'se-head__kind' }, kindLabel)
    ),
    nextBtn
  );

  const phone = h('div', { cls: 'va__phone' });
  _buildFramePreview(phone, frame, imgMap, _isLastTextFrame(frame));

  const rail = _buildRail(body, frame, imgMap);
  phone.appendChild(rail);

  if (frame.rendered_url) phone.style.cursor = 'zoom-in';

  // Tap zones + swipe on phone frame
  let _swipeX = 0;
  let _swipeMoved = false;
  phone.addEventListener('touchstart', e => {
    _swipeX = e.changedTouches[0].clientX;
    _swipeMoved = false;
  }, { passive: true });
  phone.addEventListener('touchmove', () => { _swipeMoved = true; }, { passive: true });
  phone.addEventListener('touchend', e => {
    if (e.target.closest('.se-rail')) return;
    const dx = e.changedTouches[0].clientX - _swipeX;
    if (_swipeMoved && Math.abs(dx) >= 40) {
      // swipe
      if (dx < 0 && frameIdx < frames.length - 1) { _storyCtx.frameIdx = frameIdx + 1; _renderStoryEditorV2(body); }
      else if (dx > 0 && frameIdx > 0) { _storyCtx.frameIdx = frameIdx - 1; _renderStoryEditorV2(body); }
    }
  }, { passive: true });

  phone.addEventListener('click', e => {
    if (e.target.closest('.se-rail')) return;
    const rect = phone.getBoundingClientRect();
    const xRatio = (e.clientX - rect.left) / rect.width;
    if (xRatio < 0.3 && frameIdx > 0) {
      _storyCtx.frameIdx = frameIdx - 1; _renderStoryEditorV2(body);
    } else if (xRatio > 0.7 && frameIdx < frames.length - 1) {
      _storyCtx.frameIdx = frameIdx + 1; _renderStoryEditorV2(body);
    } else if (frame.rendered_url) {
      // center tap → fullscreen
      const rendered = frames.filter(f => f.rendered_url);
      const idx = rendered.findIndex(f => f.id === frame.id);
      _openStoryFullscreen(rendered.map(f => f.rendered_url), idx);
    }
  });

  const showColorbar = frame.frame_type === 'text' || (frame.frame_type === 'image' && frame.title);
  const colorbar = showColorbar ? _buildColorBar(body, frame) : null;

  const strip = h('div', { cls: 'se-strip', 'data-story-frames': story.id });
  frames.forEach((f, i) => {
    const chip = h('div', {
      cls: 'se-strip__chip' + (i === frameIdx ? ' is-on' : '') + (!f.is_enabled ? ' is-off' : ''),
    },
      h('span', { cls: 'se-strip__num' }, String(i + 1).padStart(2, '0')),
      h('span', { cls: 'se-strip__kind' },
        f.frame_type === 'image' ? (f.title ? 'cover' : 'image') : 'text'),
      ...(!f.is_enabled ? [h('span', { cls: 'se-strip__skip' }, 'skip')] : [])
    );
    chip.addEventListener('click', () => { _storyCtx.frameIdx = i; _renderStoryEditorV2(body); });
    strip.appendChild(chip);
  });

  let controlEl = null;
  if (frame.frame_type === 'text') {
    const prevTextFrame = frames.slice(0, frameIdx).reverse().find(f => f.frame_type === 'text' && f.is_enabled);
    const nextTextFrame = frames.slice(frameIdx + 1).find(f => f.frame_type === 'text' && f.is_enabled);

    const fromPrevBtn = h('button', { cls: 'va__transfer-btn', title: 'Send first line to previous text frame' }, '↑ to prev');
    const updateToPrevState = () => {
      const [first] = _splitFirstLine(frame.text || '');
      fromPrevBtn.disabled = !prevTextFrame || !first;
    };
    updateToPrevState();
    fromPrevBtn.addEventListener('click', () => {
      const [taken, rest] = _splitFirstLine(frame.text || '');
      if (!taken) return;
      frame.text = rest; frame.rendered_url = null; _markFrameDirty(frame.id);
      prevTextFrame.text = (prevTextFrame.text ? prevTextFrame.text + '\n' : '') + taken;
      prevTextFrame.rendered_url = null; _markFrameDirty(prevTextFrame.id);
      _renderStoryEditorV2(body);
    });

    const textarea = h('textarea', { cls: 'va__textarea', rows: '4', 'data-story-frame-text': frame.id });
    textarea.value = frame.text || '';
    const charCount = h('span', { style: 'font-family:var(--aap-font-mono);font-size:11px;color:var(--aap-ink-mute);text-align:right;display:block' });
    const updateCount = () => { charCount.textContent = textarea.value.length; };
    updateCount();
    const toNextBtn = h('button', { cls: 'va__transfer-btn', title: 'Send last line to next text frame' }, '↓ to next');
    const updateToNextState = () => {
      const [, last] = _splitLastLine(frame.text || '');
      toNextBtn.disabled = !nextTextFrame || !last;
    };
    updateToNextState();

    textarea.addEventListener('input', () => {
      updateCount();
      frame.text = textarea.value;
      frame.rendered_url = null;
      _markFrameDirty(frame.id);
      _buildFramePreview(phone, frame, imgMap, _isLastTextFrame(frame));
      updateToPrevState();
      updateToNextState();
    });
    toNextBtn.addEventListener('click', () => {
      const [rest, taken] = _splitLastLine(frame.text || '');
      if (!taken) return;
      frame.text = rest; frame.rendered_url = null; _markFrameDirty(frame.id);
      nextTextFrame.text = taken + (nextTextFrame.text ? '\n' + nextTextFrame.text : '');
      nextTextFrame.rendered_url = null; _markFrameDirty(nextTextFrame.id);
      _renderStoryEditorV2(body);
    });

    controlEl = h('div', {}, fromPrevBtn, textarea, charCount, toNextBtn);
  } else {
    const titleInput = h('input', {
      type: 'text', cls: 'form-control',
      style: 'background:var(--aap-field-bg);border-color:var(--aap-rule);color:var(--aap-ink)',
      placeholder: 'Title (leave empty for no title)',
      'data-story-frame-title': frame.id,
    });
    titleInput.value = frame.title || '';
    titleInput.addEventListener('input', () => {
      frame.title = titleInput.value || null;
      frame.rendered_url = null;
      _markFrameDirty(frame.id);
      _buildFramePreview(phone, frame, imgMap, _isLastTextFrame(frame));
    });
    controlEl = titleInput;
  }

  const incCb = h('input', { type: 'checkbox', cls: 'form-check-input' });
  incCb.checked = frame.is_enabled;
  incCb.addEventListener('change', () => {
    frame.is_enabled = incCb.checked;
    _markFrameDirty(frame.id);
    const chip = strip.children[frameIdx];
    if (chip) {
      chip.classList.toggle('is-off', !incCb.checked);
      const skipEl = chip.querySelector('.se-strip__skip');
      if (!incCb.checked && !skipEl) chip.appendChild(h('span', { cls: 'se-strip__skip' }, 'skip'));
      else if (incCb.checked && skipEl) skipEl.remove();
    }
  });

  const includeRow = h('div', { cls: 'd-flex align-items-center gap-2' },
    h('label', { cls: 'form-check-label d-flex align-items-center gap-2', style: 'cursor:pointer;font-size:13px' },
      incCb, document.createTextNode('Include frame'))
  );

  const renderBtn = h('button', { cls: 'va__btn va__btn--primary', text: 'Render Preview', 'data-story-render-btn': story.id });
  renderBtn.addEventListener('click', async () => {
    renderBtn.disabled = true;
    renderBtn.textContent = 'Saving…';
    try {
      await _flushDirtyFrames();
      _clearDraftFromLS(story.id);
      renderBtn.textContent = 'Rendering…';
      const updated = await apiFetch('POST', '/api/stories/' + story.id + '/render');
      _storyCtx.story = updated;
      _renderStoryEditorV2(body);
      showToast('Rendered ' + updated.frames.filter(f => f.is_enabled).length + ' frames', 'success');
    } catch (e) {
      showToast(e.message, 'danger');
      renderBtn.disabled = false;
      renderBtn.textContent = 'Render Preview';
    }
  });

  const publishBtn = h('button', { cls: 'va__btn', text: 'Publish Stories', 'data-story-publish-btn': story.id });
  publishBtn.disabled = story.status !== 'rendered' && story.status !== 'failed';
  publishBtn.addEventListener('click', async () => {
    publishBtn.disabled = true;
    publishBtn.textContent = 'Publishing…';
    try {
      await apiFetch('POST', '/api/stories/' + story.id + '/publish');
      const seriesId = _storyCtx?.post?.series_id || App.currentSeriesId;
      bootstrap.Modal.getInstance(document.getElementById('storyEditorModal'))?.hide();
      if (seriesId) {
        _startSendingPoller(seriesId);
        await loadSeriesDetail(seriesId, { silent: true });
      }
    } catch (e) {
      showToast(e.message, 'danger');
      publishBtn.disabled = false;
      publishBtn.textContent = 'Publish Stories';
      _renderStoryEditorV2(body);
    }
  });

  // Font size slider (text frames + cover frames)
  const showSizeSlider = frame.frame_type === 'text' || (frame.frame_type === 'image' && frame.title);
  let sizeSlider = null;
  if (showSizeSlider) {
    const DEFAULT_SIZE = 64;
    const slider = h('input', { type: 'range', min: '32', max: '120', step: '4', style: 'flex:1;accent-color:var(--aap-accent)' });
    slider.value = String(frame.font_size || DEFAULT_SIZE);
    const sizeLabel = h('span', { style: 'font-family:var(--aap-font-mono);font-size:11px;color:var(--aap-ink-mute);min-width:28px;text-align:right' });
    sizeLabel.textContent = slider.value;
    slider.addEventListener('input', () => {
      const sz = parseInt(slider.value);
      sizeLabel.textContent = sz;
      frame.font_size = sz;
      frame.rendered_url = null;
      _markFrameDirty(frame.id);
      const phoneEl = body.querySelector('.va__phone');
      if (phoneEl) _buildFramePreview(phoneEl, frame, imgMap, _isLastTextFrame(frame));
    });

    const applyAllBtn = h('button', {
      style: 'font-family:var(--aap-font-mono);font-size:10px;color:var(--aap-ink-mute);background:transparent;border:1px solid var(--aap-rule);border-radius:4px;padding:2px 7px;cursor:pointer;white-space:nowrap',
      title: 'Apply this size to all frames',
    }, 'All');
    applyAllBtn.addEventListener('click', () => {
      const sz = parseInt(slider.value);
      const color = frame.text_color || null;
      const halign = frame.text_halign || null;
      frames.filter(f => f.frame_type === 'text').forEach(f => {
        f.font_size = sz;
        if (color) f.text_color = color;
        if (halign) f.text_halign = halign;
        f.rendered_url = null;
        _markFrameDirty(f.id);
      });
      const phoneEl = body.querySelector('.va__phone');
      if (phoneEl) _buildFramePreview(phoneEl, frame, imgMap, _isLastTextFrame(frame));
    });

    sizeSlider = h('div', { cls: 'd-flex align-items-center gap-2', style: 'padding:4px 0' },
      h('span', { style: 'font-family:var(--aap-font-mono);font-size:10px;color:var(--aap-ink-mute);letter-spacing:.1em;text-transform:uppercase;white-space:nowrap' }, 'Size'),
      slider,
      sizeLabel,
      applyAllBtn
    );
  }

  const children = [topbar, head, phone];
  if (colorbar) children.push(colorbar);
  if (sizeSlider) children.push(sizeSlider);
  const addTextFrameBtn = h('button', {
    cls: 'va__transfer-btn',
    title: 'Add a new text frame, splitting current text evenly',
    style: 'align-self:flex-end',
  }, '＋ text frame');
  addTextFrameBtn.addEventListener('click', async () => {
    addTextFrameBtn.disabled = true;
    addTextFrameBtn.textContent = 'Adding…';
    try {
      await _flushDirtyFrames();
      _clearDraftFromLS(story.id);
      const updated = await apiFetch('POST', '/api/stories/' + story.id + '/frames');
      _storyCtx.story = updated;
      _storyCtx.frameIdx = updated.frames.length - 1;
      _renderStoryEditorV2(body);
    } catch (e) {
      showToast(e.message, 'danger');
      addTextFrameBtn.disabled = false;
      addTextFrameBtn.textContent = '＋ text frame';
    }
  });

  children.push(strip, h('div', { cls: 'd-flex justify-content-end' }, addTextFrameBtn), includeRow);
  if (controlEl) children.push(controlEl);
  children.push(h('div', { cls: 'va__foot' }, renderBtn, publishBtn));

  body.replaceChildren(h('div', { cls: 'se-va', 'data-story-panel': post.id }, ...children));
}

function _isLastTextFrame(frame) {
  if (!_storyCtx) return false;
  const last = [..._storyCtx.story.frames].reverse().find(f => f.frame_type === 'text' && f.is_enabled);
  return !!last && last.id === frame.id;
}

function _buildFramePreview(phone, frame, imgMap, isLastTextFrame = false) {
  const savedRail = phone.querySelector('.se-rail');
  phone.replaceChildren();
  const bgUrl = (imgMap && frame.source_image_id) ? imgMap[frame.source_image_id] : '';

  if (frame.rendered_url) {
    const img = document.createElement('img');
    img.src = frame.rendered_url;
    img.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block';
    phone.appendChild(img);
    return;
  }

  if (frame.frame_type === 'image') {
    if (bgUrl) phone.appendChild(h('div', { cls: 'se-frame-bg', style: 'background-image:url(' + bgUrl + ')' }));
    else phone.appendChild(h('div', { style: 'position:absolute;inset:0;background:#1a1015' }));
    if (frame.title) {
      const pos = (frame.title_position === 'top' || frame.title_position === 'middle') ? frame.title_position : 'bottom';
      const barPos = 'se-frame-bar--' + pos;
      const PREVIEW_RATIO = 0.37;
      const sz = frame.font_size || 64;
      const titleStyle = 'color:' + (frame.text_color || '#ffffff') + ';font-size:' + Math.round(sz * 1.25 * PREVIEW_RATIO) + 'px;text-align:' + (frame.text_halign || 'center');
      const BAR_BG = { solid_dark: 'rgba(0,0,0,0.85)', solid_light: 'rgba(245,240,230,0.92)', solid_accent: 'rgba(184,80,31,0.92)', image_blur_dim: 'rgba(0,0,0,0.47)' };
      const bgMode = frame.background_mode || 'solid_dark';
      if (bgMode === 'image_clean') {
        // floating title — no bar, absolute text with shadow
        const alignCls = 'se-frame-text-block se-frame-text-block--' + pos;
        phone.appendChild(h('div', { cls: alignCls },
          h('div', { cls: 'se-frame-title', text: frame.title, style: titleStyle })
        ));
      } else {
        const barBg = BAR_BG[bgMode] || 'rgba(0,0,0,0.5)';
        phone.appendChild(h('div', { cls: 'se-frame-bar ' + barPos, style: 'background:' + barBg },
          h('div', { cls: 'se-frame-title', text: frame.title, style: titleStyle })
        ));
      }
    }
  } else {
    const mode = frame.background_mode || 'image_blur_dim';
    const SOLID_OVERLAY = { solid_dark: 'rgba(0,0,0,0.85)', solid_light: 'rgba(245,240,230,0.92)', solid_accent: 'rgba(184,80,31,0.92)' };
    if (SOLID_OVERLAY[mode]) {
      if (bgUrl) phone.appendChild(h('div', { cls: 'se-frame-bg', style: 'background-image:url(' + bgUrl + ')' }));
      else phone.appendChild(h('div', { style: 'position:absolute;inset:0;background:#1a1015' }));
      phone.appendChild(h('div', { style: 'position:absolute;inset:0;background:' + SOLID_OVERLAY[mode] }));
    } else {
      if (bgUrl) phone.appendChild(h('div', { cls: 'se-frame-bg' + (mode !== 'image_clean' ? ' se-frame-bg--blur' : ''), style: 'background-image:url(' + bgUrl + ')' }));
      else phone.appendChild(h('div', { style: 'position:absolute;inset:0;background:#1a1015' }));
      if (mode === 'image_blur_dim') phone.appendChild(h('div', { cls: 'se-frame-dim' }));
    }

    if (frame.text || frame.title) {
      const ALIGN_MAP = { top: 'se-frame-text-block--top', middle: 'se-frame-text-block--middle', bottom: 'se-frame-text-block--bottom' };
      const alignCls = ALIGN_MAP[frame.text_align || 'middle'] || 'se-frame-text-block--middle';
      const _ha = frame.text_halign || 'center';
      const _flexAlign = _ha === 'left' ? 'flex-start' : _ha === 'right' ? 'flex-end' : 'center';
      const textEl = h('div', { cls: 'se-frame-text-block ' + alignCls, style: 'align-items:' + _flexAlign });
      const color = frame.text_color || '#ffffff';
      const pRatio = 0.37;
      const pSz = frame.font_size || 64;
      if (frame.title) textEl.appendChild(h('div', { cls: 'se-frame-title mb-1', text: frame.title, style: 'color:' + color + ';font-size:' + Math.round(pSz * 1.25 * pRatio) + 'px;text-align:' + _ha }));
      if (frame.text) textEl.appendChild(h('div', { cls: 'se-frame-text', style: 'color:' + color + ';font-size:' + Math.round(pSz * pRatio) + 'px;text-align:' + _ha }, frame.text));
      phone.appendChild(textEl);
    }
    if (isLastTextFrame) {
      phone.appendChild(h('div', { cls: 'se-frame-label-latest', style: 'color:' + (frame.text_color || '#ffffff') }, '↘ latest post'));
    }
  }
  if (savedRail) phone.appendChild(savedRail);
}

function _buildRail(body, frame, imgMap) {
  let openPanel = null;
  const rail = h('div', { cls: 'se-rail' });

  const closePanel = () => {
    if (openPanel) { openPanel.remove(); openPanel = null; }
    document.removeEventListener('click', closeOnOutside);
  };
  const closeOnOutside = e => {
    if (!rail.contains(e.target)) closePanel();
  };

  // BG button
  if (frame.frame_type === 'text' || frame.title !== null) {
    const bgChip = h('span', { style: 'width:16px;height:16px;border-radius:999px;display:inline-block;box-shadow:inset 0 0 0 1px rgba(255,255,255,.45)' });
    _setBgChipStyle(bgChip, frame.background_mode, imgMap && imgMap[frame.source_image_id]);
    const bgBtn = h('button', { cls: 'se-rail__btn' }, bgChip, document.createTextNode('BG'));
    bgBtn.addEventListener('click', e => {
      e.stopPropagation();
      if (openPanel) { closePanel(); return; }
      const panel = h('div', { cls: 'se-rail__panel' });
      panel.appendChild(h('div', { cls: 'se-rail__panel-lbl' }, 'Background'));
      const opts = frame.frame_type === 'text'
        ? [['image_clean','Image'],['image_blur_dim','Blurred'],['solid_dark','Dark'],['solid_light','Light'],['solid_accent','Accent']]
        : [['solid_dark','Dark bar'],['solid_light','Light bar'],['solid_accent','Accent bar'],['image_blur_dim','Dim bar'],['image_clean','Floating']];
      opts.forEach(([val, lbl]) => {
        const chip = h('span', { cls: 'se-rail__pick-chip' });
        _setBgChipStyle(chip, val, imgMap && imgMap[frame.source_image_id]);
        const pick = h('button', { cls: 'se-rail__pick' + (frame.background_mode === val ? ' is-on' : '') }, chip, document.createTextNode(lbl));
        pick.addEventListener('click', () => {
          closePanel();
          frame.background_mode = val;
          frame.rendered_url = null;
          _markFrameDirty(frame.id);
          const phone = bgBtn.closest('.va__phone');
          if (phone) _buildFramePreview(phone, frame, imgMap, _isLastTextFrame(frame));
          _setBgChipStyle(bgChip, frame.background_mode, imgMap && imgMap[frame.source_image_id]);
        });
        panel.appendChild(pick);
      });
      bgBtn.after(panel);
      openPanel = panel;
      document.addEventListener('click', closeOnOutside);
    });
    rail.appendChild(h('div', { cls: 'se-rail__pop' }, bgBtn));
  }

  // Align button — hidden for image frames with no title (nothing to align)
  if (frame.frame_type === 'text' || frame.title) {
    const alignBtn = h('button', { cls: 'se-rail__btn' },
      h('span', { style: 'font-size:14px;line-height:1' }, '≡'),
      document.createTextNode('Align')
    );
    alignBtn.addEventListener('click', e => {
      e.stopPropagation();
      if (openPanel) { closePanel(); return; }
      const panel = h('div', { cls: 'se-rail__panel' });
      panel.appendChild(h('div', { cls: 'se-rail__panel-lbl' }, 'Position'));
      const opts = [['top','Top'],['middle','Middle'],['bottom','Bottom']];
      const current = frame.frame_type === 'text' ? (frame.text_align || 'middle') : (frame.title_position || 'bottom');
      opts.forEach(([val, lbl]) => {
        const pick = h('button', { cls: 'se-rail__pick' + (current === val ? ' is-on' : '') }, document.createTextNode(lbl));
        pick.addEventListener('click', () => {
          closePanel();
          if (frame.frame_type === 'text') frame.text_align = val;
          else frame.title_position = val;
          frame.rendered_url = null;
          _markFrameDirty(frame.id);
          const phone = alignBtn.closest('.va__phone');
          if (phone) _buildFramePreview(phone, frame, imgMap, _isLastTextFrame(frame));
        });
        panel.appendChild(pick);
      });
      alignBtn.after(panel);
      openPanel = panel;
      document.addEventListener('click', closeOnOutside);
    });
    rail.appendChild(h('div', { cls: 'se-rail__pop' }, alignBtn));
  }

  // H-Align button — horizontal text alignment (left / center / right)
  if (frame.frame_type === 'text' || frame.title) {
    const halignBtn = h('button', { cls: 'se-rail__btn' },
      h('span', { style: 'font-size:14px;line-height:1' }, '⇔'),
      document.createTextNode('H-Align')
    );
    halignBtn.addEventListener('click', e => {
      e.stopPropagation();
      if (openPanel) { closePanel(); return; }
      const panel = h('div', { cls: 'se-rail__panel' });
      panel.appendChild(h('div', { cls: 'se-rail__panel-lbl' }, 'H-Align'));
      const opts = [['left','Left'],['center','Center'],['right','Right']];
      const current = frame.text_halign || 'center';
      opts.forEach(([val, lbl]) => {
        const pick = h('button', { cls: 'se-rail__pick' + (current === val ? ' is-on' : '') }, document.createTextNode(lbl));
        pick.addEventListener('click', () => {
          closePanel();
          frame.text_halign = val;
          frame.rendered_url = null;
          _markFrameDirty(frame.id);
          const phone = halignBtn.closest('.va__phone');
          if (phone) _buildFramePreview(phone, frame, imgMap, _isLastTextFrame(frame));
        });
        panel.appendChild(pick);
      });
      halignBtn.after(panel);
      openPanel = panel;
      document.addEventListener('click', closeOnOutside);
    });
    rail.appendChild(h('div', { cls: 'se-rail__pop' }, halignBtn));
  }

  return rail;
}

function _setBgChipStyle(el, mode, imageUrl) {
  el.style.backgroundImage = '';
  el.style.filter = '';
  if (mode === 'solid_dark') { el.style.background = '#121212'; return; }
  if (mode === 'solid_light') { el.style.background = '#f0ede7'; return; }
  if (mode === 'solid_accent') { el.style.background = '#b8501f'; return; }
  if (imageUrl) {
    el.style.background = '';
    el.style.backgroundImage = 'url(' + imageUrl + ')';
    el.style.backgroundSize = 'cover';
    el.style.backgroundPosition = 'center';
    if (mode === 'image_blur_dim') el.style.filter = 'blur(1.5px)';
  } else {
    el.style.background = '#333';
  }
}

function _buildColorBar(body, frame) {
  const swatches = _TEXT_COLORS.map(({ hex }) => {
    const chip = h('span', { cls: 'se-swatch__chip', style: 'background:' + hex });
    const swatch = h('button', { cls: 'se-swatch' + (frame.text_color === hex ? ' is-on' : ''), 'data-color-hex': hex }, chip);
    swatch.addEventListener('click', () => {
      frame.text_color = hex;
      frame.rendered_url = null;
      _markFrameDirty(frame.id);
      body.querySelectorAll('.se-swatch').forEach(s => s.classList.toggle('is-on', s.dataset.colorHex === hex));
      const phone = body.querySelector('.va__phone');
      if (phone && _storyCtx) _buildFramePreview(phone, frame, _storyCtx.imgMap, _isLastTextFrame(frame));
    });
    return swatch;
  });
  return h('div', { cls: 'va__colorbar' },
    h('span', { cls: 'va__colorbar-lbl' }, 'Text'),
    ...swatches
  );
}

function _openStoryFullscreen(urls, startIdx) {
  let idx = startIdx ?? 0;
  const overlay = h('div', {
    style: 'position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:2000;display:flex;align-items:center;justify-content:center',
  });
  const img = document.createElement('img');
  img.style.cssText = 'max-width:calc(100% - 96px);max-height:100%;object-fit:contain;display:block';
  const counter = h('div', {
    style: 'position:absolute;top:12px;left:50%;transform:translateX(-50%);color:#fff;font-size:13px;opacity:.7;pointer-events:none',
  });
  const btnStyle = 'position:absolute;top:50%;transform:translateY(-50%);background:rgba(0,0,0,.45);border:none;color:#fff;font-size:28px;padding:8px 14px;cursor:pointer;border-radius:4px;line-height:1;user-select:none';
  const prevBtn = h('button', { style: btnStyle + ';left:12px', 'aria-label': 'Previous' }, '‹');
  const nextBtn = h('button', { style: btnStyle + ';right:12px', 'aria-label': 'Next' }, '›');
  function render() {
    img.src = urls[idx];
    const single = urls.length <= 1;
    prevBtn.style.display = single ? 'none' : '';
    nextBtn.style.display = single ? 'none' : '';
    counter.textContent = single ? '' : (idx + 1) + ' / ' + urls.length;
  }
  prevBtn.addEventListener('click', e => { e.stopPropagation(); idx = (idx - 1 + urls.length) % urls.length; render(); });
  nextBtn.addEventListener('click', e => { e.stopPropagation(); idx = (idx + 1) % urls.length; render(); });
  const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey); };
  overlay.addEventListener('click', close);
  function onKey(e) {
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft')  { idx = (idx - 1 + urls.length) % urls.length; render(); }
    else if (e.key === 'ArrowRight') { idx = (idx + 1) % urls.length; render(); }
  }
  document.addEventListener('keydown', onKey);
  overlay.append(img, prevBtn, nextBtn, counter);
  render();
  document.body.appendChild(overlay);
}
