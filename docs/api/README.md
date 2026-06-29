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
- 短答题评估：教师 rubric、学生提交、AI 建议反馈和教师复核。
- 学生端 Study Planner 计划生成、读取、调整和重新生成。
- 教师端课程、测验和教学洞察分析。
- 教师端 AI 内容草稿生成、编辑和保存。

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

短答题评估：

- `PUT /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management`：教师 owner/admin 创建或更新模块短答题评估，包含标题、题干、rubric、满分和状态。
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management`：教师读取模块短答题评估。
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management/submissions`：教师查看学生提交、AI 建议分数和反馈。
- `PATCH /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management/submissions/{submissionUuid}/review`：教师复核并发布最终分数与反馈。
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer`：学生读取已发布短答题评估和自己的最近提交。
- `POST /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/submissions`：学生提交答案；`learning-service` 保存提交前调用内部 `ai-service` 获取建议分数、反馈、strengths 和 improvements。

短答题学生接口要求 learner 身份、课程报名和模块解锁；教师管理接口要求模块更新权限。AI 建议只作为草稿反馈，最终分数和可见反馈由教师复核接口确认。

教师端学习分析：

- `GET /api/learning/courses/me/analytics`：教师读取自己课程的报名汇总，包括课程数、总报名、活跃报名、完成报名和平均进度。
- `GET /api/learning/courses/me/analytics/quiz`：教师读取自己课程中各模块 quiz 的尝试数、唯一学生数、平均分、通过率和平均耗时。
- `GET /api/learning/courses/me/analytics/teaching-insights`：教师读取教学洞察聚合，只统计当前教师拥有的课程。响应包含 `moduleBottlenecks`（模块 enrolled/started/completed/completionRate/avgProgressPercent 和卡点信号）、`atRiskLearners`（低进度、久未访问、未完成模块较多的学生）、`completionTrends`（按日期聚合的模块完成数）和 `assessmentSignals`（quiz 低通过率/低均分，以及短答题 AI/最终均分和待复核数量）。

以上学习分析接口仅限具备教师课程管理权限的用户使用；聚合由 `learning-service` 基于课程报名、模块进度、quiz attempt 和短答题提交表计算，不调用 `ai-service`。

教师端 AI 内容草稿：

- `POST /api/learning/courses/{courseUuid}/modules/{moduleUuid}/content-drafts/management/generate`：教师 owner/admin 为模块生成并保存一个可编辑内容草稿。支持 `summary`、`learning_objectives`、`activity_suggestions`、`differentiated_explanation` 和 `slide_outline`。请求可包含草稿标题、教师提示和材料范围；`learning-service` 传入模块内容和材料摘要，调用内部 `ai-service`。
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/content-drafts/management`：教师读取模块下已保存的内容草稿。
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/content-drafts/management/{draftUuid}`：教师读取单个内容草稿。
- `PATCH /api/learning/courses/{courseUuid}/modules/{moduleUuid}/content-drafts/management/{draftUuid}`：教师保存编辑后的结构化内容和 `grounding` 来源依据。

内容草稿仅保存在教师管理侧，不会自动发布给学生，也不会自动覆盖模块正文。前端提供手动复制到模块内容编辑器的入口；是否保存为模块正文仍由教师显式执行。AI provider 缺失、quota/timeout、非法 JSON 或低置信度时，`ai-service` 返回可编辑 fallback 草稿并标记 `isFallback` 和 `fallbackReason`。

核心文件：

- `services/learning-service/app/api/course_management.py`
- `services/learning-service/app/api/course_catalog.py`
- `services/learning-service/app/api/module_management.py`
- `services/learning-service/app/api/module_content.py`
- `services/learning-service/app/api/content_generation.py`
- `services/learning-service/app/api/quiz.py`
- `services/learning-service/app/api/short_answer.py`
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
- 短答题评估内部接口，供 `learning-service` 获取建议分数和反馈。
- Study Planner 内部生成接口，供 `learning-service` 调用。
- 教师端 AI 内容草稿内部生成接口，供 `learning-service` 调用。
- Celery smoke task 和任务状态查询。

核心文件：

- `services/ai-service/app/api/chat.py`
- `services/ai-service/app/api/tasks.py`
- `services/ai-service/app/api/internal_index_jobs.py`
- `services/ai-service/app/api/internal_profile_update.py`
- `services/ai-service/app/api/internal_quiz_generation.py`
- `services/ai-service/app/api/internal_study_planner.py`
- `services/ai-service/app/api/internal_content_generation.py`
- `services/ai-service/app/api/profiles.py`

内部 AI 测验接口：

- `POST /api/ai/internal/quiz-generation/educator-draft`：内部接口，仅供 `learning-service` 通过 internal token 调用。返回候选题集合、检索上下文和计划，每题包含 `sourceGrounding`。nginx 不应向浏览器直接开放该接口。
- `POST /api/ai/internal/content-generation/educator-draft`：内部接口，仅供 `learning-service` 通过 internal token 调用。输入课程、模块、内容类型、教师提示和材料摘要，输出结构化内容草稿、来源依据、置信度和 provider/fallback 元数据。nginx 不应向浏览器直接开放该接口。
- `POST /api/ai/internal/short-answer/evaluate`：内部接口，仅供 `learning-service` 通过 internal token 调用。输入题干、rubric、满分和学生答案，输出建议分数、反馈、strengths 和 improvements；当前实现为 mock-friendly 的本地评估器，便于后续替换为 provider-backed 工作流。

## 鉴权约定

- 前端通过 JWT Bearer Token 调用后端。
- nginx 只暴露公共前缀，内部 API 由网关规则保护。
- 跨服务调用使用内部 HTTP client 和共享用户上下文。
- 权限常量集中在 `packages/platform_common/platform_common/permissions/`。

## 错误处理

- 服务通过统一错误模型返回结构化错误。
- 公共 API 优先返回清晰的业务错误信息。
- 内部 API 在调用失败时应保留上下文日志，避免向前端暴露敏感细节。
