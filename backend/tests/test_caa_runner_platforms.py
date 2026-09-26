import struct
from pathlib import Path

import pytest

from app.catia_worker.caa_new_runner import CaaNewRunner, CaaNewRunnerError
from app.catia_worker.server import CatiaWorkerServerSettings, create_app
from fastapi.testclient import TestClient


def install_test_target(root: Path, platform: str, bits: int) -> Path:
    script = root / 'tools' / ('run_r21_x64.bat' if bits == 64 else 'run_r21_x86.bat')
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('@echo off\n')
    binary = root / platform / 'code' / 'bin' / 'CadCapture.exe'
    binary.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(256)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3C, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<H', data, 132, 0x8664 if bits == 64 else 0x14C)
    binary.write_bytes(data)
    return binary


@pytest.mark.parametrize('platform,bits,script', [('intel_a', 32, 'run_r21_x86.bat'), ('win_b64', 64, 'run_r21_x64.bat')])
@pytest.mark.asyncio
async def test_target_controls_script_environment_and_binary(tmp_path, monkeypatch, platform, bits, script):
    install_test_target(tmp_path, platform, bits)
    source = tmp_path / 'part.CATPart'
    source.write_bytes(b'fixture')
    runner = CaaNewRunner(project_root=tmp_path, platform=platform, bitness=bits)
    calls = []

    async def execute(command, timeout, environment):
        calls.append((command, environment))
        return 7, 'controlled child process failure'

    monkeypatch.setattr(runner, '_run', execute)
    assert runner.parser_available()
    with pytest.raises(CaaNewRunnerError) as error:
        await runner.capture(source, tmp_path / 'out', timeout_seconds=5)
    assert error.value.code == 'caa_parse_failed'
    assert Path(calls[0][0][3]).name == script
    assert calls[0][1]['_MkmkOS_BitMode'] == str(bits)


def test_mismatched_binary_is_not_available(tmp_path):
    binary = install_test_target(tmp_path, 'win_b64', 64)
    data = bytearray(binary.read_bytes())
    struct.pack_into('<H', data, 132, 0x14C)
    binary.write_bytes(data)
    runner = CaaNewRunner(project_root=tmp_path, platform='win_b64', bitness=64)
    assert not runner.parser_available()
    with pytest.raises(CaaNewRunnerError) as error:
        runner._validate_target()
    assert error.value.code == 'caa_new_binary_incompatible'


@pytest.mark.parametrize('platform,bits', [('win_b64', 32), ('intel_a', 64), ('unknown', 64)])
def test_inconsistent_target_is_rejected(tmp_path, platform, bits):
    runner = CaaNewRunner(project_root=tmp_path, platform=platform, bitness=bits)
    with pytest.raises(CaaNewRunnerError) as error:
        runner._validate_target()
    assert error.value.code == 'caa_new_platform_invalid'


@pytest.mark.parametrize('script_name', ['run_r21_x86.bat', 'RUN_R21_X86.BAT'])
def test_explicit_x86_script_cannot_launch_x64_target(tmp_path, script_name):
    install_test_target(tmp_path, 'win_b64', 64)
    install_test_target(tmp_path, 'intel_a', 32)
    runner = CaaNewRunner(project_root=tmp_path, platform='win_b64', bitness=64,
                          runner=tmp_path / 'tools' / script_name)
    with pytest.raises(CaaNewRunnerError) as error:
        runner._validate_target()
    assert error.value.code == 'caa_new_platform_invalid'


@pytest.mark.asyncio
async def test_missing_x64_never_uses_existing_x86(tmp_path):
    install_test_target(tmp_path, 'intel_a', 32)
    runner = CaaNewRunner(project_root=tmp_path, platform='win_b64', bitness=64)
    assert not runner.parser_available()
    with pytest.raises(CaaNewRunnerError) as error:
        await runner.capture(tmp_path / 'source.CATPart', tmp_path / 'out', timeout_seconds=1)
    assert error.value.code == 'caa_new_runner_missing'


def test_x64_health_uses_selected_target_script(tmp_path):
    install_test_target(tmp_path, 'win_b64', 64)
    settings = CatiaWorkerServerSettings(_env_file=None, work_dir=tmp_path / 'jobs',
        caa_capture_project_root=tmp_path, caa_capture_platform='win_b64', caa_capture_bitness=64,
        caa_rade_root='D:/rade', caa_prereq_root='D:/catia', caa_capture_runner=None, caa_run_script='')
    with TestClient(create_app(settings)) as client:
        data = client.get('/health').json()
    assert data['parser_available']
    assert data['capture_bitness'] == 64
