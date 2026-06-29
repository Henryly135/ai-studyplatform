# 后续开发路线图

本路线图面向个人项目继续开发和中文面试讲解，强调可以逐步落地、可以演示、可以测试的功能增量。

English version: [roadmap.en.md](roadmap.en.md)

## 阶段 0：基线稳定化

目标：确保项目可以从干净环境启动、测试和演示。

任务：

- 使用 `.env.example` 创建 `.env` 并完整启动 Docker Compose。
- 校验 nginx、前端、四个后端服务、MySQL、PostgreSQL、Redis 和 MinIO。
- 验证注册、登录、邮箱验证、密码重置、课程创建、模块发布、材料上传、测验作答、论坛通知、AI 聊天和 RAG。
- 修复已知问题：教师邮箱验证、学生文档预览、AI 聊天入口限制。
- 记录 bug、复现步骤、修复说明和回归结果。

验收：

- 干净 checkout 可以按照 README 启动。
- 健康检查全部通过。
- 修复内容有对应测试或明确回归记录。

## 阶段 1：GitHub CI/CD 测试门禁（已实现）

目标：先让 GitHub 自动跑完整测试，再进入新功能开发。

任务：

- 将 `.github/workflows/ci.yml` 作为唯一质量门禁。
- 覆盖前端 lint/build、`platform_common` 测试、Docker Compose config、完整后端 pytest 和 nginx gateway smoke test。
- 使用 `scripts/create-ci-env.sh` 生成安全 CI `.env`，不依赖真实 Gemini、SMTP 或生产密钥。
- 建立新功能测试约定：后端测试放入对应服务 `tests/` 目录，AI 测试使用 mock provider，前端测试命令统一接入 `frontend/package.json`。

验收：

- push 和 PR 会自动触发 CI。
- 四个后端服务都会执行完整 `pytest tests -q`。
- 后续新增测试文件能被 GitHub Actions 自动收集。
- 文档说明本地和 CI 测试入口。

## 阶段 2：AI Provider Adapter 与多模型支持（已实现）

目标：把当前 Gemini 绑定改造成可配置的 AI provider 层，支持以后接入 OpenAI、DeepSeek、Claude、OpenRouter 等模型供应商。

当前完成内容：

- 在 `ai-service` 中抽象 chat provider 接口，保留 Gemini 默认实现。
- 新增 OpenAI-compatible chat provider adapter，支持 DeepSeek、OpenRouter 和自定义兼容 base URL。
- 配置层接入 `AI_CHAT_PROVIDER`、`AI_CHAT_MODEL`、`AI_CHAT_BASE_URL`、`AI_CHAT_API_KEY`、`DEEPSEEK_API_KEY`，并兼容 `GEMINI_API_KEY`。
- AI 聊天、RAG fallback、测验生成、学习画像决策、Study Planner 和教师端 AI 内容草稿都复用 `get_chat_provider`。
- 统一 provider 错误分类，包括 timeout、quota/rate-limit、invalid key、transient network 和 unknown provider error。
- Embedding provider 保持独立配置，目前只支持 Gemini embedding；非 Gemini 配置会返回可解释错误，并提示新增 adapter 后重新索引材料。
- 为 chat provider factory、Gemini mock、DeepSeek/OpenAI-compatible mock、错误分类、embedding 维度校验和重新索引提示补充测试。

验收：

- 通过 `.env` 切换 Gemini 与至少一个 OpenAI-compatible chat provider。
- AI 聊天、RAG fallback、测验生成、学习画像决策、Study Planner 和教师端内容生成可通过统一 chat provider 调用。
- provider 错误能返回统一、可解释的错误信息。
- 文档说明 chat provider 配置方式、embedding 限制和重新索引要求。

后续增强项：

- 新增 OpenAI-compatible embedding adapter，并为不同 embedding provider 维护索引版本迁移。
- 接入 Claude 等非 OpenAI-compatible 专有 SDK。
- 增加 provider 成本统计、模型效果对比和可配置 failover。

## 阶段 3：教师端 AI 测验生成（已实现）

目标：教师可以从模块材料或提示词生成可编辑测验草稿。

当前完成内容：

- 在 `ai-service` 复用现有测验生成工作流，新增教师端内部生成接口。
- 支持难度、题型、题目数量、学习目标、材料范围和教师说明。
- 生成结果先返回预览，不直接写入题库；教师接受后才写入 `learning-service` 的 unpublished/draft 测验草稿。
- 支持替换或追加现有题库，并保留现有 quiz authoring/publish 流程。
- 每题保存 `sourceGrounding` 来源依据，并在前端预览中可见/可调整。
- 在课程管理测验页面增加题型选择、生成预览、接受、丢弃和重新生成流程。

验收：

- 教师可以生成测验草稿。
- 题目包含选项、答案、解释和来源依据。
- 未经教师确认不能发布给学生。

后续增强项：

- 支持更丰富的题型和 rubric。
- 引入服务端短期 draft preview 存储，支持跨设备恢复未接受预览。
- 为来源依据提供更细粒度 citation 链接到材料片段。

