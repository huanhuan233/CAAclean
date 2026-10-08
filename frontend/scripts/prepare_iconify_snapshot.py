"""Verify and archive the lockfile's complete @iconify/json package for transport."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "frontend/node_modules/@iconify/json"
DESTINATION = ROOT / "offline-assets/iconify"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def prepare(package: Path, destination: Path) -> dict:
    metadata = json.loads((package / "package.json").read_text(encoding="utf-8"))
    version = metadata["version"]
    collection_metadata = json.loads((package / "collections.json").read_text(encoding="utf-8"))
    collection_files = sorted((package / "json").glob("*.json"))
    prefixes = {path.stem for path in collection_files}
    if not set(collection_metadata).issubset(prefixes):
        raise ValueError("a collection named in collections.json is missing from the package")
    extra_prefixes = sorted(prefixes - set(collection_metadata))
    icon_count = alias_count = 0
    for path in collection_files:
        collection = json.loads(path.read_text(encoding="utf-8"))
        if collection.get("prefix") != path.stem or not isinstance(collection.get("icons"), dict):
            raise ValueError(f"invalid collection: {path.name}")
        icon_count += len(collection["icons"])
        alias_count += len(collection.get("aliases") or {})
    files = sorted(path for path in package.rglob("*") if path.is_file())
    file_hashes = {str(path.relative_to(package)).replace("\\", "/"): digest(path) for path in files}
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"iconify-json-{version}.tar.gz"
    with tarfile.open(archive, "w:gz", compresslevel=6, dereference=True) as output:
        for path in files:
            relative = str(path.relative_to(package)).replace("\\", "/")
            info = output.gettarinfo(str(path), arcname=f"@iconify/json/{relative}")
            info.mtime = 0
            with path.open("rb") as stream:
                output.addfile(info, stream)
    manifest = {
        "package": "@iconify/json", "version": version,
        "source": "npm package resolved by frontend/pnpm-lock.yaml",
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "collections": len(prefixes), "icons": icon_count, "aliases": alias_count,
        "collections_without_index_entry": extra_prefixes,
        "archive": archive.name, "archive_bytes": archive.stat().st_size,
        "archive_sha256": digest(archive), "file_sha256": file_hashes,
        "license_metadata": "collections.json and each json/<prefix>.json info block are included in the archive",
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in manifest.items() if key != "file_sha256"}


def verify(destination: Path) -> dict:
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    archive = destination / manifest["archive"]
    if archive.stat().st_size != manifest["archive_bytes"] or digest(archive) != manifest["archive_sha256"]:
        raise ValueError("Iconify archive size or hash mismatch")
    expected = manifest["file_sha256"]
    with tarfile.open(archive, "r:gz") as source:
        members = {member.name.removeprefix("@iconify/json/"): member for member in source if member.isfile()}
        if set(members) != set(expected):
            raise ValueError("Iconify archive members differ from file hash manifest")
        for name, member in members.items():
            stream = source.extractfile(member)
            if stream is None:
                raise ValueError(f"cannot read {name}")
            if hashlib.sha256(stream.read()).hexdigest() != expected[name]:
                raise ValueError(f"Iconify archive member hash mismatch: {name}")
    return {"status": "verified", "version": manifest["version"], "files": len(expected),
            "collections": manifest["collections"], "archive_sha256": manifest["archive_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--destination", type=Path, default=DESTINATION)
    parser.add_argument("--verify", action="store_true", help="verify every archived file against manifest")
    args = parser.parse_args()
    result = verify(args.destination) if args.verify else prepare(args.package, args.destination)
    print(json.dumps(result, ensure_ascii=False, indent=2))
