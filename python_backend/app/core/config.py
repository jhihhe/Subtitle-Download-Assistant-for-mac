"""MoviePilot app.core.config 的最小独立存根。"""

from __future__ import annotations


class _Settings:
    """提供 MoviePilot 宿主配置中本子项目实际使用的字段。"""

    # 视频扩展名集合
    RMT_MEDIAEXT = [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".m4v", ".ts", ".strm"]
    # 字幕扩展名集合
    RMT_SUBEXT = [".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt"]
    # 代理设置，可在环境变量 SUBTITLE_PROXY 中覆盖，例如 http://127.0.0.1:7890
    PROXY: dict[str, str] | None = None

    def __init__(self) -> None:
        import os

        proxy = os.environ.get("SUBTITLE_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if proxy:
            self.PROXY = {"http": proxy, "https": proxy}


settings = _Settings()
global_vars = type("global_vars", (), {"loop": None})()
