from __future__ import annotations

import base64
import binascii
import os
import tempfile
from dataclasses import dataclass
from email.message import Message
from email.utils import collapse_rfc2231_value
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.schemas.extraction import BackendFileDescriptor
from app.services.file_validation_service import MIME_ALIASES, SUPPORTED
from app.services.url_file_loader import UrlFileLoadError, load_url_to_tempfile


class BackendFileClientError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class DownloadedBackendFile:
    path: str
    file_name: str
    mime_type: str
    document_id: str | None = None


def _headers() -> dict[str, str]:
    token = settings.backend_api_token
    return {"Authorization": f"Bearer {token}"} if token else {}


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(settings.backend_api_timeout_seconds, connect=settings.backend_api_timeout_seconds)


def _format_url(template: str, *, user_id: str, file_name: str | None = None) -> str:
    encoded_file_name = quote(file_name or "", safe="")
    return template.format(user_id=quote(user_id, safe=""), file_name=encoded_file_name)


def _filename_from_cd(value: str | None) -> str | None:
    if not value:
        return None
    msg = Message()
    msg["content-disposition"] = value
    filename = msg.get_param("filename", header="content-disposition") or msg.get_param("filename*", header="content-disposition")
    if isinstance(filename, tuple):
        filename = collapse_rfc2231_value(filename)
    return Path(str(filename)).name if filename else None


def _mime(provided: str | None, content_type: str | None, file_name: str) -> str:
    candidate = provided or (content_type.split(";", 1)[0].strip().lower() if content_type else None)
    candidate = MIME_ALIASES.get(candidate or "", candidate)
    return candidate or SUPPORTED.get(Path(file_name).suffix.lower()) or "application/octet-stream"


