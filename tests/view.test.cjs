/*
 * Copyright 2026 Christian Grobmeier and contributors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const view = require('../src/oss_stats/web/view.js');
test('ranges reject inverted, missing, invalid and uncovered months', () => {
  const dates = ['2025-01', '2026-10'];
  assert.equal(view.range('2025-01', '2026-10', dates), '');
  for (const pair of [['2027-01','2026-10'], ['','2026-10'], ['2025-13','2026-10'], ['2024-01','2026-10']])
    assert.notEqual(view.range(...pair, dates), '');
});
test('deltas retain missing endpoints and measure absolute change', () => {
  assert.equal(view.delta([{value: 4}, {value: null}, {value: 7}]), 3);
  assert.equal(view.delta([{value: null}, {value: 7}]), null);
  assert.equal(view.delta([{value: 4}]), null);
});
test('URL state preserves custom months and module characters', () => {
  const state = {from:'2023-01', to:'2026-10', group:'quarterly', module:'Bridges and adapters'};
  assert.deepEqual(Object.fromEntries(new URLSearchParams(view.query(state))), state);
});

test('quarter containment uses the end after the selected last month', () => {
  assert.equal(view.endExclusive('2026-08'), '2026-09-01T00:00:00Z');
  assert.equal(view.endExclusive('2026-12'), '2027-01-01T00:00:00Z');
});

test('period labels identify monthly, quarterly, and partial periods in UTC', () => {
  assert.equal(view.periodLabel({start:'2026-10-01T00:00:00Z',grouping:'monthly'}), 'Oct 2026');
  assert.equal(view.periodLabel({start:'2026-07-01T00:00:00Z',grouping:'quarterly'}), 'Q3 2026');
  assert.equal(view.periodLabel({start:'2026-11-01T00:00:00Z',grouping:'partial month'}), 'Nov 2026 (partial)');
});
