import subprocess
import sys
from pathlib import Path


# 用途：验证 Sidecar 暴露 build、validate、inspect 三个稳定子命令。
def test_feature_center_cli_exposes_required_commands() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "feature_center.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "build" in completed.stdout
    assert "validate" in completed.stdout
    assert "inspect" in completed.stdout