class BackendFileClient:
    def list_user_files(self, user_id: str) -> list[BackendFileDescriptor]:
        if not settings.backend_file_list_url_template:
            raise BackendFileClientError("BACKEND_LIST_FILES_NOT_CONFIGURED", "BACKEND_FILE_LIST_URL_TEMPLATE is not configured")
        url = _format_url(settings.backend_file_list_url_template, user_id=user_id)
        try:
            with httpx.Client(timeout=_timeout()) as client:
                response = client.get(url, headers=_headers())
        except httpx.HTTPError as exc:
            raise BackendFileClientError("BACKEND_LIST_FILES_FAILED", f"Backend list-files request failed: {exc.__class__.__name__}")
        if response.status_code != 200:
            raise BackendFileClientError("BACKEND_LIST_FILES_FAILED", "Backend list-files API did not return HTTP 200")
        try:
            payload = response.json()
        except Exception:
            raise BackendFileClientError("BACKEND_LIST_FILES_INVALID_RESPONSE", "Backend list-files response was not valid JSON")
        if not isinstance(payload, list):
            raise BackendFileClientError("BACKEND_LIST_FILES_INVALID_RESPONSE", "Backend list-files response must be an array")
        max_files = settings.backend_api_max_files
        if max_files and len(payload) > max_files:
            raise BackendFileClientError("BACKEND_TOO_MANY_FILES", "Backend returned too many files")
        descriptors: list[BackendFileDescriptor] = []
        for item in payload:
            if isinstance(item, str) and item:
                descriptors.append(BackendFileDescriptor(file_name=item))
            elif isinstance(item, dict) and item.get("file_name"):
                descriptors.append(BackendFileDescriptor(**item))
            else:
                raise BackendFileClientError("BACKEND_LIST_FILES_INVALID_RESPONSE", "Backend file descriptor is invalid")
        return descriptors

    def fetch_file_to_tempfile(self, user_id: str, file_descriptor: BackendFileDescriptor) -> DownloadedBackendFile:
        if not settings.backend_file_fetch_url_template:
            raise BackendFileClientError("BACKEND_FETCH_FILE_NOT_CONFIGURED", "BACKEND_FILE_FETCH_URL_TEMPLATE is not configured")
        url = _format_url(settings.backend_file_fetch_url_template, user_id=user_id, file_name=file_descriptor.file_name)
        mode = settings.backend_api_file_response_mode
        try:
            with httpx.Client(timeout=_timeout()) as client:
                with client.stream("GET", url, headers=_headers()) as response:
                    if response.status_code != 200:
                        raise BackendFileClientError("BACKEND_FETCH_FILE_FAILED", "Backend fetch-file API did not return HTTP 200")
                    content_type = response.headers.get("content-type", "")
                    if mode in {"json_url", "json_base64"} or (mode == "auto" and content_type.split(";", 1)[0].lower() == "application/json"):
                        data = response.read()
                        if not data:
                            raise BackendFileClientError("BACKEND_FETCH_FILE_EMPTY", "Backend fetch-file response was empty")
                        return self._json_file(data, file_descriptor, mode)
                    return self._binary_file(response, file_descriptor)
        except BackendFileClientError:
            raise
        except httpx.HTTPError as exc:
            raise BackendFileClientError("BACKEND_FETCH_FILE_FAILED", f"Backend fetch-file request failed: {exc.__class__.__name__}")

    def _json_file(self, data: bytes, desc: BackendFileDescriptor, mode: str) -> DownloadedBackendFile:
        try:
            import json
            payload = json.loads(data.decode("utf-8"))
        except Exception:
            raise BackendFileClientError("BACKEND_FETCH_FILE_INVALID_RESPONSE", "Backend JSON file response was invalid")
        if not isinstance(payload, dict):
            raise BackendFileClientError("BACKEND_FETCH_FILE_INVALID_RESPONSE", "Backend JSON file response must be an object")
        file_name = Path(payload.get("file_name") or desc.file_name).name
        mime_type = payload.get("mime_type") or desc.mime_type
        if payload.get("file_url") and mode in {"auto", "json_url"}:
            try:
                downloaded = load_url_to_tempfile(payload["file_url"], file_name, mime_type)
            except UrlFileLoadError as exc:
                raise BackendFileClientError(exc.code, exc.message)
            return DownloadedBackendFile(downloaded.path, downloaded.file_name, downloaded.mime_type, desc.document_id)
        if payload.get("base64_content") and mode in {"auto", "json_base64"}:
            try:
                raw = base64.b64decode(payload["base64_content"], validate=True)
            except (binascii.Error, ValueError):
                raise BackendFileClientError("BACKEND_FETCH_FILE_BASE64_DECODE_FAILED", "Backend base64_content could not be decoded")
            if not raw:
                raise BackendFileClientError("BACKEND_FETCH_FILE_EMPTY", "Backend base64_content was empty")
            if len(raw) > settings.max_upload_mb * 1024 * 1024:
                raise BackendFileClientError("BACKEND_FETCH_FILE_TOO_LARGE", "Backend file exceeds maximum upload size")
            suffix = Path(file_name).suffix
            tmp = tempfile.NamedTemporaryFile(prefix="extract_backend_b64_", suffix=suffix, delete=False)
            with tmp:
                tmp.write(raw)
            return DownloadedBackendFile(tmp.name, file_name, _mime(mime_type, None, file_name), desc.document_id)
        raise BackendFileClientError("BACKEND_FETCH_FILE_UNSUPPORTED_CONTENT", "Backend JSON response did not contain a supported file_url or base64_content")

    def _binary_file(self, response: httpx.Response, desc: BackendFileDescriptor) -> DownloadedBackendFile:
        max_bytes = settings.max_upload_mb * 1024 * 1024
        file_name = _filename_from_cd(response.headers.get("content-disposition")) or Path(desc.file_name).name
        mime_type = _mime(desc.mime_type, response.headers.get("content-type"), file_name)
        tmp = tempfile.NamedTemporaryFile(prefix="extract_backend_", suffix=Path(file_name).suffix, delete=False)
        total = 0
        try:
            with tmp:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise BackendFileClientError("BACKEND_FETCH_FILE_TOO_LARGE", "Backend file exceeds maximum upload size")
                    tmp.write(chunk)
            if total == 0:
                raise BackendFileClientError("BACKEND_FETCH_FILE_EMPTY", "Backend fetch-file response was empty")
            return DownloadedBackendFile(tmp.name, file_name, mime_type, desc.document_id)
        except Exception:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise
