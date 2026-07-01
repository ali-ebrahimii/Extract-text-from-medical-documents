from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from email.utils import collapse_rfc2231_value
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
import ipaddress
import mimetypes
import os
import socket
import tempfile

import httpx

from app.core.config import settings
from app.services.file_validation_service import MIME_ALIASES, SUPPORTED


class UrlFileLoadError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class DownloadedUrlFile:
    path: str
    file_name: str
    mime_type: str


def _allowed_hosts() -> list[str]:
    raw = settings.file_url_allowed_hosts or ""
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def _host_matches(host: str, allowed: str) -> bool:
    host = host.lower().rstrip(".")
    allowed = allowed.lower().rstrip(".")
    if allowed.startswith("*."):
        suffix = allowed[1:]
        return host.endswith(suffix) and host != allowed[2:]
    return host == allowed or host.endswith(f".{allowed}")


def _is_private_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or value == "169.254.169.254"
    )


def _validate_url(raw_url: str) -> tuple[str, str]:
    if not raw_url:
        raise UrlFileLoadError("INVALID_FILE_URL", "file_url is required")
    try:
        parsed = urlparse(raw_url)
    except Exception:
        raise UrlFileLoadError("INVALID_FILE_URL", "file_url is invalid")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UrlFileLoadError("URL_SCHEME_NOT_ALLOWED", "Only http and https file_url schemes are allowed")

    host = parsed.hostname.lower()
    allowed = _allowed_hosts()
    if not settings.file_url_allow_private_hosts and _is_private_ip(host):
        raise UrlFileLoadError("URL_PRIVATE_HOST_BLOCKED", "Private or local file_url hosts are blocked")
    if allowed and not any(_host_matches(host, item) for item in allowed):
        raise UrlFileLoadError("URL_HOST_NOT_ALLOWED", "file_url host is not allowed")
    if not allowed and parsed.scheme != "https":
        raise UrlFileLoadError("URL_SCHEME_NOT_ALLOWED", "Only public https file_url values are allowed by default")
    if not allowed and "." not in host and not _is_private_ip(host):
        raise UrlFileLoadError("URL_HOST_NOT_ALLOWED", "Internal hostnames are not allowed")

    if not settings.file_url_allow_private_hosts:
        addresses: set[str] = set()
        try:
            for family, _type, _proto, _canon, sockaddr in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80)):
                if family in (socket.AF_INET, socket.AF_INET6):
                    addresses.add(sockaddr[0])
        except socket.gaierror:
            raise UrlFileLoadError("URL_HOST_NOT_ALLOWED", "file_url host could not be resolved")
        if any(_is_private_ip(addr) for addr in addresses):
            raise UrlFileLoadError("URL_PRIVATE_HOST_BLOCKED", "Private or local file_url hosts are blocked")
    return raw_url, host


def _filename_from_content_disposition(value: str | None) -> str | None:
    if not value:
        return None
    msg = Message()
    msg["content-disposition"] = value
    filename = msg.get_param("filename", header="content-disposition") or msg.get_param("filename*", header="content-disposition")
    if isinstance(filename, tuple):
        filename = collapse_rfc2231_value(filename)
    return Path(str(filename)).name if filename else None


def _derive_file_name(provided: str | None, content_disposition: str | None, url: str) -> str:
    if provided:
        return Path(provided).name
    from_cd = _filename_from_content_disposition(content_disposition)
    if from_cd:
        return from_cd
    basename = Path(unquote(urlparse(url).path)).name
    return basename or "downloaded_file"


def _derive_mime_type(provided: str | None, content_type: str | None, file_name: str) -> str:
    candidate = provided or (content_type.split(";", 1)[0].strip().lower() if content_type else None)
    candidate = MIME_ALIASES.get(candidate or "", candidate)
    if candidate:
        return candidate
    ext = Path(file_name).suffix.lower()
    return SUPPORTED.get(ext) or mimetypes.guess_type(file_name)[0] or "application/octet-stream"


def load_url_to_tempfile(file_url: str, file_name: str | None = None, mime_type: str | None = None) -> DownloadedUrlFile:
    url, _host = _validate_url(file_url)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    timeout = httpx.Timeout(settings.file_url_timeout_seconds, connect=settings.file_url_timeout_seconds)
    tmp = tempfile.NamedTemporaryFile(prefix="extract_url_", delete=False)
    total = 0
    final_name = "downloaded_file"
    final_mime = "application/octet-stream"
    try:
        with tmp:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                redirects = 0
                while True:
                    try:
                        with client.stream("GET", url) as response:
                            if response.status_code in {301, 302, 303, 307, 308}:
                                redirects += 1
                                if redirects > settings.file_url_max_redirects:
                                    raise UrlFileLoadError("URL_DOWNLOAD_FAILED", "file_url exceeded maximum redirects")
                                location = response.headers.get("location")
                                if not location:
                                    raise UrlFileLoadError("URL_DOWNLOAD_FAILED", "file_url redirect missing Location header")
                                url, _host = _validate_url(urljoin(url, location))
                                continue
                            if response.status_code != 200:
                                raise UrlFileLoadError("URL_DOWNLOAD_FAILED", "file_url download did not return HTTP 200")
                            final_name = _derive_file_name(file_name, response.headers.get("content-disposition"), url)
                            final_mime = _derive_mime_type(mime_type, response.headers.get("content-type"), final_name)
                            if final_mime not in set(SUPPORTED.values()) | {"application/octet-stream"}:
                                raise UrlFileLoadError("URL_CONTENT_TYPE_UNSUPPORTED", "file_url content type is not supported")
                            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                                if not chunk:
                                    continue
                                total += len(chunk)
                                if total > max_bytes:
                                    raise UrlFileLoadError("URL_FILE_TOO_LARGE", "file_url download exceeds maximum upload size")
                                tmp.write(chunk)
                            break
                    except httpx.TimeoutException:
                        raise UrlFileLoadError("URL_DOWNLOAD_TIMEOUT", "file_url download timed out")
                    except httpx.HTTPError as exc:
                        raise UrlFileLoadError("URL_DOWNLOAD_FAILED", f"file_url download failed: {exc.__class__.__name__}")
        if total == 0:
            raise UrlFileLoadError("URL_EMPTY_FILE", "file_url download was empty")
        return DownloadedUrlFile(tmp.name, final_name, final_mime)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise
