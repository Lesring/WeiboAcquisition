import json, re, time
from pathlib import Path
import requests

from weibo_env import env_path, env_str, env_user_agent

UID = env_str("WEIBO_UID", "5635286888")
OUT = env_path("WEIBO_JSONL_PC", Path(f"weibovault_{UID}_pc.jsonl"))

UA = env_user_agent()
COOKIE = env_str("WEIBO_COOKIE")
XSRF = env_str("WEIBO_XSRF_PC")

def strip_html(s: str) -> str:
    s = s or ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<.*?>", "", s)
    return s.replace("&nbsp;", " ").replace("&amp;", "&").strip()

def extract_pics(mblog: dict):
    """
    PC ajax/statuses/mymblog 常见结构：
    - pic_ids: ["xxxx", "yyyy", ...]
    - pic_infos: { "xxxx": {...}, "yyyy": {...} }
    每个 info 里可能有 largest/original/large 等 url
    """
    out = []

    # 1) 主路径：pic_infos + pic_ids
    pic_infos = mblog.get("pic_infos") or {}
    pic_ids = mblog.get("pic_ids") or []

    if isinstance(pic_ids, list) and isinstance(pic_infos, dict) and pic_infos:
        for pid in pic_ids:
            info = pic_infos.get(pid) or {}
            # 优先取更大图
            for key in ["largest", "original", "large", "mw2000", "bmiddle", "thumbnail"]:
                v = info.get(key) or {}
                url = v.get("url") if isinstance(v, dict) else None
                if url:
                    out.append(url)
                    break

    # 2) 兼容路径：少数情况下存在 pics 数组
    if not out:
        for p in (mblog.get("pics") or []):
            url = ((p.get("large") or {}).get("url") or
                   (p.get("original") or {}).get("url") or
                   p.get("url"))
            if url:
                out.append(url)

    # 去重保持顺序
    dedup, seen = [], set()
    for u in out:
        if u not in seen:
            seen.add(u)
            dedup.append(u)
    return dedup

def extract_videos(mblog: dict):
    videos = []
    page_info = mblog.get("page_info") or {}
    media_info = page_info.get("media_info") or {}
    urls = page_info.get("urls") or {}

    for key in ["mp4_1080p_mp4", "mp4_720p_mp4", "mp4_hd_mp4", "mp4_sd_mp4", "mp4_ld_mp4"]:
        v = media_info.get(key)
        if isinstance(v, str) and v:
            videos.append(v)
    for key in ["mp4_1080p_mp4", "mp4_720p_mp4", "mp4_hd_mp4", "mp4_sd_mp4", "mp4_ld_mp4", "mp4"]:
        v = urls.get(key)
        if isinstance(v, str) and v:
            videos.append(v)

    # 去重
    out, seen = [], set()
    for v in videos:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out

def load_seen():
    seen = set()
    if OUT.exists():
        for line in OUT.open("r", encoding="utf-8"):
            try:
                obj = json.loads(line)
                mid = str(obj.get("mid") or "")
                if mid:
                    seen.add(mid)
            except:
                pass
    return seen

def main():
    if not COOKIE.strip():
        raise SystemExit("请在 .env 中设置 WEIBO_COOKIE（见 .env.example）")
    if not XSRF.strip():
        raise SystemExit("请在 .env 中设置 WEIBO_XSRF_PC（见 .env.example）")

    seen = load_seen()

    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": f"https://weibo.com/u/{UID}",
        "Cookie": COOKIE,
        "X-XSRF-TOKEN": XSRF,
        "Connection": "keep-alive",
    })

    page = 1
    for _ in range(2000):
        url = f"https://weibo.com/ajax/statuses/mymblog?uid={UID}&page={page}&feature=0"
        r = s.get(url, timeout=20)
        ct = (r.headers.get("content-type") or "").lower()

        if r.status_code != 200 or "application/json" not in ct:
            print("HTTP", r.status_code, "ct:", ct, "url:", r.url)
            print("Body head:", r.text[:300])
            break

        data = r.json()
        lst = (data.get("data") or {}).get("list") or []
        if not lst:
            print("No list on page", page)
            break

        new_cnt = 0
        with OUT.open("a", encoding="utf-8") as f:
            for m in lst:
                mid = str(m.get("mid") or m.get("id") or "")
                if not mid or mid in seen:
                    continue
                item = {
                    "mid": mid,
                    "time": m.get("created_at"),
                    "text": strip_html(m.get("text_raw") or m.get("text") or ""),
                    "pics": extract_pics(m),
                    "videos": extract_videos(m),
                }
                seen.add(mid)
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                new_cnt += 1

        print("page", page, "new", new_cnt, "total", len(seen))
        if new_cnt == 0:
            break

        page += 1
        time.sleep(1.0)

if __name__ == "__main__":
    main()
