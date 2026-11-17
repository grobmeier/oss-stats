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
"""Prevent stale or unrelated source from entering a public wheel."""
import importlib.util
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location("distribution", Path(__file__).resolve().parents[1] / "scripts/build_distribution.py")
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


def test_wheel_allowlist_accepts_package_and_licence_metadata(tmp_path):
    wheel = tmp_path / "example.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("oss_stats/cli.py", "source")
        archive.writestr("oss_stats-0.4.0.dist-info/licenses/NOTICE", "attribution")
    distribution.validate_wheel(wheel, "0.4.0")


def test_wheel_allowlist_rejects_stale_packages(tmp_path):
    wheel = tmp_path / "example.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("oss_stats/cli.py", "source")
        archive.writestr("unrelated_package/old.py", "stale source")
    with pytest.raises(ValueError, match="stale build output"):
        distribution.validate_wheel(wheel, "0.4.0")
