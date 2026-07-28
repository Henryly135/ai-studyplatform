# AI 个性化学习平台

这是一个全栈 AI 学习平台，核心目标是把课程学习、教学管理、学习进度、论坛通知和 AI 辅助学习整合到一个统一系统中。

## 功能范围

- 学生：注册登录、加入课程、查看课程模块和资料、完成测验、查看学习进度、使用课程上下文 AI 助手、参与课程论坛。
- 教师：创建和管理课程、模块、资料、测验、课程发布、学生报名管理、查看教学数据和 AI 辅助信息。
- 管理员：管理用户、角色权限、课程治理和 AI 运行状态。
- 系统能力：JWT 鉴权、角色权限、文件上传、私有资料访问、RAG 检索、异步任务、服务健康检查、容器化部署。

## 技术栈

- 前端：React、Vite、TypeScript、React Router。
- 后端：FastAPI 微服务。
- 数据库：MySQL、PostgreSQL、pgvector。
- 异步与缓存：Redis、Celery。
- 文件存储：MinIO。
- 网关与部署：Nginx、Docker Compose。
- AI：Gemini、GLM、OpenRouter，多向量 RAG、测验生成、学习画像工作流。

## 环境要求

- Docker Desktop
- Docker Compose v2
- Node.js 20+
- Python 3.11+

检查命令：

```bash
docker --version
docker compose version
node --version
python --version
```

## 环境变量

复制模板文件：

```bash
cp .env.example .env
```

Windows 可使用：

```powershell
copy .env.example .env
```

注意事项：

- 不要提交 `.env`。
- 真实密钥只放在本地 `.env` 或部署环境中。
- `.env.example` 只保留占位值。
- 生产环境需要使用 HTTPS 的 `PUBLIC_FRONTEND_URL`。

常用配置项：

```env
DEFAULT_ADMIN_EMAIL=your.project.email@gmail.com
DEFAULT_ADMIN_PASSWORD=your-system-admin-password
DEFAULT_ADMIN_FULL_NAME='System Admin'

AI_PROVIDER_KEY_ENCRYPTION_SECRET=replace-with-a-stable-random-secret-at-least-32-characters
AI_EMBEDDING_DIMENSION=1024

SMTP_HOST=email-smtp.ap-southeast-2.amazonaws.com
SMTP_PORT=587
SMTP_USER=your_smtp_username
SMTP_PASS=your_smtp_password
SMTP_FROM=your_verified_sender_email
SMTP_TLS=true
PUBLIC_FRONTEND_URL=https://your-learning-platform.example.com
```

数据库和端口配置请以 `.env.example` 为准。如果本机已经占用 `3306` 或 `5432`，可以在 `.env` 中调整外部映射端口。

## AI Provider 与模型选择

平台只提供 Gemini、GLM 和 OpenRouter 三类受控 Provider，不支持 DeepSeek。Provider Key 由管理员在管理界面录入并加密保存；不要把真实 Key 写入 `.env`、源代码或 GitHub Actions 日志。

普通用户在课程聊天中只选择聊天模型。每个聊天模型在模型目录中配有一个固定的 1024 维向量模型：

| 聊天 Provider | 对应向量模型 |
| --- | --- |
| Gemini | Gemini Embedding 2 |
| GLM | GLM Embedding-3 |
| OpenRouter | OpenAI Text Embedding 3 Small via OpenRouter |

前端会展示配对的向量模型和课程索引状态，但向量模型由后端派生，浏览器不能单独覆盖。同一知识块可保存三套独立向量，因此切换聊天模型时无需临时重建资料，也不会混用不同模型的向量空间。

管理员配置顺序：

1. 登录管理员工作区。
2. 为要使用的 Provider 保存 API Key。
3. 分别执行健康检查。
4. 设置平台默认聊天模型。
5. 等待演示课程在对应向量模型下的索引覆盖率达到 100%。

详细调用逻辑见 [`docs/architecture/智能服务架构.md`](docs/architecture/智能服务架构.md)。

## 本地启动

在项目根目录执行：

