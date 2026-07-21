from pathlib import Path

import pytest

from scripts.test_real_freecad import DEFAULT_STEP_PATH, validate_step_path


def test_default_real_freecad_path_uses_xms06_sample():
    assert DEFAULT_STEP_PATH == Path(r"D:\3D解析\XMS06-DN80.stp")


def test_validate_step_path_rejects_non_step_file(tmp_path):
    file_path = tmp_path / "bad.txt"
    file_path.write_text("not step", encoding="utf-8")

    with pytest.raises(ValueError, match="STEP/STP"):
        validate_step_path(file_path)


def test_validate_step_path_accepts_existing_stp(tmp_path):
    file_path = tmp_path / "part.stp"
    file_path.write_text("ISO-10303-21;", encoding="utf-8")

    assert validate_step_path(file_path) == file_path
