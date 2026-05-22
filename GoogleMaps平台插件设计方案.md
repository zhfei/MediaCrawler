# Google Maps 平台插件设计方案

## 1. 目标

| 目标 | 说明 |
| --- | --- |
| 平台插件 | 在 MediaCrawler 中新增 `google_maps` 平台 |
| 输入方式 | 支持点位 CSV：`city/address/country/lat/lng` |
| 任务模型 | 按 `点位 × 关键词` 生成采集任务 |
| 采集流程 | Google Maps Web，定位点位，附近搜索，关键词搜索 |
| 字段输出 | 输出 Google 巴西采集方案要求的店铺字段 |
| 去重逻辑 | 按 `shop_id` 去重，重复命中合并关键词集合 |
| 扩展性 | 遵循 MediaCrawler 现有平台插件模式，不污染已有平台 |
| 存储能力 | 分阶段实现 JSONL、CSV、SQLite、Postgres |
| 长期扩展 | 可继续接入其他地图平台、本地生活平台 |

## 2. 结论

| 问题 | 判断 |
| --- | --- |
| MediaCrawler 是否适合扩展 Google Maps | 适合 |
| 是否只新增一个子类即可完成 | 不够 |
| 推荐实现方式 | 新增完整 `google_maps` 平台插件 |
| 第一阶段重点 | 平台注册、点位任务、单任务采集、标准字段输出 |
| 第二阶段重点 | 详情字段解析、DB 去重、断点续采、失败重试 |
| 第三阶段重点 | WebUI 接入、运行监控、导出完善、稳定性增强 |

MediaCrawler 已有抽象爬虫、平台工厂、平台目录、存储工厂、配置系统、CLI 参数等扩展点。Google Maps 应按现有平台规范作为一个独立平台加入，而不是塞进现有 `xhs/dy/zhihu` 等平台逻辑里。

本方案不是区分“只做 MVP”和“后续可选”。所有阶段都属于必做交付范围，只是为了降低风险和方便 review，将完整插件拆成第一阶段、第二阶段、第三阶段逐步实现。最终结果必须是一个功能完善、可运行、可扩展的 Google Maps 平台插件。

## 3. 开发阶段

| 阶段 | 名称 | 目标 |
| --- | --- | --- |
| P0 | 架构接入 | 让 `--platform google_maps` 能被识别和启动 |
| P1 | 配置接入 | 增加 Google Maps 专属配置、关键词、点位文件路径 |
| P2 | 任务系统 | 生成点位关键词任务，支持基础状态管理 |
| P3 | 浏览器采集 | 实现 Google Maps 页面定位、搜索、滚动 |
| P4 | 字段解析 | 解析店铺列表和详情字段 |
| P5 | 存储导出 | 按需求字段保存和导出 |
| P6 | 稳定性 | 增加断点续采、失败重试、限速、截图 |
| P7 | WebUI 接入 | 在 MediaCrawler WebUI 中支持 Google Maps |

## 4. 文件改造计划

