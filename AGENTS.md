# MuseFlow (灵眸流) — Instructions for AI Coding Agents

本文件面向在 **MuseFlow (灵眸流)** 仓库中协作与开发的 AI Coding Agent（包括 Antigravity, Claude, Copilot, Trae, Cursor 等）。  
人类开发者与开源贡献者请参阅 [README.md](README.md)、[README_CN.md](README_CN.md) 与 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 1. Project Mission & Invariants (核心定位与不可破坏的契约)

MuseFlow 是 `*Flow` 生态下专注海量多媒体资产纳管与沉浸流媒体消费的个人数字资产基础设施 (Local-First AI-Powered DAM & Streaming Hub)。  
其核心差异化在于 **“非破坏性物理文件索引 + 大模型目录拓扑重组 + 复合音画字原子单元打包 + 沉浸式流媒体消费双态体验”**。

### 核心不可违背契约 (Invariants)：

1. **底层物理文件非破坏性纳管 (Zero-Destruction Invariant)**：
   - **严禁**静默重命名、移动、修改或删除用户磁盘上的原始物理文件。
   - 所有的归类、分层、重组必须在虚拟数据层通过 `Collection`、`AssetUnit` 和 `AssetFile` 的映射关系实现。
   - 任何涉及磁盘文件的物理整理操作，必须由用户通过 UI 明确触发与二次确认。

2. **原子消费单元粒度守恒 (AssetUnit Particle Invariant)**：
   - 推荐信息流（Feed）、播放器及消费接口**只能向用户呈现 `AssetUnit`**。
   - **绝不能**把伴随的孤立字幕文件（`.srt` / `.vtt`）或背景音轨（`.wav` / `.flac`）作为孤岛卡片推送到瀑布流中。
   - 复合包（`bundle`）必须由主媒体（视频或音频）作为 `primary`，附属文件按 `role`（`subtitle`、`audio`、`lyrics`）挂载关联。

3. **有效停留时长防挂机截断 (Telemetry Cap Contract)**：
   - 用户单次停留时长上报必须经过 `min(dwell_seconds, MAX_DWELL_SECONDS)` 截断（默认上限 180 秒）。
   - **严禁**将用户未关闭浏览器标签页、待机或离开数小时的时长原始计入数据库，防止污染推荐系统偏好打分。

4. **流媒体 HTTP 206 与 WebVTT 转换协议**:
   - 视频/音频路由必须支持 HTTP `Range` 请求头并返回 `206 Partial Content`，否则前端播放器无法拖拽进度条与分段缓冲。
   - 字幕流通过 `/api/stream/subtitle/{file_id}` 必须动态转换为浏览器标准的 `text/vtt; charset=utf-8`，后端须具备字符集（UTF-8, GBK, GB18030）自动探测容错。

5. **AI 目录拓扑分析纯净与幂等性**:
   - 向 LLM 发送目录结构分析请求时，仅提取目录树相对路径、扩展名与文件体积元数据，**严禁上传大体积媒体二进制流**。
   - AI 输出方案必须遵循严格的结构化 JSON Schema，并在 UI 弹窗呈现可视化预览，用户未点击确认应用前绝不修改数据库结构。

6. **仓库代码与二进制干净边界 (Git Cleanliness)**:
   - **严禁**在 Git 中提交测试用音视频二进制文件（如 `*.mp4`, `*.wav`, `*.jpg`, `*.sqlite3`）。
   - 测试样本媒体统一由 `backend/generate_samples.py` 动态生成并在 `.gitignore` 中排除。

7. **开源项目与绝对隐私隔离 (Zero Privacy Leakage & Open-Source Decoupling Invariant)**:
   - **开源公共资产定位**：MuseFlow 是通用开源项目。本地开发或测试过程中挂载的物理 NAS、测试目录名、个人网络 IP、登录凭据或真实媒体文件，**仅作为临时验证沙箱**，**严禁将其泄漏至 Git 仓库**。
   - **严禁硬编码用户隐私路径**：禁止在代码、默认配置、提交文档中写入包含特定用户名、私有盘符子路径（如 `/mnt/private_nas/...` 等用户私有目录）、内网固定 IP 或私人音视频作品命名。
   - **统一环境变量解耦**：所有外部存储路径一律抽象为环境变量（`MUSEFLOW_NAS_MOUNT`、`MUSEFLOW_MEDIA_ROOTS`），开源默认值统一回退为标准抽象路径（如 `/mnt/media` 或 `sample_media/`）。用户专属测试路径严格通过未跟踪的 `.env` 注入。
   - **临时审计脚本隔离**：针对特定用户数据库的单次修复/探测脚本（如 `audit_*.py`、`database_healer.py`、`manual_*.py`）必须被 `.gitignore` 严格排除，严禁作为生产代码提交。
   - **系统运维脚本参数化**：自动化挂载等运维脚本必须设计为通用入参驱动，提供环境变量与命令行参数回退，禁止写死用户个人的盘符或用户 ID。

8. **通用核心引擎与特定领域规则绝对解耦 (Generic Core Engine vs. Domain-Specific Rules Invariant)**:
   - **核心通用契约**：MuseFlow 核心代码库只负责提供通用抽象与多媒体管理基础设施（如文件元数据解析、HTTP 206 流媒体传输、音画复合包绑定、投影 DSL 解释器、面向对象多维标签图谱）。
   - **严禁领域与私人硬编码**：**严禁**在仓库核心代码（如 `reverse_tagger.py`、`tag_organizer.py`、`scanner.py`）中硬编码任何特定媒体领域术语（如特定小众分类词库）、特定创作者别名、特定称谓规约或私有俚语过滤。
   - **外部配置驱动与沙箱隔离**：所有非通用的创作者别名映射、称号后缀剥离、题材重命名与路径过滤规则，必须统一通过外部用户配置文件（`backend/data/config/user_rules.json`）动态注入，或存放在外挂运维脚本中，并在 `.gitignore` 中严格排除，绝不污染开源代码。

