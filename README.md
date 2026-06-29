# AI Study Platform

AI Study Platform 是一个面向学习场景的全栈 AI 学习平台。项目采用 React + FastAPI 微服务架构，围绕课程、模块、材料、测验、论坛通知、AI 聊天、RAG 检索、学习画像和个性化学习支持构建。

该仓库已整理为个人项目版本，中文文档作为面试和讲解主入口，英文文档作为对应版本保留。

English version: [README.en.md](README.en.md)

## 项目亮点

- 微服务后端：`identity-service`、`learning-service`、`communication-service`、`ai-service` 分离职责。
- AI 能力：基于 Gemini、LangChain、pgvector 的 RAG 聊天、材料索引、测验生成和学习画像更新。
- 学习平台核心能力：注册登录、邮箱验证、角色权限、课程管理、模块材料、学习进度、测验、论坛和站内通知。
- 异步任务：Redis + Celery 支撑材料索引、通知、测验会话和 AI 后台流程。
- 可本地复现：Docker Compose 一键启动 MySQL、PostgreSQL、Redis、MinIO、nginx、前端和后端服务。
- 双语文档：中文用于面试表达，英文用于技术复盘和开源阅读。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React, Vite, TypeScript, Bootstrap |
| 后端 | FastAPI, SQLAlchemy, Pydantic |
| AI | Gemini API, LangChain, LangGraph, pgvector |
| 数据库 | MySQL, PostgreSQL |
| 异步任务 | Redis, Celery |
| 文件存储 | MinIO |
| 网关与部署 | nginx, Docker Compose, GitHub Actions |

## 快速启动

### 1. 准备环境

需要安装：

- Docker Desktop
- Docker Compose v2
- Node.js 20+（仅在本地直接运行前端时需要）
- Python 3.11+（仅在本地直接运行后端服务时需要）

检查命令：

```bash
docker --version
docker compose version
node --version
python --version
```

### 2. 创建环境变量文件

```bash
cp .env.example .env
```

Windows 可以使用：

```bash
copy .env.example .env
```

`.env` 只用于本地或部署环境，不能提交到 Git。真实密钥、SMTP 密码、Gemini API Key 和数据库密码都应只写入 `.env` 或部署平台的 secret。

本地 demo 默认管理员账号已经写在 `.env.example` 中，方便面试官试用后台：

```text
Email: admin@example.com
Password: DemoAdmin123!
```

该账号只用于本地管理后台登录；注册、邮箱验证、忘记密码和教师邀请等邮件流程，应使用真实收件邮箱配合 SMTP 测试。

### 3. 修改必要配置

`.env.example` 中标记 `# Have to Change` 的字段需要替换，例如：

```env
SMTP_USER=your_ses_smtp_username
SMTP_PASS=your_ses_smtp_password
SMTP_FROM=your_email@example.com
GEMINI_API_KEY=your_gemini_api_key
```

如果部署到公网环境，请同时修改默认管理员邮箱、密码和姓名。

如果本机端口冲突，可以修改 `.env` 中的外部端口，例如 `MYSQL_PORT`、`AI_DB_EXTERNAL_PORT`、`FRONTEND_PORT` 和 `NGINX_PORT`。

### 4. 启动完整系统

从仓库根目录运行：

```bash
docker compose --env-file .env -f infra/docker-compose.yml down -v --remove-orphans
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker-compose.yml ps
```

默认访问地址：

```text
http://localhost:8080
```

健康检查：

```bash
curl http://127.0.0.1:${NGINX_PORT}/api/health
curl http://127.0.0.1:${NGINX_PORT}/api/learning/health
curl http://127.0.0.1:${NGINX_PORT}/api/communication/health
curl http://127.0.0.1:${NGINX_PORT}/api/ai/health
```

## 项目结构

```text
.
├─ frontend/                       # React + Vite 前端
├─ services/
│  ├─ identity-service/            # 认证、用户、角色权限
│  ├─ learning-service/            # 课程、模块、材料、测验、学习进度
│  ├─ communication-service/       # 论坛、评论、站内通知
│  └─ ai-service/                  # AI 聊天、RAG、材料索引、学习画像
├─ packages/platform_common/       # 后端服务共享工具包
├─ database/                       # schema、迁移、初始化和示例数据
├─ infra/                          # Docker Compose 与 nginx
├─ scripts/                        # 测试、部署和运维脚本
├─ docs/                           # 双语项目文档
└─ .github/workflows/              # CI/CD workflow
```

## 文档入口

- [文档索引](docs/README.md)
- [项目需求](docs/project-requirements.md)
- [后续开发路线图](docs/roadmap.md)
- [系统架构](docs/architecture/README.md)
- [API 概览](docs/api/README.md)
- [部署与配置](docs/deployment/README.md)
- [测试指南](docs/testing/README.md)

## 面试讲解路线

建议按下面顺序介绍本项目，能同时覆盖业务价值、系统设计和个人后续开发计划：

1. **项目定位**：这是一个 AI 个性化学习平台，核心用户是学生、教师和管理员。
2. **业务闭环**：教师创建课程和模块，上传材料并发布；学生报名课程、学习材料、完成测验和论坛互动；系统通过通知和进度记录连接学习过程。
3. **AI 能力**：材料被索引到 PostgreSQL + pgvector，聊天和测验生成通过 RAG 检索课程上下文，再由 Gemini/LangChain 生成 grounded response。
4. **微服务架构**：identity、learning、communication、ai 四个 FastAPI 服务通过 nginx 统一暴露 API，内部使用 MySQL、PostgreSQL、Redis、MinIO 和 Celery。
5. **质量与部署**：Docker Compose 可以复现完整运行环境，GitHub Actions 覆盖前端构建、后端测试和基础设施检查。
6. **后续开发**：优先实现 AI Provider Adapter 和学生端 Study Planner，再扩展教师端 AI 测验草稿生成、短答题评估和教师端学习分析。

可重点展开的技术点：

- RAG 索引链路：文件解析、chunk、embedding、向量检索、prompt grounding。
- 学习画像更新：从测验和聊天信号中提取学习状态，用于反馈和推荐。
- 权限与网关：JWT + RBAC + nginx 路由隔离公共 API 和内部 API。
- 异步任务：Celery 处理材料索引、通知、AI workflow 和测验会话。

## 常用开发命令

后端测试：

```bash
./scripts/run-backend-tests.sh
```

后端覆盖率：

```bash
./scripts/backend-coverage.sh
```

前端：

```bash
cd frontend
npm ci
npm run lint
npm run build
```

Docker 配置校验：

```bash
docker compose --env-file .env.example -f infra/docker-compose.yml config
```

## 后续方向

当前个人项目版本会继续围绕以下能力演进：

- 教师端 AI 测验草稿生成与人工审核。
- AI Provider Adapter，支持 Gemini 之外的 OpenAI-compatible provider。
- 短答题等非选择题评估方式。
- 教师端学习分析 Dashboard。
- 学生端个性化 Study Planner。
- 更完整的 AI 输出安全层、来源引用和结构化校验。

详细计划见 [docs/roadmap.md](docs/roadmap.md)。