| 文件/目录 | 动作 | 说明 |
| --- | --- | --- |
| `media_platform/google_maps/` | 新增 | Google Maps 平台插件目录 |
| `media_platform/google_maps/__init__.py` | 新增 | 导出 `GoogleMapsCrawler` |
| `media_platform/google_maps/core.py` | 新增 | 主流程：点位加载、任务生成、任务执行 |
| `media_platform/google_maps/client.py` | 新增 | Google Maps 页面操作和数据解析 |
| `media_platform/google_maps/login.py` | 新增 | Google 登录态/CDP 处理 |
| `media_platform/google_maps/field.py` | 新增 | 字段枚举、任务状态、店铺状态 |
| `media_platform/google_maps/help.py` | 新增 | URL、价格、经纬度、状态解析工具 |
| `config/google_maps_config.py` | 新增 | BR 关键词、语言、比例尺、点位路径 |
| `model/m_google_maps.py` | 新增 | Pydantic 店铺模型 |
| `store/google_maps/` | 新增 | Google Maps 存储工厂和存储实现 |
| `store/google_maps/__init__.py` | 新增 | 根据保存方式创建存储器 |
| `store/google_maps/_store_impl.py` | 新增 | CSV、JSONL、DB 存储实现 |
| `database/models.py` | 修改 | 新增点位、任务、店铺、任务结果表 |
| `main.py` | 修改 | 注册 `google_maps` 平台 |
| `cmd_arg/arg.py` | 修改 | CLI 枚举支持 `google_maps` |
| `api/schemas/crawler.py` | 修改 | WebUI 平台枚举支持 Google Maps |
| `api/main.py` | 修改 | 平台列表展示 Google Maps |
| `config/__init__.py` | 修改 | 引入 Google Maps 配置 |
| `docs/` | 修改 | 增加 Google Maps 使用说明 |

## 5. 新增目录结构

```text
media_platform/google_maps/
├── __init__.py
├── core.py
├── client.py
├── login.py
├── field.py
└── help.py

store/google_maps/
├── __init__.py
└── _store_impl.py

model/
└── m_google_maps.py

config/
└── google_maps_config.py
```

## 6. 核心类设计

| 类 | 父类 | 作用 |
| --- | --- | --- |
| `GoogleMapsCrawler` | `AbstractCrawler` | Google Maps 平台主爬虫 |
| `GoogleMapsClient` | `AbstractApiClient` | 页面操作与字段解析客户端 |
| `GoogleMapsLogin` | `AbstractLogin` | Google 登录态处理 |
| `GoogleMapsStoreFactory` | 无 | 根据保存方式创建存储器 |
| `GoogleMapsJsonlStoreImplement` | `AbstractStore` | JSONL 输出 |
| `GoogleMapsCsvStoreImplement` | `AbstractStore` | CSV 输出 |
| `GoogleMapsDbStoreImplement` | `AbstractStore` | DB 去重保存 |
| `GoogleMapsTask` | Pydantic/ORM | 点位关键词任务 |
| `GoogleMapsShop` | Pydantic/ORM | 店铺数据模型 |

## 7. 采集流程设计

| 步骤 | 说明 |
| --- | --- |
| 1 | 读取点位 CSV |
| 2 | 读取 Google Maps BR 关键词 |
| 3 | 生成 `point × keyword` 任务 |
| 4 | 启动 Playwright/CDP 浏览器 |
| 5 | 切换语言为 `pt-BR` |
| 6 | 打开 `https://www.google.com/maps/@lat,lng,20z?hl=pt-BR` |
| 7 | 点击或触发“附近”搜索 |
| 8 | 输入关键词并搜索 |
| 9 | 缓慢滚动结果列表，直到无新增结果 |
| 10 | 进入店铺详情页 |
| 11 | 解析店铺字段 |
| 12 | 按 `shop_id` 去重保存 |
| 13 | 若重复店铺，则合并 `keyword` 并增加 `report_count` |
| 14 | 标记任务状态 |
| 15 | 导出结果 |

## 8. 标准输出字段

