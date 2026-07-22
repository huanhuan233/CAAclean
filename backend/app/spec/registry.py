from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.spec.schemas import ComponentProfile, FieldDefinition, FieldMapping


SPEC_DIR = Path(__file__).resolve().parent


class ProfileRegistry:
    def __init__(self, *, profiles: dict[str, ComponentProfile], field_catalog: dict[str, FieldDefinition]):
        self.profiles = profiles
        self.field_catalog = field_catalog

    @classmethod
    def default(cls) -> "ProfileRegistry":
        return cls.from_directory(SPEC_DIR)

    @classmethod
    def from_directory(cls, root: Path) -> "ProfileRegistry":
        field_catalog = _load_field_catalog(root / "field-catalog.yaml")
        profiles = {}
        for path in sorted((root / "profiles").glob("*.yaml")):
            profile = _load_profile(path)
            profiles[profile.profile_id] = profile
        return cls(profiles=profiles, field_catalog=field_catalog)

    def get(self, profile_id: str) -> ComponentProfile:
        return self.profiles[profile_id]

    def select(self, *, component_type: str | None, subtype: str | None = None, profile_id: str | None = None) -> ComponentProfile:
        if profile_id:
            return self.get(profile_id)
        normalized_type = (component_type or "unknown").lower()
        normalized_subtype = (subtype or "").lower()
        for profile in self.profiles.values():
            if profile.profile_id == "generic":
                continue
            if profile.component_type.lower() == normalized_type and (not profile.subtype or profile.subtype.lower() == normalized_subtype):
                return profile
        return self.get("generic")


def _load_field_catalog(path: Path) -> dict[str, FieldDefinition]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        item["name"]: FieldDefinition.model_validate(item)
        for item in payload.get("fields", [])
    }


def _load_profile(path: Path) -> ComponentProfile:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_mappings: dict[str, Any] = payload.get("field_mappings", {})
    payload["field_mappings"] = {
        symbol: FieldMapping(symbol=symbol, **mapping)
        for symbol, mapping in raw_mappings.items()
    }
    return ComponentProfile.model_validate(payload)

