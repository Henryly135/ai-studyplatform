# 最新收尾计划：Gemini、GLM、OpenRouter 与统一多向量

更新时间：2026-07-28

执行分支：`agent/multi-provider-vector-handoff`

目标分支：`develop`

Draft PR：`https://github.com/Henryly135/ai-studyplatform/pull/26`

详细上下文：`CONTINUATION_HANDOFF.md`

> 本文件和 `CONTINUATION_HANDOFF.md` 都是临时续作控制文件。只有下面所有合并门槛通过后，
> 执行代理才算完成任务；届时必须自动删除这两个文件，把删除纳入最终提交并推送，
> 不需要等待用户再次提醒。

## 一、最终范围

只支持以下三类 Provider：

- Gemini：聊天与 `gemini-embedding-001`。
- GLM：聊天与 `embedding-3`。
- OpenRouter：聊天与 `openai/text-embedding-3-small`。

明确不做：

- 不恢复 DeepSeek adapter、目录项、管理员配置或前端选项。
- 不允许 Provider Key 从环境变量回退。
- 不让用户直接选择 Embedding；用户只选择聊天模型，后端目录决定受控配对。
- 不把不同 Provider、模型或版本的向量放在同一检索空间使用。

## 二、目标调用逻辑

```text
前端选择 chat modelId
        |
        v
课程/模块权限校验
        |
        v
后端模型目录解析 chat -> paired embedding
        |
        +--> 凭据、Provider 与模型健康检查
        |
        v
按 embedding modelId + version 检查课程覆盖率
        |
        +--> 无资料：课程聊天可明确走普通聊天
        +--> 排队/部分/失败/未索引：返回可识别的未就绪错误
        |
        v
使用精确向量空间检索 -> 调用所选聊天模型 -> 返回实际模型组合
```

AI 测验使用任务启动时固定的管理员默认聊天模型及配对向量模型，不读取学生侧下拉框状态，也不允许任务中途切换组合。

## 三、实施阶段与当前状态

### P0：范围和数据模型收敛

- [x] Provider 运行时白名单收敛为 Gemini、GLM、OpenRouter。
- [x] DeepSeek 从前端、adapter、管理员可选项和默认配置中移除。
- [x] 数据库升级清理旧 DeepSeek 行和旧默认引用。
- [x] 所有向量模型统一为 1024 维。

### P1：统一模型目录与 Provider adapter

- [x] chat 模型通过 `paired_embedding_model_id` 声明配对。
- [x] Gemini、GLM、OpenRouter 的聊天和 Embedding 均走统一 invocation 边界。
- [x] GLM `embedding-3` 适配。
- [x] OpenRouter Embedding、`require_parameters` 和 HTTP 200 error-body 识别。
- [x] 移除 Gemini-only Embedding service。
- [x] API Key 只读管理员加密凭据。
- [x] quota 映射 429，配置与运行失败映射 503。

### P2：多向量存储、索引和回填

- [x] canonical chunk 与 Provider 向量分表。
- [x] 每个 chunk 可保存多套 `embedding_model_id + version` 向量。
- [x] 每份资料按向量模型记录 queued/running/success/failed 与覆盖数。
- [x] 检索按精确模型和版本过滤。
- [x] 启用新 Provider 凭据时自动排队历史回填。
- [x] 全量 reindex 支持任务复用、supersede 和失败重投。
- [x] material advisory lock 覆盖创建、回填、删除和最终写入。
- [x] worker 获取最终写栅栏后重新确认任务仍为 RUNNING 且没有更新任务。

### P3：RAG readiness 与业务语义

- [x] 课程聊天和 AI 测验共享 readiness 服务。
- [x] 真正无资料与索引未就绪分开处理。
- [x] 部分覆盖、失败、排队、版本不一致不会伪装成普通聊天。
- [x] AI 测验在一次运行内固定模型组合。
- [x] `/models` 按课程/模块做访问控制，避免泄漏覆盖信息。

### P4：前端模型选择

- [x] 自动选中的模型也会显式发送 `modelId`。
- [x] course、module、catalog、session 与 send 请求有异步 scope 隔离。
- [x] 页面展示实际聊天模型、配对向量模型与 readiness。
- [x] 前端无 DeepSeek 选项。

### P5：测试、CI、依赖与文档

- [x] Provider adapter 和 HTTP contract 测试。
- [x] 管理员模型 API 数据库集成测试。
- [x] 前端自动选模与异步竞态测试。
- [x] learning-service 和 AI 全量测试进入 CI。
- [x] npm audit 使用精确、限时、fail-closed 的临时策略。
- [x] 架构、API、多向量迁移、Demo 与预检文档更新。
- [x] 本地 AI 全量测试当前为 263 passed。

## 四、剩余工作：合并前门槛

以下任务应按顺序执行。若某项失败，修复后从受影响层重新验证，不要跳过。