| 字段 | 类型 | 来源 |
| --- | --- | --- |
| `keyword` | `list[str]` | 命中关键词集合 |
| `platform` | `str` | 固定 `GoogleMap` |
| `city` | `str` | 点位 CSV |
| `shop_id` | `str` | Google Maps URL 或页面数据 |
| `shop_name` | `str` | 店铺详情 |
| `level` | `float/null` | 评分 |
| `category` | `list[str]` | 店铺品类 |
| `is_open` | `str` | 营业状态原文 |
| `shop_lat` | `float/null` | 店铺坐标 |
| `shop_lng` | `float/null` | 店铺坐标 |
| `crawl_lat` | `float` | 采集点纬度 |
| `crawl_lng` | `float` | 采集点经度 |
| `address` | `str` | 地址 |
| `phone` | `str` | 电话 |
| `order_url` | `str` | 下单链接 |
| `official_url` | `str` | 官网 |
| `user_ratings_total` | `int` | 评论数 |
| `avg_price` | `str` | 原始人均消费 |
| `open_hours` | `list` | 营业时间 |
| `report_count` | `int` | 召回次数 |
| `menu_url` | `str` | 菜单链接 |
| `service_options` | `list[str]` | 服务项 |
| `busy_time` | `str` | 繁忙时间 |
| `create_time` | `str` | 创建时间 |
| `real_shop_state` | `str` | 店铺状态 |
| `currency_symbol` | `str` | 价格解析 |
| `price_range` | `str` | 价格解析 |
| `consumption_level` | `str` | 价格解析 |

## 9. 数据库表设计

| 表 | 作用 |
| --- | --- |
| `google_maps_points` | 存储 CSV 点位 |
| `google_maps_tasks` | 存储点位关键词任务 |
| `google_maps_shops` | 存储去重后的店铺 |
| `google_maps_task_results` | 记录任务和店铺命中关系 |
| `google_maps_run_logs` | 记录采集运行日志和错误 |

## 10. 价格字段拆分规则

| 原始格式示例 | `currency_symbol` | `price_range` | `consumption_level` |
| --- | --- | --- | --- |
| 空 | 空 | 空 | 空 |
| `BRL 100-120` | `R$` | `100-120` | 空 |
| `Más de BRL 180` | `R$` | `180+` | 空 |
| `Más de R$ 180` | `R$` | `180+` | 空 |
| `R$60–100` | `R$` | `60-100` | 空 |
| `+R$ 200` | `R$` | `200+` | 空 |
| `R$200+` | `R$` | `200+` | 空 |
| `BRL 50-60 K` | `R$` | `50000-60000` | 空 |
| `Más de BRL 1 K` | `R$` | `1000+` | 空 |
| `$` / `$$` / `$$$` / `$$$$` | 空 | 空 | 原值 |

## 11. 优先级计划

| 优先级 | 任务 | 交付标准 |
| --- | --- | --- |
| P0 | 注册平台 | `uv run main.py --platform google_maps --type search` 可启动 |
| P0 | 新增配置 | 能读取点位路径、关键词、语言、缩放配置 |
| P1 | 点位任务生成 | 1005 点位 × 25 关键词生成任务 |
| P1 | JSONL 存储 | 能输出标准字段空壳和基础数据 |
| P2 | Playwright 页面打开 | 能打开 Google Maps 指定经纬度 |
| P2 | 搜索流程 | 能按关键词搜索附近结果 |
| P3 | 列表解析 | 能拿到店铺名称、URL、`shop_id` |
| P3 | 详情解析 | 能拿到地址、电话、评分、营业时间等 |
| P4 | 去重合并 | 同一 `shop_id` 合并关键词 |
| P4 | 价格拆分 | 正确解析 `avg_price` 三字段 |
| P5 | DB 存储 | SQLite/Postgres 支持去重保存 |
| P6 | WebUI 接入 | 可从 WebUI 选择 Google Maps 并运行 |

## 12. 分阶段实现范围

| 阶段 | 必做范围 | 交付目标 |
| --- | --- | --- |
| 第一阶段 | 平台注册、点位 CSV 读取、任务生成、Google Maps 打开、单点位单关键词搜索、基础字段输出、JSONL/CSV 输出 | `google_maps` 能作为 MediaCrawler 正式平台启动，并完成最小闭环采集 |
| 第二阶段 | 店铺详情字段解析、价格字段拆分、`shop_id` 去重、关键词合并、任务状态、失败重试、SQLite/Postgres 存储 | 满足采集方案的核心字段、去重和稳定运行要求 |
| 第三阶段 | WebUI 接入、运行监控、任务筛选、导出完善、失败截图、批量调度、采集报告 | 形成完整可操作的 Google Maps 平台插件功能 |

