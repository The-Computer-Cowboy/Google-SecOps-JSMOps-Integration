#!/usr/bin/env python3
"""Build a SecOps IDE import ZIP with Integration-{Identifier}.def at the archive root."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZIP_NAME = "JSM-Ops-integration.zip"
PACKAGE_DIRS = (
    "ActionsDefinitions",
    "ActionsScripts",
    "Dependencies",
    "Managers",
)
# Official built packages (mp pack) use Jobs/ + JobsScrips/ — not JobsDefinitions/JobsScripts.
# JobsScrips is Google's folder name (missing 't'); the IDE importer looks for that spelling.
JOB_SOURCE_TO_ARCHIVE = {
    "JobsDefinitions": "Jobs",
    "JobsScripts": "JobsScrips",
}
SKIP_NAMES = {".gitkeep", ".DS_Store"}


def _add_file(zf: zipfile.ZipFile, path: Path, arcname: str) -> None:
    file_info = zipfile.ZipInfo(arcname)
    file_info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(file_info, path.read_bytes())


def _add_directory(zf: zipfile.ZipFile, directory: Path, archive_dir: str) -> int:
    count = 0
    for path in sorted(directory.rglob("*")):
        if path.is_dir() or path.name in SKIP_NAMES or path.suffix == ".pyc":
            continue
        relative = path.relative_to(directory).as_posix()
        _add_file(zf, path, f"{archive_dir}/{relative}")
        count += 1
    return count


def main() -> None:
    def_files = list(ROOT.glob("Integration-*.def"))
    if len(def_files) != 1:
        raise SystemExit(
            f"Expected exactly one Integration-*.def at repo root, found {len(def_files)}: {def_files}"
        )
    def_path = def_files[0]
    identifier = json.loads(def_path.read_text(encoding="utf-8"))["Identifier"]
    expected_name = f"Integration-{identifier}.def"
    if def_path.name != expected_name:
        raise SystemExit(
            f"Def filename {def_path.name!r} must match identifier {identifier!r} "
            f"({expected_name!r}). SecOps looks for Integration-<Identifier>.def."
        )

    zip_path = ROOT / ZIP_NAME
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo(def_path.name)
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, def_path.read_bytes())
        for dirname in PACKAGE_DIRS:
            directory = ROOT / dirname
            if not directory.is_dir():
                raise SystemExit(f"Missing required package directory: {directory}")
            _add_directory(zf, directory, dirname)
        for source_dir, archive_dir in JOB_SOURCE_TO_ARCHIVE.items():
            directory = ROOT / source_dir
            if not directory.is_dir():
                raise SystemExit(f"Missing required package directory: {directory}")
            added = _add_directory(zf, directory, archive_dir)
            if added == 0:
                raise SystemExit(f"No files packed from {directory} into {archive_dir}/")

    names = zipfile.ZipFile(zip_path).namelist()
    if expected_name not in names:
        raise SystemExit(f"{expected_name} missing from ZIP root: {names[:10]}")
    jobdefs = [n for n in names if n.startswith("Jobs/") and n.endswith(".jobdef")]
    job_scripts = [n for n in names if n.startswith("JobsScrips/") and n.endswith(".py")]
    if not jobdefs or not job_scripts:
        raise SystemExit(
            "Jobs missing from ZIP in SecOps folder names "
            f"(Jobs/*.jobdef and JobsScrips/*.py). Found: {names}"
        )
    print(f"Wrote {zip_path} ({len(names)} files, {len(jobdefs)} jobs)")


if __name__ == "__main__":
    main()
