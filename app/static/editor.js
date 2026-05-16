// ── Selection state ───────────────────────────────────────────────────────────
let _selectedImages = new Set();

// Single document-level listener for closing the collection picker panel.
// Stored here so it is added once and never accumulates.
let _activeCollPickerHide = null;
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

function _updateSaveStatusBtn() {
  const btn = document.getElementById('saveStatusBtn');
  const sel = document.getElementById('statusSelect');
  if (!btn || !sel || !App.currentSeries) return;
  const dirty = sel.value !== App.currentSeries.status;
  btn.classList.toggle('btn-primary', dirty);
  btn.classList.toggle('btn-outline-primary', !dirty);
}

// ── Editor entry point ────────────────────────────────────────────────────────
function renderEditor(series) {
  _selectedImages = new Set(series.images.filter(i => i.status === 'queued').map(i => i.id));
  App.activeVariantId = series.chosen_variant_id || null;

  const titleInput = h('input', {
    type: 'text', cls: 'form-control form-control-sm fw-semibold',
    id: 'editorTitle', placeholder: 'Series name (internal)...',
  });
  titleInput.value = series.name || series.title || '';
  titleInput.addEventListener('blur', () => saveTitle(series.id));

  const titleRow = h('div', { cls: 'd-flex align-items-center gap-2 mb-2' }, titleInput);
  if (series.original_folder_name) {
    const note = h('span', { cls: 'text-muted small text-truncate flex-shrink-1', style: 'max-width:180px', text: series.original_folder_name });
    note.title = series.original_folder_name;
    titleRow.appendChild(note);
  }

  document.getElementById('editorPanel').replaceChildren(
    titleRow,
    buildCollectionPicker(series),
    buildImagesCard(series),
    buildDescriptionsCard(series),
    buildGenerateCard(series.id),
    buildActionsCard(series),
    buildPostsCard(series),
  );

  initImageSortable(series.id);
  restoreDraft(series.id);
  document.getElementById('editorTitle')?.addEventListener('input', _updateSaveDescBtn);
  _updateSaveDescBtn();
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

// ── Images card ───────────────────────────────────────────────────────────────
function buildImagesCard(series) {
  const addBtn = h('button', { cls: 'btn btn-xs btn-outline-secondary' });
  addBtn.appendChild(icon('bi bi-plus'));
  addBtn.appendChild(document.createTextNode(' Add'));
  addBtn.addEventListener('click', () => addImages(series.id));

  const headerLabel = h('span', { cls: 'small fw-medium', id: 'imagesCardLabel' });
  headerLabel.appendChild(icon('bi bi-images me-1'));
  headerLabel.appendChild(document.createTextNode(_imagesCountLabel(series.images.length)));

  const strip = h('div', { id: 'imageStrip', cls: 'd-flex gap-2', style: 'min-height:160px;overflow-x:auto;flex-wrap:nowrap;padding-bottom:4px' });
  if (!series.images.length) {
    strip.appendChild(h('span', { cls: 'text-muted small align-self-center p-2', text: 'No images yet' }));
  } else {
    const _group = s => _selectedImages.has(s.id) ? 0 : s.status === 'posted' ? 2 : s.status === 'skip' ? 3 : 1;
    [...series.images].sort((a, b) => _group(a) - _group(b))
      .forEach(img => strip.appendChild(buildThumb(img, series.id)));
  }

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header d-flex justify-content-between align-items-center py-2' }, headerLabel, addBtn),
    h('div', { cls: 'card-body p-2' }, strip, buildActionBar(series.id)));
}

function _imagesCountLabel(total) {
  const sel = _selectedImages.size;
  return sel > 0
    ? 'Images (' + sel + ' selected / ' + total + ')'
    : 'Images (' + total + ')';
}

function _refreshImagesHeader(total) {
  const el = document.getElementById('imagesCardLabel');
  if (!el) return;
  el.replaceChildren(icon('bi bi-images me-1'), document.createTextNode(_imagesCountLabel(total)));
}