## 13. 阶段验收标准

| 阶段 | 验收项 | 标准 |
| --- | --- | --- |
| 第一阶段 | 平台启动 | `--platform google_maps` 正常识别 |
| 第一阶段 | 点位读取 | 能读取 `谷歌巴西-采集点位_test(1).csv` |
| 第一阶段 | 任务数量 | 能生成 25125 个任务 |
| 第一阶段 | 单任务采集 | 能完成 1 个点位 + 1 个关键词 |
| 第一阶段 | 基础字段输出 | 能输出标准字段结构 |
| 第二阶段 | 详情字段输出 | 输出采集方案要求的店铺字段 |
| 第二阶段 | 去重 | 重复 `shop_id` 不重复保存 |
| 第二阶段 | 价格拆分 | `BRL 40-60` 能拆成 `R$ / 40-60 / 空` |
| 第二阶段 | 任务稳定性 | 支持任务状态、失败重试、断点续采 |
| 第三阶段 | WebUI | 可从 WebUI 选择 Google Maps、查看任务、触发采集 |
| 第三阶段 | 导出 | 可导出最终店铺数据和任务报告 |
| 全阶段 | 可扩展 | 新平台逻辑不污染 xhs/dy 等平台 |

## 14. 风险点与应对

| 风险 | 应对 |
| --- | --- |
| Google Maps DOM 变化 | 解析逻辑集中在 `client.py` |
| 登录态失效 | 复用 CDP 和持久化浏览器目录 |
| 结果加载不稳定 | 滚动、重试、截图 |
| 字段隐藏 | 多选择器策略和原始详情 JSON 兜底 |
| 数据重复 | `shop_id` 唯一键 |
| 采集耗时长 | 断点任务表和批量执行 |
| 许可证限制 | MediaCrawler 许可证偏学习研究，商业化前需确认授权 |

## 15. 开发顺序

| 顺序 | 任务 |
| --- | --- |
| 1 | 新建 `media_platform/google_maps` 目录和基础类 |
| 2 | 注册 `google_maps` 到 CLI、API、CrawlerFactory |
| 3 | 新增 `google_maps_config.py` |
| 4 | 实现点位 CSV 读取与任务生成 |
| 5 | 实现标准字段模型和价格拆分 |
| 6 | 实现 JSONL/CSV 存储 |
| 7 | 实现浏览器启动和 Google Maps URL 定位 |
| 8 | 实现关键词搜索和列表滚动 |
| 9 | 实现详情页字段解析 |
| 10 | 实现去重、任务状态、失败重试 |
| 11 | 接入 SQLite/Postgres |
| 12 | 接入 WebUI |

## 16. 完整交付节奏

| 阶段 | 实现内容 |
| --- | --- |
| 第一阶段 | 跑通 `平台注册 -> 点位读取 -> 任务生成 -> 单任务采集 -> JSONL/CSV 输出` |
| 第二阶段 | 补全详情字段解析、去重、价格拆分、SQLite/Postgres、断点续采、失败重试 |
| 第三阶段 | 接入 WebUI、运行监控、批量调度、导出报告、稳定性增强 |

## 17. 当前实现与验证记录