```bash
docker compose --env-file .env -f infra/docker-compose.yml down -v --remove-orphans
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker-compose.yml ps
```

默认访问地址：

```text
http://localhost:8080
```

如果端口配置被修改，请以 `infra/docker-compose.yml` 和 `.env` 中的映射为准。

## 服务组成

Docker Compose 本地环境包含：

- `frontend`：React 前端。
- `nginx`：统一网关。
- `identity-service`：用户、认证、角色和权限服务。
- `learning-service`：课程、模块、资料、测验和学习进度服务。
- `communication-service`：论坛和通知服务。
- `ai-service`：AI 对话、RAG、资料索引和 AI 工作流服务。
- `communication-worker`：通知异步任务。
- `learning-worker`：测验和学习相关异步任务。
- `ai-worker`：资料索引和 AI 异步任务。
- `mysql`：身份、学习和通信数据。
- `postgres-ai`：AI 数据和向量检索。
- `redis`：Celery broker 和结果存储。
- `redis-quiz`：测验会话状态。
- `minio`：学习资料对象存储。

## 项目结构

```text
repo/
├─ frontend/                       # React + Vite + TypeScript 前端
├─ services/
│  ├─ identity-service/            # 身份认证服务
│  ├─ communication-service/       # 论坛和通知服务
│  ├─ learning-service/            # 课程、模块、资料和测验服务
│  └─ ai-service/                  # AI 对话、RAG 和索引服务
├─ packages/
│  └─ platform_common/             # Python 服务共享包
├─ database/
│  ├─ schema.*.sql                 # MySQL 初始化 schema
│  ├─ ai-init/                     # PostgreSQL / pgvector 初始化脚本
│  ├─ migrations/                  # 增量迁移
│  ├─ mysql-apply/                 # MySQL 初始化辅助脚本
│  └─ seed/                        # 本地示例数据
├─ infra/
│  ├─ docker-compose.yml           # 本地容器编排
│  └─ nginx/                       # 网关配置
├─ storage/
│  └─ learning-materials/          # 本地资料挂载目录
├─ scripts/                        # 运维和测试脚本
├─ docs/                           # API、架构、运维和图表文档
│  ├─ api/
│  ├─ architecture/
│  ├─ operations/
│  └─ diagrams/
├─ .env.example
└─ README.md
```

## 数据库初始化

首次启动时，MySQL schema 由 `mysql-schema-apply` 应用：

- `database/schema.identity.sql`
- `database/schema.communication.sql`
- `database/schema.learning.sql`

PostgreSQL 和 pgvector 初始化由 `postgres-schema-apply` 应用：

- `database/ai-init/`

如果需要重建本地数据卷：

```bash
docker compose --env-file .env -f infra/docker-compose.yml down -v
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

## 测试与检查

前端：

```bash
cd frontend
npm ci
npm run lint
npm test -- --run
npm run build
```

后端：

```bash
./scripts/run-backend-tests.sh
```

Docker Compose 配置检查：

```bash
docker compose --env-file .env -f infra/docker-compose.yml config --quiet
```

对外演示前请按 [`docs/operations/Demo演示指南.md`](docs/operations/Demo演示指南.md) 完成三 Provider 模型切换和索引预检。
旧环境升级或新增 Provider 凭据时，先按 [`docs/operations/多向量迁移与回填.md`](docs/operations/多向量迁移与回填.md) 完成回填门禁。

## 文档

- `docs/api/`：各服务 API 说明。
- `docs/architecture/`：架构和服务边界说明。
- `docs/operations/`：CI/CD、后端运行和测试说明。
- `docs/diagrams/`：系统图、ER 图和工作流图。

## 安全说明

- `.env`、真实密钥、访问令牌、验证码和私有凭证不得提交到 Git。
- 生产环境必须配置强 JWT 密钥、内部服务密钥、数据库密码和 HTTPS 前端地址。
- 学习资料通过私有 MinIO bucket 和后端授权接口访问。
- 后端权限校验是安全边界，前端隐藏入口只作为用户体验优化。