function buildThumb(img, seriesId) {
  const imgEl = document.createElement('img');
  imgEl.setAttribute('src', img.public_url);
  imgEl.className = 'rounded';
  imgEl.style.cssText = 'width:160px;height:140px;object-fit:cover';
  imgEl.loading = 'lazy';
  imgEl.setAttribute('draggable', 'false');
  imgEl.style.cursor = 'zoom-in';
  imgEl.addEventListener('click', e => {
    e.stopPropagation();
    const strip = document.getElementById('imageStrip');
    const thumbs = [...strip.querySelectorAll('[data-image-id]')];
    const images = thumbs.map(el => ({
      id: el.dataset.imageId,
      public_url: el.querySelector('img').getAttribute('src'),
      status: el.dataset.imageStatus || 'pending',
    }));
    const idx = thumbs.findIndex(el => el.dataset.imageId === img.id);
    openLightbox(images, idx >= 0 ? idx : 0);
  });

  const menuBtn = h('button', { cls: 'btn btn-xs btn-dark opacity-75', text: '⋯' });
  menuBtn.setAttribute('data-bs-toggle', 'dropdown');
  menuBtn.addEventListener('click', e => e.stopPropagation());

  const dropItems = document.createElement('ul');
  dropItems.className = 'dropdown-menu dropdown-menu-end';

  // "Move to" header + items
  const hdr = document.createElement('li');
  hdr.appendChild(h('h6', { cls: 'dropdown-header', text: 'Move to' }));
  dropItems.appendChild(hdr);
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

  const gripEl = h('div', { cls: 'thumb-grip position-absolute' });
  gripEl.appendChild(icon('bi bi-grip-vertical'));

  const statusBtn = h('button', {
    cls: 'btn btn-xs position-absolute top-0 start-0 m-1 p-1 border-0 bg-transparent',
    style: 'line-height:1',
    'data-select-btn': img.id,
  });
  statusBtn.appendChild(icon(_selectIcon(img.id, img.status)));
  statusBtn.addEventListener('click', e => {
    e.stopPropagation();
    _toggleSelection(img.id, img.status, seriesId);
  });

  const isSelected = _selectedImages.has(img.id);
  const outerCls = 'position-relative flex-shrink-0' +
    (img.status === 'posted' ? ' thumb-posted' : '') +
    (img.status === 'skip' ? ' thumb-skip' : '') +
    (isSelected ? ' thumb-selected' : '');
  return h('div', { cls: outerCls, 'data-image-id': img.id, 'data-image-status': img.status },
    imgEl,
    statusBtn,
    gripEl,
    h('div', { cls: 'position-absolute top-0 end-0 m-1' },
      h('div', { cls: 'dropdown' }, menuBtn, dropItems)));
}

function _selectIcon(imgId, status) {
  if (_selectedImages.has(imgId)) return 'bi bi-check-circle-fill text-primary fs-5';
  if (status === 'posted') return 'bi bi-check-circle-fill text-success fs-5';
  return 'bi bi-circle text-white fs-5';
}

function _toggleSelection(imgId, imgStatus, seriesId) {
  if (imgStatus === 'posted') return;
  const isNowSelected = !_selectedImages.has(imgId);
  if (isNowSelected) _selectedImages.add(imgId); else _selectedImages.delete(imgId);
  const btn = document.querySelector('[data-select-btn="' + imgId + '"]');
  if (btn) { btn.replaceChildren(icon(_selectIcon(imgId, imgStatus))); }
  const thumb = document.querySelector('[data-image-id="' + imgId + '"]');
  if (thumb) thumb.classList.toggle('thumb-selected', isNowSelected);
  _resortStrip();
  const total = App.currentSeries?.images?.length ?? 0;
  _refreshImagesHeader(total);
  _refreshActionBar(seriesId);
  _lightboxSyncSelectBtn(imgId);
}

