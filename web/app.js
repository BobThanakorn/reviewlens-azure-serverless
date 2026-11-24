/* ReviewLens dashboard. Pure data helpers first (unit-tested with `node --test`), then DOM code.
 * Review text comes from users, so it is only ever written with textContent (no HTML parsing). */
(function (root) {
  'use strict';

  var SENTIMENTS = ['positive', 'neutral', 'negative'];
  var POINT_STYLES = { positive: 'circle', neutral: 'rect', negative: 'triangle', unknown: 'crossRot' };
  var NEGATIVE_ROWS = 20;
  var REVIEW_PREVIEW_CHARS = 160;

  // ---------------------------------------------------------------- pure helpers

  function percent(part, whole) {
    return whole > 0 ? (part / whole) * 100 : 0;
  }

  function formatPercent(value) {
    return value.toFixed(1) + '%';
  }

  function truncate(text, limit) {
    var flat = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
    return flat.length <= limit ? flat : flat.slice(0, limit - 1) + '…';
  }

  function kpisFromDaily(series) {
    var total = 0;
    var negative = 0;
    (series || []).forEach(function (day) {
      total += day.total || 0;
      negative += day.negative || 0;
    });
    return { total: total, negative: negative, negativePercent: percent(negative, total) };
  }

  function dailyChartData(series) {
    var days = series || [];
    var labels = days.map(function (d) { return d.date; });
    var labelsToShow = SENTIMENTS.concat(
      days.some(function (d) { return d.unknown > 0; }) ? ['unknown'] : []
    );
    var datasets = labelsToShow.map(function (name) {
      return {
        key: name,
        label: name,
        data: days.map(function (d) { return d[name] || 0; }),
        pointStyle: POINT_STYLES[name]
      };
    });
    return { labels: labels, datasets: datasets };
  }

  function topicChartData(topics) {
    var rows = (topics || []).filter(function (t) { return t.count > 0; });
    return {
      labels: rows.map(function (t) { return t.topic; }),
      negative: rows.map(function (t) { return t.negative; }),
      other: rows.map(function (t) { return t.count - t.negative; })
    };
  }

  function describeDaily(series) {
    var k = kpisFromDaily(series);
    return 'Daily sentiment: ' + k.total + ' reviews, ' + k.negative + ' negative, over ' +
      (series || []).length + ' days.';
  }

  function describeTopics(data) {
    return 'Topic counts: ' + data.labels.map(function (name, i) {
      return name + ' ' + (data.negative[i] + data.other[i]);
    }).join(', ') + '.';
  }

  function joinUrl(base, path) {
    return String(base).replace(/\/+$/, '') + '/' + String(path).replace(/^\/+/, '');
  }

  // -------------------------------------------------------------------- DOM code

  function $(id) {
    return root.document.getElementById(id);
  }

  function setStatus(panelId, message, isError) {
    var node = $(panelId).querySelector('[data-status]');
    node.textContent = message;
    node.classList.toggle('error', Boolean(isError));
    node.hidden = !message;
  }

  function setKpi(id, value, note) {
    var card = $(id);
    card.querySelector('[data-value]').textContent = value;
    if (note) { card.querySelector('[data-note]').textContent = note; }
  }

  function cssVar(name) {
    return root.getComputedStyle(root.document.documentElement).getPropertyValue(name).trim();
  }

  function fetchJson(base, path) {
    return root.fetch(joinUrl(base, path), { headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (!response.ok) { throw new Error('HTTP ' + response.status); }
        return response.json();
      });
  }

  var charts = {};

  function drawChart(id, config) {
    if (typeof root.Chart === 'undefined') {
      throw new Error('Chart.js did not load');
    }
    if (charts[id]) { charts[id].destroy(); }
    charts[id] = new root.Chart($(id), config);
  }

  function renderDaily(data) {
    var chart = dailyChartData(data.series);
    var datasets = chart.datasets.map(function (ds) {
      return {
        label: ds.label,
        data: ds.data,
        pointStyle: ds.pointStyle,
        borderColor: cssVar('--' + ds.key),
        backgroundColor: cssVar('--' + ds.key),
        pointRadius: 4,
        tension: 0
      };
    });
    drawChart('chart-daily', {
      type: 'line',
      data: { labels: chart.labels, datasets: datasets },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { labels: { usePointStyle: true, color: cssVar('--text') } } },
        scales: {
          x: { ticks: { color: cssVar('--muted') } },
          y: { beginAtZero: true, ticks: { precision: 0, color: cssVar('--muted') } }
        }
      }
    });
    $('chart-daily').setAttribute('aria-label', describeDaily(data.series));
  }

  function renderTopics(data) {
    var chart = topicChartData(data.topics);
    drawChart('chart-topics', {
      type: 'bar',
      data: {
        labels: chart.labels,
        datasets: [
          { label: 'negative', data: chart.negative, backgroundColor: cssVar('--negative') },
          { label: 'other sentiment', data: chart.other, backgroundColor: cssVar('--neutral') }
        ]
      },
      options: {
        indexAxis: 'y',
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: cssVar('--text') } } },
        scales: {
          x: { stacked: true, beginAtZero: true, ticks: { precision: 0, color: cssVar('--muted') } },
          y: { stacked: true, ticks: { color: cssVar('--muted') } }
        }
      }
    });
    $('chart-topics').setAttribute('aria-label', describeTopics(chart));
  }

  function cell(tag, text, attributes) {
    var node = root.document.createElement(tag);
    node.textContent = text;
    Object.keys(attributes || {}).forEach(function (name) { node.setAttribute(name, attributes[name]); });
    return node;
  }

  function renderNegativeTable(data) {
    var table = $('negative-table');
    var body = table.querySelector('tbody');
    body.replaceChildren();
    if (!data.reviews.length) {
      table.hidden = true;
      setStatus('panel-negative', 'No negative reviews yet.', false);
      return;
    }
    data.reviews.forEach(function (review) {
      var row = root.document.createElement('tr');
      row.appendChild(cell('td', review.date));
      row.appendChild(cell('td', String(review.stars)));
      row.appendChild(cell('td', review.topic));
      row.appendChild(cell('td', review.summary || '–', { lang: 'th' }));
      row.appendChild(cell('td', truncate(review.review_text, REVIEW_PREVIEW_CHARS),
        { lang: 'th', class: 'review', title: review.review_text }));
      body.appendChild(row);
    });
    table.hidden = false;
    setStatus('panel-negative', '', false);
  }

  function showError(panelId, error) {
    setStatus(panelId, 'Could not load this panel (' + error.message + ').', true);
  }

  function loadAll(base) {
    var tasks = [
      fetchJson(base, 'stats/daily?days=14').then(function (data) {
        var k = kpisFromDaily(data.series);
        setKpi('kpi-total', String(k.total));
        setKpi('kpi-negative', formatPercent(k.negativePercent), k.negative + ' negative reviews');
        renderDaily(data);
        setStatus('panel-daily', '', false);
      }).catch(function (e) {
        showError('panel-daily', e);
        setKpi('kpi-total', '–');
        setKpi('kpi-negative', '–');
      }),

      fetchJson(base, 'stats/topics').then(function (data) {
        renderTopics(data);
        setStatus('panel-topics', '', false);
      }).catch(function (e) { showError('panel-topics', e); }),

      fetchJson(base, 'stats/accuracy').then(function (data) {
        setKpi('kpi-accuracy', formatPercent(data.accuracy * 100),
          data.correct + ' of ' + data.sample_size + ' match the star rating');
      }).catch(function (e) {
        setKpi('kpi-accuracy', '–', 'Could not load accuracy (' + e.message + ')');
      }),

      fetchJson(base, 'reviews?sentiment=negative&limit=' + NEGATIVE_ROWS).then(renderNegativeTable)
        .catch(function (e) { showError('panel-negative', e); })
    ];
    return Promise.all(tasks).then(function () {
      $('updated').textContent = 'Updated ' + new Date().toLocaleTimeString();
    });
  }

  function init() {
    var config = root.REVIEWLENS_CONFIG;
    var banner = $('banner');
    if (!config || !config.apiBaseUrl) {
      banner.textContent = 'config.js is missing or has no apiBaseUrl. It is generated by Terraform at deploy time.';
      banner.hidden = false;
      ['panel-daily', 'panel-topics', 'panel-negative'].forEach(function (id) {
        setStatus(id, 'Waiting for configuration.', true);
      });
      return;
    }
    $('refresh').addEventListener('click', function () { loadAll(config.apiBaseUrl); });
    loadAll(config.apiBaseUrl);
  }

  var api = {
    percent: percent,
    formatPercent: formatPercent,
    truncate: truncate,
    kpisFromDaily: kpisFromDaily,
    dailyChartData: dailyChartData,
    topicChartData: topicChartData,
    describeDaily: describeDaily,
    describeTopics: describeTopics,
    joinUrl: joinUrl
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.document.addEventListener('DOMContentLoaded', init);
  }
})(typeof window !== 'undefined' ? window : globalThis);
