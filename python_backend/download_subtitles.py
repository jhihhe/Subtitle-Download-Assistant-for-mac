"""字幕下载助手独立后端 CLI。

用法：
    python download_subtitles.py --paths /path/to/movie.mkv /path/to/folder \
        [--sources shooter thunder] [--manual] [--overwrite]

输出：每行一个 JSON 事件，SwiftUI 前端读取并更新界面。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

from subtitle_sources import (
    CandidateHandle,
    MediaContext,
    ShooterSource,
    ThunderSource,
    collect_video_files,
    existing_subtitle_path,
    extract_archive,
    guess_season_episode,
    guess_year,
)


def emit(event: str, **kwargs: object) -> None:
    print(json.dumps({"event": event, **kwargs}, ensure_ascii=False), flush=True)


def read_selection() -> dict[str, object] | None:
    """从标准输入读取用户选择。"""
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)
    except Exception:
        return None


def build_context(video: Path) -> MediaContext:
    season, episode = guess_season_episode(video.name)
    return MediaContext(
        title=video.stem,
        target_path=str(video),
        target_file_name=video.name,
        year=guess_year(video.name),
        season=season,
        episode=episode,
    )


def serialize_candidate(source_name: str, handle: CandidateHandle) -> dict[str, object]:
    candidate = handle.candidate
    score = int(candidate.score) if candidate.score else 0
    if candidate.metadata.get("content_hash_match"):
        score = max(score, 100)
    return {
        "source": source_name,
        "name": candidate.name,
        "file_name": candidate.file_name,
        "format": candidate.format,
        "language": candidate.language,
        "score": score,
    }


async def process_video(
    video: Path,
    overwrite: bool,
    sources: list[ShooterSource | ThunderSource],
    manual: bool,
) -> tuple[str, str, bool, str]:
    if not overwrite:
        existing = existing_subtitle_path(video)
        if existing:
            return str(video), "skipped", True, f"Subtitle already exists: {existing.name}"

    context = build_context(video)
    temp_root = Path(tempfile.gettempdir()) / "subtitle_download_gui"
    temp_root.mkdir(parents=True, exist_ok=True)

    all_handles: list[tuple[str, CandidateHandle]] = []
    source_errors: list[str] = []

    for source in sources:
        result = await source.search(context)
        if result.error_summary:
            source_errors.append(f"{source.source}: {result.error_summary}")
        for handle in result.candidates:
            all_handles.append((source.source, handle))

    if not all_handles:
        detail = "; ".join(source_errors) if source_errors else "No subtitle candidates found"
        return str(video), "failed", False, detail

    source_order = {"shooter": 0, "thunder": 1}
    all_handles.sort(
        key=lambda item: (
            not item[1].candidate.metadata.get("content_hash_match"),
            source_order.get(item[0], 99),
            -item[1].candidate.score,
        )
    )

    if manual:
        candidates = [serialize_candidate(name, handle) for name, handle in all_handles]
        emit("candidates", path=str(video), candidates=candidates)
        selection = read_selection()
        if not selection or selection.get("path") != str(video):
            return str(video), "failed", False, "No manual selection received"
        index = selection.get("index")
        if index is None or not isinstance(index, int) or index < 0 or index >= len(all_handles):
            return str(video), "failed", False, "Skipped by user"
        all_handles = [all_handles[index]]

    last_error = ""
    for source_name, handle in all_handles:
        source = next(s for s in sources if s.source == source_name)
        try:
            asset = await source.download(handle, temp_root / "downloads")
            extracted = await extract_archive(asset, temp_root / "extracted", {"SRT", "ASS", "SSA"})
            if not extracted:
                last_error = "Downloaded file cannot be parsed"
                continue
            if len(extracted) == 1:
                selected = extracted[0]
            else:
                selected = min(extracted, key=lambda p: abs(len(p.stem) - len(video.stem)))
            destination = video.with_suffix(selected.suffix)
            if destination.exists() and not overwrite:
                last_error = f"Target subtitle already exists: {destination.name}"
                continue
            shutil.copy2(selected, destination)
            return str(video), "success", True, f"Saved {destination.name} ({source_name})"
        except Exception as exc:
            last_error = f"{source_name} download failed: {exc}"
            continue

    return str(video), "failed", False, last_error or "All candidates failed"


async def main() -> int:
    parser = argparse.ArgumentParser(description="字幕下载助手独立后端")
    parser.add_argument("--paths", nargs="+", required=True, help="视频文件或文件夹路径")
    parser.add_argument("--sources", nargs="+", default=["shooter", "thunder"], help="启用的字幕源")
    parser.add_argument("--manual", action="store_true", help="手动选择字幕")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有字幕")
    args = parser.parse_args()

    videos = collect_video_files(args.paths)
    emit("started", total=len(videos))

    source_map: dict[str, type[ShooterSource] | type[ThunderSource]] = {
        "shooter": ShooterSource,
        "thunder": ThunderSource,
    }
    sources: list[ShooterSource | ThunderSource] = []
    for name in args.sources:
        cls = source_map.get(name.lower())
        if cls is not None:
            sources.append(cls())

    success_count = 0
    failed_count = 0
    skipped_count = 0

    for video in videos:
        path, status, ok, detail = await process_video(video, args.overwrite, sources, args.manual)
        success = ok if status == "success" else (None if status == "skipped" else False)
        if status == "success":
            success_count += 1
        elif status == "skipped":
            skipped_count += 1
        else:
            failed_count += 1
        emit("progress", path=path, status=status, detail=detail, success=success)

    emit("finished", success=success_count, failed=failed_count, skipped=skipped_count)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
