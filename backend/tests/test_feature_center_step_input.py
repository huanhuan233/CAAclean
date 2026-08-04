import hashlib
from pathlib import Path

import pytest

from app.feature_center.step_input import StepInputError, inspect_step_input


# 用途：验证 STEP Header、毫米单位、文件哈希和默认单位变换能够被确定读取。
def test_inspect_step_input_reads_schema_hash_and_millimetre_unit(tmp_path: Path) -> None:
    source = tmp_path / "part.step"
    source.write_text(
        "ISO-10303-21;\nHEADER;FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));ENDSEC;\n"
        "DATA;#1=SI_UNIT(.MILLI.,.METRE.);ENDSEC;END-ISO-10303-21;\n",
        encoding="ascii",
    )

    inspected = inspect_step_input(source)

    assert inspected.file_name == "part.step"
    assert inspected.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert inspected.step_schema == "AUTOMOTIVE_DESIGN"
    assert inspected.source_unit == "mm"
    assert inspected.kernel_unit == "mm"
    assert inspected.source_to_kernel_scale == 1.0
    assert inspected.source_to_kernel_transform[0] == [1.0, 0.0, 0.0, 0.0]


# 用途：验证缺失或不是 STEP 的输入在进入 FreeCAD 前就返回明确错误。
def test_inspect_step_input_rejects_missing_and_invalid_files(tmp_path: Path) -> None:
    with pytest.raises(StepInputError, match="STEP_INPUT_NOT_FOUND"):
        inspect_step_input(tmp_path / "missing.step")

    invalid = tmp_path / "invalid.step"
    invalid.write_text("not a step file", encoding="utf-8")
    with pytest.raises(StepInputError, match="STEP_HEADER_INVALID"):
        inspect_step_input(invalid)


# 用途：验证单位无法确认时明确失败，避免把错误比例的几何静默当成毫米。
def test_inspect_step_input_rejects_unknown_unit(tmp_path: Path) -> None:
    source = tmp_path / "unknown-unit.step"
    source.write_text(
        "ISO-10303-21;HEADER;FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));ENDSEC;"
        "DATA;ENDSEC;END-ISO-10303-21;",
        encoding="ascii",
    )
    with pytest.raises(StepInputError, match="STEP_UNIT_UNKNOWN"):
        inspect_step_input(source)
