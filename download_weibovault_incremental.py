import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Iterable

import requests
from requests.exceptions import ReadTimeout, ConnectTimeout, ChunkedEncodingError, RequestException

from weibo_env import env_float, env_path, env_str, env_user_agent, http_timeout_pair

_UID = env_str("WEIBO_UID", "5635286888")

# ====== 配置（.env）======
JSONL_PATH = env_path("WEIBO_JSONL_M_PRE", Path(f"weibovault_{_UID}_m_pre20170301.jsonl"))
OUT_DIR = env_path("WEIBO_DOWNLOAD_DIR", Path(r"D:\lww"))

UA = env_user_agent()
COOKIE = env_str("WEIBO_COOKIE")

SLEEP_SEC = env_float("WEIBO_SLEEP_SEC", 0.6)
TIMEOUT = http_timeout_pair(default_read=60)
RETRIES = 5

FAILED_LOG = OUT_DIR / "_failed.txt"

# ====== 工具函数 ======
def safe_name(s: str) -> str:
    s = s or ""
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    s = s.strip()
    return s[:200] if len(s) > 200 else s

def parse_date_folder(time_str: str) -> str:
    # "Thu Mar 01 16:21:38 +0800 2018" -> "2018-03-01"
    if not time_str:
        return "unknown_date"
    try:
        dt = datetime.strptime(time_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return "unknown_date"

def guess_ext(url: str, fallback: str) -> str:
    if not url:
        return fallback
    m = re.search(r"\.([a-zA-Z0-9]{2,5})(?:\?|$)", url)
    if m:
        ext = m.group(1).lower()
        if ext in {"jpg", "jpeg", "png", "webp", "gif", "mp4", "mov", "m4v"}:
            return ext
    return fallback

def log_failed(kind: str, mid: str, url: str, dest: Path, reason: str):
    FAILED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FAILED_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{kind}\t{mid}\t{dest}\t{url}\t{reason}\n")

def read_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def download_file(session: requests.Session, url: str, dest: Path) -> tuple[bool, str]:
    """
    断点续传 + 不重复：
    - dest 已存在且 >0，直接返回成功
    - 否则写到 dest.part，成功后替换
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size > 0:
        return True, "exists"

    tmp = dest.with_suffix(dest.suffix + ".part")
    downloaded = tmp.stat().st_size if tmp.exists() else 0

    headers = {}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"

    for i in range(RETRIES):
        try:
            with session.get(url, stream=True, timeout=TIMEOUT, headers=headers) as r:
                if r.status_code not in (200, 206):
                    return False, f"http_{r.status_code}"

                mode = "ab" if r.status_code == 206 else "wb"
                if mode == "wb" and tmp.exists():
                    tmp.unlink(missing_ok=True)

                with open(tmp, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

            if tmp.exists() and tmp.stat().st_size > 0:
                tmp.replace(dest)
                return True, "ok"
            return False, "empty"

        except (ReadTimeout, ConnectTimeout, TimeoutError, ChunkedEncodingError) as e:
            time.sleep(1.0 + i)
            continue
        except RequestException as e:
            time.sleep(1.0 + i)
            continue
        except Exception as e:
            time.sleep(1.0 + i)
            continue

    return False, "retry_exhausted"

def main():
    if not JSONL_PATH.exists():
        raise FileNotFoundError(JSONL_PATH)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://m.weibo.cn/",
        "Connection": "keep-alive",
    })
    if COOKIE.strip():
        s.headers["Cookie"] = COOKIE

    posts = list(read_jsonl(JSONL_PATH))

    done_posts = 0
    skip_posts = 0
    img_ok = img_fail = 0
    vid_ok = vid_fail = 0

    for idx, post in enumerate(posts, start=1):
        mid = str(post.get("mid") or "")
        if not mid:
            continue

        date_folder = parse_date_folder(post.get("time") or "")
        post_dir = OUT_DIR / date_folder / safe_name(mid)
        done_flag = post_dir / ".done"

        # 规则：如果存在 .done，直接跳过整条微博（增量下载不重复）
        if done_flag.exists():
            skip_posts += 1
            continue

        images_dir = post_dir / "images"
        videos_dir = post_dir / "videos"
        post_dir.mkdir(parents=True, exist_ok=True)

        # 保存文案与元信息（每次覆盖，保证最新）
        (post_dir / "post.txt").write_text(post.get("text") or "", encoding="utf-8")
        (post_dir / "meta.json").write_text(
            json.dumps(
                {"mid": mid, "time": post.get("time"), "pics": post.get("pics") or [], "videos": post.get("videos") or []},
                ensure_ascii=False, indent=2
            ),
            encoding="utf-8"
        )

        # 下载图片（文件存在就不重复）
        pics = post.get("pics") or []
        for j, url in enumerate(pics, start=1):
            ext = guess_ext(url, "jpg")
            dest = images_dir / f"{j:03d}.{ext}"
            ok, reason = download_file(s, url, dest)
            if ok:
                img_ok += 1
            else:
                img_fail += 1
                log_failed("img", mid, url, dest, reason)
            time.sleep(SLEEP_SEC)

        # 下载视频
        videos = post.get("videos") or []
        for j, url in enumerate(videos, start=1):
            ext = guess_ext(url, "mp4")
            dest = videos_dir / f"{j:03d}.{ext}"
            ok, reason = download_file(s, url, dest)
            if ok:
                vid_ok += 1
            else:
                vid_fail += 1
                log_failed("vid", mid, url, dest, reason)
            time.sleep(SLEEP_SEC)

        # 处理完成标记：只有当图片/视频都尝试过后才写 done
        done_flag.write_text("ok\n", encoding="utf-8")
        done_posts += 1

        if idx % 50 == 0:
            print(f"processed={idx}/{len(posts)} done={done_posts} skipped={skip_posts} img_ok={img_ok} img_fail={img_fail} vid_ok={vid_ok} vid_fail={vid_fail}")

    print("DONE")
    print(f"posts_total={len(posts)} done={done_posts} skipped={skip_posts}")
    print(f"images ok={img_ok} fail={img_fail}")
    print(f"videos ok={vid_ok} fail={vid_fail}")
    print(f"failed_log={FAILED_LOG}")

if __name__ == "__main__":
    main()
