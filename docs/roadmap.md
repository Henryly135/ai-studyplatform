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

## 阶段 1：GitHub CI/CD 测试门禁

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

## 阶段 2：AI Provider Adapter 与多模型支持

目标：把当前 Gemini 绑定改造成可配置的 AI provider 层，支持以后接入 OpenAI、DeepSeek、Claude、OpenRouter 等模型供应商。

实现方向：

- 在 `ai-service` 中抽象 chat、embedding、结构化生成和错误处理接口，保留 Gemini 作为默认实现。
- 增加 provider 配置，例如 `AI_CHAT_PROVIDER`、`AI_EMBEDDING_PROVIDER`、模型名、base URL 和对应 API key；兼容现有 `GEMINI_API_KEY`。
- 配置层已预留 `AI_CHAT_*`、`DEEPSEEK_API_KEY` 和 `AI_EMBEDDING_API_KEY` 入口；业务调用链接入仍属于后续 adapter 工作。
- 优先支持 OpenAI-compatible API，用于接入 DeepSeek、OpenRouter 和其他兼容服务；再按需扩展 Claude 等专有 SDK。
- 统一 token usage、quota/rate-limit、timeout、重试、日志和 prompt 记录字段。
- 为 embedding provider 切换增加向量维度校验、索引版本标记和重新索引提示，避免新旧 embedding 混用。
- 为聊天、RAG、测验生成、学习画像更新和材料索引增加 provider mock 测试。

验收：

- 通过 `.env` 切换 Gemini 与至少一个 OpenAI-compatible provider。
- AI 聊天、RAG、测验生成和材料 embedding 能在新 provider 下跑通。
- provider 错误能返回统一、可解释的错误信息。
- 文档说明不同 provider 的配置方式、限制和重新索引要求。

## 阶段 3：教师端 AI 测验生成

目标：教师可以从模块材料或提示词生成可编辑测验草稿。

实现方向：

- 在 `ai-service` 复用现有测验生成工作流，新增教师端生成 run。
- 支持难度、题型、题目数量、学习目标、材料范围和教师说明。
- 将生成结果写入 `learning-service` 的测验草稿，而不是直接发布。
- 在课程管理测验页面增加生成、预览、编辑、接受、丢弃和重新生成流程。

验收：

- 教师可以生成测验草稿。
- 题目包含选项、答案、解释和来源依据。
- 未经教师确认不能发布给学生。

## 阶段 4：短答题评估

目标：增加一种选择题之外的评估方式。

实现方向：

- 新增短答题定义、rubric、学生提交、AI 反馈和教师复核数据结构。
- 学生提交短答文本后，AI 基于 rubric 和材料上下文给出建议分数与反馈。
- 教师可以查看提交、调整反馈并确认最终结果。
- 后续将短答题数据接入学习分析。

验收：

- 教师可以发布短答题。
- 学生可以提交答案。
- 教师可以复核 AI 建议。

## 阶段 5：教师端学习分析

目标：把 Dashboard 从统计展示升级为教学决策工具。

实现方向：

- 增加课程、模块、测验、短答题、活跃度和学习画像维度。
- 展示模块卡点、薄弱题目、学习者风险、完成趋势和掌握度。
- 支持课程、模块、时间范围和学习者状态筛选。
- 保持 educator/admin 权限边界。

验收：

- 教师可以识别需要帮助的学生和高风险模块。
- Dashboard 数据与后端聚合结果一致。

## 阶段 6：教师端 AI 内容生成

目标：帮助教师快速生成教学材料草稿。

实现方向：

- 支持摘要、学习目标、活动建议、分层解释和课件大纲。
- 结果包含结构化字段和材料来源。
- 对 AI 低置信度结果提供 fallback 和人工编辑入口。

验收：

- 教师可以从材料生成内容草稿。
- 生成结果可以编辑和保存。

## 阶段 7：学生端 Study Planner

目标：让学生上传个人材料并获得个性化学习计划。

实现方向：

- 新增独立 Study Planner 页面。
- 支持材料上传、目标、需求、偏好和可用时间输入。
- AI 生成学习工作流、阶段计划、主题顺序和理由。
- 后续与聊天、推荐和学习画像联动。

验收：

- 学生可以生成一份可读、可调整的学习计划。
- 计划能引用学生输入和上传材料。

## 长期方向

- 更强的 AI 来源引用与结构化输出验证。
- 可插拔 AI provider、成本控制和模型效果评估。
- 更多评估形式，例如 concept map、peer review、mini project。
- 更细粒度的画像更新和推荐解释。
- 生产部署监控、日志分析和自动恢复。
