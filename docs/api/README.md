# API 概览

本项目后端由四个 FastAPI 服务组成，统一通过 nginx 暴露给前端。公共 API 默认使用 camelCase 字段，AI 聊天相关历史接口仍保留部分 snake_case 字段。

English version: [README.en.md](README.en.md)

## 服务入口

| 服务 | nginx 前缀 | 代码目录 | 职责 |
| --- | --- | --- | --- |
| Identity | `/api` | `services/identity-service` | 注册、登录、邮箱验证、密码、用户、角色、权限 |
| Learning | `/api/learning` | `services/learning-service` | 课程、模块、材料、进度、报名、测验、分析 |
| Communication | `/api/communication` | `services/communication-service` | 论坛、评论、站内通知 |
| AI | `/api/ai` | `services/ai-service` | AI 聊天、RAG、材料索引、画像、AI 任务 |

## Identity API

主要能力：

- 注册、登录、刷新当前用户信息。
- 邮箱验证、重新发送验证邮件。
- 忘记密码、重置密码、修改密码。
- 查询当前用户权限。
- 管理员用户列表、状态更新、角色相关操作。
- 教师申请审批与教师邀请链接。
- 内部用户目录查询，供其他服务解析用户信息。

核心文件：

- `services/identity-service/app/api/auth.py`
- `services/identity-service/app/api/admin.py`
- `services/identity-service/app/api/internal.py`

## Learning API

主要能力：

- 课程创建、更新、发布、搜索和详情查询。
- 模块创建、排序、发布、先修关系和学习进度。
- 课程报名、退课、邀请链接。
- 材料上传、分片上传、删除和公开访问。
- 教师手动测验编辑、发布、学生作答。
- AI 生成测验的上下文查询、题目写入和教师端草稿预览/接受。
- 学生端 Study Planner 计划生成、读取、调整和重新生成。
- 教师端课程与测验分析。

学生端 Study Planner：

- `POST /api/learning/study-plans`：学生创建学习计划。请求包含学习目标、每周可用时间、目标日期、偏好和材料摘要；`learning-service` 保存计划元数据、输入和用户可见计划内容，并通过内部接口调用 `ai-service` 生成计划内容。
- `GET /api/learning/study-plans`：学生读取自己的学习计划列表。
- `GET /api/learning/study-plans/{planUuid}`：学生读取自己的单个学习计划；其他用户或非拥有者不可访问。
- `PATCH /api/learning/study-plans/{planUuid}`：学生调整自己的计划标题、状态、计划内容或备注。
- `POST /api/learning/study-plans/{planUuid}/regenerate`：学生基于原始输入重新生成计划内容。

以上接口仅限 learner 身份使用；`learning-service` 负责持久化，`ai-service` 只通过内部 `study-planner` 接口负责生成阶段计划、主题顺序、复习节奏和理由。

教师端 AI 测验草稿：

- `POST /api/learning/courses/{courseUuid}/modules/{moduleUuid}/quiz/management/ai-draft`：教师 owner/admin 从模块材料生成 AI 草稿预览。请求包含标题、题目数量、难度、题型、学习目标、材料范围和教师说明；`learning-service` 调用内部 `ai-service`，校验候选题数量、选项、正确答案和 `sourceGrounding`，但不写入题库。
- `POST /api/learning/courses/{courseUuid}/modules/{moduleUuid}/quiz/management/ai-draft/accept`：教师确认预览后写入既有 quiz authoring 草稿。可选择替换或追加题库；写入后保持 unpublished/draft，后续仍走现有编辑与 publish 流程。

以上接口仅限具备模块更新权限的教师 owner/admin 使用。`learning-service` 保存 quiz 元数据、题目、选项和每题来源依据；`ai-service` 只负责生成候选内容。

核心文件：

- `services/learning-service/app/api/course_management.py`
- `services/learning-service/app/api/course_catalog.py`
- `services/learning-service/app/api/module_management.py`
- `services/learning-service/app/api/module_content.py`
- `services/learning-service/app/api/quiz.py`
- `services/learning-service/app/api/internal_quiz_generation.py`
- `services/learning-service/app/api/study_planner.py`

## Communication API

主要能力：

- 课程论坛帖子创建、查询、更新和删除。
- 评论、回复、删除和帖子置顶。
- 系统通知创建。
- 用户通知列表、未读数、标记已读、隐藏和恢复。

核心文件：

- `services/communication-service/app/api/forum.py`
- `services/communication-service/app/api/notifications.py`
- `services/communication-service/app/api/internal_notifications.py`

## AI API

主要能力：

- AI 聊天和会话历史。
- RAG 检索课程材料并生成 grounded response。
- 材料索引任务注册、查询、重试和恢复。
- 学习画像初始化和模块画像更新。
- AI 测验生成 workflow。
- 教师端 AI 测验草稿内部生成接口，供 `learning-service` 调用。
- Study Planner 内部生成接口，供 `learning-service` 调用。
- Celery smoke task 和任务状态查询。

核心文件：

- `services/ai-service/app/api/chat.py`
- `services/ai-service/app/api/tasks.py`
- `services/ai-service/app/api/internal_index_jobs.py`
- `services/ai-service/app/api/internal_profile_update.py`
- `services/ai-service/app/api/internal_quiz_generation.py`
- `services/ai-service/app/api/internal_study_planner.py`
- `services/ai-service/app/api/profiles.py`

内部 AI 测验接口：

- `POST /api/ai/internal/quiz-generation/educator-draft`：内部接口，仅供 `learning-service` 通过 internal token 调用。返回候选题集合、检索上下文和计划，每题包含 `sourceGrounding`。nginx 不应向浏览器直接开放该接口。

## 鉴权约定

- 前端通过 JWT Bearer Token 调用后端。
- nginx 只暴露公共前缀，内部 API 由网关规则保护。
- 跨服务调用使用内部 HTTP client 和共享用户上下文。
- 权限常量集中在 `packages/platform_common/platform_common/permissions/`。

## 错误处理

- 服务通过统一错误模型返回结构化错误。
- 公共 API 优先返回清晰的业务错误信息。
- 内部 API 在调用失败时应保留上下文日志，避免向前端暴露敏感细节。
