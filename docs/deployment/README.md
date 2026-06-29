# 部署与配置

本项目默认支持本地 Docker Compose 运行，也保留 GitHub Actions 的 CI 与手动部署 workflow。

English version: [README.en.md](README.en.md)

## 本地环境变量

从模板创建本地配置：

```bash
cp .env.example .env
```

关键规则：

- `.env` 不提交。
- `.env.example` 只保留安全占位符。
- 真实密钥放在本地 `.env`、服务器环境变量或 GitHub Secrets。

必须配置的常见字段：

```env
SMTP_USER=your_ses_smtp_username
SMTP_PASS=your_ses_smtp_password
SMTP_FROM=your_email@example.com
DEFAULT_ADMIN_EMAIL=your_email@example.com
DEFAULT_ADMIN_PASSWORD=your-system-admin-password
GEMINI_API_KEY=your_gemini_api_key
```

## Docker Compose

启动：

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

停止并清理卷：

```bash
docker compose --env-file .env -f infra/docker-compose.yml down -v --remove-orphans
```

校验配置：

```bash
docker compose --env-file .env.example -f infra/docker-compose.yml config
```

默认 compose 项目名：

```env
COMPOSE_PROJECT_NAME=ai-studyplatform
```

## GitHub Actions

CI workflow：

- 前端 `npm ci`、lint、build。
- Python 后端服务测试。
- Docker image build。
- Compose config 校验。
- Redis、MinIO 和 nginx 网关基础验证。

部署 workflow：

- `deploy-dev.yml` 默认部署分支：`develop`。
- `deploy-demo.yml` 默认部署分支：`main`。
- 默认远程目录：`~/ai-studyplatform`。
- 服务器连接信息通过 GitHub Secrets 提供。

Secret 名称保持：

- `SERVER_HOST_DEV`
- `SERVER_USER_DEV`
- `SERVER_PORT_DEV`
- `SSH_PRIVATE_KEY_DEV`
- `SERVER_HOST_DEMO`
- `SERVER_USER_DEMO`
- `SERVER_PORT_DEMO`
- `SSH_PRIVATE_KEY_DEMO`

## 部署脚本行为

`scripts/deploy-dev.sh` 和 `scripts/deploy-demo.sh` 的核心流程：

1. 检查远程服务器 `.env`。
2. 使用 Docker Compose 停止旧容器。
3. 重新 build 并启动服务。
4. 输出 compose 服务状态。

## 运维检查

常用检查：

```bash
docker compose --env-file .env -f infra/docker-compose.yml ps
docker compose --env-file .env -f infra/docker-compose.yml logs nginx
docker compose --env-file .env -f infra/docker-compose.yml logs ai-service
```

健康检查：

```bash
curl http://127.0.0.1:${NGINX_PORT}/api/health
curl http://127.0.0.1:${NGINX_PORT}/api/learning/health
curl http://127.0.0.1:${NGINX_PORT}/api/communication/health
curl http://127.0.0.1:${NGINX_PORT}/api/ai/health
```
