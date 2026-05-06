# Weibo 备份与下载工具

一组用于从微博 **m.weibo.cn / weibo.com** 拉取时间线、导出为 **JSON Lines（`.jsonl`）**，并按需下载图片/视频的 Python 脚本。适用于个人备份与学习，请遵守微博服务条款与当地法律法规。

## 环境要求

- Python 3.10+（建议 3.11）
- 依赖见 `requirements.txt`

## 安装

```bash
cd d:\Projects\python\weibo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 脚本说明

| 文件 | 作用 |
|------|------|
| `WeiboVault.py` | 移动端时间线抓取，写入 `weibovault_{uid}.jsonl` |
| `weibom_pre_20170301.py` | 按截止时间抓取较早微博（m 站），输出带 `_m_pre20170301` 后缀的 jsonl |
| `weibopc.py` | PC 端接口抓取个人微博列表，输出 `weibovault_{uid}_pc.jsonl` |
| `downloadweibopc.py` | 根据 PC 端 jsonl 下载媒体，按日期分子目录 |
| `download_weibovault_incremental.py` | 根据 jsonl 增量下载资源（可配置 Cookie） |
| `download_album_all_images.py` | 相册 API 分页下载相册内全部图片 |
| `collect_media_by_date.py` | 将已下载目录中的图片/视频按类型汇总到两个目标文件夹 |

各脚本顶部均有 **路径、UID、Cookie、输出目录** 等常量，运行前请按需修改。

## 使用提示

1. **登录与 Cookie**：多数接口需要浏览器登录后的 Cookie（如 `SUB`、`SUBP` 等）。从开发者工具复制后填入对应脚本的 `COOKIE`（及 `weibopc.py` 中的 `XSRF`）。
2. **频率**：脚本中已设置 `SLEEP_SEC`、重试等以降低请求压力，请勿改得过激以免触发风控。
3. **输出**：下载目录、jsonl 文件名在脚本里配置；Windows 路径可用 `r"D:\path"` 或 `Path("D:/path")`。

## 安全与仓库规范

- **不要**把真实 Cookie 或 token 推到**公开**远程仓库。推送前请清空或改写脚本中的 `COOKIE` / `XSRF`，或使用环境变量（可自行封装）。
- 默认 **`.gitignore` 忽略 `*.jsonl`**，避免误提交大批量个人数据；若需要纳入版本控制，可使用 `git add -f 某文件.jsonl`。

## 许可证

脚本为个人工具性质，使用与分发责任由使用者自行承担。
