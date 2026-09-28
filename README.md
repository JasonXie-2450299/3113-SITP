# Bilibili 评论与弹幕爬虫

根据关键词搜索 Bilibili 视频，抓取每个视频的评论和弹幕，并分别保存到 CSV 文件。

## 1. 项目文件

| 文件 | 作用 |
| --- | --- |
| `bilibili_crawler.py` | 程序入口 |
| `cli.py` | 命令行参数和主抓取流程 |
| `api_client.py` | Bilibili 搜索、评论、弹幕请求 |
| `protobuf.py` | 分段弹幕 Protobuf 解析 |
| `utils.py` | 文本、时间、Cookie 等工具函数 |
| `config.py` | API 地址和签名常量 |
| `output.py` | CSV 字段和写入逻辑 |
| `errors.py` | 异常类型 |
| `requirements.txt` | Python 依赖 |

## 2. 环境要求

- Python 3.8 或更高版本
- `requests` 库

安装依赖：

```powershell
pip install -r requirements.txt
```

当前电脑的 `python` 命令可能指向 Python 2.7，建议使用：

```powershell
C:\miniconda\python.exe
```

## 3. 基本运行

先进入项目目录：

```powershell
cd "C:\Users\Jason Xie\OneDrive\Desktop\智驾SITP"
```

抓取关键词“智驾”下所有视频：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾"
```

结果默认写入当前目录：

```text
智驾_comments.csv
智驾_danmaku.csv
```

CSV 使用 UTF-8 BOM 编码，可以用 Excel 直接打开。

## 4. 常用参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `keyword` | 搜索关键词 | 必填 |
| `--output-dir` | CSV 输出目录 | 当前目录 |
| `--max-videos` | 最多处理多少个视频，0 表示不限制 | `0` |
| `--search-pages` | 最多搜索多少页，0 表示不限制 | `0` |
| `--max-comments` | 每个视频最多抓多少条评论，0 表示全部 | `0` |
| `--max-danmaku` | 每个分 P 最多抓多少条弹幕，0 表示全部 | `0` |
| `--start-date` | 只抓取该日期之后发布的视频 | 无限制 |
| `--end-date` | 只抓取该日期之前发布的视频 | 无限制 |
| `--comments-csv` | 指定评论 CSV 文件路径 | 自动生成 |
| `--danmaku-csv` | 指定弹幕 CSV 文件路径 | 自动生成 |
| `--append` | 追加到已有 CSV，而不是覆盖 | 关闭 |
| `--order` | 搜索排序方式 | `totalrank` |
| `--delay` | 每次请求之间的秒数 | `0.8` |
| `--timeout` | 请求超时秒数 | `15` |
| `--retries` | 网络错误重试次数 | `3` |
| `--cookie` | Cookie 字符串或 Cookie 文件路径 | 无 |
| `--proxy` | HTTP/HTTPS 代理地址 | 无 |

## 5. 发布时间过滤

只抓取 2026 年 9 月 10 日之后发布的视频：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --start-date 2026-09-10
```

只抓取 2026 年 9 月 10 日到 2026 年 9 月 20 日的视频：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --start-date 2026-09-10 --end-date 2026-09-20
```

日期格式为 `YYYY-MM-DD`，开始日期和结束日期都包含当天。

## 6. 指定输出文件

把评论写入指定文件：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --comments-csv output\comments.csv --danmaku-csv output\danmaku.csv
```

默认情况下会覆盖指定文件。如果希望保留旧数据并追加新数据：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --comments-csv output\comments.csv --danmaku-csv output\danmaku.csv --append
```

追加模式下：

- 已有文件不会覆盖。
- 已有文件不会重复写入表头。
- 空文件或新文件会自动写入表头。

## 7. 限制抓取数量

只测试 3 个视频，每个视频最多抓 100 条评论和 100 条弹幕：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --max-videos 3 --max-comments 100 --max-danmaku 100
```

## 8. Cookie 和代理

如果 B 站触发风控，可以使用浏览器 Cookie：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --cookie cookies.txt
```

也可以直接使用代理：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --proxy http://127.0.0.1:7890
```

Cookie 可以是从浏览器导出的 Netscape 格式文件，也可以是完整的 Cookie 字符串。

## 9. 输出字段

评论 CSV 主要字段：

```text
video_bvid, video_aid, video_title, video_author, video_pubdate,
video_play, video_review_count, rpid, root_rpid, parent_rpid,
user_id, username, user_level, message, like_count, reply_count,
comment_time, comment_timestamp
```

弹幕 CSV 主要字段：

```text
video_bvid, video_aid, video_title, video_author, video_pubdate,
video_play, video_review_count, part_page, part_title, cid,
time_seconds, mode, font_size, color, send_time, send_timestamp,
danmaku_pool, user_hash, row_id, text
```

## 10. 常见问题

### 搜索提示 risk control

程序会自动切换 WBI 签名接口重试。可以增加请求间隔：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --delay 1.5
```

### 评论提示“请求错误”

通常是临时风控。程序会自动重试，也可以提供 Cookie 或代理。

### 控制台中文乱码

程序已经切换到 UTF-8 输出。如果终端仍然乱码，可以在 PowerShell 中先执行：

```powershell
chcp 65001
```

### 想读取多个关键词

每次运行使用不同关键词，并指定同一个 CSV 文件追加：

```powershell
C:\miniconda\python.exe bilibili_crawler.py "智驾" --comments-csv output\all_comments.csv --danmaku-csv output\all_danmaku.csv --append
C:\miniconda\python.exe bilibili_crawler.py "特斯拉" --comments-csv output\all_comments.csv --danmaku-csv output\all_danmaku.csv --append
```

## 11. 关联 GitHub

如果还没有远程仓库：

```powershell
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
git add .
git commit -m "Initial commit"
git push -u origin main
```

以后更新代码：

```powershell
git add .
git commit -m "update crawler"
git push
```

提交时如果进入 Vim 编辑提交信息，保存退出：

```text
Esc
:wq
Enter
```
