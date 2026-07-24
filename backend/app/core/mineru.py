from __future__ import annotations

import asyncio
import json
import shlex
import urllib.request
from pathlib import Path
from typing import Awaitable, Callable


class MineruError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class MineruClient:
    def __init__(
        self,
        *,
        mode: str = "disabled",
        url: str | None = None,
        command: str | None = None,
        timeout: int = 180,
        transport: Callable[[Path], Awaitable[dict]] | None = None,
    ):
        self.mode = mode
        self.url = url
        self.command = command
        self.timeout = timeout
        self.transport = transport

    async def fetch_payload(self, input_path: Path) -> dict:
        if self.mode == "disabled":
            raise MineruError("mineru_not_configured", "MinerU provider is disabled")
        try:
            if self.transport:
                payload = await asyncio.wait_for(self.transport(input_path), timeout=self.timeout)
            elif self.mode == "http":
                payload = await asyncio.wait_for(asyncio.to_thread(self._http_fetch, input_path), timeout=self.timeout)
            elif self.mode == "command":
                payload = await asyncio.wait_for(self._command_fetch(input_path), timeout=self.timeout)
            else:
                raise MineruError("mineru_not_configured", "unsupported MinerU layout mode")
        except TimeoutError as exc:
            raise MineruError("mineru_timeout", "MinerU layout detection timed out") from exc
        except MineruError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MineruError("mineru_invalid_result", "MinerU returned an invalid JSON result") from exc
        except Exception as exc:
            raise MineruError("mineru_connection_failed", "MinerU layout detection failed") from exc
        if not isinstance(payload, dict):
            raise MineruError("mineru_invalid_result", "MinerU returned an invalid JSON result")
        return payload

    def _http_fetch(self, input_path: Path) -> dict:
        if not self.url:
            raise MineruError("mineru_not_configured", "MINERU_LAYOUT_URL is not configured")
        request = urllib.request.Request(
            self.url,
            data=input_path.read_bytes(),
            method="POST",
            headers={"Content-Type": "application/octet-stream"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    async def _command_fetch(self, input_path: Path) -> dict:
        if not self.command:
            raise MineruError("mineru_not_configured", "MINERU_LAYOUT_COMMAND is not configured")
        args = [*shlex.split(self.command), str(input_path)]
        process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, _stderr = await process.communicate()
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
            try:
                await asyncio.wait_for(process.wait(), timeout=1)
            except TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            raise
        if process.returncode != 0:
            raise MineruError("mineru_connection_failed", "MinerU command failed")
        return json.loads(stdout.decode("utf-8"))
