#!/usr/bin/env python3
"""
微博备份统一入口：指定主页 URL 或 UID 与数据目录后，执行抓取/下载等子命令。

示例：
  python run_weibo.py -t https://weibo.com/u/1234567890 crawl-pc
  python run_weibo.py -t 1234567890 pipeline-pc
  python run_weibo.py --data-root D:/weibo_export -t https://m.weibo.cn/u/123 crawl-mobile
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _run(command: str) -> None:
    if command == "crawl-mobile":
        import WeiboVault

        WeiboVault.main()
    elif command == "crawl-pc":
        import weibopc

        weibopc.main()
    elif command == "crawl-m-pre":
        import weibom_pre_20170301

        weibom_pre_20170301.main()
    elif command == "download-pc":
        import downloadweibopc

        downloadweibopc.main()
    elif command == "download-m-pre":
        import download_weibovault_incremental

        download_weibovault_incremental.main()
    elif command == "album":
        import download_album_all_images

        download_album_all_images.main()
    elif command == "collect":
        import collect_media_by_date

        collect_media_by_date.main()
    elif command == "pipeline-pc":
        import weibopc
        import downloadweibopc

        weibopc.main()
        downloadweibopc.main()
    elif command == "pipeline-m-pre":
        import weibom_pre_20170301
        import download_weibovault_incremental

        weibom_pre_20170301.main()
        download_weibovault_incremental.main()
    else:
        raise SystemExit(f"未知子命令: {command}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="指定微博用户（主页 URL 或 UID），将数据写入 WEIBO_DATA_ROOT/<UID>/（默认 ./data/<UID>/）",
    )
    p.add_argument(
        "-t",
        "--target",
        default=None,
        help="用户主页 URL（含 /u/<数字UID>）或纯数字 UID；也可只在 .env 设置 WEIBO_TARGET / WEIBO_UID",
    )
    p.add_argument(
        "--data-root",
        dest="data_root",
        default=None,
        help="导出根目录（默认 .env 的 WEIBO_DATA_ROOT 或 ./data）",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("crawl-mobile", help="m 站当前时间线 → timeline_mobile.jsonl")
    sub.add_parser("crawl-pc", help="PC 时间线 → timeline_pc.jsonl（需 Cookie + XSRF）")
    sub.add_parser("crawl-m-pre", help="m 站向前翻至 WEIBO_STOP_BEFORE → timeline_m_pre20170301.jsonl")
    sub.add_parser("download-pc", help="按 PC jsonl 下载到 media/")
    sub.add_parser("download-m-pre", help="按 m_pre jsonl 增量下载到 media/")
    p_album = sub.add_parser("album", help="相册分页下载到 album/（需 container id）")
    p_album.add_argument(
        "--container-id",
        dest="album_container_id",
        default=None,
        help="相册接口 containerid，覆盖 .env 的 WEIBO_ALBUM_CONTAINER_ID",
    )
    sub.add_parser("collect", help="汇总 media/ 下内容到 collected/images|videos/")
    sub.add_parser("pipeline-pc", help="crawl-pc 完成后 download-pc")
    sub.add_parser("pipeline-m-pre", help="crawl-m-pre 完成后 download-m-pre")

    return p


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    if args.data_root:
        os.environ["WEIBO_DATA_ROOT"] = str(Path(args.data_root).expanduser())
    elif not os.environ.get("WEIBO_DATA_ROOT"):
        os.environ["WEIBO_DATA_ROOT"] = str(ROOT / "data")

    if args.target:
        os.environ["WEIBO_TARGET"] = args.target.strip()

    ac = getattr(args, "album_container_id", None)
    if ac:
        os.environ["WEIBO_ALBUM_CONTAINER_ID"] = ac.strip()

    from weibo_bootstrap import ensure_job_env

    if args.command == "album":
        uid = ensure_job_env(allow_missing_target=True)
        if uid is None:
            root = Path(os.environ["WEIBO_DATA_ROOT"]).expanduser()
            os.environ.setdefault("WEIBO_ALBUM_OUT_DIR", str(root / "album"))
            Path(os.environ["WEIBO_ALBUM_OUT_DIR"]).mkdir(parents=True, exist_ok=True)
        if not os.environ.get("WEIBO_ALBUM_CONTAINER_ID", "").strip():
            raise SystemExit(
                "album 子命令需要相册 containerid：在 .env 设置 WEIBO_ALBUM_CONTAINER_ID "
                "或使用 python run_weibo.py ... album --container-id <id>"
            )
    else:
        if not (
            os.environ.get("WEIBO_TARGET", "").strip()
            or os.environ.get("WEIBO_UID", "").strip()
        ):
            raise SystemExit(
                "该子命令需要用户身份：请传 -t/--target，或在 .env 中设置 WEIBO_TARGET / WEIBO_UID"
            )
        ensure_job_env()

    _run(args.command)


if __name__ == "__main__":
    main()
