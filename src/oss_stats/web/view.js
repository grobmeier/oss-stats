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
"use strict";
const CommunityView = (() => {
  function range(from, to, dates) {
    const valid = /^\d{4}-(0[1-9]|1[0-2])$/;
    if (!valid.test(from) || !valid.test(to)) return "Select both months.";
    if (from > to) return "From must be on or before To.";
    if (from < dates[0] || to > dates.at(-1))
      return `Available complete months: ${dates[0]} to ${dates.at(-1)}.`;
    return "";
  }
  function endExclusive(month) {
    const [year, number] = month.split("-").map(Number);
    return new Date(Date.UTC(year, number, 1)).toISOString().replace(".000Z", "Z");
  }
  function periodLabel(row) {
    const date = new Date(row.start);
    if (row.grouping === "quarterly") return `Q${Math.floor(date.getUTCMonth() / 3) + 1} ${date.getUTCFullYear()}`;
    const label = new Intl.DateTimeFormat("en-GB", {month: "short", year: "numeric", timeZone: "UTC"}).format(date);
    return label + (row.grouping === "partial month" ? " (partial)" : "");
  }
  function delta(points) {
    // Do not bridge unavailable endpoints or compare a partial period to a full period.
    if (points.length < 2 || points[0].value === null || points.at(-1).value === null) return null;
    return points.at(-1).value - points[0].value;
  }
  function query(state) {
    return new URLSearchParams(Object.entries(state).filter(([, v]) => v !== "")).toString();
  }
  return {range, endExclusive, periodLabel, delta, query};
})();
if (typeof module !== "undefined") module.exports = CommunityView;