| 项目 | 结果 |
| --- | --- |
| 平台注册 | 已支持 `--platform google_maps` |
| 点位读取 | 已读取 `1005` 个巴西 Itabira 点位 |
| 任务生成 | 已生成 `25125` 个 `点位 × 关键词` 任务 |
| 标准字段输出 | 已覆盖方案字段，JSONL 保持数组字段，CSV/DB 序列化数组字段 |
| SQLite 表 | 已创建 `google_maps_points/tasks/shops/task_results/run_logs` |
| 断点续采 | SQLite/Postgres 模式下已跳过 `success` 任务 |
| 失败重试 | 已支持 `GOOGLE_MAPS_MAX_RETRY_TIMES` 自动重试 |
| WebUI/API | 已新增 `/google-maps` 控制页和 Google Maps 专属 API |
| API 接口 | 已支持配置、概览、任务预览、任务状态、任务重置、店铺列表、采集报告、CSV/JSON 导出、运行日志 |
| 运行日志 | 已支持失败任务日志与截图路径落库到 `google_maps_run_logs` |
| 导出能力 | 已支持 `/api/google-maps/export?file_type=csv/json` |
| 报告能力 | 已支持关键词、分类、店铺状态、城市维度聚合 |
| 使用文档 | 已新增 `docs/google_maps_plugin_guide.md` |
| 单元测试 | 已新增 `tests/test_google_maps_plugin.py`，覆盖点位、任务、URL、价格、状态、字段和存储工厂 |
| 启动方式 | 与 MediaCrawler 主项目保持一致：通过 `main.py` 或 `uvicorn api.main:app` 启动，不提供插件专属 Docker 入口 |
| 真实采集验证 | 已采集 `café`、`bar`、`padaria` 三个任务 |
| 去重合并验证 | `Panhok Padaria Artesanal` 已合并关键词 `["café", "padaria"]`，`report_count=2` |
| 当前 SQLite 店铺数 | `8` |
| 当前 SQLite 任务结果数 | `9` |
| 当前 SQLite 任务状态 | `success=3`，`pending=25122` |
| 最新真实样例 | `Bar do Tarcisio`、`Bar da Marlene`、`Bar Do Bim`、`Deck`、`Estação Slod Choperia e Gastronomia` |
| 已验证字段样例 | 店名、评分、分类、地址、电话、官网、营业状态、营业时间、服务项、繁忙时间、店铺坐标、采集坐标 |
| 本机注意事项 | Codex 沙箱内直接启动 Chromium 会被 macOS Crashpad 权限限制拦截；真实采集需在普通终端或提升权限环境运行 |

第一阶段不是最终目标，只是完整插件交付路径中的第一步。最终必须完成第二阶段和第三阶段，让 `google_maps` 成为 MediaCrawler 中可启动、可配置、可采集、可去重、可断点续采、可在 WebUI 操作、可导出交付数据的正式平台。

## 18. Google Maps 插件详细启动步骤

Google Maps 是 MediaCrawler 项目内的平台插件，启动方式必须与 MediaCrawler 主项目保持一致。插件不提供独立 Docker 启动入口，不单独启动后端，也不脱离 `main.py`、`api.main:app`、MediaCrawler WebUI 运行。

### 18.1 前置准备

