# Copyright 2026 Christian Grobmeier and contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
"""Check source licensing and upstream attribution."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_source_files_have_full_apache_headers():
    roots = [ROOT / name for name in ('src', 'scripts', 'tests', 'config', 'landing', '.github')]
    files = [ROOT / 'pyproject.toml']
    for directory in roots:
        files.extend(p for p in directory.rglob('*') if p.suffix in ('.py', '.js', '.cjs', '.css', '.html', '.yaml', '.yml'))
    for path in files:
        header = path.read_text().splitlines()[:24]
        text = '\n'.join(header)
        assert 'Licensed under the Apache License, Version 2.0' in text, path
        assert 'SPDX-License-Identifier: Apache-2.0' in text, path
        assert 'Copyright' in text, path
    assert 'Copyright Russell Spitzer' in (ROOT / 'src/oss_stats/timeutil.py').read_text()
