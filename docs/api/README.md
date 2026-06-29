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
- AI 生成测验的上下文查询和题目写入。
- 教师端课程与测验分析。

核心文件：

- `services/learning-service/app/api/course_management.py`
- `services/learning-service/app/api/course_catalog.py`
- `services/learning-service/app/api/module_management.py`
- `services/learning-service/app/api/module_content.py`
- `services/learning-service/app/api/quiz.py`
- `services/learning-service/app/api/internal_quiz_generation.py`

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
- Celery smoke task 和任务状态查询。

核心文件：

- `services/ai-service/app/api/chat.py`
- `services/ai-service/app/api/tasks.py`
- `services/ai-service/app/api/internal_index_jobs.py`
- `services/ai-service/app/api/internal_profile_update.py`
- `services/ai-service/app/api/internal_quiz_generation.py`
- `services/ai-service/app/api/profiles.py`

## 鉴权约定

- 前端通过 JWT Bearer Token 调用后端。
- nginx 只暴露公共前缀，内部 API 由网关规则保护。
- 跨服务调用使用内部 HTTP client 和共享用户上下文。
- 权限常量集中在 `packages/platform_common/platform_common/permissions/`。

## 错误处理

- 服务通过统一错误模型返回结构化错误。
- 公共 API 优先返回清晰的业务错误信息。
- 内部 API 在调用失败时应保留上下文日志，避免向前端暴露敏感细节。
