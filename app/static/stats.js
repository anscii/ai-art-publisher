let _statsData = null;
let _statsSort  = { key: 'generated', dir: -1 };
let _statsRange = 'all';  // 'all' | 'week'

async function refreshStats() {
  const el = document.getElementById('statsContent');
  el.replaceChildren(
    h('div', { cls: 'text-center' }, h('div', { cls: 'spinner-border spinner-border-sm' }))
  );
  try {
    _statsData = await apiFetch('GET', '/api/stats/ai?range=' + _statsRange);
    _renderStats(el, _statsData);
  } catch (e) {
    el.replaceChildren(h('p', { cls: 'text-danger small', text: 'Failed to load stats: ' + e.message }));
  }
}

function setStatsRange(range) {
  _statsRange = range;
  document.getElementById('statsRangeAll')?.classList.toggle('aap-btn-primary', range === 'all');
  document.getElementById('statsRangeWeek')?.classList.toggle('aap-btn-primary', range === 'week');
  refreshStats();
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
  // Update kicker
  const kicker = document.getElementById('statsKicker');
  if (kicker) {
    if (!data.rows.length) {
      kicker.textContent = 'No data yet';
    } else {
      const cost = '$' + data.total_cost_usd.toFixed(4);
      kicker.textContent =
        data.total_generated + ' generation' + (data.total_generated !== 1 ? 's' : '') +
        ' · ' + data.total_chosen + ' chosen · ' + cost + ' spent';
    }
  }

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

  const maxGenerated = Math.max(...sorted.map(r => r.generated), 1);

  // Column template: Provider · Model · Generated · Chosen · Selection% · Total Cost · $/selection
  const COLS = '110px 1fr 90px 70px 90px 90px 100px';

  function sortIndicator(colKey) {
    if (_statsSort.key !== colKey) return '';
    return _statsSort.dir === -1 ? ' ▾' : ' ▴';
  }

  function thSpan(label, colKey, isNum) {
    const sp = h('span', { cls: isNum ? 'aap-num user-select-none' : 'user-select-none',
                            style: 'cursor:pointer',
                            text: label + sortIndicator(colKey) });
    sp.addEventListener('click', () => _sortStats(colKey));
    return sp;
  }

  const head = h('div', { cls: 'aap-table__head' },
    thSpan('Provider',     'provider',          false),
    thSpan('Model',        'model',              false),
    thSpan('Generated',    'generated',          true),
    thSpan('Chosen',       'chosen',             true),
    thSpan('Selection %',  'selection_rate',     true),
    thSpan('Total Cost',   'total_cost_usd',     true),
    thSpan('$ / selection','cost_per_selection', true),
  );

  const dataRows = sorted.map(r => {
    const barPct = (r.generated / maxGenerated * 100).toFixed(1) + '%';
    const selStr  = r.chosen > 0 ? r.selection_rate.toFixed(1) + '%' : '—';
    const cpStr   = r.cost_per_selection != null ? '$' + r.cost_per_selection.toFixed(4) : '—';
    const isEmpty = v => v === '—';

    function cell(text, mod) {
      return h('span', { cls: 'aap-stats-cell aap-stats-cell--' + mod + (isEmpty(text) ? ' is-empty' : ''), text });
    }

    const row = h('div', { cls: 'aap-table__row' });
    row.appendChild(h('span', { cls: 'aap-stats-bar', style: 'width:' + barPct }));
    row.appendChild(cell(r.provider,  'ink'));
    row.appendChild(cell(r.model,     'model'));
    row.appendChild(cell(String(r.generated), 'num'));
    row.appendChild(cell(String(r.chosen),    'num'));
    row.appendChild(cell(selStr,              'num'));
    row.appendChild(cell('$' + r.total_cost_usd.toFixed(4), 'num'));
    row.appendChild(cell(cpStr, 'num'));
    return row;
  });

  // Totals row
  const overallRate = data.total_generated > 0
    ? (data.total_chosen / data.total_generated * 100).toFixed(1) + '%'
    : '—';
  const totalRow = h('div', { cls: 'aap-stats-total' },
    h('span', { cls: 'aap-stats-cell aap-stats-cell--ink', text: 'Total' }),
    h('span'),
    h('span', { cls: 'aap-stats-cell aap-stats-cell--num', text: String(data.total_generated) }),
    h('span', { cls: 'aap-stats-cell aap-stats-cell--num', text: String(data.total_chosen) }),
    h('span', { cls: 'aap-stats-cell aap-stats-cell--num', text: overallRate }),
    h('span', { cls: 'aap-stats-cell aap-stats-cell--num', text: '$' + data.total_cost_usd.toFixed(4) }),
    h('span'),
  );

  const table = h('div', { cls: 'aap-table', style: '--cols:' + COLS });
  table.appendChild(head);
  dataRows.forEach(r => table.appendChild(r));
  table.appendChild(totalRow);

  el.replaceChildren(table);
}
