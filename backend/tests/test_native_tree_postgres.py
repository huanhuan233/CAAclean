"""Opt-in checks with real FK constraints in a connection-local temporary table.

Run with CAA_TEST_POSTGRES=1. Existing application data is never modified.
"""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.cad.repository import CadRepository
from app.component_builds.caa_new_bundle import CaaNewBundleReader
from app.component_builds.native_tree_store import native_tree_rows
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
from app.core.config import get_settings


pytestmark = pytest.mark.skipif(
    os.environ.get("CAA_TEST_POSTGRES") != "1", reason="requires local PostgreSQL"
)


async def check_database_rows(rows, revision_id):
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text(
                "CREATE TEMP TABLE cad_entities (LIKE public.cad_entities INCLUDING DEFAULTS, "
                "PRIMARY KEY (id), FOREIGN KEY (parent_entity_id) REFERENCES pg_temp.cad_entities(id))"
            ))
            await connection.commit()
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                repository = CadRepository(session)
                # Reverse input to exercise dependency ordering across 1,000-row batches.
                assert await repository.replace_native_tree_entities(
                    revision_id, list(reversed(rows)), len(rows)
                ) == len(rows)
                result = await session.execute(text("SELECT id, parent_entity_id FROM pg_temp.cad_entities"))
                assert {entity_id: parent_id for entity_id, parent_id in result} == {
                    row["id"]: row["parent_entity_id"] for row in rows
                }
                invalid = [dict(row) for row in rows]
                invalid[0]["parent_entity_id"] = uuid4()
                with pytest.raises(ValueError, match="missing parent"):
                    await repository.replace_native_tree_entities(revision_id, invalid, len(rows))
                assert await session.scalar(text("SELECT count(*) FROM pg_temp.cad_entities")) == len(rows)
            await connection.execute(text("DROP TABLE pg_temp.cad_entities"))
            await connection.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,size", [("CATPart", 1), ("CATPart", 1005), ("CATProduct", 1005)])
async def test_complete_tree_with_real_foreign_keys(kind, size):
    revision_id = uuid4()
    root = {"node_id": "root", "node_kind": "product_occurrence", "startup_type": kind,
            "children": [{"node_id": f"part-{i}", "parent_id": "root",
                          "presentation_status": "non_primary" if i % 2 else "visible",
                          "children": [{"node_id": f"feature-{i}", "parent_id": f"part-{i}"}]}
                         for i in range(size)]}
    rows = native_tree_rows(revision_id, {"roots": [root], "node_count": 1 + size * 2})
    await check_database_rows(rows, revision_id)


@pytest.mark.asyncio
async def test_existing_caa_bundles_with_real_foreign_keys():
    bundle_root = Path(__file__).resolve().parents[1] / "cad-spec-work"
    bundles = sorted(bundle_root.glob("*/native-caa/manifest.json"))
    if not bundles:
        pytest.skip("no local capture bundles")
    for manifest in bundles:
        reader = CaaNewBundleReader(manifest.parent)
        tree = reader.build_tree(include_supplemental=True)
        revision_id = uuid4()
        rows = native_tree_rows(revision_id, tree)
        await check_database_rows(rows, revision_id)
        print(f"verified {manifest.parent.parent.name}: {len(rows)} nodes", flush=True)


@pytest.mark.asyncio
async def test_linked_catproduct_bundle_with_real_foreign_keys():
    """关联 CATPart 的新增类型化/拓扑证据不得破坏完整树入库顺序。"""
    bundle_path = os.environ.get("CAA_LINKED_BUNDLE")
    if not bundle_path:
        pytest.skip("set CAA_LINKED_BUNDLE to a captured CATProduct bundle")
    reader = CaaNewBundleReader(Path(bundle_path))
    tree = reader.build_tree(include_supplemental=True)
    revision_id = uuid4()
    rows = native_tree_rows(revision_id, tree)
    assert rows
    await check_database_rows(rows, revision_id)


@pytest.mark.asyncio
async def test_default_tree_query_excludes_supplemental_after_sql_pagination():
    revision_id = uuid4()
    rows = native_tree_rows(revision_id, {"roots": [{
        "node_id": "root", "presentation_status": "visible", "children": [
            {"node_id": "sag", "presentation_status": "non_primary"},
            {"node_id": "plies", "presentation_status": "visible"},
        ],
    }], "node_count": 3})
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text(
                "CREATE TEMP TABLE cad_entities (LIKE public.cad_entities INCLUDING DEFAULTS, "
                "PRIMARY KEY (id), FOREIGN KEY (parent_entity_id) REFERENCES pg_temp.cad_entities(id))"
            ))
            await connection.commit()
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                await CadRepository(session).replace_native_tree_entities(revision_id, rows, 3)
                repository = SqlAlchemyComponentBuildRepository(session)
                visible = await repository.list_native_tree_entities(
                    revision_id, "root", limit=2, include_supplemental=False
                )
                assert [row.metadata_json["node_id"] for row in visible] == ["plies"]
                all_rows = await repository.list_native_tree_entities(
                    revision_id, "root", limit=2, include_supplemental=True
                )
                assert [row.metadata_json["node_id"] for row in all_rows] == ["sag", "plies"]
            await connection.execute(text("DROP TABLE pg_temp.cad_entities"))
            await connection.commit()
    finally:
        await engine.dispose()
