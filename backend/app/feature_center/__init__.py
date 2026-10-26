# 特征中心包入口：仅公开数据契约版本号，供调用方检查输出兼容性。
"""Feature Center 现代 Sidecar 的公共入口。"""

from .contracts import FEATURE_CENTER_SCHEMA_VERSION

__all__ = ["FEATURE_CENTER_SCHEMA_VERSION"]