---

## 2. Repository Layout (项目结构速查)

```text
MuseFlow/
├── .github/workflows/          # GitHub Actions CI/CD 流水线 (ci.yml)
├── backend/                    # FastAPI 后端核心引擎
│   ├── app/
│   │   ├── api/                # REST 路由 (assets, stream, recommend, telemetry, ai, system, organize)
│   │   ├── core/               # 配置管理 (config.py), 规则加载器 (user_rules.py), 数据库 (db.py)
│   │   ├── models/             # 领域模型 (entities.py: AssetUnit, AssetFile, Collection, Superset)
│   │   ├── plugins/            # 可插拔推荐算法 (base.py, registry.py: discover, flashback, affinity)
│   │   ├── services/           # bundle_detector.py, scanner.py, reverse_tagger.py, projection_dsl.py
│   │   └── main.py             # FastAPI 入口及静态资源挂载
│   ├── generate_samples.py     # 自动化测试样本生成器
│   ├── pyproject.toml          # 后端依赖配置
│   ├── rules.example.json      # 用户外挂规则配置示例模板 (脱敏通用)
│   └── run.py                  # 服务启动入口
├── frontend/                   # Vue 3 + Tailwind CSS v4 现代前端
│   ├── src/
│   │   ├── api/index.js        # Axios API 客户端 (含 120s AI 拓扑分析超时配置)
│   │   ├── components/         # 核心交互组件 (Navbar, StreamFeed, Workplace, PipelineBuilderModal, ...)
│   │   ├── stores/             # Pinia 状态管理 (mediaStore, playerStore, themeStore)
│   │   ├── style.css           # 7 款沉浸式主题设计变量系统
│   │   └── App.vue             # 双态主界面切换与全局播放浮层
│   ├── package.json
│   └── vite.config.js
├── docs/                       # 架构设计、AI 拓扑分析、推荐算法插件深度文档
├── scripts/                    # 开发、构建、测试与无头整理脚本 (organize_nas.py, dev.sh, build.sh, test.sh)
├── Dockerfile                  # 容器化多阶段镜像构建
├── compose.yaml                # Docker Compose 一键编排
├── AGENTS.md                   # AI Coding Agent 契约与操作规范 (本文件)
├── CHANGELOG.md                # 版本更新日志 (Keep a Changelog)
├── CONTRIBUTING.md             # 开发者与开源贡献指南
├── SECURITY.md                 # 安全与漏洞披露策略
├── LICENSE                     # MIT 开源许可证
├── README.md                   # 英文旗舰项目介绍
└── README_CN.md                # 中文旗舰项目介绍
```

---

## 3. Essential Commands (核心研发与验证命令)

### 3.1 后端服务 (`backend/`)
```bash
# 1. 运行依赖同步
uv sync

# 2. 启动开发服务器 (端口 8765)
uv run python run.py

# 3. 动态生成测试样本媒体库
uv run python generate_samples.py

# 4. 执行全量单元测试与 API 路由测试
uv run pytest tests/ -v
```

### 3.2 前端界面 (`frontend/`)
```bash
# 1. 安装前端依赖
pnpm install

# 2. 启动 Vite 开发服务器 (端口 5173，自动代理 /api 至 8765)
pnpm dev

# 3. 生产环境构建 (编译至 frontend/dist，后端自动提供静态托管)
pnpm build
```

### 3.3 自动化流水线 (`scripts/`)
```bash
# 启动本地完整开发环境
./scripts/dev.sh

# 编译前端并自检后端
./scripts/build.sh

# 运行自动化测试与健康巡检
./scripts/test.sh
```

---

## 4. Coding Agent Verification Checklist (变更交付自检清单)

在向仓库提交任何代码修改前，请逐项检查确认：
- [ ] **物理文件安全**：未写入任何会静默覆写或删除用户源文件的逻辑。
- [ ] **数据结构守恒**：信息流推荐始终为 `AssetUnit`，复合包正常保留主/附文件关系。
- [ ] **流媒体 Range 206 兼容**：新加入的媒体路由支持 HTTP Byte Range 请求。
- [ ] **构建无错**：前端 `pnpm build` 无报错且产物正常输出到 `frontend/dist`。
- [ ] **主题设计系统兼容**：新增 UI 元素颜色全部引用 CSS 主题变量（如 `var(--bg-surface)`、`var(--text-main)`），禁止硬编码颜色。
- [ ] **代码无脏数据**：没有将音视频媒体、临时 SQLite 库或日志文件引入 Git 追踪。
- [ ] **隐私与环境解耦**：未硬编码任何特定用户的物理盘符、NAS 路径、私有 IP、特定作品名或个人目录名称；临时审计脚本与本地 `.env` 已被 `.gitignore` 排除。
- [ ] **通用与特定绝对解耦**：严禁在核心代码中硬编码任何特定媒体领域分类（如特定小众词库）、特定创作者别名或特定称谓后缀；所有个性化规则一律通过外部配置文件 (`user_rules.json`) 或用户外挂脚本驱动。
- [ ] **类型与文档完整**：新增核心服务函数具备完备的 Python 类型注解及 Google-style 语义化说明。
