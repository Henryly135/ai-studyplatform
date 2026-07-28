# 续作交接：多供应商与多向量收尾

更新时间：2026-07-28

工作分支：`agent/multi-provider-vector-handoff`

基线分支：`develop`

Draft PR：`https://github.com/Henryly135/ai-studyplatform/pull/26`

> 临时文件：接手者完成 `CONTINUATION_PLAN.md` 的全部验收项后，必须自动执行
> `git rm CONTINUATION_HANDOFF.md CONTINUATION_PLAN.md`，将删除包含在最终提交并推送；
> 不需要等待用户再次提醒。

## 1. 本次目标与当前结论

目标是把 AI 能力收敛为 Gemini、GLM、OpenRouter 三个 Provider，移除 DeepSeek 的运行时适配与前端选项；用户切换聊天模型时，由后端目录自动选择对应向量模型，不允许前端或业务流程硬编码向量模型。

主体代码已完成，当前单元、组件、真实 PostgreSQL/pgvector 并发测试和隔离 Compose 启动均已通过。尚未完成的是依赖真实 Gemini、GLM、OpenRouter Key 的 contract smoke、三套真实向量回填与完整 Demo 验收，以及本次新增 PostgreSQL CI 测试推送后的远端检查，因此本分支应继续保持 Draft，暂不要合并到 `develop`。

## 2. 已完成的实现

### Provider 与模型配对

| 聊天 Provider | 聊天模型 | 自动配对的 Embedding | 维度 |
| --- | --- | --- | ---: |
| Gemini | Gemini 2.5 Flash Lite / Flash / Pro | `gemini:gemini-embedding-001` | 1024 |
| GLM | GLM 4.5 Air / GLM 4.7 | `glm:embedding-3` | 1024 |
| OpenRouter | OpenRouter Auto / Gemini 2.5 Flash via OpenRouter | `openrouter:openai/text-embedding-3-small` | 1024 |

- 运行时白名单只包含 `gemini`、`glm`、`openrouter`。
- DeepSeek 只在数据库清理 SQL 中出现，用于移除旧目录、凭据和默认配置，不再是可选 Provider。
- Provider Key 只从管理员加密凭据存储读取，不再从环境变量兜底。
- GLM 与 OpenRouter 走统一的 OpenAI-compatible adapter；Gemini 保留原生 adapter。
- OpenRouter 已处理 HTTP 200 但响应体携带 `error` 的失败契约，并启用 `require_parameters`。
- Embedding 配额错误映射为 HTTP 429；凭据、配置和 Provider 运行错误映射为 HTTP 503。

核心目录定义在：

- `services/ai-service/app/services/providers/model_registry.py`
- `services/ai-service/app/services/providers/model_service.py`
- `services/ai-service/app/services/providers/adapters.py`
- `services/ai-service/app/services/indexing/embedding_service.py`

### 用户选模与调用链

当前课程聊天调用链如下：

1. 前端按课程和模块请求 `/api/ai/models?courseUuid=...&moduleUuid=...`。
2. 页面自动选中模型时也会保存并显式发送 `modelId`，不再要求用户手动触碰下拉框。
3. 后端从受控模型目录解析聊天模型及其 `paired_embedding_model_id`。
4. readiness 服务检查该课程在这一精确 Embedding 模型与版本下的覆盖状态。
5. 仅在覆盖就绪时，以同一模型 ID 和版本执行向量检索，再调用所选聊天模型。
6. 真正没有课程资料时，课程聊天可明确退化为普通聊天；索引中、部分覆盖、失败或未索引状态返回可识别错误，不伪装成 RAG 成功。

AI 测验不继承某个学生的前端选择，而是在一次生成任务开始时固定管理员默认聊天模型及其配对 Embedding，整个任务使用同一组合。

相关入口：

