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
| `weibo_env.py` | 加载项目根目录 `.env`，被各脚本引用 |

配置项见 **`.env`**（从 `.env.example` 复制：`copy .env.example .env`）。敏感信息只放在 `.env`，该文件已被 Git 忽略。

## 配置（.env）

1. 复制示例：`copy .env.example .env`（Linux/macOS：`cp .env.example .env`）
2. 在 `.env` 中填写 `WEIBO_COOKIE`、`WEIBO_XSRF_PC`（及按需的 `WEIBO_XSRF_M`）、路径等。
3. Cookie 若包含 `#` 等字符，建议用双引号包裹整段值，例如：`WEIBO_COOKIE="SUB=...; ..."`

主要变量说明见 `.env.example` 内注释。

## 使用提示

1. **登录与 Cookie**：多数接口需要浏览器登录后的 Cookie（如 `SUB`、`SUBP` 等），写入 `.env` 的 `WEIBO_COOKIE`。`weibopc.py` 另需 `WEIBO_XSRF_PC`；`weibom_pre_20170301.py` 可设 `WEIBO_XSRF_M`，不填则回退为 `WEIBO_XSRF_PC`。
2. **频率**：可通过 `WEIBO_SLEEP_SEC` 调节间隔；也可用各脚本原有默认。
3. **输出**：`WEIBO_DOWNLOAD_DIR`、`WEIBO_JSONL_PC` 等在 `.env` 中配置；路径支持 `D:\path` 或 `D:/path`。

## 安全与仓库规范

- **不要**把 `.env` 推到远程仓库（已列入 `.gitignore`）。仅提交 `.env.example` 作为模板。
- **`WEIBO_COOKIE` / XSRF** 只放在本机 `.env`，公开仓库中勿填写真实值。
- 默认 **`.gitignore` 忽略 `*.jsonl`**，避免误提交大批量个人数据；若需要纳入版本控制，可使用 `git add -f 某文件.jsonl`。

## 许可证

脚本为个人工具性质，使用与分发责任由使用者自行承担。
