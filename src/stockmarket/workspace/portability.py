"""Checksummed, consistent SQLite backup and staged restore for QuantEdge.

Backs up the v2 workspace plus optional legacy paper DB as separate SQLite
snapshots. Restores into a NEW directory only; the running app must be stopped
and its configured paths changed explicitly, avoiding overwriting live engines.
No SQL scripts are imported. No unrestricted ZIP extraction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import zipfile

from .database import WorkspaceDB

FORMAT = "quantedge-local-backup/v1"
MAX_ARCHIVE = 100 * 1024 * 1024
MAX_DATABASE = 180 * 1024 * 1024
WORKSPACE_TABLES = {"workspace_symbols", "workspace_ohlcv", "workspace_schema_versions"}
ALLOWED = {"workspace.sqlite", "paper.sqlite"}
MAX_MANIFEST = 10000


def _check_sqlite(path: Path, *, workspace: bool) -> None:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("SQLite integrity check failed")
            if workspace:
                names = {r[0] for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
                if not WORKSPACE_TABLES.issubset(names):
                    raise ValueError("The uploaded database is not a QuantEdge workspace")
    except sqlite3.DatabaseError as exc:
        raise ValueError("The uploaded file is not a valid SQLite database") from exc


def _snapshot(source: Path) -> bytes:
    if not source.is_file() or source.stat().st_size > MAX_DATABASE:
        raise ValueError("SQLite database missing or over the backup size limit")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "snapshot.sqlite"
        # SQLite online backup includes committed WAL changes consistently.
        with sqlite3.connect(str(source), timeout=10) as original:
            with sqlite3.connect(str(target)) as snapshot:
                original.backup(snapshot)
        if target.stat().st_size > MAX_DATABASE:
            raise ValueError("SQLite snapshot exceeded the backup size limit")
        return target.read_bytes()


def make_archive(db: WorkspaceDB, legacy_path: str | None = None) -> bytes:
    """Export both databases when present. Does not mutate either database."""
    sources = {"workspace.sqlite": Path(db.path)}
    if legacy_path and Path(legacy_path).is_file():
        sources["paper.sqlite"] = Path(legacy_path)
    payloads = {name: _snapshot(path) for name, path in sources.items()}
    manifest = {
        "format": FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "databases": {
            name: {"size": len(data), "sha256": sha256(data).hexdigest()}
            for name, data in payloads.items()
        },
    }
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=False) as out:
        out.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, data in payloads.items():
            out.writestr(name, data)
    result = archive.getvalue()
    if len(result) > MAX_ARCHIVE:
        raise ValueError("Backup archive exceeds the 100 MB size limit")
    return result


def inspect_archive(content: bytes) -> dict:
    """Verify manifest, archive layout, hashes, sizes and SQLite integrity."""
    if not isinstance(content, bytes) or not content or len(content) > MAX_ARCHIVE:
        raise ValueError("Backup archive empty or exceeds 100 MB")
    try:
        with zipfile.ZipFile(BytesIO(content), "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(set(names)) != len(names) or set(names) - (ALLOWED | {"manifest.json"}):
                raise ValueError("Unknown or duplicate archive entry")
            if not {"workspace.sqlite", "manifest.json"}.issubset(names) or len(infos) > 3:
                raise ValueError("Backup must include workspace and manifest")
            if any(info.file_size > (MAX_MANIFEST if info.filename == "manifest.json"
                                    else MAX_DATABASE) for info in infos):
                raise ValueError("Backup entry exceeds size limit")
            if any(info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000 for info in infos):
                raise ValueError("Backup cannot contain links or folders")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != FORMAT:
                raise ValueError("Unsupported backup format")
            databases = manifest.get("databases")
            if not isinstance(databases, dict) or set(databases) != set(names) - {"manifest.json"}:
                raise ValueError("Backup manifest does not match archive")
            with tempfile.TemporaryDirectory() as folder:
                for name, facts in databases.items():
                    data = archive.read(name)
                    if not isinstance(facts, dict) or not (
                        len(data) == facts.get("size")
                        and sha256(data).hexdigest() == facts.get("sha256")
                    ):
                        raise ValueError("Backup checksum or byte count mismatch")
                    target = Path(folder) / name
                    target.write_bytes(data)
                    _check_sqlite(target, workspace=(name == "workspace.sqlite"))
            return {
                "format": FORMAT,
                "created_at": manifest.get("created_at", "unavailable"),
                "databases": {name: dict(facts) for name, facts in databases.items()},
            }
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Backup archive could not be validated") from exc


def stage_restore(content: bytes, destination: str | Path) -> dict:
    """Restore verified snapshots to a fresh path, never an active SQLite DB."""
    info = inspect_archive(content)
    target = Path(destination).resolve()
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError("Restore destination already exists; no files were overwritten")
    # Stage files with private filesystem permissions before the atomic dir rename.
    folder = Path(tempfile.mkdtemp(prefix=".qe-restore-", dir=str(parent)))
    try:
        with zipfile.ZipFile(BytesIO(content), "r") as archive:
            for filename in info["databases"]:
                target_file = folder / filename
                target_file.write_bytes(archive.read(filename))
                target_file.chmod(0o600)
                _check_sqlite(target_file, workspace=(filename == "workspace.sqlite"))
        os.rename(folder, target)  # parent is same filesystem
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return {
        "restored_directory": str(target),
        "workspace_db": str(target / "workspace.sqlite"),
        "paper_db": str(target / "paper.sqlite") if "paper.sqlite" in info["databases"] else None,
        "requires_restart": True,
        "archive": info,
    }