- `frontend/src/pages/Course/CourseChatSidebar.tsx`
- `frontend/src/pages/Course/courseChatModels.ts`
- `services/ai-service/app/api/ai_models.py`
- `services/ai-service/app/services/retrieval_readiness_service.py`
- `services/ai-service/app/services/chat/rag_retrieval_service.py`
- `services/ai-service/app/services/orchestration/langgraph/quiz_generation_graph.py`

### 多向量索引

- canonical chunk 与 Provider 向量分离。
- `ai_knowledge_chunk_embeddings` 按 chunk 与 Embedding 模型保存独立 1024 维向量。
- `ai_knowledge_source_embedding_statuses` 保存每份资料、每个 Embedding 模型的覆盖与失败状态。
- 检索按精确 `embedding_model_id` 和 `embedding_version` 隔离，避免混用不同向量空间。
- 新增 Provider 凭据并启用后，会自动为历史资料排队回填。
- 回填与上传任务按 material advisory lock 串行化；worker 最终写入前再次获取物料级写栅栏，并确认任务仍为 `RUNNING` 且没有更新任务。
- 删除资料索引也获取同一物料锁，避免旧 worker 在删除后重新写回。

迁移及关键实现：

- `database/ai-init/011_ai_model_provider_settings.sql`
- `database/ai-init/012_ai_multi_embedding.sql`
- `services/ai-service/app/tasks/material_index.py`
- `services/ai-service/app/services/indexing/index_job_service.py`
- `services/ai-service/app/repositories/ai_knowledge_chunks_repository.py`
- `services/ai-service/app/repositories/ai_knowledge_source_embedding_statuses_repository.py`

## 3. 已完成验证

本分支最新代码已执行：

- AI 服务全量：`263 passed`，另有 1 个 Starlette/httpx 弃用警告。
- AI 服务接入真实 PostgreSQL DSN 后：`267 passed`，其中新增 4 个 material advisory lock、回填、删除和 broker 重发并发集成测试。
- 最终写栅栏、删除锁和 Embedding 错误分类聚焦回归：`44 passed`。
- 前一轮同一工作树验证：learning-service 71、identity-service 72、communication-service 19、platform_common 27，全部通过。
- 前端当前验证：74 项测试与生产构建通过；lint 为 0 error、37 warnings。
- `npm run audit:ci` 当前通过。React Router 的临时精确豁免截止 2026-09-30，届时必须升级或重新评估，不能扩大豁免范围。
- Compose 配置解析与 `git diff --check` 当前通过；Python compileall、CI YAML、SQL 静态解析、Bash/PowerShell 预检脚本语法在前一轮通过。
- 全新 1024 维 pgvector 数据库、旧 1536 维单向量数据库升级、011/012 重跑幂等、约束负例和三模型覆盖统计已在隔离容器通过。
- 独立 Compose project 已完成全栈构建与启动：四个 API、MySQL、PostgreSQL、Redis、Redis Quiz、MinIO 健康，三个 worker 在线，nginx 六个入口均返回 HTTP 200；验证资源已单独清理，未触碰原有数据卷。
- 管理员浏览器登录与治理页只读验收通过：只显示 Gemini、GLM、OpenRouter，Gemini 配对向量为 1024 维，缺少 Key 时明确显示未配置状态，不显示 DeepSeek。

AI 服务本地复现命令：

```powershell
cd services/ai-service
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ..\..\packages\platform_common
.\.venv\Scripts\python.exe -m pytest -q
```

前端复现命令：

```powershell
cd frontend
npm ci
npm run lint
npm test
npm run build
npm run audit:ci
```

## 4. 下一台电脑必须完成的验收

按以下顺序继续，前三项是合并前门槛。

### A. 在真实 PostgreSQL/pgvector 上验证迁移与并发

本项的迁移、约束、幂等和并发数据库门槛已在隔离 pgvector 容器完成，并新增
`services/ai-service/tests/indexing/test_postgres_material_index_concurrency.py`。
无 Key 的合成回填覆盖统计已经通过；真实 Provider 产生的三套向量仍需在 B、C 项完成。

