let _statsData = null;
let _statsSort = { key: 'generated', dir: -1 };

async function refreshStats() {
  const el = document.getElementById('statsContent');
  el.replaceChildren(
    h('div', { cls: 'text-center' }, h('div', { cls: 'spinner-border spinner-border-sm' }))
  );
  try {
    _statsData = await apiFetch('GET', '/api/stats/ai');
    _renderStats(el, _statsData);
  } catch (e) {
    el.replaceChildren(h('p', { cls: 'text-danger small', text: 'Failed to load stats: ' + e.message }));
  }
}

function _sortStats(key) {
  if (_statsSort.key === key) {
    _statsSort.dir *= -1;
  } else {
    _statsSort = { key, dir: key === 'provider' || key === 'model' ? 1 : -1 };
  }
  if (_statsData) _renderStats(document.getElementById('statsContent'), _statsData);
}

function _renderStats(el, data) {
  if (!data.rows.length) {
    el.replaceChildren(h('p', { cls: 'text-muted', text: 'No generation data yet.' }));
    return;
  }

  const { key, dir } = _statsSort;
  const sorted = [...data.rows].sort((a, b) => {
    const av = a[key] ?? -Infinity;
    const bv = b[key] ?? -Infinity;
    if (typeof av === 'string') return dir * av.localeCompare(bv);
    return dir * (av - bv);
  });

  function thSort(label, colKey, align) {
    const active = _statsSort.key === colKey;
    const indicator = active ? (_statsSort.dir === -1 ? ' ▼' : ' ▲') : '';
    const cls = 'small fw-normal text-muted' + (align ? ' ' + align : '') + ' user-select-none';
    const th = h('th', { cls, style: 'cursor:pointer', text: label + indicator });
    th.addEventListener('click', () => _sortStats(colKey));
    return th;
  }

  const thead = h('thead', {},
    h('tr', {},
      thSort('Provider', 'provider', ''),
      thSort('Model', 'model', ''),
      thSort('Generated', 'generated', 'text-end'),
      thSort('Chosen', 'chosen', 'text-end'),
      thSort('Selection %', 'selection_rate', 'text-end'),
      thSort('Total Cost', 'total_cost_usd', 'text-end'),
      thSort('$ / selection', 'cost_per_selection', 'text-end'),
    )
  );
  const tbody = h('tbody');
  sorted.forEach(r => {
    tbody.appendChild(h('tr', {},
      h('td', { cls: 'small', text: r.provider }),
      h('td', { cls: 'small text-secondary text-truncate', style: 'max-width:180px', text: r.model }),
      h('td', { cls: 'small text-end', text: String(r.generated) }),
      h('td', { cls: 'small text-end', text: String(r.chosen) }),
      h('td', { cls: 'small text-end', text: r.selection_rate.toFixed(1) + '%' }),
      h('td', { cls: 'small text-end', text: '$' + r.total_cost_usd.toFixed(4) }),
      h('td', { cls: 'small text-end',
        text: r.cost_per_selection != null ? '$' + r.cost_per_selection.toFixed(4) : '—' }),
    ));
  });
  const overallRate = data.total_generated > 0
    ? (data.total_chosen / data.total_generated * 100).toFixed(1) + '%'
    : '—';
  const tfoot = h('tfoot', {},
    h('tr', { cls: 'border-top' },
      h('td', { cls: 'small text-secondary fw-semibold', text: 'Total', colspan: '2' }),
      h('td', { cls: 'small text-end fw-semibold', text: String(data.total_generated) }),
      h('td', { cls: 'small text-end fw-semibold', text: String(data.total_chosen) }),
      h('td', { cls: 'small text-end fw-semibold', text: overallRate }),
      h('td', { cls: 'small text-end fw-semibold', text: '$' + data.total_cost_usd.toFixed(4) }),
      h('td'),
    )
  );
  el.replaceChildren(
    h('table', { cls: 'table table-sm table-dark table-hover' }, thead, tbody, tfoot)
  );
}
