"""从个人主页 URL 或纯数字解析微博 UID。"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


def parse_target_to_uid(target: str) -> str:
    t = (target or "").strip()
    if not t:
        raise ValueError("爬取目标为空")
    if re.fullmatch(r"\d{5,}", t):
        return t
    if not re.match(r"^https?://", t, re.I):
        t = "https://" + t
    parsed = urlparse(t)
    path = parsed.path or ""

    m = re.search(r"/u/(\d+)", path, re.I)
    if m:
        return m.group(1)

    m = re.search(r"/profile/(\d+)", path, re.I)
    if m:
        return m.group(1)

    qs = parse_qs(parsed.query)
    uid_vals = qs.get("uid") or []
    if uid_vals and re.fullmatch(r"\d+", uid_vals[0]):
        return uid_vals[0]

    raise ValueError(
        "无法从该地址解析数字 UID。请使用个人主页链接（含 /u/1234567890），"
        "例如 https://weibo.com/u/1234567890 或 https://m.weibo.cn/u/1234567890；"
        "或直接填写纯数字 UID。"
        f" 当前输入: {target!r}"
    )
