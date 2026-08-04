from pathlib import Path


# 用途：锁定独立 Automation 导出器不含仓库绝对路径，并保留只读关闭与源文件哈希校验。
def test_catia_step_export_script_is_portable_and_read_only() -> None:
    script = Path(__file__).resolve().parents[2] / "3DjiexiCAA" / "tools" / "export_catpart_step.ps1"
    automation = script.with_suffix(".vbs")
    text = script.read_text(encoding="utf-8-sig")
    automation_text = automation.read_text(encoding="utf-8-sig")

    assert "D:\\3Djiexi" not in text
    assert "cscript.exe" in text
    assert "Get-FileHash" in text
    assert "Stop-Process" not in text
    assert "ExportData" in automation_text
    assert ".Close" in automation_text
    assert ".Save" not in automation_text
    assert ".Update" not in automation_text
