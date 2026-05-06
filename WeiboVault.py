import json
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import requests

UID = "5635286888"
CONTAINER_ID = f"107603{UID}"
BASE = (
    "https://m.weibo.cn/api/container/getIndex"
    f"?type=uid&value={UID}&containerid={CONTAINER_ID}"
)

OUT = Path(f"weibovault_{UID}.jsonl")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def strip_html(s: str) -> str:
    s = s or ""
    # 去掉 HTML 标签
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<.*?>", "", s)
    # 还原常见转义
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
    # 图片
    pics = []
    for p in (mblog.get("pics") or []):
        url = (
            (p.get("large") or {}).get("url")
            or (p.get("original") or {}).get("url")
            or p.get("url")
        )
        if url:
            pics.append(url)

    # 视频（字段会变化，尽量兼容）
    videos = []

    # 常见：page_info.media_info / page_info.urls
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

    # 去重保持顺序
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
        "time": created_at,   # 微博原始时间字符串
        "text": text,         # 去 HTML 的文案
        "pics": pics,         # 图片 URL 列表
        "videos": videos,     # 视频 URL 列表（可能为空）
    }

def main():
    seen = load_seen(OUT)
    headers = {"User-Agent": UA, "Referer": "https://m.weibo.cn/"}

    since_id = ""
    max_pages = 2000  # 防止无限循环，自行调整

    for _ in range(max_pages):
        url = BASE if not since_id else f"{BASE}&since_id={since_id}"
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
        with OUT.open("a", encoding="utf-8") as f:
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
            # next_since 为空：可能到底；new_cnt==0：可能重复/被限制
            break

        since_id = next_since
        time.sleep(0.8)  # 限速，降低风控概率

if __name__ == "__main__":
    main()