function _resortStrip() {
  const strip = document.getElementById('imageStrip');
  if (!strip) return;
  const thumbs = [...strip.querySelectorAll('[data-image-id]')];
  if (!thumbs.length) return;
  const _g = el => {
    if (_selectedImages.has(el.dataset.imageId)) return 0;
    const s = el.dataset.imageStatus || 'pending';
    return s === 'posted' ? 2 : s === 'skip' ? 3 : 1;
  };
  thumbs
    .map((el, i) => ({ el, g: _g(el), i }))
    .sort((a, b) => a.g - b.g || a.i - b.i)
    .forEach(({ el }) => strip.appendChild(el));
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
  const bar = h('div', { id: 'imageActionBar', cls: 'd-flex align-items-center gap-2 flex-wrap mt-2 pt-2 border-top' });
  if (_selectedImages.size === 0) { bar.classList.add('d-none'); return bar; }

  bar.appendChild(h('span', { cls: 'small text-muted', text: _selectedImages.size + ' selected' }));

  // Move to dropdown
  const moveBtn = h('button', { cls: 'btn btn-xs btn-outline-secondary' });
  moveBtn.appendChild(icon('bi bi-box-arrow-right me-1'));
  moveBtn.appendChild(document.createTextNode('Move to…'));
  moveBtn.setAttribute('data-bs-toggle', 'dropdown');

  const moveDropItems = document.createElement('ul');
  moveDropItems.className = 'dropdown-menu';
  buildMoveToItems(null, seriesId, true).forEach(li => moveDropItems.appendChild(li));

  bar.appendChild(h('div', { cls: 'dropdown' }, moveBtn, moveDropItems));

  // Skip / Unskip — shown based on what's selected
  const statusMap = new Map((App.currentSeries?.images ?? []).map(i => [i.id, i.status]));
  const toSkip   = [..._selectedImages].filter(id => { const s = statusMap.get(id); return s && s !== 'skip' && s !== 'posted'; });
  const toUnskip = [..._selectedImages].filter(id => statusMap.get(id) === 'skip');

  const _mkStatusAction = (label, iconCls, ids, newStatus) => {
    const btn = h('button', { cls: 'btn btn-xs btn-outline-secondary' });
    btn.appendChild(icon(iconCls + ' me-1'));
    btn.appendChild(document.createTextNode(label));
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

  if (toSkip.length > 0)   bar.appendChild(_mkStatusAction('Skip',   'bi bi-eye-slash', toSkip,   'skip'));
  if (toUnskip.length > 0) bar.appendChild(_mkStatusAction('Unskip', 'bi bi-eye',       toUnskip, 'pending'));

  // Delete selected
  const delBtn = h('button', { cls: 'btn btn-xs btn-outline-danger' });
  delBtn.appendChild(icon('bi bi-trash me-1'));
  delBtn.appendChild(document.createTextNode('Delete'));
  delBtn.addEventListener('click', () => {
    showConfirm('Delete ' + _selectedImages.size + ' image(s)?', async () => {
      try {
        const toDelete = [..._selectedImages];
        await Promise.all(toDelete.map(id => apiFetch('DELETE', '/api/images/' + id)));
        const updated = await apiFetch('GET', '/api/series/' + seriesId);
        App.currentSeries = updated;
        renderEditor(updated);
        showToast('Moved to Trash', 'success');
      } catch (e) { showToast(e.message, 'danger'); }
    });
  });
  bar.appendChild(delBtn);

  // Save (persist selection as queued)
  const saveBtn = h('button', { cls: 'btn btn-xs btn-outline-primary' });
  saveBtn.appendChild(icon('bi bi-floppy me-1'));
  saveBtn.appendChild(document.createTextNode('Save'));
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
  if (old) old.replaceWith(buildActionBar(seriesId));
}

let _sortable = null;
let _lightboxImages = [];
let _lightboxIdx    = 0;
let _lightboxOpen   = false;

function initImageSortable(seriesId) {
  const strip = document.getElementById('imageStrip');
  if (!strip) return;
  if (_sortable) { _sortable.destroy(); _sortable = null; }
  const touch = window.matchMedia('(pointer: coarse)').matches;
  _sortable = Sortable.create(strip, {
    animation: 150,
    ghostClass: 'sortable-ghost',
    ...(touch
      ? { delay: 300, forceFallback: true, touchStartThreshold: 8 }
      : { handle: '.thumb-grip', touchStartThreshold: 4 }),
    onEnd: async () => {
      const ids = [...strip.querySelectorAll('[data-image-id]')].map(el => el.dataset.imageId);
      try {
        await apiFetch('PUT', '/api/series/' + seriesId + '/images/reorder', { image_ids: ids });
      } catch (e) { showToast('Reorder failed: ' + e.message, 'danger'); }
    },
  });
  if (touch) strip.addEventListener('contextmenu', e => e.preventDefault());
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
      // preserve frontend selection across re-render; remove patched image if it became skip/posted
      const savedSelection = new Set(_selectedImages);
      if (newStatus === 'skip' || newStatus === 'posted') savedSelection.delete(img.id);
      App.currentSeries = updated;
      renderEditor(updated);
      // restore selection (renderEditor re-inits from DB queued; we override with saved)
      _selectedImages = savedSelection;
      _lightboxRender();
    } catch (err) { showToast(err.message, 'danger'); }
  }

  document.getElementById('lightboxQueueBtn').addEventListener('click', () => {
    const img = _lightboxImages[_lightboxIdx];
    if (img.status === 'posted') return;
    const seriesId = App.currentSeriesId;
    _toggleSelection(img.id, img.status, seriesId);
    _lightboxRender();
  });
  document.getElementById('lightboxSkipBtn').addEventListener('click', () => {
    const img = _lightboxImages[_lightboxIdx];
    _lightboxPatch(img.status === 'skip' ? 'pending' : 'skip');
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
  document.getElementById('lightboxCounter').textContent =
    (_lightboxIdx + 1) + ' / ' + _lightboxImages.length;
  const single = _lightboxImages.length <= 1;
  document.getElementById('lightboxPrev').classList.toggle('invisible', single);
  document.getElementById('lightboxNext').classList.toggle('invisible', single);

  const qBtn = document.getElementById('lightboxQueueBtn');
  const isSelected = _selectedImages.has(img.id);
  qBtn.replaceChildren(icon(isSelected ? 'bi bi-check-circle-fill me-1' : 'bi bi-circle me-1'),
    document.createTextNode(isSelected ? 'Deselect' : 'Select'));
  qBtn.disabled = img.status === 'posted';

  const sBtn = document.getElementById('lightboxSkipBtn');
  const isSkip = img.status === 'skip';
  sBtn.replaceChildren(icon(isSkip ? 'bi bi-eye me-1' : 'bi bi-eye-slash me-1'),
    document.createTextNode(isSkip ? 'Unskip' : 'Skip'));

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

async function deleteVariant(variantId) {
  try {
    const updated = await apiFetch('DELETE', '/api/ai_variants/' + variantId);
    App.currentSeries = updated;
    renderEditor(updated);
    showToast('Variant deleted', 'success');
  } catch (e) { showToast(e.message, 'danger'); }
}

// ── Descriptions card ─────────────────────────────────────────────────────────
function buildDescriptionsCard(series) {
  const variants = series.ai_variants || [];
  const variantBtns = h('div', { cls: 'd-flex gap-1 flex-wrap mb-2' });
  if (!variants.length) {
    variantBtns.appendChild(h('p', { cls: 'text-muted small mb-2', text: 'No AI variants yet.' }));
  } else {
    variants.forEach((v, i) => {
      const btn = h('button', {
        cls: 'btn btn-xs ' + (v.id === series.chosen_variant_id ? 'btn-primary' : 'btn-outline-secondary'),
        'data-variant-idx': String(i),
        onclick: () => applyVariant(i),
      });
      btn.appendChild(document.createTextNode('V' + (variants.length - i) + ' '));
      btn.appendChild(h('span', { cls: 'opacity-75', style: 'font-size:12px', text: v.model }));
      const delBtn = h('button', {
        cls: 'btn btn-xs btn-outline-danger px-1',
        title: 'Delete variant',
        onclick: (e) => { e.stopPropagation(); deleteVariant(v.id); },
      });
      delBtn.appendChild(document.createTextNode('×'));
      variantBtns.appendChild(h('span', { style: 'display:inline-flex;gap:2px;align-items:center' }, btn, delBtn));
    });
  }

  const descEn = h('textarea', { cls: 'form-control form-control-sm', id: 'f_desc_en', rows: '4' });
  descEn.value = series.description_en || '';
  const descRu = h('textarea', { cls: 'form-control form-control-sm', id: 'f_desc_ru', rows: '4' });
  descRu.value = series.description_ru || '';
  const tagsIg = h('textarea', { cls: 'form-control form-control-sm', id: 'f_tags_ig', rows: '2' });
  tagsIg.value = (series.tags_instagram || []).join(' ');
  const tagsTg = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_tags_tg' });
  tagsTg.value = (series.tags_telegram || []).join(' ');

  const pubTitle = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_pub_title', placeholder: 'Publication title (pre-fills new posts)' });
  pubTitle.value = series.title || '';
  const pubTitleRu = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_pub_title_ru', placeholder: 'Publication title RU (pre-fills Telegram posts)' });
  pubTitleRu.value = series.title_ru || '';

  const _chosenVariant = series.chosen_variant_id
    ? (series.ai_variants || []).find(v => v.id === series.chosen_variant_id)
    : null;
  const _chosenArch = _chosenVariant?.archive_metadata || {};

  const igSeo = h('textarea', { cls: 'form-control form-control-sm', id: 'f_instagram_seo', rows: '2' });
  igSeo.value = _chosenVariant?.instagram_seo || '';
  const pinTitle = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_pin_title' });
  pinTitle.value = _chosenVariant?.pinterest_title || '';
  const pinDesc = h('textarea', { cls: 'form-control form-control-sm', id: 'f_pin_desc', rows: '2' });
  pinDesc.value = _chosenVariant?.pinterest_description || '';
  const pinBoard = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_pin_board' });
  pinBoard.value = _chosenVariant?.pinterest_board || '';
  const archWorld = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_arch_world', placeholder: 'comma-separated' });
  archWorld.value = (_chosenArch.world_keywords || []).join(', ');
  const archVisual = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_arch_visual', placeholder: 'comma-separated' });
  archVisual.value = (_chosenArch.visual_keywords || []).join(', ');
  const archMood = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'f_arch_mood', placeholder: 'comma-separated' });
  archMood.value = (_chosenArch.mood_keywords || []).join(', ');

  const saveBtn = h('button', { cls: 'btn btn-sm btn-outline-primary', id: 'saveDescBtn' });
  saveBtn.appendChild(icon('bi bi-floppy me-1'));
  saveBtn.appendChild(document.createTextNode('Save'));
  saveBtn.addEventListener('click', () => saveDescription(series.id));

  const resetBtn = h('button', { cls: 'btn btn-sm btn-outline-secondary ms-2' });
  resetBtn.appendChild(icon('bi bi-arrow-counterclockwise me-1'));
  resetBtn.appendChild(document.createTextNode('Reset'));
  resetBtn.addEventListener('click', resetToSaved);

  const mkField = (lbl, ctrl) => h('div', { cls: 'col-12 col-lg-6' },
    h('label', { cls: 'form-label small mb-0', text: lbl }), ctrl);

  const form = h('div', { cls: 'row g-2' },
    h('div', { cls: 'col-12 col-lg-6' }, h('label', { cls: 'form-label small mb-0', text: 'Publication title EN (pre-fills posts)' }), pubTitle),
    h('div', { cls: 'col-12 col-lg-6' }, h('label', { cls: 'form-label small mb-0', text: 'Publication title RU (pre-fills Telegram posts)' }), pubTitleRu),
    mkField('Description EN (Instagram & FB Page)', descEn),
    mkField('Description RU (Telegram)', descRu),
    mkField('Instagram & FB Page tags', tagsIg),
    h('div', { cls: 'col-12 col-lg-6' }, h('label', { cls: 'form-label small mb-0', text: 'Telegram tags' }), tagsTg),
    h('div', { cls: 'col-12' }, saveBtn, resetBtn));

  form.addEventListener('input', _updateSaveDescBtn);

  const semDetails = document.createElement('details');
  semDetails.className = 'mt-2';
  const semSummary = document.createElement('summary');
  semSummary.className = 'small text-muted';
  semSummary.textContent = 'Semantic Layer';
  semDetails.appendChild(semSummary);
  const semGrid = h('div', { cls: 'row g-2 mt-1' },
    h('div', { cls: 'col-12' }, h('label', { cls: 'form-label small mb-0', text: 'Instagram discovery' }), igSeo),
    h('div', { cls: 'col-12 col-lg-6' }, h('label', { cls: 'form-label small mb-0', text: 'Pinterest title' }), pinTitle),
    h('div', { cls: 'col-12 col-lg-6' }, h('label', { cls: 'form-label small mb-0', text: 'Pinterest board' }), pinBoard),
    h('div', { cls: 'col-12' }, h('label', { cls: 'form-label small mb-0', text: 'Pinterest description' }), pinDesc),
    h('div', { cls: 'col-12 col-lg-4' }, h('label', { cls: 'form-label small mb-0', text: 'Archive: world keywords' }), archWorld),
    h('div', { cls: 'col-12 col-lg-4' }, h('label', { cls: 'form-label small mb-0', text: 'Archive: visual keywords' }), archVisual),
    h('div', { cls: 'col-12 col-lg-4' }, h('label', { cls: 'form-label small mb-0', text: 'Archive: mood keywords' }), archMood));
  semDetails.appendChild(semGrid);

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-card-text me-1'));
  headerLabel.appendChild(document.createTextNode('Descriptions'));

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header py-2' }, headerLabel),
    h('div', { cls: 'card-body p-2' }, variantBtns, form, semDetails));
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
  set('f_instagram_seo', '');
  set('f_pin_title', '');
  set('f_pin_desc', '');
  set('f_pin_board', '');
  set('f_arch_world', '');
  set('f_arch_visual', '');
  set('f_arch_mood', '');
  App.activeVariantId = null;
  _updateSaveDescBtn();
  document.querySelectorAll('[data-variant-idx]').forEach(btn => {
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-outline-secondary');
  });
}

