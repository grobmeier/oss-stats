#!/usr/bin/env python3
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
"""Build shareable archives from an explicit public-file allowlist."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ("logging.yaml", "maven.yaml", "commons.yaml")


def common_files(destination):
    for name in ("LICENSE", "NOTICE"):
        shutil.copy2(ROOT / name, destination / name)
    shutil.copy2(ROOT / "docs/DISTRIBUTION.md", destination / "README.md")
    shutil.copy2(ROOT / "docs/PROVENANCE.md", destination / "PROVENANCE.md")
    (destination / "config").mkdir()
    for name in CONFIGS:
        shutil.copy2(ROOT / "config" / name, destination / "config" / name)


def finish_manifest(destination, version, kind):
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True))
    manifest = {"version": version, "kind": kind, "source_revision": revision, "source_dirty": dirty,
                "platform": platform.platform(), "architecture": platform.machine(),
                "python": platform.python_version(),
                "build_dependencies": {name: importlib.metadata.version(name) for name in ("duckdb", "pyyaml", "pyinstaller", "build")},
                "files": {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(destination.rglob("*")) if p.is_file()}}
    (destination / "BUILD.json").write_text(json.dumps(manifest, indent=2) + "\n")


def validate_wheel(wheel, version):
    allowed = ("oss_stats/", f"oss_stats-{version}.dist-info/")
    with zipfile.ZipFile(wheel) as archive:
        unexpected = [name for name in archive.namelist() if not name.startswith(allowed)]
    if unexpected:
        raise ValueError("Unexpected wheel contents. Remove stale build output and rebuild.")


def build(output, binary=False):
    if sys.platform not in ("darwin", "linux"):
        raise SystemExit("Distribution builds support macOS and Linux only.")
    version = importlib.metadata.version("oss-stats")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    archives = []
    with tempfile.TemporaryDirectory(prefix="oss-stats-build-") as temporary:
        work = Path(temporary)
        wheel_dir = work / "wheels"
        subprocess.run([sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir)], cwd=ROOT, check=True)
        package = work / f"oss-stats-{version}-python"
        package.mkdir()
        common_files(package)
        wheel = next(wheel_dir.glob("*.whl"))
        if not wheel.name.startswith("oss_stats-" + version + "-"):
            raise SystemExit("Installed package version differs from the built wheel. Reinstall the packaging environment.")
        validate_wheel(wheel, version)
        shutil.copy2(wheel, package / wheel.name)
        finish_manifest(package, version, "python-wheel")
        archive = output / (package.name + ".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as stream:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    stream.write(path, str(Path(package.name) / path.relative_to(package)))
        archives.append(archive)
        if binary:
            executable_dir = work / "executable"
            subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
                            "--name", "oss-stats", "--distpath", str(executable_dir), "--workpath", str(work / "objects"),
                            "--specpath", str(work), "--paths", str(ROOT / "src"),
                            "--collect-all", "duckdb", "--collect-all", "yaml",
                            "--add-data", str(ROOT / "src/oss_stats/web") + ":oss_stats/web",
                            str(ROOT / "scripts/binary_entry.py")], cwd=ROOT, check=True)
            system = "macos" if sys.platform == "darwin" else "linux"
            architecture = {"aarch64": "arm64", "AMD64": "x86_64"}.get(platform.machine(), platform.machine())
            package = work / f"oss-stats-{version}-{system}-{architecture}"
            package.mkdir()
            common_files(package)
            shutil.copy2(executable_dir / "oss-stats", package / "oss-stats")
            for dependency in ("duckdb", "pyyaml", "pyinstaller"):
                distribution = importlib.metadata.distribution(dependency)
                for filename in distribution.files or []:
                    if filename.name.lower().startswith(("license", "copying", "notice")):
                        source = Path(distribution.locate_file(filename))
                        if source.is_file():
                            target = package / "third-party" / dependency / str(filename)
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(source, target)
            python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
            if not python_license.is_file():
                raise SystemExit("Python runtime licence is missing. Supply a Python installation with LICENSE.txt.")
            target = package / "third-party/python/LICENSE.txt"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(python_license, target)
            finish_manifest(package, version, "native-executable")
            archive = output / (package.name + ".tar.gz")
            with tarfile.open(archive, "w:gz") as stream:
                stream.add(package, arcname=package.name)
            archives.append(archive)
    for archive in archives:
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.with_name(archive.name + ".sha256").write_text(checksum + "  " + archive.name + "\n")
        print(archive)
    return archives


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/distribution")
    parser.add_argument("--binary", action="store_true", help="Also build an executable for this operating system and CPU")
    args = parser.parse_args()
    build(args.output, args.binary)