| 步骤 | 命令/操作 | 说明 |
| --- | --- | --- |
| 1 | `cd /Volumes/DK5A1-2TB-SSD/MacMini/爬虫/project1/MediaCrawler` | 进入 MediaCrawler 项目目录 |
| 2 | `uv sync` | 按 MediaCrawler 原项目方式安装依赖 |
| 3 | `uv run playwright install chromium` | 安装 Playwright Chromium |
| 4 | 确认 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` 存在 | macOS 本机默认优先使用系统 Chrome |
| 5 | 确认 `../谷歌巴西-采集点位_test(1).csv` 存在 | 默认点位 CSV 路径 |

### 18.2 一条指令启动

日常本机使用时，推荐直接用下面这一条指令完成依赖同步、浏览器安装、SQLite 初始化、启动 WebUI API：

```bash
cd /Volumes/DK5A1-2TB-SSD/MacMini/爬虫/project1/MediaCrawler && { for pid in $(lsof -ti tcp:8080); do kill -9 "$pid"; done; sleep 1; uv sync && uv run playwright install chromium && uv run python main.py --init_db sqlite && uv run uvicorn api.main:app --host 127.0.0.1 --port 8080; }
```

启动成功后打开：

```text
http://127.0.0.1:8080/google-maps
```

| 说明 | 内容 |
| --- | --- |
| 这条指令做什么 | 安装依赖、安装浏览器、初始化 SQLite、启动 MediaCrawler WebUI API |
| 如何处理端口占用 | 启动前通过 `lsof -ti tcp:8080` 查找占用 `8080` 的旧进程；如果存在，则自动 `kill` |
| 是否是插件专属启动器 | 不是，仍然使用 MediaCrawler 标准 `main.py` 和 `api.main:app` |
| 适合场景 | 本机第一次启动或不确定环境是否完整时 |
| 后续日常启动 | 如果依赖和数据库已初始化，只需要执行 `uv run uvicorn api.main:app --host 127.0.0.1 --port 8080` |

### 18.3 初始化数据库

| 场景 | 命令 | 说明 |
| --- | --- | --- |
| 初始化 SQLite 表 | `uv run python main.py --init_db sqlite` | 创建 Google Maps 点位、任务、店铺、任务结果、运行日志表 |
| 检查数据库 | `uv run python tools/google_maps_smoke_check.py` | 检查点位、任务、SQLite 表和记录数 |

### 18.4 CLI 方式启动采集

| 场景 | 命令 | 说明 |
| --- | --- | --- |
| 采集 1 个任务到 JSONL | `GOOGLE_MAPS_TASK_LIMIT=1 uv run python main.py --platform google_maps --type search --save_data_option jsonl --headless false` | 快速验证浏览器和字段输出 |
| 采集 1 个任务到 SQLite | `GOOGLE_MAPS_TASK_LIMIT=1 uv run python main.py --platform google_maps --type search --save_data_option sqlite --headless false` | 推荐验证方式，支持任务状态和去重 |
| 小批量采集 | `GOOGLE_MAPS_TASK_LIMIT=10 GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK=5 uv run python main.py --platform google_maps --type search --save_data_option sqlite --headless false` | 控制风险，适合逐步扩大采集范围 |
| 全量采集 | `GOOGLE_MAPS_TASK_LIMIT=0 uv run python main.py --platform google_maps --type search --save_data_option sqlite --headless false` | 执行全部 25125 个任务，需确认限速、运行时间和合规风险 |

### 18.5 WebUI/API 方式启动

| 步骤 | 命令/操作 | 说明 |
| --- | --- | --- |
| 1 | `uv run uvicorn api.main:app --host 127.0.0.1 --port 8080` | 按 MediaCrawler 原 WebUI API 方式启动 |
| 2 | 打开 `http://127.0.0.1:8080/google-maps` | 使用 Google Maps 插件专属控制页 |
| 3 | 查看点位数、关键词数、计划任务数、任务状态 | 页面会读取 `/api/google-maps/summary` 和 `/api/google-maps/tasks/status` |
| 4 | 保存方式选择 `SQLite Database` | 推荐使用 SQLite，支持去重、断点续采和报告 |
| 5 | 设置任务数量，例如 `1`、`3`、`10` | 对应 `GOOGLE_MAPS_TASK_LIMIT` |
| 6 | 设置单任务店铺上限，例如 `5` 或 `20` | 对应 `GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK` |
| 7 | 设置失败重试次数，例如 `1` 或 `2` | 对应 `GOOGLE_MAPS_MAX_RETRY_TIMES` |
| 8 | 点击“点位文件”的“选择文件”按钮 | 从电脑目录中选择 CSV 文件，页面会上传到 MediaCrawler 本地输入目录 |
| 9 | 浏览器模式选择“有界面” | macOS 本机真实采集推荐 headed 模式 |
| 10 | 点击“启动” | 由 MediaCrawler API 调用 `main.py --platform google_maps` 启动采集，并使用已选择的点位文件 |
| 11 | 采集完成后查看报告或导出 CSV/JSON | 页面提供报告、店铺列表和导出入口 |

### 18.6 原始主页与 Google Maps 专属页的区别

