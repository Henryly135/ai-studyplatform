# 系统架构

AI Study Platform 使用前后端分离和微服务架构。前端通过 nginx 访问统一 API，后端服务围绕身份、学习、沟通和 AI 四个领域拆分。

English version: [README.en.md](README.en.md)

## 架构总览

```text
Frontend -> nginx -> FastAPI services -> databases / queues / object storage / AI provider
```

核心服务：

- `identity-service`：认证、用户、角色、权限和教师审批。
- `learning-service`：课程、模块、材料、学习进度、报名、测验和分析。
- `communication-service`：论坛、评论和站内通知。
- `ai-service`：AI 聊天、RAG、材料索引、学习画像和 AI workflow。

## 数据层

| 数据 | 技术 | 说明 |
| --- | --- | --- |
| 身份、课程、论坛 | MySQL | 结构化业务数据 |
| AI、RAG、画像 | PostgreSQL + pgvector | 向量检索、AI 日志、画像资产 |
| 异步任务 | Redis | Celery broker/result backend |
| 测验会话 | Redis | 测验会话状态和锁 |
| 学习材料 | MinIO | S3-compatible 文件存储 |

## 异步任务

Celery worker 负责把耗时操作移出请求链路：

- 材料索引和 embedding 生成。
- 通知投递。
- 测验会话自动提交。
- AI workflow 后台任务。

## AI 工作流

AI 能力围绕三条主线：

- RAG：材料上传后被索引为 chunks 和 embeddings，聊天或测验生成时按课程/模块范围检索。
- Quiz Generation：加载测验上下文、检索材料、规划题目、生成候选题、结构校验并写回学习服务。
- Profile Update：从测验和聊天信号中提取学习状态，更新模块画像和后续推荐依据。

相关图表：

- [RAG 与材料索引工作流](../diagrams/rag-workflow.md)
- [学习画像更新工作流](../diagrams/profile-update-workflow.md)
- [AI 测验生成工作流](../diagrams/quiz-generation-workflow.md)

## 代码分层

后端服务遵循以下方向：

```text
api/controller -> service -> repository -> model
```

- `api/`：HTTP 输入输出、鉴权依赖、参数解析。
- `services/`：业务规则、跨 repository 协作、事务边界。
- `repositories/`：数据库查询和持久化。
- `models/`：SQLAlchemy 表映射和关系。
- `schemas/`：Pydantic 请求/响应模型。
- `core/`：配置、安全、时间、Celery、公共依赖。

## 面试讲解重点

- 为什么把 AI 独立成服务：AI workflow、向量库、任务队列和日志与普通课程业务解耦。
- 为什么需要 PostgreSQL + pgvector：课程材料检索和 RAG grounding 需要向量相似度查询。
- 为什么使用 Celery：embedding、文件解析、通知等任务不应阻塞 API 请求。
- 为什么通过 nginx 暴露统一 API：前端只需要一个网关入口，内部服务路径可以独立演进。
