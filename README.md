# Everyone Agent

> 一个本地运行的全能 AI Agent，支持 25 个工具、三层记忆、技能自进化和多 Agent 协作。

## 特性一览

| 特性 | 说明 |
|------|------|
| **ReAct Agent 循环** | 思考→行动→观察，最多 10 轮工具调用 |
| **25 个内置工具** | 文件系统、命令执行、代码编辑、搜索、Git、Python REPL、记忆、技能、多 Agent 委派 |
| **多 Agent 协作** | 主 Agent 可委派子任务：Single / Parallel（3 并发） / Chain（流水线） |
| **三层记忆系统** | SOUL.md（人格）+ USER.md（用户画像）+ Session Memory（会话笔记） |
| **技能自进化** | Agent 将复杂工作流沉淀为可复用的结构化 Skill（YAML frontmatter） |
| **树形会话管理** | 类 Git 分支结构，支持分支创建与回溯 |
| **分级上下文压缩** | Tier1 摘要归档 + Tier2 近期保留，长对话 Token 降低 ~76% |
| **流式输出** | SSE 实时推送，逐字显示 AI 回复和工具调用过程 |

## 架构

```
┌──────────────┐      HTTP/SSE       ┌──────────────────────────────────────┐
│  React 前端   │  ◄──────────────►  │          FastAPI Backend              │
│  (Vite + TW)  │                    │                                      │
└──────────────┘                    │  Agent Loop (ReAct) ──► LLM API      │
                                    │       │                               │
                                    │  Tool Registry (25 tools)             │
                                    │       │                               │
                                    │  Multi-Agent Service                  │
                                    │  ┌──────────┐┌──────┐┌────────┐      │
                                    │  │Researcher││Coder ││Reviewer│ ...  │
                                    │  └──────────┘└──────┘└────────┘      │
                                    └──────────────────────────────────────┘
```

## 快速开始

### 环境要求

- **Python** 3.10+
- **Node.js** 18+
- **LLM API Key**：支持 OpenAI / DeepSeek 等兼容接口
- **Tavily API Key**（可选，用于联网搜索，[免费申请](https://tavily.com)）

### 1. 克隆项目

```bash
git clone https://github.com/your-username/everyone_agent.git
cd everyone_agent
```

### 2. 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `backend/.env`，填入你的 API Key：

```env
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://api.deepseek.com   # 或其他兼容 OpenAI 的地址
LLM_MODEL=deepseek-chat
TAVILY_API_KEY=tvly-your-key-here        # 可选，不填则搜索不可用
```

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt
python main.py
```

看到以下输出说明后端启动成功：

```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. 启动前端（新开一个终端）

```bash
cd frontend
npm install
npm run dev
```

看到以下输出说明前端启动成功：

```
  VITE v5.x.x  ready in xxx ms
  ➜  Local:   http://localhost:5173/
```

### 5. 开始使用

浏览器打开 **http://localhost:5173** ，即可与 Agent 对话。

## 工具系统（25 个）

### 文件操作（5 个）

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件内容 |
| `write_file` | 写入文件 |
| `edit_file` | 精确查找替换编辑 |
| `list_directory` | 列出目录结构 |
| `grep` | 正则搜索文件内容 |

### 执行（2 个）

| 工具 | 功能 |
|------|------|
| `run_command` | Shell 命令执行（30s 超时） |
| `python_eval` | Python REPL（独立子进程，30s 超时） |

### 网络（2 个）

| 工具 | 功能 |
|------|------|
| `web_search` | Tavily 联网搜索 |
| `read_url` | 读取 URL 内容 |

### Git（4 个）

| 工具 | 功能 |
|------|------|
| `git_status` | 工作区状态 |
| `git_diff` | 查看变更 |
| `git_commit` | 暂存 + 提交 |
| `git_log` | 提交历史 |

### 记忆（3 个）

| 工具 | 功能 |
|------|------|
| `read_memory` | 读取指定记忆层 |
| `update_memory` | 写入会话记忆 |
| `update_user_profile` | 更新用户画像 |

### 技能（5 个）

| 工具 | 功能 |
|------|------|
| `list_skills` / `read_skill` | 列出 / 读取技能 |
| `create_skill` / `update_skill` / `delete_skill` | 创建 / 更新 / 删除技能 |

### 多 Agent 协作（4 个）

| 工具 | 模式 | 功能 |
|------|------|------|
| `list_agents` | — | 列出可用子 Agent 角色 |
| `delegate_task` | Single | 委派单个子任务 |
| `delegate_parallel` | Parallel | 多个子 Agent 同时执行（最多 3 并发） |
| `delegate_chain` | Chain | 流水线：A 输出 → B 输入 → C 输入 |

### 扩展工具

新增工具只需 3 步：
1. 在 `backend/tools/` 创建新文件，继承 `BaseTool`
2. 实现 `name`、`description`、`parameters` 和 `execute()` 方法
3. 在 `backend/tools/__init__.py` 中注册

## 多 Agent 协作

主 Agent 可以将子任务委派给专门的子 Agent，每个子 Agent 有独立的上下文和工具权限。

### 内置角色

| 角色 | 可用工具 | 职责 |
|------|---------|------|
| **researcher** | `web_search`, `read_url` | 信息检索，返回事实摘要 |
| **coder** | `read_file`, `write_file`, `edit_file`, `list_directory`, `grep`, `run_command`, `python_eval` | 编写 / 修改 / 调试代码 |
| **reviewer** | `read_file`, `list_directory`, `grep` | 代码审查，输出问题报告 |

### 自定义角色

在 `backend/data/agents/` 放一个 YAML 文件即可，无需改代码：

```yaml
name: translator
description: 专业翻译助手
system_prompt: |
  你是一个专业翻译...
tools:
  - web_search
  - read_url
max_rounds: 4
```

## 记忆系统

| 层级 | 文件 | 维护者 | 作用 |
|------|------|--------|------|
| **SOUL.md** | `data/memories/SOUL.md` | 用户手动 | Agent 人格与固定规则（只读） |
| **USER.md** | `data/memories/USER.md` | Agent | 用户画像、偏好，跨会话共享 |
| **Session Memory** | `data/sessions/{id}_memory.md` | Agent | 当前会话的工作笔记 |

## 技能系统

Agent 可将复杂工作流沉淀为可复用的技能（SOP）。技能存放在 `backend/data/skills/`，支持两种格式：

```markdown
---
name: 技能名称
description: 一句话描述
---

## 触发条件
...

## 操作步骤
...
```

## 配置说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | 大模型 API 密钥 | （必填） |
| `LLM_BASE_URL` | API 基础地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 默认模型 | `gpt-3.5-turbo` |
| `MAX_CONTEXT_TOKENS` | 上下文窗口最大 token | `8000` |
| `NUDGE_INTERVAL` | 记忆反思间隔（轮数，0=关闭） | `5` |
| `SERVER_HOST` | 监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 监听端口 | `8000` |
| `TAVILY_API_KEY` | Tavily 搜索 API 密钥 | （选填） |

## License

MIT
