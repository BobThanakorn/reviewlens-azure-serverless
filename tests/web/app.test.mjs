// Unit tests for the pure helpers in web/app.js. Run with: node --test tests/web
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const app = require('../../web/app.js');

const series = [
  { date: '2026-11-24', total: 10, positive: 6, neutral: 2, negative: 2, unknown: 0 },
  { date: '2026-11-25', total: 30, positive: 15, neutral: 10, negative: 3, unknown: 2 },
];

test('percent handles zero and normal values', () => {
  assert.equal(app.percent(0, 0), 0);
  assert.equal(app.percent(1, 4), 25);
  assert.equal(app.formatPercent(12.345), '12.3%');
});

test('kpis sum the daily series', () => {
  const k = app.kpisFromDaily(series);
  assert.deepEqual([k.total, k.negative], [40, 5]);
  assert.equal(k.negativePercent, 12.5);
  assert.deepEqual(app.kpisFromDaily([]), { total: 0, negative: 0, negativePercent: 0 });
  assert.equal(app.kpisFromDaily(undefined).total, 0);
});

test('daily chart has one dataset per sentiment and adds unknown only when present', () => {
  const chart = app.dailyChartData(series);
  assert.deepEqual(chart.labels, ['2026-11-24', '2026-11-25']);
  assert.deepEqual(chart.datasets.map((d) => d.key), ['positive', 'neutral', 'negative', 'unknown']);
  assert.deepEqual(chart.datasets[0].data, [6, 15]);
  const noUnknown = app.dailyChartData([{ date: 'd', positive: 1, neutral: 0, negative: 0, unknown: 0 }]);
  assert.deepEqual(noUnknown.datasets.map((d) => d.key), ['positive', 'neutral', 'negative']);
});

test('each sentiment line uses a different point shape (not colour alone)', () => {
  const shapes = app.dailyChartData(series).datasets.map((d) => d.pointStyle);
  assert.equal(new Set(shapes).size, shapes.length);
});

test('topic chart drops empty topics and splits negative from the rest', () => {
  const chart = app.topicChartData([
    { topic: 'food', count: 10, negative: 3 },
    { topic: 'price', count: 0, negative: 0 },
  ]);
  assert.deepEqual(chart.labels, ['food']);
  assert.deepEqual([chart.negative[0], chart.other[0]], [3, 7]);
});

test('truncate flattens whitespace, keeps Thai text and adds an ellipsis', () => {
  assert.equal(app.truncate('  อร่อย \n มาก  ', 50), 'อร่อย มาก');
  const out = app.truncate('ก'.repeat(300), 160);
  assert.equal(out.length, 160);
  assert.ok(out.endsWith('…'));
  assert.equal(app.truncate(null, 10), '');
});

test('joinUrl never doubles or drops the slash', () => {
  assert.equal(app.joinUrl('https://x/api/', '/stats/daily'), 'https://x/api/stats/daily');
  assert.equal(app.joinUrl('https://x/api', 'reviews?limit=1'), 'https://x/api/reviews?limit=1');
});

test('text descriptions for screen readers include the numbers', () => {
  assert.match(app.describeDaily(series), /40 reviews, 5 negative, over 2 days/);
  const chart = app.topicChartData([{ topic: 'food', count: 10, negative: 3 }]);
  assert.match(app.describeTopics(chart), /food 10/);
});
