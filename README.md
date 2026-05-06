# 微博备份工具

从 **m.weibo.cn / weibo.com** 抓取个人微博时间线（JSON Lines）、按需下载图片/视频，并支持相册分页下载。适用于**任意用户**：只需提供**个人主页 URL（含数字 UID）或纯数字 UID**，数据会按用户隔离存放。

请遵守微博服务条款与当地法律法规，仅限个人备份与学习使用。

## 环境

- Python 3.10+
- `pip install -r requirements.txt`

```bash
cd d:\Projects\python\weibo
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# 编辑 .env：至少填写 WEIBO_TARGET 或 WEIBO_UID，按需填写 WEIBO_COOKIE、WEIBO_XSRF_PC 等
```

## 核心用法：`run_weibo.py`（推荐）

统一入口：**先指定要备份的用户**，再选子命令。用户可从 URL 解析（`/u/数字`）或直接使用数字 UID。

```text
python run_weibo.py -t <主页URL或UID> [--data-root 导出根目录] <子命令>
```

- **`-t` / `--target`**：例如 `https://weibo.com/u/1234567890`、`https://m.weibo.cn/u/1234567890` 或 `1234567890`。也可只在 `.env` 里配置 `WEIBO_TARGET` 或 `WEIBO_UID`，则命令行可省略 `-t`（`album` 子命令除外说明见下）。
- **`--data-root`**：数据根目录，默认 `./data`（或 `.env` 中 `WEIBO_DATA_ROOT`）。每个用户独占子目录：**`<data-root>/<UID>/`**.

### 子命令一览

| 子命令 | 作用 |
|--------|------|
| `crawl-mobile` | m 站当前时间线 → `timeline_mobile.jsonl` |
| `crawl-pc` | PC 接口时间线 → `timeline_pc.jsonl`（需 `WEIBO_COOKIE` + `WEIBO_XSRF_PC`） |
| `crawl-m-pre` | m 站向前翻页，直到早于 `WEIBO_STOP_BEFORE` → `timeline_m_pre20170301.jsonl` |
| `download-pc` | 根据 PC 的 jsonl 下载图文视频到 `media/` |
| `download-m-pre` | 根据 m_pre 的 jsonl **增量**下载到 `media/`（`.done` 标记） |
| `album` | 相册图片分页下载到 `album/`（需 `WEIBO_ALBUM_CONTAINER_ID` 或 `--container-id`） |
| `collect` | 将 `media/` 下按日期的目录扁平汇总到 `collected/images`、`collected/videos` |
| `pipeline-pc` | 依次：`crawl-pc` → `download-pc` |
| `pipeline-m-pre` | 依次：`crawl-m-pre` → `download-m-pre` |

### 示例

```bash
# PC 一条龙：抓时间线 + 下载媒体（需在 .env 配置 Cookie / XSRF）
python run_weibo.py -t https://weibo.com/u/1234567890 pipeline-pc

# 仅 m 站当前时间线
python run_weibo.py -t 1234567890 crawl-mobile

# 指定导出目录
python run_weibo.py --data-root D:/weibo_backup -t https://m.weibo.cn/u/123 crawl-m-pre

# 相册（containerid 需自行抓包；可与 -t 同用以把相册存进该 UID 目录）
python run_weibo.py -t 1234567890 album --container-id "107803..._-_albumeach"
```

### 每个 UID 下默认目录结构

在 `<WEIBO_DATA_ROOT>/<UID>/` 中：

- `timeline_mobile.jsonl`、`timeline_pc.jsonl`、`timeline_m_pre20170301.jsonl`
- `media/`：按 `YYYY-MM-DD/<mid>/images|videos` 存放下载结果
- `album/`：相册图片
- `collected/images`、`collected/videos`：`collect` 的输出

若在 `.env` 中单独设置了 `WEIBO_JSONL_*`、`WEIBO_DOWNLOAD_DIR` 等，**未设置的项**仍按上表自动填充；已设置的项以 `.env` 为准（`setdefault` 行为）。

### `album` 与主页 URL

相册接口的 **containerid** 不能从普通个人主页 URL 自动推导，需从浏览器开发者工具抓包得到。若**不传** `-t` / 不设 `WEIBO_TARGET`亦可运行相册：图片会写入 **`WEIBO_DATA_ROOT/album/`**（默认 `./data/album`），并仍须在 `.env` 或 `--container-id` 提供相册 id。

## 关于 `.env` 与 `downloadweibopc.py` 里的 UID

`env_str("WEIBO_UID", "5635286888")` 这类写法中，**第二个参数只是“环境变量未设置时的占位默认”**；真正从 `.env` 读取的是 **`WEIBO_TARGET` / `WEIBO_UID`**（或由 `run_weibo.py -t` 写入的 `WEIBO_TARGET`）。  
当前流程中，各脚本在 `main()` 里会先执行 `ensure_job_env()`，根据目标解析出 **`WEIBO_UID`** 并补全路径，因此请**优先在 `.env` 配置 `WEIBO_TARGET`**，或始终通过 `run_weibo.py -t ...` 指定用户。

## 单独运行各脚本（高级）

仍可直接 `python weibopc.py` 等：脚本会在 `main()` 调用 `weibo_bootstrap.ensure_job_env()`。请保证 `.env` 里已有 **`WEIBO_TARGET` 或 `WEIBO_UID`**（与命令行 `-t` 二选一即可）。

## 仓库内文件说明

| 文件 | 作用 |
|------|------|
| `run_weibo.py` | **推荐入口**：解析 `-t`、设置路径、调度子命令与流水线 |
| `weibo_target.py` | 从 URL 或纯数字解析 UID |
| `weibo_bootstrap.py` | 加载 `.env`，解析目标，`setdefault` 各路径环境变量 |
| `weibo_env.py` | `python-dotenv` 与 `env_str` / `env_path` 等工具 |
| `WeiboVault.py` | m 站「当前」时间线抓取 |
| `weibopc.py` | PC 端时间线抓取 |
| `weibom_pre_20170301.py` | m 站向前翻到 `WEIBO_STOP_BEFORE` 之前 |
| `downloadweibopc.py` | 按 PC jsonl 下载媒体 |
| `download_weibovault_incremental.py` | 按 m_pre jsonl 增量下载 |
| `download_album_all_images.py` | 相册分页下载 |
| `collect_media_by_date.py` | 汇总 `media/` 到扁平目录 |

## 安全说明

- **勿**将 `.env`、真实 Cookie、token 推送到公开仓库。
- 默认 `.gitignore` 包含 `.env` 与 `*.jsonl`。

## 许可

个人工具性质；使用与分发责任自负。