function applyVariant(idx) {
  const v = App.currentSeries?.ai_variants?.[idx];
  if (!v) return;
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
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
  App.activeVariantId = v.id;
  _updateSaveDescBtn();
  document.querySelectorAll('[data-variant-idx]').forEach((btn, i) => {
    btn.classList.toggle('btn-primary', i === idx);
    btn.classList.toggle('btn-outline-secondary', i !== idx);
  });
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
  (App.currentSeries?.images ?? []).forEach(img => {
    const isSelected = savedSel.has(img.id);
    const btn = document.querySelector('[data-select-btn="' + img.id + '"]');
    if (btn) btn.replaceChildren(icon(_selectIcon(img.id, img.status)));
    const thumb = document.querySelector('[data-image-id="' + img.id + '"]');
    if (thumb) thumb.classList.toggle('thumb-selected', isSelected);
  });
  const strip = document.getElementById('imageStrip');
  if (strip) {
    const thumbs = [...strip.querySelectorAll('[data-image-id]')];
    const _grp = el => {
      const id = el.dataset.imageId, st = el.dataset.imageStatus;
      return savedSel.has(id) ? 0 : st === 'posted' ? 2 : st === 'skip' ? 3 : 1;
    };
    thumbs.sort((a, b) => _grp(a) - _grp(b)).forEach(t => strip.appendChild(t));
  }
  const bar = document.getElementById('imageActionBar');
  if (bar) bar.replaceWith(buildActionBar(seriesId));
  _refreshImagesHeader((App.currentSeries?.images ?? []).length);
}

