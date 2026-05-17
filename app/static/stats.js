async function refreshStats() {
  const el = document.getElementById('statsContent');
  el.replaceChildren(
    h('div', { cls: 'text-center' }, h('div', { cls: 'spinner-border spinner-border-sm' }))
  );
  try {
    const data = await apiFetch('GET', '/api/stats/ai');
    _renderStats(el, data);
  } catch (e) {
    el.replaceChildren(h('p', { cls: 'text-danger small', text: 'Failed to load stats: ' + e.message }));
  }
}

function _renderStats(el, data) {
  if (!data.rows.length) {
    el.replaceChildren(h('p', { cls: 'text-muted', text: 'No generation data yet.' }));
    return;
  }
  const thead = h('thead', {},
    h('tr', {},
      h('th', { cls: 'small fw-normal text-muted', text: 'Provider' }),
      h('th', { cls: 'small fw-normal text-muted', text: 'Model' }),
      h('th', { cls: 'small fw-normal text-muted text-end', text: 'Generated' }),
      h('th', { cls: 'small fw-normal text-muted text-end', text: 'Chosen' }),
      h('th', { cls: 'small fw-normal text-muted text-end', text: 'Selection %' }),
      h('th', { cls: 'small fw-normal text-muted text-end', text: 'Total Cost' }),
      h('th', { cls: 'small fw-normal text-muted text-end', text: '$ / selection' }),
    )
  );
  const tbody = h('tbody');
  data.rows.forEach(r => {
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
