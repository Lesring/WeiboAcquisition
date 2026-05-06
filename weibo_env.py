"""从项目根目录加载 .env，供各脚本读取配置。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def env_str(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    if v is None:
        return default
    return v


def env_path(key: str, default: str | Path) -> Path:
    v = os.environ.get(key)
    if v is not None and str(v).strip():
        return Path(v).expanduser()
    if isinstance(default, Path):
        return default
    return Path(default).expanduser()


def env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    return int(v)


def env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or not str(v).strip():
        return default
    return float(v)


def env_user_agent() -> str:
    return env_str("WEIBO_UA", _DEFAULT_UA)


def http_timeout_pair(
    connect_key: str = "WEIBO_HTTP_CONNECT_TIMEOUT",
    read_key: str = "WEIBO_HTTP_READ_TIMEOUT",
    default_connect: int = 10,
    default_read: int = 60,
) -> tuple[int, int]:
    return (env_int(connect_key, default_connect), env_int(read_key, default_read))