// ── Generate card ─────────────────────────────────────────────────────────────
function buildGenerateCard(seriesId) {
  const hintInput = h('input', { type: 'text', cls: 'form-control form-control-sm', id: 'genHint', placeholder: 'e.g. this is a fox spirit...' });
  const provSel = document.createElement('select');
  provSel.className = 'form-select form-select-sm'; provSel.id = 'genProvider'; provSel.style.width = '120px';
  [['', 'Default'], ['anthropic', 'Anthropic'], ['openai', 'OpenAI'], ['google', 'Google'], ['deepseek', 'DeepSeek']].forEach(([val, lbl]) => {
    const o = document.createElement('option'); o.value = val; o.textContent = lbl; provSel.appendChild(o);
  });
  const modelSel = document.createElement('select');
  modelSel.className = 'form-select form-select-sm'; modelSel.id = 'genModel'; modelSel.style.width = '200px';
  buildProviderModelSelect(modelSel, '', { withDefault: true });
  provSel.addEventListener('change', () => buildProviderModelSelect(modelSel, provSel.value, { withDefault: true }));
  const genBtn = h('button', { cls: 'btn btn-sm btn-outline-primary', id: 'generateBtn' });
  genBtn.appendChild(icon('bi bi-robot me-1'));
  genBtn.appendChild(document.createTextNode('Generate'));
  genBtn.addEventListener('click', () => generateDescriptions(seriesId));

  const imgCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'genIncludeImages' });
  const imgLabel = h('label', { cls: 'd-flex align-items-center gap-1 small text-muted', style: 'cursor:pointer' });
  imgLabel.appendChild(imgCheck);
  imgLabel.appendChild(document.createTextNode(' Include images'));

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-robot me-1'));
  headerLabel.appendChild(document.createTextNode('AI Generation'));

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header py-2' }, headerLabel),
    h('div', { cls: 'card-body p-2' },
      h('div', { cls: 'd-flex gap-2 flex-wrap align-items-end' },
        h('div', { cls: 'flex-grow-1' }, h('label', { cls: 'form-label small mb-0', text: 'Hint' }), hintInput),
        h('div', null, h('label', { cls: 'form-label small mb-0', text: 'Provider' }), provSel),
        h('div', null, h('label', { cls: 'form-label small mb-0', text: 'Model' }), modelSel),
        h('div', null, h('label', { cls: 'form-label small mb-0 d-block', text: ' ' }), genBtn),
        h('div', { cls: 'align-self-end pb-1' }, imgLabel))));
}

