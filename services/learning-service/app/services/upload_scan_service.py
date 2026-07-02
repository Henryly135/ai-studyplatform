from __future__ import annotations

import shlex
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.core.config import settings


EICAR_TEST_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class UploadScanFailure(ValueError):
    pass


@dataclass(frozen=True)
class UploadScanResult:
    scanner: str
    status: str
    detail: str
    bytes_scanned: int

    def as_metadata(self) -> dict[str, object]:
        return {
            "scanner": self.scanner,
            "status": self.status,
            "detail": self.detail,
            "bytesScanned": self.bytes_scanned,
        }


class UploadScanService:
    def scan_upload(self, upload: UploadFile, *, label: str) -> UploadScanResult:
        if not settings.material_scan_enabled:
            return self._skipped_result()

        original_position = self._tell(upload.file)
        self._seek(upload.file, 0)
        try:
            return self.scan_file_object(upload.file, label=label)
        finally:
            self._seek(upload.file, original_position if original_position is not None else 0)

    def scan_path(self, path: Path, *, label: str) -> UploadScanResult:
        if not settings.material_scan_enabled:
            return self._skipped_result()

        with path.open("rb") as input_stream:
            bytes_scanned = self._scan_chunks(
                self._iter_file_object(input_stream),
                label=label,
                external_scan_path=path,
            )

        return self._clean_result(bytes_scanned)

    def scan_file_object(self, file_object: BinaryIO, *, label: str) -> UploadScanResult:
        if not settings.material_scan_enabled:
            return self._skipped_result()

        bytes_scanned = self._scan_chunks(self._iter_file_object(file_object), label=label)
        return self._clean_result(bytes_scanned)

    def scan_chunks(self, chunks: Iterable[bytes], *, label: str) -> UploadScanResult:
        if not settings.material_scan_enabled:
            return self._skipped_result()

        bytes_scanned = self._scan_chunks(chunks, label=label)
        return self._clean_result(bytes_scanned)

    def _scan_chunks(
        self,
        chunks: Iterable[bytes],
        *,
        label: str,
        external_scan_path: Path | None = None,
    ) -> int:
        temp_file_path: str | None = None
        temp_file = None
        command = settings.material_scan_command.strip()
        if command and external_scan_path is None:
            temp_file = tempfile.NamedTemporaryFile(prefix="material-scan-", delete=False)
            temp_file_path = temp_file.name

        signature_window = b""
        bytes_scanned = 0

        try:
            for chunk in chunks:
                if not chunk:
                    continue

                bytes_scanned += len(chunk)
                if bytes_scanned > settings.material_scan_max_bytes:
                    raise UploadScanFailure(
                        f"File exceeds the configured security scan limit of {settings.material_scan_max_bytes} bytes."
                    )

                search_buffer = signature_window + chunk
                if EICAR_TEST_SIGNATURE in search_buffer:
                    raise UploadScanFailure("File failed security scan: malware test signature detected.")

                signature_window = search_buffer[-(len(EICAR_TEST_SIGNATURE) - 1) :]
                if temp_file is not None:
                    temp_file.write(chunk)

            if temp_file is not None:
                temp_file.flush()
                temp_file.close()
                temp_file = None

            scan_path = external_scan_path or (Path(temp_file_path) if temp_file_path else None)
            if command and scan_path is not None:
                self._run_external_scan(command=command, path=scan_path, label=label)

            return bytes_scanned
        finally:
            if temp_file is not None:
                temp_file.close()
            if temp_file_path is not None:
                Path(temp_file_path).unlink(missing_ok=True)

    def _run_external_scan(self, *, command: str, path: Path, label: str) -> None:
        command_parts = shlex.split(command)
        if not command_parts:
            return

        if any("{path}" in part for part in command_parts):
            args = [part.replace("{path}", str(path)) for part in command_parts]
        else:
            args = [*command_parts, str(path)]

        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                check=False,
                text=True,
                timeout=settings.material_scan_timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise UploadScanFailure(f"File security scanner is unavailable for {label}.") from exc

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "External scanner rejected the file.").strip()
            raise UploadScanFailure(f"File failed security scan: {detail[:300]}")

    def _iter_file_object(self, file_object: BinaryIO) -> Iterable[bytes]:
        chunk_size = max(4096, settings.material_scan_chunk_bytes)
        while True:
            chunk = file_object.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def _clean_result(self, bytes_scanned: int) -> UploadScanResult:
        scanner = "builtin"
        if settings.material_scan_command.strip():
            scanner = "builtin+external"
        return UploadScanResult(
            scanner=scanner,
            status="clean",
            detail="No blocked signature detected.",
            bytes_scanned=bytes_scanned,
        )

    def _skipped_result(self) -> UploadScanResult:
        return UploadScanResult(
            scanner="disabled",
            status="skipped",
            detail="Material security scanning is disabled.",
            bytes_scanned=0,
        )

    def _tell(self, file_object: BinaryIO) -> int | None:
        try:
            return file_object.tell()
        except (AttributeError, OSError):
            return None

    def _seek(self, file_object: BinaryIO, position: int) -> None:
        try:
            file_object.seek(position)
        except (AttributeError, OSError):
            return
