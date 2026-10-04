"""Revision-scoped native connection evidence queries; no JSONL reads on click."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assembly.context import AssemblyContextError
from app.db.models import CadNativeEvidence
from app.measurement.repository import MeasurementRepository


class ConnectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.measurements = MeasurementRepository(session)

    async def _revision_id(self, build_id: UUID) -> UUID:
        context = await self.measurements.get_build_context(build_id)
        if context is None:
            raise LookupError("component build or revision unavailable")
        return context[1].id

    async def list(self, build_id: UUID, *, offset: int, limit: int,
                   kind: str | None = None) -> dict:
        if kind and kind not in {"fastener", "seal", "bond"}:
            raise AssemblyContextError("invalid_input: connection kind")
        revision_id = await self._revision_id(build_id)
        status = await self.session.scalar(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "connection_semantics_status"))
        if status is None:
            raise AssemblyContextError("connection_source_unavailable: native connection collection was not captured")
        filters = [CadNativeEvidence.revision_id == revision_id,
                   CadNativeEvidence.kind == "connection_semantics"]
        if kind:
            filters.append(CadNativeEvidence.payload["kind"].astext == kind)
        total = int(await self.session.scalar(select(func.count()).select_from(CadNativeEvidence).where(*filters)) or 0)
        rows = await self.session.scalars(select(CadNativeEvidence).where(*filters)
                                          .order_by(CadNativeEvidence.ordinal).offset(offset).limit(limit))
        records = [row.payload for row in rows]
        return {"source_status": status.payload, "records": records, "total": total,
                "has_more": offset + len(records) < total}

    async def detail(self, build_id: UUID, connection_id: str) -> dict:
        if not connection_id or len(connection_id) > 64:
            raise AssemblyContextError("invalid_input: connection ID")
        revision_id = await self._revision_id(build_id)
        status = await self.session.scalar(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "connection_semantics_status"))
        if status is None:
            raise AssemblyContextError("connection_source_unavailable: native connection collection was not captured")
        rows = await self.session.scalars(select(CadNativeEvidence).where(
            CadNativeEvidence.revision_id == revision_id,
            CadNativeEvidence.kind == "connection_semantics",
            CadNativeEvidence.payload["connection_id"].astext == connection_id).limit(2))
        records = [row.payload for row in rows]
        if len(records) != 1:
            raise AssemblyContextError("connection_unavailable: missing or duplicate connection")
        return {"source_status": status.payload, "connection": records[0]}