async function generateDescriptions(seriesId) {
  const btn = document.getElementById('generateBtn');
  const provider = document.getElementById('genProvider')?.value || null;
  const model    = document.getElementById('genModel')?.value.trim() || null;
  const hint          = document.getElementById('genHint')?.value.trim() || null;
  const includeImages = document.getElementById('genIncludeImages')?.checked ?? false;
  if (btn) {
    btn.disabled = true;
    btn.replaceChildren(h('span', { cls: 'spinner-border spinner-border-sm me-1' }), document.createTextNode('Generating…'));
  }
  let selectedImageIds = null;
  if (includeImages && _selectedImages.size > 0) {
    const strip = document.getElementById('imageStrip');
    selectedImageIds = strip
      ? [...strip.querySelectorAll('[data-image-id]')]
          .map(el => el.dataset.imageId)
          .filter(id => _selectedImages.has(id))
          .slice(0, 3)
      : [..._selectedImages].slice(0, 3);
  }
  try {
    const newVariants = await apiFetch('POST', '/api/series/' + seriesId + '/generate', {
      provider: provider || null, model: model || null, hint: hint || null,
      include_images: includeImages, selected_image_ids: selectedImageIds,
    });
    const savedSelection = new Set(_selectedImages);
    await loadSeriesDetail(seriesId);
    applyVariant(0);
    _restoreSelectionAfterRender(savedSelection, seriesId);
    const cost = newVariants[0]?.cost_usd;
    const costLabel = cost > 0 ? ` · $${cost.toFixed(4)}` : '';
    showToast(`Generated new variants${costLabel}`, 'success');
  } catch (e) {
    showToast(e.message, 'danger');
    if (btn) {
      btn.disabled = false;
      btn.replaceChildren(icon('bi bi-robot me-1'), document.createTextNode('Generate'));
    }
  }
}

// ── Actions card ──────────────────────────────────────────────────────────────
function buildActionsCard(series) {
  const statusSel = document.createElement('select');
  statusSel.className = 'form-select form-select-sm'; statusSel.id = 'statusSelect'; statusSel.style.width = '140px';
  ['new', 'draft', 'approved', 'skip'].forEach(s => {
    const o = document.createElement('option'); o.value = s; o.textContent = s;
    if (s === series.status) o.selected = true;
    statusSel.appendChild(o);
  });
  if (!['new', 'draft', 'approved', 'skip'].includes(series.status)) {
    const o = document.createElement('option'); o.value = series.status; o.textContent = series.status; o.selected = true;
    statusSel.appendChild(o);
  }
  const saveStatusBtn = h('button', { cls: 'btn btn-sm btn-outline-primary', id: 'saveStatusBtn' });
  saveStatusBtn.appendChild(icon('bi bi-floppy me-1'));
  saveStatusBtn.appendChild(document.createTextNode('Save status'));
  saveStatusBtn.addEventListener('click', () => saveStatus(series.id));
  statusSel.addEventListener('change', _updateSaveStatusBtn);

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-gear me-1'));
  headerLabel.appendChild(document.createTextNode('Series'));

  const deleteSeriesBtn = h('button', {
    cls: 'btn btn-xs btn-outline-danger ms-auto',
    title: 'Delete series',
  });
  deleteSeriesBtn.appendChild(icon('bi bi-trash'));
  deleteSeriesBtn.addEventListener('click', () => deleteSeries(series.id));

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header d-flex align-items-center py-2' }, headerLabel, deleteSeriesBtn),
    h('div', { cls: 'card-body p-2' },
      h('div', { cls: 'd-flex gap-2 align-items-center' }, statusSel, saveStatusBtn)));
}

