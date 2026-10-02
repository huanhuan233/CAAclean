from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import REPOSITORY_ROOT


@dataclass(frozen=True)
class CaaNewCaptureResult:
    capture_status: str
    schema_version: str
    parser_version: str
    document_kind: str
    manifest_path: Path
    artifact_paths: dict[str, Path]
    diagnostic_summary: dict[str, Any]
    capability_summary: dict[str, Any]
    has_geometry: bool
    selected_reconstruction_route: str
    exact_brep_body_count: int | None = None
    incomplete_brep_body_count: int | None = None


class CaaNewRunnerError(RuntimeError):
    def __init__(self, code: str, stage: str, message: str):
        super().__init__(message)
        self.code = code
        self.stage = stage


class CaaNewRunner:
    # 平台、目标位数和脚本是一组契约；不能因本机缺少 x64 就静默切回 x86。
    _TARGETS = {"intel_a": (32, "run_r21_x86.bat", 0x14C), "win_b64": (64, "run_r21_x64.bat", 0x8664)}
    def __init__(
        self,
        *,
        project_root: Path | None = None,
        runner: Path | None = None,
        platform: str = "intel_a",
        bitness: int = 32,
        rade_root: str = "",
        prereq_root: str = "",
    ):
        self.project_root = (project_root or REPOSITORY_ROOT / "caa_new").resolve()
        self.platform = platform
        self.bitness = bitness
        target = self._TARGETS.get(platform)
        self.runner = (runner or self.project_root / "tools" / (target[1] if target else "unsupported-platform.bat")).resolve()
        self.rade_root = rade_root
        self.prereq_root = prereq_root

    def parser_available(self) -> bool:
        try:
            self._validate_target()
            return True
        except CaaNewRunnerError:
            return False

    def _validate_target(self) -> None:
        target = self._TARGETS.get(self.platform)
        if target is None or target[0] != self.bitness:
            raise CaaNewRunnerError("caa_new_platform_invalid", "running_caa", "CAA 平台与位数不匹配：intel_a/32 或 win_b64/64")
        script_name = self.runner.name.casefold()
        if script_name in {item[1] for item in self._TARGETS.values()} and script_name != target[1]:
            raise CaaNewRunnerError("caa_new_platform_invalid", "running_caa", "CAA 运行脚本与目标位数不匹配")
        if not self.runner.is_file():
            raise CaaNewRunnerError("caa_new_runner_missing", "running_caa", "CAA_NEW 运行脚本不存在")
        executable = self.project_root / self.platform / "code" / "bin" / "CadCapture.exe"
        if not executable.is_file():
            raise CaaNewRunnerError("caa_new_executable_missing", "running_caa", f"缺少 {self.platform} 的 CadCapture.exe")
        # 读取 PE 文件头验证真实架构，避免把改目录名当作完成了 64 位编译。
        try:
            with executable.open("rb") as stream:
                header = stream.read(64)
                if len(header) != 64 or header[:2] != b"MZ":
                    raise ValueError("not a PE executable")
                stream.seek(struct.unpack_from("<I", header, 0x3C)[0])
                pe = stream.read(6)
                if len(pe) != 6 or pe[:4] != b"PE\0\0" or struct.unpack_from("<H", pe, 4)[0] != target[2]:
                    raise ValueError("PE machine mismatch")
        except (OSError, ValueError, struct.error) as exc:
            raise CaaNewRunnerError("caa_new_binary_incompatible", "running_caa", f"CadCapture.exe 不是所配置的 {self.bitness} 位程序") from exc

    async def capture(self, source_path: Path, output_dir: Path, *, timeout_seconds: int) -> CaaNewCaptureResult:
        self._validate_target()
        if not source_path.is_file():
            raise CaaNewRunnerError("caa_source_missing", "running_caa", "CATIA 源文件不存在")

        output_dir.mkdir(parents=True, exist_ok=True)
        command = [
            "cmd.exe",
            "/d",
            "/c",
            str(self.runner),
            "--input",
            str(source_path),
            "--output",
            str(output_dir),
        ]
        environment = {
            **os.environ,
            "CAA_RADE_ROOT": self.rade_root or os.environ.get("CAA_RADE_ROOT", ""),
            "CAA_PREREQ_ROOT": self.prereq_root or os.environ.get("CAA_PREREQ_ROOT", ""),
            "_MkmkOS_BitMode": str(self.bitness),
        }
        try:
            return_code, output = await self._run(command, timeout_seconds, environment)
        except asyncio.TimeoutError as exc:
            raise CaaNewRunnerError("caa_new_timeout", "running_caa", "CAA_NEW 处理超时") from exc
        log_path = output_dir / "caa_new_runner.log"
        log_path.write_text(output, encoding="utf-8")
        if return_code != 0:
            raise CaaNewRunnerError("caa_parse_failed", "running_caa", f"CAA_NEW 退出码 {return_code}")
        return self.inspect(output_dir)

    def inspect(self, output_dir: Path) -> CaaNewCaptureResult:
        manifest_path = output_dir / "manifest.json"
        if not manifest_path.is_file():
            raise CaaNewRunnerError("caa_new_manifest_missing", "running_caa", "CAA_NEW 未生成 manifest.json")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not str(manifest.get("schema_version") or "").startswith("caa_capture_"):
            raise CaaNewRunnerError("caa_new_manifest_invalid", "running_caa", "CAA_NEW manifest schema 不受支持")

        artifact_paths: dict[str, Path] = {}
        for path in sorted(output_dir.iterdir()):
            # 事务标记只是原生写出内部状态，绝不作为采集产物上传或入库。
            if path.is_file() and path.name != "caa_new_runner.log" and not path.name.startswith(".cadcapture_"):
                artifact_paths[path.name] = path

        required = ("manifest.json", "object_entities.jsonl", "tree_occurrences.jsonl", "property_facts.jsonl")
        missing = [name for name in required if name not in artifact_paths]
        if missing:
            raise CaaNewRunnerError("caa_new_artifact_missing", "running_caa", "CAA_NEW 缺少必需产物：" + ",".join(missing))

        return CaaNewCaptureResult(
            capture_status=str(manifest.get("capture_status") or "unknown"),
            schema_version=str(manifest.get("schema_version") or ""),
            parser_version=str(manifest.get("parser_version") or ""),
            document_kind=str(manifest.get("document_kind") or manifest.get("source_format") or ""),
            manifest_path=manifest_path,
            artifact_paths=artifact_paths,
            diagnostic_summary=self._read_optional_json(output_dir / "diagnostics.json"),
            capability_summary=self._read_optional_json(output_dir / "capabilities.json"),
            has_geometry=int(manifest.get("geometry_count") or 0) > 0,
            selected_reconstruction_route=str(manifest.get("selected_reconstruction_route") or ""),
            exact_brep_body_count=int(manifest["exact_brep_body_count"]) if "exact_brep_body_count" in manifest else None,
            incomplete_brep_body_count=int(manifest["incomplete_brep_body_count"]) if "incomplete_brep_body_count" in manifest else None,
        )

    @staticmethod
    def archive_native_bundle(native_dir: Path, archive_path: Path) -> list[dict[str, Any]]:
        archive_path.unlink(missing_ok=True)
        shutil.make_archive(str(archive_path.with_suffix("")), "zip", native_dir.parent, native_dir.name)
        archive_path = archive_path.with_suffix(".zip")
        artifacts: list[dict[str, Any]] = []
        for path in sorted(native_dir.rglob("*")):
            if not path.is_file():
                continue
            data = path.read_bytes()
            artifacts.append({"name": path.relative_to(native_dir).as_posix(), "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return artifacts

    @staticmethod
    async def _run(command: list[str], timeout_seconds: int, environment: dict[str, str]) -> tuple[int, str]:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(REPOSITORY_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=environment,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), timeout=max(1, timeout_seconds))
        except (asyncio.TimeoutError, asyncio.CancelledError):
            await _terminate_process_tree(process)
            raise
        return int(process.returncode or 0), output.decode("utf-8", errors="replace")

    @staticmethod
    def _read_optional_json(path: Path) -> dict[str, Any]:
        if not path.is_file() or path.stat().st_size == 0:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"items": value}


async def _terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec(
            "taskkill.exe",
            "/F",
            "/T",
            "/PID",
            str(process.pid),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.communicate()
    else:
        process.kill()
    await process.wait()
