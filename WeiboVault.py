import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from weibo_env import env_path, env_str, env_user_agent


def strip_html(s: str) -> str:
    s = s or ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<.*?>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    return s.strip()


def load_seen(path: Path) -> set:
    seen = set()
    if not path.exists():
        return seen
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                mid = str(obj.get("mid") or "")
                if mid:
                    seen.add(mid)
            except Exception:
                continue
    return seen


def extract_mblogs_and_since(data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
    d = data.get("data") or {}
    cards = d.get("cards") or []
    mblogs: List[Dict[str, Any]] = []

    for c in cards:
        mb = c.get("mblog")
        if mb:
            mblogs.append(mb)
            continue
        for cg in (c.get("card_group") or []):
            if cg.get("mblog"):
                mblogs.append(cg["mblog"])

    since_id = str((d.get("cardlistInfo") or {}).get("since_id") or "")
    return mblogs, since_id


def extract_media(mblog: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    pics = []
    for p in (mblog.get("pics") or []):
        url = (
            (p.get("large") or {}).get("url")
            or (p.get("original") or {}).get("url")
            or p.get("url")
        )
        if url:
            pics.append(url)

    videos = []
    page_info = mblog.get("page_info") or {}
    media_info = page_info.get("media_info") or {}
    urls = page_info.get("urls") or {}

    for key in ["mp4_1080p_mp4", "mp4_720p_mp4", "mp4_hd_mp4", "mp4_sd_mp4", "mp4_ld_mp4"]:
        v = media_info.get(key)
        if v and isinstance(v, str):
            videos.append(v)

    for key in ["mp4_1080p_mp4", "mp4_720p_mp4", "mp4_hd_mp4", "mp4_sd_mp4", "mp4_ld_mp4", "mp4"]:
        v = urls.get(key)
        if v and isinstance(v, str):
            videos.append(v)

    dedup = []
    seen = set()
    for v in videos:
        if v not in seen:
            seen.add(v)
            dedup.append(v)

    return pics, dedup


def to_min_item(mblog: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mid = str(mblog.get("mid") or mblog.get("id") or "")
    if not mid:
        return None

    created_at = mblog.get("created_at")
    text = strip_html(mblog.get("text") or "")
    pics, videos = extract_media(mblog)

    return {
        "mid": mid,
        "time": created_at,
        "text": text,
        "pics": pics,
        "videos": videos,
    }


def main():
    from weibo_bootstrap import ensure_job_env

    ensure_job_env()

    uid = env_str("WEIBO_UID")
    out = env_path("WEIBO_JSONL_MOBILE", Path(f"weibovault_{uid}.jsonl"))
    container_id = f"107603{uid}"
    base = (
        "https://m.weibo.cn/api/container/getIndex"
        f"?type=uid&value={uid}&containerid={container_id}"
    )
    ua = env_user_agent()
    seen = load_seen(out)
    headers = {"User-Agent": ua, "Referer": "https://m.weibo.cn/"}

    since_id = ""
    max_pages = 2000

    for _ in range(max_pages):
        url = base if not since_id else f"{base}&since_id={since_id}"
        r = requests.get(url, headers=headers, timeout=20)
        data = r.json()

        if data.get("ok") != 1:
            print("Stopped: ok!=1", data.get("msg") or "")
            break

        mblogs, next_since = extract_mblogs_and_since(data)
        if not mblogs:
            print("Stopped: no mblogs")
            break

        new_cnt = 0
        with out.open("a", encoding="utf-8") as f:
            for mb in mblogs:
                item = to_min_item(mb)
                if not item:
                    continue
                if item["mid"] in seen:
                    continue
                seen.add(item["mid"])
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                new_cnt += 1

        print(f"new={new_cnt} total={len(seen)} since_id={next_since}")

        if not next_since or new_cnt == 0:
            break

        since_id = next_since
        time.sleep(0.8)

    print("写入:", out.resolve())


if __name__ == "__main__":
    main()
