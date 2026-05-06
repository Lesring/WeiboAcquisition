import json
import re
import time
from pathlib import Path
from datetime import datetime

import requests
from requests.exceptions import ReadTimeout, ConnectTimeout, ChunkedEncodingError, RequestException

from weibo_env import env_float, env_path, env_str, env_user_agent, http_timeout_pair


def safe_name(s: str) -> str:
    s = s or ""
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    s = s.strip()
    return s[:200] if len(s) > 200 else s


def parse_date_folder(time_str: str) -> str:
    if not time_str:
        return "unknown_date"
    try:
        dt = datetime.strptime(time_str, "%a %b %d %H:%M:%S %z %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return "unknown_date"


def guess_ext_from_url(url: str, fallback: str) -> str:
    if not url:
        return fallback
    m = re.search(r"\.([a-zA-Z0-9]{2,5})(?:\?|$)", url)
    if m:
        ext = m.group(1).lower()
        if ext in {"jpg", "jpeg", "png", "webp", "gif", "mp4", "mov", "m4v"}:
            return ext
    return fallback


def log_failed(failed_path: Path, url: str, dest: Path, kind: str):
    failed_path.parent.mkdir(parents=True, exist_ok=True)
    with failed_path.open("a", encoding="utf-8") as f:
        f.write(f"{kind}\t{dest}\t{url}\n")


def download_file(
    session: requests.Session,
    url: str,
    dest: Path,
    timeout: tuple[int, int],
    retries: int,
) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_suffix(dest.suffix + ".part")
    downloaded = tmp.stat().st_size if tmp.exists() else 0
    headers = {}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"

    for i in range(retries):
        try:
            with session.get(url, stream=True, timeout=timeout, headers=headers) as r:
                if r.status_code not in (200, 206):
                    return False

                mode = "ab" if r.status_code == 206 else "wb"
                if mode == "wb" and tmp.exists():
                    tmp.unlink(missing_ok=True)

                with open(tmp, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

            if tmp.exists() and tmp.stat().st_size > 0:
                tmp.replace(dest)
                return True

        except (ReadTimeout, ConnectTimeout, TimeoutError, ChunkedEncodingError):
            time.sleep(1.0 + i)
            continue
        except RequestException:
            time.sleep(1.0 + i)
            continue
        except Exception:
            time.sleep(1.0 + i)
            continue

    return False


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or "", encoding="utf-8")


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main():
    from weibo_bootstrap import ensure_job_env

    ensure_job_env()

    uid = env_str("WEIBO_UID")
    jsonl_path = env_path("WEIBO_JSONL_PC", Path(f"weibovault_{uid}_pc.jsonl"))
    out_dir = env_path("WEIBO_DOWNLOAD_DIR", Path("media"))
    timeout = http_timeout_pair(default_read=60)
    retries = 5
    sleep_sec = env_float("WEIBO_SLEEP_SEC", 0.8)
    ua = env_user_agent()
    cookie = env_str("WEIBO_COOKIE")
    failed_path = out_dir / "_failed.txt"

    if not jsonl_path.exists():
        raise FileNotFoundError(f"找不到 {jsonl_path.resolve()}，请先 crawl-pc 或检查 WEIBO_JSONL_PC")

    session = requests.Session()
    session.headers.update({
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://weibo.com/",
        "Connection": "keep-alive",
    })
    if cookie.strip():
        session.headers["Cookie"] = cookie

    out_dir.mkdir(parents=True, exist_ok=True)

    total_posts = 0
    ok_img = fail_img = 0
    ok_vid = fail_vid = 0

    for post in read_jsonl(jsonl_path):
        total_posts += 1
        mid = str(post.get("mid") or "")
        if not mid:
            continue

        date_folder = parse_date_folder(post.get("time") or "")
        post_dir = out_dir / date_folder / safe_name(mid)
        images_dir = post_dir / "images"
        videos_dir = post_dir / "videos"

        write_text(post_dir / "post.txt", post.get("text") or "")
        (post_dir / "meta.json").write_text(
            json.dumps(
                {"mid": mid, "time": post.get("time"), "pics": post.get("pics") or [], "videos": post.get("videos") or []},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )

        pics = post.get("pics") or []
        for idx, url in enumerate(pics, start=1):
            ext = guess_ext_from_url(url, "jpg")
            dest = images_dir / f"{idx:03d}.{ext}"
            if download_file(session, url, dest, timeout, retries):
                ok_img += 1
            else:
                fail_img += 1
                log_failed(failed_path, url, dest, "img")
            time.sleep(sleep_sec)

        videos = post.get("videos") or []
        for idx, url in enumerate(videos, start=1):
            ext = guess_ext_from_url(url, "mp4")
            dest = videos_dir / f"{idx:03d}.{ext}"
            if download_file(session, url, dest, timeout, retries):
                ok_vid += 1
            else:
                fail_vid += 1
                log_failed(failed_path, url, dest, "vid")
            time.sleep(sleep_sec)

        if total_posts % 50 == 0:
            print(f"posts={total_posts} img_ok={ok_img} img_fail={fail_img} vid_ok={ok_vid} vid_fail={fail_vid}")

    print("DONE")
    print(f"posts={total_posts}")
    print(f"images: ok={ok_img} fail={fail_img}")
    print(f"videos: ok={ok_vid} fail={fail_vid}")
    print("输出目录:", out_dir.resolve())


if __name__ == "__main__":
    main()