1. 在全新、可丢弃的数据卷上完整运行 `database/ai-init`。
2. 再在含旧单向量资料、旧 DeepSeek 配置的数据库副本上运行 011、012。
3. 验证旧 Provider 清理、默认模型修正、1024 维约束、外键和重复启动幂等性。
4. 增加或手工执行 PostgreSQL 并发场景：旧 worker 与新上传、全量回填、删除操作交错，确认旧任务不能覆盖或复活资料。

不要在含重要数据的环境运行 `docker compose down -v`；该命令只用于明确可丢弃的验收环境。

### B. 用真实 Key 做 Provider contract smoke test

Key 只在管理员页面录入，不写入 `.env`、测试、日志、截图或仓库。

对 Gemini、GLM、OpenRouter 分别验证：

1. 保存并启用凭据；
2. Provider 健康检查；
3. 一次聊天调用；
4. 一次 1024 维 Embedding；
5. 历史资料自动回填；
6. 同一课程切换模型后，响应中的聊天模型与配对向量模型和页面一致。

另外验证 GLM 的 `embedding-3` 返回维度、Gemini reduced dimension，以及 OpenRouter 的 quota、HTTP 非 2xx、HTTP 200 error-body 三类失败。

### C. 完整 Compose 与 Demo 验收

隔离 Compose 的构建、启动、服务健康、worker ping、nginx 路由和缺少预检参数时的
fail-closed 已完成。下面需要真实 Key、管理员 token 和演示课程的步骤仍未完成。

```powershell
Copy-Item .env.example .env
docker compose --env-file .env -f infra/docker-compose.yml config --quiet
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker-compose.yml ps
```

准备管理员 token 与演示课程后：

```powershell
$env:DEMO_ACCESS_TOKEN = "replace-with-admin-access-token"
$env:DEMO_COURSE_UUID = "replace-with-demo-course-uuid"
$env:DEMO_TRIGGER_BACKFILL = "true"
.\scripts\demo-preflight.ps1
```

预检必须达到三套模型组合健康、指定课程 100% 覆盖，再按 `docs/operations/Demo演示指南.md` 走一次课程问答、三 Provider 切换、AI 测验和管理员治理流程。

### D. 远端 CI 与依赖收口

- 检查本分支 Draft PR 的全部 GitHub Actions；本次已把 learning-service 与 AI 全量测试纳入 CI。
- 原提交 `0df0990` 的 13 项 PR 检查全部通过；新增真实 PostgreSQL CI 测试尚未提交和推送，推送后必须重新确认远端检查。
- 若 CI 失败，优先区分 Linux/Windows 换行差异、真实 Compose 启动、依赖安装与业务回归。
- 在 2026-09-30 前处理 React Router advisory，删除 `frontend/scripts/audit-policy.mjs` 中对应临时豁免。

## 5. 在另一台电脑恢复

```powershell
git clone git@github.com:Henryly135/ai-studyplatform.git
cd ai-studyplatform
git fetch origin
git switch --track origin/agent/multi-provider-vector-handoff
git status
```

若分支已在本地存在，则使用：

```powershell
git switch agent/multi-provider-vector-handoff
git pull --ff-only
```

然后从上面的 B 项真实 Provider contract smoke 开始，并复核 C 项的真实回填与 Demo。模型与回填说明见 `docs/operations/多向量迁移与回填.md`，演示流程见 `docs/operations/Demo演示指南.md`，CI 命令见 `docs/operations/持续集成与部署.md`。

## 6. 续作时的边界

- 不恢复 DeepSeek 运行时或 UI 选项。
- 不允许前端直接指定 Embedding 模型；只发送聊天 `modelId`，配对由后端目录决定。
- 不增加 Provider Key 环境变量兜底。
- 不把索引未就绪、部分覆盖或 Provider 失败描述为普通的“无资料”。
- 不在不同 `embedding_model_id` 或版本之间混合检索。
- 修改模型配对、Embedding 版本或维度时，必须同时考虑迁移、历史回填、readiness、检索过滤、Demo 预检与回滚策略。
