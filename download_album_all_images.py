import re
import time
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.exceptions import ReadTimeout, ConnectTimeout, ChunkedEncodingError, RequestException

from weibo_env import env_float, env_int, env_path, env_str, env_user_agent, http_timeout_pair

API = "https://m.weibo.cn/api/container/getSecond"
IMG_EXT_ALLOW = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def is_html(resp: requests.Response) -> bool:
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        return False
    head = (resp.text or "").lstrip()[:20].lower()
    return head.startswith("<!doctype") or head.startswith("<html")


def normalize_url(u: str) -> str:
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    return u


def guess_ext(url: str) -> str:
    try:
        path = urlparse(url).path
        ext = Path(path).suffix.lower()
        return ext if ext else ".jpg"
    except Exception:
        return ".jpg"


def collect_image_urls(obj, out_set: set):
    if obj is None:
        return
    if isinstance(obj, dict):
        for key in ("largest", "original", "large", "mw2000", "bmiddle", "thumbnail"):
            v = obj.get(key)
            if isinstance(v, dict) and isinstance(v.get("url"), str):
                out_set.add(normalize_url(v["url"]))
        if isinstance(obj.get("url"), str) and ("sinaimg" in obj["url"]):
            out_set.add(normalize_url(obj["url"]))

        for v in obj.values():
            if isinstance(v, (dict, list)):
                collect_image_urls(v, out_set)
            elif isinstance(v, str):
                s = v.strip()
                if "sinaimg" in s and (".jpg" in s or ".png" in s or ".webp" in s or ".gif" in s):
                    out_set.add(normalize_url(s))

    elif isinstance(obj, list):
        for it in obj:
            collect_image_urls(it, out_set)


def download_file(
    session: requests.Session,
    url: str,
    dest: Path,
    timeout: tuple[int, int],
    retries: int,
) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True

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
            return False
        except (ReadTimeout, ConnectTimeout, TimeoutError, ChunkedEncodingError, RequestException):
            time.sleep(1.0 + i)
            continue
    return False


def fetch_page(
    session: requests.Session,
    container_id: str,
    page: int,
    count: int,
    timeout: tuple[int, int],
) -> dict:
    r = session.get(
        API,
        params={"containerid": container_id, "page": page, "count": count},
        timeout=timeout,
        allow_redirects=False,
    )
    if r.status_code in (301, 302, 303, 307, 308):
        raise RuntimeError(f"redirected: {r.headers.get('Location')}")
    if r.status_code != 200 or is_html(r):
        raise RuntimeError(f"not json: status={r.status_code} ct={r.headers.get('content-type')}")
    return r.json()


def main():
    from weibo_bootstrap import ensure_job_env

    uid_or_none = ensure_job_env(allow_missing_target=True)
    if uid_or_none is None:
        root = Path(os.environ.get("WEIBO_DATA_ROOT", "data")).expanduser()
        os.environ.setdefault("WEIBO_ALBUM_OUT_DIR", str(root / "album"))
        Path(os.environ["WEIBO_ALBUM_OUT_DIR"]).mkdir(parents=True, exist_ok=True)

    container_id = env_str("WEIBO_ALBUM_CONTAINER_ID", "").strip()
    if not container_id:
        raise SystemExit(
            "请设置 WEIBO_ALBUM_CONTAINER_ID（相册接口 containerid，需从浏览器抓包），"
            "或使用 run_weibo.py album --container-id <id>"
        )

    out_dir = env_path("WEIBO_ALBUM_OUT_DIR", Path("album"))
    start_page = env_int("WEIBO_ALBUM_START_PAGE", 1)
    max_pages = env_int("WEIBO_ALBUM_MAX_PAGES", 5000)
    count = env_int("WEIBO_ALBUM_PAGE_COUNT", 24)
    ua = env_user_agent()
    cookie = env_str("WEIBO_COOKIE")
    sleep_sec = env_float("WEIBO_SLEEP_SEC", 0.8)
    timeout = http_timeout_pair(default_read=30)
    retries = 5

    if not cookie.strip():
        raise SystemExit("请在 .env 中设置 WEIBO_COOKIE（相册接口通常需要登录态）")

    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://m.weibo.cn/",
        "Origin": "https://m.weibo.cn",
        "Connection": "keep-alive",
        "Cookie": cookie,
    })

    all_urls = set()

    for page in range(start_page, max_pages + 1):
        data = fetch_page(session, container_id, page, count, timeout)
        ok = data.get("ok")
        if ok != 1:
            print("page", page, "ok!=1:", data.get("msg") or "")
            break

        before = len(all_urls)
        collect_image_urls(data, all_urls)
        new = len(all_urls) - before
        print("page", page, "new_urls", new, "total", len(all_urls))

        if new == 0 and page > start_page:
            break

        time.sleep(sleep_sec)

    urls = sorted(all_urls)
    dl = skip = fail = 0

    for i, url in enumerate(urls, start=1):
        url = normalize_url(url)
        ext = guess_ext(url)
        if ext not in IMG_EXT_ALLOW:
            ext = ".jpg"
        dest = out_dir / f"{i:06d}{ext}"

        if dest.exists() and dest.stat().st_size > 0:
            skip += 1
            continue

        if download_file(session, url, dest, timeout, retries):
            dl += 1
        else:
            fail += 1

        if i % 50 == 0:
            print("progress", f"{i}/{len(urls)}", "dl", dl, "skip", skip, "fail", fail)

        time.sleep(0.2)

    print("DONE", "total_urls", len(urls), "downloaded", dl, "skipped", skip, "failed", fail)
    print("OUT_DIR:", str(out_dir.resolve()))


if __name__ == "__main__":
    main()
