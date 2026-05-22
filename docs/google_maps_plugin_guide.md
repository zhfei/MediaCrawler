# Google Maps 平台插件使用指南

## 1. 能力概览

| 能力 | 说明 |
| --- | --- |
| 平台标识 | `google_maps` |
| 输入文件 | CSV，字段为 `city,address,country,lat,lng` |
| 任务模型 | `点位 × 关键词` |
| 默认关键词 | 巴西本地生活/餐饮相关 25 个关键词 |
| 语言区域 | `pt-BR` |
| 缩放级别 | `20z` |
| 存储方式 | `jsonl`、`json`、`csv`、`sqlite`、`db/postgres` |
| 去重方式 | 按 `shop_id` 去重，合并 `keyword`，累计 `report_count` |
| 断点续采 | SQLite/Postgres 模式下跳过 `success` 任务 |
| WebUI | `http://127.0.0.1:8080/google-maps` |

## 2. 常用命令

| 场景 | 命令 |
| --- | --- |
| 初始化 SQLite | `uv run python main.py --init_db sqlite` |
| 单任务采集到 JSONL | `GOOGLE_MAPS_TASK_LIMIT=1 uv run python main.py --platform google_maps --type search --save_data_option jsonl --headless false` |
| 小批量采集到 SQLite | `GOOGLE_MAPS_TASK_LIMIT=10 GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK=5 uv run python main.py --platform google_maps --type search --save_data_option sqlite --headless false` |
| 全量任务采集 | `GOOGLE_MAPS_TASK_LIMIT=0 uv run python main.py --platform google_maps --type search --save_data_option sqlite --headless false` |
| 启动 WebUI API | `uv run uvicorn api.main:app --host 127.0.0.1 --port 8080` |

## 3. 配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `GOOGLE_MAPS_POINTS_FILE` | `../谷歌巴西-采集点位_test(1).csv` | 点位 CSV 路径 |
| `GOOGLE_MAPS_TASK_LIMIT` | `1` | 本次最多执行任务数，`0` 表示全量 |
| `GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK` | `20` | 单任务最多采集店铺详情数 |
| `GOOGLE_MAPS_MAX_RETRY_TIMES` | `2` | 单任务失败自动重试次数 |
| `GOOGLE_MAPS_SCROLL_TIMES` | `8` | 结果列表滚动次数 |
| `GOOGLE_MAPS_SCROLL_SLEEP_SEC` | `1.2` | 每次滚动等待秒数 |
| `GOOGLE_MAPS_DETAIL_SLEEP_SEC` | `1.0` | 详情页等待秒数 |
| `GOOGLE_MAPS_ENABLE_CDP_MODE` | `false` | 是否使用 CDP 连接浏览器 |
| `GOOGLE_MAPS_USE_SYSTEM_CHROME` | `true` | 是否优先使用系统 Chrome |

## 4. API 接口

| 接口 | 用途 |
| --- | --- |
| `/api/config/google-maps` | 查看 Google Maps 配置 |
| `/api/google-maps/summary` | 查看点位、任务、数据库概览 |
| `/api/google-maps/tasks/preview?limit=20` | 预览任务 |
| `/api/google-maps/tasks/status` | 查看任务状态分布 |
| `/api/google-maps/tasks/reset` | 重置指定状态任务 |
| `/api/google-maps/shops?limit=100` | 查看已采集店铺 |
| `/api/google-maps/report` | 查看聚合报告 |
| `/api/google-maps/export?file_type=csv` | 导出 CSV |
| `/api/google-maps/export?file_type=json` | 导出 JSON |
| `/api/google-maps/run-logs` | 查看持久化运行日志 |

## 5. WebUI 操作

| 步骤 | 操作 |
| --- | --- |
| 1 | 启动 API 服务 |
| 2 | 打开 `http://127.0.0.1:8080/google-maps` |
| 3 | 查看点位数、任务数、任务状态 |
| 4 | 设置保存方式、任务数量、单任务店铺上限、重试次数 |
| 5 | 点击“启动”开始采集 |
| 6 | 采集完成后查看报告或导出 CSV/JSON |

## 6. 启动方式

Google Maps 是 MediaCrawler 的平台插件，启动方式与 MediaCrawler 主项目保持一致，不提供插件专属 Docker 启动入口。

| 场景 | 命令 |
| --- | --- |
| 安装依赖 | `uv sync` |
| 安装浏览器 | `uv run playwright install chromium` |
| 初始化 SQLite | `uv run python main.py --init_db sqlite` |
| 启动 WebUI API | `uv run uvicorn api.main:app --host 127.0.0.1 --port 8080` |
| CLI 采集 | `uv run python main.py --platform google_maps --type search --save_data_option sqlite --headless false` |

启动 WebUI API 后访问：

```text
http://127.0.0.1:8080/google-maps
```

## 7. 验收口径

| 验收项 | 标准 |
| --- | --- |
| 平台注册 | `uv run python main.py --help` 能看到 `google_maps` |
| 点位任务 | 1005 点位 × 25 关键词生成 25125 个任务 |
| 真实采集 | 能采集 Google Maps 店铺详情并写入 SQLite |
| 去重合并 | 同一 `shop_id` 不重复建店，合并关键词并增加 `report_count` |
| 断点续采 | 已成功任务再次运行会跳过 |
| 导出 | CSV/JSON 可从 API 或 WebUI 下载 |
| 报告 | 可查看关键词、分类、状态、城市统计 |

## 8. 自检脚本

| 场景 | 命令 |
| --- | --- |
| 检查点位、任务、SQLite | `uv run python tools/google_maps_smoke_check.py` |
| 连同 API 一起检查 | `uv run python tools/google_maps_smoke_check.py --api-url http://127.0.0.1:8080` |
