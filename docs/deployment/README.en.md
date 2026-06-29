# Deployment and Configuration

The project supports local Docker Compose runtime and keeps GitHub Actions for CI and manual deployment workflows.

中文版本: [README.md](README.md)

## Local Environment Variables

Create local config from the template:

```bash
cp .env.example .env
```

Rules:

- Do not commit `.env`.
- Keep only safe placeholders in `.env.example`.
- Put real secrets in local `.env`, server environment variables, or GitHub Secrets.

Common required fields:

```env
SMTP_USER=your_ses_smtp_username
SMTP_PASS=your_ses_smtp_password
SMTP_FROM=your_email@example.com
DEFAULT_ADMIN_EMAIL=your_email@example.com
DEFAULT_ADMIN_PASSWORD=your-system-admin-password
GEMINI_API_KEY=your_gemini_api_key
```

## Docker Compose

Start:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
```

Stop and remove volumes:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down -v --remove-orphans
```

Validate config:

```bash
docker compose --env-file .env.example -f infra/docker-compose.yml config
```

Default compose project name:

```env
COMPOSE_PROJECT_NAME=ai-studyplatform
```

## GitHub Actions

CI workflow:

- Frontend `npm ci`, lint, and build.
- Python backend service tests.
- Docker image build.
- Compose config validation.
- Basic Redis, MinIO, and nginx gateway checks.

Deployment workflows:

- `deploy-dev.yml` default branch: `develop`.
- `deploy-demo.yml` default branch: `main`.
- Default remote directory: `~/ai-studyplatform`.
- Server connection details are provided through GitHub Secrets.

Secret names remain:

- `SERVER_HOST_DEV`
- `SERVER_USER_DEV`
- `SERVER_PORT_DEV`
- `SSH_PRIVATE_KEY_DEV`
- `SERVER_HOST_DEMO`
- `SERVER_USER_DEMO`
- `SERVER_PORT_DEMO`
- `SSH_PRIVATE_KEY_DEMO`

## Deploy Script Behavior

`scripts/deploy-dev.sh` and `scripts/deploy-demo.sh`:

1. Check remote `.env`.
2. Stop old containers with Docker Compose.
3. Rebuild and restart services.
4. Print compose service status.

## Operations Checks

Common checks:

```bash
docker compose --env-file .env -f infra/docker-compose.yml ps
docker compose --env-file .env -f infra/docker-compose.yml logs nginx
docker compose --env-file .env -f infra/docker-compose.yml logs ai-service
```

Health checks:

```bash
curl http://127.0.0.1:${NGINX_PORT}/api/health
curl http://127.0.0.1:${NGINX_PORT}/api/learning/health
curl http://127.0.0.1:${NGINX_PORT}/api/communication/health
curl http://127.0.0.1:${NGINX_PORT}/api/ai/health
```
