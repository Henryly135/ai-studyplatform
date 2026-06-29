# 测试指南

本项目测试分为后端 pytest、前端 lint/build、Docker Compose 配置校验和手动 API 流程验证。

English version: [README.en.md](README.en.md)

## 后端测试

运行全部后端测试：

```bash
./scripts/run-backend-tests.sh
```

生成后端覆盖率：

```bash
./scripts/backend-coverage.sh
```

单服务测试示例：

```bash
cd services/identity-service
pytest tests -q
```

重点覆盖：

- 注册、登录、邮箱验证、密码重置。
- 管理员和教师审批。
- 课程、模块、材料和报名。
- 测验编辑、作答和自动提交。
- 论坛、评论、通知。
- AI 聊天、RAG、材料索引、画像更新和测验生成。

## 前端检查

```bash
cd frontend
npm ci
npm run lint
npm run build
```

当前前端以 lint/build 为基础质量门禁，后续可补充页面级 smoke test 和组件测试。

## Docker 与集成检查

校验 compose 配置：

```bash
docker compose --env-file .env.example -f infra/docker-compose.yml config
```

启动后检查服务：

```bash
docker compose --env-file .env -f infra/docker-compose.yml ps
```

健康检查：

```bash
curl http://127.0.0.1:${NGINX_PORT}/api/health
curl http://127.0.0.1:${NGINX_PORT}/api/learning/health
curl http://127.0.0.1:${NGINX_PORT}/api/communication/health
curl http://127.0.0.1:${NGINX_PORT}/api/ai/health
```

## 手动验证流程

建议按以下顺序验证完整系统：

1. 注册学生账号并完成邮箱验证。
2. 注册教师账号，通过管理员审批或邀请链接激活。
3. 教师创建课程、模块并上传材料。
4. 发布模块和课程。
5. 学生报名课程，查看材料并更新学习进度。
6. 教师创建测验，学生作答并查看结果。
7. 学生在课程中使用 AI 聊天。
8. 检查材料索引任务和 RAG 回答。
9. 发布论坛帖子、评论和通知。
10. 查看教师端分析页面。

## 回归记录建议

修复 bug 时记录：

- 问题描述。
- 复现步骤。
- 根因。
- 修改文件。
- 自动化测试或手动验证结果。
- 是否影响已有接口或数据。