### G1：真实 PostgreSQL/pgvector 迁移

- [x] 在全新可丢弃数据库完整执行 `database/ai-init/*.sql`。
- [x] 在包含旧单向量、Gemini 默认和 DeepSeek 配置的数据副本执行 011、012。
- [x] 确认旧配置清理、默认组合修正、1024 维约束、外键、唯一键正确。
- [x] 重启 schema apply，确认迁移脚本可重复执行。
- [ ] 验证历史资料回填后，三套向量的 chunk 数和 status 覆盖一致。（无 Key 合成数据的 2 chunks × 3 models 覆盖已通过；真实 Provider worker 回填并入 G3/G4。）

验收证据：保存不含 Key 和隐私数据的命令、行数统计与 schema 查询结果。

### G2：PostgreSQL 并发一致性

- [x] 旧索引 worker 运行时创建同一 material 的新上传任务，旧任务必须 superseded。
- [x] worker 最终提交前触发全量回填，新任务必须具有最终写入权。
- [x] worker 等待锁时删除 material，worker 恢复后不得重建 source/chunk/vector。
- [x] broker 首次 dispatch 失败后重新排队，不能形成永久 queued 孤儿任务。
- [x] 将以上场景至少补成一组真实 PostgreSQL 集成测试，不能只依赖 mock 调用顺序。

验收证据：`services/ai-service/tests/indexing/test_postgres_material_index_concurrency.py`
在真实 pgvector DSN 下 `4 passed`；AI 全量为 `267 passed`。CI 的
`ai-service-check` 已增加独立 pgvector service 和完整迁移步骤。

### G3：三 Provider 真实 contract smoke

- [ ] 管理员页面分别保存、启用并健康检查 Gemini、GLM、OpenRouter Key。
- [ ] 每个 Provider 各执行一次聊天和一次 1024 维 Embedding。
- [ ] 验证 Gemini reduced dimension 和 GLM `embedding-3`。
- [ ] 验证 OpenRouter 非 2xx、200 error-body、quota 三类错误。
- [ ] 确认错误码为预期的 429 或 503，响应与日志不泄漏 Key。
- [ ] 确认新 Provider 启用后会自动触发历史资料回填。

真实 Key 不得进入 `.env`、Git、终端录屏、截图或测试夹具。

### G4：Compose、前端与 Demo 端到端

- [x] `docker compose ... config --quiet` 通过。
- [x] 全栈 `up -d --build` 后服务和 worker 健康。
- [ ] 运行 `scripts/demo-preflight.ps1` 或 `.sh`，三套组合均健康且课程覆盖率为 100%。
- [ ] 不手动触碰下拉框，确认页面自动选择的模型就是实际请求模型。
- [ ] 按 Gemini -> GLM -> OpenRouter 切换，确认聊天与配对向量模型同步变化。
- [ ] 验证无资料、回填中、部分失败和 Provider 暂时不可用四种状态文案与 HTTP 语义。
- [ ] 使用已索引资料生成 AI 测验并发布一份草稿。

### G5：完整回归与远端 CI

- [x] platform_common、identity、communication、learning、AI 全量测试通过。
- [x] 前端 lint、test、build、`audit:ci` 全部通过。
- [x] GitHub Actions 所有必需检查通过。
- [x] `git diff --check`、Compose config、脚本语法和敏感信息扫描通过。
- [x] 处理审查新发现的 blocker/high-risk；中低风险记录到正式 issue 或文档。

包含新增 PostgreSQL 测试与 CI 配置的提交 `1dd6bbd` 已通过 GitHub Actions run
`30333176428`，13 项 PR 检查全部成功。

## 五、完成判定

只有同时满足以下条件，才可以把 Draft 转为 Ready 或合并：

1. G1 至 G5 全部勾选并留有可复核证据。
2. 三 Provider 均完成真实聊天、Embedding、回填和课程检索。
3. 不存在 DeepSeek 可执行路径或 UI 选项。
4. 模型配对只由后端目录产生，所有检索精确隔离模型与版本。
5. 索引并发场景在真实 PostgreSQL 上验证通过。
6. 远端 CI 通过，且无未解释的 blocker/high-risk。

## 六、强制自动清理

达到“完成判定”后，执行代理必须直接运行：

```powershell
git rm -- CONTINUATION_HANDOFF.md CONTINUATION_PLAN.md
git commit -m "complete multi-provider vector integration"
git push
```

如果最终实现还需要其他代码提交，可以把上述删除放入同一个最终提交。删除后再确认：

```powershell
git status --short
git ls-tree -r HEAD --name-only | Select-String 'CONTINUATION_(HANDOFF|PLAN)\.md'
```

第二条命令应无输出。随后再将 PR 转为 Ready 或执行合并。任何验收项未通过时，不得提前删除这两份临时文件。
