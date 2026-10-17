<div align="center">

# MuseFlow

本地优先、零破坏索引、支持多轨复合包识别与沉浸流播放的智能数字资产中枢。

[![Family: *Flow](https://img.shields.io/badge/Family-*Flow-8A2BE2.svg)](https://github.com/mcocdaa)
[![CI Status](https://github.com/mcocdaa/MuseFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/mcocdaa/MuseFlow/actions)
[![Release](https://img.shields.io/github/v/release/mcocdaa/MuseFlow?include_prereleases&color=blue)](https://github.com/mcocdaa/MuseFlow/releases)
[![Python 3.13+](https://img.shields.io/badge/Python-3.13%2B-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![Vue 3.5+](https://img.shields.io/badge/Vue-3.5%2B-4FC08D.svg?logo=vuedotjs&logoColor=white)](frontend/package.json)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](docker-compose.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[English](README.md) · [简体中文](README_CN.md)

<img src="docs/assets/demo_museflow.gif" alt="MuseFlow Demo" width="840">

</div>

---

## ✨ 核心特性

- **零破坏原生就地索引**：直接对本地磁盘目录、物理系列与跨维虚拟超集（Supersets）建立非破坏性索引，绝不强制迁移、重命名或锁定原始媒体文件。
- **多轨复合原子包自动绑定**：自动识别同名或同工程伴随文件（`mp4 + srt + wav`、`mp3 + lrc`）并聚合为单一原子消费单元 `AssetUnit [bundle]`，支持 `.srt`/`.ass` 实时转码 WebVTT 字幕及多编码自动探测（`UTF-8`、`GBK`、`GB18030`）。
- **LLM 目录拓扑智能重组**：结合大语言模型（`Grok-4.7`、`Claude 3.5`、`GPT-4o`）与 AST 投影规则引擎，自动剥离嵌套子系列、配对跨目录音画字工程，并提供非破坏性干跑（Dry-Run）三色体检预览。
- **双态交互体验 — 资源工作台与抖音式沉浸流**：一键切换“小红书双列瀑布流 + 抖音上下滑沉浸视频流 + 悬浮黑胶音乐条”与“专业资源工作台”，支持跨平台原生文件定位（`explorer.exe /select`、`open -R`、`xdg-open`）。
- **可插拔推荐算法与 180s 防挂机埋点**：内置 **探索漫游 (Discover)**、**时光倒流 (Flashback)** 与 **猜你喜欢 (Affinity)** 算法，单次播放停留时长严格截断于 `min(dwell, 180s)`，防止页面后台挂机污染推荐权重。
- **7 款精选沉浸主题**：内置幻紫流光、黑曜深空（OLED）、粉黛微光、赛博电青、苍翠松隐、落日熔金与摄影工坊 7 套调色盘，支持 `localStorage` 即时持久化切换。

<details>
<summary><b>📊 为什么选择 MuseFlow？（点击展开与传统工具对比）</b></summary>

| 维度对比 | 传统素材库 (Eagle / Billfish) | 传统家庭影院 (Jellyfin / Plex) | 传统云相册 (Immich) | **MuseFlow (灵眸流)** |
| :--- | :--- | :--- | :--- | :--- |
| **底层物理文件** | 导入私有库，破坏原目录结构 | 纯物理只读挂载 | 按时间线重命名或迁移 | **零破坏原生就地索引，随时外部调用** |
| **复合音画字工程** | 拆成孤立碎文件，列表杂乱 | 仅识别单视频或剧集 | 无法配对多轨伴随文件 | **智能绑定 `mp4 + srt + wav` 原子包** |
| **混乱目录拓扑** | 纯人工打标签整理 | 死板扫描，不支持子系列剥离 | 强制时间线扁平化 | **LLM 拓扑推断 + Dry-Run 干跑预览** |
| **浏览消费体验** | 密集网格，无推荐流 | 传统电视海报墙 | 时间轴流水账 | **双列瀑布流 + 抖音上下滑 + 悬浮音乐条** |
| **推荐算法引擎** | 无推荐，纯靠搜索 | 仅“最近添加/继续观看” | 无 | **可插拔推荐（漫游 / 怀旧 / 偏好加权）** |

</details>

---

## 🚀 快速开始

### 方式一：Docker Compose 一键部署（1 条命令）

```bash
cp .env.example .env && docker compose up -d --build
```

启动后浏览器访问 **`http://localhost:8799`**（或 `.env` 中配置的 `MUSEFLOW_PORT`）。

### 方式二：本地开发运行（`uv` + `npm`）

```bash
cp .env.example .env
cd backend && uv sync && uv run python generate_samples.py
cd ../frontend && npm install && npm run dev &
cd ../backend && uv run uvicorn app.main:app --reload --port 8799
```

<details>
<summary><b>⚙️ 环境变量配置参考</b></summary>

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `MUSEFLOW_HOST` | `127.0.0.1` | 服务监听地址（Docker 环境默认 `0.0.0.0` 支持局域网访问） |
| `MUSEFLOW_PORT` | `8765` | 后端与 Web 服务端口（可配置为 `8799` 或 `8765`） |
| `MUSEFLOW_DATA_DIR` | `backend/data` | SQLite 数据库与缩略图缓存存储路径 |
| `MAX_DWELL_SECONDS` | `180.0` | 推荐系统单次有效停留防挂机截断上限（秒） |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容的大模型 API 基础地址 |
| `LLM_API_KEY` | `your_api_key_here` | 大模型 API 密钥 |
| `LLM_MODEL` | `gpt-4o` | 用于目录拓扑重组的模型（支持 `grok-4.7`、`gpt-4o`、`claude-3-5-sonnet` 等） |

</details>

---

## 🤖 AI 与 API 接口

MuseFlow 提供完整的 RESTful API（交互式文档位于 `/docs`）以及面向智能体的 MCP Server 工具集：

```bash
# 1. 查询已索引的原子媒体资产 (/api/assets)
curl -s "http://localhost:8799/api/assets?unit_type=video&limit=10" | jq .

# 2. 获取个性化推荐流 (/api/recommend)
curl -s "http://localhost:8799/api/recommend/feed?mode=unit&algorithm=affinity&limit=5" | jq .

# 3. 执行非破坏性目录拓扑重组干跑评估 (/api/organize/evaluate)
curl -s -X POST "http://localhost:8799/api/organize/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "collection_id": 1,
    "pipeline": {
      "levels": [
        {"level_index": 0, "facet": "tag.domain", "fallback": "通用分类"},
        {"level_index": 1, "naming": "{unit.title}%unique{}"}
      ]
    }
  }' | jq .
```

> **提示**：执行 `cd backend && uv run python -m app.mcp.server` 即可启动 Model Context Protocol (MCP) 服务供 Claude Desktop 或 Cursor 智能体调用。

---

## 📚 文档与开源协议

- 🏛️ [系统架构与领域实体模型](docs/architecture.md)
- 🤖 [LLM 目录拓扑分析与智能重组指南](docs/ai_triage_guide.md)
- 🔌 [可插拔推荐系统与行为埋点规范](docs/recommender_plugin.md)
- 🛠️ [AI 智能体操作契约](AGENTS.md) · [贡献指南](CONTRIBUTING.md) · [安全策略](SECURITY.md) · [更新日志](CHANGELOG.md)

本项目基于 [MIT License](LICENSE) 开源许可证发布。