async function saveStatus(seriesId) {
  const status = document.getElementById('statusSelect')?.value;
  try {
    const updated = await apiFetch('PUT', '/api/series/' + seriesId, { status });
    App.currentSeries = updated;
    updateSeriesItem(updated);
    _updateSaveStatusBtn();
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
    document.getElementById('editorPanel').replaceChildren(
      h('p', { cls: 'text-muted text-center mt-5 d-none d-lg-block', text: 'Select a series to edit' })
    );
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
const POST_PLATFORM_ICON = { telegram: 'bi bi-telegram', instagram: 'bi bi-instagram', facebook: 'bi bi-facebook' };
const POST_STATUS_COLOR  = { draft: 'bg-secondary', scheduled: 'bg-purple', posted: 'bg-success', failed: 'bg-danger' };

function buildPostsCard(series) {
  const imgMap = {};
  series.images.forEach(i => { if (!i.deleted_at) imgMap[i.id] = i.public_url; });

  const headerLabel = h('span', { cls: 'small fw-medium' });
  headerLabel.appendChild(icon('bi bi-send me-1'));
  headerLabel.appendChild(document.createTextNode('Posts'));

  const newPostBtn = h('button', { cls: 'btn btn-xs btn-outline-primary' });
  newPostBtn.appendChild(icon('bi bi-plus me-1'));
  newPostBtn.appendChild(document.createTextNode('New post'));

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
  const activePosts = (series.posts || []).filter(p => !p.deleted_at);
  if (!activePosts.length) {
    postList.appendChild(h('p', { cls: 'text-muted small mb-0', text: 'No posts yet.' }));
  } else {
    activePosts.forEach(p => postList.appendChild(buildPostRow(p, imgMap, series)));
  }

  return h('div', { cls: 'card mb-3' },
    h('div', { cls: 'card-header d-flex align-items-center justify-content-between py-2' }, headerLabel, newPostBtn),
    h('div', { cls: 'card-body p-2' }, formWrap, postList));
}

function buildPostRow(post, imgMap, series) {
  const platIcon = icon((POST_PLATFORM_ICON[post.platform] || 'bi bi-send') + ' me-1');
  const statusBadgeEl = h('span', { cls: 'badge ' + (POST_STATUS_COLOR[post.status] || 'bg-secondary') + ' ms-1', text: post.status });
  const titleEl = h('span', { cls: 'small text-truncate flex-grow-1', text: post.title || '(no title)', style: 'max-width:180px' });

  const timeEl = post.posted_at
    ? h('span', { cls: 'text-muted small', text: formatDate(post.posted_at) })
    : post.scheduled_at
      ? h('span', { cls: 'text-purple small' }, icon('bi bi-clock me-1'), document.createTextNode(formatDate(post.scheduled_at)))
      : null;

  const thumbs = h('div', { cls: 'd-flex gap-1 flex-wrap' });
  (post.image_ids || []).slice(0, 3).forEach(id => {
    if (imgMap[id]) {
      const img = document.createElement('img');
      img.setAttribute('src', imgMap[id]);
      img.style.cssText = 'width:28px;height:24px;object-fit:cover;border-radius:2px';
      thumbs.appendChild(img);
    }
  });

  const actions = h('div', { cls: 'd-flex gap-1 flex-shrink-0' });

  if (post.status !== 'posted') {
    const postNowBtn = h('button', { cls: 'btn btn-sm btn-outline-info', title: 'Post now' });
    postNowBtn.appendChild(icon('bi bi-send'));
    postNowBtn.addEventListener('click', () => postNow(post.id));
    actions.appendChild(postNowBtn);
  }

  if (post.status === 'draft' || post.status === 'failed') {
    const schedBtn = h('button', { cls: 'btn btn-sm btn-outline-secondary', title: 'Schedule' });
    schedBtn.appendChild(icon('bi bi-calendar-plus'));
    schedBtn.addEventListener('click', () => {
      const pickerId = 'sched-picker-' + post.id;
      const existing = document.getElementById(pickerId);
      if (existing) { existing.remove(); return; }
      const dtInput = h('input', { type: 'datetime-local', cls: 'form-control form-control-sm', style: 'width:200px' });
      // Pre-fill with current scheduled_at or +1h from now
      const base = post.scheduled_at
        ? new Date(post.scheduled_at.endsWith('Z') ? post.scheduled_at : post.scheduled_at + 'Z')
        : new Date(Date.now() + 3600000);
      dtInput.value = base.toISOString().slice(0, 16);
      const okBtn = h('button', { cls: 'btn btn-sm btn-primary', text: 'Schedule' });
      okBtn.addEventListener('click', async () => {
        if (!dtInput.value) return;
        await schedulePost(post.id, new Date(dtInput.value).toISOString());
        picker.remove();
      });
      const cancelBtn = h('button', { cls: 'btn btn-sm btn-outline-secondary', text: 'Cancel' });
      cancelBtn.addEventListener('click', () => picker.remove());
      const picker = h('div', { id: pickerId, cls: 'border rounded p-2 mb-1 bg-body-tertiary d-flex align-items-center gap-2 flex-wrap' },
        dtInput, okBtn, cancelBtn);
      rowWrap.after(picker);
    });
    actions.appendChild(schedBtn);
  }

  if (post.status === 'scheduled') {
    const cancelBtn = h('button', { cls: 'btn btn-sm btn-outline-warning', title: 'Cancel schedule' });
    cancelBtn.appendChild(icon('bi bi-x-circle'));
    cancelBtn.addEventListener('click', () => cancelPostSchedule(post.id));
    actions.appendChild(cancelBtn);
  }

  if (post.status !== 'posted') {
    const editBtn = h('button', { cls: 'btn btn-sm btn-outline-secondary', title: 'Edit post' });
    editBtn.appendChild(icon('bi bi-pencil'));
    editBtn.addEventListener('click', () => {
      const existing = document.getElementById('edit-form-' + post.id);
      if (existing) { existing.remove(); return; }
      const form = buildEditPostForm(post, imgMap, series, () => {
        const el = document.getElementById('edit-form-' + post.id);
        if (el) el.remove();
      });
      form.id = 'edit-form-' + post.id;
      rowWrap.after(form);
    });
    actions.appendChild(editBtn);

    const delBtn = h('button', { cls: 'btn btn-sm btn-outline-danger', title: 'Delete post' });
    delBtn.appendChild(icon('bi bi-trash'));
    delBtn.addEventListener('click', () => deletePost(post.id));
    actions.appendChild(delBtn);
  }

  const info = h('div', { cls: 'd-flex align-items-center gap-1 flex-grow-1 overflow-hidden' },
    platIcon, titleEl, statusBadgeEl, timeEl ? timeEl : null);

  const rowWrap = h('div', { cls: 'p-1 border rounded d-flex align-items-center gap-2', 'data-post-row': post.id },
    thumbs, info, actions);
  return rowWrap;
}

function buildEditPostForm(post, imgMap, series, onClose) {
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
      await loadSeriesDetail(series.id);
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
  // Seed from current strip selection; fall back to all images if nothing selected
  const initialSel = _selectedImages.size > 0
    ? allImages.filter(i => _selectedImages.has(i.id)).map(i => i.id)
    : allImages.map(i => i.id);
  const { grid: imgGrid, selected: _selectedPostImages } = _buildImageSelector(allImages, initialSel, imgMap);

  // Platform checkboxes
  const tgCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'pf_tg' });
  tgCheck.checked = true;
  const igCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'pf_ig' });
  igCheck.checked = true;
  const fbCheck = h('input', { type: 'checkbox', cls: 'form-check-input m-0', id: 'pf_fb' });
  fbCheck.checked = true;

  const platformRow = h('div', { cls: 'd-flex gap-3 mb-2 align-items-center' },
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, tgCheck, document.createTextNode(' Telegram')),
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, igCheck, document.createTextNode(' Instagram')),
    h('label', { cls: 'd-flex align-items-center gap-1 small' }, fbCheck, document.createTextNode(' Facebook')));

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

  // Save button
  const saveBtn = h('button', { cls: 'btn btn-sm btn-primary me-1' });
  saveBtn.appendChild(icon('bi bi-send me-1'));
  saveBtn.appendChild(document.createTextNode('Save post(s)'));
  saveBtn.addEventListener('click', async () => {
    const platforms = [];
    if (tgCheck.checked) platforms.push('telegram');
    if (igCheck.checked) platforms.push('instagram');
    if (fbCheck.checked) platforms.push('facebook');
    if (!platforms.length) { showToast('Select at least one platform', 'danger'); return; }
    if (!_selectedPostImages.size) { showToast('Select at least one image', 'danger'); return; }
    const imageIds = allImages.filter(i => _selectedPostImages.has(i.id)).map(i => i.id);
    const schedVal = schedInput.value ? new Date(schedInput.value).toISOString() : null;
    try {
      saveBtn.disabled = true;
      await apiFetch('POST', '/api/series/' + series.id + '/posts', {
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
        scheduled_at: schedVal,
      });
      showToast(platforms.length + ' post(s) created', 'success');
      onClose();
      await loadSeriesDetail(series.id);
    } catch (e) {
      showToast(e.message, 'danger');
      saveBtn.disabled = false;
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
    h('div', null, saveBtn, cancelBtn));
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
