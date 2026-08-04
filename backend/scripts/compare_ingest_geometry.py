"""从命令行执行 STEP/CATPart Feature Center Bundle 几何对照。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.component_builds.geometry_compare import compare_feature_center_bundles


# 用途：读取两个 Bundle 路径，输出机器可读报告，并在不匹配时返回非零退出码。
def main() -> int:
    parser = argparse.ArgumentParser(description="对照同一零件的 STEP 与 CATPart Web 产物")
    parser.add_argument("--step-bundle", required=True)
    parser.add_argument("--catpart-bundle", required=True)
    args = parser.parse_args()
    result = compare_feature_center_bundles(Path(args.step_bundle), Path(args.catpart_bundle))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["status"] == "match" else 1


if __name__ == "__main__":
    raise SystemExit(main())