## 阶段 4：短答题评估（已实现）

目标：增加一种选择题之外的评估方式。

当前完成内容：

- 新增模块级短答题定义、rubric、学生提交、AI 建议反馈和教师复核数据结构。
- 教师可以在课程管理模块中创建/更新短答题评估，设置 draft/published/archived 状态。
- 学生可以读取已发布短答题、提交答案并查看 AI 建议反馈。
- `ai-service` 提供内部短答题评估接口，输出建议分数、反馈、strengths 和 improvements；当前实现为 mock-friendly 本地评估器。
- 教师可以查看提交并覆盖最终分数与反馈，最终反馈由教师 review 后发布给学生。

验收：

- 教师可以发布短答题。
- 学生可以提交答案。
- 教师可以复核 AI 建议。

后续增强项：

- 基于真实材料检索为短答反馈补充引用依据。
- 将短答题数据接入学习分析和学习画像。
- 支持多题短答作业、rubric 维度评分和批量复核。

## 阶段 5：教师端学习分析（已实现）

目标：把 Dashboard 从统计展示升级为教学决策工具。

当前完成内容：

- 已有教师课程报名汇总和 quiz 模块统计接口。
- 新增 `teaching-insights` 聚合接口，按当前教师拥有的课程统计模块卡点、风险学生、完成趋势和评估信号。
- 模块卡点基于报名数、started/completed 数、完成率和平均进度生成 low completion、no activity 等信号。
- 风险学生基于低进度、久未访问和未完成模块较多生成风险原因。
- 评估信号结合 quiz 低通过率/低均分，以及短答题 AI/最终平均分和待复核数量。
- 前端 Analytics 页面展示课程概览、quiz performance、风险学生、模块瓶颈、评估信号和完成趋势。
- 聚合仅使用 `learning-service` 现有报名、模块进度、quiz attempt 和短答题提交表，不调用 AI。

验收：

- 教师可以识别需要帮助的学生和高风险模块。
- Dashboard 数据与后端聚合结果一致。

后续增强项：

- 增加课程、模块、时间范围和学习者状态筛选。
- 接入更细粒度的薄弱题目、rubric 维度和学习画像掌握度。
- 增加趋势图表、导出和主动提醒。

## 阶段 6：教师端 AI 内容生成（已实现）

目标：帮助教师快速生成教学材料草稿。

当前完成内容：

- 教师可以在模块详情页生成 AI 内容草稿，支持摘要、学习目标、活动建议、分层解释和课件大纲。
- `learning-service` 持久化草稿标题、教师提示、材料范围、结构化内容、来源依据、置信度和 provider/fallback 元数据。
- `ai-service` 提供内部内容生成接口，优先调用当前 `AI_CHAT_*` provider adapter；provider 缺失、quota/timeout、非法 JSON 或低置信度时返回 deterministic fallback 草稿。
- 草稿只存在于教师管理侧，不自动发布给学生，也不自动覆盖模块正文。
- 前端支持选择已保存草稿、编辑结构化内容和 source grounding、保存修改，并可手动复制到模块内容编辑器。
- 新增数据库 migration、后端 mock provider/fallback 测试、权限和保存逻辑测试。

验收：

- 教师可以从材料生成内容草稿。
- 生成结果可以编辑和保存。

后续增强项：

- 接入更细粒度的材料 chunk citation，而不只是材料标题/摘要。
- 支持版本历史、草稿归档和一键应用到模块正文的确认流程。
- 为不同内容类型提供更专门的前端编辑器，而不是通用结构化文本编辑。

## 阶段 7：学生端 Study Planner（已实现）

目标：让学生输入目标、材料摘要、偏好和可用时间，并获得个性化学习计划。

当前完成内容：

- 新增独立 Study Planner 页面。
- 支持学习目标、目标日期、偏好、每周可用时间和材料摘要输入。
- `learning-service` 保存计划元数据、原始输入、生成内容、状态和调整备注。
- `ai-service` 通过内部接口生成阶段计划、主题顺序、复习节奏和理由，并提供 provider 失败 fallback。
- 学生可以查看、调整、归档/恢复和重新生成自己的计划。
- 已覆盖学生权限、输入校验、provider mock 成功路径、provider 失败 fallback、计划保存读取和前端 lint/build。

后续增强项：

- 支持真实材料上传与材料内容抽取，而不只是材料摘要。
- 与 AI 聊天、推荐和学习画像联动。
- 增加更细粒度的来源引用、学习进度同步和日历视图。

验收：

- 学生可以生成一份可读、可调整的学习计划。
- 计划能引用学生输入和材料摘要。

## 长期方向

- 更强的 AI 来源引用与结构化输出验证。
- 可插拔 AI provider、成本控制和模型效果评估。
- 更多评估形式，例如 concept map、peer review、mini project。
- 更细粒度的画像更新和推荐解释。
- 生产部署监控、日志分析和自动恢复。
