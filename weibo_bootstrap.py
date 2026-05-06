"""加载 .env，解析爬取目标 UID，并补全各脚本共用的路径环境变量（可被 .env 覆盖）。"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent


def apply_default_paths(uid: str) -> None:
    root = Path(os.environ.get("WEIBO_DATA_ROOT", "data")).expanduser()
    job = root / uid
    job.mkdir(parents=True, exist_ok=True)
    (job / "media").mkdir(parents=True, exist_ok=True)
    (job / "album").mkdir(parents=True, exist_ok=True)
    (job / "collected" / "images").mkdir(parents=True, exist_ok=True)
    (job / "collected" / "videos").mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("WEIBO_UID", uid)
    os.environ.setdefault("WEIBO_JSONL_MOBILE", str(job / "timeline_mobile.jsonl"))
    os.environ.setdefault("WEIBO_JSONL_PC", str(job / "timeline_pc.jsonl"))
    os.environ.setdefault("WEIBO_JSONL_M_PRE", str(job / "timeline_m_pre20170301.jsonl"))
    os.environ.setdefault("WEIBO_DOWNLOAD_DIR", str(job / "media"))
    os.environ.setdefault("WEIBO_ALBUM_OUT_DIR", str(job / "album"))
    os.environ.setdefault("WEIBO_COLLECT_SRC", str(job / "media"))
    os.environ.setdefault("WEIBO_COLLECT_DST_IMAGES", str(job / "collected" / "images"))
    os.environ.setdefault("WEIBO_COLLECT_DST_VIDEOS", str(job / "collected" / "videos"))


def ensure_job_env(allow_missing_target: bool = False) -> str | None:
    """
    读取项目下 .env，根据 WEIBO_TARGET 或 WEIBO_UID 写入 WEIBO_UID，并 setdefault 各路径。
    allow_missing_target=True 时若两者皆空则返回 None（仅供特殊脚本使用）。
    """
    load_dotenv(_ROOT / ".env")
    from weibo_target import parse_target_to_uid

    t = os.environ.get("WEIBO_TARGET", "").strip()
    u = os.environ.get("WEIBO_UID", "").strip()
    if t:
        uid = parse_target_to_uid(t)
    elif u:
        uid = parse_target_to_uid(u)
    else:
        if allow_missing_target:
            return None
        raise SystemExit(
            "请指定爬取目标：\n"
            "  • 在 .env 中设置 WEIBO_TARGET=https://weibo.com/u/<数字UID>（或纯数字）\n"
            "  • 或运行：python run_weibo.py -t <URL或UID> <子命令>\n"
            "（WEIBO_TARGET 与 URL 等价，都会经 parse_target_to_uid 得到 WEIBO_UID。）\n"
        )

    os.environ["WEIBO_UID"] = uid
    apply_default_paths(uid)
    return uid
