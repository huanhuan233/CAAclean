# 从 YAML 加载字段目录与部件配置，并按显式配置或类型/子类型选择规则。
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.spec.schemas import ComponentProfile, FieldDefinition, FieldMapping


SPEC_DIR = Path(__file__).resolve().parent


# 保存已校验的配置和字段目录，为规格生成与绑定提供统一规则入口。
class ProfileRegistry:
    # 接收解析完成的配置索引和字段定义索引。
    def __init__(self, *, profiles: dict[str, ComponentProfile], field_catalog: dict[str, FieldDefinition]):
        self.profiles = profiles
        self.field_catalog = field_catalog

    # 以当前 spec 包目录作为默认 YAML 配置根目录。
    @classmethod
    def default(cls) -> "ProfileRegistry":
        return cls.from_directory(SPEC_DIR)

    # 加载字段目录及按文件名排序的配置；相同配置 ID 后加载项覆盖先前项。
    @classmethod
    def from_directory(cls, root: Path) -> "ProfileRegistry":
        field_catalog = _load_field_catalog(root / "field-catalog.yaml")
        profiles = {}
        for path in sorted((root / "profiles").glob("*.yaml")):
            profile = _load_profile(path)
            profiles[profile.profile_id] = profile
        return cls(profiles=profiles, field_catalog=field_catalog)

    # 按 ID 获取配置，缺失时抛出 KeyError。
    def get(self, profile_id: str) -> ComponentProfile:
        return self.profiles[profile_id]

    # 显式 ID 优先，否则按类型及可选子类型匹配，未命中使用 generic 配置。
    def select(self, *, component_type: str | None, subtype: str | None = None, profile_id: str | None = None) -> ComponentProfile:
        if profile_id:
            return self.get(profile_id)
        # 当前选择只使用类型与子类型；配置中的 match_rules 不在这里执行。
        normalized_type = (component_type or "unknown").lower()
        normalized_subtype = (subtype or "").lower()
        for profile in self.profiles.values():
            if profile.profile_id == "generic":
                continue
            if profile.component_type.lower() == normalized_type and (not profile.subtype or profile.subtype.lower() == normalized_subtype):
                return profile
        return self.get("generic")


# 安全解析 YAML 并用字段模型校验，以规范字段名建立索引。
def _load_field_catalog(path: Path) -> dict[str, FieldDefinition]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        item["name"]: FieldDefinition.model_validate(item)
        for item in payload.get("fields", [])
    }


# 将 YAML 映射键补为 symbol 字段，再校验完整部件配置。
def _load_profile(path: Path) -> ComponentProfile:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_mappings: dict[str, Any] = payload.get("field_mappings", {})
    payload["field_mappings"] = {
        symbol: FieldMapping(symbol=symbol, **mapping)
        for symbol, mapping in raw_mappings.items()
    }
    return ComponentProfile.model_validate(payload)

