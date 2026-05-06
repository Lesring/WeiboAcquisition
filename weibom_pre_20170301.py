import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import requests

# ================== 配置 ==================
UID = "5635286888"
CONTAINER_ID = f"107603{UID}"
API = "https://m.weibo.cn/api/container/getIndex"

OUT = Path(f"weibovault_{UID}_m_pre20170301.jsonl")

# 抓到这个日期(含)之前就停止：2017-03-01 00:00:00 +0800
STOP_BEFORE = datetime(2014, 3, 1, 0, 0, 0).astimezone()  # 以本机时区为准，不用于比较
# 我们按微博时间字符串自带的 +0800 来解析后比较

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 你提供的 cookie（建议按 name=value; 拼成一行）
# 注意：__cf_bm 是 geetest.com 的，不要放进来；只放 weibo.cn / m.weibo.cn 域的即可
COOKIE = (
    "M_WEIBOCN_PARAMS=luicode%3D20000174%26lfid%3D231583%26launchid%3D10000360-page_H5%26oid%3D4217165634776166%26fid%3D1076035635286888%26uicode%3D10000011; "
    "XSRF-TOKEN=bef309; "
    "SUB=_2A25EfBDzDeRhGeFH6VQR8S_LzTuIHXVn8Cw7rDV6PUJbktANLWfdkW1Ne42WMp4jmnBYkOqLsthR69iXQj8QUQ-8; "
    "SCF=AvkAo2rEkoAXVkmpxbnyxhxF2WvTHTZrYVwxH1S-CmsdU3ZGtAqFDfThQZ8lLc3S67yYleTc-bSewRkv-Qz-7CE.; "
    "_T_WM=41643702471; "
    "ALF=1772088739; "
    "SSOLoginState=1769496739; "
    "WEIBOCN_FROM=1110006030; "
    "MLOGIN=1; "
    "SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WW.wZE0u6EW0W006O-QhbZU5NHD95QN1Kzceh2pS0qNWs4DqcjMi--NiK.Xi-2Ri--ciKnRi-zNS0.ESo5peKMcS7tt"
)

SLEEP_SEC = 1.0
TIMEOUT = (10, 30)   # (连接超时, 读取超时)
MAX_PAGES = 10000

# ================== 工具函数 ==================
def strip_html(s: str) -> str:
    s = s or ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<.*?>", "", s)
    return s.replace("&nbsp;", " ").replace("&amp;", "&").strip()

def parse_weibo_time(s: str) -> Optional[datetime]:
    # 示例: "Thu Mar 01 16:21:38 +0800 2018"
    if not s:
        return None
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        return None

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
                pass
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
        url = ((p.get("large") or {}).get("url")
               or (p.get("original") or {}).get("url")
               or p.get("url"))
        if url:
            pics.append(url)

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

    def dedup(seq):
        out, seen = [], set()
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return dedup(pics), dedup(videos)

def is_html(resp: requests.Response) -> bool:
    ct = (resp.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        return False
    # 有时 ct 不靠谱，再兜底看内容开头
    head = (resp.text or "").lstrip()[:20].lower()
    return head.startswith("<!doctype") or head.startswith("<html")

# ================== 主流程 ==================
def main():
    seen = load_seen(OUT)

    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": f"https://m.weibo.cn/u/{UID}",
        "Origin": "https://m.weibo.cn",
        "Connection": "keep-alive",
        "Cookie": COOKIE,
        # 很多站点会校验这个 header 名（不是必须，但有时有用）
        "X-XSRF-TOKEN": "bef309",
    })

    # 先探测一次，禁止自动跳转，避免你再次遇到 passport
    probe = session.get(
        API,
        params={"type": "uid", "value": UID, "containerid": CONTAINER_ID},
        timeout=TIMEOUT,
        allow_redirects=False,
    )
    if probe.status_code in (301, 302, 303, 307, 308):
        print("Redirected. Location:", probe.headers.get("Location"))
        print("说明当前 Cookie 登录态无效/过期/不是 m.weibo.cn 的。")
        return
    if probe.status_code != 200 or is_html(probe):
        print("Probe not JSON / not OK")
        print("status:", probe.status_code, "ct:", probe.headers.get("content-type"))
        print("url:", probe.url)
        print("body head:", (probe.text or "")[:300])
        return
    print("Probe OK:", probe.status_code, probe.headers.get("content-type"))

    since_id = ""
    for page_i in range(1, MAX_PAGES + 1):
        params = {"type": "uid", "value": UID, "containerid": CONTAINER_ID}
        if since_id:
            params["since_id"] = since_id

        r = session.get(API, params=params, timeout=TIMEOUT, allow_redirects=False)

        if r.status_code in (301, 302, 303, 307, 308):
            print("Redirected at page", page_i, "Location:", r.headers.get("Location"))
            break
        if r.status_code != 200 or is_html(r):
            print("Not JSON / HTTP!=200 at page", page_i)
            print("status:", r.status_code, "ct:", r.headers.get("content-type"))
            print("url:", r.url)
            print("body head:", (r.text or "")[:300])
            break

        data = r.json()
        if data.get("ok") != 1:
            print("ok!=1 at page", page_i, "msg:", data.get("msg") or "")
            break

        mblogs, next_since = extract_mblogs_and_since(data)
        if not mblogs:
            print("no mblogs, stop.")
            break

        new_cnt = 0
        oldest_dt: Optional[datetime] = None

        with OUT.open("a", encoding="utf-8") as f:
            for mb in mblogs:
                mid = str(mb.get("mid") or mb.get("id") or "")
                if not mid or mid in seen:
                    continue

                created_at = mb.get("created_at")
                dt = parse_weibo_time(created_at)
                if dt and (oldest_dt is None or dt < oldest_dt):
                    oldest_dt = dt

                pics, videos = extract_media(mb)

                item = {
                    "mid": mid,
                    "time": created_at,
                    "text": strip_html(mb.get("text") or ""),
                    "pics": pics,
                    "videos": videos,
                }
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

                seen.add(mid)
                new_cnt += 1

        print(
            "page", page_i,
            "new", new_cnt,
            "total", len(seen),
            "since_id", next_since,
            "oldest_on_page", oldest_dt.isoformat() if oldest_dt else None
        )

        # 停止条件：翻到 2017-03-01 之前（含更早）
        if oldest_dt is not None:
            stop_point = datetime(2017, 3, 1, 0, 0, 0, tzinfo=oldest_dt.tzinfo)
            if oldest_dt < stop_point:
                print("Reached before 2017-03-01, stop.")
                break

        if not next_since:
            break
        since_id = next_since
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main()
