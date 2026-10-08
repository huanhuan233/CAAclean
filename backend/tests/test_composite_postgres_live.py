"""Opt-in real PostgreSQL check in a connection-local temporary table only."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.cad.repository import CadRepository
from app.component_builds.repository import SqlAlchemyComponentBuildRepository
from app.core.config import get_settings


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("CAA_TEST_POSTGRES") != "1", reason="requires local PostgreSQL")
async def test_composite_definition_pagination_and_detail_identity():
    engine = create_async_engine(get_settings().database_url)
    revision = uuid4()
    try:
        async with engine.connect() as connection:
            await connection.execute(text(
                "CREATE TEMP TABLE cad_native_evidence (LIKE public.cad_native_evidence INCLUDING DEFAULTS, "
                "PRIMARY KEY (revision_id, kind, ordinal))"))
            await connection.commit()
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                repository = CadRepository(session)
                rows = [{"object_id": "ply_a", "kind": "ply", "display_name": "Ply.1"},
                        {"object_id": "ply_b", "kind": "ply", "display_name": "Ply.1"}]
                assert await repository.replace_native_evidence(
                    revision, {"composite_structure": rows}, replace_all=False,
                ) == {"composite_structure": 2}
                assert await repository.list_native_evidence(revision, "composite_structure", 0, 1) == rows[:1]
                assert await repository.list_native_evidence(revision, "composite_structure", 1, 1) == rows[1:]
                assert await repository.get_native_evidence_object(
                    revision, "composite_structure", "ply_b") == rows[1]
                assert await repository.get_native_evidence_object(
                    revision, "composite_structure", "missing") is None
                viewer_repository = SqlAlchemyComponentBuildRepository(session)
                assert await viewer_repository.get_native_evidence_object(
                    revision, "composite_structure", "ply_b") == rows[1]
                coverage = {"object_id": "group", "status": "computed", "cells": [
                    {"region_id": "region_1", "ply_object_ids": ["ply_a", "ply_b"],
                     "nominal_thickness_mm": 0.5}]}
                assert await repository.replace_native_evidence(
                    revision, {"composite_coverage": [coverage]}, replace_all=False,
                ) == {"composite_coverage": 1}
                assert await viewer_repository.get_native_evidence_object(
                    revision, "composite_coverage", "group") == coverage
    finally:
        await engine.dispose()
