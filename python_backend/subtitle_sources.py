"""从 MoviePilot 插件中提取的独立字幕源实现。

支持射手网（内容指纹）和迅雷影音（文件名 / CID）。
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import re
import time
import zipfile
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote, urlparse

import httpx


_SHOOTER_API = "https://www.shooter.cn/api/subapi.php"
_THUNDER_API = "https://api-shoulei-ssl.xunlei.com/oracle/subtitle"
_SHOOTER_MINIMUM_SIZE = 8 * 1024
_THUNDER_SAMPLE_SIZE = 0x5000
_THUNDER_FULL_SAMPLE_SIZE = 0xF000
_STRM_READ_LIMIT = 64 * 1024
_CONTENT_RANGE = re.compile(r"^bytes\s+(\d+)-(\d+)/(\d+|\*)$", re.IGNORECASE)

_PROXY = os.environ.get("SUBTITLE_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")


def _proxy() -> dict[str, str] | None:
    return {"http": _PROXY, "https": _PROXY} if _PROXY else None


@dataclass(frozen=True)
class MediaContext:
    title: str
    target_path: str
    target_file_name: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None


@dataclass(frozen=True)
class SubtitleCandidate:
    stable_key: str
    source: str
    name: str
    file_name: str
    format: str
    language: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateHandle:
    candidate: SubtitleCandidate
    opaque: dict[str, Any]


@dataclass(frozen=True)
class SourceSearchResult:
    source: str
    candidates: list[CandidateHandle] = field(default_factory=list)
    error_summary: str | None = None


@dataclass(frozen=True)
class DownloadedAsset:
    path: Path
    file_name: str


class SourceRequestError(RuntimeError):
    pass


class _Response:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> httpx.Headers:
        return self._response.headers

    @property
    def content(self) -> bytes:
        return self._response.content

    @property
    def text(self) -> str:
        return self._response.text

    def json(self) -> Any:
        return self._response.json()

    async def aiter_bytes(self, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        async for chunk in self._response.aiter_bytes(chunk_size):
            yield chunk

    async def aclose(self) -> None:
        await self._response.aclose()


class _AsyncRequestUtils:
    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        proxies: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> None:
        proxy = proxies.get("https") or proxies.get("http") if proxies else None
        self._client = httpx.AsyncClient(
            headers=headers or {},
            proxy=proxy,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def get_res(self, url: str, **kwargs: Any) -> _Response | None:
        try:
            return _Response(await self._client.get(url, **kwargs))
        except Exception:
            return None

    async def post_res(self, url: str, **kwargs: Any) -> _Response | None:
        try:
            return _Response(await self._client.post(url, **kwargs))
        except Exception:
            return None

    @asynccontextmanager
    async def get_stream(self, url: str) -> AsyncIterator[_Response]:
        async with self._client.stream("GET", url) as response:
            yield _Response(response)

    async def aclose(self) -> None:
        await self._client.aclose()


async def _request_with_proxy_fallback(method: str, url: str, **kwargs: Any) -> tuple[_Response | None, dict[str, Any]]:
    proxies = _proxy()
    selected = proxies if proxies else {}
    transport = "直连"
    fallback = False

    request = _AsyncRequestUtils(headers=kwargs.pop("headers", None), proxies=selected)
    response = await getattr(request, method)(url, **kwargs)
    if response is None and proxies:
        request2 = _AsyncRequestUtils(headers=kwargs.pop("headers", None), proxies={})
        response = await getattr(request2, method)(url, **kwargs)
        selected = {}
        transport = "直连"
        fallback = True
    return response, {"transport": transport, "proxy_fallback": fallback}


async def _download_file(url: str, directory: Path, file_name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / file_name
    request = _AsyncRequestUtils(headers={"User-Agent": "SubtitleDownloaderGUI/1.0"}, proxies=_proxy())
    try:
        async with request._client.stream("GET", url) as response:
            response.raise_for_status()
            with path.open("wb") as stream:
                async for chunk in response.aiter_bytes(64 * 1024):
                    stream.write(chunk)
    except Exception as exc:
        raise SourceRequestError(f"下载失败：{exc}") from exc
    finally:
        await request.aclose()
    return path


def _safe_file_name(value: Any, default: str) -> str:
    text = str(value or default)
    return re.sub(r'[\\/:*?"<>|]', "_", text)[:128]


def _subtitle_format(file_name: str | None, ext: str | None) -> str | None:
    value = (ext or "").strip().lstrip(".").upper()
    if not value and file_name:
        value = Path(file_name).suffix.lstrip(".").upper()
    return value if value in {"SRT", "ASS", "SSA", "SUB", "IDX", "VTT"} else None


@dataclass(frozen=True)
class MediaFingerprints:
    media_name: str
    media_size: int
    shooter_hash: str | None
    thunder_cid: str | None
    shooter_error: str | None = None
    thunder_error: str | None = None


class FingerprintService:
    def _shooter_hash_from_bytes(self, data: bytes, size: int) -> str | None:
        if size < _SHOOTER_MINIMUM_SIZE or len(data) != size:
            return None
        offsets = (4 * 1024, size // 3 * 2, size // 3, size - 8 * 1024)
        return ";".join(hashlib.md5(data[offset : offset + 4096]).hexdigest() for offset in offsets)

    def _thunder_cid_from_bytes(self, data: bytes, size: int) -> str:
        if size < _THUNDER_FULL_SAMPLE_SIZE:
            sample = data
        else:
            sample = b"".join(
                (
                    data[:_THUNDER_SAMPLE_SIZE],
                    data[size // 3 : size // 3 + _THUNDER_SAMPLE_SIZE],
                    data[size - _THUNDER_SAMPLE_SIZE :],
                )
            )
        return hashlib.sha1(sample).hexdigest().upper()

    def compute_local(self, path: Path, media_name: str) -> MediaFingerprints:
        size = path.stat().st_size
        if size <= 0 or not path.is_file():
            raise SourceRequestError("本地媒体文件无法读取")
        with path.open("rb") as stream:
            if size < _THUNDER_FULL_SAMPLE_SIZE:
                data = stream.read()
                shooter_hash = self._shooter_hash_from_bytes(data, size)
                thunder_cid = self._thunder_cid_from_bytes(data, size)
            else:
                start = stream.read(_THUNDER_SAMPLE_SIZE)
                stream.seek(size // 3)
                third = stream.read(_THUNDER_SAMPLE_SIZE)
                stream.seek(size // 3 * 2)
                two_thirds = stream.read(4096)
                stream.seek(size - _THUNDER_SAMPLE_SIZE)
                tail = stream.read(_THUNDER_SAMPLE_SIZE)
                if min(len(start), len(third), len(tail)) < _THUNDER_SAMPLE_SIZE or len(two_thirds) < 4096:
                    raise SourceRequestError("本地媒体文件读取不完整")
                shooter_hash = ";".join(
                    (
                        hashlib.md5(start[4096:8192]).hexdigest(),
                        hashlib.md5(two_thirds).hexdigest(),
                        hashlib.md5(third[:4096]).hexdigest(),
                        hashlib.md5(tail[-8192:-4096]).hexdigest(),
                    )
                )
                thunder_cid = hashlib.sha1(start + third + tail).hexdigest().upper()
        return MediaFingerprints(
            media_name=media_name,
            media_size=size,
            shooter_hash=shooter_hash,
            thunder_cid=thunder_cid,
            shooter_error=None if shooter_hash else "媒体文件小于 8 KiB，无法计算射手指纹",
        )

    async def get(self, context: MediaContext) -> MediaFingerprints:
        target = Path(context.target_path)
        media_name = Path(context.target_file_name).stem
        if target.suffix.casefold() == ".strm":
            raw = target.read_bytes()
            if len(raw) > _STRM_READ_LIMIT:
                raise SourceRequestError("STRM 文件内容超过 64 KiB")
            locator = next((line.strip() for line in raw.decode("utf-8-sig", errors="replace").splitlines() if line.strip()), "")
            if not locator:
                raise SourceRequestError("STRM 文件没有可用的媒体地址")
            parsed = urlparse(locator)
            if parsed.scheme.casefold() in {"http", "https"}:
                return await self._compute_remote(locator, media_name)
            local = Path(unquote(parsed.path)) if parsed.scheme.casefold() == "file" else (Path(locator) if not parsed.scheme else None)
            if local is None:
                raise SourceRequestError("STRM 媒体地址不受支持")
            target = local if local.is_absolute() else target.parent / local
        return await asyncio.to_thread(self.compute_local, target, media_name)

    async def _compute_remote(self, url: str, media_name: str) -> MediaFingerprints:
        # 简化实现：仅探测大小并读取完整小文件；大文件按 Range 读取。
        request = _AsyncRequestUtils(headers={"Range": "bytes=0-0"}, proxies=_proxy())
        try:
            response = await request.get_res(url)
            if response is None or response.status_code >= 400:
                raise SourceRequestError("远程媒体长度探测失败")
            size = None
            supports_ranges = False
            content_range = str(response.headers.get("content-range") or "").strip()
            match = _CONTENT_RANGE.match(content_range)
            if match and match.group(3) != "*":
                size = int(match.group(3))
                supports_ranges = True
            else:
                content_length = str(response.headers.get("content-length") or "").strip()
                if content_length.isdigit():
                    size = int(content_length)
                    supports_ranges = "bytes" in str(response.headers.get("accept-ranges") or "").casefold()
            await response.aclose()
            if size is None or size <= 0:
                raise SourceRequestError("远程媒体长度探测失败")
            if size < _THUNDER_FULL_SAMPLE_SIZE:
                data = await self._read_range(url, 0, size)
                return MediaFingerprints(
                    media_name=media_name,
                    media_size=size,
                    shooter_hash=self._shooter_hash_from_bytes(data, size),
                    thunder_cid=self._thunder_cid_from_bytes(data, size),
                    shooter_error=None,
                )
            if not supports_ranges:
                raise SourceRequestError("STRM 远程媒体不支持 HTTP Range")
            start = await self._read_range(url, 0, _THUNDER_SAMPLE_SIZE)
            third = await self._read_range(url, size // 3, _THUNDER_SAMPLE_SIZE)
            two_thirds = await self._read_range(url, size // 3 * 2, 4096)
            tail = await self._read_range(url, size - _THUNDER_SAMPLE_SIZE, _THUNDER_SAMPLE_SIZE)
            shooter_hash = ";".join(
                (
                    hashlib.md5(start[4096:8192]).hexdigest(),
                    hashlib.md5(two_thirds).hexdigest(),
                    hashlib.md5(third[:4096]).hexdigest(),
                    hashlib.md5(tail[-8192:-4096]).hexdigest(),
                )
            )
            thunder_cid = hashlib.sha1(start + third + tail).hexdigest().upper()
            return MediaFingerprints(
                media_name=media_name,
                media_size=size,
                shooter_hash=shooter_hash,
                thunder_cid=thunder_cid,
            )
        finally:
            await request.aclose()

    async def _read_range(self, url: str, offset: int, length: int) -> bytes:
        request = _AsyncRequestUtils(
            headers={"Range": f"bytes={offset}-{offset + length - 1}"},
            proxies=_proxy(),
        )
        try:
            response = await request.get_res(url)
            if response is None or response.status_code >= 400:
                raise SourceRequestError("远程媒体范围请求失败")
            data = await response._response.aread()
            await response.aclose()
            if len(data) != length:
                raise SourceRequestError("远程媒体返回字节数不足")
            return data
        finally:
            await request.aclose()


class ShooterSource:
    source = "shooter"

    def __init__(self) -> None:
        self._fingerprints = FingerprintService()

    def _valid_download_url(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        parsed = urlparse(value.strip())
        return value.strip() if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc else None

    async def search(self, context: MediaContext) -> SourceSearchResult:
        try:
            fingerprints = await self._fingerprints.get(context)
            if not fingerprints.shooter_hash:
                return SourceSearchResult(source=self.source, error_summary=fingerprints.shooter_error or "射手指纹不可用")
            response, _details = await _request_with_proxy_fallback(
                "post_res",
                _SHOOTER_API,
                headers={"Accept": "*/*", "User-Agent": "MoviePilot-SubtitleDownloadAssistant-Shooter"},
                data={
                    "filehash": fingerprints.shooter_hash,
                    "pathinfo": fingerprints.media_name,
                    "format": "json",
                    "lang": "chn",
                },
            )
            if response is None:
                return SourceSearchResult(source=self.source, error_summary="射手字幕接口无响应")
            if response.status_code != 200:
                await response.aclose()
                return SourceSearchResult(source=self.source, error_summary=f"射手字幕接口返回 HTTP {response.status_code}")
            try:
                payload = response.json()
            except Exception as exc:
                await response.aclose()
                return SourceSearchResult(source=self.source, error_summary=f"射手返回格式无效：{exc}")
            finally:
                await response.aclose()
            if not isinstance(payload, list):
                return SourceSearchResult(source=self.source, error_summary="射手返回格式无效")
            handles: list[CandidateHandle] = []
            for group in payload:
                if not isinstance(group, dict):
                    continue
                files = group.get("Files") or group.get("files") or []
                if not isinstance(files, list):
                    continue
                for file_info in files:
                    if not isinstance(file_info, dict):
                        continue
                    url = self._valid_download_url(file_info.get("Link") or file_info.get("link"))
                    extension = _subtitle_format(None, str(file_info.get("Ext") or file_info.get("ext") or ""))
                    if not url or not extension:
                        continue
                    digest = hashlib.sha256(f"{url}\0{extension}".encode("utf-8")).hexdigest()
                    file_name = f"shooter-{digest[:16]}.{extension.casefold()}"
                    candidate = SubtitleCandidate(
                        stable_key=f"shooter:{digest}",
                        source=self.source,
                        name=f"{Path(context.target_file_name).stem} · 射手字幕",
                        file_name=file_name,
                        format=extension,
                        language="简体中文",
                    )
                    handles.append(CandidateHandle(candidate=candidate, opaque={"url": url, "file_name": file_name}))
            return SourceSearchResult(source=self.source, candidates=handles)
        except Exception as exc:
            return SourceSearchResult(source=self.source, error_summary=f"射手搜索失败：{exc}")

    async def download(self, handle: CandidateHandle, directory: Path) -> DownloadedAsset:
        url = str(handle.opaque.get("url") or "")
        file_name = _safe_file_name(handle.opaque.get("file_name"), "shooter-subtitle.srt")
        path = await _download_file(url, directory, file_name)
        return DownloadedAsset(path=path, file_name=file_name)


class ThunderSource:
    source = "thunder"

    def __init__(self) -> None:
        self._fingerprints = FingerprintService()

    def _valid_download_url(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        parsed = urlparse(value.strip())
        return value.strip() if parsed.scheme.casefold() in {"http", "https"} and parsed.netloc else None

    def _language_text(self, value: Any) -> str:
        values = value if isinstance(value, list) else []
        decoded: list[str] = []
        for item in values:
            text = html.unescape(html.unescape(str(item or ""))).strip()
            if text and text.casefold() not in {"amp", "eng"} and text not in decoded:
                decoded.append(text)
        return "、".join(decoded)

    def _integer(self, value: Any) -> int | None:
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def _media_name(self, context: MediaContext) -> str:
        name = Path(context.target_file_name).name
        return Path(name).stem if Path(name).suffix.casefold() == ".strm" else name

    async def search(self, context: MediaContext) -> SourceSearchResult:
        try:
            cid: str | None = None
            media_name = self._media_name(context)
            try:
                fingerprints = await self._fingerprints.get(context)
                cid = fingerprints.thunder_cid
                media_name = fingerprints.media_name or media_name
            except Exception:
                pass
            response, _details = await _request_with_proxy_fallback(
                "get_res",
                _THUNDER_API,
                headers={"Accept": "*/*", "User-Agent": "MoviePilot-SubtitleDownloadAssistant-Thunder"},
                params={"name": media_name},
            )
            if response is None:
                return SourceSearchResult(source=self.source, error_summary="迅雷字幕接口无响应")
            if response.status_code != 200:
                await response.aclose()
                return SourceSearchResult(source=self.source, error_summary=f"迅雷字幕接口返回 HTTP {response.status_code}")
            try:
                payload = response.json()
            except Exception as exc:
                await response.aclose()
                return SourceSearchResult(source=self.source, error_summary=f"迅雷返回格式无效：{exc}")
            finally:
                await response.aclose()
            if not isinstance(payload, dict) or self._integer(payload.get("code")) != 0:
                return SourceSearchResult(source=self.source, error_summary="迅雷字幕接口返回错误状态")
            data = payload.get("data") or []
            if not isinstance(data, list):
                return SourceSearchResult(source=self.source, error_summary="迅雷候选列表无效")
            handles: list[CandidateHandle] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                url = self._valid_download_url(item.get("url"))
                native_name = _safe_file_name(str(item.get("name") or ""), "thunder-subtitle")
                extension = _subtitle_format(native_name, str(item.get("ext") or ""))
                if not url or not extension:
                    continue
                item_cid = str(item.get("cid") or "").strip().upper()
                hash_match = bool(cid and item_cid and cid == item_cid)
                digest = hashlib.sha256(f"{url}\0{native_name}".encode("utf-8")).hexdigest()
                language = self._language_text(item.get("languages"))
                candidate = SubtitleCandidate(
                    stable_key=f"thunder:{digest}",
                    source=self.source,
                    name=native_name,
                    file_name=native_name,
                    format=extension,
                    language=language,
                    score=float(self._integer(item.get("fingerprintf_score")) or self._integer(item.get("score")) or 0),
                    metadata={"content_hash_match": hash_match},
                )
                handles.append(CandidateHandle(candidate=candidate, opaque={"url": url, "file_name": native_name}))
            # 优先返回 CID 匹配的候选
            handles.sort(key=lambda h: (not h.candidate.metadata.get("content_hash_match"), -h.candidate.score))
            return SourceSearchResult(source=self.source, candidates=handles)
        except Exception as exc:
            return SourceSearchResult(source=self.source, error_summary=f"迅雷搜索失败：{exc}")

    async def download(self, handle: CandidateHandle, directory: Path) -> DownloadedAsset:
        url = str(handle.opaque.get("url") or "")
        file_name = _safe_file_name(handle.opaque.get("file_name"), "thunder-subtitle.srt")
        path = await _download_file(url, directory, file_name)
        return DownloadedAsset(path=path, file_name=file_name)


async def extract_archive(asset: DownloadedAsset, output: Path, allowed_formats: set[str]) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    suffix = asset.path.suffix.lower()
    files: list[Path] = []
    if suffix == ".zip":
        with zipfile.ZipFile(asset.path, "r") as archive:
            for member in archive.namelist():
                if Path(member).suffix.lstrip(".").upper() in allowed_formats:
                    archive.extract(member, output)
                    files.append(output / member)
    else:
        # 非压缩包直接视为已提取
        if asset.path.suffix.lstrip(".").upper() in allowed_formats:
            files.append(asset.path)
    return files


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".strm"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt"}


def collect_video_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            files.append(path)
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                    files.append(item)
    return files


def existing_subtitle_path(video: Path) -> Path | None:
    for ext in SUBTITLE_EXTENSIONS:
        candidate = video.with_suffix(ext)
        if candidate.exists():
            return candidate
        # 也检查 .zh.ext / .cn.ext 等多语言后缀变体
        for suffix in [".zh", ".cn", ".sc", ".chs", ".en"]:
            candidate = video.parent / f"{video.stem}{suffix}{ext}"
            if candidate.exists():
                return candidate
    return None


def guess_season_episode(file_name: str) -> tuple[int | None, int | None]:
    text = Path(file_name).stem
    match = re.search(r"[Ss](\d+)[Ee](\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"(\d+)x(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r"[Ee][Pp]?(\d+)", text)
    if match:
        return None, int(match.group(1))
    return None, None


def guess_year(file_name: str) -> int | None:
    match = re.search(r"\(?(\d{4})\)?", Path(file_name).stem)
    if match:
        year = int(match.group(1))
        if 1900 < year < 2100:
            return year
    return None