| 页面 | 地址 | 用途 | 注意事项 |
| --- | --- | --- | --- |
| MediaCrawler 原始主页 | `http://127.0.0.1:8080/` | 原项目通用控制台 | 下拉框可出现 Google Maps，但没有完整 Google Maps 专属参数和报告区 |
| Google Maps 专属页 | `http://127.0.0.1:8080/google-maps` | Google Maps 点位采集控制台 | 推荐使用，支持任务预览、启动、停止、状态、报告和导出 |

如果在原始主页选择了 `Google Maps` 但界面没有明显变化，这是因为原始 React WebUI 没有为 Google Maps 重建专属表单。Google Maps 插件完整操作入口是 `/google-maps`。

### 18.7 常用接口

| 接口 | 说明 |
| --- | --- |
| `/api/config/google-maps` | 查看 Google Maps 当前配置 |
| `/api/google-maps/summary` | 查看点位数、关键词数、计划任务数、数据库统计 |
| `/api/google-maps/tasks/preview?limit=20` | 预览生成的点位关键词任务 |
| `/api/google-maps/points/upload` | 上传用户从电脑目录中选择的点位 CSV 文件 |
| `/api/google-maps/tasks/status` | 查看任务状态分布 |
| `/api/google-maps/tasks/reset` | 将指定状态任务重置为 `pending` |
| `/api/google-maps/shops?limit=100` | 查看已采集店铺 |
| `/api/google-maps/report` | 查看关键词、分类、城市、店铺状态聚合报告 |
| `/api/google-maps/export?file_type=csv` | 导出 CSV |
| `/api/google-maps/export?file_type=json` | 导出 JSON |
| `/api/google-maps/run-logs` | 查看持久化运行日志 |

### 18.8 自检与验收

| 场景 | 命令 | 预期 |
| --- | --- | --- |
| 插件单元测试 | `uv run pytest tests/test_google_maps_plugin.py -q` | `7 passed` |
| 本地自检 | `uv run python tools/google_maps_smoke_check.py` | 点位、任务、SQLite 检查为 `PASS` |
| API 自检 | `uv run python tools/google_maps_smoke_check.py --api-url http://127.0.0.1:8080` | API、点位、任务、SQLite 检查为 `PASS` |

## 19. 当前关键配置

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `GOOGLE_MAPS_POINTS_FILE` | `../谷歌巴西-采集点位_test(1).csv` | 点位 CSV 路径 |
| `GOOGLE_MAPS_TASK_LIMIT` | `1` | 单次执行任务数；`0` 表示全量 |
| `GOOGLE_MAPS_USE_SYSTEM_CHROME` | `true` | 优先使用系统 Google Chrome |
| `GOOGLE_MAPS_CHROME_EXECUTABLE_PATH` | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` | macOS Chrome 路径 |
| `GOOGLE_MAPS_LOCALE` | `pt-BR` | Google Maps 页面语言 |
| `GOOGLE_MAPS_TIMEZONE` | `America/Sao_Paulo` | 浏览器时区 |
| `GOOGLE_MAPS_ZOOM` | `20z` | 地图缩放级别 |
| `GOOGLE_MAPS_MAX_RESULT_LINKS_PER_TASK` | `20` | 单任务最多进入详情页数量 |

## 20. 当前真实采集验证结果

| 验证项 | 结果 |
| --- | --- |
| 点位读取 | 1005 个 |
| 任务生成 | 25125 个 |
| 真实浏览器 | 系统 Google Chrome headed 模式跑通 |
| 单任务样例 | `Itabira / -19.628,-43.232 / café` |
| 店铺召回 | 成功召回并保存 `Panhok Padaria Artesanal` 等店铺 |
| 已验证字段 | `shop_id`、`shop_name`、`level`、`category`、`address`、`phone`、`official_url`、`avg_price`、`open_hours`、`service_options`、`shop_lat`、`shop_lng` |
