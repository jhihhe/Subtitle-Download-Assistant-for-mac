"""字幕下载助手独立后端 CLI。

用法：
    python download_subtitles.py --paths /path/to/movie.mkv /path/to/folder [--overwrite]

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


async def process_video(
    video: Path,
    overwrite: bool,
    sources: list[ShooterSource | ThunderSource],
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

    # Priority: shooter fingerprint > thunder CID > default source order
    source_order = {"shooter": 0, "thunder": 1}
    all_handles.sort(
        key=lambda item: (
            not item[1].candidate.metadata.get("content_hash_match"),
            source_order.get(item[0], 99),
            -item[1].candidate.score,
        )
    )

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
                # Pick the file whose name length is closest to the video stem
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
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有字幕")
    args = parser.parse_args()

    videos = collect_video_files(args.paths)
    emit("started", total=len(videos))

    sources: list[ShooterSource | ThunderSource] = [ShooterSource(), ThunderSource()]

    success_count = 0
    failed_count = 0
    skipped_count = 0

    for video in videos:
        path, status, ok, detail = await process_video(video, args.overwrite, sources)
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
