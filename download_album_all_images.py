import json
import re
import time
import time
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.exceptions import ReadTimeout, ConnectTimeout, ChunkedEncodingError, RequestException

# ====== 配置 ======
CONTAINER_ID = "1078035635286888_38555701961531260000005635286888_-_albumeach"
OUT_DIR = Path(r"D:\weibo_album_images")  # 改成你想要的目录
START_PAGE = 1
MAX_PAGES = 5000
COUNT = 24

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 用你 m.weibo.cn 能看相册的那套 Cookie（SUB/SUBP/SSOLoginState/ALF/SCF/_T_WM 等）
COOKIE = r"""SUB=_2A25EfBDzDeRhGeFH6VQR8S_LzTuIHXVn8Cw7rDV6PUJbktANLWfdkW1Ne42WMp4jmnBYkOqLsthR69iXQj8QUQ-8; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WW.wZE0u6EW0W006O-QhbZU5NHD95QN1Kzceh2pS0qNWs4DqcjMi--NiK.Xi-2Ri--ciKnRi-zNS0.ESo5peKMcS7tt; SSOLoginState=1769496739; ALF=1772088739; SCF=AvkAo2rEkoAXVkmpxbnyxhxF2WvTHTZrYVwxH1S-CmsdU3ZGtAqFDfThQZ8lLc3S67yYleTc-bSewRkv-Qz-7CE; _T_WM=41643702471; MLOGIN=1; WEIBOCN_FROM=1110006030"""

SLEEP_SEC = 0.8
TIMEOUT = (10, 30)
RETRIES = 5

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
        # 结构化字段：largest/original/large/url
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


def download_file(session: requests.Session, url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True

    tmp = dest.with_suffix(dest.suffix + ".part")
    downloaded = tmp.stat().st_size if tmp.exists() else 0
    headers = {}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"

    for i in range(RETRIES):
        try:
            with session.get(url, stream=True, timeout=TIMEOUT, headers=headers) as r:
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


def fetch_page(session: requests.Session, page: int) -> dict:
    r = session.get(
        API,
        params={"containerid": CONTAINER_ID, "page": page, "count": COUNT},
        timeout=TIMEOUT,
        allow_redirects=False,
    )
    if r.status_code in (301, 302, 303, 307, 308):
        raise RuntimeError(f"redirected: {r.headers.get('Location')}")
    if r.status_code != 200 or is_html(r):
        raise RuntimeError(f"not json: status={r.status_code} ct={r.headers.get('content-type')}")
    return r.json()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://m.weibo.cn/",
        "Origin": "https://m.weibo.cn",
        "Connection": "keep-alive",
        "Cookie": COOKIE,
    })

    all_urls = set()

    # 拉取所有页
    for page in range(START_PAGE, MAX_PAGES + 1):
        data = fetch_page(session, page)
        ok = data.get("ok")
        if ok != 1:
            print("page", page, "ok!=1:", data.get("msg") or "")
            break

        before = len(all_urls)
        collect_image_urls(data, all_urls)
        new = len(all_urls) - before
        print("page", page, "new_urls", new, "total", len(all_urls))

        if new == 0 and page > START_PAGE:
            break

        time.sleep(SLEEP_SEC)

    # 下载（按序号命名，不重复：文件存在直接跳过）
    urls = sorted(all_urls)
    dl = skip = fail = 0

    for i, url in enumerate(urls, start=1):
        url = normalize_url(url)
        ext = guess_ext(url)
        if ext not in IMG_EXT_ALLOW:
            ext = ".jpg"
        dest = OUT_DIR / f"{i:06d}{ext}"

        if dest.exists() and dest.stat().st_size > 0:
            skip += 1
            continue

        if download_file(session, url, dest):
            dl += 1
        else:
            fail += 1

        if i % 50 == 0:
            print("progress", f"{i}/{len(urls)}", "dl", dl, "skip", skip, "fail", fail)

        time.sleep(0.2)

    print("DONE", "total_urls", len(urls), "downloaded", dl, "skipped", skip, "failed", fail)
    print("OUT_DIR:", str(OUT_DIR))


if __name__ == "__main__":
    main()
