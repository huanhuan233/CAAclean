"""Scope a new composite projection to an existing matching local Revision.

This never replaces the native tree, generic properties, feature recognition or
source model. Default is read-only. Apply publishes only composite evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from pathlib import Path
from uuid import UUID

from app.cad.repository import CadRepository
from app.component_builds.caa_new_bundle import CaaNewBundleReader
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
from app.db.session import SessionLocal


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


async def backfill(revision_id: UUID, bundle: Path, apply: bool) -> dict:
    reader = CaaNewBundleReader(bundle)
    if reader.manifest.get("capture_status") != "complete" or reader.manifest.get("document_count") != 1:
        raise ValueError("complete single-document R21 capture required")
    records = reader.composite_structure()
    if not records:
        raise ValueError("bundle has no composite definitions")
    async with SessionLocal() as session:
        repository = SqlAlchemyComponentBuildRepository(session)
        revision = await repository.get_raw_revision(revision_id)
        if revision is None:
            raise ValueError("revision not found")
        source = Path(revision.source_file_path)
        if not source.is_file() or _sha256(source) != str(revision.source_sha256).lower():
            raise ValueError("revision source file is missing or changed")
        tree_storage = (revision.parse_manifest or {}).get("native_tree_storage") or {}
        if (not tree_storage.get("complete") or
                tree_storage.get("node_count") != reader.manifest.get("occurrence_count")):
            raise ValueError("capture occurrence count differs from persisted revision tree")
        for record in records:
            if not record["occurrence_ids"]:
                raise ValueError(f"composite object has no matching tree occurrence: {record['object_id']}")
            for occurrence_id in record["occurrence_ids"]:
                entity = await repository.get_native_tree_entity(revision_id, occurrence_id)
                metadata = dict(entity.metadata_json or {}) if entity else {}
                if (metadata.get("object_id") != record["object_id"] or
                        metadata.get("startup_type") != record["startup_type"] or
                        metadata.get("document_id") != record["document_id"]):
                    raise ValueError(f"capture/tree identity mismatch: {record['object_id']}")
        summary = {"revision_id": str(revision_id), "definition_count": len(records),
                   "ply_count": sum(record["kind"] == "ply" for record in records),
                   "status": "validated_not_applied"}
        if not apply:
            return summary
        writer = CadRepository(session)
        async with writer.native_publish_transaction():
            counts = await writer.replace_native_evidence(revision_id, {
                "composite_structure": records, "composite_coverage": []}, replace_all=False)
            await writer.update_revision_manifest(revision_id, {
                "native_evidence_storage": {"backend": "postgresql", "complete": True,
                                            "counts": {"composite_structure": counts["composite_structure"]}},
                "composite_coverage_storage": {"backend": "postgresql", "complete": False,
                                               "counts": {}, "status": "source_changed"}})
        summary["status"] = "published"
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True, type=UUID)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(asyncio.run(backfill(args.revision, args.bundle, args.apply)))


if __name__ == "__main__":
    main()
