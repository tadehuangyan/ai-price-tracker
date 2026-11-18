# 商品历史价格追踪系统 · AI 智能导购

> 全国高校 AI Web 开发挑战赛参赛作品 —— AI Native Web 应用

一个面向消费者的商品历史价格追踪与智能导购 Web 应用：粘贴商品链接或搜索关键词即可抓取多平台历史价格、生成价格曲线、设置降价提醒，并内置 **AI 智能导购 Agent**，基于 Function Calling、RAG 知识库、多模态识图与 MCP 网页行情工具，给出可溯源、可解释的个性化购买建议。

## 项目简介

**核心功能**

| 模块 | 说明 |
| --- | --- |
| 商品查询 | 关键词实时比价搜索 / 粘贴商品链接自动抓取，展示多平台报价与历史价格曲线（ECharts） |
| 价格追踪 | 收藏商品、设置目标价，后台定时采集，降价后站内信 / 邮件提醒 |
| 价格对比 | 多商品横向对比，支持通过关键词、商品链接、收藏列表加入对比 |
| AI 智能导购 | 流式对话 + 多轮会话历史；Agent 自主调用工具完成查历史价、比价、建提醒、查行情等多步任务 |
| 用户画像 | Agent 从对话中沉淀消费偏好到 Markdown 画像文件，用户可在个人页查看 / 手动修正，实现个性化建议 |
| 后台管理 | 用户 / 商品 / 数据源 / 敏感词 / 系统参数 / 操作日志管理 |

**AI 能力亮点**

- **Function Calling Agent**：历史价查询、跨平台比价、降价提醒、画像读写、知识库检索、网页行情获取等 10+ 工具由模型自主规划调用，支持多步推理与降级兜底
- **RAG 知识库**：比价攻略 / 大促规律 / 选购指南入库，向量 + 关键词混合检索注入 Prompt，回答标注引用来源
- **结构化建议卡**：JSON mode 输出「动作 / 置信度 / 依据数据点」，前端渲染为可视化建议卡（含「AI 基于哪些数据得出结论」）
- **多模态**：图片识别商品并自动拉取历史价；语音输入转写提问
- **自建 MCP 工具**：stdio JSON-RPC 协议的网页行情 MCP Server，Agent 主动获取外部信息判断行情
- **AI 安全**：提示注入防御（用户输入隔离为数据）、敏感词过滤、输出价格事实核对兜底

## 技术架构

```
┌────────────────────────────── 前端 ──────────────────────────────┐
│ Vue 3 + TypeScript + Vite + Element Plus                         │
│ Pinia（状态）· Vue Router · ECharts（价格曲线）· GSAP（动效）      │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP / SSE 流式
┌──────────────────────────┴───────────────────────────────────────┐
│ 后端 FastAPI（Python）                                            │
│ ├─ routers: auth / products / tracking / compare / ai / admin     │
│ ├─ AI 层: Function Calling Agent · RAG 知识库 · 结构化建议卡       │
│ │        多模态识图/语音 · 注入防御与事实核对 · 用户画像 MD         │
│ ├─ MCP: 自建 stdio JSON-RPC 网页行情工具                          │
│ ├─ 采集: httpx + Playwright（多平台商品/历史价格抓取）             │
│ └─ APScheduler（定时采集 / 降价提醒）                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                    MySQL 8（SQLAlchemy）
```

**目录结构**

```
backend/                 FastAPI 后端
  app/routers/           接口路由（认证/商品/追踪/对比/AI/后台/站内信）
  app/services/          业务与 AI 服务（Agent 工具、RAG、MCP、识图、画像、采集器…）
  app/models.py          SQLAlchemy 数据模型
  tests/                 pytest 接口与模块测试
  scripts/               数据初始化、知识库导入、采集调试脚本
frontend/                Vue 3 + TS 前端
  src/views/             页面（首页/商品详情/追踪/对比/AI 导购/后台/个人中心…）
  src/components/        价格曲线图、AI 建议卡等组件
  src/api.ts             后端 API 封装
```

## 环境要求

- Python 3.11+
- Node.js 20+
- MySQL 8.0+

## 安装运行

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows；Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 配置环境变量（切勿提交真实密钥）
copy .env.example .env        # Windows；Linux/macOS: cp .env.example .env
# 编辑 .env，填入 MySQL 密钥与 LLM API Key

playwright install chromium   # 采集器依赖

# 建库（MySQL）：创建名为 spt 的数据库（编码 utf8mb4）
# 启动（首次启动自动建表并初始化默认管理员 / 数据源 / 系统配置）
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

可选初始化脚本：

```bash
python scripts/seed_data.py       # 导入演示商品数据
python scripts/seed_knowledge.py  # 导入 RAG 知识库
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173（/api 与 /uploads 代理到 8001）
```

### 3. 体验账号

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `admin123456` | 管理员 |
| 注册任意账号 | — | 普通用户 |

## 环境变量（backend/.env）

| 变量 | 说明 |
| --- | --- |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 连接配置 |
| `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` | 登录令牌配置 |
| `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` | 大模型 OpenAI 兼容接口配置 |
| `LLM_VISION_MODEL` | 多模态识图模型（可选） |

> 安全提示：所有密钥仅通过 `.env` 配置，`.env` 已被 `.gitignore` 排除，仓库只保留 `.env.example` 模板。

## 团队信息

- 参赛赛项：全国高校 AI Web 开发挑战赛（智启未来：AI 驱动的 Web 应用创新挑战）
- 学校：哈尔滨信息工程学院
- 组别：B 组
- 团队成员：陈泓宇（开发）、刘寅（文档）、刘生存（测试）
- 指导教师：李婷
