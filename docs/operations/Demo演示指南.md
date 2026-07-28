# Demo 演示指南

目标是在 10–12 分钟内展示课程学习闭环、多供应商模型切换和架构取舍。演示只使用 Gemini、GLM、OpenRouter，不展示 DeepSeek。

## 演示前准备

### 1. 启动并检查环境

```bash
cp .env.example .env
docker compose --env-file .env -f infra/docker-compose.yml config --quiet
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker-compose.yml ps
```

不要为了演示执行 `down -v`，除非已经确认可以删除本地数据库和对象存储数据。

### 2. 准备课程

演示课程至少包含：

- 一名可登录的教师和一名已报名学生。
- 一个已发布模块。
- 一份能由平台提取文本的自有资料。
- 一份可发布的测验草稿。
- 一个用于展示讨论功能的论坛主题。

推荐使用仓库中的 [`学习规划示例笔记.md`](../demo/fixtures/学习规划示例笔记.md) 作为小型检索资料，避免依赖未提交的外部 PDF 或视频。

### 3. 配置 Provider

使用管理员账号进入 AI 管理区域：

1. 分别录入 Gemini、GLM、OpenRouter API Key；保存并启用凭据会自动排队历史资料回填。
2. 对每个 Provider 执行健康检查。
3. 选择演示所需的默认聊天模型。
4. 确认模型目录只显示 Gemini、GLM 和 OpenRouter。
5. 等待演示课程在三套向量模型下完成回填。

Key 只能在管理员界面录入，不应出现在截图、终端历史、浏览器录屏或仓库文件中。

### 4. 执行预检

获取管理员访问令牌后，在 Linux/macOS 确认已安装 `curl` 与 `jq`，然后执行：

```bash
export DEMO_ACCESS_TOKEN='replace-with-admin-access-token'
export DEMO_COURSE_UUID='replace-with-demo-course-uuid'
bash scripts/demo-preflight.sh
```

Windows PowerShell：

```powershell
$env:DEMO_ACCESS_TOKEN = "replace-with-admin-access-token"
$env:DEMO_COURSE_UUID = "replace-with-demo-course-uuid"
.\scripts\demo-preflight.ps1
```

管理员令牌与课程 UUID 都是必填项；缺少课程 UUID 时预检会直接失败，避免跳过 RAG 覆盖检查后误报 Demo 已就绪。

远程 Demo 环境可额外设置：

```bash
export DEMO_BASE_URL='https://demo.example.com'
```

预检验证：

- 身份、学习、通信、AI 服务健康。
- 模型目录恰好包含 Gemini、GLM、OpenRouter。
- 三个 Provider 已配置且健康。
- 所有聊天模型都有 1024 维配对向量模型。
- 指定课程的可用模型均达到 RAG 就绪和 100% 索引覆盖。

预检失败时不要继续对外演示。先查看 Provider 健康状态、索引任务错误和 worker 日志。

## 推荐演示流程

### 1. 产品与架构，1 分钟

用一句话定位产品：课程、资料、测验、学习进度和讨论都处于同一权限边界内，AI 使用课程资料提供可追溯的辅助。

展示两个设计点：

- 用户选择聊天模型，后端自动派生对应的 Embedding。
- 同一知识块有 Gemini、GLM、OpenRouter 三套向量，切换模型不会临时重建资料或混用向量空间。

### 2. 学习者课程体验，3 分钟

1. 学生打开演示课程和已发布模块。
2. 查看课程资料和学习进度。
3. 向课程助手提出一个必须依赖资料才能回答的问题。
4. 展示回答来源和当前聊天/向量模型组合。

问题应提前验证答案确实存在于演示资料中，避免使用开放式常识问题。

### 3. 三 Provider 切换，3 分钟

在同一课程与同一问题上依次选择：

```text
Gemini → GLM → OpenRouter
```

每次切换后指出：

- 前端只切换聊天模型。
- 页面自动显示配对向量模型。
- 响应中的实际聊天模型与向量模型和页面一致。
- 索引覆盖率保持就绪，没有重新上传或重新切分资料。

演示重点是调用隔离和一致性，不比较不同模型的主观答案质量。

### 4. 教师工作流，2 分钟

1. 教师打开同一模块。
2. 基于已索引资料生成测验草稿。
3. 检查题目、选项、正确答案和解析。
4. 修改一处内容并发布。

说明后台测验使用管理员默认模型组合，不继承某个学生在聊天侧栏中的个人选择。

### 5. 管理与治理，2 分钟

管理员页面展示：

- Provider Key 只显示脱敏状态。
- 三个 Provider 的聊天与 Embedding 健康状态。
- 默认模型组合。
- 每套向量的索引覆盖率。
- 失败调用与索引任务的脱敏审计。

不要在演示中点击删除 Key 或切换生产默认模型。

### 6. 收尾，1 分钟

总结三个设计原则：

1. Provider Adapter 将业务流程与供应商 API 解耦。
2. 聊天模型与向量模型由受控目录配对，前端不能制造不兼容组合。
3. 多向量索引以额外存储和首次回填成本换取即时、安全的 Provider 切换。

## 演示降级方案

- 某个 Provider 临时不可用：展示其明确的不可用状态，继续使用另外两个 Provider；不要伪造成功结果。
- 某套向量仍在回填：展示覆盖率和任务状态，不把普通聊天描述为 RAG。
- 外网不稳定：提前准备不含 Key 和隐私数据的截图或录屏，但要说明这是预录结果。
- AI 测验生成失败：保留一份已生成草稿，说明实时调用失败原因和重试边界。

## Go / No-Go

满足以下条件才开始演示：

- `demo-preflight` 通过。
- 三个 Provider 的模型切换至少手工走查一次。
- 演示问题、引用来源和测验结果已经检查。
- 浏览器、终端和日志中没有完整 API Key。
- Demo 账号和素材不包含真实学生数据。
- 准备了一个不依赖实时 Provider 的降级展示材料。
